from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .core import ROOT, UserError, load_yaml, now_iso, scene_path
from .media_tools import find_ffmpeg
from .multicast import validate_scene
from .postprocess import find_video

CONFIG = ROOT / "configs" / "lipsync.yaml"


def load_config() -> dict[str, Any]:
    if not CONFIG.is_file():
        raise UserError("configs/lipsync.yaml bulunamadı.")
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise UserError("configs/lipsync.yaml geçersiz.")
    return data


def _root(config: dict[str, Any]) -> Path:
    return ROOT / str(config.get("root", "tools/MuseTalk"))


def _python(config: dict[str, Any]) -> Path:
    return ROOT / str(config.get("python", "tools/MuseTalk/.venv/Scripts/python.exe"))


def _model_paths(config: dict[str, Any]) -> dict[str, Path]:
    root = _root(config)
    models = config.get("models", {})
    if not isinstance(models, dict):
        return {}
    return {str(name): root / str(relative) for name, relative in models.items()}


def status() -> dict[str, Any]:
    config = load_config()
    root = _root(config)
    python = _python(config)
    models = _model_paths(config)
    model_status = {
        name: {"path": str(path), "exists": path.is_file()}
        for name, path in models.items()
    }
    ffmpeg = find_ffmpeg()
    repository_ready = (root / "scripts" / "inference.py").is_file()
    ready = bool(
        root.is_dir()
        and repository_ready
        and python.is_file()
        and ffmpeg
        and model_status
        and all(item["exists"] for item in model_status.values())
    )
    return {
        "backend": config.get("backend"),
        "ready": ready,
        "root": str(root),
        "repository_ready": repository_ready,
        "python": str(python),
        "python_ready": python.is_file(),
        "ffmpeg": str(ffmpeg) if ffmpeg else None,
        "models": model_status,
        "installation_note": (
            "MuseTalk ayrı bir Python 3.10 ortamı ve kendi model paketini gerektirir. "
            "Hazır değilse group/solo video üretimi etkilenmez; yalnızca lipsync komutu kullanılamaz."
        ),
    }


def _resolve_path(value: Any, *, label: str) -> Path:
    if not value:
        raise UserError(f"{label} gerekli.")
    path = Path(str(value))
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise UserError(f"{label} bulunamadı: {path}")
    return path


def _run(command: list[str], log: Path, *, cwd: Path | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND:\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT:\n"
        + completed.stdout + "\n\nSTDERR:\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise UserError(
            f"Komut başarısız. Kod: {completed.returncode}. Log: {log.relative_to(ROOT)}"
        )


def _prepare_inputs(
    source_video: Path,
    source_audio: Path,
    run_dir: Path,
    *,
    fps: int,
    start_seconds: float | None,
    end_seconds: float | None,
) -> tuple[Path, Path]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("MuseTalk hazırlığı için FFmpeg bulunamadı.")
    video = run_dir / "input_25fps.mp4"
    audio = run_dir / "driving_audio.wav"
    video_command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(source_video), "-vf", f"fps={fps}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-an", str(video),
    ]
    _run(video_command, run_dir / "prepare_video.log")

    audio_command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "warning",
    ]
    if start_seconds is not None:
        audio_command.extend(["-ss", f"{start_seconds:.3f}"])
    audio_command.extend(["-i", str(source_audio)])
    if end_seconds is not None:
        duration = end_seconds - (start_seconds or 0.0)
        if duration <= 0:
            raise UserError("lipsync.end_seconds, start_seconds değerinden büyük olmalı.")
        audio_command.extend(["-t", f"{duration:.3f}"])
    audio_command.extend(["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)])
    _run(audio_command, run_dir / "prepare_audio.log")
    return video, audio


def prepare(project: str, scene: str) -> dict[str, Any]:
    report = validate_scene(project, scene)
    if not report["ready"]:
        raise UserError("Solo lipsync sahnesi hazır değil:\n- " + "\n- ".join(report["errors"]))
    if report["cast_size"] != 1:
        raise UserError("Lip-sync yalnızca tek karakterli solo sahnede çalışır.")
    data = report["scene"]
    lipsync = data.get("lipsync", {})
    if not bool(lipsync.get("enabled", False)):
        raise UserError("scene.yaml içinde lipsync.enabled: true olmalı.")
    target = str(lipsync.get("target_identity") or "").strip()
    scene_identity = str(report["cast"][0].get("identity_id") or report["cast"][0].get("id"))
    if target and target != scene_identity:
        raise UserError(
            f"lipsync.target_identity sahnedeki tek kimlikle aynı olmalı: {scene_identity}"
        )

    config = load_config()
    fps = int(config.get("recommended_input_fps", 25))
    source_video = find_video(project, scene)
    source_audio = _resolve_path(lipsync.get("source_audio"), label="lipsync.source_audio")
    start = lipsync.get("start_seconds")
    end = lipsync.get("end_seconds")
    start_seconds = float(start) if start not in (None, "") else None
    end_seconds = float(end) if end not in (None, "") else None

    run_dir = scene_path(project, scene) / "lipsync" / ("prepared_" + now_iso().replace(":", "-"))
    run_dir.mkdir(parents=True, exist_ok=True)
    prepared_video, prepared_audio = _prepare_inputs(
        source_video,
        source_audio,
        run_dir,
        fps=fps,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )
    inference = config.get("inference", {})
    task = {
        "clipctl_scene": {
            "video_path": str(prepared_video.resolve()),
            "audio_path": str(prepared_audio.resolve()),
            "bbox_shift": int(inference.get("bbox_shift", 0)),
        }
    }
    task_file = run_dir / "musetalk_inference.yaml"
    task_file.write_text(
        yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    manifest = {
        "project": project,
        "scene": scene,
        "target_identity": scene_identity,
        "source_video": str(source_video.relative_to(ROOT)),
        "source_audio": str(source_audio),
        "prepared_video": str(prepared_video.relative_to(ROOT)),
        "prepared_audio": str(prepared_audio.relative_to(ROOT)),
        "inference_config": str(task_file.relative_to(ROOT)),
        "fps": fps,
        "created_at": now_iso(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"run_dir": str(run_dir.relative_to(ROOT)), **manifest}


def build_command(prepared_dir: Path) -> list[str]:
    config = load_config()
    root = _root(config)
    python = _python(config)
    models = _model_paths(config)
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("FFmpeg bulunamadı.")
    inference_file = prepared_dir / "musetalk_inference.yaml"
    if not inference_file.is_file():
        raise UserError(f"MuseTalk inference config bulunamadı: {inference_file}")
    result_dir = prepared_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    return [
        str(python),
        "-m", str(config.get("inference", {}).get("module", "scripts.inference")),
        "--inference_config", str(inference_file),
        "--result_dir", str(result_dir),
        "--unet_model_path", str(models["unet"]),
        "--unet_config", str(models["unet_config"]),
        "--version", str(config.get("inference", {}).get("version", "v15")),
        "--ffmpeg_path", str(Path(ffmpeg).parent),
    ]


def run(project: str, scene: str, prepared: str | None = None) -> dict[str, Any]:
    state = status()
    if not state["ready"]:
        missing = [name for name, item in state["models"].items() if not item["exists"]]
        raise UserError(
            "MuseTalk hazır değil. Eksik: "
            + ", ".join(
                part for part in (
                    "repository" if not state["repository_ready"] else "",
                    "python environment" if not state["python_ready"] else "",
                    "models=" + "/".join(missing) if missing else "",
                ) if part
            )
        )
    if prepared:
        prepared_dir = Path(prepared)
        if not prepared_dir.is_absolute():
            prepared_dir = ROOT / prepared_dir
    else:
        prepared_info = prepare(project, scene)
        prepared_dir = ROOT / str(prepared_info["run_dir"])
    prepared_dir = prepared_dir.resolve()
    command = build_command(prepared_dir)
    log = prepared_dir / "musetalk.log"
    _run(command, log, cwd=_root(load_config()))
    outputs = sorted((prepared_dir / "results").glob("**/*.mp4"))
    if not outputs:
        raise UserError(
            f"MuseTalk tamamlandı fakat MP4 bulunamadı. Log: {log.relative_to(ROOT)}"
        )
    selected = outputs[-1]
    result = {
        "prepared_dir": str(prepared_dir.relative_to(ROOT)),
        "output": str(selected.relative_to(ROOT)),
        "log": str(log.relative_to(ROOT)),
        "source_preserved": True,
    }
    (prepared_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    scene_file = scene_path(project, scene) / "scene.yaml"
    data = load_yaml(scene_file)
    data.setdefault("lipsync", {})["selected_output"] = str(
        selected.relative_to(ROOT)
    ).replace("\\", "/")
    data.setdefault("scene", {})["status"] = "lipsync_generated"
    scene_file.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return result
