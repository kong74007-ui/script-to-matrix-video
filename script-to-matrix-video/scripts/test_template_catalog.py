#!/usr/bin/env python3
"""Small regression check for template catalog rendering defaults."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import render_video as renderer
import validate_template_batch as batch_validator


def assert_raises_runtime(action) -> None:
    try:
        action()
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


def check_real_catalog() -> None:
    if not renderer.TEMPLATE_CATALOG_PATH.is_file():
        print("catalog check pending: assets/templates/catalog.json is not present")
        return
    catalog = json.loads(renderer.TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    ids = [item.get("id") for item in catalog.get("templates", []) if isinstance(item, dict)]
    assert catalog.get("version") == 1
    assert len(ids) == 12 and len(ids) == len(set(ids)) and all(ids)


def check_template_resolution() -> None:
    assert batch_validator.resolve_template is renderer.resolve_template
    assert renderer.manifest_path(r"assets\clip.mp4", "test") == Path("assets") / "clip.mp4"
    bilingual, _ = renderer.wrap_layout_text("ONE STORY\n12种风格\n不只是换颜色", 13, 2)
    assert "ONE STORY" in bilingual
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value)
        catalog_path = temp / "catalog.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "templates": [
                        {
                            "id": "demo-card",
                            "render": {"subtitle_font": "Template Font", "crf": 16},
                            "layout": {
                                "preset": "text-media-text",
                                "background_mode": "blurred-media",
                                "top_text_y": 111,
                                "media": {"x": 20, "y": 500, "width": 1040, "height": 940},
                                "kicker": {"text": "限时", "x": 20, "y": 30, "font_size": 32, "color": "#FFFFFF", "background_color": "#111111", "padding": 8},
                                "surface_boxes": [{"x": 0, "y": 0, "width": 40, "height": 40, "color": "#FF0000", "opacity": 0.5}],
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        original_catalog, original_run = renderer.TEMPLATE_CATALOG_PATH, renderer.run
        renderer.TEMPLATE_CATALOG_PATH = catalog_path
        try:
            quoted_root = temp / "O'Neil"
            source_fonts = quoted_root / "source fonts"
            render_temp = quoted_root / ".matrix-render-safe"
            source_fonts.mkdir(parents=True)
            render_temp.mkdir()
            (source_fonts / "demo.ttf").write_bytes(b"font")
            staged_fonts = renderer.stage_fonts(source_fonts, render_temp)
            assert renderer.ffmpeg_filter_path(staged_fonts, quoted_root) == ".matrix-render-safe/fonts"
            assert_raises_runtime(lambda: renderer.ffmpeg_filter_path(source_fonts, quoted_root))

            source = {"layout": {"template_id": "demo-card", "top_text_y": 222, "media": {"x": 44}}, "render": {"subtitle_font": "Project Font"}}
            project, template_id = renderer.resolve_template(source)
            assert template_id == "demo-card"
            assert "background_mode" not in source["layout"] and "crf" not in source["render"]
            assert project["render"]["subtitle_font"] == "Project Font" and project["render"]["crf"] == 16
            assert project["layout"]["top_text_y"] == 222 and project["layout"]["media"] == {"x": 44, "y": 500, "width": 1040, "height": 940}
            assert_raises_runtime(lambda: renderer.resolve_template({"layout": {"template_id": "missing"}}))
            assert_raises_runtime(
                lambda: batch_validator.collect_media({"scenes": [{"media": [r"assets\missing.mp4"]}]}, temp / "project.json")
            )
            assert_raises_runtime(lambda: batch_validator.bgm_identity({"bgm": {"enabled": True}}, temp / "project.json"))
            assert_raises_runtime(lambda: renderer.resolve_fonts_dir(temp, {"fonts_dir": "missing-fonts"}))

            layout = renderer.resolve_layout(project, 1080, 1920, [])
            assert layout and layout["kicker"]["text"] == "限时" and len(layout["surface_boxes"]) == 1
            commands: list[list[str]] = []
            renderer.run = lambda command, cwd=None: commands.append(command)
            renderer.render_media_segment(
                "ffmpeg", temp / "source.mp4", "video", 0, temp / "output.mp4", 1080, 1920, 60, 120,
                "static", 0, 0, 18, "medium", layout,
            )
            filters = commands[0][commands[0].index("-filter_complex") + 1]
            assert "[bgsrc]fps=60" in filters
        finally:
            renderer.TEMPLATE_CATALOG_PATH, renderer.run = original_catalog, original_run


if __name__ == "__main__":
    check_real_catalog()
    check_template_resolution()
    print("template catalog checks passed")
