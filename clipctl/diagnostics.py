from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part)[:60] or "unknown"


def new_run_id(command: str) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{_safe_slug(command)}_{uuid.uuid4().hex[:8]}"


def _tail(path: Path, lines: int = 200) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            data = handle.readlines()
        return [line.rstrip("\n") for line in data[-lines:]]
    except OSError as exc:
        return [f"<log okunamadı: {exc}>"]


def _run_text(command: list[str], timeout: int = 20) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return f"<komut çalıştırılamadı: {exc}>"
    return ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()


def system_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "time": now_iso(),
        "platform": platform.platform(),
        "python": {"version": sys.version, "executable": sys.executable},
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "env": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
        "disk": {},
    }
    try:
        total, used, free = shutil.disk_usage(ROOT)
        snapshot["disk"] = {
            "total_gb": round(total / 1024**3, 2),
            "used_gb": round(used / 1024**3, 2),
            "free_gb": round(free / 1024**3, 2),
        }
    except OSError as exc:
        snapshot["disk"] = {"error": str(exc)}
    snapshot["nvidia_smi"] = _run_text([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    snapshot["git"] = {
        "head": _run_text(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "status": _run_text(["git", "-C", str(ROOT), "status", "--short"]),
        "remote": _run_text(["git", "-C", str(ROOT), "remote", "-v"]),
    }
    return snapshot


class RunJournal:
    """One-command journal with stable run id and machine-readable events."""

    def __init__(self, command: str, argv: Iterable[str] | None = None) -> None:
        self.command = command
        self.argv = list(argv or [])
        self.run_id = new_run_id(command)
        self.run_dir = ROOT / "logs" / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.run_dir / "events.jsonl"
        self.human_file = self.run_dir / "run.log"
        self.meta_file = self.run_dir / "meta.json"
        self.meta_file.write_text(json.dumps({
            "run_id": self.run_id,
            "command": self.command,
            "argv": self.argv,
            "started_at": now_iso(),
            "root": str(ROOT),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.event("command.start", status="running", argv=self.argv)

    def event(self, event: str, **payload: Any) -> None:
        record = {
            "time": now_iso(), "run_id": self.run_id,
            "command": self.command, "event": event, **payload,
        }
        with self.events_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        text = f"[{record['time']}] {event}"
        if payload:
            text += " " + json.dumps(payload, ensure_ascii=False, default=str)
        with self.human_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")

    def success(self, **payload: Any) -> None:
        self.event("command.finish", status="completed", **payload)

    def failure(self, exc: BaseException, *, stage: str = "engine", component: str = "unknown", user_message: str | None = None) -> tuple[str, Path]:
        error_code = f"E-{_safe_slug(stage).upper()}-{_safe_slug(component).upper()}-{dt.datetime.now().strftime('%H%M%S')}"
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        (self.run_dir / "traceback.txt").write_text(trace, encoding="utf-8")
        self.event("command.failure", status="failed", error_code=error_code,
                   stage=stage, component=component, exception_type=type(exc).__name__,
                   exception=str(exc), user_message=user_message)
        bundle = collect_diagnostics(reason=f"{error_code}: {user_message or str(exc)}",
                                     run_id=self.run_id, exception_text=trace)
        return error_code, bundle


def collect_diagnostics(*, reason: str = "manual", run_id: str | None = None, exception_text: str | None = None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / "logs" / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    work = output_dir / f"diagnostic_{stamp}_{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True, exist_ok=True)
    (work / "reason.txt").write_text(reason + "\n", encoding="utf-8")
    (work / "system.json").write_text(json.dumps(system_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    if exception_text:
        (work / "exception.txt").write_text(exception_text, encoding="utf-8")
    for name, source in {
        "comfyui_server_tail.txt": ROOT / "logs" / "comfyui" / "server.log",
        "engine_tail.txt": ROOT / "logs" / "engine" / "engine.jsonl",
    }.items():
        (work / name).write_text("\n".join(_tail(source, 250)) + "\n", encoding="utf-8")
    if run_id:
        run_dir = ROOT / "logs" / "runs" / run_id
        if run_dir.exists():
            shutil.copytree(run_dir, work / "run", dirs_exist_ok=True)
    config_dir = work / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "configs").glob("*.yaml")):
        try:
            shutil.copy2(source, config_dir / source.name)
        except OSError:
            pass
    manifests = work / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / "models_manifest").glob("*")):
        if source.is_file() and source.stat().st_size < 2_000_000:
            try:
                shutil.copy2(source, manifests / source.name)
            except OSError:
                pass
    inventory = []
    for relative in ["comfyui/runtime", "comfyui/ComfyUI", "comfyui/python_embeded", "workflows", "models_manifest"]:
        base = ROOT / relative
        inventory.append({"path": relative, "exists": base.exists(), "is_dir": base.is_dir()})
    (work / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = output_dir / f"DIAGNOSTIC_{stamp}.zip"
    counter = 1
    while zip_path.exists():
        zip_path = output_dir / f"DIAGNOSTIC_{stamp}_{counter}.zip"
        counter += 1
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(work)))
    shutil.rmtree(work, ignore_errors=True)
    return zip_path


def latest_diagnostic() -> Path | None:
    directory = ROOT / "logs" / "diagnostics"
    if not directory.exists():
        return None
    files = sorted(directory.glob("DIAGNOSTIC_*.zip"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None
