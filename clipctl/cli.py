from __future__ import annotations

import argparse
import json
import subprocess
import sys
import webbrowser
from typing import Any

import yaml

from . import __version__
from .comfy_api import (
    ComfyAPIError,
    status as comfy_status,
    validate_node_types,
    wait_until_online,
)
from .core import (
    ROOT,
    UserError,
    cancel_lock,
    create_identity,
    create_project,
    create_scene,
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
from .diagnostics import RunJournal, collect_diagnostics, latest_diagnostic
from .generation import (
    approve_frame,
    generate_video,
    list_frame_candidates,
    prepare_frame_candidates,
)
from .models import download_models, model_status, write_inventory
from .workflows import WAN_REQUIRED_NODES


def ok(text: str) -> None:
    print(f"[OK] {text}")


def info(text: str) -> None:
    print(f"[BİLGİ] {text}")


def missing(text: str) -> None:
    print(f"[EKSİK] {text}")


def show_yaml(data: dict[str, Any]) -> None:
    print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def show_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def run_system(action: str) -> int:
    if action == "init":
        init_runtime()
        ok("Çekirdek klasörler hazırlandı.")
        return 0

    report = system_report()
    if action == "status":
        show_json(report)
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
    models = model_status()
    (ok if models["ready"] else missing)("Wan 2.2 5B model paketi")
    if action == "doctor":
        print("\nNe yapmalısın?")
        if not report["comfyui"]["installed"]:
            print("- Önce 2. AŞAMA ComfyUI kurulumunu tamamla.")
        elif not report["comfyui"]["api_online"]:
            print("- START_ENGINE.bat dosyasını çalıştır.")
        elif not models["ready"]:
            print("- clipctl.bat model install çalıştır.")
        else:
            print("- Sistem üretime hazır.")
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
        if not script.exists():
            raise UserError(f"Başlatma dosyası bulunamadı: {script.relative_to(ROOT)}")
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=ROOT)
        result = wait_until_online(timeout=600)
        if not result.get("online"):
            raise UserError(
                "ComfyUI başlatıldı ancak API yanıt vermedi. "
                "logs/comfyui/server.log dosyasını kontrol et."
            )
        ok("ComfyUI API hazır: http://127.0.0.1:8188")
        return 0

    if action == "stop":
        script = ROOT / "comfyui" / "stop_server.bat"
        return subprocess.run(
            ["cmd.exe", "/c", str(script)], cwd=ROOT, check=False
        ).returncode

    if action == "open":
        webbrowser.open("http://127.0.0.1:8188")
        return 0
    return 2


def run_model(action: str) -> int:
    if action == "status":
        data = model_status()
        show_json(data)
        return 0 if data["ready"] else 1
    if action == "install":
        result = download_models(progress=lambda text: info(text))
        inventory = write_inventory()
        ok("Wan 2.2 5B model paketi hazır.")
        info(f"Envanter: {inventory.relative_to(ROOT)}")
        show_json(result)
        return 0
    return 2


def _goal_report() -> dict[str, Any]:
    report = system_report()
    models = model_status()
    api = comfy_status()
    nodes: dict[str, Any] = {
        "ok": False,
        "missing": WAN_REQUIRED_NODES,
        "reason": "ComfyUI API çevrimdışı",
    }
    if api.get("online"):
        try:
            nodes = validate_node_types(WAN_REQUIRED_NODES)
        except Exception as exc:
            nodes = {
                "ok": False,
                "missing": [],
                "reason": f"{type(exc).__name__}: {exc}",
            }
    ready = bool(
        report["python"]["ok"]
        and report["gpu"].get("available")
        and report["ram"]["ok"]
        and report["configs"]["ok"]
        and report["comfyui"]["installed"]
        and api.get("online")
        and models["ready"]
        and nodes.get("ok")
    )
    return {
        "ready": ready,
        "engine_version": __version__,
        "system": report,
        "models": models,
        "comfy_api": api,
        "required_nodes": nodes,
    }


def run_goal(action: str) -> int:
    if action == "status":
        report = _goal_report()
        show_json(report)
        if report["ready"]:
            ok("GOAL hazır: kimlik referansı → başlangıç karesi → Wan video.")
            return 0
        missing("GOAL henüz hazır değil. Eksik bölümler üstte listelendi.")
        return 1

    if action == "install":
        init_runtime()
        report = system_report()
        if not report["comfyui"]["installed"]:
            raise UserError(
                "ComfyUI kurulu değil. Önce 2. Aşama v0.2.2 kurulumunu tamamla."
            )
        if not comfy_status().get("online"):
            info("ComfyUI başlatılıyor...")
            run_comfy("start")
        download_models(progress=lambda text: info(text))
        write_inventory()
        nodes = validate_node_types(WAN_REQUIRED_NODES)
        if not nodes["ok"]:
            raise UserError(
                "ComfyUI sürümünde gerekli Wan node'ları eksik: "
                + ", ".join(nodes["missing"])
                + "\nComfyUI güncelleme aracını çalıştır, sonra goal install "
                "komutunu yeniden çalıştır."
            )
        report = _goal_report()
        if not report["ready"]:
            raise UserError("Kurulum tamamlandı ancak final doğrulama geçmedi.")
        ok("TÜM AŞAMALAR KURULDU VE GOAL HAZIR.")
        return 0
    return 2


def _looks_like_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "out of memory",
        "cuda out of memory",
        "allocation on device",
        "not enough memory",
        "cublas_status_alloc_failed",
        "torch.cuda",
    )
    return any(marker in text for marker in markers)


def run_video(
    action: str, project: str, scene: str, journal: RunJournal
) -> int:
    if action == "retry":
        result = generate_video(project, scene, retry=True, journal=journal)
        show_json(result)
        ok(f"Video üretildi: {result['selected']}")
        return 0

    try:
        result = generate_video(project, scene, retry=False, journal=journal)
    except (UserError, ComfyAPIError) as exc:
        if not _looks_like_oom(exc):
            raise
        journal.event(
            "video.retry",
            status="retrying",
            reason="cuda_out_of_memory",
            profile="704x400",
            first_error=str(exc),
        )
        info(
            "GPU belleği yetmedi. Bir kez düşük çözünürlük kurtarma "
            "profili deneniyor."
        )
        result = generate_video(project, scene, retry=True, journal=journal)
    show_json(result)
    ok(f"Video üretildi: {result['selected']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipctl",
        description="AI Music Video Engine terminal yöneticisi",
    )
    parser.add_argument("--version", action="version", version=__version__)
    groups = parser.add_subparsers(dest="group", required=True)

    system = groups.add_parser("system")
    system.add_argument("action", choices=["init", "check", "status", "doctor"])

    comfy = groups.add_parser("comfy")
    comfy.add_argument("action", choices=["status", "start", "stop", "open"])

    model = groups.add_parser("model")
    model.add_argument("action", choices=["status", "install"])

    goal = groups.add_parser("goal")
    goal.add_argument("action", choices=["status", "install"])

    diagnose = groups.add_parser("diagnose")
    diagnose.add_argument("action", choices=["collect", "latest"])

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
    frame.add_argument("action", choices=["prepare", "list", "approve"])
    frame.add_argument("project")
    frame.add_argument("scene")
    frame.add_argument("candidate", nargs="?")

    video = groups.add_parser("video")
    video.add_argument("action", choices=["generate", "retry"])
    video.add_argument("project")
    video.add_argument("scene")

    job = groups.add_parser("job")
    job.add_argument("action", choices=["status", "cancel"])
    return parser


def dispatch(args: argparse.Namespace, journal: RunJournal) -> int:
    if args.group == "system":
        return run_system(args.action)
    if args.group == "comfy":
        return run_comfy(args.action)
    if args.group == "model":
        return run_model(args.action)
    if args.group == "goal":
        return run_goal(args.action)
    if args.group == "diagnose":
        if args.action == "collect":
            bundle = collect_diagnostics(reason="manual", run_id=journal.run_id)
            ok(f"Tanı paketi oluşturuldu: {bundle.relative_to(ROOT)}")
            return 0
        latest = latest_diagnostic()
        if latest:
            print(latest)
            return 0
        missing("Henüz tanı paketi yok.")
        return 1
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
            print(
                f"Referans: {len(result['images'])}, "
                f"izin: {result['permission']}, hazır: {result['ready']}"
            )
            return 0 if result["ready"] else 1
        else:
            show_yaml(load_yaml(identity_path(args.name) / "identity.yaml"))
        return 0
    if args.group == "scene":
        if args.action == "create":
            ok(
                f"Sahne oluşturuldu: "
                f"{create_scene(args.project, args.scene).relative_to(ROOT)}"
            )
        elif args.action == "check":
            result = scene_check(args.project, args.scene)
            print(
                json.dumps(
                    {key: value for key, value in result.items() if key != "data"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if result["ready"] else 1
        else:
            show_yaml(load_yaml(scene_path(args.project, args.scene) / "scene.yaml"))
        return 0
    if args.group == "frame":
        if args.action == "prepare":
            files = prepare_frame_candidates(args.project, args.scene)
            for path in files:
                print(path.relative_to(ROOT))
            ok(f"{len(files)} başlangıç karesi adayı hazırlandı.")
            return 0
        if args.action == "list":
            files = list_frame_candidates(args.project, args.scene)
            for index, path in enumerate(files, start=1):
                print(f"[{index}] {path.relative_to(ROOT)}")
            return 0 if files else 1
        if not args.candidate:
            raise UserError("Onaylanacak görsel dosyası gerekli.")
        selected = approve_frame(
            args.project, args.scene, args.candidate
        )
        ok(f"Başlangıç karesi onaylandı: {selected.relative_to(ROOT)}")
        return 0
    if args.group == "video":
        return run_video(args.action, args.project, args.scene, journal)
    if args.group == "job":
        if args.action == "status":
            show_json(read_lock() or {"status": "idle"})
            return 0
        ok("Görev kilidi kaldırıldı" if cancel_lock() else "Aktif görev yok")
        return 0
    return 2


def _component(args: argparse.Namespace) -> tuple[str, str]:
    stage_map = {
        "system": "core",
        "comfy": "stage2",
        "model": "models",
        "goal": "goal",
        "diagnose": "diagnostics",
        "identity": "identity",
        "frame": "frame",
        "video": "video",
        "project": "project",
        "scene": "scene",
        "job": "queue",
    }
    return stage_map.get(args.group, "engine"), str(
        getattr(args, "action", args.group)
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = f"{args.group}.{getattr(args, 'action', '')}".rstrip(".")
    journal = RunJournal(
        command, argv=sys.argv[1:] if argv is None else argv
    )
    try:
        code = dispatch(args, journal)
        if code == 0:
            journal.success(exit_code=0)
        else:
            journal.event(
                "command.finish", status="incomplete", exit_code=code
            )
        return code
    except (UserError, ComfyAPIError) as exc:
        stage, component = _component(args)
        error_code, bundle = journal.failure(
            exc,
            stage=stage,
            component=component,
            user_message=str(exc),
        )
        print(f"[HATA] {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1
    except Exception as exc:
        stage, component = _component(args)
        error_code, bundle = journal.failure(
            exc,
            stage=stage,
            component=component,
            user_message="Beklenmeyen motor hatası",
        )
        print(f"[KRİTİK HATA] {type(exc).__name__}: {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
