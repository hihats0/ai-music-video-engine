from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

from .core import (
    ROOT,
    UserError,
    identity_check,
    load_yaml,
    now_iso,
    project_path,
    save_yaml,
    scene_path,
)

MAX_CAST = 7
MAX_HIGH_PRIORITY_FACES = 3

_TEMPLATE_FILES = ("cast.yaml", "wardrobe.yaml", "continuity.yaml")

# Normalized x/y/width/height layouts. The layouts intentionally place people
# at different heights and depths instead of using a flat police-line lineup.
_LAYOUTS: dict[int, list[dict[str, Any]]] = {
    1: [
        {"x": 0.33, "y": 0.12, "width": 0.34, "height": 0.82, "depth": "front"},
    ],
    2: [
        {"x": 0.12, "y": 0.16, "width": 0.32, "height": 0.78, "depth": "front"},
        {"x": 0.56, "y": 0.16, "width": 0.32, "height": 0.78, "depth": "front"},
    ],
    3: [
        {"x": 0.34, "y": 0.09, "width": 0.32, "height": 0.84, "depth": "front"},
        {"x": 0.08, "y": 0.23, "width": 0.28, "height": 0.68, "depth": "mid"},
        {"x": 0.64, "y": 0.23, "width": 0.28, "height": 0.68, "depth": "mid"},
    ],
    4: [
        {"x": 0.08, "y": 0.17, "width": 0.27, "height": 0.75, "depth": "front"},
        {"x": 0.36, "y": 0.10, "width": 0.28, "height": 0.82, "depth": "front"},
        {"x": 0.65, "y": 0.21, "width": 0.27, "height": 0.70, "depth": "mid"},
        {"x": 0.28, "y": 0.29, "width": 0.24, "height": 0.60, "depth": "back"},
    ],
    5: [
        {"x": 0.08, "y": 0.19, "width": 0.27, "height": 0.73, "depth": "front"},
        {"x": 0.37, "y": 0.10, "width": 0.28, "height": 0.82, "depth": "front"},
        {"x": 0.66, "y": 0.22, "width": 0.26, "height": 0.69, "depth": "mid"},
        {"x": 0.23, "y": 0.31, "width": 0.23, "height": 0.57, "depth": "back"},
        {"x": 0.52, "y": 0.30, "width": 0.23, "height": 0.58, "depth": "back"},
    ],
    6: [
        {"x": 0.05, "y": 0.19, "width": 0.25, "height": 0.73, "depth": "front"},
        {"x": 0.37, "y": 0.09, "width": 0.27, "height": 0.83, "depth": "front"},
        {"x": 0.70, "y": 0.22, "width": 0.25, "height": 0.69, "depth": "mid"},
        {"x": 0.20, "y": 0.29, "width": 0.22, "height": 0.59, "depth": "mid"},
        {"x": 0.48, "y": 0.31, "width": 0.22, "height": 0.57, "depth": "back"},
        {"x": 0.64, "y": 0.33, "width": 0.20, "height": 0.54, "depth": "back"},
    ],
    7: [
        {"x": 0.04, "y": 0.20, "width": 0.24, "height": 0.72, "depth": "front"},
        {"x": 0.38, "y": 0.08, "width": 0.27, "height": 0.84, "depth": "front"},
        {"x": 0.72, "y": 0.22, "width": 0.24, "height": 0.69, "depth": "mid"},
        {"x": 0.18, "y": 0.31, "width": 0.21, "height": 0.57, "depth": "mid"},
        {"x": 0.49, "y": 0.30, "width": 0.21, "height": 0.58, "depth": "mid"},
        {"x": 0.29, "y": 0.38, "width": 0.19, "height": 0.49, "depth": "back"},
        {"x": 0.61, "y": 0.37, "width": 0.19, "height": 0.50, "depth": "back"},
    ],
}


def project_asset_path(project: str, filename: str) -> Path:
    if filename not in _TEMPLATE_FILES:
        raise UserError(f"Bilinmeyen proje varlığı: {filename}")
    return project_path(project) / filename


def initialize_project(project: str, *, overwrite: bool = False) -> dict[str, Any]:
    root = project_path(project)
    if not root.exists():
        raise UserError(f"Proje bulunamadı: {project}")
    created: list[str] = []
    skipped: list[str] = []
    for filename in _TEMPLATE_FILES:
        source = ROOT / "projects" / "_template" / filename
        target = root / filename
        if target.exists() and not overwrite:
            skipped.append(filename)
            continue
        data = copy.deepcopy(load_yaml(source))
        save_yaml(target, data)
        created.append(filename)
    return {"project": project, "created": created, "skipped": skipped}


def load_project_assets(project: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    initialize_project(project)
    return (
        load_yaml(project_asset_path(project, "cast.yaml")),
        load_yaml(project_asset_path(project, "wardrobe.yaml")),
        load_yaml(project_asset_path(project, "continuity.yaml")),
    )


def _cast_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    members = data.get("cast", {}).get("members", [])
    if not isinstance(members, list):
        raise UserError("cast.yaml içinde cast.members liste olmalı.")
    return [item for item in members if isinstance(item, dict)]


def _member_map(cast_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _cast_list(cast_data):
        member_id = str(item.get("id", "")).strip()
        if member_id:
            result[member_id] = item
    return result


def add_cast_member(
    project: str,
    identity_id: str,
    *,
    role: str = "support",
    look: str = "look_main",
    priority: str = "normal",
) -> dict[str, Any]:
    identity = identity_check(identity_id)
    if not identity["ready"]:
        raise UserError(
            f"Kimlik hazır değil: {identity_id}. En az bir source fotoğrafı ve permission.confirmed: true gerekli."
        )
    cast_data, wardrobe_data, _ = load_project_assets(project)
    members = _cast_list(cast_data)
    if any(str(item.get("id")) == identity_id for item in members):
        raise UserError(f"Karakter zaten cast içinde: {identity_id}")
    if len(members) >= MAX_CAST:
        raise UserError(f"Cast en fazla {MAX_CAST} kişi olabilir.")
    members.append(
        {
            "id": identity_id,
            "identity_id": identity_id,
            "display_name": identity_id.replace("_", " ").replace("-", " ").title(),
            "role": role,
            "priority": priority,
            "approved_look": look,
            "continuity_notes": "",
        }
    )
    cast_data.setdefault("cast", {})["members"] = members
    characters = wardrobe_data.setdefault("wardrobe", {}).setdefault("characters", {})
    characters.setdefault(identity_id, {"looks": {}}).setdefault("looks", {}).setdefault(
        look,
        {
            "outerwear": "",
            "top": "",
            "bottom": "",
            "footwear": "",
            "accessories": [],
            "hair_and_grooming": "match approved identity reference",
            "makeup": "",
            "dominant_colors": [],
            "accent_colors": [],
            "prohibited_substitutions": [],
        },
    )
    save_yaml(project_asset_path(project, "cast.yaml"), cast_data)
    save_yaml(project_asset_path(project, "wardrobe.yaml"), wardrobe_data)
    return {"project": project, "member": members[-1], "cast_size": len(members)}


def default_blocking(count: int) -> list[dict[str, Any]]:
    if count not in _LAYOUTS:
        raise UserError(f"Otomatik blocking 1-{MAX_CAST} kişi destekler.")
    return copy.deepcopy(_LAYOUTS[count])


def configure_scene(project: str, scene: str, member_ids: Iterable[str]) -> Path:
    ids = [str(value).strip() for value in member_ids if str(value).strip()]
    if not ids:
        raise UserError("Sahneye en az bir karakter eklenmeli.")
    if len(ids) > MAX_CAST:
        raise UserError(f"Bir sahnede en fazla {MAX_CAST} karakter olabilir.")
    if len(set(ids)) != len(ids):
        raise UserError("Aynı karakter sahne cast listesinde iki kez kullanılamaz.")
    cast_data, _, _ = load_project_assets(project)
    registry = _member_map(cast_data)
    unknown = [member_id for member_id in ids if member_id not in registry]
    if unknown:
        raise UserError("Önce proje cast listesine ekle: " + ", ".join(unknown))
    path = scene_path(project, scene) / "scene.yaml"
    data = load_yaml(path)
    layout = default_blocking(len(ids))
    scene_cast: list[dict[str, Any]] = []
    for index, member_id in enumerate(ids):
        registered = registry[member_id]
        scene_cast.append(
            {
                "id": member_id,
                "identity_id": str(registered.get("identity_id") or member_id),
                "role": str(registered.get("role", "support")),
                "look": str(registered.get("approved_look", "look_main")),
                "position": layout[index],
                "face_priority": "high" if index < min(2, len(ids)) else "normal",
                "action": "subtle rhythmic performance stance",
                "allow_occlusion": False,
            }
        )
    data.setdefault("scene", {})["mode"] = "solo" if len(ids) == 1 else "group"
    data["cast"] = scene_cast
    if len(ids) == 1:
        data.setdefault("identity", {})["character_id"] = ids[0]
    else:
        data.setdefault("identity", {})["character_id"] = None
        data.setdefault("lipsync", {})["enabled"] = False
        data.setdefault("composition", {})["shot_type"] = "medium_wide"
        data.setdefault("composition", {})["framing"] = "layered_group"
    data.setdefault("scene", {})["updated_at"] = now_iso()
    save_yaml(path, data)
    return path


def _look_for(
    wardrobe_data: dict[str, Any], identity_id: str, look_name: str
) -> dict[str, Any] | None:
    characters = wardrobe_data.get("wardrobe", {}).get("characters", {})
    if not isinstance(characters, dict):
        return None
    character = characters.get(identity_id, {})
    if not isinstance(character, dict):
        return None
    looks = character.get("looks", {})
    return looks.get(look_name) if isinstance(looks, dict) else None


def _strength_rank(value: Any) -> int:
    return {"none": 0, "very_low": 1, "low": 2, "medium_low": 3, "medium": 4, "high": 5}.get(
        str(value).lower(), 99
    )


def _box(member: dict[str, Any]) -> tuple[float, float, float, float] | None:
    position = member.get("position", {})
    try:
        return tuple(float(position[key]) for key in ("x", "y", "width", "height"))  # type: ignore[return-value]
    except (KeyError, TypeError, ValueError):
        return None


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def validate_scene(project: str, scene: str) -> dict[str, Any]:
    cast_data, wardrobe_data, continuity_data = load_project_assets(project)
    registry = _member_map(cast_data)
    path = scene_path(project, scene) / "scene.yaml"
    data = load_yaml(path)
    scene_cast = data.get("cast", [])
    if not isinstance(scene_cast, list):
        scene_cast = []

    # Backward compatibility: treat identity.character_id as a one-person cast.
    if not scene_cast:
        legacy_id = data.get("identity", {}).get("character_id")
        if legacy_id:
            scene_cast = [
                {
                    "id": str(legacy_id),
                    "identity_id": str(legacy_id),
                    "role": "lead",
                    "look": "look_main",
                    "position": default_blocking(1)[0],
                    "face_priority": "high",
                    "action": data.get("movement", {}).get("character_action", ""),
                    "allow_occlusion": False,
                }
            ]

    errors: list[str] = []
    warnings: list[str] = []
    count = len(scene_cast)
    if count < 1 or count > MAX_CAST:
        errors.append(f"cast sayısı 1-{MAX_CAST} arasında olmalı; mevcut: {count}")

    ids: list[str] = []
    boxes: list[tuple[str, tuple[float, float, float, float], bool]] = []
    high_priority = 0
    for index, item in enumerate(scene_cast):
        if not isinstance(item, dict):
            errors.append(f"cast[{index}] sözlük olmalı")
            continue
        member_id = str(item.get("id") or item.get("identity_id") or "").strip()
        identity_id = str(item.get("identity_id") or member_id).strip()
        if not member_id or not identity_id:
            errors.append(f"cast[{index}] id ve identity_id gerekli")
            continue
        ids.append(member_id)
        if member_id not in registry and count > 1:
            errors.append(f"proje cast kaydında yok: {member_id}")
        try:
            identity = identity_check(identity_id)
            if not identity["ready"]:
                errors.append(f"kimlik hazır değil veya izin eksik: {identity_id}")
        except UserError as exc:
            errors.append(str(exc))
        look_name = str(item.get("look", "")).strip()
        if not look_name:
            errors.append(f"{member_id}: look adı gerekli")
        elif _look_for(wardrobe_data, identity_id, look_name) is None:
            errors.append(f"{member_id}: wardrobe look bulunamadı: {look_name}")
        if not str(item.get("action", "")).strip():
            errors.append(f"{member_id}: action gerekli")
        box = _box(item)
        if box is None:
            errors.append(f"{member_id}: position x/y/width/height gerekli")
        else:
            x, y, width, height = box
            if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1 or y + height > 1:
                errors.append(f"{member_id}: blocking kutusu 0.0-1.0 kare sınırları içinde olmalı")
            boxes.append((member_id, box, bool(item.get("allow_occlusion", False))))
        if str(item.get("face_priority", "normal")).lower() == "high":
            high_priority += 1

    if len(set(ids)) != len(ids):
        errors.append("aynı karakter sahnede iki kez kullanılamaz")
    maximum_high = int(
        continuity_data.get("continuity", {})
        .get("group_shots", {})
        .get("maximum_high_priority_faces", MAX_HIGH_PRIORITY_FACES)
    )
    if high_priority > maximum_high:
        errors.append(f"high face_priority en fazla {maximum_high}; mevcut: {high_priority}")

    for left_index, (left_id, left_box, left_allow) in enumerate(boxes):
        for right_id, right_box, right_allow in boxes[left_index + 1 :]:
            overlap = _iou(left_box, right_box)
            if overlap > 0.55 and not (left_allow or right_allow):
                warnings.append(
                    f"yüksek blocking çakışması: {left_id}/{right_id} IoU={overlap:.2f}; yüz veya beden birleşmesi riski"
                )

    composition = data.get("composition", {})
    style = data.get("style", {})
    lighting = data.get("lighting", {})
    movement = data.get("movement", {})
    if not str(composition.get("location", "")).strip():
        errors.append("composition.location gerekli")
    if not str(style.get("mood", "")).strip():
        errors.append("style.mood gerekli")
    if not (str(lighting.get("style", "")).strip() or str(lighting.get("key_light", "")).strip()):
        warnings.append("lighting.style veya lighting.key_light boş; shot continuity zayıflayabilir")

    mode = "solo" if count == 1 else "group"
    lipsync_enabled = bool(data.get("lipsync", {}).get("enabled", False))
    if mode == "group" and lipsync_enabled:
        errors.append("group sahnede lipsync kapalı olmalı; solo shot kullan")
    if mode == "group":
        allowed_shots = (
            continuity_data.get("continuity", {})
            .get("group_shots", {})
            .get("allowed_shot_types", ["wide", "medium_wide", "full_body_group"])
        )
        if composition.get("shot_type") not in allowed_shots:
            errors.append("group shot_type şunlardan biri olmalı: " + ", ".join(map(str, allowed_shots)))
        policy = continuity_data.get("continuity", {}).get("group_shots", {})
        for key in ("camera_motion_strength", "body_motion_strength", "head_motion_strength"):
            configured = movement.get(key, "low")
            maximum = policy.get(f"maximum_{key}", "low")
            if _strength_rank(configured) > _strength_rank(maximum):
                errors.append(f"group {key} en fazla {maximum}; mevcut: {configured}")

    return {
        "ready": not errors,
        "mode": mode,
        "cast_size": count,
        "errors": errors,
        "warnings": warnings,
        "cast": scene_cast,
        "scene": data,
        "registry": registry,
        "wardrobe": wardrobe_data,
        "continuity": continuity_data,
    }


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def _look_prompt(look: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, label in (
        ("outerwear", "outerwear"),
        ("top", "top"),
        ("bottom", "bottom"),
        ("footwear", "footwear"),
        ("accessories", "accessories"),
        ("hair_and_grooming", "hair and grooming"),
        ("makeup", "makeup"),
        ("dominant_colors", "dominant colors"),
        ("accent_colors", "accent colors"),
    ):
        text = _list_text(look.get(key))
        if text:
            parts.append(f"{label}: {text}")
    return "; ".join(parts)


def build_prompts(project: str, scene: str) -> dict[str, Any]:
    report = validate_scene(project, scene)
    if not report["ready"]:
        raise UserError("Multi-character sahne hazır değil:\n- " + "\n- ".join(report["errors"]))
    data = report["scene"]
    scene_cast = report["cast"]
    wardrobe = report["wardrobe"]
    composition = data.get("composition", {})
    lighting = data.get("lighting", {})
    movement = data.get("movement", {})
    style = data.get("style", {})
    count = len(scene_cast)
    global_positive = ", ".join(
        part
        for part in (
            "photorealistic live-action cinematic music video frame",
            f"exactly {count} distinct people, no duplicate people",
            str(composition.get("location", "")),
            str(composition.get("time_of_day", "")),
            f"{composition.get('shot_type', 'medium_wide')} shot",
            f"{composition.get('lens_mm', 35)}mm cinematic lens language",
            str(composition.get("framing", "layered_group")),
            str(lighting.get("style", "")),
            str(lighting.get("key_light", "")),
            str(lighting.get("background_light", "")),
            str(style.get("mood", "")),
            str(style.get("color_description", "")),
            "natural skin texture, realistic anatomy, realistic hands, coherent shadows",
            "layered depth, controlled occlusion, physically plausible perspective",
            f"camera movement concept: {movement.get('camera_motion', 'static')}",
        )
        if part and str(part).strip()
    )
    negative = ", ".join(
        (
            "extra people, missing people, duplicate person, cloned person",
            "merged faces, blended identity, swapped faces, same face on multiple bodies",
            "deformed face, asymmetric eyes, malformed body, extra limbs, extra fingers",
            "wardrobe color drift, changed outfit, random accessories",
            "beautified plastic skin, waxy skin, illustration, CGI, anime",
            "motion blur on faces, heavy occlusion, extreme profile, cropped head",
            "text, watermark, logo",
        )
    )
    regional: list[dict[str, Any]] = []
    for member in scene_cast:
        member_id = str(member.get("id") or member.get("identity_id"))
        identity_id = str(member.get("identity_id") or member_id)
        look_name = str(member.get("look", "look_main"))
        look = _look_for(wardrobe, identity_id, look_name) or {}
        position = member.get("position", {})
        regional.append(
            {
                "id": member_id,
                "identity_id": identity_id,
                "look": look_name,
                "position": position,
                "face_priority": str(member.get("face_priority", "normal")),
                "prompt": ", ".join(
                    part
                    for part in (
                        f"one distinct person named {member_id}",
                        f"role: {member.get('role', 'support')}",
                        _look_prompt(look),
                        f"action: {member.get('action', 'subtle stance')}",
                        "preserve exact face shape, hairline, skin texture and distinguishing features from reference",
                    )
                    if part and str(part).strip()
                ),
            }
        )
    return {
        "global_positive": global_positive,
        "negative": negative,
        "regional": regional,
        "cast_size": count,
        "mode": report["mode"],
        "warnings": report["warnings"],
    }
