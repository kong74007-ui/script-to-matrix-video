#!/usr/bin/env python3
"""Deterministic policy helpers for text-media-text template videos."""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any


MIN_DURATION_SECONDS = 8.0
NORMAL_MAX_DURATION_SECONDS = 15.0
READING_UNITS_PER_SECOND = 5.0
READING_TAIL_SECONDS = 1.5
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


def visible_reading_units(value: Any) -> int:
    """Count visible CJK characters, Latin letters, and digits."""

    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9]", str(value or "")))


def unique_copy_pairs(scenes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return unique top/bottom copy pairs without multiplying persistent text."""

    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for scene in scenes:
        pair = (str(scene.get("top_text") or ""), str(scene.get("bottom_text") or ""))
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(pair)
    return pairs


def recommended_duration(scenes: list[dict[str, Any]]) -> float:
    """Calculate the template duration from persistent visible copy."""

    units = sum(visible_reading_units(top) + visible_reading_units(bottom) for top, bottom in unique_copy_pairs(scenes))
    raw = max(MIN_DURATION_SECONDS, units / READING_UNITS_PER_SECOND + READING_TAIL_SECONDS)
    return math.ceil(raw * 10.0) / 10.0


def required_media_count(duration: float) -> int:
    """Return the minimum number of distinct media assets for a duration."""

    if duration <= 10.0:
        return 2
    if duration <= NORMAL_MAX_DURATION_SECONDS:
        return 3
    return 4


def infer_media_type(path: str | Path, explicit: str | None = None) -> str:
    """Normalize a media type, falling back to the filename suffix."""

    normalized = str(explicit or "").strip().lower()
    if normalized in {"video", "视频"}:
        return "video"
    if normalized in {"image", "图片"}:
        return "image"
    return "video" if Path(str(path)).suffix.lower() in VIDEO_SUFFIXES else "image"
