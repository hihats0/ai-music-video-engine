from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
required = [
    ROOT / "configs/comfyui.yaml",
    ROOT / "comfyui/ComfyUI/main.py",
    ROOT / "comfyui/ComfyUI/comfy/options.py",
    ROOT / "comfyui/python_embeded/python.exe",
    ROOT / "comfyui/run_server.bat",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    print("[HATA] Eksik ComfyUI dosyalari:")
    for item in missing:
        print(f"- {item}")
    raise SystemExit(1)
print("[OK] ComfyUI portable klasor yapisi")
