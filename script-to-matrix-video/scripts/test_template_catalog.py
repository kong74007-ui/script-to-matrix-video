#!/usr/bin/env python3
"""Small regression check for template catalog rendering defaults."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
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
    assert renderer.TEMPLATE_CATALOG_PATH.is_file(), "required template catalog is missing"
    catalog = json.loads(renderer.TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    ids = [item.get("id") for item in catalog.get("templates", []) if isinstance(item, dict)]
    assert catalog.get("version") == 1
    assert len(ids) == 12 and len(ids) == len(set(ids)) and all(ids)
    for template_id in ids:
        project, resolved_id = renderer.resolve_template({"layout": {"template_id": template_id}})
        assert resolved_id == template_id
        layout = renderer.resolve_layout(project, 1080, 1920, [])
        assert layout
        renderer.validated_font(project["render"]["subtitle_font"], f"{template_id}.subtitle_font")
        assert renderer.resolve_font_files(
            renderer.DEFAULT_FONTS_DIR, renderer.required_font_families(project["render"], layout)
        )


def check_template_resolution() -> None:
    assert batch_validator.resolve_template is renderer.resolve_template
    assert renderer.manifest_path(r"assets\clip.mp4", "test") == Path("assets") / "clip.mp4"
    if renderer.os.name != "nt":
        assert_raises_runtime(lambda: renderer.manifest_path(r"C:\video\clip.mp4", "test"))
    unchanged = {"layout": {"preset": "text-media-text"}}
    assert renderer.resolve_template(unchanged) == (unchanged, None)
    warnings: list[str] = []
    assert renderer.resolve_layout({"layout": "invalid"}, 1080, 1920, warnings) is None
    assert warnings
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
            staged_fonts = renderer.stage_fonts(renderer.resolve_font_files(source_fonts, {"Demo Font"}), render_temp)
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


def check_invalid_catalogs() -> None:
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value)
        original_catalog = renderer.TEMPLATE_CATALOG_PATH
        renderer.TEMPLATE_CATALOG_PATH = temp / "catalog.json"
        try:
            for payload in (
                {"version": 2, "templates": []},
                {"version": 1, "templates": [{"id": "same"}, {"id": "same"}]},
                {"version": 1, "templates": [{"id": "bad", "layout": {}, "render": "nope"}]},
            ):
                renderer.TEMPLATE_CATALOG_PATH.write_text(json.dumps(payload), encoding="utf-8")
                assert_raises_runtime(lambda: renderer.resolve_template({"layout": {"template_id": "bad"}}))
            assert_raises_runtime(lambda: renderer.resolve_template({"layout": {"template_id": "../bad"}}))
        finally:
            renderer.TEMPLATE_CATALOG_PATH = original_catalog


def check_layout_and_ass() -> None:
    assert_raises_runtime(lambda: renderer.validated_color("red", "color"))
    assert_raises_runtime(lambda: renderer.validated_font("Bad,Font\n[Events]", "font"))
    assert_raises_runtime(lambda: renderer.resolve_kicker({"text": "x", "x": -1}, 1080, 1920))
    assert_raises_runtime(
        lambda: renderer.resolve_surface_boxes(
            [{"x": 1070, "y": 0, "width": 20, "height": 20, "color": "#000000"}], 1080, 1920
        )
    )
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value).resolve()
        project = {
            "render": {"subtitle_font": "Noto Sans SC"},
            "layout": {
                "preset": "text-media-text",
                "variant": "classic",
                "top_font": "Ma Shan Zheng",
                "bottom_font": "ZCOOL XiaoWei",
                "kicker": {
                    "text": "风物小记",
                    "x": 80,
                    "y": 120,
                    "font_size": 30,
                    "color": "#FFFFFF",
                    "background_color": "#B7352C",
                    "padding": 12,
                },
            },
        }
        layout = renderer.resolve_layout(project, 1080, 1920, [])
        assert layout
        ass_path = temp / "captions.ass"
        renderer.write_ass(
            project,
            ass_path,
            1080,
            1920,
            [{"scene": {"top_text": "国风标题", "bottom_text": "评论关键词"}, "start": 0.0, "duration": 8.0}],
            layout,
        )
        ass = ass_path.read_text(encoding="utf-8-sig")
        assert "Style: TopText,Ma Shan Zheng" in ass
        assert "Style: BottomText,ZCOOL XiaoWei" in ass
        assert "Style: Kicker" in ass and "风物小记" in ass


def check_paths_and_fonts() -> None:
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value).resolve()
        inside = renderer.resolve_output(temp, "output/final.mp4")
        assert inside == temp / "output/final.mp4"
        assert_raises_runtime(lambda: renderer.resolve_output(temp, "../outside.mp4"))
        fonts = temp / "fonts"
        fonts.mkdir()
        (fonts / "custom.ttf").write_bytes(b"font")
        assert renderer.resolve_fonts_dir(temp, {"fonts_dir": "fonts"}) == fonts
        assert_raises_runtime(lambda: renderer.resolve_fonts_dir(temp, {"fonts_dir": "../fonts"}))
        empty = temp / "empty"
        empty.mkdir()
        target = temp / "render"
        target.mkdir()
        assert_raises_runtime(lambda: renderer.resolve_font_files(empty, {"Empty Font"}))

        original_link = renderer.os.link
        renderer.os.link = lambda source, destination: (_ for _ in ()).throw(OSError("cross-device"))
        try:
            fallback = temp / "fallback"
            fallback.mkdir()
            copied = renderer.stage_fonts(renderer.resolve_font_files(fonts, {"Custom Font"}), fallback)
            assert (copied / "custom.ttf").read_bytes() == b"font"
        finally:
            renderer.os.link = original_link

        bundle = temp / "bundle"
        bundle.mkdir()
        for name in ("noto.ttf", "style.ttf", "unused.ttf"):
            (bundle / name).write_bytes(name.encode())
        (bundle / "sources.json").write_text(
            json.dumps(
                {
                    "fonts": [
                        {"family": "Noto Sans SC", "file": "noto.ttf", "sha256": hashlib.sha256(b"noto.ttf").hexdigest()},
                        {"family": "Style Font", "file": "style.ttf", "sha256": hashlib.sha256(b"style.ttf").hexdigest()},
                        {"family": "Unused Font", "file": "unused.ttf", "sha256": hashlib.sha256(b"unused.ttf").hexdigest()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        selected_root = temp / "selected"
        selected_root.mkdir()
        selected_files = renderer.resolve_font_files(bundle, {"Style Font"})
        selected = renderer.stage_fonts(selected_files, selected_root)
        assert {path.name for path in selected.iterdir()} == {"noto.ttf", "style.ttf"}
        assert_raises_runtime(lambda: renderer.resolve_font_files(bundle, {"Missing Family"}))
        (bundle / "style.ttf").write_bytes(b"corrupt")
        assert_raises_runtime(lambda: renderer.resolve_font_files(bundle, {"Style Font"}))
        (bundle / "style.ttf").write_bytes(b"style.ttf")
        (bundle / "noto.ttf").unlink()
        assert_raises_runtime(lambda: renderer.resolve_font_files(bundle, {"Style Font"}))

        first = temp / "first.mp4"
        second = temp / "second.mp4"
        first.write_bytes(b"same-media")
        second.write_bytes(b"same-media")
        media = batch_validator.collect_media(
            {"scenes": [{"media": [{"path": "first.mp4"}, {"path": "second.mp4"}]}]}, temp / "project.json"
        )
        assert media[0]["identity"] == media[1]["identity"]


def check_cli_dry_run_and_batch() -> None:
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value)
        media = temp / "media"
        media.mkdir()
        first = media / "first.mp4"
        second = media / "second.mp4"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        project_path = temp / "project.json"
        project = {
            "version": 1,
            "canvas": {"width": 1080, "height": 1920, "fps": 30},
            "layout": {"template_id": "business-black"},
            "voice": {"enabled": False},
            "bgm": False,
            "material_policy": {"allow_image_only": False, "image_only_reason": ""},
            "scenes": [
                {
                    "id": "s01",
                    "top_text": "同一套素材 12种风格",
                    "bottom_text": "选择模板",
                    "duration": 8.0,
                    "media": [
                        {"path": "media/first.mp4", "type": "video", "record_id": "first"},
                        {"path": "media/second.mp4", "type": "video", "record_id": "second"},
                    ],
                }
            ],
            "render": {"output": "output/final.mp4", "preset": "medium", "crf": 18},
        }
        project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
        dry_run = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_video.py"), str(project_path), "--dry-run"],
            check=True,
            capture_output=True,
            text=True,
        )
        dry = json.loads(dry_run.stdout)
        assert dry["template_id"] == "business-black" and dry["layout"] == "text-media-text"
        assert dry["scenes"][0]["video_assets"] == 2

        batch_path = temp / "batch.json"
        report_path = temp / "report.json"
        batch_path.write_text(json.dumps({"jobs": [{"project": "project.json"}]}), encoding="utf-8")
        valid = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path), "--report", str(report_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        validated = json.loads(valid.stdout)
        assert validated["ok"] and validated["jobs"][0]["template_id"] == "business-black"
        assert validated["jobs"][0]["video_media"] == 2

        duplicate_batch = {
            "jobs": [
                {"project": "project.json", "copy_id": "same", "variant_id": "A"},
                {"project": "project.json", "copy_id": "same", "variant_id": "B"},
            ]
        }
        batch_path.write_text(json.dumps(duplicate_batch), encoding="utf-8")
        duplicate = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            capture_output=True,
            text=True,
        )
        assert duplicate.returncode == 1 and "duplicates the full media set" in duplicate.stdout

        project["scenes"][0]["top_text"] = "ONE STORY 12种风格 不只是换颜色"
        project["scenes"][0]["bottom_text"] = "PICK A STYLE 再批量生成"
        project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
        batch_path.write_text(json.dumps({"jobs": [{"project": "project.json"}]}), encoding="utf-8")
        fixed = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path), "--fix-duration"],
            check=True,
            capture_output=True,
            text=True,
        )
        fixed_report = json.loads(fixed.stdout)
        fixed_project = json.loads(project_path.read_text(encoding="utf-8"))
        assert fixed_report["jobs"][0]["duration_fixed"]
        assert fixed_project["scenes"][0]["duration"] > 8.0


def check_concurrency_and_boundaries() -> None:
    assert_raises_runtime(
        lambda: renderer.resolve_layout(
            {"layout": {"preset": "text-media-text", "top_font_size": 100000}}, 1080, 1920, []
        )
    )
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value).resolve()
        project_path = temp / "project.json"
        project_path.write_text(json.dumps({"value": 1}), encoding="utf-8")
        payload, digest = renderer.load_json_snapshot(project_path)
        project_path.write_text(json.dumps({"value": 2}), encoding="utf-8")
        assert_raises_runtime(lambda: renderer.save_json_if_unchanged(project_path, payload, digest))
        assert not (temp / ".project.json.lock").exists()

        payload, digest = renderer.load_json_snapshot(project_path)
        lock_path = temp / ".project.json.lock"
        lock_path.write_text("locked", encoding="utf-8")
        assert_raises_runtime(lambda: renderer.save_json_if_unchanged(project_path, payload, digest))
        lock_path.unlink()

        assert_raises_runtime(
            lambda: batch_validator.normalize_jobs(
                {"jobs": [{"project": "../outside/project.json"}]}, temp / "batch.json"
            )
        )
        assert_raises_runtime(
            lambda: batch_validator.normalize_jobs(
                {"jobs": [{"project": str(Path("/tmp/outside-project.json"))}]}, temp / "batch.json"
            )
        )

        invalid_project = {
            "layout": {"template_id": "business-black"},
            "render": {"output": "output/final.mp4"},
            "scenes": ["not-an-object"],
        }
        project_path.write_text(json.dumps(invalid_project), encoding="utf-8")
        batch_path = temp / "batch.json"
        batch_path.write_text(json.dumps({"jobs": [{"project": "project.json"}]}), encoding="utf-8")
        invalid_scene = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            capture_output=True,
            text=True,
        )
        assert invalid_scene.returncode == 1
        assert "array of scene objects" in invalid_scene.stdout

        layout = renderer.resolve_layout(
            {"layout": {"preset": "text-media-text"}}, 1080, 1920, []
        )
        assert layout
        assert_raises_runtime(
            lambda: renderer.write_ass(
                {"render": {"subtitle_font": "Noto Sans SC", "subtitle_font_size": 100000}},
                temp / "invalid.ass",
                1080,
                1920,
                [
                    {
                        "scene": {"top_text": "标题", "overlays": [{"text": "越界", "x": 2000}]},
                        "start": 0.0,
                        "duration": 8.0,
                    }
                ],
                layout,
            )
        )


if __name__ == "__main__":
    check_real_catalog()
    check_template_resolution()
    check_invalid_catalogs()
    check_layout_and_ass()
    check_paths_and_fonts()
    check_cli_dry_run_and_batch()
    check_concurrency_and_boundaries()
    print("template catalog checks passed")
