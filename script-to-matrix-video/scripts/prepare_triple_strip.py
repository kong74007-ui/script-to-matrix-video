#!/usr/bin/env python3
"""Prepare a local 17.6-second triple-strip-shutter project; never render.

Task JSON: opening=[3 distinct video records], main=[5 video records, at least
3 distinct sources]. Records use path plus source="user", or status="可使用"
and record_id. Optional source_start selects a nonnegative source in-point in
seconds. Optional title/subtitle/ctaLine1/ctaLine2 replace template defaults.
The template's bound BGM is copied byte-for-byte; no task BGM is needed.
Relative input paths resolve beside the task JSON. Existing outputs are rejected.
Short video, unverified color metadata and camera LOG are rejected; no looping,
black-frame padding or AI assets are used. Tagged HDR is converted to Rec709 SDR.
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

from prepare_nine_grid import color_conversion as validated_color_conversion
from prepare_nine_grid import local_file, media_info, run, sha256


TEMPLATE_ID = "triple-strip-shutter"
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "assets/templates" / TEMPLATE_ID
FPS = 30
DURATION = 17.6
OPENING_FRAMES = 117
MAIN_FRAMES = (82, 82, 82, 82, 83)
TEXT_LIMITS = {"title": 10, "subtitle": 18, "ctaLine1": 14, "ctaLine2": 14}
BASE_FILES = ("index.html", "template.json", "package.json", "hyperframes.json", "gpu_runtime.py")
OPTIONAL_FILES = ("index.motion.json", "meta.json", "frame.md")
MEDIA_PATHS = {f"{group}{index}": f"assets/{group}/{index:02}.mp4"
               for group, count in (("opening", 3), ("main", 5)) for index in range(1, count + 1)}
HLG_FILTER = ("libplacebo=colorspace=bt709:color_primaries=bt709:color_trc=bt709:"
              "range=tv:format=yuv420p:tonemapping=bt.2390:peak_detect=0")


def color_conversion(info):
    """Reuse input validation; only this template's HLG conversion is replaced."""
    conversion = validated_color_conversion(info)  # Validates/builds parameters; does not run a filter.
    if conversion["branch"] != "HLG-to-SDR":
        return conversion
    return {"branch": "HLG-to-SDR", "filter": HLG_FILTER,
            "engine": "libplacebo", "algorithm": "bt.2390", "peak_detect": False,
            "peak_mode": "metadata/defaults; dynamic peak detection disabled",
            "peak_source": "input HDR metadata or libplacebo defaults"}


def require_hlg_filter(ffmpeg):
    filters = run([ffmpeg, "-hide_banner", "-nostdin", "-filters"])
    if not re.search(r"(?m)^\s*\S+\s+libplacebo\s+", filters):
        raise ValueError("HLG-to-SDR requires the FFmpeg libplacebo filter; install a libplacebo-enabled "
                         "build or provide it with --ffmpeg. No fallback conversion is used.")


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
        raise ValueError("Template must declare each of its four text variables exactly once")
    if "bgm" in ids or "boundBgm" in ids:
        raise ValueError("Bound BGM must not be an editable template variable")
    return match, schema


def text_values(job, source):
    _, schema = variable_schema(source)
    defaults = {item["id"]: item.get("default") for item in schema}
    values = {}
    for key, maximum in TEXT_LIMITS.items():
        value = job.get(key, defaults.get(key))
        if (not isinstance(value, str) or not value.strip() or len(value) > maximum
                or any(ord(character) < 32 for character in value)):
            raise ValueError(f"{key} requires 1–{maximum} characters, without line breaks/control characters")
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


def template_files(template):
    files = list(BASE_FILES)
    files.extend(name for name in OPTIONAL_FILES if (template / name).is_file())
    for folder in ("compositions", "assets"):
        directory = template / folder
        if not directory.is_dir():
            raise ValueError(f"Template dependency is missing: {folder}")
        files.extend(path.relative_to(template).as_posix() for path in directory.rglob("*") if path.is_file())
    for name in files:
        path = (template / name).resolve(strict=True)
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


def bound_audio(template, metadata, job, job_base, ffprobe):
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
            or not math.isfinite(expected_duration) or expected_duration <= 0):
        raise ValueError("Bound BGM metadata requires a finite positive duration")
    probe = media_info(path, "audio", max(DURATION - 0.1, expected_duration - 0.1), ffprobe)
    if (probe["duration"] < DURATION - 0.1 - 1e-9
            or abs(probe["duration"] - expected_duration) > 0.1 + 1e-9):
        raise ValueError("Bound BGM must match its duration within 0.1s and be no more than 0.1s shorter than 17.6s")
    if "bgm" in job:
        conflict = "BGM is template-bound; omit task.bgm or supply a byte-identical copy of the bound track"
        try:
            legacy_hash = sha256(local_file(job["bgm"], job_base))
        except (ValueError, OSError) as error:
            raise ValueError(conflict) from error
        if legacy_hash != actual_hash:
            raise ValueError(conflict)
    return {"source": "template-bound", "template_id": TEMPLATE_ID,
            "template_path": relative.as_posix(), "path": str(path), "sha256": actual_hash,
            "duration": expected_duration, "probe": probe, "start": 0, "volume": 1}


def record(value, minimum, base, ffprobe):
    if not isinstance(value, dict):
        raise ValueError("Every opening/main entry must be a video record object")
    user = value.get("source") == "user"
    if not user and (value.get("status") != "可使用" or not isinstance(value.get("record_id"), str)
                     or not value["record_id"].strip()):
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
    for group, count in (("opening", 3), ("main", 5)):
        if not isinstance(job.get(group), list) or len(job[group]) != count:
            raise ValueError(f"{group} must contain exactly {count} video records")
    template = Path(args.template_dir).resolve(strict=True)
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    metadata = json.loads((template / "template.json").read_text(encoding="utf-8-sig"))
    if not isinstance(metadata, dict) or metadata.get("id") != TEMPLATE_ID:
        raise ValueError(f"Expected the {TEMPLATE_ID} template")
    source = (template / "index.html").read_text(encoding="utf-8-sig")
    variables = text_values(job, source)
    authored = update_html(source, variables)
    ffmpeg, ffprobe = shutil.which(args.ffmpeg), shutil.which(args.ffprobe)
    if not ffmpeg or not ffprobe:
        raise ValueError("Provide valid --ffmpeg and --ffprobe executables or add them to PATH")
    audio = bound_audio(template, metadata, job, task_path.parent, ffprobe)
    files = template_files(template)
    validate_fixed_media(template, files, audio["template_path"])
    opening = [record(item, OPENING_FRAMES / FPS, task_path.parent, ffprobe) for item in job["opening"]]
    if len({item["path"] for item in opening}) != 3 or len({item["sha256"] for item in opening}) != 3:
        raise ValueError("Opening requires three distinct videos; duplicate paths or file contents detected")
    mains = [record(item, frames / FPS, task_path.parent, ffprobe)
             for item, frames in zip(job["main"], MAIN_FRAMES)]
    if len({item["path"] for item in mains}) < 3 or len({item["sha256"] for item in mains}) < 3:
        raise ValueError("Main requires at least three distinct source videos")
    if any(item["color_conversion"].get("engine") == "libplacebo" for item in opening + mains):
        require_hlg_filter(ffmpeg)
    output.mkdir(parents=True, exist_ok=False)  # Validate all inputs before creating output.
    for name in files:
        if name == audio["template_path"]:
            continue
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template / name, target)
    (output / "index.html").write_text(authored, encoding="utf-8")

    def encode(entry):
        item, group, index, frames, height = entry
        relative = MEDIA_PATHS[f"{group}{index}"]
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe",
             "-ss", str(item["source_start"]), "-i", item["path"], "-map", "0:v:0", "-an", "-filter_threads", "1", "-vf",
             item["color_conversion"]["filter"] + "," +
             f"scale=1080:{height}:force_original_aspect_ratio=increase,crop=1080:{height},setsar=1,fps={FPS}",
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-threads", "2", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-colorspace", "bt709", "-color_range", "tv", "-map_metadata", "-1",
             "-movflags", "+faststart", str(target)])
        derived = media_info(target, "video", frames / FPS, ffprobe)
        expected = {"codec": "h264", "pix_fmt": "yuv420p", "color_primaries": "bt709",
                    "color_transfer": "bt709", "color_space": "bt709", "color_range": "tv",
                    "width": 1080, "height": height}
        if any(derived.get(key) != value for key, value in expected.items()) or abs(derived["duration"] - frames / FPS) > 0.002:
            raise ValueError(f"Normalized video does not match its SDR dimensions/duration: {target}")
        return {**item, "slot": f"{group}{index}", "derived_path": relative, "frames": frames,
                "derived_sha256": sha256(target), "derived_probe": derived,
                "operation": "Verified Rec709 SDR conversion; center crop; 30fps; muted; "
                             f"source start={item['source_start']}s; no padding/looping"}

    entries = [(item, "opening", index, OPENING_FRAMES, 640) for index, item in enumerate(opening, 1)]
    entries += [(item, "main", index, frames, 1920)
                for index, (item, frames) in enumerate(zip(mains, MAIN_FRAMES), 1)]
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
            "template_id": TEMPLATE_ID, "duration": DURATION, "frames": 528, "fps": FPS,
            "created_at": datetime.now(timezone.utc).isoformat(), "videos": videos, "bgm": audio,
            "privacy": "Local source paths; review before sharing."})):
        (output / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared: {output}")


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, help="Task JSON with three opening and five main video records")
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
