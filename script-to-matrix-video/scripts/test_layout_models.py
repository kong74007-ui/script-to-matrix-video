#!/usr/bin/env python3
"""Focused regression checks for the reusable conversion layout models."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

import render_video


ROOT = Path(__file__).resolve().parents[1]


def load_model(name: str) -> dict:
    path = ROOT / "assets" / "layout-models" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    expected = {
        "full-overlay-bold": (0, 0, 1080, 1920),
        "poster-split": (0, 600, 1080, 820),
    }
    catalog = json.loads((ROOT / "assets" / "templates" / "catalog.json").read_text(encoding="utf-8"))
    templates = {item["id"]: item for item in catalog["templates"]}
    for name, geometry in expected.items():
        model = load_model(name)
        assert templates[name]["layout"] == model["layout"]
        warnings: list[str] = []
        layout = render_video.resolve_layout(model, 1080, 1920, warnings)
        assert layout is not None
        assert layout["variant"] == name
        assert (
            layout["media_x"],
            layout["media_y"],
            layout["media_width"],
            layout["media_height"],
        ) == geometry
        assert not warnings

        scene = {"id": "s01", "text": "通用模型测试", **model["scene_text_model"]}
        timeline = [{"scene": scene, "start": 0.0, "duration": 8.0}]
        project = {
            "layout": model["layout"],
            "cover": {"title": scene["top_text"]},
            "render": {"subtitle_font": "Noto Sans SC"},
        }
        with tempfile.TemporaryDirectory() as temp:
            ass_path = Path(temp) / f"{name}.ass"
            render_video.write_ass(project, ass_path, 1080, 1920, timeline, layout)
            ass = ass_path.read_text(encoding="utf-8-sig")
        assert "Style: TopText" in ass and "Style: BottomText" in ass
        assert "评论区" in ass
        if name == "poster-split":
            assert layout["top_outer_outline"] > layout["top_text_outline"]
            assert layout["bottom_outer_outline"] > layout["bottom_text_outline"]
            assert "Style: TopTextGlow" in ass
            assert "Style: BottomTextGlow" in ass
            assert ",TopTextGlow," in ass
            assert ",BottomTextGlow," in ass

    print("layout models: 2 passed")


if __name__ == "__main__":
    main()
