#!/usr/bin/env python3
"""Offline checks for bound nine-grid audio; video encoding is mocked."""
import argparse
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepare_nine_grid as preparer


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/templates/nine-grid-reveal"
BOUND_PATH = "assets/audio/reference-bgm.m4a"
BOUND_HASH = "d9b3d892623b9dfc9dee4f8642e2844e3700c13a9795e76b48e3a96b24ac9874"


class BoundBgmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffprobe = shutil.which("ffprobe")
        if not cls.ffprobe:
            raise RuntimeError("ffprobe is required to verify the actual bound audio asset")
        cls.actual_audio = preparer.bound_audio(TEMPLATE, {}, TEMPLATE, cls.ffprobe)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nine-grid-bound-bgm-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.template = self.root / "template"
        self.template.mkdir()
        for filename in preparer.BASE_FILES:
            shutil.copy2(TEMPLATE / filename, self.template / filename)
        for filename in preparer.ASSETS:
            target = self.template / "assets" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"unused video-test dependency")
        self.audio_file = self.template / BOUND_PATH
        self.audio_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TEMPLATE / BOUND_PATH, self.audio_file)
        self.job = {
            "title": "测试公司", "tagline": "品质与细节",
            "grid": [{"path": f"clip-{i}.mp4", "source": "user"} for i in range(9)],
            "main": [{"path": f"clip-{i}.mp4", "source": "user"} for i in range(3)],
        }
        self.commands = []

    def video_record(self, value, minimum, base, ffprobe):
        path = str(base / value["path"])
        return {"path": path, "source": "user", "status": "user-supplied", "record_id": None,
                "sha256": hashlib.sha256(path.encode()).hexdigest(), "probe": {"duration": minimum},
                "color_conversion": {"branch": "SDR-to-Rec709", "filter": "null"}}

    def probe(self, path, kind, minimum, ffprobe):
        if kind == "audio":
            return self.actual_audio["probe"].copy()
        return {"duration": minimum, "codec": "h264", "pix_fmt": "yuv420p",
                "color_primaries": "bt709", "color_transfer": "bt709",
                "color_space": "bt709", "color_range": "tv"}

    def encode_video(self, command):
        self.assertIn("-an", command)
        self.assertNotIn("-c:a", command)
        self.commands.append(command)
        Path(command[-1]).write_bytes(b"mock encoded video")
        return ""

    def run_prepare(self, output_name="output"):
        job_path = self.root / "job.json"
        job_path.write_text(json.dumps(self.job, ensure_ascii=False), encoding="utf-8")
        output = self.root / output_name
        with ExitStack() as stack:
            stack.enter_context(patch.object(preparer.shutil, "which", side_effect=lambda name: name))
            stack.enter_context(patch.object(preparer, "media_info", side_effect=self.probe))
            self.record_mock = stack.enter_context(patch.object(preparer, "record", side_effect=self.video_record))
            stack.enter_context(patch.object(preparer, "run", side_effect=self.encode_video))
            stack.enter_context(redirect_stdout(io.StringIO()))
            preparer.prepare(argparse.Namespace(job=str(job_path), template_dir=str(self.template),
                                                output_dir=str(output)))
        return output

    def assert_prepare_rejected(self, message, output_name="output"):
        with self.assertRaisesRegex(ValueError, message):
            self.run_prepare(output_name)
        self.assertFalse((self.root / output_name).exists())
        self.record_mock.assert_not_called()
        self.assertEqual(self.commands, [])

    def test_actual_bound_asset(self):
        self.assertEqual((TEMPLATE / BOUND_PATH).stat().st_size, 296532)
        self.assertEqual(self.actual_audio["sha256"], BOUND_HASH)
        self.assertEqual(self.actual_audio["probe"]["codec"], "aac")
        self.assertAlmostEqual(self.actual_audio["probe"]["duration"], 12, places=3)
        self.assertEqual(self.actual_audio["start"], 0)
        self.assertEqual(self.actual_audio["volume"], 1)

    def test_omitted_job_bgm_copies_exact_audio_without_variable(self):
        output = self.run_prepare()
        self.assertEqual((output / BOUND_PATH).read_bytes(), self.audio_file.read_bytes())
        variables = json.loads((output / "variables.json").read_text(encoding="utf-8"))
        self.assertNotIn("bgm", variables)
        self.assertEqual(len(variables), 14)
        authored = (output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('data-var-src="bgm"', authored)
        self.assertNotIn('&quot;id&quot;: &quot;bgm&quot;', authored)
        self.assertIn(f'src="{BOUND_PATH}"', authored)
        audio = json.loads((output / "provenance.json").read_text(encoding="utf-8"))["bgm"]
        self.assertEqual(audio["source"], "template-bound")
        self.assertEqual(audio["template_id"], "nine-grid-reveal")
        self.assertEqual(audio["template_path"], BOUND_PATH)
        self.assertEqual(audio["derived_path"], BOUND_PATH)
        self.assertEqual(audio["sha256"], BOUND_HASH)
        self.assertEqual(audio["derived_sha256"], BOUND_HASH)
        self.assertEqual(len(self.commands), 12)

    def test_legacy_identical_copy_is_accepted(self):
        legacy = self.root / "legacy.m4a"
        shutil.copy2(self.audio_file, legacy)
        self.job["bgm"] = legacy.name
        output = self.run_prepare()
        self.assertEqual(preparer.sha256(output / BOUND_PATH), BOUND_HASH)

    def test_legacy_conflicts_are_rejected_before_output(self):
        different = self.root / "different.m4a"
        different.write_bytes(b"different music")
        for index, value in enumerate((None, "auto", "silence", "", different.name)):
            with self.subTest(bgm=value):
                self.job["bgm"] = value
                self.assert_prepare_rejected("template-bound", f"rejected-{index}")

    def test_missing_bound_audio_is_rejected_before_output(self):
        self.audio_file.unlink()
        self.assert_prepare_rejected("Bound BGM file is missing")

    def test_changed_bound_bytes_are_rejected_before_output(self):
        self.audio_file.write_bytes(b"replaced track")
        self.assert_prepare_rejected("Bound BGM hash mismatch")

    def test_bound_path_cannot_leave_template(self):
        manifest_path = self.template / "template.json"
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
        for index, path in enumerate(("../outside.m4a", str(TEMPLATE / BOUND_PATH))):
            with self.subTest(path=path):
                metadata["bgm"]["path"] = path
                manifest_path.write_text(json.dumps(metadata), encoding="utf-8")
                self.assert_prepare_rejected("Bound BGM path must stay inside", f"rejected-{index}")

    def test_bound_duration_mismatch_is_rejected(self):
        with patch.object(preparer, "media_info", return_value={"duration": 11.9, "codec": "aac"}):
            with self.assertRaisesRegex(ValueError, "Bound BGM audio duration"):
                preparer.bound_audio(self.template, {}, self.root, self.ffprobe)


if __name__ == "__main__":
    unittest.main(verbosity=2)
