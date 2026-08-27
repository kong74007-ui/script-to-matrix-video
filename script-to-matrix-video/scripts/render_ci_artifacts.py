#!/usr/bin/env python3
"""Render zero-cost semantic-emphasis artifacts for CI review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from template_policy import emphasis_source_hash
import render_video as renderer


CASES = (
    ("yellow-blue-pop", "不是所有字都该一样大", "先让观众看到重点", "一样大", "看到重点"),
    ("torn-magazine", "信息越多，越要有主次", "三秒留下一个记忆点", "有主次", "记忆点"),
    ("chinese-title", "表达有轻重，内容才有气韵", "把结论留在第一眼", "有轻重", "第一眼"),
)


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "command failed")[-4000:])
    return result.stdout.strip()


def absolute_filter_path(path: Path) -> str:
    """Escape an absolute path for a quoted FFmpeg filter option."""

    value = path.resolve().as_posix()
    if any(character in value for character in ("'", "\n", "\r")):
        raise RuntimeError(f"FFmpeg filter path contains unsupported characters: {value}")
    return value.replace("\\", "\\\\").replace(":", "\\:")


def span(text: str, term: str, role: str) -> dict[str, object]:
    start = text.index(term)
    return {
        "start": start,
        "end": start + len(term),
        "text": term,
        "role": role,
        "priority": 1,
        "confidence": 0.95,
    }


def render_profile_stills(output: Path, ffmpeg: str, source: Path) -> tuple[list[str], Path]:
    """Exercise every catalog profile through ASS/libass without rendering 15 full MP4s."""

    top, bottom = "15套模板都有重点", "大字高亮 一眼看懂"
    catalog = json.loads(renderer.TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    template_ids = [str(item["id"]) for item in catalog["templates"]]
    still_root = output / "profile-stills"
    still_root.mkdir(exist_ok=True)
    previews: list[Path] = []
    for template_id in template_ids:
        project = {
            "layout": {"template_id": template_id},
            "render": {"subtitle_font": "Noto Sans SC"},
            "emphasis": {
                "schema_version": "emphasis.v1",
                "provider": "codex-fixture",
                "source_hash": emphasis_source_hash(top, bottom),
                "prompt_version": "ci-v1",
                "top": [span(top, "重点", "conclusion")],
                "bottom": [span(bottom, "一眼看懂", "cta")],
            },
        }
        project, _ = renderer.resolve_template(project)
        layout = renderer.resolve_layout(project, 1080, 1920, [])
        if not layout:
            raise RuntimeError(f"template did not resolve to text-media-text: {template_id}")
        emphasis, warnings = renderer.resolve_emphasis(
            project, [{"top_text": top, "bottom_text": bottom}]
        )
        if warnings or not emphasis["input_valid"]:
            raise RuntimeError(f"invalid CI emphasis for {template_id}: {warnings}")
        template_dir = still_root / template_id
        template_dir.mkdir(exist_ok=True)
        base = template_dir / "base.mp4"
        renderer.render_media_segment(
            ffmpeg,
            source,
            "video",
            0,
            base,
            1080,
            1920,
            30,
            30,
            "static",
            0,
            0,
            23,
            "veryfast",
            layout,
        )
        ass_path = template_dir / "preview.ass"
        renderer.write_ass(
            project,
            ass_path,
            1080,
            1920,
            [{"scene": {"top_text": top, "bottom_text": bottom}, "start": 0.0, "duration": 1.0}],
            layout,
            emphasis,
        )
        preview = still_root / f"{template_id}.png"
        subtitle_filter = (
            f"subtitles=filename='{absolute_filter_path(ass_path)}':"
            f"fontsdir='{absolute_filter_path(renderer.DEFAULT_FONTS_DIR)}'"
        )
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(base),
                "-ss",
                "0.3",
                "-vf",
                subtitle_filter,
                "-frames:v",
                "1",
                str(preview),
            ]
        )
        previews.append(preview)

    labels = [f"[p{index}]" for index in range(len(previews))]
    filters = [f"[{index}:v]scale=270:480{labels[index]}" for index in range(len(previews))]
    layout_values = [f"{(index % 4) * 270}_{(index // 4) * 480}" for index in range(len(previews))]
    filters.append(
        "".join(labels) + f"xstack=inputs={len(previews)}:layout={'|'.join(layout_values)}[v]"
    )
    contact_sheet = still_root / "all-15-contact-sheet.png"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *[part for preview in previews for part in ("-i", str(preview))],
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-frames:v",
            "1",
            str(contact_sheet),
        ]
    )
    return template_ids, contact_sheet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")

    source_dir = output / "_sources"
    source_dir.mkdir(exist_ok=True)
    sources = (("first.mp4", "0x315EFB", 60), ("second.mp4", "0xF3C95B", 30))
    for name, color, fps in sources:
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=720x1280:r={fps}:d=5",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source_dir / name),
            ]
        )

    profile_ids, profile_contact_sheet = render_profile_stills(
        output, ffmpeg, source_dir / "first.mp4"
    )

    rendered: list[dict[str, object]] = []
    previews: list[Path] = []
    renderer = Path(__file__).with_name("render_video.py")
    for template_id, top, bottom, top_term, bottom_term in CASES:
        project_dir = output / template_id
        assets = project_dir / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        for name, _, _ in sources:
            shutil.copy2(source_dir / name, assets / name)
        project = {
            "version": 1,
            "project_id": f"ci-{template_id}",
            "source_text": f"{top}\n{bottom}",
            "canvas": {"width": 1080, "height": 1920, "fps": 30},
            "layout": {"template_id": template_id},
            "voice": {"enabled": False},
            "bgm": False,
            "material_policy": {"allow_image_only": False, "image_only_reason": ""},
            "emphasis": {
                "schema_version": "emphasis.v1",
                "provider": "codex-fixture",
                "source_hash": emphasis_source_hash(top, bottom),
                "prompt_version": "ci-v1",
                "top": [span(top, top_term, "contrast")],
                "bottom": [span(bottom, bottom_term, "conclusion")],
            },
            "cover": {"title": top},
            "scenes": [
                {
                    "id": "s01",
                    "top_text": top,
                    "bottom_text": bottom,
                    "duration": 10.0,
                    "motion": "static",
                    "transition": "cut",
                    "media": [
                        {"path": "assets/first.mp4", "type": "video", "record_id": "ci-first"},
                        {"path": "assets/second.mp4", "type": "video", "record_id": "ci-second"},
                    ],
                }
            ],
            "render": {"output": "output/final.mp4", "preset": "veryfast", "crf": 23},
        }
        project_path = project_dir / "project.json"
        project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = json.loads(run([sys.executable, str(renderer), str(project_path)]))
        video = project_dir / "output" / "final.mp4"
        preview = output / f"{template_id}.png"
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "0.6",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=270:480",
                str(preview),
            ]
        )
        previews.append(preview)
        rendered.append({"template_id": template_id, "video": str(video), "preview": str(preview), **report})

    contact_sheet = output / "contact-sheet.png"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *[part for preview in previews for part in ("-i", str(preview))],
            "-filter_complex",
            "[0:v][1:v][2:v]hstack=inputs=3[v]",
            "-map",
            "[v]",
            "-frames:v",
            "1",
            str(contact_sheet),
        ]
    )
    report_path = output / "artifact-report.json"
    report_path.write_text(
        json.dumps(
            {
                "ok": True,
                "contact_sheet": str(contact_sheet),
                "profile_contact_sheet": str(profile_contact_sheet),
                "profile_ids": profile_ids,
                "outputs": rendered,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "contact_sheet": str(contact_sheet),
                "profile_contact_sheet": str(profile_contact_sheet),
                "profile_count": len(profile_ids),
                "video_count": len(rendered),
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:4000]}), file=sys.stderr)
        raise SystemExit(1)
