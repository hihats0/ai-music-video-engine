from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import comfy_api
from .core import ROOT, UserError, load_yaml, now_iso, save_yaml, scene_path
from .generation import load_pipeline, selected_frame
from .models import model_status
from .multicast import build_prompts, validate_scene
from .workflows import build_wan22_i2v_prompt, validate_and_adapt_prompt


def _lock_path() -> Path:
    return ROOT / "runtime" / "locks" / "gpu.lock"


def _acquire_lock(project: str, scene: str, retry: bool) -> None:
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise UserError("Başka bir GPU işi çalışıyor. clipctl.bat job status ile kontrol et.")
    path.write_text(
        json.dumps(
            {
                "kind": "wan22_group_video",
                "project": project,
                "scene": scene,
                "retry": retry,
                "started_at": now_iso(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _uploaded_name(response: dict[str, Any]) -> str:
    folder = str(response.get("subfolder", "")).strip("/\\")
    name = str(response["name"])
    return f"{folder}/{name}" if folder else name


def _queue_progress(queue: dict[str, Any]) -> None:
    running = queue.get("queue_running", [])
    pending = queue.get("queue_pending", [])
    print(
        f"[BİLGİ] ComfyUI kuyruğu — çalışan: {len(running)}, bekleyen: {len(pending)}",
        flush=True,
    )


def _download_outputs(history_item: dict[str, Any], destination: Path) -> list[Path]:
    entries = comfy_api.extract_output_files(history_item)
    if not entries:
        raise UserError("Group video tamamlandı fakat indirilebilir çıktı bulunamadı.")
    destination.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for index, info in enumerate(entries, start=1):
        suffix = Path(info["filename"]).suffix or ".bin"
        target = destination / f"output_{index:02d}{suffix}"
        comfy_api.download_output(info, target)
        outputs.append(target)
    return outputs


def _ffprobe(path: Path) -> dict[str, Any]:
    command = shutil.which("ffprobe")
    if not command:
        return {"available": False}
    completed = subprocess.run(
        [
            command,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height,codec_type,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return {"available": True, "ok": False, "stderr": completed.stderr[-2000:]}
    try:
        return {"available": True, "ok": True, "data": json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"available": True, "ok": False, "stdout": completed.stdout[-2000:]}


def generate_group_video(
    project: str,
    scene: str,
    *,
    retry: bool = False,
    journal: Any | None = None,
) -> dict[str, Any]:
    report = validate_scene(project, scene)
    if not report["ready"]:
        raise UserError("Group sahne hazır değil:\n- " + "\n- ".join(report["errors"]))
    if report["cast_size"] < 2:
        raise UserError("Group video komutu en az iki kişilik sahne gerektirir.")
    frame = selected_frame(project, scene)
    models = model_status()
    if not models["ready"]:
        missing = [Path(item["path"]).name for item in models["files"] if not item["ok"]]
        raise UserError("Wan model paketi eksik: " + ", ".join(missing))
    api = comfy_api.status()
    if not api.get("online"):
        raise UserError("ComfyUI API çalışmıyor. START_ENGINE.bat dosyasını çalıştır.")

    config = load_pipeline()
    video_cfg = dict(config.get("video", {}))
    recovery = dict(config.get("recovery", {}))
    data = report["scene"]
    seconds = float(data.get("generation", {}).get("duration_seconds", 4))
    if retry:
        width = int(recovery.get("retry_width", 704))
        height = int(recovery.get("retry_height", 400))
        retry_frames = int(recovery.get("retry_frames", 81))
        fps = int(video_cfg.get("fps", 24))
        seconds = retry_frames / fps
    else:
        width = int(data.get("generation", {}).get("width") or video_cfg.get("width", 832))
        height = int(data.get("generation", {}).get("height") or video_cfg.get("height", 480))
        fps = int(video_cfg.get("fps", 24))

    prompts = build_prompts(project, scene)
    positive = prompts["global_positive"] + (
        ", preserve the exact approved group composition and character count, "
        "each person remains in their assigned position and clothing, subtle independent body movement, "
        "stable faces, coherent temporal lighting, restrained music-video performance, single continuous shot"
    )
    negative = prompts["negative"] + (
        ", person entering or leaving frame, character teleportation, identity drift, face swapping, "
        "outfit morphing, aggressive dancing, fast arm crossing, camera whip, severe motion blur"
    )
    upload = comfy_api.upload_image(frame, subfolder=f"clipctl/{project}/{scene}/group_video")
    uploaded = _uploaded_name(upload)
    seed_value = data.get("generation", {}).get("seed", "random")
    seed = None if seed_value in (None, "", "random") else int(seed_value)
    prefix = f"clipctl/{project}/{scene}/group_video_{now_iso().replace(':', '-')}"
    workflow = build_wan22_i2v_prompt(
        uploaded_image=uploaded,
        positive=positive,
        negative=negative,
        width=width,
        height=height,
        seconds=seconds,
        fps=fps,
        steps=max(22, int(video_cfg.get("steps", 20))),
        cfg=min(5.0, float(video_cfg.get("cfg", 5.0))),
        sampler=str(video_cfg.get("sampler", "uni_pc")),
        scheduler=str(video_cfg.get("scheduler", "simple")),
        shift=float(video_cfg.get("shift", 8.0)),
        seed=seed,
        filename_prefix=prefix,
    )
    workflow = validate_and_adapt_prompt(workflow)

    generation_dir = scene_path(project, scene) / "generations" / (
        "group_" + now_iso().replace(":", "-")
    )
    generation_dir.mkdir(parents=True, exist_ok=True)
    (generation_dir / "prompt_api.json").write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (generation_dir / "prompt.txt").write_text(
        positive + "\n\nNEGATIVE:\n" + negative + "\n", encoding="utf-8"
    )
    metadata = {
        "project": project,
        "scene": scene,
        "kind": "wan22_group_video",
        "cast_size": report["cast_size"],
        "start_frame": str(frame.relative_to(ROOT)),
        "retry_profile": retry,
        "resolution": {"width": width, "height": height},
        "fps": fps,
        "seconds": seconds,
        "created_at": now_iso(),
    }
    (generation_dir / "metadata_before.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _acquire_lock(project, scene, retry)
    prompt_id = "not-queued"
    try:
        queued = comfy_api.queue_prompt(workflow, extra_data={"clipctl": metadata})
        prompt_id = str(queued["prompt_id"])
        if journal:
            journal.event(
                "group_video.queued",
                project=project,
                scene=scene,
                prompt_id=prompt_id,
                cast_size=report["cast_size"],
                retry=retry,
            )
        history = comfy_api.wait_for_prompt(
            prompt_id,
            timeout=float(video_cfg.get("timeout_seconds", 10800)),
            on_progress=_queue_progress,
        )
        (generation_dir / "history.json").write_text(
            json.dumps(history, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        outputs = _download_outputs(history, generation_dir)
    finally:
        _lock_path().unlink(missing_ok=True)

    video_files = [
        path for path in outputs if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}
    ]
    selected = video_files[0] if video_files else outputs[0]
    result = {
        "prompt_id": prompt_id,
        "generation_dir": str(generation_dir.relative_to(ROOT)),
        "outputs": [str(path.relative_to(ROOT)) for path in outputs],
        "selected": str(selected.relative_to(ROOT)),
        "ffprobe": _ffprobe(selected),
        "retry_profile": retry,
        "cast_size": report["cast_size"],
    }
    (generation_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    scene_file = scene_path(project, scene) / "scene.yaml"
    scene_data = load_yaml(scene_file)
    scene_data.setdefault("approval", {})["selected_video"] = str(
        selected.relative_to(ROOT)
    ).replace("\\", "/")
    scene_data.setdefault("scene", {})["status"] = "group_video_generated"
    save_yaml(scene_file, scene_data)
    return result
