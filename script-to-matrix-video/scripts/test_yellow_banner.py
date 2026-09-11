#!/usr/bin/env python3
"""Local yellow-banner preparation tests; encoding is mocked, installed BGM is probed."""
from contextlib import ExitStack, redirect_stdout
import html
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepare_triple_strip
import prepare_yellow_banner as preparer


SDR = {"codec": "h264", "pix_fmt": "yuv420p", "color_primaries": "bt709",
       "color_transfer": "bt709", "color_space": "bt709", "color_range": "tv"}
HLG = {**SDR, "pix_fmt": "yuv420p10le", "color_primaries": "bt2020",
       "color_transfer": "arib-std-b67", "color_space": "bt2020nc"}
DEFAULTS = {"title": "企业展示", "subtitle1": "品质成就未来", "subtitle2": "细节创造价值",
            "sourceLabel": "实景记录", "body": "用心做好每一件事\n让品质看得见", "cta": "欢迎咨询了解"}
AUDIO_PATH = "assets/audio/bound-bgm.m4a"


class YellowBannerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="yellow-banner-prepare-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.template = self.root / "template"
        self.template.mkdir()
        schema = [{"id": key, "type": "string", "default": value} for key, value in DEFAULTS.items()]
        self.source = ('<html data-composition-variables="' + html.escape(json.dumps(schema), quote=True) + '">'
                       '<body><div data-composition-id="yellow-banner-zoom" data-duration="10.066666666667">' +
                       "".join(f'<div data-var-text="{key}">{value}</div>' for key, value in DEFAULTS.items()) +
                       f'<audio src="{AUDIO_PATH}" data-start="0" data-duration="10.054"></audio>' +
                       '</div></body></html>')
        (self.template / "index.html").write_text(self.source, encoding="utf-8")
        for name in ("package.json", "hyperframes.json", "index.motion.json", "meta.json"):
            (self.template / name).write_text("{}", encoding="utf-8")
        (self.template / "frame.md").write_text("Fixture design", encoding="utf-8")
        shutil.copy2(Path(__file__).with_name("gpu_runtime.py"), self.template / "gpu_runtime.py")
        (self.template / "compositions").mkdir()
        for index in range(1, 4):
            (self.template / f"compositions/scene-{index:02}.html").write_text(
                f'<template><video src="assets/media/{index:02}.mp4"></video></template>', encoding="utf-8")
        for relative in ("assets/fonts/nested/font.ttf", "assets/vendor/gsap.min.js", AUDIO_PATH):
            path = self.template / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("fixture " + relative).encode())
        self.audio = self.template / AUDIO_PATH
        self.metadata = {"id": preparer.TEMPLATE_ID, "width": 1080, "height": 1920,
                         "fps": 30, "frames": 302, "duration": 302 / 30,
                         "boundBgm": {"path": AUDIO_PATH, "sha256": preparer.sha256(self.audio),
                                      "duration": 10.054, "start": 0, "volume": 1}}
        self.save_metadata()
        self.probes = {}
        for index in range(3):
            source = self.root / f"clip-{index}.mp4"
            source.write_bytes(f"distinct source {index}".encode())
            self.probes[str(source)] = {**SDR, "width": 1920, "height": 1080, "duration": 10}
        self.job = {"media": [{"path": f"clip-{index}.mp4", "source": "user"} for index in range(3)]}
        self.audio_duration = 10.054
        self.commands = []
        self.filter_commands = []
        self.available_filters = "Filters:\n .. libplacebo        V->V       Apply libplacebo effects.\n"
        self.derived = {}

    def save_metadata(self):
        (self.template / "template.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def probe(self, path, kind, minimum, ffprobe):
        if kind == "audio":
            result = {"duration": self.audio_duration, "codec": "aac"}
        else:
            result = self.probes.get(str(path), self.derived.get(str(path)))
            if result is None:
                raise AssertionError(f"Unregistered test video: {path}")
        if result["duration"] + 0.002 < minimum:
            raise ValueError(f"Input must be at least {minimum}s")
        return result.copy()

    def encode(self, command):
        if "-filters" in command:
            self.assertFalse(self.output_path.exists())
            self.filter_commands.append(command)
            return self.available_filters
        self.assertIn("-an", command)
        self.assertIn("-ss", command)
        self.assertIn("-n", command)
        self.assertNotIn("-y", command)
        self.assertNotIn("-c:a", command)
        self.assertNotIn("-stream_loop", command)
        self.assertNotIn("-loop", command)
        filters = command[command.index("-vf") + 1]
        self.assertNotIn("tpad", filters)
        self.assertNotIn("color=", filters)
        self.assertIn("scale=1080:1920", filters)
        self.assertIn("crop=1080:1920", filters)
        frames = int(command[command.index("-frames:v") + 1])
        target = Path(command[-1])
        self.derived[str(target)] = {**SDR, "width": 1080, "height": 1920, "duration": frames / 30}
        target.write_bytes(b"mock normalized video")
        self.commands.append(command)
        return ""

    def run_prepare(self, output_name="output"):
        task = self.root / "task.json"
        task.write_text(json.dumps(self.job, ensure_ascii=False), encoding="utf-8")
        output = self.root / output_name
        self.output_path = output
        args = preparer.argument_parser().parse_args([
            "--task", str(task), "--output", str(output), "--template-dir", str(self.template),
            "--ffmpeg", "custom-ffmpeg", "--ffprobe", "custom-ffprobe"])
        with ExitStack() as stack:
            stack.enter_context(patch.object(preparer.shutil, "which", side_effect=lambda value: value))
            stack.enter_context(patch.object(preparer, "media_info", side_effect=self.probe))
            stack.enter_context(patch.object(preparer, "run", side_effect=self.encode))
            stack.enter_context(patch.object(prepare_triple_strip, "run", side_effect=self.encode))
            stack.enter_context(redirect_stdout(io.StringIO()))
            preparer.prepare(args)
        return output

    def assert_rejected(self, message, output_name="output"):
        with self.assertRaisesRegex(ValueError, message):
            self.run_prepare(output_name)
        self.assertFalse((self.root / output_name).exists())
        self.assertEqual(self.commands, [])

    def test_timing_normalization_defaults_and_byte_identical_bgm(self):
        output = self.run_prepare()
        self.assertEqual(json.loads((output / "variables.json").read_text(encoding="utf-8")), DEFAULTS)
        self.assertEqual((output / AUDIO_PATH).read_bytes(), self.audio.read_bytes())
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual((provenance["width"], provenance["height"], provenance["fps"]), (1080, 1920, 30))
        self.assertEqual((provenance["frames"], provenance["duration"]), (302, 302 / 30))
        self.assertEqual(provenance["cut_frames"], [86, 183])
        self.assertEqual([item["frames"] for item in provenance["videos"]], [86, 97, 119])
        self.assertEqual([item["derived_path"] for item in provenance["videos"]], list(preparer.MEDIA_PATHS.values()))
        self.assertEqual(provenance["bgm"]["sha256"], provenance["bgm"]["derived_sha256"])
        self.assertEqual(provenance["bgm"]["duration"], 10.054)
        self.assertEqual(len(self.commands), 3)
        self.assertTrue(all(command[0] == "custom-ffmpeg" for command in self.commands))

    def test_runtime_dependencies_copied_but_private_video_excluded(self):
        for relative in ("assets/source/reference.MOV", "assets/media/01.mp4", "assets/media/private.json"):
            path = self.template / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"private source")
        (self.template / "private-reference.mp4").write_bytes(b"private source")
        output = self.run_prepare()
        for relative in ("compositions/scene-03.html", "assets/fonts/nested/font.ttf", "index.motion.json", "frame.md"):
            self.assertEqual((output / relative).read_bytes(), (self.template / relative).read_bytes())
        self.assertFalse((output / "assets/source/reference.MOV").exists())
        self.assertFalse((output / "assets/media/private.json").exists())
        self.assertFalse((output / "private-reference.mp4").exists())
        self.assertNotEqual((output / "assets/media/01.mp4").read_bytes(), b"private source")

    def test_text_replacements_empty_optionals_and_multiline_body(self):
        replacements = {"title": "<好&>", "subtitle1": "精工品质", "subtitle2": "", "sourceLabel": "",
                        "body": "第一行\n第二行\n第三行\n第四行", "cta": ""}
        self.job.update(replacements)
        output = self.run_prepare()
        authored = (output / "index.html").read_text(encoding="utf-8")
        _, schema = preparer.variable_schema(authored)
        self.assertEqual({item["id"]: item["default"] for item in schema}, replacements)
        self.assertEqual(json.loads((output / "variables.json").read_text(encoding="utf-8")), replacements)
        for key, value in replacements.items():
            self.assertIn(f'data-var-text="{key}">{html.escape(value)}</div>', authored)

    def test_text_limits_controls_and_required_fields(self):
        cases = [(key, "字" * (limit + 1)) for key, limit in preparer.TEXT_LIMITS.items()]
        cases += [("title", ""), ("subtitle1", "  "), ("body", "\n"), ("body", "a\nb\nc\nd\ne"),
                  ("body", "a\r\nb"), ("body", "a\tb"), ("title", "a\nb"), ("cta", "a\x7fb"), ("cta", None)]
        for index, (key, value) in enumerate(cases):
            self.job[key] = value
            self.assert_rejected(key, f"bad-text-{index}")
            del self.job[key]

    def test_media_count_and_duplicate_content_are_rejected(self):
        saved = self.job["media"]
        self.job["media"] = saved[:2]
        self.assert_rejected("exactly three", "count")
        self.job["media"] = saved
        duplicate = self.root / "duplicate.mp4"
        shutil.copy2(self.root / "clip-0.mp4", duplicate)
        self.probes[str(duplicate)] = self.probes[str(self.root / "clip-0.mp4")]
        self.job["media"][2]["path"] = duplicate.name
        self.assert_rejected("three distinct", "duplicate")

    def test_source_window_is_applied_and_recorded(self):
        self.job["media"][0]["source_start"] = 2.1
        output = self.run_prepare()
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        first = provenance["videos"][0]
        self.assertEqual(first["source_window"], {"in": 2.1, "out": 2.1 + 86 / 30})
        command = next(item for item in self.commands if Path(item[-1]).name == "01.mp4")
        self.assertEqual(command[command.index("-ss") + 1], "2.1")

    def test_invalid_start_and_short_source_are_rejected_before_output(self):
        for index, start in enumerate((-1, float("inf"), float("nan"), None, "1", True)):
            self.job["media"][0]["source_start"] = start
            self.assert_rejected("source_start", f"bad-start-{index}")
        self.job["media"][0]["source_start"] = 8
        self.assert_rejected("at least", "remaining")
        self.job["media"][0]["source_start"] = 0
        self.probes[str(self.root / "clip-2.mp4")]["duration"] = 118 / 30
        self.assert_rejected("at least", "short-last")

    def test_approved_library_and_hlg_use_shared_bt2390_conversion(self):
        self.job["media"][0] = {"path": "clip-0.mp4", "status": "可使用", "record_id": "approved-0"}
        self.probes[str(self.root / "clip-0.mp4")].update(HLG)
        output = self.run_prepare()
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        first = provenance["videos"][0]
        self.assertEqual(first["source"], "library")
        self.assertEqual(first["record_id"], "approved-0")
        self.assertEqual(first["color_conversion"], prepare_triple_strip.color_conversion(first["probe"]))
        self.assertEqual(first["color_conversion"]["algorithm"], "bt.2390")
        command = next(item for item in self.commands if Path(item[-1]).name == "01.mp4")
        self.assertTrue(command[command.index("-vf") + 1].startswith(prepare_triple_strip.HLG_FILTER + ",scale="))
        self.assertEqual(len(self.filter_commands), 1)

    def test_sdr_needs_no_hlg_filter(self):
        self.available_filters = "Filters:\n .. scale V->V Scale video.\n"
        self.run_prepare()
        self.assertEqual(self.filter_commands, [])
        for command in self.commands:
            filters = command[command.index("-vf") + 1]
            self.assertNotIn("tonemap", filters)
            self.assertNotIn("libplacebo", filters)

    def test_missing_hlg_filter_and_unverified_color_are_rejected(self):
        self.probes[str(self.root / "clip-0.mp4")].update(HLG)
        self.available_filters = "Filters:\n .. scale V->V Scale video.\n"
        self.assert_rejected("requires the FFmpeg libplacebo filter", "filter")
        self.probes[str(self.root / "clip-0.mp4")]["color_range"] = None
        self.assert_rejected("Unverified color range", "range")
        self.probes[str(self.root / "clip-0.mp4")].update({**SDR, "camera_log_flag": True})
        self.assert_rejected("Camera LOG", "log")

    def test_unapproved_or_ai_source_rejected_even_with_approval_fields(self):
        self.job["media"][0].update(source="ai", status="可使用", record_id="mislabelled")
        self.assert_rejected("AI assets are not allowed", "ai")
        self.job["media"][0] = {"path": "clip-0.mp4", "status": "待确认", "record_id": "not-approved"}
        self.assert_rejected("AI assets are not allowed", "unapproved")

    def test_bgm_override_missing_and_corrupt_audio_rejected(self):
        self.job["bgm"] = str(self.audio)
        self.assert_rejected("template-bound", "override")
        del self.job["bgm"]
        original = self.audio.read_bytes()
        self.audio.write_bytes(b"other track")
        self.assert_rejected("hash mismatch", "hash")
        self.audio.write_bytes(original)
        self.audio.unlink()
        self.assert_rejected("missing or unreadable", "missing")

    def test_bgm_duration_and_binding_parameters_are_verified(self):
        self.audio_duration = 10.060
        self.assert_rejected("duration must match", "duration-mismatch")
        self.audio_duration = 10.054
        self.metadata["boundBgm"]["duration"] = 17.577
        self.save_metadata()
        self.assert_rejected("within 0.1s", "old-duration")
        self.metadata["boundBgm"]["duration"] = 10.054
        for key, value in (("start", 1), ("volume", 0.5)):
            original = self.metadata["boundBgm"][key]
            self.metadata["boundBgm"][key] = value
            self.save_metadata()
            self.assert_rejected("start=0 and volume=1", key)
            self.metadata["boundBgm"][key] = original

    def test_bgm_path_escape_and_invalid_hash_rejected(self):
        self.metadata["boundBgm"]["path"] = "../other.m4a"
        self.save_metadata()
        self.assert_rejected("must stay inside", "path")
        self.metadata["boundBgm"]["path"] = AUDIO_PATH
        self.metadata["boundBgm"]["sha256"] = "not-a-hash"
        self.save_metadata()
        self.assert_rejected("valid SHA256", "invalid-hash")

    def test_template_timing_drift_rejected_before_output(self):
        for key, value in (("width", 720), ("height", 1280), ("fps", 25), ("frames", 301), ("duration", 10)):
            original = self.metadata[key]
            self.metadata[key] = value
            self.save_metadata()
            self.assert_rejected(f"Template {key}", key)
            self.metadata[key] = original

    def test_static_text_and_media_fallback_bindings_are_required(self):
        index = self.template / "index.html"
        index.write_text(self.source.replace('data-var-text="title"', 'data-old-text="title"'), encoding="utf-8")
        self.assert_rejected("Expected one static title", "text")
        index.write_text(self.source, encoding="utf-8")
        (self.template / "compositions/scene-03.html").write_text(
            '<template><video data-var-src="assets/media/03.mp4"></video></template>', encoding="utf-8")
        self.assert_rejected("missing its fixed video src", "video")

    def test_existing_output_preserved(self):
        output = self.root / "output"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Output directory already exists"):
            self.run_prepare()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual(self.commands, [])


class InstalledTemplateTests(unittest.TestCase):
    def test_actual_template_binding_and_runtime_contract(self):
        template = preparer.DEFAULT_TEMPLATE
        if not (template / "template.json").is_file():
            self.skipTest("Installed template is not available yet")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            self.skipTest("ffprobe is unavailable")
        metadata = json.loads((template / "template.json").read_text(encoding="utf-8-sig"))
        preparer.validate_metadata(metadata)
        audio = preparer.bound_audio(template, metadata, {}, ffprobe)
        self.assertEqual(audio["probe"]["codec"], "aac")
        self.assertEqual(audio["sha256"], metadata["boundBgm"]["sha256"])
        preparer.validate_fixed_media(template, preparer.template_files(template), audio["template_path"])
        source = (template / "index.html").read_text(encoding="utf-8-sig")
        values = preparer.text_values({}, source)
        self.assertEqual(set(values), set(preparer.TEXT_LIMITS))
        self.assertTrue(preparer.update_html(source, values))


if __name__ == "__main__":
    unittest.main(verbosity=2)
