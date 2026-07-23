from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def fetch(path: str, timeout: float = 5.0):
    request = urllib.request.Request("http://127.0.0.1:8188" + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        stats = fetch("/system_stats")
        queue = fetch("/queue")
    except (OSError, ValueError, urllib.error.URLError) as exc:
        if not args.quiet:
            print(f"[HATA] ComfyUI API yanıt vermiyor: {type(exc).__name__}: {exc}")
        return 1
    if not args.quiet:
        print("[OK] ComfyUI API çevrimiçi: http://127.0.0.1:8188")
        print(json.dumps({"devices": stats.get("devices", []), "queue": queue}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
