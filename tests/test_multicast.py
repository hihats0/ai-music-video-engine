from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from clipctl.group_frame_generation import (
    GROUP_FRAME_REQUIRED_NODES,
    build_group_master_workflow,
    write_blocking_mask,
)
from clipctl.multicast import default_blocking


class MultiCharacterTests(unittest.TestCase):
    def test_seven_person_layout_stays_inside_frame(self) -> None:
        layout = default_blocking(7)
        self.assertEqual(len(layout), 7)
        for box in layout:
            self.assertGreater(box["width"], 0)
            self.assertGreater(box["height"], 0)
            self.assertGreaterEqual(box["x"], 0)
            self.assertGreaterEqual(box["y"], 0)
            self.assertLessEqual(box["x"] + box["width"], 1)
            self.assertLessEqual(box["y"] + box["height"], 1)

    def test_group_workflow_has_one_masked_adapter_per_person(self) -> None:
        layout = default_blocking(7)
        members = []
        uploaded_images = {}
        uploaded_masks = {}
        regional_prompts = {}
        for index, position in enumerate(layout, start=1):
            member_id = f"person_{index}"
            members.append(
                {
                    "id": member_id,
                    "identity_id": member_id,
                    "role": "lead" if index == 1 else "support",
                    "face_priority": "high" if index <= 2 else "normal",
                    "position": position,
                }
            )
            uploaded_images[member_id] = f"identity/{member_id}.png"
            uploaded_masks[member_id] = f"masks/{member_id}.png"
            regional_prompts[member_id] = f"distinct person {index}"

        workflow = build_group_master_workflow(
            members=members,
            uploaded_images=uploaded_images,
            uploaded_masks=uploaded_masks,
            global_positive="photorealistic group",
            negative="duplicate people",
            regional_prompts=regional_prompts,
            width=1024,
            height=576,
            filename_prefix="clipctl/test/group",
            seed=42,
        )
        classes = [node["class_type"] for node in workflow.values()]
        self.assertEqual(classes.count("IPAdapterAdvanced"), 7)
        self.assertEqual(classes.count("LoadImageMask"), 7)
        self.assertEqual(classes.count("ConditioningSetAreaPercentage"), 7)
        self.assertTrue(set(GROUP_FRAME_REQUIRED_NODES).issubset(set(classes)))
        sampler = next(node for node in workflow.values() if node["class_type"] == "KSampler")
        self.assertEqual(sampler["inputs"]["seed"], 42)

    def test_blocking_mask_is_valid_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "mask.png"
            write_blocking_mask(
                target,
                width=128,
                height=72,
                position={"x": 0.2, "y": 0.1, "width": 0.4, "height": 0.8},
                feather_pixels=8,
            )
            payload = target.read_bytes()
            self.assertTrue(payload.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(len(payload), 100)

    def test_templates_parse(self) -> None:
        root = Path(__file__).resolve().parent.parent
        for filename in ("cast.yaml", "wardrobe.yaml", "continuity.yaml"):
            data = yaml.safe_load((root / "projects" / "_template" / filename).read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)


if __name__ == "__main__":
    unittest.main()
