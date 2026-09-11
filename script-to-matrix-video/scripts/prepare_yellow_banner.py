#!/usr/bin/env python3
"""Prepare a local yellow-banner-zoom project without rendering.

Task JSON has exactly three ``media`` video records and optional title,
subtitle1, subtitle2, sourceLabel, body and cta replacements. User records have
source="user"; approved library records have status="可使用" and record_id.
Optional source_start selects the source in-point in seconds. Relative paths
resolve beside the task JSON. Three distinct source files are required.

The reference timing stays at 1080x1920, 30fps, 302 frames, with 86/97/119-frame
media slots. The template-bound BGM is validated and copied byte-for-byte;
task BGM overrides are unsupported. Short inputs are rejected without looping
or padding. Verified color conversion is shared with triple-strip-shutter.
Existing output directories are never overwritten. Failed preparation remains
on disk for diagnosis and must be retried using a new output directory.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

from prepare_triple_strip import color_conversion, require_hlg_filter
from prepare_triple_strip import local_file, media_info, run, sha256


TEMPLATE_ID = "yellow-banner-zoom"
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "assets/templates" / TEMPLATE_ID
FPS = 30
FRAMES = 302
DURATION = FRAMES / FPS
MEDIA_FRAMES = (86, 97, 119)
CUT_FRAMES = (86, 183)
TEXT_LIMITS = {"title": 12, "subtitle1": 16, "subtitle2": 16,
               "sourceLabel": 8, "body": 90, "cta": 24}
OPTIONAL_TEXT = frozenset(("subtitle2", "sourceLabel", "cta"))
BASE_FILES = ("index.html", "template.json", "package.json", "hyperframes.json", "gpu_runtime.py")
OPTIONAL_FILES = ("index.motion.json", "meta.json", "frame.md")
MEDIA_PATHS = {f"media{index}": f"assets/media/{index:02}.mp4" for index in range(1, 4)}
VIDEO_SUFFIXES = frozenset((".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".mts", ".m2ts", ".mpeg", ".mpg"))


def variable_schema(source):
    match = re.search(r'data-composition-variables=(["\'])(.*?)\1', source, re.S)
    if not match:
        raise ValueError("Template is missing its text variable schema")
    schema = json.loads(html.unescape(match.group(2)))
    if (not isinstance(schema, list) or any(not isinstance(item, dict) or
            not isinstance(item.get("id"), str) for item in schema)):
        raise ValueError("Template variable schema must be an array of declarations")
    ids = [item["id"] for item in schema]
    if len(ids) != len(set(ids)) or not set(TEXT_LIMITS).issubset(ids):
        raise ValueError("Template must declare each of its six text variables exactly once")
    if "bgm" in ids or "boundBgm" in ids:
        raise ValueError("Bound BGM must not be an editable template variable")
    return match, schema


def text_values(job, source):
    _, schema = variable_schema(source)
    defaults = {item["id"]: item.get("default") for item in schema}
    values = {}
    for key, maximum in TEXT_LIMITS.items():
        value = job.get(key, defaults.get(key))
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        minimum = 0 if key in OPTIONAL_TEXT else 1
        printable_length = len(value.replace("\n", "")) if key == "body" else len(value)
        controls = any((ord(character) < 32 or 127 <= ord(character) <= 159)
                       and not (key == "body" and character == "\n") for character in value)
        if (printable_length > maximum or (minimum and not value.strip()) or controls
                or (key == "body" and value.count("\n") > 3)):
            line_rule = "with at most three LF line breaks" if key == "body" else "without line breaks"
            raise ValueError(f"{key} requires {minimum}–{maximum} characters {line_rule}; control characters are unsupported")
        values[key] = value
    return values


def update_html(source, values):
    match, schema = variable_schema(source)
    for item in schema:
        if item["id"] in values:
            item["default"] = values[item["id"]]
    replacement = 'data-composition-variables="' + html.escape(
        json.dumps(schema, ensure_ascii=False), quote=True) + '"'
    source = source[:match.start()] + replacement + source[match.end():]
    for key, value in values.items():
        pattern = (rf'(<(?P<tag>[A-Za-z][\w:-]*)\b[^>]*(?<![\w-])data-var-text='
                   rf'(?P<quote>["\']){key}(?P=quote)[^>]*>).*?(</(?P=tag)\s*>)')
        source, count = re.subn(pattern, lambda item: item[1] + html.escape(value) + item[4],
                                source, flags=re.S)
        if count != 1:
            raise ValueError(f"Expected one static {key} text binding in index.html")
    return source


def validate_metadata(metadata):
    if not isinstance(metadata, dict) or metadata.get("id") != TEMPLATE_ID:
        raise ValueError(f"Expected the {TEMPLATE_ID} template")
    for key, expected in (("width", 1080), ("height", 1920), ("fps", FPS), ("frames", FRAMES)):
        actual = metadata.get(key)
        if isinstance(actual, bool) or actual != expected:
            raise ValueError(f"Template {key} must remain {expected}")
    duration = metadata.get("duration")
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(duration) or abs(duration - DURATION) > 1e-6):
        raise ValueError(f"Template duration must remain {FRAMES}/{FPS} seconds")


def template_files(template):
    """Copy runtime dependencies, never bundled demonstration/private videos."""
    files = list(BASE_FILES)
    files.extend(name for name in OPTIONAL_FILES if (template / name).is_file())
    for folder in ("compositions", "assets"):
        directory = template / folder
        if not directory.is_dir():
            raise ValueError(f"Template dependency is missing: {folder}")
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() not in VIDEO_SUFFIXES:
                relative = path.relative_to(template)
                if relative.parts[:2] != ("assets", "media"):
                    files.append(relative.as_posix())
    for name in files:
        try:
            path = (template / name).resolve(strict=True)
        except OSError as error:
            raise ValueError(f"Template dependency is missing: {name}") from error
        if not path.is_relative_to(template) or not path.is_file():
            raise ValueError(f"Template dependency must be a file inside the template: {name}")
    return sorted(set(files))


def validate_fixed_media(template, files, audio_path):
    documents = "\n".join((template / name).read_text(encoding="utf-8-sig")
                          for name in files if name.endswith(".html"))
    for relative in MEDIA_PATHS.values():
        if not re.search(r'<video\b[^>]*(?<![\w-])src=(["\'])' + re.escape(relative) + r'\1', documents):
            raise ValueError(f"Template is missing its fixed video src: {relative}")
    if not re.search(r'<audio\b[^>]*(?<![\w-])src=(["\'])' + re.escape(audio_path) + r'\1', documents):
        raise ValueError("Template is missing the fixed bound BGM audio src")
    if re.search(r'<audio\b[^>]*\bdata-var-src=', documents):
        raise ValueError("Bound BGM must not have an editable data-var-src binding")


def bound_audio(template, metadata, job, ffprobe):
    if "bgm" in job or "boundBgm" in job:
        raise ValueError("BGM is template-bound; omit task.bgm and task.boundBgm")
    binding = metadata.get("boundBgm")
    if not isinstance(binding, dict):
        raise ValueError("Template boundBgm metadata is missing")
    raw = binding.get("path")
    if not isinstance(raw, str) or not raw.strip() or re.match(r"\w+://", raw):
        raise ValueError("Bound BGM path must be a relative file inside the template")
    relative = Path(raw)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError("Bound BGM path must stay inside the template")
    try:
        path = (template / relative).resolve(strict=True)
        if not path.is_relative_to(template) or not path.is_file():
            raise ValueError("Bound BGM path must be a file inside the template")
    except OSError as error:
        raise ValueError("Bound BGM file is missing or unreadable") from error
    expected_hash = binding.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        raise ValueError("Bound BGM metadata requires a valid SHA256")
    actual_hash = sha256(path)
    if actual_hash != expected_hash.lower():
        raise ValueError("Bound BGM hash mismatch; restore this template's original track")
    expected_duration = binding.get("duration")
    if (isinstance(expected_duration, bool) or not isinstance(expected_duration, (int, float))
            or not math.isfinite(expected_duration) or abs(expected_duration - DURATION) > 0.1):
        raise ValueError("Bound BGM metadata duration must be within 0.1s of the reference timeline")
    if (isinstance(binding.get("start"), bool) or binding.get("start") != 0
            or isinstance(binding.get("volume"), bool) or binding.get("volume") != 1):
        raise ValueError("Bound BGM must retain start=0 and volume=1")
    probe = media_info(path, "audio", expected_duration, ffprobe)
    if abs(probe["duration"] - expected_duration) > 0.002:
        raise ValueError("Bound BGM audio duration must match its binding within 0.002s")
    return {"source": "template-bound", "template_id": TEMPLATE_ID,
            "template_path": relative.as_posix(), "path": str(path), "sha256": actual_hash,
            "duration": expected_duration, "probe": probe, "start": 0, "volume": 1}


def record(value, minimum, base, ffprobe):
    if not isinstance(value, dict):
        raise ValueError("Every media entry must be a video record object")
    user = value.get("source") == "user"
    if not user and (value.get("source") not in (None, "library") or value.get("status") != "可使用"
                     or not isinstance(value.get("record_id"), str) or not value["record_id"].strip()):
        raise ValueError("Video must be user supplied or have status=可使用 and record_id; AI assets are not allowed")
    source_start = value.get("source_start", 0)
    if (isinstance(source_start, bool) or not isinstance(source_start, (int, float))
            or not math.isfinite(source_start) or source_start < 0):
        raise ValueError("Video source_start must be a finite nonnegative number of seconds")
    path = local_file(value.get("path"), base)
    probe = media_info(path, "video", source_start + minimum, ffprobe)
    return {"path": str(path), "source": "user" if user else "library",
            "status": "user-supplied" if user else "可使用", "record_id": None if user else value["record_id"],
            "sha256": sha256(path), "probe": probe, "source_start": source_start,
            "source_window": {"in": source_start, "out": source_start + minimum},
            "color_conversion": color_conversion(probe)}


def prepare(args):
    task_path = Path(args.task).resolve(strict=True)
    job = json.loads(task_path.read_text(encoding="utf-8-sig"))
    if not isinstance(job, dict):
        raise ValueError("Task JSON must be an object")
    if not isinstance(job.get("media"), list) or len(job["media"]) != 3:
        raise ValueError("media must contain exactly three video records")
    template = Path(args.template_dir).resolve(strict=True)
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    if output.is_relative_to(template):
        raise ValueError("Output must be outside the reusable template directory")
    metadata = json.loads((template / "template.json").read_text(encoding="utf-8-sig"))
    validate_metadata(metadata)
    source = (template / "index.html").read_text(encoding="utf-8-sig")
    variables = text_values(job, source)
    authored = update_html(source, variables)
    ffmpeg, ffprobe = shutil.which(args.ffmpeg), shutil.which(args.ffprobe)
    if not ffmpeg or not ffprobe:
        raise ValueError("Provide valid --ffmpeg and --ffprobe executables or add them to PATH")
    audio = bound_audio(template, metadata, job, ffprobe)
    files = template_files(template)
    validate_fixed_media(template, files, audio["template_path"])
    media = [record(item, frames / FPS, task_path.parent, ffprobe)
             for item, frames in zip(job["media"], MEDIA_FRAMES)]
    if len({item["path"] for item in media}) != 3 or len({item["sha256"] for item in media}) != 3:
        raise ValueError("Media requires three distinct videos; duplicate paths or file contents detected")
    if any(item["color_conversion"].get("engine") == "libplacebo" for item in media):
        require_hlg_filter(ffmpeg)
    output.mkdir(parents=True, exist_ok=False)  # Validate every input before creating output.
    for name in files:
        if name == audio["template_path"]:
            continue
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template / name, target)
    (output / "index.html").write_text(authored, encoding="utf-8")

    def encode(entry):
        item, index, frames = entry
        relative = MEDIA_PATHS[f"media{index}"]
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-protocol_whitelist", "file,pipe",
             "-ss", str(item["source_start"]), "-i", item["path"], "-map", "0:v:0", "-an", "-filter_threads", "1", "-vf",
             item["color_conversion"]["filter"] + "," +
             f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={FPS}",
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-threads", "2", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-colorspace", "bt709", "-color_range", "tv", "-map_metadata", "-1",
             "-movflags", "+faststart", str(target)])
        derived = media_info(target, "video", frames / FPS, ffprobe)
        expected = {"codec": "h264", "pix_fmt": "yuv420p", "color_primaries": "bt709",
                    "color_transfer": "bt709", "color_space": "bt709", "color_range": "tv",
                    "width": 1080, "height": 1920}
        if any(derived.get(key) != value for key, value in expected.items()) or abs(derived["duration"] - frames / FPS) > 0.002:
            raise ValueError(f"Normalized video does not match its SDR dimensions/duration: {target}")
        return {**item, "slot": f"media{index}", "derived_path": relative, "frames": frames,
                "derived_sha256": sha256(target), "derived_probe": derived,
                "operation": "Verified Rec709 SDR conversion; center crop; 30fps; muted; "
                             f"source start={item['source_start']}s; no padding/looping"}

    entries = [(item, index, frames) for index, (item, frames) in enumerate(zip(media, MEDIA_FRAMES), 1)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        videos = list(pool.map(encode, entries))
    audio_target = output / audio["template_path"]
    audio_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(audio["path"], audio_target)
    derived_hash = sha256(audio_target)
    if derived_hash != audio["sha256"]:
        raise ValueError("Bound BGM changed during preparation; restore the original track and retry")
    audio.update(derived_path=audio["template_path"], derived_sha256=derived_hash,
                 operation="Byte-identical copy of the template-bound track; no re-encoding, padding, gain, fade or loop")
    for name, payload in (("variables.json", variables), ("provenance.json", {
            "template_id": TEMPLATE_ID, "width": 1080, "height": 1920,
            "duration": DURATION, "frames": FRAMES, "fps": FPS, "cut_frames": CUT_FRAMES,
            "created_at": datetime.now(timezone.utc).isoformat(), "videos": videos, "bgm": audio,
            "privacy": "Local source paths; review before sharing."})):
        (output / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared: {output}")


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, help="Task JSON with exactly three media video records")
    parser.add_argument("--output", required=True, help="New project output directory")
    parser.add_argument("--template-dir", default=str(DEFAULT_TEMPLATE), help="Installed reusable template directory")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable path or command name")
    parser.add_argument("--ffprobe", default="ffprobe", help="ffprobe executable path or command name")
    return parser


if __name__ == "__main__":
    try:
        prepare(argument_parser().parse_args())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        sys.exit(2)
