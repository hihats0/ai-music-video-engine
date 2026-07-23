from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clipctl.lipsync import build_command, load_config, status


class LipSyncTests(unittest.TestCase):
    def test_lipsync_config_is_musetalk_v15(self) -> None:
        config = load_config()
        self.assertEqual(config["backend"], "musetalk_v15")
        self.assertEqual(config["recommended_input_fps"], 25)
        self.assertTrue(config["policy"]["solo_only"])
        self.assertFalse(config["policy"]["allow_group_scene"])

    def test_command_uses_official_normal_inference_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared = Path(directory)
            (prepared / "musetalk_inference.yaml").write_text(
                "clipctl_scene:\n  video_path: video.mp4\n  audio_path: audio.wav\n  bbox_shift: 0\n",
                encoding="utf-8",
            )
            with patch("clipctl.lipsync.find_ffmpeg", return_value=Path("C:/ffmpeg/bin/ffmpeg.exe")):
                command = build_command(prepared)
        self.assertIn("scripts.inference", command)
        self.assertIn("--inference_config", command)
        self.assertIn("--result_dir", command)
        self.assertIn("--unet_model_path", command)
        self.assertIn("--unet_config", command)
        self.assertIn("--version", command)
        self.assertIn("v15", command)
        self.assertIn("--ffmpeg_path", command)

    def test_status_is_non_destructive(self) -> None:
        state = status()
        self.assertIn("ready", state)
        self.assertIn("models", state)
        self.assertIn("installation_note", state)


if __name__ == "__main__":
    unittest.main()
