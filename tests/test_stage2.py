from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    required_patch_files = [
        ROOT / "configs" / "comfyui.yaml",
        ROOT / "comfyui" / "start_headless.bat",
        ROOT / "comfyui" / "start_interface.bat",
        ROOT / "comfyui" / "run_server.bat",
        ROOT / "comfyui" / "stop_server.bat",
        ROOT / "comfyui" / "stop_server.py",
        ROOT / "comfyui" / "healthcheck.py",
        ROOT / "comfyui" / "wait_for_server.py",
        ROOT / "clipctl" / "comfy_api.py",
        ROOT / "agents" / "shared" / "COMFYUI_OPERATIONS.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_patch_files if not path.exists()]
    if missing:
        print("[HATA] Eksik 2. ASAMA dosyalari:")
        for item in missing:
            print(f"- {item}")
        return 1

    comfy_root = ROOT / "comfyui" / "ComfyUI"
    runtime_root = ROOT / "comfyui" / "runtime"
    embedded = ROOT / "comfyui" / "python_embeded" / "python.exe"
    runtime_required = [
        comfy_root / "main.py",
        comfy_root / "comfy",
        comfy_root / "comfy" / "options.py",
        comfy_root / "nodes.py",
        comfy_root / "folder_paths.py",
    ]

    print("[OK] 2. ASAMA patch dosyalari tam")
    print(f"[{'OK' if embedded.exists() else 'EKSIK'}] ComfyUI embedded Python")
    print(f"[{'OK' if comfy_root.exists() else 'EKSIK'}] ComfyUI portable yolu")
    print(f"[{'OK' if runtime_root.exists() else 'EKSIK'}] ComfyUI runtime klasoru")

    missing_runtime = [str(path) for path in runtime_required if not path.exists()]
    if missing_runtime:
        print("[HATA] ComfyUI portable yapisi eksik:")
        for item in missing_runtime:
            print(f"- {item}")
        return 1
    if not embedded.exists():
        return 1

    print("[OK] ComfyUI main.py")
    print("[OK] ComfyUI comfy/options.py")
    print("[OK] ComfyUI portable klasor yapisi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
