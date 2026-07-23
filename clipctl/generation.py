from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from . import comfy_api
from .core import (
    ROOT,
    IMAGE_EXTENSIONS,
    UserError,
    identity_check,
    load_yaml,
    now_iso,
    save_yaml,
    scene_check,
    scene_path,
)
from .models import model_status
from .workflows import build_wan22_i2v_prompt, validate_and_adapt_prompt


DEFAULT_NEGATIVE = (
    "low quality, worst quality, blurry, jpeg artifacts, deformed face, "
    "distorted eyes, asymmetrical eyes, extra fingers, malformed hands, "
    "duplicate person, multiple main faces, face occlusion, extreme head turn, "
    "text, subtitles, watermark, logo, frozen frame, excessive flicker"
)


def load_pipeline() -> dict[str, Any]:
    path = ROOT / "configs" / "pipeline.yaml"
    if not path.exists():
        raise UserError("configs/pipeline.yaml bulunamadı.")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise UserError("pipeline.yaml geçersiz.")
    return data


def build_scene_prompt(data: dict[str, Any]) -> tuple[str, str]:
    composition = data.get("composition", {})
    lighting = data.get("lighting", {})
    movement = data.get("movement", {})
    style = data.get("style", {})
    identity = data.get("identity", {})
    rules = data.get("rules", {})
    pieces = [
        "Cinematic music video shot",
        f"one main performer, identity reference {identity.get('character_id', 'performer')}",
        f"location: {composition.get('location', '')}",
        f"time: {composition.get('time_of_day', '')}",
        f"wardrobe: {composition.get('wardrobe', '')}",
        f"shot type: {composition.get('shot_type', 'medium close-up')}",
        f"camera angle: {composition.get('camera_angle', 'eye level')}",
        f"framing: {composition.get('framing', 'centered')}",
        f"character action: {movement.get('character_action', '')}",
        f"camera movement: {movement.get('camera_motion', 'static')}, strength {movement.get('camera_motion_strength', 'low')}",
        f"body motion: {movement.get('body_motion_strength', 'low')}",
        f"head motion: {movement.get('head_motion_strength', 'low')}",
        f"lighting: {lighting.get('style', 'cinematic')}, key light {lighting.get('key_light', '')}, background light {lighting.get('background_light', '')}, contrast {lighting.get('contrast', 'medium')}",
        f"visual style: {style.get('visual_style', 'cinematic')}",
        f"mood: {style.get('mood', '')}",
        f"color palette: {style.get('color_description', '')}",
        f"film texture: {style.get('film_texture', 'subtle')}",
        "natural facial motion, stable facial structure, coherent body anatomy",
        "single continuous shot, 16:9",
    ]
    positive = ". ".join(str(piece).strip(" .") for piece in pieces if str(piece).strip(" .")) + "."
    negatives = [DEFAULT_NEGATIVE]
    if not rules.get("allow_fast_head_rotation", False):
        negatives.append("fast head rotation")
    if not rules.get("allow_face_occlusion", False):
        negatives.append("covered face, hand over face")
    if not rules.get("allow_extreme_profile", False):
        negatives.append("extreme side profile")
    if not rules.get("allow_multiple_main_faces", False):
        negatives.append("crowd near camera, second prominent face")
    return positive, ", ".join(negatives)


def _candidate_dir(project: str, scene: str) -> Path:
    path = scene_path(project, scene) / "frames"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _selected_dir(project: str, scene: str) -> Path:
    path = scene_path(project, scene) / "selected"
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_frame_candidates(project: str, scene: str) -> list[Path]:
    check = scene_check(project, scene)
    if not check["identity"]:
        raise UserError("scene.yaml içinde identity.character_id doldurulmalı.")
    identity_name = str(check["identity"])
    identity_result = identity_check(identity_name)
    if not identity_result["permission"]:
        raise UserError(
            "Kimlik kullanım izni onaylanmamış. "
            f"identities/{identity_name}/identity.yaml içinde permission.confirmed: true yap."
        )
    images: list[Path] = identity_result["images"]
    if not images:
        raise UserError(
            f"Referans görsel yok: identities/{identity_name}/source klasörüne "
            "en az bir net fotoğraf koy."
        )
    destination = _candidate_dir(project, scene)
    copied: list[Path] = []
    for index, source in enumerate(images, start=1):
        target = destination / f"identity_reference_{index:02d}{source.suffix.lower()}"
        shutil.copy2(source, target)
        copied.append(target)

    data = check["data"]
    references = data.get("references", {})
    for label in ("pose_image", "composition_image", "wardrobe_image", "previous_scene_frame"):
        value = references.get(label)
        if not value:
            continue
        source = Path(str(value))
        if not source.is_absolute():
            source = ROOT / source
        if source.exists() and source.is_file() and source.suffix.lower() in IMAGE_EXTENSIONS:
            target = destination / f"{label}{source.suffix.lower()}"
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def list_frame_candidates(project: str, scene: str) -> list[Path]:
    return sorted(path for path in _candidate_dir(project, scene).iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def approve_frame(project: str, scene: str, candidate: str) -> Path:
    spath = scene_path(project, scene)
    if not spath.exists():
        raise UserError(f"Sahne bulunamadı: {project}/{scene}")
    raw = Path(candidate)
    choices = [raw, ROOT / raw, _candidate_dir(project, scene) / raw.name, spath / raw]
    source = next((path for path in choices if path.exists() and path.is_file()), None)
    if source is None or source.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UserError(f"Onaylanacak görsel bulunamadı: {candidate}")
    selected = _selected_dir(project, scene) / f"start_frame{source.suffix.lower()}"
    shutil.copy2(source, selected)
    data = load_yaml(spath / "scene.yaml")
    data.setdefault("approval", {})["start_frame_approved"] = True
    data["approval"]["selected_start_frame"] = str(selected.relative_to(ROOT)).replace("\\", "/")
    data["scene"]["status"] = "frame_approved"
    save_yaml(spath / "scene.yaml", data)
    return selected


def selected_frame(project: str, scene: str) -> Path:
    data = load_yaml(scene_path(project, scene) / "scene.yaml")
    approval = data.get("approval", {})
    value = approval.get("selected_start_frame")
    if value:
        candidate = Path(str(value))
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.exists():
            return candidate
    found = sorted(_selected_dir(project, scene).glob("start_frame.*"))
    if found:
        return found[0]
    raise UserError(
        "Onaylı başlangıç karesi yok. Önce:\n"
        f"clipctl.bat frame prepare {project} {scene}\n"
        f"clipctl.bat frame approve {project} {scene} <dosya>"
    )


def _lock_file() -> Path:
    return ROOT / "runtime" / "locks" / "gpu.lock"


def _acquire_lock(payload: dict[str, Any]) -> None:
    path = _lock_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise UserError(
            "GPU üzerinde başka iş kilidi var. "
            "clipctl.bat job status ile kontrol et; süreç yoksa clipctl.bat job cancel kullan."
        )
    path.write_text(json.dumps({"started_at": now_iso(), **payload}, ensure_ascii=False, indent=2), encoding="utf-8")


def _release_lock() -> None:
    _lock_file().unlink(missing_ok=True)


def _uploaded_name(response: dict[str, Any]) -> str:
    name = str(response["name"])
    subfolder = str(response.get("subfolder", "")).strip("/\\")
    return f"{subfolder}/{name}" if subfolder else name


def _queue_progress(queue: dict[str, Any]) -> None:
    running = queue.get("queue_running", [])
    pending = queue.get("queue_pending", [])
    print(f"[BİLGİ] ComfyUI kuyruğu — çalışan: {len(running)}, bekleyen: {len(pending)}", flush=True)


def _download_history_outputs(history_item: dict[str, Any], destination: Path) -> list[Path]:
    outputs = comfy_api.extract_output_files(history_item)
    if not outputs:
        raise UserError(
            "ComfyUI işi tamamlandı fakat indirilebilir çıktı bulunamadı. "
            "Tanı paketinde history ve server.log kontrol edilmeli."
        )
    destination.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for index, info in enumerate(outputs, start=1):
        suffix = Path(info["filename"]).suffix or ".bin"
        target = destination / f"output_{index:02d}{suffix}"
        comfy_api.download_output(info, target)
        downloaded.append(target)
    return downloaded


def _ffprobe(path: Path) -> dict[str, Any]:
    command = shutil.which("ffprobe")
    if not command:
        return {"available": False}
    completed = subprocess.run(
        [command, "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode != 0:
        return {"available": True, "ok": False, "stderr": completed.stderr[-2000:]}
    try:
        return {"available": True, "ok": True, "data": json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"available": True, "ok": False, "stdout": completed.stdout[-2000:]}


def generate_video(project: str, scene: str, *, retry: bool = False, journal: Any | None = None) -> dict[str, Any]:
    check = scene_check(project, scene)
    if not check["ready"]:
        reasons = list(check["missing"])
        if check["identity"] and not check["identity_exists"]:
            reasons.append(f"kimlik yok: {check['identity']}")
        raise UserError("Sahne hazır değil: " + ", ".join(reasons))
    frame = selected_frame(project, scene)
    models = model_status()
    if not models["ready"]:
        missing = [Path(item["path"]).name for item in models["files"] if not item["ok"]]
        raise UserError("Wan model paketi eksik: " + ", ".join(missing) + "\nKurmak için: clipctl.bat model install")
    api = comfy_api.status()
    if not api.get("online"):
        raise UserError("ComfyUI API çalışmıyor. START_ENGINE.bat dosyasını çalıştır. " + f"Ayrıntı: {api.get('reason')}")

    config = load_pipeline()
    video_cfg = dict(config.get("video", {}))
    recovery = dict(config.get("recovery", {}))
    scene_data = check["data"]
    seconds = float(scene_data.get("generation", {}).get("duration_seconds") or video_cfg.get("duration_seconds", 4))
    if retry:
        video_cfg["width"] = recovery.get("retry_width", 704)
        video_cfg["height"] = recovery.get("retry_height", 400)
        video_cfg["frames"] = recovery.get("retry_frames", 81)
        seconds = float(video_cfg["frames"]) / float(video_cfg.get("fps", 24))

    positive, negative = build_scene_prompt(scene_data)
    upload = comfy_api.upload_image(frame, subfolder=f"clipctl/{project}/{scene}")
    uploaded = _uploaded_name(upload)
    seed_value = scene_data.get("generation", {}).get("seed", "random")
    seed = None if seed_value in (None, "", "random") else int(seed_value)
    prefix = f"clipctl/{project}/{scene}/{now_iso().replace(':', '-')}"
    prompt = build_wan22_i2v_prompt(
        uploaded_image=uploaded, positive=positive, negative=negative,
        width=int(video_cfg.get("width", 832)), height=int(video_cfg.get("height", 480)),
        seconds=seconds, fps=int(video_cfg.get("fps", 24)), steps=int(video_cfg.get("steps", 20)),
        cfg=float(video_cfg.get("cfg", 5.0)), sampler=str(video_cfg.get("sampler", "uni_pc")),
        scheduler=str(video_cfg.get("scheduler", "simple")), shift=float(video_cfg.get("shift", 8.0)),
        seed=seed, filename_prefix=prefix,
    )
    prompt = validate_and_adapt_prompt(prompt)

    generation_dir = scene_path(project, scene) / "generations" / now_iso().replace(":", "-")
    generation_dir.mkdir(parents=True, exist_ok=True)
    (generation_dir / "prompt_api.json").write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    (generation_dir / "prompt.txt").write_text(positive + "\n\nNEGATIVE:\n" + negative + "\n", encoding="utf-8")
    metadata = {
        "project": project, "scene": scene, "start_frame": str(frame.relative_to(ROOT)),
        "uploaded": uploaded, "retry_profile": retry, "created_at": now_iso(), "video_config": video_cfg,
    }
    (generation_dir / "metadata_before.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    _acquire_lock({"project": project, "scene": scene, "kind": "wan22_video", "retry": retry})
    prompt_id = "not-queued"
    try:
        queued = comfy_api.queue_prompt(prompt, extra_data={"clipctl": metadata})
        prompt_id = str(queued["prompt_id"])
        if journal:
            journal.event("comfy.prompt.queued", prompt_id=prompt_id, retry=retry)
        history_item = comfy_api.wait_for_prompt(
            prompt_id, timeout=float(video_cfg.get("timeout_seconds", 10800)), on_progress=_queue_progress,
        )
        (generation_dir / "history.json").write_text(json.dumps(history_item, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        outputs = _download_history_outputs(history_item, generation_dir)
    finally:
        _release_lock()

    video_files = [path for path in outputs if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}]
    selected = video_files[0] if video_files else outputs[0]
    probe = _ffprobe(selected)
    result = {
        "prompt_id": prompt_id, "generation_dir": str(generation_dir),
        "outputs": [str(path) for path in outputs], "selected": str(selected),
        "ffprobe": probe, "retry_profile": retry,
    }
    (generation_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    data = load_yaml(scene_path(project, scene) / "scene.yaml")
    data.setdefault("approval", {})["selected_video"] = str(selected.relative_to(ROOT)).replace("\\", "/")
    data["scene"]["status"] = "video_generated"
    save_yaml(scene_path(project, scene) / "scene.yaml", data)
    return result
