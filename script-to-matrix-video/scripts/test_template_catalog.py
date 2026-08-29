#!/usr/bin/env python3
"""Small regression check for template catalog rendering defaults."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import render_video as renderer
import render_reference_typography as reference_renderer
import validate_template_batch as batch_validator
from template_policy import emphasis_source_hash, fallback_emphasis, resolve_emphasis


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
    profiles = catalog.get("emphasis_profiles") or {}
    assert catalog.get("version") == 1
    assert ids == [
        "black-left-bold",
        "white-center-bold",
        "white-handwritten",
        "black-playful",
        "white-left-editorial",
        "black-right-modern",
        "white-left-playful",
        "black-center-editorial",
    ]
    assert len(ids) == len(set(ids))
    assert set(profiles) == set(ids)
    for template_id in ids:
        project, resolved_id = renderer.resolve_template({"layout": {"template_id": template_id}})
        assert resolved_id == template_id
        layout = renderer.resolve_layout(project, 1080, 1920, [])
        assert layout and layout["emphasis_profile"]["scale"] > 1
        renderer.validated_font(project["render"]["subtitle_font"], f"{template_id}.subtitle_font")
        assert renderer.resolve_font_files(
            renderer.DEFAULT_FONTS_DIR, renderer.required_font_families(project["render"], layout)
        )


def check_reference_typography_pack() -> None:
    skill_root = SCRIPTS.parent
    pack_root = skill_root / "assets" / "templates" / "reference-typography-17"
    manifest_path = pack_root / "manifest.json"
    wrapper_path = SCRIPTS / "render_reference_typography.py"
    assert manifest_path.is_file(), "reference typography manifest is missing"
    assert wrapper_path.is_file(), "reference typography renderer is missing"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    templates = manifest.get("templates") or []
    ids = [item.get("id") for item in templates]
    variants = [item.get("variant") for item in templates]
    assert manifest.get("version") == 2 and manifest.get("engine") == "hyperframes"
    assert manifest.get("hyperframes_version") == "0.8.17"
    assert manifest.get("duration_mode") == "random_integer_per_output"
    assert manifest.get("duration_range_seconds") == [8, 15]
    assert manifest.get("generated_fields") == ["duration"]
    assert len(templates) == 18 and len(ids) == len(set(ids))
    assert all(isinstance(value, str) and value.startswith("ref-") for value in ids)
    assert variants == [f"v{index:02d}" for index in range(1, 19)]

    index_html = (pack_root / "index.html").read_text(encoding="utf-8")
    for variable in (
        "top1",
        "top2",
        "top3",
        "bottom1",
        "bottom2",
        "duration",
        "videoA",
        "videoB",
        "videoC",
        "bgm",
    ):
        assert variable in index_html
    assert "Math.random" not in index_html
    assert "duration / 3" in index_html
    root_tag = re.search(r'<div[^>]+id="root"[^>]*>', index_html)
    assert root_tag and "data-duration" not in root_tag.group(0)
    assert (pack_root / "assets" / "library" / "default-c.mp4").is_file()
    for variant in variants:
        assert f".{variant} " in index_html

    sample_row = {
        "name": "duration-contract",
        "template_id": ids[0],
        "top1": "标题",
        "bottom2": "行动",
        "videoA": "a.mp4",
        "videoB": "b.mp4",
        "videoC": "c.mp4",
    }
    durations = {
        reference_renderer.random_duration(f"{seed:064x}", sample_row, seed)
        for seed in range(64)
    }
    assert durations.issubset(set(range(8, 16))) and durations == set(range(8, 16))

    for item in templates:
        for field, suffix in (("example_mp4", ".mp4"), ("example_jpg", ".jpg")):
            example = (pack_root / item[field]).resolve()
            assert example.suffix.lower() == suffix and example.is_file()
            assert example.stat().st_size > 10_000


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
    bilingual, _ = renderer.wrap_layout_text("ONE STORY\n4种风格\n不只是换颜色", 13, 2)
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
        text_fade_ins = [int(value) for value in re.findall(r"\\fad\((\d+),\d+\)", ass)]
        assert text_fade_ins and all(value == 0 for value in text_fade_ins)

        top = "大健康行业的私域复购率是40%，美妆只有15%。选赛道这件事，数据不会骗人。"
        bottom = "评论区扣勾兑"
        native_project, _ = renderer.resolve_template(
            {
                "layout": {"template_id": "black-left-bold"},
                "cover": {"title": top},
                "render": {"subtitle_font": "Noto Sans SC"},
            }
        )
        native_layout = renderer.resolve_layout(native_project, 1080, 1920, [])
        assert native_layout and native_layout["top_text_layout"] == "block"
        native_ass_path = temp / "native.ass"
        renderer.write_ass(
            native_project,
            native_ass_path,
            1080,
            1920,
            [{"scene": {"top_text": top, "bottom_text": bottom}, "start": 0.0, "duration": 8.0}],
            native_layout,
        )
        native_ass = native_ass_path.read_text(encoding="utf-8-sig")
        assert "\\an7\\pos(76,80)" in native_ass
        native_plain = re.sub(r"\{[^}]*\}", "", native_ass).replace(r"\N", "")
        assert "40%" in native_plain and "15%" in native_plain and "数据不会骗人" in native_plain
        assert "美妆只有15%。选赛道这件事，数据不会骗人。" in native_plain
        assert "\\an7\\pos(76,1730)" in native_ass and "评论区扣勾兑" in native_ass
        assert "\\fscx94" not in native_ass and "\\fscx96" not in native_ass

        right_project, _ = renderer.resolve_template(
            {"layout": {"template_id": "black-right-modern"}, "render": {"subtitle_font": "Noto Sans SC"}}
        )
        right_layout = renderer.resolve_layout(right_project, 1080, 1920, [])
        assert right_layout and right_layout["text_alignment"] == "right"
        right_ass_path = temp / "right.ass"
        renderer.write_ass(
            right_project,
            right_ass_path,
            1080,
            1920,
            [{"scene": {"top_text": "右对齐标题", "bottom_text": "右对齐行动"}, "start": 0.0, "duration": 8.0}],
            right_layout,
        )
        right_ass = right_ass_path.read_text(encoding="utf-8-sig")
        assert "\\an9\\pos(1004,80)" in right_ass
        assert "\\an9\\pos(1004,1730)" in right_ass


def check_emphasis_protocol() -> None:
    top = "不是所有字都该一样大"
    bottom = "先让观众看到重点"
    project = {
        "emphasis": {
            "schema_version": "emphasis.v1",
            "provider": "codex",
            "source_hash": emphasis_source_hash(top, bottom),
            "prompt_version": "v1",
            "top": [
                {"start": 7, "end": 10, "text": "一样大", "role": "contrast", "priority": 1, "confidence": 0.95},
                {"start": 2, "end": 5, "text": "所有字", "role": "pain", "priority": 2, "confidence": 0.86},
                {"start": 4, "end": 7, "text": "字都该", "role": "pain", "priority": 3, "confidence": 0.8},
                {"start": 0, "end": 2, "text": "不是", "role": "contrast", "priority": 4, "confidence": 0.4},
            ],
            "bottom": [
                {"start": 4, "end": 8, "text": "看到重点", "role": "conclusion", "priority": 1, "confidence": 0.94}
            ],
        }
    }
    scenes = [{"top_text": top, "bottom_text": bottom}]
    emphasis, warnings = resolve_emphasis(project, scenes)
    assert emphasis["input_valid"] and len(emphasis["top"]) == 2 and len(emphasis["bottom"]) == 1
    assert any("overlapping" in warning for warning in warnings)
    assert any("confidence" in warning for warning in warnings)

    stale = json.loads(json.dumps(project, ensure_ascii=False))
    stale["emphasis"]["source_hash"] = "0" * 64
    fallback, stale_warnings = resolve_emphasis(stale, scenes)
    assert not fallback["input_valid"] and not fallback["top"] and stale_warnings

    assert any(item["role"] == "number" for item in fallback_emphasis("2026年增长40%", "top"))
    assert any(item["role"] == "cta" for item in fallback_emphasis("立即保存这条内容", "bottom"))

    wrapped, _ = renderer.wrap_layout_text(top, 6, 2, ["一样大"])
    assert wrapped.replace("\n", "") == top and "一样大" in wrapped
    long_text = "这是不会被截断的完整长标题用于验证排版"
    wrapped_long, _ = renderer.wrap_layout_text(long_text, 5, 2)
    assert wrapped_long.replace("\n", "") == long_text

    styled_project, _ = renderer.resolve_template(
        {"layout": {"template_id": "black-playful"}, "render": {"subtitle_font": "Noto Sans SC"}, **project}
    )
    layout = renderer.resolve_layout(styled_project, 1080, 1920, [])
    assert layout
    resolved, _ = resolve_emphasis(styled_project, scenes)
    with tempfile.TemporaryDirectory() as temp_value:
        ass_path = Path(temp_value) / "emphasis.ass"
        renderer.write_ass(
            styled_project,
            ass_path,
            1080,
            1920,
            [{"scene": scenes[0], "start": 0.0, "duration": 8.0}],
            layout,
            resolved,
        )
        ass = ass_path.read_text(encoding="utf-8-sig")
        assert "\\fscx" in ass and "\\u1" not in ass
        assert "一样大" in ass and "看到重点" in ass

    assert_raises_runtime(
        lambda: renderer.resolve_emphasis_profile(
            {"role_colors": {"unknown": "#FFFFFF"}}, "#FFD400", "#FF453A"
        )
    )

    legacy_project, _ = renderer.resolve_template({"layout": {"template_id": "white-handwritten"}})
    legacy_layout = renderer.resolve_layout(legacy_project, 1080, 1920, [])
    assert legacy_layout and not legacy_layout["auto_highlight"]
    legacy = renderer.normalize_highlights(
        {"top_highlights": [{"text": "重点", "color": "#FF0000", "scale": 1.5}]},
        "top_highlights",
        "旧清单重点",
        legacy_layout,
    )
    assert legacy[0]["scale"] == 1 and not legacy[0]["underline"] and legacy[0]["color"] == "#FF0000"
    old_auto_project, _ = renderer.resolve_template({"layout": {"template_id": "black-left-bold"}})
    old_auto_layout = renderer.resolve_layout(old_auto_project, 1080, 1920, [])
    assert old_auto_layout
    old_auto = renderer.normalize_highlights(
        {}, "top_highlights", "增长40%", old_auto_layout, resolve_emphasis({}, [{"top_text": "增长40%"}])[0]
    )
    assert old_auto == []

    repeated_top, repeated_bottom = "哈哈哈", "立即保存"
    repeated_project = {
        "emphasis": {
            "schema_version": "emphasis.v1",
            "provider": "codex",
            "source_hash": emphasis_source_hash(repeated_top, repeated_bottom),
            "prompt_version": "v1",
            "top": [
                {"start": 1, "end": 3, "text": "哈哈", "role": "conclusion", "priority": 1, "confidence": 0.9}
            ],
            "bottom": [],
        }
    }
    repeated, _ = resolve_emphasis(
        repeated_project, [{"top_text": repeated_top, "bottom_text": repeated_bottom}]
    )
    repeated_highlights = renderer.normalize_highlights(
        {}, "top_highlights", repeated_top, legacy_layout, repeated
    )
    repeated_wrapped, _, repeated_highlights = renderer.wrap_highlighted_text(
        repeated_top, 1, 2, repeated_highlights
    )
    repeated_intervals = renderer.highlight_intervals(repeated_wrapped, repeated_highlights)
    assert repeated_wrapped == "哈\n哈哈"
    assert repeated_intervals[0][:2] == (2, 4)

    later_scene = renderer.normalize_highlights(
        {}, "top_highlights", "别人也哈哈哈", legacy_layout, repeated
    )
    assert later_scene == []

    invalid_region_project = json.loads(json.dumps(repeated_project, ensure_ascii=False))
    invalid_region_project["emphasis"]["top"] = "not-an-array"
    invalid_region_project["emphasis"]["source_hash"] = emphasis_source_hash("增长40%", repeated_bottom)
    invalid_region, invalid_warnings = resolve_emphasis(
        invalid_region_project, [{"top_text": "增长40%", "bottom_text": repeated_bottom}]
    )
    invalid_fallback = renderer.normalize_highlights(
        {}, "top_highlights", "增长40%", legacy_layout, invalid_region
    )
    assert (
        invalid_warnings
        and invalid_fallback
        and invalid_fallback[0]["role"] == "number"
        and invalid_fallback[0]["scale"] > 1
    )

    float_offsets = json.loads(json.dumps(repeated_project, ensure_ascii=False))
    float_offsets["emphasis"]["top"][0]["start"] = 1.9
    float_offsets["emphasis"]["top"][0]["end"] = 3.9
    float_result, float_warnings = resolve_emphasis(
        float_offsets, [{"top_text": repeated_top, "bottom_text": repeated_bottom}]
    )
    assert not float_result["top"] and any("numeric" in warning for warning in float_warnings)

    assert_raises_runtime(
        lambda: renderer.fit_emphasis(
            "这是一个明显超过模板容量且不能继续缩小的超长标题文本" * 3,
            [],
            legacy_layout["top_min_font_size"],
            legacy_layout["top_min_font_size"],
            legacy_layout["top_font_size"],
            legacy_layout["top_max_chars"],
        )
    )


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

        malformed = temp / "malformed-fonts"
        malformed.mkdir()
        (malformed / "sources.json").write_text("not json", encoding="utf-8")
        assert_raises_runtime(lambda: renderer.resolve_font_files(malformed, {"Noto Sans SC"}))

        duplicate = temp / "duplicate-fonts"
        duplicate.mkdir()
        (duplicate / "noto.ttf").write_bytes(b"noto")
        noto_sha = hashlib.sha256(b"noto").hexdigest()
        (duplicate / "sources.json").write_text(
            json.dumps(
                {
                    "fonts": [
                        {"family": "Noto Sans SC", "file": "noto.ttf", "sha256": noto_sha},
                        {"family": "Noto Sans SC", "file": "noto.ttf", "sha256": noto_sha},
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert_raises_runtime(lambda: renderer.resolve_font_files(duplicate, {"Noto Sans SC"}))

        unsafe = temp / "unsafe-fonts"
        unsafe.mkdir()
        (unsafe / "sources.json").write_text(
            json.dumps(
                {
                    "fonts": [
                        {"family": "Noto Sans SC", "file": "../noto.ttf", "sha256": "0" * 64}
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert_raises_runtime(lambda: renderer.resolve_font_files(unsafe, {"Noto Sans SC"}))

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
            "layout": {"template_id": "white-center-bold"},
            "voice": {"enabled": False},
            "bgm": False,
            "material_policy": {"allow_image_only": False, "image_only_reason": ""},
            "scenes": [
                {
                    "id": "s01",
                    "top_text": "同一套素材 4种风格",
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
        assert dry["template_id"] == "white-center-bold" and dry["layout"] == "text-media-text"
        assert dry["scenes"][0]["video_assets"] == 2

        for field, value, expected_error in (
            ("canvas", "invalid", "canvas must be an object"),
            ("render", "invalid", "render must be an object"),
        ):
            invalid = dict(project)
            invalid[field] = value
            project_path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "render_video.py"), str(project_path), "--dry-run"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1 and expected_error in result.stderr

        invalid_duration = json.loads(json.dumps(project, ensure_ascii=False))
        invalid_duration["scenes"][0]["duration"] = float("nan")
        project_path.write_text(json.dumps(invalid_duration, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_video.py"), str(project_path), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1 and "finite numbers" in result.stderr
        project_path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")

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
        assert validated["ok"] and validated["jobs"][0]["template_id"] == "white-center-bold"
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

        first_image = media / "first.png"
        second_image = media / "second.png"
        first_image.write_bytes(b"first-image")
        second_image.write_bytes(b"second-image")
        image_project = json.loads(json.dumps(project, ensure_ascii=False))
        image_project["scenes"][0]["media"] = [
            {"path": "media/first.png", "type": "image", "record_id": "image-first"},
            {"path": "media/second.png", "type": "image", "record_id": "image-second"},
        ]
        image_path = temp / "image-project.json"
        image_path.write_text(json.dumps(image_project, ensure_ascii=False), encoding="utf-8")
        batch_path.write_text(json.dumps({"jobs": [{"project": "image-project.json"}]}), encoding="utf-8")
        image_rejected = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            capture_output=True,
            text=True,
        )
        assert image_rejected.returncode == 1 and "image-only output is not allowed" in image_rejected.stdout
        image_project["material_policy"] = {
            "allow_image_only": True,
            "image_only_reason": "Two approved video searches returned no suitable record",
        }
        image_path.write_text(json.dumps(image_project, ensure_ascii=False), encoding="utf-8")
        image_allowed = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "image-only fallback recorded" in image_allowed.stdout

        music = media / "music.mp3"
        music.write_bytes(b"music")
        bgm_project = json.loads(json.dumps(project, ensure_ascii=False))
        bgm_project["bgm"] = {"enabled": True, "path": "media/music.mp3", "record_id": "music"}
        bgm_path = temp / "bgm-project.json"
        bgm_path.write_text(json.dumps(bgm_project, ensure_ascii=False), encoding="utf-8")
        batch_path.write_text(
            json.dumps(
                {
                    "jobs": [
                        {"project": "bgm-project.json"},
                        {"project": "project.json"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        mixed_bgm = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            capture_output=True,
            text=True,
        )
        assert mixed_bgm.returncode == 1 and "BGM is enabled on 1 of 2" in mixed_bgm.stdout
        batch_path.write_text(
            json.dumps({"jobs": [{"project": "bgm-project.json"}] * 4}), encoding="utf-8"
        )
        repeated_bgm = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_template_batch.py"), str(batch_path)],
            capture_output=True,
            text=True,
        )
        assert repeated_bgm.returncode == 1
        assert "require at least 3 distinct BGM tracks" in repeated_bgm.stdout
        assert "reuse the same BGM" in repeated_bgm.stdout

        project["scenes"][0]["top_text"] = "ONE STORY 4种风格 不只是换颜色"
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

        output = temp / "output.mp4"
        output.write_bytes(b"old-output")
        candidate = temp / "candidate.mp4"
        candidate.write_bytes(b"new-output")
        payload, digest = renderer.load_json_snapshot(project_path)
        project_path.write_text(json.dumps({"value": 3}), encoding="utf-8")
        assert_raises_runtime(
            lambda: renderer.publish_render_if_unchanged(project_path, payload, digest, candidate, output)
        )
        assert output.read_bytes() == b"old-output"

        project_path.write_text(json.dumps({"value": 4}), encoding="utf-8")
        payload, digest = renderer.load_json_snapshot(project_path)
        candidate.write_bytes(b"new-output")
        original_save = renderer.save_json
        renderer.save_json = lambda path, value: (_ for _ in ()).throw(RuntimeError("disk full"))
        try:
            assert_raises_runtime(
                lambda: renderer.publish_render_if_unchanged(project_path, payload, digest, candidate, output)
            )
            assert output.read_bytes() == b"old-output"
        finally:
            renderer.save_json = original_save

        candidate.write_bytes(b"new-output")
        payload, digest = renderer.load_json_snapshot(project_path)
        renderer.publish_render_if_unchanged(project_path, payload, digest, candidate, output)
        assert output.read_bytes() == b"new-output"

        no_previous = temp / "first-output.mp4"
        first_candidate = temp / "first-candidate.mp4"
        first_candidate.write_bytes(b"first-publish")
        payload, digest = renderer.load_json_snapshot(project_path)
        renderer.publish_render_if_unchanged(project_path, payload, digest, first_candidate, no_previous)
        assert no_previous.read_bytes() == b"first-publish"

        output.write_bytes(b"stable-output")
        failed_candidate = temp / "failed-candidate.mp4"
        failed_candidate.write_bytes(b"should-not-publish")
        payload, digest = renderer.load_json_snapshot(project_path)
        original_replace = renderer.os.replace

        def fail_candidate_replace(source, destination):
            if Path(source) == failed_candidate:
                raise RuntimeError("candidate replace failed")
            return original_replace(source, destination)

        renderer.os.replace = fail_candidate_replace
        try:
            assert_raises_runtime(
                lambda: renderer.publish_render_if_unchanged(
                    project_path, payload, digest, failed_candidate, output
                )
            )
            assert output.read_bytes() == b"stable-output"
        finally:
            renderer.os.replace = original_replace

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
            "layout": {"template_id": "white-center-bold"},
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


def check_real_render() -> None:
    ffmpeg, _ = renderer.validate_tools()
    with tempfile.TemporaryDirectory() as temp_value:
        temp = Path(temp_value).resolve()
        media = temp / "media"
        media.mkdir()
        for name, color, fps in (("first.mp4", "0x315EFB", 60), ("second.mp4", "0xF3C95B", 30)):
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s=320x180:r={fps}:d=4",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(media / name),
                ],
                check=True,
            )
        project_path = temp / "project.json"
        project_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "canvas": {"width": 1080, "height": 1920, "fps": 30},
                    "layout": {"template_id": "white-handwritten"},
                    "voice": {"enabled": False},
                    "bgm": False,
                    "material_policy": {"allow_image_only": False, "image_only_reason": ""},
                    "scenes": [
                        {
                            "id": "s01",
                            "top_text": "真实渲染回归",
                            "bottom_text": "模板字体与高帧率",
                            "duration": 8.0,
                            "media": [
                                {"path": "media/first.mp4", "type": "video", "record_id": "first"},
                                {"path": "media/second.mp4", "type": "video", "record_id": "second"},
                            ],
                        }
                    ],
                    "render": {"output": "output/final.mp4", "preset": "veryfast", "crf": 23},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_video.py"), str(project_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(result.stdout)
        assert report["video_codec"] == "h264" and report["audio_codec"] == "aac"
        assert (report["width"], report["height"], report["template_id"]) == (1080, 1920, "white-handwritten")
        assert report["duration"] >= 8.0 and (temp / "output/final.mp4").is_file()
        saved = json.loads(project_path.read_text(encoding="utf-8"))
        assert saved["render_report"]["template_id"] == "white-handwritten"


if __name__ == "__main__":
    check_real_catalog()
    check_reference_typography_pack()
    check_template_resolution()
    check_invalid_catalogs()
    check_layout_and_ass()
    check_emphasis_protocol()
    check_paths_and_fonts()
    check_cli_dry_run_and_batch()
    check_concurrency_and_boundaries()
    check_real_render()
    print("template catalog checks passed")
