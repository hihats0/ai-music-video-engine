from __future__ import annotations

import json
import math
import random
import struct
import zlib
from pathlib import Path
from typing import Any

from . import comfy_api
from .core import ROOT, UserError, identity_check, now_iso, scene_path
from .identity_models import identity_model_status
from .multicast import build_prompts, validate_scene
from .workflows import validate_and_adapt_prompt

GROUP_FRAME_REQUIRED_NODES = [
    "CheckpointLoaderSimple",
    "LoadImage",
    "LoadImageMask",
    "IPAdapterUnifiedLoader",
    "IPAdapterAdvanced",
    "CLIPTextEncode",
    "ConditioningSetAreaPercentage",
    "ConditioningCombine",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
]


def _ref(node: str, output: int = 0) -> list[Any]:
    return [node, output]


def _uploaded_name(response: dict[str, Any]) -> str:
    folder = str(response.get("subfolder", "")).strip("/\\")
    name = str(response["name"])
    return f"{folder}/{name}" if folder else name


def _lock_path() -> Path:
    return ROOT / "runtime" / "locks" / "gpu.lock"


def _acquire_lock(project: str, scene: str) -> None:
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise UserError("Başka bir GPU işi çalışıyor. clipctl.bat job status ile kontrol et.")
    path.write_text(
        json.dumps(
            {
                "kind": "group_master_frame",
                "project": project,
                "scene": scene,
                "started_at": now_iso(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_blocking_mask(
    path: Path,
    *,
    width: int,
    height: int,
    position: dict[str, Any],
    feather_pixels: int = 24,
) -> Path:
    """Write an 8-bit grayscale PNG mask using only the standard library."""
    try:
        left = float(position["x"]) * width
        top = float(position["y"]) * height
        right = (float(position["x"]) + float(position["width"])) * width
        bottom = (float(position["y"]) + float(position["height"])) * height
    except (KeyError, TypeError, ValueError) as exc:
        raise UserError(f"Geçersiz blocking kutusu: {position!r}") from exc
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise UserError(f"Blocking kutusu kare sınırları dışında: {position!r}")
    feather = max(0, int(feather_pixels))
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray([0])  # PNG filter type 0
        for x in range(width):
            if x < left - feather or x > right + feather or y < top - feather or y > bottom + feather:
                value = 0
            elif left <= x <= right and top <= y <= bottom:
                value = 255
            elif feather == 0:
                value = 0
            else:
                dx = 0.0 if left <= x <= right else min(abs(x - left), abs(x - right))
                dy = 0.0 if top <= y <= bottom else min(abs(y - top), abs(y - bottom))
                distance = math.sqrt(dx * dx + dy * dy)
                t = max(0.0, min(1.0, 1.0 - distance / feather))
                # Smoothstep reduces hard rectangular seams.
                t = t * t * (3.0 - 2.0 * t)
                value = int(round(255 * t))
            row.append(value)
        rows.append(bytes(row))
    raw = b"".join(rows)
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header) + _png_chunk(
        b"IDAT", zlib.compress(raw, level=9)
    ) + _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


def _identity_weight(member: dict[str, Any]) -> float:
    priority = str(member.get("face_priority", "normal")).lower()
    role = str(member.get("role", "support")).lower()
    if priority == "high":
        return 0.82
    if role in {"lead", "co_lead", "colead"}:
        return 0.74
    return 0.64


def build_group_master_workflow(
    *,
    members: list[dict[str, Any]],
    uploaded_images: dict[str, str],
    uploaded_masks: dict[str, str],
    global_positive: str,
    negative: str,
    regional_prompts: dict[str, str],
    width: int,
    height: int,
    filename_prefix: str,
    seed: int | None = None,
) -> dict[str, Any]:
    if not 1 <= len(members) <= 7:
        raise UserError("Group master workflow 1-7 kişi destekler.")
    if width % 8 or height % 8:
        raise UserError("Başlangıç karesi boyutları 8'in katı olmalı.")
    actual_seed = seed if seed is not None else random.SystemRandom().randint(0, 2**63 - 1)
    prompt: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
        },
        "2": {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {"model": _ref("1"), "preset": "PLUS FACE (portraits)"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": global_positive, "clip": _ref("1", 1)},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": _ref("1", 1)},
        },
    }
    next_id = 5
    model_ref = _ref("2")
    positive_ref = _ref("3")
    for member in members:
        member_id = str(member.get("id") or member.get("identity_id"))
        position = member.get("position", {})
        image_id = str(next_id)
        mask_id = str(next_id + 1)
        adapter_id = str(next_id + 2)
        text_id = str(next_id + 3)
        area_id = str(next_id + 4)
        combine_id = str(next_id + 5)
        next_id += 6
        prompt[image_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": uploaded_images[member_id]},
        }
        prompt[mask_id] = {
            "class_type": "LoadImageMask",
            "inputs": {"image": uploaded_masks[member_id], "channel": "red"},
        }
        prompt[adapter_id] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref,
                "ipadapter": _ref("2", 1),
                "image": _ref(image_id),
                "attn_mask": _ref(mask_id),
                "weight": _identity_weight(member),
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 0.82,
                "embeds_scaling": "K+V w/ C penalty",
                "encode_batch_size": 1,
            },
        }
        prompt[text_id] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": regional_prompts[member_id], "clip": _ref("1", 1)},
        }
        prompt[area_id] = {
            "class_type": "ConditioningSetAreaPercentage",
            "inputs": {
                "conditioning": _ref(text_id),
                "width": float(position["width"]),
                "height": float(position["height"]),
                "x": float(position["x"]),
                "y": float(position["y"]),
                "strength": 1.0 if str(member.get("face_priority")).lower() == "high" else 0.82,
            },
        }
        prompt[combine_id] = {
            "class_type": "ConditioningCombine",
            "inputs": {"conditioning_1": positive_ref, "conditioning_2": _ref(area_id)},
        }
        model_ref = _ref(adapter_id)
        positive_ref = _ref(combine_id)

    latent_id = str(next_id)
    sampler_id = str(next_id + 1)
    decode_id = str(next_id + 2)
    save_id = str(next_id + 3)
    prompt[latent_id] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }
    prompt[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref,
            "positive": positive_ref,
            "negative": _ref("4"),
            "latent_image": _ref(latent_id),
            "seed": actual_seed,
            "steps": 34,
            "cfg": 4.0,
            "sampler_name": "dpmpp_2m_sde",
            "scheduler": "karras",
            "denoise": 1.0,
        },
    }
    prompt[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": _ref(sampler_id), "vae": _ref("1", 2)},
    }
    prompt[save_id] = {
        "class_type": "SaveImage",
        "inputs": {"images": _ref(decode_id), "filename_prefix": filename_prefix},
    }
    return prompt


def generate_group_master_frames(
    project: str,
    scene: str,
    *,
    low_vram: bool = False,
    journal: Any | None = None,
) -> dict[str, Any]:
    report = validate_scene(project, scene)
    if not report["ready"]:
        raise UserError("Group sahne hazır değil:\n- " + "\n- ".join(report["errors"]))
    if report["cast_size"] < 2:
        raise UserError("Bu komut en az iki kişilik group sahne içindir.")
    if not identity_model_status()["ready_on_disk"]:
        raise UserError("Kimlik modelleri eksik: clipctl.bat identity-model install")
    node_report = comfy_api.validate_node_types(GROUP_FRAME_REQUIRED_NODES)
    if not node_report["ok"]:
        raise UserError("Eksik group-frame node'ları: " + ", ".join(node_report["missing"]))

    width, height = ((768, 432) if low_vram else (1024, 576))
    prompts = build_prompts(project, scene)
    members = report["cast"]
    upload_dir = f"clipctl/{project}/{scene}/group_master"
    uploaded_images: dict[str, str] = {}
    uploaded_masks: dict[str, str] = {}
    mask_dir = scene_path(project, scene) / "references" / "blocking_masks"
    for member in members:
        member_id = str(member.get("id") or member.get("identity_id"))
        identity_id = str(member.get("identity_id") or member_id)
        identity = identity_check(identity_id)
        reference = identity["images"][0]
        image_upload = comfy_api.upload_image(reference, subfolder=upload_dir + "/identity")
        uploaded_images[member_id] = _uploaded_name(image_upload)
        mask_path = write_blocking_mask(
            mask_dir / f"{member_id}_{width}x{height}.png",
            width=width,
            height=height,
            position=member["position"],
        )
        mask_upload = comfy_api.upload_image(mask_path, subfolder=upload_dir + "/masks")
        uploaded_masks[member_id] = _uploaded_name(mask_upload)

    regional_prompts = {str(item["id"]): str(item["prompt"]) for item in prompts["regional"]}
    alternatives = max(3, min(4, int(report["scene"].get("generation", {}).get("alternatives", 3))))
    run_dir = scene_path(project, scene) / "frames" / ("group_master_" + now_iso().replace(":", "-"))
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    _acquire_lock(project, scene)
    try:
        for index in range(alternatives):
            workflow = build_group_master_workflow(
                members=members,
                uploaded_images=uploaded_images,
                uploaded_masks=uploaded_masks,
                global_positive=prompts["global_positive"],
                negative=prompts["negative"],
                regional_prompts=regional_prompts,
                width=width,
                height=height,
                filename_prefix=f"clipctl/{project}/{scene}/group_master_{index + 1:02d}",
            )
            workflow = validate_and_adapt_prompt(workflow)
            (run_dir / f"workflow_{index + 1:02d}.json").write_text(
                json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            queued = comfy_api.queue_prompt(
                workflow,
                extra_data={
                    "clipctl": {
                        "project": project,
                        "scene": scene,
                        "kind": "group_master",
                        "cast_size": len(members),
                    }
                },
            )
            prompt_id = str(queued["prompt_id"])
            if journal:
                journal.event(
                    "group_frame.queued",
                    project=project,
                    scene=scene,
                    prompt_id=prompt_id,
                    cast_size=len(members),
                )
            history = comfy_api.wait_for_prompt(prompt_id, timeout=5400)
            (run_dir / f"history_{index + 1:02d}.json").write_text(
                json.dumps(history, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            files = [item for item in comfy_api.extract_output_files(history) if item.get("kind") == "images"]
            if not files:
                raise UserError("Group master işi tamamlandı fakat görsel çıktı yok.")
            for file_index, info in enumerate(files, start=1):
                suffix = Path(info["filename"]).suffix or ".png"
                target = run_dir / f"candidate_{index + 1:02d}_{file_index:02d}{suffix}"
                comfy_api.download_output(info, target)
                outputs.append(str(target.relative_to(ROOT)))
    finally:
        _lock_path().unlink(missing_ok=True)

    metadata = {
        "kind": "group_master",
        "project": project,
        "scene": scene,
        "cast_size": len(members),
        "resolution": {"width": width, "height": height},
        "prompts": prompts,
        "outputs": outputs,
        "created_at": now_iso(),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "outputs": outputs,
        "warnings": report["warnings"],
        "cast_size": len(members),
        "resolution": f"{width}x{height}",
    }
