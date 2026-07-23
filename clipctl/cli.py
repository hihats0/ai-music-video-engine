from __future__ import annotations

import argparse
import json
import subprocess
import webbrowser

import yaml

from . import __version__
from .comfy_api import status as comfy_status, wait_until_online
from .core import (
    ROOT,
    UserError,
    cancel_lock,
    create_identity,
    create_project,
    create_scene,
    generation_preflight,
    identity_check,
    identity_path,
    init_runtime,
    list_projects,
    load_yaml,
    project_path,
    read_lock,
    scene_check,
    scene_path,
    system_report,
)


def ok(text: str) -> None:
    print(f"[OK] {text}")


def info(text: str) -> None:
    print(f"[BİLGİ] {text}")


def missing(text: str) -> None:
    print(f"[EKSİK] {text}")


def show_yaml(data: dict) -> None:
    print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def run_system(action: str) -> int:
    if action == "init":
        init_runtime()
        ok("Çekirdek klasörler hazırlandı.")
        return 0

    report = system_report()
    if action == "status":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    py = report["python"]
    (ok if py["ok"] else missing)(f"Python {py['version']}")
    gpu = report["gpu"]
    if gpu.get("available"):
        ok(f"{gpu.get('name', 'NVIDIA GPU')} — {gpu.get('vram_mb', '?')} MB VRAM")
    else:
        missing(f"NVIDIA GPU: {gpu.get('reason')}")
    ram = report["ram"]
    (ok if ram["ok"] else missing)(f"Sistem RAM: {ram['total_gb']} GB")
    (ok if report["configs"]["ok"] else missing)("Config dosyaları")
    (ok if report["comfyui"]["installed"] else missing)("ComfyUI kurulumu")
    if report["comfyui"]["installed"]:
        (ok if report["comfyui"]["api_online"] else missing)("ComfyUI API")
    if action == "doctor":
        print("\nNe yapmalısın?")
        if not report["comfyui"]["installed"]:
            print("- 2. AŞAMA ComfyUI kurulumunu uygula.")
        elif not report["comfyui"]["api_online"]:
            print("- START_ENGINE.bat dosyasını çalıştır.")
        else:
            print("- Sistem hazır. Model ve workflow aşamasına geçilebilir.")
    return 0


def run_comfy(action: str) -> int:
    if action == "status":
        result = comfy_status()
        if result.get("online"):
            ok("ComfyUI API çevrimiçi: http://127.0.0.1:8188")
            return 0
        missing(f"ComfyUI API çevrimdışı: {result.get('reason')}")
        return 1

    if action == "start":
        script = ROOT / "comfyui" / "start_headless.bat"
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=ROOT)
        result = wait_until_online(timeout=600)
        if not result.get("online"):
            raise UserError("ComfyUI başlatıldı ancak API yanıt vermedi. logs/comfyui/server.log dosyasını kontrol et.")
        ok("ComfyUI API hazır: http://127.0.0.1:8188")
        return 0

    if action == "stop":
        script = ROOT / "comfyui" / "stop_server.bat"
        return subprocess.run(["cmd.exe", "/c", str(script)], cwd=ROOT, check=False).returncode

    if action == "open":
        webbrowser.open("http://127.0.0.1:8188")
        return 0
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clipctl", description="AI Music Video Engine terminal yöneticisi")
    parser.add_argument("--version", action="version", version=__version__)
    groups = parser.add_subparsers(dest="group", required=True)

    system = groups.add_parser("system")
    system.add_argument("action", choices=["init", "check", "status", "doctor"])

    comfy = groups.add_parser("comfy")
    comfy.add_argument("action", choices=["status", "start", "stop", "open"])

    project = groups.add_parser("project")
    project.add_argument("action", choices=["create", "list", "show"])
    project.add_argument("name", nargs="?")

    identity = groups.add_parser("identity")
    identity.add_argument("action", choices=["create", "check", "show"])
    identity.add_argument("name")

    scene = groups.add_parser("scene")
    scene.add_argument("action", choices=["create", "check", "show"])
    scene.add_argument("project")
    scene.add_argument("scene")

    frame = groups.add_parser("frame")
    frame.add_argument("action", choices=["generate"])
    frame.add_argument("project")
    frame.add_argument("scene")

    video = groups.add_parser("video")
    video.add_argument("action", choices=["generate", "retry"])
    video.add_argument("project")
    video.add_argument("scene")

    job = groups.add_parser("job")
    job.add_argument("action", choices=["status", "cancel"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.group == "system":
            return run_system(args.action)
        if args.group == "comfy":
            return run_comfy(args.action)
        if args.group == "project":
            if args.action == "list":
                for name in list_projects():
                    print(name)
                return 0
            if not args.name:
                raise UserError("Proje adı gerekli.")
            if args.action == "create":
                ok(f"Proje oluşturuldu: {create_project(args.name).relative_to(ROOT)}")
            else:
                show_yaml(load_yaml(project_path(args.name) / "project.yaml"))
            return 0
        if args.group == "identity":
            if args.action == "create":
                ok(f"Kimlik oluşturuldu: {create_identity(args.name).relative_to(ROOT)}")
            elif args.action == "check":
                result = identity_check(args.name)
                print(f"Referans: {len(result['images'])}, izin: {result['permission']}, hazır: {result['ready']}")
                return 0 if result["ready"] else 1
            else:
                show_yaml(load_yaml(identity_path(args.name) / "identity.yaml"))
            return 0
        if args.group == "scene":
            if args.action == "create":
                ok(f"Sahne oluşturuldu: {create_scene(args.project, args.scene).relative_to(ROOT)}")
            elif args.action == "check":
                result = scene_check(args.project, args.scene)
                print(json.dumps({k: v for k, v in result.items() if k != "data"}, ensure_ascii=False, indent=2))
                return 0 if result["ready"] else 1
            else:
                show_yaml(load_yaml(scene_path(args.project, args.scene) / "scene.yaml"))
            return 0
        if args.group == "frame":
            generation_preflight(args.project, args.scene, "Başlangıç karesi")
        if args.group == "video":
            generation_preflight(args.project, args.scene, "Video")
        if args.group == "job":
            if args.action == "status":
                print(json.dumps(read_lock() or {"status": "idle"}, ensure_ascii=False, indent=2))
                return 0
            ok("Görev kilidi kaldırıldı" if cancel_lock() else "Aktif görev yok")
            return 0
    except UserError as exc:
        print(f"[HATA] {exc}")
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
