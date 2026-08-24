#!/usr/bin/env python3
"""Render a script-to-matrix-video project manifest to a vertical MP4.

This renderer is intentionally deterministic: it turns local images or video
clips, narration, optional sound effects, captions, and simple motion into one
H.264/AAC master. AI generation and semantic storyboarding happen before this
step.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from template_policy import recommended_duration, required_media_count


SUPPORTED_MOTIONS = {"zoom-in", "zoom-out", "pan-left", "pan-right", "static"}
SUPPORTED_TRANSITIONS = {"cut", "dissolve", "dip-black", "push"}
SUPPORTED_LAYOUTS = {"full-frame", "text-media-text"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_CATALOG_PATH = SKILL_ROOT / "assets" / "templates" / "catalog.json"
DEFAULT_FONTS_DIR = SKILL_ROOT / "assets" / "fonts"
FONT_FAMILY_ALIASES = {"Microsoft YaHei": "Noto Sans SC"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to project.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without rendering")
    return parser.parse_args()


def run(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "unknown command failure")[-4000:]
        raise RuntimeError(f"Command failed ({Path(command[0]).name}): {details}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Project manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid project JSON: {exc}") from exc


def load_json_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Project manifest not found: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid project JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Project JSON root must be an object: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def save_json(path: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, suffix=".tmp", delete=False
    ) as handle:
        temp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def save_json_if_unchanged(path: Path, payload: dict[str, Any], expected_sha256: str) -> str:
    lock_path = path.with_name(f".{path.name}.lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"Project manifest is locked by another process: {path}") from exc
    try:
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if current != expected_sha256:
            raise RuntimeError(f"Project manifest changed during processing: {path}")
        save_json(path, payload)
        return hashlib.sha256(path.read_bytes()).hexdigest()
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def manifest_path(value: str, label: str) -> Path:
    text = value.strip()
    if re.match(r"^[A-Za-z]:[\\/]", text) and os.name != "nt":
        raise RuntimeError(f"{label} uses a Windows absolute path on this platform: {text}")
    text = text.replace("\\", os.sep).replace("/", os.sep)
    return Path(text)


def resolve_input(root: Path, value: str, label: str) -> Path:
    candidate = manifest_path(value, label)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not candidate.is_file():
        raise RuntimeError(f"Missing {label}: {candidate}")
    return candidate


def resolve_output(root: Path, value: str) -> Path:
    candidate = manifest_path(value, "render output")
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Render output must stay inside project folder: {candidate}") from exc
    return candidate


def merge_defaults(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge manifest fields over template defaults without mutating either input."""

    merged = dict(defaults)
    for key, value in overrides.items():
        merged[key] = merge_defaults(merged[key], value) if isinstance(merged.get(key), dict) and isinstance(value, dict) else value
    return merged


def resolve_template(project: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    raw_layout = project.get("layout") or {}
    if not isinstance(raw_layout, dict):
        return project, None
    template_id = raw_layout.get("template_id")
    if template_id in (None, ""):
        return project, None
    template_id = str(template_id).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", template_id):
        raise RuntimeError(f"Illegal template_id: {template_id!r}")
    catalog = load_json(TEMPLATE_CATALOG_PATH)
    if catalog.get("version") != 1 or not isinstance(catalog.get("templates"), list):
        raise RuntimeError(f"Invalid template catalog: {TEMPLATE_CATALOG_PATH}")
    templates = [item for item in catalog["templates"] if isinstance(item, dict)]
    ids = [str(item.get("id") or "") for item in templates]
    if len(ids) != len(set(ids)) or not template_id in ids:
        raise RuntimeError(f"Unknown template_id: {template_id}")
    template = next(item for item in templates if item["id"] == template_id)
    template_layout = template.get("layout") or {}
    template_render = template.get("render") or {}
    if not isinstance(template_layout, dict) or not isinstance(template_render, dict):
        raise RuntimeError(f"Invalid template defaults for {template_id}")
    resolved = dict(project)
    resolved["layout"] = merge_defaults(template_layout, raw_layout)
    render = project.get("render") or {}
    if not isinstance(render, dict):
        raise RuntimeError("render must be an object")
    resolved["render"] = merge_defaults(template_render, render)
    return resolved, template_id


def resolve_fonts_dir(root: Path, render: dict[str, Any]) -> Path:
    value = render.get("fonts_dir")
    if value in (None, ""):
        candidate = DEFAULT_FONTS_DIR.resolve()
    else:
        candidate = manifest_path(str(value), "fonts_dir")
        candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"fonts_dir must stay inside project folder: {candidate}") from exc
    if not candidate.is_dir():
        raise RuntimeError(f"fonts_dir is not a directory: {candidate}")
    return candidate


def ffmpeg_filter_path(path: Path, root: Path) -> str:
    try:
        value = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"FFmpeg filter input must be staged inside the project: {path}") from exc
    if not re.fullmatch(r"[A-Za-z0-9._/\-]+", value):
        raise RuntimeError(f"FFmpeg filter path contains unsupported characters: {value}")
    return value


@lru_cache(maxsize=64)
def cached_file_sha256(path_value: str, size: int, mtime_ns: int) -> str:
    digest = hashlib.sha256()
    with Path(path_value).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_font_files(source: Path, families: set[str]) -> list[Path]:
    font_files = [path for path in source.iterdir() if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}]
    source_manifest = source / "sources.json"
    if source_manifest.is_file():
        try:
            font_sources = json.loads(source_manifest.read_text(encoding="utf-8"))["fonts"]
            selected_families = {FONT_FAMILY_ALIASES.get(family, family) for family in families} | {"Noto Sans SC"}
            source_families = [str(item["family"]) for item in font_sources]
            if len(source_families) != len(set(source_families)):
                raise RuntimeError(f"Bundled font source manifest has duplicate families: {source_manifest}")
            missing_families = selected_families - set(source_families)
            if missing_families:
                raise RuntimeError(f"Bundled font families are missing: {', '.join(sorted(missing_families))}")
            selected_sources = [item for item in font_sources if str(item["family"]) in selected_families]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid bundled font source manifest: {source_manifest}") from exc
        font_files = []
        for item in selected_sources:
            filename = str(item.get("file") or "")
            if Path(filename).name != filename:
                raise RuntimeError(f"Bundled font source manifest contains an unsafe path: {filename}")
            path = source / filename
            if not path.is_file():
                raise RuntimeError(f"Bundled font file is missing: {path}")
            expected = str(item.get("sha256") or "").lower()
            stat = path.stat()
            actual = cached_file_sha256(str(path), stat.st_size, stat.st_mtime_ns)
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
                raise RuntimeError(f"Bundled font hash mismatch: {path}")
            font_files.append(path)
    if not font_files:
        raise RuntimeError(f"fonts_dir contains no supported font files: {source}")
    return font_files


def stage_fonts(font_files: list[Path], destination: Path) -> Path:
    staged = destination / "fonts"
    staged.mkdir()
    for source_file in font_files:
        target = staged / source_file.name
        try:
            os.link(source_file, target)
        except OSError:
            shutil.copy2(source_file, target)
    return staged


def required_font_families(render: dict[str, Any], layout: dict[str, Any] | None) -> set[str]:
    families = {validated_font(render.get("subtitle_font", "Microsoft YaHei"), "render.subtitle_font")}
    if layout:
        families.update(font for font in (layout["top_font"], layout["bottom_font"]) if font)
        if layout["kicker"] and layout["kicker"]["font"]:
            families.add(layout["kicker"]["font"])
    return families


def validate_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required on PATH")
    return ffmpeg, ffprobe


def probe_media(ffprobe: str, path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    video = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), {})
    audio = next((item for item in payload.get("streams", []) if item.get("codec_type") == "audio"), {})
    return {
        "duration": round(float(payload.get("format", {}).get("duration", 0)), 3),
        "size_bytes": int(payload.get("format", {}).get("size", 0)),
        "video_codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixel_format": video.get("pix_fmt"),
        "audio_codec": audio.get("codec_name"),
        "sample_rate": int(audio.get("sample_rate", 0)) if audio.get("sample_rate") else None,
        "channels": audio.get("channels"),
    }


def probe_duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(result.stdout.strip() or 0)
    if duration <= 0:
        raise RuntimeError(f"Could not determine positive media duration: {path}")
    return duration


def resolve_bgm(
    project: dict[str, Any], root: Path, voice_enabled: bool, warnings: list[str]
) -> dict[str, Any] | None:
    raw = project.get("bgm")
    if raw in (None, False):
        return None
    if raw is True:
        raw = {"enabled": True}
    if not isinstance(raw, dict):
        warnings.append("bgm must be an object; skipped")
        return None

    enabled = raw.get("enabled", bool(raw.get("path") or raw.get("local_path")))
    if enabled is False or str(enabled).strip().lower() in {"false", "off", "no", "0"}:
        return None
    path_value = str(raw.get("path") or raw.get("local_path") or "").strip()
    if not path_value:
        warnings.append("bgm is enabled but no local path was selected; skipped")
        raw["render_status"] = "skipped-no-path"
        return None

    loop_mode = str(raw.get("loop_mode", "crossfade")).strip().lower()
    if loop_mode not in {"crossfade", "hard"}:
        warnings.append(f"unsupported BGM loop_mode {loop_mode!r}; used 'crossfade'")
        loop_mode = "crossfade"
    default_lufs = -27.0 if voice_enabled else -18.0
    return {
        "config": raw,
        "path": resolve_input(root, path_value, "BGM"),
        "loop_mode": loop_mode,
        "crossfade_seconds": min(2.0, max(0.05, float(raw.get("crossfade_seconds", 0.35)))),
        "fade_in_seconds": min(5.0, max(0.0, float(raw.get("fade_in_seconds", 0.35)))),
        "fade_out_seconds": min(5.0, max(0.0, float(raw.get("fade_out_seconds", 0.70)))),
        "target_lufs": min(-10.0, max(-40.0, float(raw.get("target_lufs", default_lufs)))),
        "gain_db": min(12.0, max(-24.0, float(raw.get("gain_db", 0.0)))),
        "ducking": bool(raw.get("ducking", voice_enabled)),
    }


def allocate_frames(total_frames: int, count: int) -> list[int]:
    if count <= 0:
        raise RuntimeError("Cannot allocate frames without media assets")
    if total_frames < count:
        raise RuntimeError(f"Scene is too short for {count} media assets")
    base, remainder = divmod(total_frames, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def motion_filter(motion: str, width: int, height: int, fps: int, frames: int) -> str:
    if motion not in SUPPORTED_MOTIONS:
        motion = "static"
    fill = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    if motion == "static":
        return fill

    large_w, large_h = width * 2, height * 2
    pre = f"scale={large_w}:{large_h}:force_original_aspect_ratio=increase,crop={large_w}:{large_h}"
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    if motion == "zoom-in":
        z_expr = "min(pzoom+0.0008,1.08)"
        x_expr, y_expr = center_x, center_y
    elif motion == "zoom-out":
        z_expr = "if(eq(on,0),1.08,max(1.0,pzoom-0.0008))"
        x_expr, y_expr = center_x, center_y
    elif motion == "pan-left":
        z_expr = "1.08"
        denominator = max(1, frames - 1)
        x_expr = f"(iw-iw/zoom)*(1-min(on/{denominator},1))"
        y_expr = center_y
    else:  # pan-right
        z_expr = "1.08"
        denominator = max(1, frames - 1)
        x_expr = f"(iw-iw/zoom)*min(on/{denominator},1)"
        y_expr = center_y
    return f"{pre},zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d=1:s={width}x{height}:fps={fps}"


def transition_fade(transition: str) -> float:
    return {"cut": 0.0, "dissolve": 0.12, "dip-black": 0.22, "push": 0.12}.get(transition, 0.0)


def split_caption(text: str, max_chars: int = 14) -> list[str]:
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact:
        return []
    phrases = [part for part in re.split(r"(?<=[，。！？；：,.!?;:])", compact) if part]
    chunks: list[str] = []
    for phrase in phrases:
        while len(phrase) > max_chars:
            chunks.append(phrase[:max_chars])
            phrase = phrase[max_chars:]
        if phrase:
            if chunks and len(chunks[-1]) + len(phrase) <= max_chars:
                chunks[-1] += phrase
            else:
                chunks.append(phrase)
    return chunks


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def wrap_layout_text(text: str, max_chars: int, max_lines: int) -> tuple[str, int]:
    manual_lines = [re.sub(r"[ \t]+", " ", item.strip()) for item in re.split(r"\r?\n", text) if item.strip()]
    if len(manual_lines) > 1 and len(manual_lines) <= max_lines and max(map(len, manual_lines)) <= max_chars + 3:
        return "\n".join(manual_lines), max(map(len, manual_lines))

    compact = ""
    for line in manual_lines:
        if compact and compact[-1].isascii() and compact[-1].isalnum() and line[0].isascii() and line[0].isalnum():
            compact += " "
        compact += line
    if not compact:
        return "", 0
    effective_max = max(max_chars, math.ceil(len(compact) / max_lines))
    chunks = split_caption(compact, max_chars=effective_max)
    if len(chunks) > max_lines:
        effective_max = math.ceil(len(compact) / max_lines)
        chunks = [compact[index : index + effective_max] for index in range(0, len(compact), effective_max)]
    chunks = chunks[:max_lines]
    return "\n".join(chunks), max(map(len, chunks), default=0)


def ass_primary_color(value: str) -> str:
    match = re.fullmatch(r"#([0-9a-fA-F]{6})", value.strip())
    if not match:
        return "&H00FFFFFF&"
    rgb = match.group(1)
    return f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&"


def ffmpeg_color(value: str, default: str) -> str:
    candidate = value.strip()
    match = re.fullmatch(r"#([0-9a-fA-F]{6})", candidate)
    return f"0x{match.group(1)}" if match else f"0x{default.lstrip('#')}"


def ffmpeg_color_alpha(value: str, default: str, opacity: float) -> str:
    return f"{ffmpeg_color(value, default)}@{min(1.0, max(0.0, opacity)):.3f}"


def normalize_highlights(
    scene: dict[str, Any], field: str, text: str, layout: dict[str, Any]
) -> list[tuple[str, str]]:
    raw = scene.get(field)
    highlights: list[tuple[str, str]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            if isinstance(item, dict):
                term = str(item.get("text") or "").strip()
                color = str(item.get("color") or layout["accent_color"])
            else:
                term = str(item).strip()
                color = layout["accent_color"] if index % 2 == 0 else layout["secondary_accent_color"]
            if term:
                highlights.append((term, color))
        return highlights

    if not layout["auto_highlight"]:
        return []

    candidates: list[str] = []
    candidates.extend(re.findall(r"\d+(?:\.\d+)?%?", text))
    candidates.extend(match.strip() for match in re.findall(r"[“\"「『]([^”\"」』]{1,10})[”\"」』]", text))
    if field == "bottom_highlights" and "：" in text:
        tail = text.rsplit("：", 1)[-1].strip("。！!？? ，,")
        if 1 <= len(tail) <= 8:
            candidates.append(tail)

    seen: set[str] = set()
    for index, term in enumerate(candidates):
        if not term or term in seen:
            continue
        seen.add(term)
        color = layout["accent_color"] if index % 2 == 0 else layout["secondary_accent_color"]
        highlights.append((term, color))
    return highlights


def ass_highlight_text(text: str, highlights: list[tuple[str, str]], base_color: str) -> str:
    intervals: list[tuple[int, int, str]] = []
    occupied = [False] * len(text)
    for term, color in sorted(highlights, key=lambda item: len(item[0]), reverse=True):
        cursor = 0
        while term and cursor < len(text):
            start = text.find(term, cursor)
            if start < 0:
                break
            end = start + len(term)
            if not any(occupied[start:end]):
                intervals.append((start, end, color))
                for index in range(start, end):
                    occupied[index] = True
            cursor = end
    if not intervals:
        return ass_escape(text)

    intervals.sort(key=lambda item: item[0])
    parts: list[str] = []
    cursor = 0
    base = ass_primary_color(base_color)
    for start, end, color in intervals:
        if start > cursor:
            parts.append(ass_escape(text[cursor:start]))
        parts.append(f"{{\\1c{ass_primary_color(color)}}}{ass_escape(text[start:end])}{{\\1c{base}}}")
        cursor = end
    if cursor < len(text):
        parts.append(ass_escape(text[cursor:]))
    return "".join(parts)


def even_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(2, parsed - parsed % 2)


def nonnegative_even_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(0, parsed)
    return parsed - parsed % 2


def validated_color(value: Any, label: str) -> str:
    color = str(value).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise RuntimeError(f"{label} must be a #RRGGBB color")
    return color


def validated_font(value: Any, label: str, allow_empty: bool = False) -> str:
    font = str(value or "").strip()
    if allow_empty and not font:
        return ""
    if not re.fullmatch(r"[\w .\-]{1,120}", font):
        raise RuntimeError(f"{label} contains unsupported characters")
    return font


def bounded_int(value: Any, label: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(default if value is None else value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeError(f"{label} must be between {minimum} and {maximum}")
    return parsed


def resolve_kicker(raw: Any, width: int, height: int) -> dict[str, Any] | None:
    if raw in (None, False):
        return None
    if not isinstance(raw, dict):
        raise RuntimeError("layout.kicker must be an object")
    text = str(raw.get("text") or "").strip()
    if not text or len(text) > 120:
        raise RuntimeError("layout.kicker.text must contain 1-120 characters")
    try:
        x, y = int(raw.get("x", 40)), int(raw.get("y", 40))
        font_size, padding = int(raw.get("font_size", 36)), int(raw.get("padding", 12))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("layout.kicker positions and sizes must be integers") from exc
    if not 0 <= x <= width or not 0 <= y <= height or not 12 <= font_size <= height // 2 or not 0 <= padding <= 120:
        raise RuntimeError("layout.kicker values are outside the canvas or reasonable range")
    return {
        "text": text,
        "x": x,
        "y": y,
        "font_size": font_size,
        "color": validated_color(raw.get("color", "#FFFFFF"), "layout.kicker.color"),
        "background_color": validated_color(raw.get("background_color", "#111111"), "layout.kicker.background_color"),
        "font": validated_font(raw.get("font"), "layout.kicker.font", allow_empty=True),
        "padding": padding,
    }


def resolve_surface_boxes(raw: Any, width: int, height: int) -> list[dict[str, Any]]:
    if raw in (None, False):
        return []
    if not isinstance(raw, list) or len(raw) > 24:
        raise RuntimeError("layout.surface_boxes must contain at most 24 rectangles")
    boxes: list[dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"layout.surface_boxes[{index}] must be an object")
        try:
            x, y = int(item.get("x")), int(item.get("y"))
            box_width, box_height = int(item.get("width")), int(item.get("height"))
            opacity = float(item.get("opacity", 1))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"layout.surface_boxes[{index}] needs numeric geometry") from exc
        if x < 0 or y < 0 or box_width <= 0 or box_height <= 0 or x + box_width > width or y + box_height > height or not 0 <= opacity <= 1:
            raise RuntimeError(f"layout.surface_boxes[{index}] must stay within the canvas")
        boxes.append({
            "x": x, "y": y, "width": box_width, "height": box_height,
            "color": validated_color(item.get("color", "#000000"), f"layout.surface_boxes[{index}].color"),
            "opacity": opacity,
        })
    return boxes


def resolve_layout(
    project: dict[str, Any], width: int, height: int, warnings: list[str]
) -> dict[str, Any] | None:
    raw = project.get("layout") or {}
    if not isinstance(raw, dict):
        warnings.append("layout must be an object; used 'full-frame'")
        return None
    preset = str(raw.get("preset", "full-frame")).strip().lower()
    if preset not in SUPPORTED_LAYOUTS:
        warnings.append(f"unsupported layout {preset!r}; used 'full-frame'")
        return None
    if preset == "full-frame":
        return None

    variant = str(raw.get("variant", "native-bold")).strip().lower()
    if variant not in {"native-bold", "classic"}:
        warnings.append(f"unsupported text-media-text variant {variant!r}; used 'native-bold'")
        variant = "native-bold"
    native_bold = variant == "native-bold"

    media = raw.get("media") or {}
    if not isinstance(media, dict):
        media = {}
    default_x = even_int(round(width * (0.0185 if native_bold else 0.0556)), 20 if native_bold else 60)
    default_y = even_int(round(height * (0.2604 if native_bold else 0.21875)), 500 if native_bold else 420)
    default_w = even_int(round(width * (0.9630 if native_bold else 0.8889)), 1040 if native_bold else 960)
    default_h = even_int(round(height * (0.4896 if native_bold else 0.5417)), 940 if native_bold else 1040)
    media_x = even_int(media.get("x"), default_x)
    media_y = even_int(media.get("y"), default_y)
    media_width = even_int(media.get("width"), default_w)
    media_height = even_int(media.get("height"), default_h)
    if media_x + media_width > width or media_y + media_height > height:
        warnings.append("text-media-text media region exceeded the canvas; used default region")
        media_x, media_y, media_width, media_height = default_x, default_y, default_w, default_h

    border_width = nonnegative_even_int(raw.get("media_border_width"), 0 if native_bold else 4)
    border_width = min(border_width, media_x, media_y, width - media_x - media_width, height - media_y - media_height)
    border_width = max(0, border_width - border_width % 2)
    top_y = int(raw.get("top_text_y", round(height * (0.1406 if native_bold else 0.115))))
    bottom_y = int(raw.get("bottom_text_y", round(height * (0.8594 if native_bold else 0.855))))
    top_y = min(max(80, top_y), max(80, media_y - 70))
    bottom_y = min(max(media_y + media_height + 70, bottom_y), height - 170)
    bottom_mode = str(raw.get("bottom_text_mode", "captions")).strip().lower()
    if bottom_mode not in {"captions", "fixed"}:
        warnings.append(f"unsupported bottom_text_mode {bottom_mode!r}; used 'captions'")
        bottom_mode = "captions"

    background_mode = str(raw.get("background_mode", "blurred-media" if native_bold else "solid")).strip().lower()
    if background_mode not in {"solid", "blurred-media"}:
        warnings.append(f"unsupported background_mode {background_mode!r}; used 'solid'")
        background_mode = "solid"

    top_font_size = bounded_int(raw.get("top_font_size"), "layout.top_font_size", 80 if native_bold else 76, 12, height // 2)
    bottom_font_size = bounded_int(raw.get("bottom_font_size"), "layout.bottom_font_size", 70 if native_bold else 62, 12, height // 2)
    top_min_font_size = min(
        top_font_size,
        bounded_int(raw.get("top_min_font_size"), "layout.top_min_font_size", 52 if native_bold else 48, 12, height // 2),
    )
    bottom_min_font_size = min(
        bottom_font_size,
        bounded_int(raw.get("bottom_min_font_size"), "layout.bottom_min_font_size", 46 if native_bold else 42, 12, height // 2),
    )

    return {
        "preset": preset,
        "variant": variant,
        "background_mode": background_mode,
        "background_color": str(raw.get("background_color", "#11151C" if native_bold else "#F5F1E8")),
        "background_blur": min(60.0, max(0.0, float(raw.get("background_blur", 28.0)))),
        "background_brightness": min(1.0, max(-1.0, float(raw.get("background_brightness", -0.22)))),
        "background_saturation": min(3.0, max(0.0, float(raw.get("background_saturation", 0.78)))),
        "band_color": str(raw.get("band_color", "#101318")),
        "top_band_height": min(height, max(0, int(raw.get("top_band_height", media_y)))),
        "top_band_opacity": min(1.0, max(0.0, float(raw.get("top_band_opacity", 0.42 if native_bold else 0.0)))),
        "bottom_band_y": min(height, max(0, int(raw.get("bottom_band_y", media_y + media_height)))),
        "bottom_band_opacity": min(1.0, max(0.0, float(raw.get("bottom_band_opacity", 0.58 if native_bold else 0.0)))),
        "divider_height": max(0, int(raw.get("divider_height", 0))),
        "divider_color": str(raw.get("divider_color", raw.get("accent_color", "#FFD400"))),
        "media_border_color": str(raw.get("media_border_color", "#FFFFFF" if native_bold else "#D8D2C8")),
        "media_border_width": border_width,
        "media_x": media_x,
        "media_y": media_y,
        "media_width": media_width,
        "media_height": media_height,
        "top_text_y": top_y,
        "bottom_text_y": bottom_y,
        "top_font": validated_font(raw.get("top_font"), "layout.top_font", allow_empty=True),
        "bottom_font": validated_font(raw.get("bottom_font"), "layout.bottom_font", allow_empty=True),
        "top_font_size": top_font_size,
        "bottom_font_size": bottom_font_size,
        "top_min_font_size": top_min_font_size,
        "bottom_min_font_size": bottom_min_font_size,
        "top_max_chars": max(6, int(raw.get("top_max_chars", 12))),
        "top_max_lines": min(4, max(1, int(raw.get("top_max_lines", 4 if native_bold else 2)))),
        "bottom_max_chars": max(6, int(raw.get("bottom_max_chars", 12 if native_bold else 14))),
        "bottom_max_lines": min(3, max(1, int(raw.get("bottom_max_lines", 3 if native_bold else 2)))),
        "top_text_color": str(raw.get("top_text_color", "#FFFFFF" if native_bold else "#1F2430")),
        "bottom_text_color": str(raw.get("bottom_text_color", "#FFFFFF" if native_bold else "#1F2430")),
        "text_outline_color": str(raw.get("text_outline_color", "#111111")),
        "top_text_outline": min(12, max(0, int(raw.get("top_text_outline", 8 if native_bold else 0)))),
        "bottom_text_outline": min(12, max(0, int(raw.get("bottom_text_outline", 7 if native_bold else 0)))),
        "text_shadow": min(6, max(0, int(raw.get("text_shadow", 2 if native_bold else 0)))),
        "accent_color": str(raw.get("accent_color", "#FFD400" if native_bold else "#D97745")),
        "secondary_accent_color": str(raw.get("secondary_accent_color", "#FF453A")),
        "auto_highlight": bool(raw.get("auto_highlight", native_bold)),
        "text_pop_in": bool(raw.get("text_pop_in", native_bold)),
        "bottom_text_mode": bottom_mode,
        "kicker": resolve_kicker(raw.get("kicker"), width, height),
        "surface_boxes": resolve_surface_boxes(raw.get("surface_boxes"), width, height),
    }


def write_ass(
    project: dict[str, Any],
    path: Path,
    width: int,
    height: int,
    timeline: list[dict[str, Any]],
    layout: dict[str, Any] | None,
) -> None:
    render = project.get("render", {})
    font = validated_font(render.get("subtitle_font", "Microsoft YaHei"), "render.subtitle_font")
    font_size = bounded_int(render.get("subtitle_font_size"), "render.subtitle_font_size", 70, 12, height // 2)
    margin_v = bounded_int(render.get("subtitle_margin_v"), "render.subtitle_margin_v", 250, 0, height)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Caption,{font},{font_size},&H00FFFFFF,&H0000D7FF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,6,1,2,90,90,{margin_v},1",
        f"Style: Cover,{font},88,&H00FFFFFF,&H0000D7FF,&H00101010,&H78000000,-1,0,0,0,100,100,0,0,1,8,2,5,110,110,0,1",
        f"Style: Overlay,{font},66,&H00FFFFFF,&H0000D7FF,&HCC101218,&HCC101218,-1,0,0,0,100,100,1,0,3,16,0,5,70,70,0,1",
        f"Style: Info,{font},48,&H00FFFFFF,&H0000D7FF,&HCC101218,&HCC101218,-1,0,0,0,100,100,1,0,3,14,0,7,70,70,0,1",
    ]
    if layout:
        top_color = ass_primary_color(layout["top_text_color"])
        bottom_color = ass_primary_color(layout["bottom_text_color"])
        outline_color = ass_primary_color(layout["text_outline_color"])
        top_font = layout["top_font"] or font
        bottom_font = layout["bottom_font"] or font
        lines.extend(
            [
                f"Style: TopText,{top_font},{layout['top_font_size']},{top_color},&H00000000,{outline_color},&H78000000,-1,0,0,0,100,100,0,0,1,{layout['top_text_outline']},{layout['text_shadow']},5,54,54,0,1",
                f"Style: BottomText,{bottom_font},{layout['bottom_font_size']},{bottom_color},&H00000000,{outline_color},&H78000000,-1,0,0,0,100,100,0,0,1,{layout['bottom_text_outline']},{layout['text_shadow']},5,54,54,0,1",
            ]
        )
        kicker = layout["kicker"]
        if kicker:
            lines.append(
                f"Style: Kicker,{kicker['font'] or font},{kicker['font_size']},{ass_primary_color(kicker['color'])},&H00000000,{ass_primary_color(kicker['background_color'])},{ass_primary_color(kicker['background_color'])},-1,0,0,0,100,100,0,0,3,{kicker['padding']},0,7,0,0,0,1"
            )
    lines.extend(
        [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    if layout and layout["kicker"] and timeline:
        kicker = layout["kicker"]
        end = timeline[-1]["start"] + timeline[-1]["duration"]
        lines.append(
            f"Dialogue: 3,{ass_time(0)},{ass_time(end)},Kicker,,0,0,0,,{{\\an7\\pos({kicker['x']},{kicker['y']})}}{ass_escape(kicker['text'])}"
        )

    cover_title = str(project.get("cover", {}).get("title") or "").strip()
    cover_end = 0.0
    if cover_title and timeline:
        first_scene_title = str(timeline[0]["scene"].get("top_text") or "").strip()
        cover_replaces_first_title = bool(
            layout
            and first_scene_title
            and re.sub(r"\s+", "", cover_title) == re.sub(r"\s+", "", first_scene_title)
        )
        cover_end = (
            timeline[0]["duration"]
            if cover_replaces_first_title
            else min(1.2, timeline[0]["duration"])
        )
        cover_max_chars = layout["top_max_chars"] if layout else 10
        cover_max_lines = layout["top_max_lines"] if layout else 2
        cover_text, cover_longest = wrap_layout_text(cover_title, cover_max_chars, cover_max_lines)
        if layout:
            cover_size = max(
                layout["top_min_font_size"],
                round(layout["top_font_size"] * min(1.0, layout["top_max_chars"] / max(1, cover_longest))),
            )
            cover_tag_parts = [f"\\an5", f"\\pos({width // 2},{layout['top_text_y']})", f"\\fs{cover_size}"]
            if layout["text_pop_in"]:
                cover_tag_parts.extend(["\\fscx94", "\\fscy94", "\\t(0,220,\\fscx100\\fscy100)"])
            cover_tags = "{" + "".join(cover_tag_parts) + "}"
            cover_highlights = (
                normalize_highlights(timeline[0]["scene"], "top_highlights", cover_text, layout)
                if cover_replaces_first_title
                else []
            )
            cover_rendered = ass_highlight_text(
                cover_text, cover_highlights, layout["top_text_color"]
            )
            lines.append(
                f"Dialogue: 1,{ass_time(0)},{ass_time(cover_end)},TopText,,0,0,0,,{cover_tags}{cover_rendered}"
            )
        else:
            lines.append(
                f"Dialogue: 1,{ass_time(0)},{ass_time(cover_end)},Cover,,0,0,0,,{ass_escape(cover_text)}"
            )

    for entry in timeline:
        scene = entry["scene"]
        if layout:
            top_text = str(scene.get("top_text") or "").strip()
            if not top_text:
                fallback = scene.get("caption_chunks") or split_caption(str(scene.get("text") or ""), max_chars=12)
                top_text = str(fallback[0]).strip() if fallback else ""
            if top_text:
                top_text, top_longest = wrap_layout_text(
                    top_text, max_chars=layout["top_max_chars"], max_lines=layout["top_max_lines"]
                )
                top_size = max(
                    layout["top_min_font_size"],
                    round(layout["top_font_size"] * min(1.0, layout["top_max_chars"] / max(1, top_longest))),
                )
                top_start = entry["start"]
                if entry is timeline[0] and cover_title:
                    top_start += cover_end
                if top_start < entry["start"] + entry["duration"]:
                    top_tag_parts = [
                        "\\an5",
                        f"\\pos({width // 2},{layout['top_text_y']})",
                        "\\fad(120,100)",
                        f"\\fs{top_size}",
                    ]
                    if layout["text_pop_in"]:
                        top_tag_parts.extend(["\\fscx94", "\\fscy94", "\\t(0,220,\\fscx100\\fscy100)"])
                    top_tags = "{" + "".join(top_tag_parts) + "}"
                    top_highlights = normalize_highlights(scene, "top_highlights", top_text, layout)
                    top_rendered = ass_highlight_text(top_text, top_highlights, layout["top_text_color"])
                    lines.append(
                        f"Dialogue: 1,{ass_time(top_start)},{ass_time(entry['start'] + entry['duration'])},TopText,,0,0,0,,{top_tags}{top_rendered}"
                    )
        for overlay in scene.get("overlays") or []:
            if not isinstance(overlay, dict):
                raise RuntimeError("scene overlays must contain objects")
            text = str(overlay.get("text") or "").strip()
            if not text:
                continue
            relative_start = max(0.0, float(overlay.get("start", 0.0)))
            relative_end = min(entry["duration"], float(overlay.get("end", entry["duration"])))
            if relative_end <= relative_start:
                continue
            x = bounded_int(overlay.get("x"), "overlay.x", width // 2, 0, width)
            y = bounded_int(overlay.get("y"), "overlay.y", height // 2, 0, height)
            style = "Info" if str(overlay.get("style", "overlay")).lower() == "info" else "Overlay"
            alignment = bounded_int(overlay.get("alignment"), "overlay.alignment", 7 if style == "Info" else 5, 1, 9)
            font_size_override = bounded_int(overlay.get("font_size"), "overlay.font_size", 0, 0, height // 2)
            if 0 < font_size_override < 12:
                raise RuntimeError("overlay.font_size must be 0 or at least 12")
            color = ass_primary_color(str(overlay.get("color", "#FFFFFF")))
            tags = [f"\\an{alignment}", f"\\pos({x},{y})", "\\fad(120,120)", f"\\1c{color}"]
            if font_size_override > 0:
                tags.append(f"\\fs{font_size_override}")
            tag_block = "{" + "".join(tags) + "}"
            lines.append(
                f"Dialogue: 2,{ass_time(entry['start'] + relative_start)},{ass_time(entry['start'] + relative_end)},{style},,0,0,0,,{tag_block}{ass_escape(text)}"
            )

        fixed_bottom_text = str(scene.get("bottom_text") or "").strip() if layout else ""
        if layout and (layout["bottom_text_mode"] == "fixed" or fixed_bottom_text):
            fixed_bottom_text = fixed_bottom_text or str(scene.get("text") or "").strip()
            fixed_bottom_text, bottom_longest = wrap_layout_text(
                fixed_bottom_text,
                max_chars=layout["bottom_max_chars"],
                max_lines=layout["bottom_max_lines"],
            )
            if fixed_bottom_text:
                bottom_size = max(
                    layout["bottom_min_font_size"],
                    round(
                        layout["bottom_font_size"]
                        * min(1.0, layout["bottom_max_chars"] / max(1, bottom_longest))
                    ),
                )
                bottom_tag_parts = [
                    "\\an5",
                    f"\\pos({width // 2},{layout['bottom_text_y']})",
                    "\\fad(160,100)",
                    f"\\fs{bottom_size}",
                ]
                if layout["text_pop_in"]:
                    bottom_tag_parts.extend(["\\fscx96", "\\fscy96", "\\t(0,260,\\fscx100\\fscy100)"])
                bottom_tags = "{" + "".join(bottom_tag_parts) + "}"
                bottom_highlights = normalize_highlights(scene, "bottom_highlights", fixed_bottom_text, layout)
                bottom_rendered = ass_highlight_text(
                    fixed_bottom_text, bottom_highlights, layout["bottom_text_color"]
                )
                lines.append(
                    f"Dialogue: 0,{ass_time(entry['start'])},{ass_time(entry['start'] + entry['duration'])},BottomText,,0,0,0,,{bottom_tags}{bottom_rendered}"
                )
            continue

        chunks = scene.get("caption_chunks") or split_caption(str(scene.get("text") or ""))
        chunks = [str(chunk).strip() for chunk in chunks if str(chunk).strip()]
        scene["caption_chunks"] = chunks
        if not chunks:
            continue
        narration_duration = min(float(scene.get("audio_duration") or entry["duration"]), entry["duration"])
        weights = [max(1, len(re.sub(r"[，。！？；：,.!?;:\s]", "", chunk))) for chunk in chunks]
        total_weight = sum(weights)
        cursor = entry["start"]
        for index, (chunk, weight) in enumerate(zip(chunks, weights)):
            part = narration_duration * weight / total_weight
            end = entry["start"] + narration_duration if index == len(chunks) - 1 else cursor + part
            if layout:
                caption_text, caption_longest = wrap_layout_text(
                    chunk, max_chars=layout["bottom_max_chars"], max_lines=layout["bottom_max_lines"]
                )
                caption_size = max(
                    layout["bottom_min_font_size"],
                    round(
                        layout["bottom_font_size"]
                        * min(1.0, layout["bottom_max_chars"] / max(1, caption_longest))
                    ),
                )
                bottom_tags = f"{{\\an5\\pos({width // 2},{layout['bottom_text_y']})\\fs{caption_size}}}"
                bottom_highlights = normalize_highlights(scene, "bottom_highlights", caption_text, layout)
                caption_rendered = ass_highlight_text(
                    caption_text, bottom_highlights, layout["bottom_text_color"]
                )
                lines.append(
                    f"Dialogue: 0,{ass_time(cursor)},{ass_time(end)},BottomText,,0,0,0,,{bottom_tags}{caption_rendered}"
                )
            else:
                lines.append(
                    f"Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Caption,,0,0,0,,{ass_escape(chunk)}"
                )
            cursor = end

    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def render_media_segment(
    ffmpeg: str,
    media: Path,
    media_kind: str,
    media_start: float,
    output: Path,
    width: int,
    height: int,
    fps: int,
    frames: int,
    motion: str,
    fade_in: float,
    fade_out: float,
    crf: int,
    preset: str,
    layout: dict[str, Any] | None,
) -> None:
    duration = frames / fps
    is_video = media_kind == "video"
    if is_video:
        input_args = ["-ss", f"{max(0.0, media_start):.3f}", "-stream_loop", "-1", "-i", str(media)]
        base_media_filter = (
            f"fps={fps},scale={{width}}:{{height}}:force_original_aspect_ratio=increase,"
            "crop={width}:{height}"
        )
    else:
        input_args = ["-loop", "1", "-framerate", str(fps), "-i", str(media)]
        base_media_filter = ""
    filter_option = "-vf"
    map_args: list[str] = []
    if layout:
        media_width = int(layout["media_width"])
        media_height = int(layout["media_height"])
        media_x = int(layout["media_x"])
        media_y = int(layout["media_y"])
        border = int(layout["media_border_width"])
        foreground_filter = (
            base_media_filter.format(width=media_width, height=media_height)
            if is_video
            else motion_filter(motion, media_width, media_height, fps, frames)
        )
        foreground_filters = [foreground_filter, "setsar=1"]
        if border > 0:
            border_color = ffmpeg_color(layout["media_border_color"], "D8D2C8")
            foreground_filters.append(
                f"pad={media_width + border * 2}:{media_height + border * 2}:{border}:{border}:color={border_color}"
            )
            media_x -= border
            media_y -= border

        surface_filters: list[str] = []
        if layout["top_band_opacity"] > 0 and layout["top_band_height"] > 0:
            color = ffmpeg_color_alpha(layout["band_color"], "101318", layout["top_band_opacity"])
            surface_filters.append(f"drawbox=x=0:y=0:w=iw:h={layout['top_band_height']}:color={color}:t=fill")
        if layout["bottom_band_opacity"] > 0 and layout["bottom_band_y"] < height:
            color = ffmpeg_color_alpha(layout["band_color"], "101318", layout["bottom_band_opacity"])
            surface_filters.append(
                f"drawbox=x=0:y={layout['bottom_band_y']}:w=iw:h={height - layout['bottom_band_y']}:color={color}:t=fill"
            )
        if layout["divider_height"] > 0 and layout["bottom_band_y"] < height:
            color = ffmpeg_color_alpha(layout["divider_color"], "FFD400", 0.95)
            divider_y = max(0, layout["bottom_band_y"] - layout["divider_height"])
            surface_filters.append(
                f"drawbox=x=0:y={divider_y}:w=iw:h={layout['divider_height']}:color={color}:t=fill"
            )
        for box in layout["surface_boxes"]:
            color = ffmpeg_color_alpha(box["color"], "000000", box["opacity"])
            surface_filters.append(
                f"drawbox=x={box['x']}:y={box['y']}:w={box['width']}:h={box['height']}:color={color}:t=fill"
            )

        if layout["background_mode"] == "blurred-media":
            blur = layout["background_blur"]
            background_filters = [
                f"fps={fps}",
                f"scale={width}:{height}:force_original_aspect_ratio=increase",
                f"crop={width}:{height}",
                f"gblur=sigma={blur:.2f}:steps=2" if blur > 0 else "null",
                f"eq=brightness={layout['background_brightness']:.3f}:saturation={layout['background_saturation']:.3f}",
                "setsar=1",
            ]
            composite_filters = [
                f"[0:v]split=2[bgsrc][fgsrc]",
                f"[bgsrc]{','.join(background_filters)}[bg]",
                f"[fgsrc]{','.join(foreground_filters)}[fg]",
                f"[bg][fg]overlay=x={media_x}:y={media_y}:shortest=1",
            ]
            tail_filters = surface_filters[:]
            if fade_in > 0:
                tail_filters.append(f"fade=t=in:st=0:d={min(fade_in, duration / 3):.3f}")
            if fade_out > 0:
                duration_out = min(fade_out, duration / 3)
                tail_filters.append(
                    f"fade=t=out:st={max(0, duration - duration_out):.3f}:d={duration_out:.3f}"
                )
            tail_filters.append("format=yuv420p")
            composite_filters[-1] += "," + ",".join(tail_filters) + "[v]"
            filters = ";".join(composite_filters)
            filter_option = "-filter_complex"
            map_args = ["-map", "[v]"]
        else:
            background_color = ffmpeg_color(layout["background_color"], "F5F1E8")
            filters_list = foreground_filters + [
                f"pad={width}:{height}:{media_x}:{media_y}:color={background_color}"
            ]
            filters_list.extend(surface_filters)
            if fade_in > 0:
                filters_list.append(f"fade=t=in:st=0:d={min(fade_in, duration / 3):.3f}")
            if fade_out > 0:
                duration_out = min(fade_out, duration / 3)
                filters_list.append(
                    f"fade=t=out:st={max(0, duration - duration_out):.3f}:d={duration_out:.3f}"
                )
            filters_list.append("format=yuv420p")
            filters = ",".join(filters_list)
    else:
        foreground_filter = (
            base_media_filter.format(width=width, height=height)
            if is_video
            else motion_filter(motion, width, height, fps, frames)
        )
        filters_list = [foreground_filter, "setsar=1"]
        if fade_in > 0:
            filters_list.append(f"fade=t=in:st=0:d={min(fade_in, duration / 3):.3f}")
        if fade_out > 0:
            duration_out = min(fade_out, duration / 3)
            filters_list.append(f"fade=t=out:st={max(0, duration - duration_out):.3f}:d={duration_out:.3f}")
        filters_list.append("format=yuv420p")
        filters = ",".join(filters_list)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *input_args,
            filter_option,
            filters,
            *map_args,
            "-frames:v",
            str(frames),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
    )


def write_concat_list(paths: list[Path], destination: Path) -> None:
    entries = []
    for path in paths:
        value = path.resolve().as_posix().replace("'", "'\\''")
        entries.append(f"file '{value}'")
    destination.write_text("\n".join(entries) + "\n", encoding="utf-8")


def mux_scene_audio(
    ffmpeg: str,
    root: Path,
    silent_video: Path,
    voice: Path | None,
    sfx_items: list[dict[str, Any]],
    duration: float,
    output: Path,
) -> None:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent_video)]
    if voice:
        command.extend(["-i", str(voice)])
    else:
        command.extend(
            ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
        )
    resolved_sfx: list[tuple[Path, float, float]] = []
    for index, item in enumerate(sfx_items):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path = resolve_input(root, str(item["path"]), f"SFX {index + 1}")
        resolved_sfx.append((path, max(0.0, float(item.get("offset", 0))), float(item.get("gain_db", -12))))
        command.extend(["-i", str(path)])

    filter_parts = [f"[1:a]apad=pad_dur={duration:.3f},atrim=0:{duration:.3f}[voice]"]
    audio_labels = ["[voice]"]
    for index, (_, offset, gain_db) in enumerate(resolved_sfx, start=2):
        delay_ms = int(round(offset * 1000))
        label = f"sfx{index}"
        filter_parts.append(f"[{index}:a]adelay={delay_ms}|{delay_ms},volume={gain_db:.2f}dB[{label}]")
        audio_labels.append(f"[{label}]")
    if len(audio_labels) == 1:
        filter_parts.append("[voice]alimiter=limit=0.95[aout]")
    else:
        filter_parts.append(
            f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration=first:dropout_transition=0,alimiter=limit=0.95[aout]"
        )
    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-t",
            f"{duration:.3f}",
            str(output),
        ]
    )
    run(command)


def mix_bgm(
    ffmpeg: str,
    ffprobe: str,
    source_video: Path,
    output: Path,
    duration: float,
    bgm: dict[str, Any],
    mix_program_audio: bool,
) -> None:
    bgm_path: Path = bgm["path"]
    bgm_duration = probe_duration(ffprobe, bgm_path)
    fade_in = min(float(bgm["fade_in_seconds"]), duration / 3)
    fade_out = min(float(bgm["fade_out_seconds"]), duration / 3)
    fade_out_start = max(0.0, duration - fade_out)
    target_lufs = float(bgm["target_lufs"])
    gain_db = float(bgm["gain_db"])
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_video)]
    filters: list[str] = []

    if bgm["loop_mode"] == "hard":
        command.extend(["-stream_loop", "-1", "-i", str(bgm_path)])
        filters.append(
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"loudnorm=I={target_lufs:.2f}:LRA=7:TP=-1.5,"
            f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[bgmloop]"
        )
        bed_label = "[bgmloop]"
        loop_count = max(1, math.ceil(duration / bgm_duration))
    else:
        crossfade = min(float(bgm["crossfade_seconds"]), max(0.05, bgm_duration / 3))
        effective = max(0.05, bgm_duration - crossfade)
        loop_count = max(1, math.ceil(max(0.0, duration - crossfade) / effective))
        if loop_count > 80:
            raise RuntimeError("BGM needs more than 80 loop segments; choose a longer track")
        for index in range(loop_count):
            command.extend(["-i", str(bgm_path)])
            filters.append(
                f"[{index + 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"atrim=0:{bgm_duration:.3f},asetpts=PTS-STARTPTS,"
                f"loudnorm=I={target_lufs:.2f}:LRA=7:TP=-1.5[bgm{index}]"
            )
        bed_label = "[bgm0]"
        for index in range(1, loop_count):
            output_label = f"bgmx{index}"
            filters.append(
                f"{bed_label}[bgm{index}]acrossfade=d={crossfade:.3f}:c1=tri:c2=tri[{output_label}]"
            )
            bed_label = f"[{output_label}]"

    bed_tail = [f"atrim=0:{duration:.3f}", "asetpts=PTS-STARTPTS"]
    if fade_in > 0:
        bed_tail.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        bed_tail.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")
    if gain_db:
        bed_tail.append(f"volume={gain_db:.2f}dB")
    filters.append(f"{bed_label}{','.join(bed_tail)}[bgmbed]")

    if mix_program_audio:
        filters.append(
            f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[program]"
        )
        if bgm["ducking"]:
            filters.append(
                "[bgmbed][program]sidechaincompress="
                "threshold=0.025:ratio=8:attack=80:release=350[bgmducked]"
            )
            mix_label = "[bgmducked]"
        else:
            mix_label = "[bgmbed]"
        filters.append(
            f"[program]{mix_label}amix=inputs=2:duration=first:normalize=0,"
            "alimiter=limit=0.95[aout]"
        )
    else:
        filters.append("[bgmbed]alimiter=limit=0.95[aout]")

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command)
    bgm["config"]["render_status"] = "mixed"
    bgm["config"]["source_duration"] = round(bgm_duration, 3)
    bgm["config"]["loop_count"] = loop_count
    bgm["config"]["resolved_target_lufs"] = target_lufs


def main() -> int:
    args = parse_args()
    project_path = args.project.resolve()
    root = project_path.parent
    source_project, source_sha256 = load_json_snapshot(project_path)
    project, template_id = resolve_template(source_project)
    ffmpeg, ffprobe = validate_tools()

    canvas = project.get("canvas", {})
    if not isinstance(canvas, dict):
        raise RuntimeError("canvas must be an object")
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    fps = int(canvas.get("fps", 30))
    if width <= 0 or height <= 0 or fps <= 0 or width % 2 or height % 2:
        raise RuntimeError("Canvas width and height must be positive even integers; fps must be positive")
    scenes = project.get("scenes")
    if not isinstance(scenes, list) or not scenes or any(not isinstance(scene, dict) for scene in scenes):
        raise RuntimeError("project.json must contain a non-empty array of scene objects")

    render = project.setdefault("render", {})
    if not isinstance(render, dict):
        raise RuntimeError("render must be an object")
    fonts_dir = resolve_fonts_dir(root, render)
    crf = int(render.get("crf", 18))
    preset = str(render.get("preset", "medium"))
    output = resolve_output(root, str(render.get("output", "output/final.mp4")))
    warnings: list[str] = []
    layout = resolve_layout(project, width, height, warnings)
    font_files = resolve_font_files(fonts_dir, required_font_families(render, layout))
    voice_config = project.get("voice") or {}
    voice_enabled = not (isinstance(voice_config, dict) and voice_config.get("enabled") is False)
    bgm = resolve_bgm(project, root, voice_enabled, warnings)
    prepared: list[dict[str, Any]] = []
    cover_path: Path | None = None
    if project.get("cover", {}).get("image"):
        cover_path = resolve_input(root, str(project["cover"]["image"]), "cover image")

    for index, scene in enumerate(scenes):
        scene_id = str(scene.get("id") or f"s{index + 1:02d}")
        scene["id"] = scene_id
        duration = float(scene.get("duration") or 0)
        audio_duration = float(scene.get("audio_duration") or 0)
        if not math.isfinite(duration) or not math.isfinite(audio_duration):
            raise RuntimeError(f"Scene {scene_id} duration values must be finite numbers")
        if voice_enabled:
            if duration <= 0 or audio_duration <= 0:
                raise RuntimeError(f"Scene {scene_id} has no locked TTS duration; run aliyun_tts.py first")
            if duration + 0.001 < audio_duration:
                raise RuntimeError(f"Scene {scene_id} duration is shorter than its narration")
            voice: Path | None = resolve_input(root, str(scene.get("audio") or ""), f"scene {scene_id} narration")
        else:
            if duration <= 0:
                raise RuntimeError(f"Scene {scene_id} needs an explicit positive duration when voice.enabled is false")
            audio_duration = 0.0
            voice = None
        media_values = scene.get("media") or scene.get("images") or []
        if not isinstance(media_values, list) or not media_values:
            raise RuntimeError(f"Scene {scene_id} has no media assets")
        assets: list[dict[str, Any]] = []
        for asset_index, value in enumerate(media_values):
            if isinstance(value, dict):
                raw_path = str(value.get("path") or "")
                media_kind = str(value.get("type") or "").strip().lower()
                media_start = max(0.0, float(value.get("start") or 0))
            else:
                raw_path = str(value)
                media_kind = ""
                media_start = 0.0
            path = resolve_input(root, raw_path, f"scene {scene_id} media {asset_index + 1}")
            if media_kind not in {"image", "video"}:
                media_kind = "video" if path.suffix.lower() in VIDEO_SUFFIXES else "image"
            assets.append({"path": path, "type": media_kind, "start": media_start})
        if index == 0 and cover_path and all(asset["path"] != cover_path for asset in assets):
            assets.insert(0, {"path": cover_path, "type": "image", "start": 0.0})
        motion = str(scene.get("motion", "static"))
        if motion not in SUPPORTED_MOTIONS:
            warnings.append(f"{scene_id}: unsupported motion {motion!r}; used 'static'")
            motion = "static"
        transition = str(scene.get("transition", "cut"))
        if transition not in SUPPORTED_TRANSITIONS:
            warnings.append(f"{scene_id}: unsupported transition {transition!r}; used 'cut'")
            transition = "cut"
        if transition == "push":
            warnings.append(f"{scene_id}: 'push' approximated with a short dissolve in the FFmpeg renderer")
        total_frames = max(1, int(round(duration * fps)))
        frame_counts = allocate_frames(total_frames, len(assets))
        exact_duration = total_frames / fps
        scene["duration"] = round(exact_duration, 3)
        prepared.append(
            {
                "scene": scene,
                "id": scene_id,
                "duration": exact_duration,
                "audio_duration": audio_duration,
                "voice": voice,
                "assets": assets,
                "frame_counts": frame_counts,
                "motion": motion,
                "transition": transition,
            }
        )

    if layout and layout["preset"] == "text-media-text":
        target_duration = recommended_duration(scenes)
        minimum_frames = math.ceil(target_duration * fps)
        current_frames = sum(sum(item["frame_counts"]) for item in prepared)
        if current_frames < minimum_frames:
            added_frames = minimum_frames - current_frames
            final_item = prepared[-1]
            final_total_frames = sum(final_item["frame_counts"]) + added_frames
            final_item["frame_counts"] = allocate_frames(final_total_frames, len(final_item["assets"]))
            final_item["duration"] = sum(final_item["frame_counts"]) / fps
            final_item["scene"]["duration"] = round(final_item["duration"], 3)
            warnings.append(
                f"text-media-text total duration was below the copy-based target {target_duration:.1f} seconds; "
                f"extended the final scene by {added_frames / fps:.3f} seconds"
            )

        effective_duration = sum(sum(item["frame_counts"]) for item in prepared) / fps
        unique_assets = {str(asset["path"]).casefold() for item in prepared for asset in item["assets"]}
        required_assets = required_media_count(effective_duration)
        if len(unique_assets) < required_assets:
            raise RuntimeError(
                f"text-media-text needs at least {required_assets} distinct media assets for "
                f"{effective_duration:.1f} seconds; found {len(unique_assets)}"
            )
        video_assets = {str(asset["path"]).casefold() for item in prepared for asset in item["assets"] if asset["type"] == "video"}
        material_policy = project.get("material_policy") or {}
        allow_image_only = bool(material_policy.get("allow_image_only")) and bool(
            str(material_policy.get("image_only_reason") or "").strip()
        )
        if not video_assets and not allow_image_only:
            raise RuntimeError(
                "text-media-text image-only output is disabled by default; search approved video records first. "
                "If no suitable video exists, set material_policy.allow_image_only=true and record image_only_reason."
            )
        if not video_assets and allow_image_only:
            warnings.append(f"image-only fallback: {material_policy['image_only_reason']}")

    timeline: list[dict[str, Any]] = []
    cursor = 0.0
    for item in prepared:
        item["scene"]["timeline_start"] = round(cursor, 3)
        cursor += item["duration"]
        item["scene"]["timeline_end"] = round(cursor, 3)
        timeline.append({"scene": item["scene"], "start": item["scene"]["timeline_start"], "duration": item["duration"]})

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "output": str(output),
                    "duration": round(cursor, 3),
                    "copy_target_duration": recommended_duration(scenes) if layout and layout["preset"] == "text-media-text" else None,
                    "layout": layout["preset"] if layout else "full-frame",
                    "layout_variant": layout["variant"] if layout else None,
                    "background_mode": layout["background_mode"] if layout else None,
                    "template_id": template_id,
                    "fonts_dir": str(fonts_dir),
                    "voice_enabled": voice_enabled,
                    "bgm_enabled": bgm is not None,
                    "bgm_path": str(bgm["path"]) if bgm else None,
                    "scenes": [
                        {
                            "id": item["id"],
                            "duration": round(item["duration"], 3),
                            "media_assets": len(item["assets"]),
                            "video_assets": sum(1 for asset in item["assets"] if asset["type"] == "video"),
                        }
                        for item in prepared
                    ],
                    "warnings": warnings,
                },
                ensure_ascii=False,
            )
        )
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".matrix-render-", dir=root) as temp_value:
        temp = Path(temp_value)
        scene_outputs: list[Path] = []
        for scene_index, item in enumerate(prepared):
            segment_paths: list[Path] = []
            fade_duration = transition_fade(item["transition"])
            intra_asset_fade = 0.0 if item["transition"] == "cut" else 0.10
            for asset_index, (asset, frames) in enumerate(zip(item["assets"], item["frame_counts"])):
                segment = temp / f"{scene_index:03d}-{asset_index:02d}.mp4"
                first_absolute_asset = scene_index == 0 and asset_index == 0
                render_media_segment(
                    ffmpeg=ffmpeg,
                    media=asset["path"],
                    media_kind=asset["type"],
                    media_start=asset["start"],
                    output=segment,
                    width=width,
                    height=height,
                    fps=fps,
                    frames=frames,
                    motion=item["motion"],
                    fade_in=(
                        0.0
                        if first_absolute_asset
                        else (intra_asset_fade if asset_index > 0 else fade_duration)
                    ),
                    fade_out=(
                        intra_asset_fade
                        if asset_index < len(item["assets"]) - 1
                        else fade_duration
                    ),
                    crf=crf,
                    preset=preset,
                    layout=layout,
                )
                segment_paths.append(segment)
            segment_list = temp / f"{scene_index:03d}-segments.txt"
            write_concat_list(segment_paths, segment_list)
            silent_scene = temp / f"{scene_index:03d}-silent.mp4"
            run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(segment_list),
                    "-c",
                    "copy",
                    str(silent_scene),
                ]
            )
            scene_output = temp / f"{scene_index:03d}-scene.mp4"
            mux_scene_audio(
                ffmpeg=ffmpeg,
                root=root,
                silent_video=silent_scene,
                voice=item["voice"],
                sfx_items=item["scene"].get("sfx") or [],
                duration=item["duration"],
                output=scene_output,
            )
            scene_outputs.append(scene_output)
            item["scene"]["render_status"] = "rendered"

        scene_list = temp / "scenes.txt"
        write_concat_list(scene_outputs, scene_list)
        assembled = temp / "assembled.mp4"
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(scene_list),
                "-c",
                "copy",
                str(assembled),
            ]
        )
        ass_path = temp / "captions.ass"
        write_ass(project, ass_path, width, height, timeline, layout)
        staged_fonts = stage_fonts(font_files, temp)
        subtitle_filter = (
            f"subtitles=filename='{ffmpeg_filter_path(ass_path, root)}':"
            f"fontsdir='{ffmpeg_filter_path(staged_fonts, root)}'"
        )
        captioned = temp / "captioned.mp4" if bgm else output
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(assembled),
                "-vf",
                subtitle_filter,
                "-c:v",
                str(render.get("video_codec", "libx264")),
                "-preset",
                preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                str(render.get("audio_codec", "aac")),
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(captioned),
            ],
            cwd=root,
        )
        if bgm:
            mix_bgm(
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                source_video=captioned,
                output=output,
                duration=cursor,
                bgm=bgm,
                mix_program_audio=voice_enabled
                or any(bool(item["scene"].get("sfx")) for item in prepared),
            )

    report = probe_media(ffprobe, output)
    if report["video_codec"] != "h264" or report["audio_codec"] != "aac":
        raise RuntimeError(f"Unexpected final codecs: {report}")
    if report["width"] != width or report["height"] != height or report["duration"] <= 0:
        raise RuntimeError(f"Final media probe did not match the project canvas: {report}")
    report["output"] = output.relative_to(root).as_posix()
    report["layout"] = layout["preset"] if layout else "full-frame"
    report["layout_variant"] = layout["variant"] if layout else None
    report["background_mode"] = layout["background_mode"] if layout else None
    report["template_id"] = template_id
    report["fonts_dir"] = str(fonts_dir)
    report["voice_enabled"] = voice_enabled
    report["bgm_enabled"] = bgm is not None
    if bgm:
        report["bgm"] = {
            "path": bgm["path"].relative_to(root).as_posix()
            if bgm["path"].is_relative_to(root)
            else str(bgm["path"]),
            "loop_mode": bgm["loop_mode"],
            "loop_count": bgm["config"].get("loop_count"),
            "target_lufs": bgm["config"].get("resolved_target_lufs"),
            "ducking": bgm["ducking"],
        }
    report["warnings"] = warnings
    source_project["render_report"] = report
    save_json_if_unchanged(project_path, source_project, source_sha256)
    print(json.dumps({"ok": True, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:4000]}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
