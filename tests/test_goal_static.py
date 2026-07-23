from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from clipctl.generation import build_scene_prompt
from clipctl.workflows import build_wan22_i2v_prompt, normalize_wan_length


class GoalStaticTests(unittest.TestCase):
    def test_wan_length_uses_four_n_plus_one_rule(self) -> None:
        length = normalize_wan_length(4.0, 24)
        self.assertGreaterEqual(length, 81)
        self.assertEqual((length - 1) % 4, 0)

    def test_wan_prompt_contains_complete_pipeline(self) -> None:
        prompt = build_wan22_i2v_prompt(
            uploaded_image="clipctl/reference.png",
            positive="cinematic performer",
            negative="blurry",
        )
        classes = {node["class_type"] for node in prompt.values()}
        expected = {
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "CLIPTextEncode",
            "LoadImage",
            "Wan22ImageToVideoLatent",
            "ModelSamplingSD3",
            "KSampler",
            "VAEDecode",
            "CreateVideo",
            "SaveVideo",
        }
        self.assertTrue(expected.issubset(classes))
        self.assertEqual(prompt["7"]["inputs"]["width"], 832)
        self.assertEqual(prompt["7"]["inputs"]["height"], 480)

    def test_workflow_rejects_excessive_8gb_resolution(self) -> None:
        with self.assertRaises(Exception):
            build_wan22_i2v_prompt(
                uploaded_image="reference.png",
                positive="test",
                negative="test",
                width=1280,
                height=720,
            )

    def test_scene_prompt_contains_user_scene_fields(self) -> None:
        positive, negative = build_scene_prompt(
            {
                "identity": {"character_id": "artist_01"},
                "composition": {
                    "location": "underground parking garage",
                    "time_of_day": "night",
                    "wardrobe": "black leather jacket",
                    "shot_type": "medium_closeup",
                    "camera_angle": "eye_level",
                    "framing": "centered",
                },
                "lighting": {
                    "style": "cinematic",
                    "key_light": "red side light",
                    "background_light": "blue back light",
                    "contrast": "high",
                },
                "movement": {
                    "character_action": "looks into camera",
                    "camera_motion": "slow push in",
                    "camera_motion_strength": "low",
                    "body_motion_strength": "low",
                    "head_motion_strength": "low",
                },
                "style": {
                    "visual_style": "rap music video",
                    "mood": "dark",
                    "color_description": "red blue black",
                    "film_texture": "subtle",
                },
                "rules": {},
            }
        )
        self.assertIn("underground parking garage", positive)
        self.assertIn("black leather jacket", positive)
        self.assertIn("fast head rotation", negative)

    def test_repository_yaml_files_parse(self) -> None:
        root = Path(__file__).resolve().parent.parent
        for relative in (
            "configs/wan_models.yaml",
            "configs/pipeline.yaml",
            "projects/_template/scenes/_template/scene.yaml",
            "identities/_template/identity.yaml",
        ):
            path = root / relative
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict, relative)


if __name__ == "__main__":
    unittest.main()
