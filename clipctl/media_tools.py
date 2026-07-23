from __future__ import annotations

import shutil
from pathlib import Path

from .core import ROOT


def find_ffmpeg() -> Path | None:
    system = shutil.which("ffmpeg")
    if system:
        return Path(system)
    patterns = [
        "comfyui/python_embeded/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*.exe",
        "comfyui/python_embeded/Lib/site-packages/**/ffmpeg*.exe",
        "runtime/tools/ffmpeg*.exe",
    ]
    for pattern in patterns:
        matches = sorted(ROOT.glob(pattern))
        if matches:
            return matches[0]
    return None
