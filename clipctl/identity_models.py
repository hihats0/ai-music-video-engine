from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml

from .core import ROOT, UserError

MANIFEST = ROOT / "configs" / "identity_models.yaml"


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise UserError(f"Kimlik model manifesti bulunamadı: {MANIFEST.relative_to(ROOT)}")
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("group"), dict):
        raise UserError("identity_models.yaml geçersiz.")
    return data


def model_root() -> Path:
    return ROOT / str(load_manifest().get("model_root", "comfyui/runtime/models"))


def custom_node_path() -> Path:
    node = load_manifest().get("custom_node", {})
    return ROOT / str(node.get("destination", "comfyui/runtime/custom_nodes/ComfyUI_IPAdapter_plus"))


def _file_status(item: dict[str, Any]) -> dict[str, Any]:
    target = model_root() / str(item["destination"])
    size = target.stat().st_size if target.exists() else 0
    minimum = int(item.get("minimum_bytes", 1))
    return {
        "id": item.get("id"),
        "path": str(target),
        "exists": target.exists(),
        "size_bytes": size,
        "minimum_bytes": minimum,
        "ok": target.exists() and size >= minimum,
    }


def identity_model_status() -> dict[str, Any]:
    data = load_manifest()
    group = data["group"]
    files = [_file_status(item) for item in group.get("files", [])]
    node_path = custom_node_path()
    return {
        "group": group.get("id"),
        "title": group.get("title"),
        "identity_mode": group.get("identity_mode"),
        "biometric_embedding": bool(group.get("biometric_embedding")),
        "license_summary": group.get("license_summary"),
        "required_free_space_gb": group.get("required_free_space_gb"),
        "free_space_gb": round(shutil.disk_usage(ROOT).free / 1024**3, 2),
        "custom_node": {
            "path": str(node_path),
            "installed": (node_path / "__init__.py").exists(),
        },
        "files": files,
        "required_nodes": list(data.get("required_nodes", [])),
        "ready_on_disk": bool(files)
        and all(item["ok"] for item in files)
        and (node_path / "__init__.py").exists(),
    }


def _tool(name: str) -> str:
    command = shutil.which(name)
    if not command:
        raise UserError(f"Gerekli komut bulunamadı: {name}")
    return command


def _sha256(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def install_custom_node(progress: Callable[[str], None] | None = None) -> Path:
    data = load_manifest()
    node = data.get("custom_node", {})
    target = custom_node_path()
    repository = str(node.get("repository", "")).strip()
    if not repository:
        raise UserError("IPAdapter custom-node repository adresi manifestte yok.")
    git = _tool("git")
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        if progress:
            progress("IPAdapter custom node güncelleniyor.")
        completed = subprocess.run(
            [git, "-C", str(target), "pull", "--ff-only"], check=False
        )
        if completed.returncode != 0:
            raise UserError(
                "ComfyUI_IPAdapter_plus güncellenemedi. "
                f"git çıkış kodu: {completed.returncode}"
            )
    elif target.exists():
        if not (target / "__init__.py").exists():
            raise UserError(
                f"Custom node hedefi dolu fakat geçersiz: {target}\n"
                "Klasörü elle silmek yerine tanı ZIP'ini paylaş."
            )
    else:
        if progress:
            progress("IPAdapter custom node indiriliyor.")
        completed = subprocess.run(
            [git, "clone", "--depth", "1", repository, str(target)], check=False
        )
        if completed.returncode != 0:
            raise UserError(
                "ComfyUI_IPAdapter_plus klonlanamadı. "
                f"git çıkış kodu: {completed.returncode}"
            )
    if not (target / "__init__.py").exists():
        raise UserError(f"IPAdapter custom node kurulumu doğrulanamadı: {target}")
    return target


def download_identity_models(
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    data = load_manifest()
    group = data["group"]
    free_gb = shutil.disk_usage(ROOT).free / 1024**3
    required = float(group.get("required_free_space_gb", 13))
    if free_gb < required:
        raise UserError(
            f"Kimlik modelleri için boş alan yetersiz. "
            f"Gerekli: {required:.0f} GB, mevcut: {free_gb:.1f} GB."
        )
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise UserError("curl.exe bulunamadı.")
    results: list[dict[str, Any]] = []
    for item in group.get("files", []):
        target = model_root() / str(item["destination"])
        target.parent.mkdir(parents=True, exist_ok=True)
        current = _file_status(item)
        if current["ok"]:
            results.append({**current, "action": "skipped"})
            if progress:
                progress(f"Zaten hazır: {target.name}")
            continue
        if progress:
            progress(f"İndiriliyor: {target.name}")
        completed = subprocess.run(
            [
                curl,
                "--location",
                "--fail",
                "--retry",
                "8",
                "--retry-delay",
                "5",
                "--continue-at",
                "-",
                "--output",
                str(target),
                str(item["url"]),
            ],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise UserError(
                f"Kimlik modeli indirilemedi: {target.name}\n"
                f"curl çıkış kodu: {completed.returncode}\n"
                "Komutu tekrar çalıştırırsan kaldığı yerden devam eder."
            )
        final = _file_status(item)
        if not final["ok"]:
            raise UserError(
                f"İndirilen dosya beklenenden küçük: {target}\n"
                f"Boyut: {final['size_bytes']}, minimum: {final['minimum_bytes']}"
            )
        expected = str(item.get("sha256", "")).strip().lower()
        if expected:
            if progress:
                progress(f"SHA-256 doğrulanıyor: {target.name}")
            actual = _sha256(target)
            if actual != expected:
                target.rename(target.with_suffix(target.suffix + ".bad"))
                raise UserError(
                    f"SHA-256 uyuşmadı: {target.name}\n"
                    f"Beklenen: {expected}\nGerçek: {actual}\n"
                    "Bozuk dosya .bad uzantısıyla saklandı."
                )
        results.append({**final, "action": "downloaded"})
    return {"ready": True, "files": results}


def install_identity_assets(
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    node = install_custom_node(progress=progress)
    result = download_identity_models(progress=progress)
    inventory = ROOT / "models_manifest" / "installed_identity.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    payload = identity_model_status()
    payload["custom_node_commit"] = None
    git = shutil.which("git")
    if git and (node / ".git").exists():
        completed = subprocess.run(
            [git, "-C", str(node), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            payload["custom_node_commit"] = completed.stdout.strip()
    inventory.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**result, "inventory": str(inventory), "status": payload}
