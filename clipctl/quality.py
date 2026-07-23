from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .core import ROOT, UserError, load_yaml, now_iso, save_yaml, scene_path
from .generation import generate_video
from .group_video_generation import generate_group_video
from .media_tools import find_ffmpeg
from .multicast import validate_scene
from .postprocess import find_video


def review_video(project: str, scene: str) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("İnceleme kareleri için FFmpeg bulunamadı.")
    source = find_video(project, scene)
    report = validate_scene(project, scene)
    out_dir = scene_path(project, scene) / "repaired" / (
        "review_" + now_iso().replace(":", "-")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%02d.jpg"
    command = [
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(source),
        "-vf",
        "fps=1,scale=960:-2",
        "-q:v",
        "2",
        str(pattern),
    ]
    run = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log = out_dir / "review.log"
    log.write_text(
        " ".join(command) + "\n\n" + run.stdout + "\n" + run.stderr,
        encoding="utf-8",
    )
    frames = sorted(out_dir.glob("frame_*.jpg"))
    if run.returncode or not frames:
        raise UserError(
            f"İnceleme kareleri çıkarılamadı. Kod: {run.returncode}. "
            f"Log: {log.relative_to(ROOT)}"
        )

    cast_checks: list[dict[str, Any]] = []
    for member in report.get("cast", []):
        cast_checks.append(
            {
                "id": member.get("id"),
                "identity_id": member.get("identity_id"),
                "look": member.get("look"),
                "role": member.get("role"),
                "face_priority": member.get("face_priority"),
                "blocking": member.get("position"),
                "checks": {
                    "recognizable_in_all_visible_frames": None,
                    "face_not_swapped_with_another_cast_member": None,
                    "approved_wardrobe_unchanged": None,
                    "hair_and_accessories_unchanged": None,
                    "body_and_hands_plausible": None,
                    "blocking_position_stable": None,
                },
            }
        )

    checklist = {
        "source": str(source.relative_to(ROOT)),
        "mode": report.get("mode"),
        "cast_size": report.get("cast_size"),
        "frames": [str(path.relative_to(ROOT)) for path in frames],
        "cast_checks": cast_checks,
        "shot_checks": {
            "exact_character_count_preserved": None,
            "no_duplicate_or_missing_character": None,
            "no_identity_blending": None,
            "wardrobe_palette_consistent": None,
            "lighting_and_shadows_coherent": None,
            "camera_motion_controlled": None,
            "no_temporal_flicker_or_teleportation": None,
            "no_face_occlusion_or_extreme_profile_on_priority_faces": None,
        },
        "manual_instructions": [
            "Her çıkarılmış kareyi sırayla aç.",
            "Her karakteri kendi referans fotoğraflarıyla karşılaştır.",
            "Kıyafetleri wardrobe.yaml içindeki named look ile karşılaştır.",
            "Bir karede bile yüz değişimi, kişi kopyalanması veya kıyafet morph varsa shot'ı reddet.",
            "Yalnızca tüm yüksek öncelikli yüzler ve kişi sayısı stabilse onayla.",
        ],
        "warnings_from_scene_validation": report.get("warnings", []),
    }
    (out_dir / "review.json").write_text(
        json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return checklist


def conservative_repair(
    project: str, scene: str, journal: Any | None = None
) -> dict[str, Any]:
    yaml_path = scene_path(project, scene) / "scene.yaml"
    original = yaml_path.read_text(encoding="utf-8")
    data = load_yaml(yaml_path)
    report = validate_scene(project, scene)
    movement = data.setdefault("movement", {})
    movement["camera_motion"] = "static"
    movement["camera_motion_strength"] = "low"
    movement["body_motion_strength"] = "low"
    movement["head_motion_strength"] = "low"
    rules = data.setdefault("rules", {})
    rules["allow_fast_head_rotation"] = False
    rules["allow_face_occlusion"] = False
    rules["allow_extreme_profile"] = False
    rules["allow_multiple_main_faces"] = report.get("cast_size", 1) > 1
    save_yaml(yaml_path, data)
    repair_dir = scene_path(project, scene) / "repaired"
    repair_dir.mkdir(parents=True, exist_ok=True)
    plan = repair_dir / (
        "repair_plan_" + now_iso().replace(":", "-") + ".json"
    )
    plan.write_text(
        json.dumps(
            {
                "mode": "conservative_regeneration",
                "scene_mode": report.get("mode"),
                "cast_size": report.get("cast_size"),
                "changes": {
                    "camera_motion": "static",
                    "body_motion": "low",
                    "head_motion": "low",
                    "face_occlusion": False,
                    "extreme_profile": False,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        if report.get("cast_size", 1) > 1:
            result = generate_group_video(project, scene, retry=True, journal=journal)
        else:
            result = generate_video(project, scene, retry=True, journal=journal)
        return {"plan": str(plan.relative_to(ROOT)), "generation": result}
    finally:
        yaml_path.write_text(original, encoding="utf-8")
