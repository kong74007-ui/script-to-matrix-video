#!/usr/bin/env python3
"""Deterministic policy helpers for text-media-text template videos."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


MIN_DURATION_SECONDS = 8.0
NORMAL_MAX_DURATION_SECONDS = 15.0
READING_UNITS_PER_SECOND = 5.0
READING_TAIL_SECONDS = 1.5
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
EMPHASIS_SCHEMA_VERSION = "emphasis.v1"
EMPHASIS_ROLES = frozenset({"number", "contrast", "pain", "benefit", "conclusion", "cta"})
EMPHASIS_MIN_CONFIDENCE = 0.6
EMPHASIS_MAX_PER_REGION = 3


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


def emphasis_copy(scenes: list[dict[str, Any]]) -> tuple[str, str]:
    """Return the first persistent top/bottom copy pair used by emphasis.v1."""

    for scene in scenes:
        top = str(scene.get("top_text") or "")
        bottom = str(scene.get("bottom_text") or "")
        if top or bottom:
            return top, bottom
    return "", ""


def emphasis_source_hash(top_text: str, bottom_text: str) -> str:
    """Hash the exact persistent copy without normalizing or rewriting it."""

    payload = json.dumps(
        {"bottom": bottom_text, "top": top_text},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _select_emphasis_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for span in sorted(spans, key=lambda item: (item["priority"], -item["confidence"], item["start"])):
        if any(span["start"] < kept["end"] and kept["start"] < span["end"] for kept in selected):
            continue
        selected.append(span)
        if len(selected) == EMPHASIS_MAX_PER_REGION:
            break
    return sorted(selected, key=lambda item: item["start"])


def resolve_emphasis(
    project: dict[str, Any], scenes: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    """Validate emphasis.v1 and silently drop unsafe spans with audit warnings."""

    top_text, bottom_text = emphasis_copy(scenes)
    expected_hash = emphasis_source_hash(top_text, bottom_text)
    resolved: dict[str, Any] = {
        "schema_version": EMPHASIS_SCHEMA_VERSION,
        "provider": "rules",
        "source_hash": expected_hash,
        "prompt_version": "fallback-v1",
        "input_present": project.get("emphasis") is not None,
        "input_valid": False,
        "region_valid": {"top": False, "bottom": False},
        "top_text": top_text,
        "bottom_text": bottom_text,
        "top": [],
        "bottom": [],
    }
    raw = project.get("emphasis")
    if raw is None:
        return resolved, []
    if not isinstance(raw, dict):
        return resolved, ["emphasis must be an object; used deterministic fallback"]

    warnings: list[str] = []
    provider = str(raw.get("provider") or "").strip()
    prompt_version = str(raw.get("prompt_version") or "").strip()
    metadata_valid = True
    if raw.get("schema_version") != EMPHASIS_SCHEMA_VERSION:
        warnings.append(f"emphasis.schema_version must be {EMPHASIS_SCHEMA_VERSION}; used deterministic fallback")
        metadata_valid = False
    if str(raw.get("source_hash") or "") != expected_hash:
        warnings.append("emphasis.source_hash does not match the exact top/bottom copy; used deterministic fallback")
        metadata_valid = False
    if not provider or len(provider) > 64:
        warnings.append("emphasis.provider must contain 1-64 characters; used deterministic fallback")
        metadata_valid = False
    if not prompt_version or len(prompt_version) > 64:
        warnings.append("emphasis.prompt_version must contain 1-64 characters; used deterministic fallback")
        metadata_valid = False
    if not metadata_valid:
        return resolved, warnings

    resolved.update({"provider": provider, "prompt_version": prompt_version, "input_valid": True})
    for region, source_text in (("top", top_text), ("bottom", bottom_text)):
        raw_spans = raw.get(region, [])
        if not isinstance(raw_spans, list):
            warnings.append(f"emphasis.{region} must be an array; ignored")
            continue
        resolved["region_valid"][region] = True
        candidates: list[dict[str, Any]] = []
        for index, item in enumerate(raw_spans):
            label = f"emphasis.{region}[{index}]"
            if not isinstance(item, dict):
                warnings.append(f"{label} must be an object; ignored")
                continue
            start, end = item.get("start"), item.get("end")
            priority = item.get("priority", 1)
            confidence_value = item.get("confidence", 0)
            if (
                type(start) is not int
                or type(end) is not int
                or type(priority) is not int
                or isinstance(confidence_value, bool)
                or not isinstance(confidence_value, (int, float))
            ):
                warnings.append(f"{label} has invalid numeric fields; ignored")
                continue
            confidence = float(confidence_value)
            text = str(item.get("text") or "")
            role = str(item.get("role") or "").strip().lower()
            if (
                start < 0
                or end <= start
                or end > len(source_text)
                or source_text[start:end] != text
            ):
                warnings.append(f"{label} does not exactly match its source offsets; ignored")
                continue
            if role not in EMPHASIS_ROLES:
                warnings.append(f"{label}.role is unsupported; ignored")
                continue
            if priority < 1 or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                warnings.append(f"{label} priority/confidence is invalid; ignored")
                continue
            if confidence < EMPHASIS_MIN_CONFIDENCE:
                warnings.append(f"{label} confidence is below {EMPHASIS_MIN_CONFIDENCE:.1f}; ignored")
                continue
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                    "role": role,
                    "priority": priority,
                    "confidence": confidence,
                }
            )
        selected = _select_emphasis_spans(candidates)
        if len(selected) < len(candidates):
            warnings.append(
                f"emphasis.{region} dropped overlapping or excess spans; kept {len(selected)} of {len(candidates)}"
            )
        resolved[region] = selected
    return resolved, warnings


def fallback_emphasis(text: str, region: str) -> list[dict[str, Any]]:
    """Return conservative deterministic spans when no valid semantic result exists."""

    candidates: list[dict[str, Any]] = []

    def add(match: re.Match[str], role: str, priority: int) -> None:
        candidates.append(
            {
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
                "role": role,
                "priority": priority,
                "confidence": 1.0,
            }
        )

    patterns = (
        (r"(?:19|20)\d{2}(?:[年/-]\d{1,2})?(?:[月/-]\d{1,2}日?)?", "number", 1),
        (r"(?:[¥￥$])?\d+(?:[.,]\d+)*(?:%|元|万|亿|岁|天|小时|分钟|秒)?", "number", 1),
        (r"[“\"「『][^”\"」』\n]{1,10}[”\"」』]", "conclusion", 2),
    )
    for pattern, role, priority in patterns:
        for match in re.finditer(pattern, text):
            add(match, role, priority)
    for match in re.finditer(r"(?:而是|但是|却|反而)[^，。！？\n]{1,10}", text):
        add(match, "contrast", 2)
    if region == "bottom":
        for match in re.finditer(r"(?:评论|私信|关注|收藏|保存|分享|点击|立即|现在)[^，。！？\n]{0,8}", text):
            add(match, "cta", 1)
        if "：" in text:
            tail_start = text.rfind("：") + 1
            tail = text[tail_start:].strip("。！!？? ，,")
            if 1 <= len(tail) <= 8:
                start = text.find(tail, tail_start)
                candidates.append(
                    {
                        "start": start,
                        "end": start + len(tail),
                        "text": tail,
                        "role": "cta",
                        "priority": 1,
                        "confidence": 1.0,
                    }
                )
    return _select_emphasis_spans(candidates)
