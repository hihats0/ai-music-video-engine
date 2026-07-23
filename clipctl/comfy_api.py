from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8188"


def get_json(path: str, timeout: float = 5.0) -> Any:
    request = urllib.request.Request(BASE_URL + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def status(timeout: float = 3.0) -> dict[str, Any]:
    try:
        stats = get_json("/system_stats", timeout=timeout)
        queue = get_json("/queue", timeout=timeout)
        return {"online": True, "url": BASE_URL, "system_stats": stats, "queue": queue}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"online": False, "url": BASE_URL, "reason": f"{type(exc).__name__}: {exc}"}


def wait_until_online(timeout: float = 180.0, interval: float = 2.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = status()
    while time.monotonic() < deadline:
        last = status()
        if last.get("online"):
            return last
        time.sleep(interval)
    return last
