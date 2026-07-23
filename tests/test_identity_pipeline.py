from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from clipctl.frame_generation import (
    IDENTITY_REQUIRED_NODES,
    build_reference_frame_workflow,
)
from clipctl.media_tools import find_ffmpeg


class IdentityPipelineTests(unittest.TestCase):
    def test_reference_workflow_contains_required_nodes(self) -> None:
        workflow = build_reference_frame_workflow(
            "clipctl/reference.png",
            "cinematic portrait",
            "blurry",
            "clipctl/test/frame",
            seed=42,
        )
        classes = {node["class_type"] for node in workflow.values()}
        self.assertTrue(set(IDENTITY_REQUIRED_NODES).issubset(classes))
        self.assertEqual(workflow["7"]["inputs"]["width"], 896)
        self.assertEqual(workflow["7"]["inputs"]["height"], 512)
        self.assertEqual(workflow["8"]["inputs"]["seed"], 42)

    def test_low_vram_reference_profile(self) -> None:
        workflow = build_reference_frame_workflow(
            "reference.png", "portrait", "bad quality", "test", low_vram=True
        )
        self.assertEqual(workflow["7"]["inputs"]["width"], 768)
        self.assertEqual(workflow["7"]["inputs"]["height"], 432)

    def test_identity_manifest_parses(self) -> None:
        root = Path(__file__).resolve().parent.parent
        manifest = yaml.safe_load(
            (root / "configs" / "identity_models.yaml").read_text(encoding="utf-8")
        )
        self.assertIsInstance(manifest, dict)
        files = manifest["group"]["files"]
        self.assertEqual(len(files), 3)
        self.assertFalse(manifest["group"]["biometric_embedding"])

    def test_ffmpeg_discovery_is_safe_when_unavailable(self) -> None:
        result = find_ffmpeg()
        self.assertTrue(result is None or isinstance(result, Path))


if __name__ == "__main__":
    unittest.main()
