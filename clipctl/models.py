from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml

from .core import ROOT, UserError

MANIFEST = ROOT / "configs" / "wan_models.yaml"


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise UserError(f"Model manifesti bulunamadı: {MANIFEST.relative_to(ROOT)}")
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("group"), dict):
        raise UserError("Wan model manifesti geçersiz.")
    return data


def model_root() -> Path:
    data = load_manifest()
    return ROOT / str(data.get("model_root", "comfyui/runtime/models"))


def _file_status(item: dict[str, Any]) -> dict[str, Any]:
    target = model_root() / str(item["destination"])
    size = target.stat().st_size if target.exists() else 0
    minimum = int(item.get("minimum_bytes", 1))
    return {"id": item.get("id"), "path": str(target), "exists": target.exists(), "size_bytes": size, "minimum_bytes": minimum, "ok": target.exists() and size >= minimum}


def model_status() -> dict[str, Any]:
    data = load_manifest()
    group = data["group"]
    files = [_file_status(item) for item in group.get("files", [])]
    free = shutil.disk_usage(ROOT).free
    return {
        "group": group.get("id"), "title": group.get("title"), "license": group.get("license"),
        "commercial_use": bool(group.get("commercial_use")),
        "required_free_space_gb": group.get("required_free_space_gb"),
        "free_space_gb": round(free / 1024**3, 2), "files": files,
        "ready": bool(files) and all(item["ok"] for item in files),
    }


def _curl() -> str:
    command = shutil.which("curl.exe") or shutil.which("curl")
    if not command:
        raise UserError("curl bulunamadı. Güncel Windows 10/11 içinde curl.exe bulunmalıdır.")
    return command


def download_models(progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    data = load_manifest()
    group = data["group"]
    root = model_root()
    root.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(ROOT).free / 1024**3
    required = float(group.get("required_free_space_gb", 18))
    if free_gb < required:
        raise UserError(f"Yeterli boş alan yok. Gerekli: en az {required:.0f} GB, mevcut: {free_gb:.1f} GB.")
    results = []
    for item in group.get("files", []):
        target = root / str(item["destination"])
        target.parent.mkdir(parents=True, exist_ok=True)
        current = _file_status(item)
        if current["ok"]:
            results.append({**current, "action": "skipped"})
            if progress:
                progress(f"Zaten hazır: {target.name}")
            continue
        if progress:
            progress(f"İndiriliyor: {target.name}")
        command = [_curl(), "--location", "--fail", "--retry", "8", "--retry-delay", "5", "--continue-at", "-", "--output", str(target), str(item["url"])]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            raise UserError(f"Model indirilemedi: {target.name}\ncurl çıkış kodu: {completed.returncode}\nAynı komutu yeniden çalıştırırsan indirme kaldığı yerden devam eder.")
        final = _file_status(item)
        if not final["ok"]:
            raise UserError(f"Model dosyası beklenenden küçük: {target}\nBoyut: {final['size_bytes']}, beklenen minimum: {final['minimum_bytes']}")
        results.append({**final, "action": "downloaded"})
    return {"ready": True, "files": results}


def sha256(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_inventory() -> Path:
    status = model_status()
    destination = ROOT / "models_manifest" / "installed_wan22.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
