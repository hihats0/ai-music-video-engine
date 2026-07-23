from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .core import ROOT, UserError, load_yaml, now_iso, save_yaml, scene_path
from .generation import generate_video
from .media_tools import find_ffmpeg
from .postprocess import find_video


def review_video(project: str, scene: str) -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise UserError("İnceleme kareleri için FFmpeg bulunamadı.")
    source = find_video(project, scene)
    out_dir = scene_path(project, scene) / "repaired" / ("review_" + now_iso().replace(":", "-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%02d.jpg"
    command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "warning", "-i", str(source),
        "-vf", "fps=1,scale=640:-2", "-q:v", "2", str(pattern),
    ]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    log = out_dir / "review.log"
    log.write_text(" ".join(command) + "\n\n" + run.stdout + "\n" + run.stderr, encoding="utf-8")
    frames = sorted(out_dir.glob("frame_*.jpg"))
    if run.returncode or not frames:
        raise UserError(f"İnceleme kareleri çıkarılamadı. Kod: {run.returncode}. Log: {log.relative_to(ROOT)}")
    checklist = {
        "source": str(source.relative_to(ROOT)),
        "frames": [str(path.relative_to(ROOT)) for path in frames],
        "manual_checks": [
            "Aynı kişi olarak tanınabilir mi?",
            "Gözler ve ağız kareler arasında tutarlı mı?",
            "Yüz kapanıyor veya aşırı profile dönüyor mu?",
            "Eller yüze yaklaşınca bozulma var mı?",
            "Titreşim veya ani kimlik değişimi var mı?",
        ],
    }
    (out_dir / "review.json").write_text(json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    return checklist


def conservative_repair(project: str, scene: str, journal: Any | None = None) -> dict[str, Any]:
    yaml_path = scene_path(project, scene) / "scene.yaml"
    original = yaml_path.read_text(encoding="utf-8")
    data = load_yaml(yaml_path)
    movement = data.setdefault("movement", {})
    movement["camera_motion_strength"] = "low"
    movement["body_motion_strength"] = "low"
    movement["head_motion_strength"] = "low"
    rules = data.setdefault("rules", {})
    rules["allow_fast_head_rotation"] = False
    rules["allow_face_occlusion"] = False
    rules["allow_extreme_profile"] = False
    rules["allow_multiple_main_faces"] = False
    save_yaml(yaml_path, data)
    repair_dir = scene_path(project, scene) / "repaired"
    repair_dir.mkdir(parents=True, exist_ok=True)
    plan = repair_dir / ("repair_plan_" + now_iso().replace(":", "-") + ".json")
    plan.write_text(
        json.dumps({"mode": "conservative_regeneration", "changes": {"motion": "low", "face_occlusion": False, "extreme_profile": False}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        result = generate_video(project, scene, retry=True, journal=journal)
        return {"plan": str(plan.relative_to(ROOT)), "generation": result}
    finally:
        yaml_path.write_text(original, encoding="utf-8")
