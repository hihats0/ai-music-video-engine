from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from . import comfy_api
from .core import ROOT, UserError, identity_check, now_iso, scene_check, scene_path
from .generation import build_scene_prompt
from .identity_models import identity_model_status
from .workflows import validate_and_adapt_prompt

IDENTITY_REQUIRED_NODES = [
    "CheckpointLoaderSimple", "LoadImage", "IPAdapterUnifiedLoader",
    "IPAdapterAdvanced", "CLIPTextEncode", "EmptyLatentImage",
    "KSampler", "VAEDecode", "SaveImage",
]


def _ref(node: str, output: int = 0) -> list[Any]:
    return [node, output]


def _uploaded_name(response: dict[str, Any]) -> str:
    folder = str(response.get("subfolder", "")).strip("/\\")
    name = str(response["name"])
    return f"{folder}/{name}" if folder else name


def build_reference_frame_workflow(
    image_name: str,
    positive: str,
    negative: str,
    prefix: str,
    seed: int | None = None,
    low_vram: bool = False,
) -> dict[str, Any]:
    width, height = ((768, 432) if low_vram else (896, 512))
    actual_seed = seed if seed is not None else random.SystemRandom().randint(0, 2**63 - 1)
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": _ref("1"), "preset": "PLUS FACE (portraits)"}},
        "4": {"class_type": "IPAdapterAdvanced", "inputs": {
            "model": _ref("3"), "ipadapter": _ref("3", 1), "image": _ref("2"),
            "weight": 0.85, "weight_type": "linear", "combine_embeds": "average",
            "start_at": 0.0, "end_at": 0.9, "embeds_scaling": "K+V w/ C penalty",
            "encode_batch_size": 0,
        }},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": _ref("1", 1)}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": _ref("1", 1)}},
        "7": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": _ref("4"), "positive": _ref("5"), "negative": _ref("6"),
            "latent_image": _ref("7"), "seed": actual_seed, "steps": 28, "cfg": 4.5,
            "sampler_name": "dpmpp_2m_sde", "scheduler": "karras", "denoise": 1.0,
        }},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": _ref("8"), "vae": _ref("1", 2)}},
        "10": {"class_type": "SaveImage", "inputs": {"images": _ref("9"), "filename_prefix": prefix}},
    }


def generate_reference_frames(
    project: str,
    scene: str,
    *,
    low_vram: bool = False,
    journal: Any | None = None,
) -> dict[str, Any]:
    check = scene_check(project, scene)
    if not check["ready"]:
        raise UserError("Sahne alanları eksik; önce scene check çalıştır.")
    identity_name = str(check["identity"])
    identity = identity_check(identity_name)
    if not identity["permission"]:
        raise UserError("Referans kullanımı için permission.confirmed: true gerekli.")
    if not identity["images"]:
        raise UserError("Kimlik source klasöründe referans görsel yok.")
    if not identity_model_status()["ready_on_disk"]:
        raise UserError("Referans kare modelleri eksik: clipctl.bat identity-model install")
    nodes = comfy_api.validate_node_types(IDENTITY_REQUIRED_NODES)
    if not nodes["ok"]:
        raise UserError("Eksik ComfyUI node'ları: " + ", ".join(nodes["missing"]))

    data = check["data"]
    positive, negative = build_scene_prompt(data)
    positive += ". Detailed cinematic keyframe, natural portrait, consistent wardrobe and lighting."
    reference = identity["images"][0]
    upload = comfy_api.upload_image(reference, subfolder=f"clipctl/{project}/{scene}/reference")
    count = max(1, min(4, int(data.get("generation", {}).get("alternatives", 2))))
    run_dir = scene_path(project, scene) / "frames" / ("generated_" + now_iso().replace(":", "-"))
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []

    for index in range(count):
        workflow = build_reference_frame_workflow(
            _uploaded_name(upload), positive, negative,
            f"clipctl/{project}/{scene}/frame_{index + 1:02d}",
            low_vram=low_vram,
        )
        workflow = validate_and_adapt_prompt(workflow)
        (run_dir / f"workflow_{index + 1:02d}.json").write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        queued = comfy_api.queue_prompt(workflow)
        prompt_id = str(queued["prompt_id"])
        if journal:
            journal.event("frame.queued", project=project, scene=scene, prompt_id=prompt_id)
        history = comfy_api.wait_for_prompt(prompt_id, timeout=3600)
        files = [item for item in comfy_api.extract_output_files(history) if item.get("kind") == "images"]
        if not files:
            raise UserError("ComfyUI kare işi tamamlandı fakat görsel çıktı yok.")
        for file_index, info in enumerate(files, start=1):
            suffix = Path(info["filename"]).suffix or ".png"
            target = run_dir / f"candidate_{index + 1:02d}_{file_index:02d}{suffix}"
            comfy_api.download_output(info, target)
            outputs.append(str(target.relative_to(ROOT)))

    return {"run_dir": str(run_dir.relative_to(ROOT)), "outputs": outputs}
