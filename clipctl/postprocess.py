from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .core import ROOT, UserError, load_yaml, now_iso, scene_path
from .media_tools import find_ffmpeg


def _optional_tool_candidates() -> dict[str, list[Path]]:
    return {
        "realesrgan": [
            ROOT / "tools" / "Real-ESRGAN" / "realesrgan-ncnn-vulkan.exe",
            ROOT / "tools" / "realesrgan" / "realesrgan-ncnn-vulkan.exe",
        ],
        "rife": [
            ROOT / "tools" / "RIFE" / "rife-ncnn-vulkan.exe",
            ROOT / "tools" / "rife" / "rife-ncnn-vulkan.exe",
        ],
    }


def tool_status() -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    optional: dict[str, str | None] = {}
    for name, candidates in _optional_tool_candidates().items():
        found = next((path for path in candidates if path.is_file()), None)
        optional[name] = str(found) if found else None
    return {
        "ffmpeg": str(ffmpeg) if ffmpeg else None,
        "baseline_ready": ffmpeg is not None,
        "optional_learned_upscale": optional["realesrgan"],
        "optional_rife": optional["rife"],
        "ready": ffmpeg is not None,
    }


def find_video(project: str, scene: str) -> Path:
    spath = scene_path(project, scene)
    data = load_yaml(spath / "scene.yaml")
    value = data.get("approval", {}).get("selected_video")
    paths: list[Path] = []
    if value:
        path = Path(str(value))
        paths.append(path if path.is_absolute() else ROOT / path)
    paths.extend(sorted((spath / "selected").glob("*.mp4"), reverse=True))
    paths.extend(sorted((spath / "generations").glob("**/*.mp4"), reverse=True))
    for path in paths:
        if path.is_file():
            return path
    raise UserError("İşlenecek MP4 bulunamadı.")


def _even(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback
    number = max(64, number)
    return number if number % 2 == 0 else number - 1


def process_video(project: str, scene: str) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("FFmpeg PATH veya ComfyUI embedded ortamında bulunamadı.")
    spath = scene_path(project, scene)
    scene_data = load_yaml(spath / "scene.yaml")
    settings = scene_data.get("postprocess", {})
    width = _even(settings.get("target_width"), 1280)
    height = _even(settings.get("target_height"), 720)
    target_fps = max(1, min(120, int(settings.get("target_fps", 24))))
    upscale_enabled = bool(settings.get("upscale", True))
    interpolation_enabled = bool(settings.get("interpolation", True))
    learned_requested = bool(settings.get("learned_upscale", False))

    source = find_video(project, scene)
    out_dir = spath / "repaired" / ("post_" + now_iso().replace(":", "-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"final_{width}x{height}_{target_fps}fps.mp4"
    log = out_dir / "postprocess.log"

    filters: list[str] = []
    # Interpolate before scaling in the baseline path to keep 8 GB systems usable.
    # Optional RIFE integration will replace this filter when its runner is installed.
    if interpolation_enabled:
        filters.append(
            f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        )
    if upscale_enabled:
        filters.extend(
            [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            ]
        )

    command = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(source),
    ]
    if filters:
        command.extend(["-vf", ",".join(filters)])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(output),
        ]
    )
    run = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log.write_text(
        " ".join(command) + "\n\n" + run.stdout + "\n" + run.stderr,
        encoding="utf-8",
    )
    if run.returncode or not output.is_file():
        raise UserError(
            f"Son işleme başarısız. Kod: {run.returncode}. Log: {log.relative_to(ROOT)}"
        )
    result = {
        "source": str(source.relative_to(ROOT)),
        "output": str(output.relative_to(ROOT)),
        "log": str(log.relative_to(ROOT)),
        "settings": {
            "upscale": upscale_enabled,
            "interpolation": interpolation_enabled,
            "target_width": width,
            "target_height": height,
            "target_fps": target_fps,
            "learned_upscale_requested": learned_requested,
            "learned_upscale_applied": False,
            "interpolation_backend": "ffmpeg_minterpolate" if interpolation_enabled else None,
            "upscale_backend": "ffmpeg_lanczos" if upscale_enabled else None,
        },
        "note": (
            "learned_upscale istendi; bu sürüm güvenli FFmpeg baseline kullandı. "
            "Real-ESRGAN runner ayrı aşamada etkinleştirilecek."
            if learned_requested
            else None
        ),
    }
    (out_dir / "postprocess.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
