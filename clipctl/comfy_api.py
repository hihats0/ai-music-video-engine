from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

BASE_URL = "http://127.0.0.1:8188"


class ComfyAPIError(RuntimeError):
    pass


def _request(path: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 30.0) -> bytes:
    request_headers = {"Accept": "application/json", **(headers or {})}
    request = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ComfyAPIError(f"HTTP {exc.code} {path}: {body[:4000]}") from exc
    except urllib.error.URLError as exc:
        raise ComfyAPIError(f"ComfyUI API bağlantı hatası {path}: {exc}") from exc


def get_json(path: str, timeout: float = 5.0) -> Any:
    return json.loads(_request(path, timeout=timeout).decode("utf-8"))


def post_json(path: str, payload: dict[str, Any], timeout: float = 30.0) -> Any:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    raw = _request(path, method="POST", data=data, headers={"Content-Type": "application/json"}, timeout=timeout)
    return json.loads(raw.decode("utf-8")) if raw else {}


def status(timeout: float = 3.0) -> dict[str, Any]:
    try:
        stats = get_json("/system_stats", timeout=timeout)
        queue = get_json("/queue", timeout=timeout)
        return {"online": True, "url": BASE_URL, "system_stats": stats, "queue": queue}
    except (OSError, ValueError, ComfyAPIError) as exc:
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


def object_info(class_name: str | None = None, timeout: float = 30.0) -> dict[str, Any]:
    path = "/object_info"
    if class_name:
        path += "/" + urllib.parse.quote(class_name)
    result = get_json(path, timeout=timeout)
    if not isinstance(result, dict):
        raise ComfyAPIError("ComfyUI object_info beklenmeyen yanıt döndürdü.")
    return result


def validate_node_types(required: list[str]) -> dict[str, Any]:
    info = object_info()
    missing = [name for name in required if name not in info]
    return {"ok": not missing, "missing": missing, "available_count": len(info)}


def upload_image(image_path: Path, *, subfolder: str = "clipctl", overwrite: bool = True, timeout: float = 120.0) -> dict[str, Any]:
    if not image_path.exists() or not image_path.is_file():
        raise ComfyAPIError(f"Yüklenecek görsel bulunamadı: {image_path}")
    boundary = "----clipctl-" + uuid.uuid4().hex
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"), b"\r\n",
        ])

    chunks.extend([
        f"--{boundary}\r\n".encode(),
        (f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n').encode("utf-8"),
        f"Content-Type: {mime}\r\n\r\n".encode(), image_path.read_bytes(), b"\r\n",
    ])
    field("type", "input")
    field("subfolder", subfolder)
    field("overwrite", "true" if overwrite else "false")
    chunks.append(f"--{boundary}--\r\n".encode())
    raw = _request("/upload/image", method="POST", data=b"".join(chunks), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=timeout)
    response = json.loads(raw.decode("utf-8"))
    if not isinstance(response, dict) or "name" not in response:
        raise ComfyAPIError(f"Görsel yükleme yanıtı geçersiz: {response!r}")
    return response


def queue_prompt(prompt: dict[str, Any], *, client_id: str | None = None, extra_data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"prompt": prompt, "client_id": client_id or uuid.uuid4().hex}
    if extra_data:
        payload["extra_data"] = extra_data
    response = post_json("/prompt", payload, timeout=60.0)
    prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
    if not prompt_id:
        raise ComfyAPIError(f"Prompt kuyruğa alınamadı: {response!r}")
    return response


def queue_state() -> dict[str, Any]:
    result = get_json("/queue", timeout=10.0)
    if not isinstance(result, dict):
        raise ComfyAPIError("Kuyruk yanıtı geçersiz.")
    return result


def history(prompt_id: str) -> dict[str, Any] | None:
    result = get_json(f"/history/{urllib.parse.quote(prompt_id)}", timeout=20.0)
    if not isinstance(result, dict):
        return None
    item = result.get(prompt_id)
    return item if isinstance(item, dict) else None


def wait_for_prompt(prompt_id: str, *, timeout: float = 7200.0, interval: float = 3.0, on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_queue: dict[str, Any] = {}
    while time.monotonic() < deadline:
        item = history(prompt_id)
        if item is not None:
            status_data = item.get("status", {})
            status_string = status_data.get("status_str") if isinstance(status_data, dict) else None
            if status_string == "error":
                messages = status_data.get("messages", [])
                raise ComfyAPIError("ComfyUI üretim hatası: " + json.dumps(messages, ensure_ascii=False, default=str)[:8000])
            return item
        try:
            last_queue = queue_state()
            if on_progress:
                on_progress(last_queue)
        except ComfyAPIError:
            pass
        time.sleep(interval)
    raise ComfyAPIError(f"ComfyUI işi zaman aşımına uğradı: {prompt_id}. Son kuyruk: {last_queue!r}")


def extract_output_files(history_item: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    outputs = history_item.get("outputs", {})
    if not isinstance(outputs, dict):
        return found
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        for key in ("images", "gifs", "videos", "audio"):
            entries = node_output.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("filename"):
                    continue
                found.append({"node_id": str(node_id), "kind": key, "filename": str(entry["filename"]), "subfolder": str(entry.get("subfolder", "")), "type": str(entry.get("type", "output"))})
    return found


def download_output(file_info: dict[str, str], destination: Path) -> Path:
    query = urllib.parse.urlencode({"filename": file_info["filename"], "subfolder": file_info.get("subfolder", ""), "type": file_info.get("type", "output")})
    raw = _request("/view?" + query, timeout=300.0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return destination


def interrupt() -> None:
    post_json("/interrupt", {}, timeout=10.0)
