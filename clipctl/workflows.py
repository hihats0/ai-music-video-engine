from __future__ import annotations

import copy
import random
from typing import Any

from .comfy_api import object_info
from .core import UserError

WAN_REQUIRED_NODES = ["UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "LoadImage", "Wan22ImageToVideoLatent", "ModelSamplingSD3", "KSampler", "VAEDecode", "CreateVideo", "SaveVideo"]


def _ref(node_id: str, output_index: int = 0) -> list[Any]:
    return [node_id, output_index]


def normalize_wan_length(seconds: float, fps: int) -> int:
    raw = max(17, int(round(seconds * fps)))
    return raw - ((raw - 1) % 4)


def build_wan22_i2v_prompt(*, uploaded_image: str, positive: str, negative: str, width: int = 832, height: int = 480, seconds: float = 4.0, fps: int = 24, steps: int = 20, cfg: float = 5.0, sampler: str = "uni_pc", scheduler: str = "simple", shift: float = 8.0, seed: int | None = None, filename_prefix: str = "clipctl/scene") -> dict[str, Any]:
    if width % 16 or height % 16:
        raise UserError("Wan video genişlik ve yükseklik değerleri 16'nın katı olmalı.")
    if width > 960 or height > 544:
        raise UserError("8 GB VRAM profili için çözünürlük fazla yüksek. Önerilen: 832x480; kurtarma: 704x400.")
    length = normalize_wan_length(seconds, fps)
    actual_seed = seed if seed is not None else random.SystemRandom().randint(0, 2**63 - 1)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": _ref("2")}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": _ref("2")}},
        "6": {"class_type": "LoadImage", "inputs": {"image": uploaded_image}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": _ref("3"), "start_image": _ref("6"), "width": width, "height": height, "length": length, "batch_size": 1}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": _ref("1"), "shift": shift}},
        "9": {"class_type": "KSampler", "inputs": {"model": _ref("8"), "positive": _ref("4"), "negative": _ref("5"), "latent_image": _ref("7"), "seed": actual_seed, "steps": steps, "cfg": cfg, "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": _ref("9"), "vae": _ref("3")}},
        "11": {"class_type": "CreateVideo", "inputs": {"images": _ref("10"), "fps": fps}},
        "12": {"class_type": "SaveVideo", "inputs": {"video": _ref("11"), "filename_prefix": filename_prefix, "format": "auto", "codec": "auto"}},
    }


def validate_and_adapt_prompt(prompt: dict[str, Any], *, object_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = object_schema or object_info()
    missing_classes: list[str] = []
    errors: list[str] = []
    adapted = copy.deepcopy(prompt)
    for node_id, node in adapted.items():
        class_type = str(node.get("class_type"))
        definition = schema.get(class_type)
        if not isinstance(definition, dict):
            missing_classes.append(class_type)
            continue
        input_definition = definition.get("input", {})
        required = input_definition.get("required", {}) if isinstance(input_definition, dict) else {}
        optional = input_definition.get("optional", {}) if isinstance(input_definition, dict) else {}
        allowed = set(required) | set(optional)
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            errors.append(f"Node {node_id}/{class_type}: inputs sözlük değil")
            continue
        for name in list(inputs):
            if name not in allowed and not isinstance(inputs[name], list):
                inputs.pop(name)
        for name in required:
            if name not in inputs:
                errors.append(f"Node {node_id}/{class_type}: zorunlu input eksik: {name}")
    if missing_classes:
        raise UserError("ComfyUI içinde gerekli node'lar bulunamadı: " + ", ".join(sorted(set(missing_classes))) + "\nComfyUI'ı güncelle ve server.log içindeki import hatalarını kontrol et.")
    if errors:
        raise UserError("Workflow kurulu ComfyUI sürümüyle uyuşmuyor:\n- " + "\n- ".join(errors))
    return adapted
