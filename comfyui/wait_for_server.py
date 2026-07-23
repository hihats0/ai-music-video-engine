from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request


def online() -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8188/system_stats", timeout=5
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if online():
            print("[OK] ComfyUI API hazir.")
            return 0
        print("[BILGI] ComfyUI aciliyor...", flush=True)
        time.sleep(5)

    print("[HATA] ComfyUI belirtilen sure icinde API yaniti vermedi.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
