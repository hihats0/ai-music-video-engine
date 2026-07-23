from __future__ import annotations

from pathlib import Path

import psutil

root = Path(__file__).resolve().parent.parent
needles = [
    str(root / "comfyui" / "ComfyUI" / "main.py").lower().replace("/", "\\"),
    str(root / "comfyui" / "runtime" / "main.py").lower().replace("/", "\\"),
]

found = 0
for process in psutil.process_iter(["pid", "cmdline"]):
    try:
        cmdline = " ".join(process.info.get("cmdline") or []).lower().replace("/", "\\")
        if any(needle in cmdline for needle in needles):
            process.terminate()
            found += 1
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue

print(f"[OK] {found} ComfyUI islemi durduruluyor." if found else "[BILGI] Calisan ComfyUI islemi bulunamadi.")
