from __future__ import annotations

import json
import sys
from typing import Any

from .comfy_api import ComfyAPIError
from .core import ROOT, UserError
from .diagnostics import RunJournal
from .extended_cli import main as engine_main
from .lipsync import prepare as prepare_lipsync
from .lipsync import run as run_lipsync
from .lipsync import status as lipsync_status


def _show(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _dispatch(args: list[str]) -> int:
    action = args[1] if len(args) > 1 else ""
    if action == "status":
        state = lipsync_status()
        _show(state)
        return 0 if state["ready"] else 1
    if action == "prepare" and len(args) >= 4:
        _show(prepare_lipsync(args[2], args[3]))
        print("[OK] Solo lipsync girdileri hazırlandı.")
        return 0
    if action == "run" and len(args) >= 4:
        prepared = args[4] if len(args) > 4 else None
        _show(run_lipsync(args[2], args[3], prepared))
        print("[OK] Solo lip-sync çıktısı üretildi.")
        return 0
    raise UserError(
        "Kullanım:\n"
        "  clipctl.bat lipsync status\n"
        "  clipctl.bat lipsync prepare <proje> <sahne>\n"
        "  clipctl.bat lipsync run <proje> <sahne> [hazırlanmış-klasör]"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "lipsync":
        return engine_main(args)
    journal = RunJournal("lipsync." + (args[1] if len(args) > 1 else "help"), argv=args)
    try:
        code = _dispatch(args)
        if code == 0:
            journal.success(exit_code=0)
        return code
    except (UserError, ComfyAPIError) as exc:
        error_code, bundle = journal.failure(
            exc,
            stage="lipsync",
            component=args[1] if len(args) > 1 else "command",
            user_message=str(exc),
        )
        print(f"[HATA] {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1
    except Exception as exc:
        error_code, bundle = journal.failure(
            exc,
            stage="lipsync",
            component=args[1] if len(args) > 1 else "command",
            user_message="Beklenmeyen lipsync hatası",
        )
        print(f"[KRİTİK HATA] {type(exc).__name__}: {exc}")
        print(f"[HATA KODU] {error_code}")
        print(f"[TANI PAKETİ] {bundle.relative_to(ROOT)}")
        return 1
