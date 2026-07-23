from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .comfy_api import status as comfy_api_status

import psutil
import yaml

ROOT = Path(__file__).resolve().parent.parent

SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class UserError(Exception):
    """Kullanıcıya anlaşılır biçimde gösterilecek hata."""


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_safe_name(value: str, label: str) -> str:
    if not value or not SAFE_NAME.fullmatch(value):
        raise UserError(
            f"{label} geçersiz: {value!r}\n"
            "Yalnızca İngilizce harf, rakam, alt çizgi (_) ve tire (-) kullanın."
        )
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise UserError(f"Gerekli dosya bulunamadı: {path.relative_to(ROOT)}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise UserError(
            f"YAML dosyası okunamadı: {path.relative_to(ROOT)}\n"
            f"Muhtemel neden: girinti veya iki nokta hatası.\nTeknik ayrıntı: {exc}"
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise UserError(f"Dosyanın ana yapısı sözlük olmalı: {path.relative_to(ROOT)}")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def append_log(event: dict[str, Any]) -> None:
    log_dir = ROOT / "logs" / "engine"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {"time": now_iso(), **event}
    with (log_dir / "engine.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def init_runtime() -> None:
    dirs = [
        "logs/engine", "logs/generations", "logs/failures", "logs/diagnostics",
        "runtime/jobs", "runtime/locks", "runtime/cache", "runtime/temp",
        "projects", "identities",
    ]
    for item in dirs:
        (ROOT / item).mkdir(parents=True, exist_ok=True)
    append_log({"actor": "user", "command": "system.init", "status": "completed"})


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_text(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return output.strip() or None


def gpu_info() -> dict[str, Any]:
    if not command_exists("nvidia-smi"):
        return {"available": False, "reason": "nvidia-smi bulunamadı"}
    query = run_text([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    if not query:
        return {"available": False, "reason": "nvidia-smi yanıt vermedi"}
    first = query.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 3:
        return {"available": True, "raw": first}
    try:
        vram_mb = int(float(parts[1]))
    except ValueError:
        vram_mb = None
    return {
        "available": True,
        "name": parts[0],
        "vram_mb": vram_mb,
        "driver": parts[2],
    }


def comfyui_report() -> dict[str, Any]:
    main = ROOT / "comfyui" / "runtime" / "main.py"
    embedded = ROOT / "comfyui" / "python_embeded" / "python.exe"
    installed = main.exists() and embedded.exists()
    api = comfy_api_status() if installed else {"online": False, "reason": "ComfyUI dosyaları kurulu değil"}
    return {
        "ok": installed,
        "installed": installed,
        "main": str(main),
        "embedded_python": str(embedded),
        "api_online": bool(api.get("online")),
        "api": api,
    }


def system_report() -> dict[str, Any]:
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    config_files = [
        ROOT / "configs/hardware.yaml",
        ROOT / "configs/engine.yaml",
        ROOT / "configs/paths.yaml",
        ROOT / "configs/quality_presets.yaml",
        ROOT / "configs/model_routes.yaml",
    ]
    return {
        "python": {
            "ok": sys.version_info >= (3, 10),
            "version": sys.version.split()[0],
            "executable": sys.executable,
        },
        "gpu": gpu_info(),
        "ram": {"ok": ram_gb >= 15.0, "total_gb": ram_gb},
        "ffmpeg": {"ok": command_exists("ffmpeg")},
        "comfyui": comfyui_report(),
        "configs": {"ok": all(p.exists() for p in config_files)},
        "writable": {"ok": os.access(ROOT, os.W_OK)},
        "models": {"ok": False, "reason": "Model paketi henüz kurulmadı"},
        "workflows": {"ok": False, "reason": "Workflow paketi henüz kurulmadı"},
    }


def project_path(name: str) -> Path:
    return ROOT / "projects" / ensure_safe_name(name, "Proje adı")


def identity_path(name: str) -> Path:
    return ROOT / "identities" / ensure_safe_name(name, "Kişi adı")


def scene_path(project: str, scene: str) -> Path:
    return project_path(project) / "scenes" / ensure_safe_name(scene, "Sahne adı")


def create_project(name: str) -> Path:
    path = project_path(name)
    if path.exists():
        raise UserError(f"Proje zaten var: {name}\nVar olan proje üzerine yazılmadı.")
    template = load_yaml(ROOT / "projects/_template/project.yaml")
    data = copy.deepcopy(template)
    data["project"]["id"] = name
    data["project"]["title"] = name.replace("_", " ").replace("-", " ").title()
    data["project"]["created_at"] = now_iso()
    data["project"]["updated_at"] = now_iso()
    for d in ["references", "scenes", "approved", "rejected", "exports", "logs"]:
        (path / d).mkdir(parents=True, exist_ok=True)
    save_yaml(path / "project.yaml", data)
    append_log({"actor": "user", "command": "project.create", "project": name, "status": "completed"})
    return path


def list_projects() -> list[str]:
    base = ROOT / "projects"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("_"))


def create_identity(name: str) -> Path:
    path = identity_path(name)
    if path.exists():
        raise UserError(f"Kişi zaten var: {name}\nVar olan klasör üzerine yazılmadı.")
    template = load_yaml(ROOT / "identities/_template/identity.yaml")
    data = copy.deepcopy(template)
    data["identity"]["id"] = name
    data["identity"]["display_name"] = name.replace("_", " ").replace("-", " ").title()
    data["identity"]["created_at"] = now_iso()
    for d in ["source", "approved", "embeddings", "face_models"]:
        (path / d).mkdir(parents=True, exist_ok=True)
    save_yaml(path / "identity.yaml", data)
    (path / "notes.md").write_text("# Kimlik notları\n", encoding="utf-8")
    append_log({"actor": "user", "command": "identity.create", "identity": name, "status": "completed"})
    return path


def identity_check(name: str) -> dict[str, Any]:
    path = identity_path(name)
    if not path.exists():
        raise UserError(f"Kişi bulunamadı: {name}")
    data = load_yaml(path / "identity.yaml")
    source = path / "source"
    images = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    permission = bool(data.get("permission", {}).get("confirmed", False))
    return {
        "path": path,
        "images": images,
        "permission": permission,
        "ready": len(images) >= 1 and permission,
    }


def create_scene(project: str, scene: str) -> Path:
    ppath = project_path(project)
    if not ppath.exists():
        raise UserError(f"Önce proje oluşturulmalı: {project}")
    spath = scene_path(project, scene)
    if spath.exists():
        raise UserError(f"Sahne zaten var: {scene}\nVar olan sahne üzerine yazılmadı.")
    template = load_yaml(ROOT / "projects/_template/scenes/_template/scene.yaml")
    data = copy.deepcopy(template)
    data["scene"]["id"] = scene
    data["scene"]["title"] = scene.replace("_", " ").replace("-", " ").title()
    data["scene"]["created_at"] = now_iso()
    for d in ["references", "frames", "generations", "repaired", "selected", "metadata", "logs"]:
        (spath / d).mkdir(parents=True, exist_ok=True)
    save_yaml(spath / "scene.yaml", data)

    project_data = load_yaml(ppath / "project.yaml")
    scenes = project_data.setdefault("scenes", [])
    if scene not in scenes:
        scenes.append(scene)
    project_data.setdefault("status", {})["total_scenes"] = len(scenes)
    project_data["project"]["updated_at"] = now_iso()
    save_yaml(ppath / "project.yaml", project_data)
    append_log({"actor": "user", "command": "scene.create", "project": project, "scene": scene, "status": "completed"})
    return spath


def scene_check(project: str, scene: str) -> dict[str, Any]:
    spath = scene_path(project, scene)
    if not spath.exists():
        raise UserError(f"Sahne bulunamadı: {project}/{scene}")
    data = load_yaml(spath / "scene.yaml")
    missing: list[str] = []
    identity = data.get("identity", {}).get("character_id")
    if not identity:
        missing.append("identity.character_id")
    composition = data.get("composition", {})
    if not composition.get("location"):
        missing.append("composition.location")
    if not composition.get("wardrobe"):
        missing.append("composition.wardrobe")
    movement = data.get("movement", {})
    if not movement.get("character_action"):
        missing.append("movement.character_action")
    style = data.get("style", {})
    if not style.get("mood"):
        missing.append("style.mood")
    identity_exists = bool(identity and identity_path(str(identity)).exists())
    return {
        "data": data,
        "missing": missing,
        "identity": identity,
        "identity_exists": identity_exists,
        "ready": not missing and identity_exists,
    }


def gpu_lock_path() -> Path:
    return ROOT / "runtime/locks/gpu.lock"


def read_lock() -> dict[str, Any] | None:
    path = gpu_lock_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unknown", "path": str(path)}


def cancel_lock() -> bool:
    path = gpu_lock_path()
    if not path.exists():
        return False
    path.unlink()
    append_log({"actor": "user", "command": "job.cancel", "status": "lock_removed"})
    return True


def generation_preflight(project: str, scene: str, kind: str) -> None:
    check = scene_check(project, scene)
    if not check["ready"]:
        reasons = []
        if check["missing"]:
            reasons.append("Eksik alanlar: " + ", ".join(check["missing"]))
        if check["identity"] and not check["identity_exists"]:
            reasons.append(f"Kimlik klasörü bulunamadı: {check['identity']}")
        raise UserError("Sahne üretime hazır değil.\n" + "\n".join(reasons))
    if read_lock():
        raise UserError("Başka bir GPU işi şu anda çalışıyor.\nDurumu görmek için: clipctl.bat job status")
    if not comfyui_report()["installed"]:
        raise UserError(
            f"{kind} üretimi başlatılamadı.\n"
            "Neden: ComfyUI henüz kurulmamış.\n"
            "Bu çekirdek paket yalnızca proje ve komut sistemini hazırlar."
        )
    if not comfy_api_status().get("online"):
        raise UserError(
            f"{kind} üretimi başlatılamadı.\n"
            "Neden: ComfyUI kurulu ancak API çalışmıyor.\n"
            "START_ENGINE.bat dosyasını çalıştır."
        )
    raise UserError(
        f"{kind} üretim bağlantısı henüz etkin değil.\n"
        "ComfyUI API hazır; model ve workflow paketi sonraki aşamada eklenecek."
    )
