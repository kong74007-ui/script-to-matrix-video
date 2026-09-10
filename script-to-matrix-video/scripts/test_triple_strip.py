#!/usr/bin/env python3
"""Fast local triple-strip preparation checks; media encoding is mocked."""
from contextlib import ExitStack, redirect_stdout
import html
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepare_triple_strip as preparer


SDR = {"codec": "h264", "pix_fmt": "yuv420p", "color_primaries": "bt709",
       "color_transfer": "bt709", "color_space": "bt709", "color_range": "tv"}
HLG = {**SDR, "pix_fmt": "yuv420p10le", "color_primaries": "bt2020",
       "color_transfer": "arib-std-b67", "color_space": "bt2020nc"}
DEFAULTS = {"title": "企业展示", "subtitle": "品质成就未来", "ctaLine1": "了解更多", "ctaLine2": "欢迎咨询"}
AUDIO_PATH = "assets/audio/bound-bgm.m4a"


class TripleStripTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="triple-strip-prepare-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.template = self.root / "template"
        self.template.mkdir()
        schema = [{"id": key, "type": "string", "label": key, "default": value}
                  for key, value in DEFAULTS.items()]
        self.source = ('<html data-composition-variables="' + html.escape(json.dumps(schema), quote=True) + '">'
                       '<body><div data-composition-id="triple-strip-shutter" data-duration="17.6">' +
                       "".join(f'<div data-var-text="{key}">{value}</div>' for key, value in DEFAULTS.items()) +
                       f'<audio id="bgm" src="{AUDIO_PATH}" data-start="0" data-duration="17.6"></audio>' +
                       '</div></body></html>')
        (self.template / "index.html").write_text(self.source, encoding="utf-8")
        for name in ("package.json", "hyperframes.json", "index.motion.json", "meta.json"):
            (self.template / name).write_text("{}", encoding="utf-8")
        (self.template / "frame.md").write_text("Fixture design", encoding="utf-8")
        (self.template / "compositions").mkdir()
        opening_html = "<template>" + "".join(
            f'<video src="assets/opening/{index:02}.mp4" data-duration="3.9"></video>'
            for index in range(1, 4)) + "</template>"
        (self.template / "compositions/opening.html").write_text(opening_html, encoding="utf-8")
        for index in range(1, 6):
            (self.template / f"compositions/main-{index:02}.html").write_text(
                f'<template><video src="assets/main/{index:02}.mp4"></video></template>', encoding="utf-8")
        for relative in ("assets/fonts/nested/font.ttf", "assets/vendor/gsap.min.js", AUDIO_PATH):
            target = self.template / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(("fixture " + relative).encode())
        self.audio = self.template / AUDIO_PATH
        self.metadata = {"id": preparer.TEMPLATE_ID, "duration": 17.6,
                         "boundBgm": {"path": AUDIO_PATH, "sha256": preparer.sha256(self.audio), "duration": 17.577007}}
        self.save_metadata()
        self.probes = {}
        for index in range(5):
            source = self.root / f"clip-{index}.mp4"
            source.write_bytes(f"distinct source {index}".encode())
            self.probes[str(source)] = {**SDR, "width": 1920, "height": 1080, "duration": 10}
        self.job = {"opening": [{"path": f"clip-{index}.mp4", "source": "user"} for index in range(3)],
                    "main": [{"path": f"clip-{index}.mp4", "source": "user"} for index in (0, 1, 2, 0, 1)]}
        self.audio_duration = 17.577007
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
        self.assertNotIn("-c:a", command)
        self.assertNotIn("-stream_loop", command)
        self.assertNotIn("-loop", command)
        filters = command[command.index("-vf") + 1]
        self.assertNotIn("tpad", filters)
        self.assertNotIn("color=", filters)
        frames = int(command[command.index("-frames:v") + 1])
        target = Path(command[-1])
        height = 640 if target.parent.name == "opening" else 1920
        self.assertIn(f"scale=1080:{height}", filters)
        self.assertIn(f"crop=1080:{height}", filters)
        self.derived[str(target)] = {**SDR, "width": 1080, "height": height, "duration": frames / 30}
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
            stack.enter_context(redirect_stdout(io.StringIO()))
            preparer.prepare(args)
        return output

    def assert_rejected(self, message, output_name="output"):
        with self.assertRaisesRegex(ValueError, message):
            self.run_prepare(output_name)
        self.assertFalse((self.root / output_name).exists())
        self.assertEqual(self.commands, [])

    def test_default_text_modular_copy_and_exact_bound_audio(self):
        output = self.run_prepare()
        variables = json.loads((output / "variables.json").read_text(encoding="utf-8"))
        self.assertEqual(variables, DEFAULTS)
        self.assertEqual((output / AUDIO_PATH).read_bytes(), self.audio.read_bytes())
        for relative in ("compositions/opening.html", "compositions/main-05.html", "assets/fonts/nested/font.ttf"):
            self.assertEqual((output / relative).read_bytes(), (self.template / relative).read_bytes())
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual((provenance["duration"], provenance["frames"], provenance["fps"]), (17.6, 528, 30))
        self.assertEqual([item["frames"] for item in provenance["videos"]], [117, 117, 117, 82, 82, 82, 82, 83])
        self.assertEqual(provenance["bgm"]["source"], "template-bound")
        self.assertEqual(provenance["bgm"]["sha256"], provenance["bgm"]["derived_sha256"])
        self.assertEqual(len(self.commands), 8)
        self.assertTrue(all(command[0] == "custom-ffmpeg" for command in self.commands))

    def test_replacements_update_json_and_escaped_static_text(self):
        replacements = {"title": "<好&>", "subtitle": "精工品质", "ctaLine1": "欢迎了解", "ctaLine2": "与您同行"}
        self.job.update(replacements)
        output = self.run_prepare()
        authored = (output / "index.html").read_text(encoding="utf-8")
        _, schema = preparer.variable_schema(authored)
        self.assertEqual({item["id"]: item["default"] for item in schema}, replacements)
        self.assertEqual(json.loads((output / "variables.json").read_text(encoding="utf-8")), replacements)
        for key, value in replacements.items():
            self.assertIn(f'data-var-text="{key}">{html.escape(value)}</div>', authored)

    def test_text_limits_and_empty_overrides(self):
        for index, (key, limit) in enumerate(preparer.TEXT_LIMITS.items()):
            self.job[key] = "字" * (limit + 1)
            self.assert_rejected(key, f"long-{index}")
            del self.job[key]
        self.job["title"] = ""
        self.assert_rejected("title", "blank")
        self.job["title"] = "首行\n次行"
        self.assert_rejected("title", "newline")

    def test_exact_input_counts(self):
        for group in ("opening", "main"):
            saved = self.job[group]
            self.job[group] = saved[:-1]
            self.assert_rejected(f"{group} must contain exactly", group)
            self.job[group] = saved

    def test_duplicate_opening_content_rejected_even_with_other_path(self):
        duplicate = self.root / "duplicate.mp4"
        shutil.copy2(self.root / "clip-0.mp4", duplicate)
        self.probes[str(duplicate)] = self.probes[str(self.root / "clip-0.mp4")]
        self.job["opening"][2]["path"] = duplicate.name
        self.assert_rejected("Opening requires three distinct")

    def test_main_requires_three_distinct_sources(self):
        self.job["main"] = [self.job["main"][index % 2] for index in range(5)]
        self.assert_rejected("Main requires at least three distinct")

    def test_short_opening_or_last_main_rejected_without_padding(self):
        self.probes[str(self.root / "clip-0.mp4")]["duration"] = 3.8
        self.assert_rejected("at least", "short-opening")
        self.probes[str(self.root / "clip-0.mp4")]["duration"] = 10
        self.job["main"][-1] = {"path": "clip-4.mp4", "source": "user"}
        self.probes[str(self.root / "clip-4.mp4")]["duration"] = 82 / 30
        self.assert_rejected("at least", "short-main")

    def test_source_start_is_applied_and_recorded(self):
        self.job["opening"][0]["source_start"] = 2.1
        self.job["main"][-1]["source_start"] = 5.2
        output = self.run_prepare()
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        first, last = provenance["videos"][0], provenance["videos"][-1]
        self.assertEqual(first["source_start"], 2.1)
        self.assertEqual(first["source_window"], {"in": 2.1, "out": 6.0})
        self.assertEqual(last["source_start"], 5.2)
        self.assertAlmostEqual(last["source_window"]["out"], 5.2 + 83 / 30)
        commands = {Path(command[-1]).relative_to(output).as_posix(): command for command in self.commands}
        opening_command = commands["assets/opening/01.mp4"]
        main_command = commands["assets/main/05.mp4"]
        self.assertEqual(opening_command[opening_command.index("-ss") + 1], "2.1")
        self.assertEqual(main_command[main_command.index("-ss") + 1], "5.2")

    def test_invalid_source_start_and_insufficient_remaining_video_rejected(self):
        for index, start in enumerate((-1, float("inf"), float("nan"), None, "1", True)):
            self.job["opening"][0]["source_start"] = start
            self.assert_rejected("source_start must be a finite nonnegative", f"invalid-start-{index}")
        self.job["opening"][0]["source_start"] = 6.2
        self.assert_rejected("at least", "short-after-start")

    def test_approved_records_and_hdr_conversion(self):
        self.job["opening"][0] = {"path": "clip-0.mp4", "status": "可使用", "record_id": "approved-0"}
        self.probes[str(self.root / "clip-0.mp4")].update(HLG)
        output = self.run_prepare()
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        first = provenance["videos"][0]
        self.assertEqual(first["source"], "library")
        self.assertEqual(first["record_id"], "approved-0")
        conversion = first["color_conversion"]
        expected_filter = ("libplacebo=colorspace=bt709:color_primaries=bt709:color_trc=bt709:"
                           "range=tv:format=yuv420p:tonemapping=bt.2390:peak_detect=0")
        self.assertEqual(conversion["branch"], "HLG-to-SDR")
        self.assertEqual(conversion["engine"], "libplacebo")
        self.assertEqual(conversion["algorithm"], "bt.2390")
        self.assertFalse(conversion["peak_detect"])
        self.assertEqual(conversion["peak_mode"], "metadata/defaults; dynamic peak detection disabled")
        self.assertEqual(conversion["peak_source"], "input HDR metadata or libplacebo defaults")
        self.assertNotIn("reference_white_nits", conversion)
        self.assertNotIn("peak_nits", conversion)
        self.assertEqual(conversion["filter"], expected_filter)
        hlg_commands = [command for command in self.commands if command[command.index("-i") + 1] == first["path"]]
        self.assertEqual(len(hlg_commands), 3)
        for command in hlg_commands:
            filters = command[command.index("-vf") + 1]
            self.assertTrue(filters.startswith(expected_filter + ",scale="))
            self.assertNotIn("tonemap=mobius", filters)
            self.assertNotIn("npl=100", filters)
        self.assertEqual(self.filter_commands, [["custom-ffmpeg", "-hide_banner", "-nostdin", "-filters"]])

    def test_sdr_does_not_tone_map_or_require_libplacebo(self):
        self.available_filters = "Filters:\n .. scale            V->V       Scale video.\n"
        output = self.run_prepare()
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(self.filter_commands, [])
        for video in provenance["videos"]:
            self.assertEqual(video["color_conversion"]["branch"], "SDR-to-Rec709")
            self.assertEqual(video["color_conversion"], preparer.validated_color_conversion(video["probe"]))
        for command in self.commands:
            filters = command[command.index("-vf") + 1]
            self.assertNotIn("libplacebo", filters)
            self.assertNotIn("tonemap", filters)

    def test_hlg_with_missing_libplacebo_fails_before_output(self):
        self.probes[str(self.root / "clip-0.mp4")].update(HLG)
        self.available_filters = "Filters:\n .. scale            V->V       Scale video.\n"
        self.assert_rejected("HLG-to-SDR requires the FFmpeg libplacebo filter")
        self.assertEqual(len(self.filter_commands), 1)

    def test_hlg_reuses_metadata_and_camera_log_validation(self):
        source = self.probes[str(self.root / "clip-0.mp4")]
        cases = (({"color_primaries": "bt709"}, "requires verified BT.2020"),
                 ({"color_space": "bt709"}, "requires verified BT.2020"),
                 ({"color_range": None}, "Unverified color range"),
                 ({"camera_log_flag": True}, "Camera LOG source is unsupported"))
        for index, (overrides, message) in enumerate(cases):
            source.update({**HLG, "camera_log_flag": False, **overrides})
            self.assert_rejected(message, f"invalid-hlg-{index}")
        self.assertEqual(self.filter_commands, [])

    def test_pq_conversion_is_unchanged(self):
        info = {**HLG, "color_transfer": "smpte2084", "hdr_peak_nits": 2000}
        self.assertEqual(preparer.color_conversion(info), preparer.validated_color_conversion(info))
        self.assertEqual(preparer.color_conversion(info)["branch"], "PQ-to-SDR")

    def test_unapproved_and_unverified_sources_rejected(self):
        self.job["opening"][0]["source"] = "ai"
        self.assert_rejected("AI assets are not allowed", "ai")
        self.job["opening"][0]["source"] = "user"
        self.probes[str(self.root / "clip-0.mp4")]["color_primaries"] = None
        self.assert_rejected("Unverified/unsupported color metadata", "color")

    def test_bound_bgm_missing_hash_mismatch_or_override_rejected(self):
        self.job["bgm"] = None
        self.assert_rejected("template-bound", "override")
        del self.job["bgm"]
        original = self.audio.read_bytes()
        self.audio.write_bytes(b"other track")
        self.assert_rejected("Bound BGM hash mismatch", "hash")
        self.audio.write_bytes(original)
        self.audio.unlink()
        self.assert_rejected("Bound BGM file is missing", "missing")

    def test_bound_bgm_duration_tolerance(self):
        self.audio_duration = 17.499
        self.assert_rejected("no more than 0.1s shorter", "short-audio")
        self.audio_duration = 17.68
        self.assert_rejected("within 0.1s", "duration-mismatch")
        self.audio_duration = 17.5
        self.assertTrue(self.run_prepare("minimum-audio").is_dir())

    def test_bound_bgm_path_cannot_escape_template(self):
        self.metadata["boundBgm"]["path"] = "../elsewhere.m4a"
        self.save_metadata()
        self.assert_rejected("Bound BGM path must stay inside")

    def test_missing_static_text_or_fixed_media_path_rejected(self):
        index = self.template / "index.html"
        index.write_text(self.source.replace('data-var-text="title"', 'data-old-text="title"'), encoding="utf-8")
        self.assert_rejected("Expected one static title", "text")
        index.write_text(self.source, encoding="utf-8")
        child = self.template / "compositions/main-05.html"
        child.write_text('<template><video src="wrong.mp4"></video></template>', encoding="utf-8")
        self.assert_rejected("missing its fixed video src", "media")
        child.write_text('<template><video data-var-src="assets/main/05.mp4"></video></template>', encoding="utf-8")
        self.assert_rejected("missing its fixed video src", "missing-fallback")

    def test_existing_output_is_preserved(self):
        output = self.root / "output"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Output directory already exists"):
            self.run_prepare()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual(self.commands, [])


class InstalledTemplateTests(unittest.TestCase):
    def test_actual_bound_asset_and_modular_contract(self):
        template = preparer.DEFAULT_TEMPLATE
        if not (template / "template.json").is_file():
            self.skipTest("Installed template is not available yet")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            self.skipTest("ffprobe is required for the actual bound audio check")
        metadata = json.loads((template / "template.json").read_text(encoding="utf-8-sig"))
        audio = preparer.bound_audio(template, metadata, {}, template, ffprobe)
        self.assertEqual(audio["probe"]["codec"], "aac")
        self.assertEqual(audio["sha256"], metadata["boundBgm"]["sha256"])
        self.assertGreaterEqual(audio["probe"]["duration"], 17.5)
        preparer.validate_fixed_media(template, preparer.template_files(template), audio["template_path"])
        source = (template / "index.html").read_text(encoding="utf-8-sig")
        values = preparer.text_values({}, source)
        self.assertEqual(set(values), set(preparer.TEXT_LIMITS))
        self.assertTrue(preparer.update_html(source, values))


if __name__ == "__main__":
    unittest.main(verbosity=2)
