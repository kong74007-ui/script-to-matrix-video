#!/usr/bin/env python3
"""Validate deterministic duration, media mix, and BGM rotation for a template batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from render_video import (
    manifest_path,
    load_json_snapshot,
    required_font_families,
    resolve_font_files,
    resolve_fonts_dir,
    resolve_input,
    resolve_layout,
    resolve_template,
    save_json_if_unchanged,
)
from template_policy import infer_media_type, recommended_duration, required_media_count, resolve_emphasis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_manifest", type=Path, help="JSON containing a jobs or projects array")
    parser.add_argument("--fix-duration", action="store_true", help="Extend short manifests to the calculated duration")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def resolve_relative(root: Path, value: str) -> Path:
    candidate = manifest_path(value, "batch project path")
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()


def file_identity(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def normalize_jobs(batch: dict[str, Any], manifest_path: Path) -> list[dict[str, Any]]:
    raw_jobs = batch.get("jobs")
    if raw_jobs is None:
        raw_jobs = batch.get("projects")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise RuntimeError("Batch manifest must contain a non-empty jobs or projects array")
    jobs: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_jobs, start=1):
        if isinstance(raw, str):
            job = {"project": raw}
        elif isinstance(raw, dict):
            job = dict(raw)
        else:
            raise RuntimeError(f"Batch job {index} must be a path string or object")
        project_value = str(job.get("project") or job.get("manifest") or "")
        if not project_value:
            raise RuntimeError(f"Batch job {index} has no project path")
        job["_index"] = index
        project_path = resolve_relative(manifest_path.parent, project_value)
        try:
            project_path.relative_to(manifest_path.parent.resolve())
        except ValueError as exc:
            raise RuntimeError(f"Batch project path must stay inside the batch folder: {project_path}") from exc
        job["_project_path"] = project_path
        jobs.append(job)
    return jobs


def collect_media(project: dict[str, Any], project_path: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for scene_index, scene in enumerate(project.get("scenes") or [], start=1):
        values = scene.get("media") or scene.get("images") or []
        for value in values:
            if isinstance(value, dict):
                raw_path = str(value.get("path") or "")
                record_id = str(value.get("record_id") or "")
                explicit = str(value.get("type") or "")
            else:
                raw_path = str(value)
                record_id = ""
                explicit = ""
            resolved = resolve_input(project_path.parent, raw_path, f"scene {scene_index} media")
            identity = f"record:{record_id}" if record_id else file_identity(resolved)
            results.append({"identity": identity, "type": infer_media_type(raw_path, explicit), "path": raw_path})
    return results


def bgm_identity(project: dict[str, Any], project_path: Path) -> str | None:
    bgm = project.get("bgm")
    if bgm in (None, False):
        return None
    if bgm is True:
        raise RuntimeError("BGM is enabled but has no local path")
    if not isinstance(bgm, dict):
        raise RuntimeError("bgm must be an object")
    enabled = bgm.get("enabled", bool(bgm.get("path") or bgm.get("local_path")))
    if enabled is False or str(enabled).strip().lower() in {"false", "off", "no", "0"}:
        return None
    raw_path = str(bgm.get("path") or bgm.get("local_path") or "").strip()
    if not raw_path:
        raise RuntimeError("BGM is enabled but has no local path")
    resolved = resolve_input(project_path.parent, raw_path, "BGM")
    record_id = str(bgm.get("record_id") or "")
    if record_id:
        return f"record:{record_id}"
    return file_identity(resolved)


def main() -> int:
    args = parse_args()
    manifest_path = args.batch_manifest.resolve()
    batch = load_json(manifest_path)
    jobs = normalize_jobs(batch, manifest_path)
    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[dict[str, Any]] = []
    variant_media: dict[str, list[tuple[str, frozenset[str], str]]] = {}
    bgm_sequence: list[tuple[str, str]] = []

    for job in jobs:
        project_path: Path = job["_project_path"]
        label = str(job.get("job_id") or project_path.stem or f"job-{job['_index']}")
        try:
            source_project, source_sha256 = load_json_snapshot(project_path)
            project, template_id = resolve_template(source_project)
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        layout = project.get("layout") or {}
        if str(layout.get("preset") or "") != "text-media-text":
            errors.append(f"{label}: layout.preset must be text-media-text")
            continue
        scenes = project.get("scenes")
        if not isinstance(scenes, list) or not scenes or any(not isinstance(scene, dict) for scene in scenes):
            errors.append(f"{label}: project must contain a non-empty array of scene objects")
            continue
        emphasis, emphasis_warnings = resolve_emphasis(project, scenes)
        warnings.extend(f"{label}: {warning}" for warning in emphasis_warnings)

        target = recommended_duration(scenes)
        try:
            durations = [float(scene.get("duration") or 0) for scene in scenes]
        except (TypeError, ValueError) as exc:
            errors.append(f"{label}: scene duration must be numeric: {exc}")
            continue
        if any(not math.isfinite(duration) or duration < 0 for duration in durations):
            errors.append(f"{label}: scene durations must be finite non-negative numbers")
            continue
        current = sum(durations)
        fixed = False
        if current + 0.001 < target:
            if args.fix_duration:
                scenes[-1]["duration"] = round(float(scenes[-1].get("duration") or 0) + target - current, 3)
                source_sha256 = save_json_if_unchanged(project_path, source_project, source_sha256)
                current = target
                fixed = True
                warnings.append(f"{label}: duration extended to {target:.1f}s")
            else:
                errors.append(
                    f"{label}: duration {current:.1f}s is below the copy-based target {target:.1f}s; rerun with --fix-duration"
                )

        render = project.get("render") or {}
        if not isinstance(render, dict):
            errors.append(f"{label}: render must be an object")
            continue
        try:
            fonts_dir = resolve_fonts_dir(project_path.parent, render)
            canvas = project.get("canvas") or {}
            resolved_layout = resolve_layout(
                project, int(canvas.get("width", 1080)), int(canvas.get("height", 1920)), []
            )
            font_files = resolve_font_files(fonts_dir, required_font_families(render, resolved_layout))
            media = collect_media(project, project_path)
            bgm_id = bgm_identity(project, project_path)
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        identities = frozenset(item["identity"] for item in media)
        required = required_media_count(max(current, target))
        if len(identities) < required:
            errors.append(
                f"{label}: needs at least {required} distinct media assets for {max(current, target):.1f}s; found {len(identities)}"
            )
        video_count = len({item["identity"] for item in media if item["type"] == "video"})
        policy = project.get("material_policy") or {}
        allow_image_only = bool(policy.get("allow_image_only")) and bool(str(policy.get("image_only_reason") or "").strip())
        if video_count == 0:
            if allow_image_only:
                warnings.append(f"{label}: image-only fallback recorded: {policy['image_only_reason']}")
            else:
                errors.append(
                    f"{label}: image-only output is not allowed by default; search approved video records first or record an explicit fallback reason"
                )

        copy_id = str(job.get("copy_id") or project.get("copy_id") or "")
        variant_id = str(job.get("variant_id") or project.get("variant_id") or label)
        if copy_id:
            variant_media.setdefault(copy_id, []).append((variant_id, identities, label))

        if bgm_id:
            bgm_sequence.append((label, bgm_id))
        summaries.append(
            {
                "job": label,
                "project": str(project_path),
                "template_id": template_id,
                "fonts_dir": str(fonts_dir),
                "font_files": [path.name for path in font_files],
                "duration": round(current, 3),
                "copy_target_duration": target,
                "duration_fixed": fixed,
                "distinct_media": len(identities),
                "required_media": required,
                "video_media": video_count,
                "bgm_identity": bgm_id,
                "emphasis": {
                    "provider": emphasis["provider"],
                    "input_valid": emphasis["input_valid"],
                    "top_count": len(emphasis["top"]),
                    "bottom_count": len(emphasis["bottom"]),
                },
            }
        )

    for copy_id, variants in variant_media.items():
        seen: dict[frozenset[str], str] = {}
        for variant_id, identities, label in variants:
            if identities in seen:
                errors.append(
                    f"{label}: copy {copy_id} variant {variant_id} duplicates the full media set used by {seen[identities]}"
                )
            else:
                seen[identities] = label

    bgm_policy = batch.get("bgm_policy") or {}
    if 0 < len(bgm_sequence) < len(summaries) and not bool(bgm_policy.get("allow_mixed_enabled")):
        errors.append(
            f"batch: BGM is enabled on {len(bgm_sequence)} of {len(summaries)} validated outputs; "
            "use one batch-wide preference or set bgm_policy.allow_mixed_enabled=true with an intentional plan"
        )
    if len(bgm_sequence) >= 2:
        required_bgm = 2 if len(bgm_sequence) < 4 else 3
        unique_bgm = {identity for _, identity in bgm_sequence}
        if len(unique_bgm) < required_bgm:
            errors.append(
                f"batch: {len(bgm_sequence)} BGM-enabled outputs require at least {required_bgm} distinct BGM tracks; found {len(unique_bgm)}"
            )
        for current_item, previous_item in zip(bgm_sequence[1:], bgm_sequence):
            if current_item[1] == previous_item[1]:
                errors.append(
                    f"batch: consecutive jobs {previous_item[0]} and {current_item[0]} reuse the same BGM; rotate the approved BGM pool"
                )

    report = {
        "ok": not errors,
        "batch_manifest": str(manifest_path),
        "job_count": len(jobs),
        "validated_count": len(summaries),
        "distinct_bgm": len({identity for _, identity in bgm_sequence}),
        "errors": errors,
        "warnings": warnings,
        "jobs": summaries,
    }
    if args.report:
        save_json(args.report.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
