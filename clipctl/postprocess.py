from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .core import ROOT, UserError, load_yaml, scene_path
from .media_tools import find_ffmpeg


def tool_status() -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    return {"ffmpeg": str(ffmpeg) if ffmpeg else None, "ready": ffmpeg is not None}


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


def process_video(project: str, scene: str) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("FFmpeg PATH veya ComfyUI embedded ortamında bulunamadı.")
    source = find_video(project, scene)
    out_dir = scene_path(project, scene) / "repaired"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "final_1280x720_48fps.mp4"
    log = out_dir / "postprocess.log"
    vf = (
        "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
        "scale=1280:720:force_original_aspect_ratio=decrease:flags=lanczos,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2"
    )
    command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(source), "-vf", vf, "-c:v", "libx264", "-preset", "slow",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(output),
    ]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    log.write_text(" ".join(command) + "\n\n" + run.stdout + "\n" + run.stderr, encoding="utf-8")
    if run.returncode or not output.is_file():
        raise UserError(f"Son işleme başarısız. Kod: {run.returncode}. Log: {log.relative_to(ROOT)}")
    result = {"source": str(source.relative_to(ROOT)), "output": str(output.relative_to(ROOT)), "log": str(log.relative_to(ROOT))}
    (out_dir / "postprocess.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
