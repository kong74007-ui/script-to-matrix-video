from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("matrix_render_video", SCRIPTS / "render_video.py")
render = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(render)


def layout():
    return {
        "preset": "text-media-text",
        "top_font_size": 80,
        "top_min_font_size": 52,
        "top_max_chars": 12,
        "top_max_lines": 4,
        "bottom_font_size": 70,
        "bottom_min_font_size": 46,
        "bottom_max_chars": 12,
        "bottom_max_lines": 3,
    }


class LayoutPreflightTests(unittest.TestCase):
    def test_fit_reports_the_exact_overflow_field(self):
        value = layout()
        with self.assertRaises(render.LayoutTextError) as top:
            render.fit_wrapped_layout_text("长" * 60, 60, [], value, "top")
        self.assertEqual("top_text", top.exception.field)
        self.assertEqual("text_overflow", top.exception.as_dict()["code"])

        with self.assertRaises(render.LayoutTextError) as bottom:
            render.fit_wrapped_layout_text("长" * 60, 60, [], value, "bottom")
        self.assertEqual("bottom_text", bottom.exception.field)

    def test_preflight_uses_the_same_wrapping_and_fitting_helper(self):
        project = {
            "canvas": {"width": 1080, "height": 1920},
            "layout": {"template_id": "native-bold"},
            "scenes": [{"top_text": "有效标题", "bottom_text": "立即咨询"}],
        }
        emphasis = {"top": [], "bottom": []}
        with mock.patch.object(render, "resolve_template", return_value=(project, "native-bold")), \
             mock.patch.object(render, "resolve_layout", return_value=layout()), \
             mock.patch.object(render, "resolve_emphasis", return_value=(emphasis, [])), \
             mock.patch.object(render, "normalize_highlights", return_value=[]), \
             mock.patch.object(render, "fit_wrapped_layout_text", wraps=render.fit_wrapped_layout_text) as fit:
            result = render.preflight_layout_text(project)
        self.assertTrue(result["ok"])
        self.assertEqual("native-bold", result["template_id"])
        self.assertEqual(["top_text", "bottom_text"], [item["field"] for item in result["regions"]])
        self.assertEqual(2, fit.call_count)

    def test_preflight_fails_before_media_or_ffmpeg_are_needed(self):
        protected = {
            "text": "长" * 60,
            "source_start": 0,
            "source_end": 60,
            "scale": 1.0,
            "min_scale": 1.0,
        }
        project = {
            "canvas": {"width": 1080, "height": 1920},
            "layout": {"template_id": "native-bold"},
            "scenes": [{"top_text": "长" * 60, "bottom_text": "立即咨询"}],
        }
        with mock.patch.object(render, "resolve_template", return_value=(project, "native-bold")), \
             mock.patch.object(render, "resolve_layout", return_value=layout()), \
             mock.patch.object(render, "resolve_emphasis", return_value=({"top": [], "bottom": []}, [])), \
             mock.patch.object(render, "normalize_highlights", side_effect=[[protected], []]):
            with self.assertRaises(render.LayoutTextError) as caught:
                render.preflight_layout_text(project)
        self.assertEqual("top_text", caught.exception.field)


if __name__ == "__main__":
    unittest.main()
