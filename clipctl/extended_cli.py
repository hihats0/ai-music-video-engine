from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from . import cli as legacy
from .comfy_api import ComfyAPIError, status as comfy_status, validate_node_types
from .core import ROOT, UserError, init_runtime, system_report
from .diagnostics import RunJournal
from .frame_generation import IDENTITY_REQUIRED_NODES, generate_reference_frames
from .identity_models import identity_model_status, install_identity_assets
from .models import download_models, model_status, write_inventory
from .postprocess import process_video, tool_status
from .quality import conservative_repair, review_video
from .workflows import WAN_REQUIRED_NODES


def show(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def info(text: str) -> None:
    print(f"[BİLGİ] {text}")


def ok(text: str) -> None:
    print(f"[OK] {text}")


def _node_report(required: list[str]) -> dict[str, Any]:
    if not comfy_status().get("online"):
        return {"ok": False, "missing": required, "reason": "ComfyUI API çevrimdışı"}
    try:
        return validate_node_types(required)
    except Exception as exc:
        return {"ok": False, "missing": [], "reason": f"{type(exc).__name__}: {exc}"}


def goal_report() -> dict[str, Any]:
    system = system_report()
    wan = model_status()
    identity = identity_model_status()
    api = comfy_status()
    wan_nodes = _node_report(WAN_REQUIRED_NODES)
    identity_nodes = _node_report(IDENTITY_REQUIRED_NODES)
    ready = bool(
        system["python"]["ok"]
        and system["gpu"].get("available")
        and system["ram"]["ok"]
        and system["configs"]["ok"]
        and system["comfyui"]["installed"]
        and api.get("online")
        and wan["ready"]
        and identity["ready_on_disk"]
        and wan_nodes.get("ok")
        and identity_nodes.get("ok")
    )
    return {
        "ready": ready,
        "engine_version": __version__,
        "system": system,
        "wan_models": wan,
        "identity_models": identity,
        "comfy_api": api,
        "wan_nodes": wan_nodes,
        "identity_nodes": identity_nodes,
        "optional_postprocess": tool_status(),
    }


def install_goal() -> dict[str, Any]:
    init_runtime()
    report = system_report()
    if not report["comfyui"]["installed"]:
        raise UserError("ComfyUI kurulu değil. Önce 2. Aşama v0.2.2 tamamlanmalı.")
    was_online = bool(comfy_status().get("online"))
    if was_online:
        info("Custom node kurulumu için ComfyUI kapatılıyor.")
        legacy.run_comfy("stop")
        time.sleep(4)
    install_identity_assets(progress=info)
    download_models(progress=info)
    write_inventory()
    info("ComfyUI yeni node'larla başlatılıyor.")
    legacy.run_comfy("start")
    wan_nodes = validate_node_types(WAN_REQUIRED_NODES)
    identity_nodes = validate_node_types(IDENTITY_REQUIRED_NODES)
    if not wan_nodes["ok"]:
        raise UserError("Eksik Wan node'ları: " + ", ".join(wan_nodes["missing"]))
    if not identity_nodes["ok"]:
        raise UserError(
            "Eksik kimlik node'ları: " + ", ".join(identity_nodes["missing"])
            + "\nlogs/comfyui/server.log içindeki custom-node import hatasını kontrol et."
        )
    final = goal_report()
    if not final["ready"]:
        raise UserError("Kurulum tamamlandı fakat final doğrulama geçmedi.")
    return final


def _looks_like_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in (
        "out of memory", "cuda out of memory", "allocation on device",
        "not enough memory", "cublas_status_alloc_failed", "torch.cuda",
    ))


def _recursive_frames(project: str, scene: str) -> list[Path]:
    base = ROOT / "projects" / project / "scenes" / scene / "frames"
    if not base.exists():
        return []
    return sorted(
        path for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def _intercept(argv: list[str]) -> bool:
    if not argv:
        return False
    return argv[0] in {"identity-model", "quality", "postprocess", "goal"} or (
        argv[0] == "frame" and len(argv) > 1 and argv[1] in {"generate", "generate-retry", "list"}
    )


def dispatch(argv: list[str], journal: RunJournal) -> int:
    group = argv[0]
    action = argv[1] if len(argv) > 1 else ""
    if group == "identity-model":
        if action == "status":
            data = identity_model_status()
            show(data)
            return 0 if data["ready_on_disk"] else 1
        if action == "install":
            show(install_identity_assets(progress=info))
            ok("Kimlik başlangıç karesi varlıkları kuruldu.")
            return 0
        raise UserError("Kullanım: clipctl.bat identity-model status|install")
    if group == "goal":
        if action == "status":
            data = goal_report()
            show(data)
            if data["ready"]:
                ok("GOAL hazır: referans kare → onay → Wan video → kalite → postprocess.")
                return 0
            return 1
        if action == "install":
            show(install_goal())
            ok("TÜM ZORUNLU AŞAMALAR KURULDU.")
            return 0
        raise UserError("Kullanım: clipctl.bat goal status|install")
    if group == "frame":
        if len(argv) < 4:
            raise UserError("Kullanım: clipctl.bat frame generate|list <proje> <sahne>")
        project, scene = argv[2], argv[3]
        if action == "list":
            files = _recursive_frames(project, scene)
            for index, path in enumerate(files, start=1):
                print(f"[{index}] {path.relative_to(ROOT)}")
            return 0 if files else 1
        try:
            result = generate_reference_frames(
                project, scene, low_vram=(action == "generate-retry"), journal=journal
            )
        except (UserError, ComfyAPIError) as exc:
            if action != "generate" or not _looks_like_oom(exc):
                raise
            journal.event("frame.retry", status="retrying", reason="cuda_out_of_memory", profile="768x432")
            info("Kare üretiminde VRAM yetmedi; bir kez 768x432 deneniyor.")
            result = generate_reference_frames(project, scene, low_vram=True, journal=journal)
        show(result)
        ok("Başlangıç karesi adayları üretildi.")
        return 0
    if group == "quality":
        if len(argv) < 4:
            raise UserError("Kullanım: clipctl.bat quality review|repair <proje> <sahne>")
        if action == "review":
            show(review_video(argv[2], argv[3]))
            ok("İnceleme kareleri hazırlandı.")
            return 0
        if action == "repair":
            show(conservative_repair(argv[2], argv[3], journal=journal))
            ok("Düşük hareketli onarım üretimi tamamlandı.")
            return 0
        raise UserError("quality işlemi review veya repair olmalı.")
    if group == "postprocess":
        if action == "status":
            data = tool_status()
            show(data)
            return 0 if data["ready"] else 1
        if action == "run" and len(argv) >= 4:
            show(process_video(argv[2], argv[3]))
            ok("720p/48 FPS çıktı hazırlandı.")
            return 0
        raise UserError("Kullanım: clipctl.bat postprocess status | run <proje> <sahne>")
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not _intercept(args):
        return legacy.main(args)
    command = ".".join(args[:2])
    journal = RunJournal(command, argv=args)
    try:
        code = dispatch(args, journal)
        if code == 0:
            journal.success(exit_code=0)
        return code
    except (UserError, ComfyAPIError) as exc:
        error_code, bundle = journal.failure(
            exc, stage=args[0], component=args[1] if len(args) > 1 else args[0], user_message=str(exc)
        )
        print(f"[HATA] {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1
    except Exception as exc:
        error_code, bundle = journal.failure(
            exc, stage=args[0], component=args[1] if len(args) > 1 else args[0], user_message="Beklenmeyen motor hatası"
        )
        print(f"[KRİTİK HATA] {type(exc).__name__}: {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1
