#!/usr/bin/env python3
"""Render the bundled 17-style reference typography pack with HyperFrames.

This wrapper keeps user media outside the Skill directory. It copies the immutable
template pack into a task-owned work directory, stages two distinct approved video
assets per row, prepares the HyperFrames batch variables, and renders the MP4s.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = SKILL_ROOT / "assets" / "templates" / "reference-typography-17"
PACK_MANIFEST = PACK_ROOT / "manifest.json"
FONT_ROOT = SKILL_ROOT / "assets" / "fonts"
FONT_FILES = (
    "NotoSansSC-Variable.ttf",
    "MaShanZheng-Regular.ttf",
    "ZCOOLKuaiLe-Regular.ttf",
    "ZCOOLXiaoWei-Regular.ttf",
)
NAME_RE = re.compile(r"[^0-9A-Za-z_-]+")


class InputError(ValueError):
    pass


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"Invalid JSON in {path}: {exc}") from exc


def resolve_input(value: object, base: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} is required and must be a local file path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise InputError(f"{field} does not exist: {path}")
    return path


def safe_name(value: object, index: int) -> str:
    raw = str(value or f"video-{index:02d}").strip()
    cleaned = NAME_RE.sub("-", raw).strip("-_")
    return cleaned or f"video-{index:02d}"


def stage_file(source: Path, directory: Path, stem: str) -> str:
    suffix = source.suffix.lower() or ".bin"
    target = directory / f"{stem}{suffix}"
    shutil.copy2(source, target)
    return target.relative_to(directory.parents[1]).as_posix()


def validate_bgm_rotation(rows: list[dict[str, object]], base: Path) -> None:
    bgm_paths: list[Path] = []
    for index, row in enumerate(rows, 1):
        value = row.get("bgm")
        if value in (None, ""):
            continue
        bgm_paths.append(resolve_input(value, base, f"row {index} bgm"))

    if len(bgm_paths) < 2:
        return
    for previous, current in zip(bgm_paths, bgm_paths[1:]):
        if previous == current:
            raise InputError("Consecutive BGM reuse is not allowed in a batch")
    required = 2 if len(bgm_paths) <= 3 else 3
    if len(set(bgm_paths)) < required:
        raise InputError(
            f"A {len(bgm_paths)}-row BGM-enabled batch requires at least {required} distinct tracks"
        )


def resolve_browser_environment(npx: str, workdir: Path) -> dict[str, str]:
    env = os.environ.copy()
    if os.name != "nt" or env.get("HYPERFRAMES_BROWSER_PATH"):
        return env
    try:
        result = subprocess.run(
            [npx, "--yes", "hyperframes@0.8.16", "browser", "path"],
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        bundled = Path(result.stdout.strip()) if result.returncode == 0 else None
        if bundled and bundled.is_file():
            probe = subprocess.run(
                [str(bundled), "--version"],
                check=False,
                capture_output=True,
                timeout=10,
            )
            if probe.returncode == 0:
                return env
    except (OSError, subprocess.SubprocessError):
        pass

    candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    )
    fallback = next((path for path in candidates if path.is_file()), None)
    if fallback:
        env["HYPERFRAMES_BROWSER_PATH"] = str(fallback)
        print(
            json.dumps(
                {
                    "warning": "Bundled HyperFrames Chrome could not start; using an installed Chromium browser for this run",
                    "browser": str(fallback),
                },
                ensure_ascii=False,
            )
        )
    return env


def prepare(args: argparse.Namespace) -> tuple[Path, Path, list[dict[str, object]]]:
    batch_path = Path(args.batch).expanduser().resolve()
    payload = load_json(batch_path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("rows", payload.get("jobs"))
    else:
        rows = None
    if not isinstance(rows, list) or not rows:
        raise InputError("Batch JSON must contain a non-empty rows or jobs array")
    if not all(isinstance(row, dict) for row in rows):
        raise InputError("Every batch row must be an object")

    pack = load_json(PACK_MANIFEST)
    templates = {
        item["id"]: item["variant"]
        for item in pack["templates"]
        if isinstance(item, dict) and "id" in item and "variant" in item
    }
    validate_bgm_rotation(rows, batch_path.parent)

    workdir = (
        Path(args.workdir).expanduser().resolve()
        if args.workdir
        else batch_path.parent / "reference-typography-hyperframes"
    )
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else workdir / "renders-delivery"
    )
    workdir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PACK_ROOT, workdir, dirs_exist_ok=True)

    fonts_dir = workdir / "assets" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for filename in FONT_FILES:
        source = FONT_ROOT / filename
        if not source.is_file():
            raise InputError(f"Bundled font is missing: {source}")
        shutil.copy2(source, fonts_dir / filename)

    input_dir = workdir / "assets" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    silence = "assets/bgm/silence.m4a"
    prepared: list[dict[str, object]] = []
    used_names: set[str] = set()

    for index, row in enumerate(rows, 1):
        template_id = row.get("template_id")
        if template_id not in templates:
            raise InputError(f"row {index} has unknown reference template_id: {template_id}")

        name = safe_name(row.get("name"), index)
        if name in used_names:
            raise InputError(f"Duplicate output name after sanitizing: {name}")
        used_names.add(name)

        top_values = [str(row.get(key, "")).strip() for key in ("top1", "top2", "top3")]
        bottom_values = [str(row.get(key, "")).strip() for key in ("bottom1", "bottom2")]
        if not any(top_values) or not any(bottom_values):
            raise InputError(f"row {index} requires at least one top and one bottom text layer")

        video_a = resolve_input(row.get("videoA"), batch_path.parent, f"row {index} videoA")
        video_b = resolve_input(row.get("videoB"), batch_path.parent, f"row {index} videoB")
        if video_a == video_b:
            raise InputError(f"row {index} must use two distinct video assets")

        bgm_value = row.get("bgm")
        if bgm_value in (None, ""):
            bgm = silence
        else:
            bgm_source = resolve_input(bgm_value, batch_path.parent, f"row {index} bgm")
            bgm = stage_file(bgm_source, input_dir, f"{index:02d}-bgm")

        prepared.append(
            {
                "name": name,
                "variant": templates[str(template_id)],
                "top1": top_values[0],
                "top2": top_values[1],
                "top3": top_values[2],
                "bottom1": bottom_values[0],
                "bottom2": bottom_values[1],
                "videoA": stage_file(video_a, input_dir, f"{index:02d}-a"),
                "videoB": stage_file(video_b, input_dir, f"{index:02d}-b"),
                "bgm": bgm,
            }
        )

    batch_dir = workdir / "batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = batch_dir / "prepared-rows.json"
    prepared_path.write_text(
        json.dumps({"rows": prepared}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return workdir, output_dir, prepared


def render(args: argparse.Namespace) -> int:
    workdir, output_dir, rows = prepare(args)
    summary = {
        "status": "prepared" if args.dry_run else "rendering",
        "engine": "hyperframes",
        "template_pack": "reference-typography-17",
        "jobs": len(rows),
        "workdir": str(workdir),
        "output_dir": str(output_dir),
        "prepared_batch": str(workdir / "batch" / "prepared-rows.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    npx = shutil.which("npx")
    if not npx:
        raise InputError("Node.js/npm is required for the reference typography templates")

    output_pattern = (output_dir / "{name}.mp4").as_posix()
    command = [
        npx,
        "--yes",
        "hyperframes@0.8.16",
        "render",
        "--batch",
        "batch/prepared-rows.json",
        "--output",
        output_pattern,
        "--batch-concurrency",
        str(args.batch_concurrency),
        "--workers",
        str(args.workers),
        "--strict-variables",
        "--quality",
        args.quality,
        "--fps",
        "30",
        "--sdr",
        "--json",
    ]
    completed = subprocess.run(
        command,
        cwd=workdir,
        env=resolve_browser_environment(npx, workdir),
        check=False,
    )
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the 17 bundled reference typography templates"
    )
    parser.add_argument("batch", help="JSON file with a rows or jobs array")
    parser.add_argument("--workdir", help="Task-owned HyperFrames project directory")
    parser.add_argument("--output-dir", help="Final MP4 output directory")
    parser.add_argument("--quality", choices=("draft", "standard", "high"), default="high")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-concurrency", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", help="Prepare and validate without rendering")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.workers < 1 or args.batch_concurrency < 1:
        parser.error("worker counts must be positive")
    try:
        return render(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
