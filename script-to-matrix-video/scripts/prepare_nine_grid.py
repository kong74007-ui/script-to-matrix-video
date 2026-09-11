#!/usr/bin/env python3
"""Prepare a local, reusable 12-second nine-grid HyperFrames project; never render.

Job: {"title":"公司名称", "tagline":"品质｜细节｜诚信｜口碑",
      "grid":[{"path":"clip.mp4","source":"user"}, ... exactly 9],
      "main":[... exactly 3]}
Library records require status="可使用" and record_id instead of source="user".
The template's bound BGM is required and copied unchanged; do not supply a job BGM.
Legacy job BGM paths are accepted only when their bytes match the bound track.
Relative media paths resolve against the job JSON directory. Requires FFmpeg and
ffprobe on PATH. Output must not exist; failed preparation is retained for diagnosis.
Tagged HLG/PQ inputs are tone-mapped from linear floating-point light to Rec709
SDR before HyperFrames effects. Unknown/LOG color metadata is rejected: export
a verified Rec709 master first. HDR fallback peak is 1000 nits, recorded explicitly.
"""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from gpu_runtime import accelerate_ffmpeg

BASE_FILES = ("index.html", "template.json", "index.motion.json", "package.json",
              "hyperframes.json", "meta.json", "gpu_runtime.py")
ASSETS = ("fonts/NotoSerifSC-Variable.ttf", "fonts/NotoSansSC-Variable.ttf",
          "fonts/OFL-NotoSerifSC.txt", "fonts/OFL-NotoSansSC.txt", "vendor/gsap.min.js")
MAIN_SECONDS = (6.3, 4.7, 5.0)


def run(command):
    command = accelerate_ffmpeg(command)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=1200, **flags)
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} failed: {result.stderr[-1500:]}")
    return result.stdout


def local_file(value, base):
    if not isinstance(value, str) or not value.strip() or re.match(r"\w+://", value):
        raise ValueError("Media must be a non-empty local file path, not a URL")
    path = Path(value).expanduser()
    path = (base / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_info(path, kind, minimum, ffprobe):
    data = json.loads(run([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
                           "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = [s for s in data.get("streams", []) if s.get("codec_type") == kind
               and not s.get("disposition", {}).get("attached_pic")]
    if not streams:
        raise ValueError(f"Missing {kind} stream: {path}")
    stream = streams[0]
    raw = stream.get("duration")
    if raw in (None, "N/A") and len(data.get("streams", [])) == 1:
        raw = data.get("format", {}).get("duration")
    try:
        duration = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot verify {kind} stream duration: {path}") from None
    if not math.isfinite(duration) or duration + 0.002 < minimum:
        raise ValueError(f"{path.name}: {kind} must be at least {minimum}s (found {duration}s)")
    info = {"duration": duration, "codec": stream.get("codec_name"),
            "width": stream.get("width"), "height": stream.get("height")}
    if kind == "video":
        info.update({key: stream.get(key) for key in
                     ("pix_fmt", "color_primaries", "color_transfer", "color_space", "color_range")})
        peaks = []
        for side in stream.get("side_data_list", []):
            for key in ("max_content", "max_luminance"):
                try:
                    numerator, _, denominator = str(side.get(key, "")).partition("/")
                    number = float(numerator) / float(denominator or 1)
                    if math.isfinite(number) and 100 < number <= 10000:
                        peaks.append(number)
                except (ValueError, ZeroDivisionError):
                    pass
        info["hdr_peak_nits"] = max(peaks) if peaks else None
        tags = {**data.get("format", {}).get("tags", {}), **stream.get("tags", {})}
        info["camera_log_flag"] = any(re.search(r"(?i)(?:s-?log[23]|c-?log[23]?|v-?log|log-?c[34]?|apple.?log)",
                                                str(value)) for value in tags.values())
    return info


def bound_audio(template, job, job_base, ffprobe):
    """Resolve only the template's fixed audio, before any preparation writes."""
    metadata = json.loads((template / "template.json").read_text(encoding="utf-8-sig"))
    binding = metadata.get("bgm") if isinstance(metadata, dict) else None
    if not isinstance(binding, dict) or binding.get("mode") != "bound":
        raise ValueError("Bound BGM metadata is missing; restore this template's bundled audio binding")
    relative = binding.get("path")
    if not isinstance(relative, str) or not relative.strip() or re.match(r"\w+://", relative):
        raise ValueError("Bound BGM path must be a relative file inside the template")
    relative = Path(relative)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise ValueError("Bound BGM path must stay inside the template")
    try:
        path = (template / relative).resolve(strict=True)
        if not path.is_relative_to(template) or not path.is_file():
            raise ValueError("Bound BGM path must be a file inside the template")
    except OSError as error:
        raise ValueError("Bound BGM file is missing or unreadable; restore the template's original track") from error
    expected_hash = binding.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        raise ValueError("Bound BGM metadata requires a valid SHA256")
    actual_hash = sha256(path)
    if actual_hash != expected_hash.lower():
        raise ValueError("Bound BGM hash mismatch; restore the template's original track")
    duration = binding.get("duration")
    if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration != 12
            or binding.get("start") != 0 or binding.get("volume") != 1):
        raise ValueError("Bound BGM must retain its 12-second duration, start=0 and volume=1")
    try:
        probe = media_info(path, "audio", duration, ffprobe)
    except ValueError as error:
        raise ValueError(f"Bound BGM audio validation failed: {error}") from error
    if abs(probe["duration"] - duration) > 0.002:
        raise ValueError("Bound BGM audio duration does not match its 12-second binding")
    if "bgm" in job:
        conflict = "BGM is template-bound; omit job.bgm or supply only a byte-identical copy of the bound track"
        try:
            legacy = local_file(job["bgm"], job_base)
            legacy_hash = sha256(legacy)
        except (ValueError, OSError) as error:
            raise ValueError(conflict) from error
        if legacy_hash != actual_hash:
            raise ValueError(conflict)
    return {"source": "template-bound", "template_id": metadata.get("id"),
            "template_path": relative.as_posix(), "path": str(path), "sha256": actual_hash,
            "duration": duration, "start": binding["start"], "volume": binding["volume"], "probe": probe}


def color_conversion(info):
    """Decode the declared transfer first; never substitute an output tag for conversion."""
    primaries, transfer, matrix, source_range = (info.get(key) for key in
        ("color_primaries", "color_transfer", "color_space", "color_range"))
    if info.get("camera_log_flag") or transfer in ("log100", "log316"):
        raise ValueError("Camera LOG source is unsupported; supply a verified Rec709 SDR export")
    if source_range not in ("tv", "pc"):
        raise ValueError("Unverified color range; supply a correctly tagged SDR or HLG/PQ master")
    prefix = f"zscale=pin={primaries}:tin={transfer}:min={matrix}:rin={source_range}"
    if transfer in ("arib-std-b67", "smpte2084"):
        if primaries != "bt2020" or matrix not in ("bt2020nc", "bt2020c"):
            raise ValueError("HLG/PQ requires verified BT.2020 primaries and matrix metadata")
        peak_nits = info.get("hdr_peak_nits") or 1000.0
        chain = (prefix + ":t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                 f"tonemap=mobius:param=0.3:desat=2:peak={peak_nits / 100:g},"
                 "zscale=t=bt709:m=bt709:r=limited:dither=error_diffusion,format=yuv420p")
        return {"branch": "HLG-to-SDR" if transfer == "arib-std-b67" else "PQ-to-SDR",
                "filter": chain, "reference_white_nits": 100, "peak_nits": peak_nits,
                "peak_source": "stream metadata" if info.get("hdr_peak_nits") else "explicit 1000-nit fallback"}
    if primaries == "bt709" and matrix == "bt709" and transfer in ("bt709", "iec61966-2-1"):
        return {"branch": "SDR-to-Rec709", "filter": prefix + ":p=bt709:t=bt709:m=bt709:r=limited,format=yuv420p"}
    raise ValueError(f"Unverified/unsupported color metadata ({primaries}, {transfer}, {matrix}); "
                     "supply a verified Rec709 SDR export; camera LOG is not guessed")


def record(value, minimum, base, ffprobe):
    if not isinstance(value, dict):
        raise ValueError("Every grid/main entry must be a video record object")
    user = value.get("source") == "user"
    if not user and (value.get("status") != "可使用" or not isinstance(value.get("record_id"), str)
                     or not value["record_id"].strip()):
        raise ValueError("Video must be user supplied or have status=可使用 and record_id")
    path = local_file(value.get("path"), base)
    info = media_info(path, "video", minimum, ffprobe)
    return {"path": str(path), "source": "user" if user else "library",
            "status": "user-supplied" if user else "可使用",
            "record_id": None if user else value["record_id"], "sha256": sha256(path),
            "probe": info, "color_conversion": color_conversion(info)}


def update_html(source, variables):
    schema_pattern = r'data-composition-variables=([\"\'])(.*?)\1'
    match = re.search(schema_pattern, source, re.S)
    if not match:
        raise ValueError("Template is missing its variable schema")
    schema = json.loads(html.unescape(match.group(2)))
    if not set(variables).issubset({item["id"] for item in schema}):
        raise ValueError("Template schema does not support all nine-grid variables")
    for item in schema:
        if item["id"] in variables:
            item["default"] = variables[item["id"]]
    replacement = 'data-composition-variables="' + html.escape(json.dumps(schema, ensure_ascii=False), quote=True) + '"'
    source = source[:match.start()] + replacement + source[match.end():]
    for key in ("title", "tagline"):
        pattern = rf'(<(?P<tag>span|div)\b[^>]*data-var-text="{key}"[^>]*>).*?(</(?P=tag)>)'
        source, count = re.subn(pattern, lambda m: m[1] + html.escape(variables[key]) + m[3], source, flags=re.S)
        if count != 1:
            raise ValueError(f"Expected one static {key} text binding")
    for key, value in variables.items():
        if key in ("title", "tagline"):
            continue
        pattern = rf'<(?:video|audio)\b[^>]*data-var-src="{key}"[^>]*>'
        def replace_tag(match):
            tag, count = re.subn(r'(?<![\w-])src="[^"]*"', 'src="' + html.escape(value, quote=True) + '"', match[0])
            if count != 1:
                raise ValueError(f"Expected one fallback src for {key}")
            return tag
        source, count = re.subn(pattern, replace_tag, source)
        if count != 1:
            raise ValueError(f"Expected one media binding for {key}")
    return source


def prepare(args):
    job_path = Path(args.job).resolve(strict=True)
    job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    if not isinstance(job, dict):
        raise ValueError("Job JSON must be an object")
    for key, maximum in (("title", 9), ("tagline", 16)):
        text = job.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or any(ord(c) < 32 for c in text):
            raise ValueError(f"{key} requires 1–{maximum} characters, without line breaks/control characters")
    for key, count in (("grid", 9), ("main", 3)):
        if not isinstance(job.get(key), list) or len(job[key]) != count:
            raise ValueError(f"{key} must contain exactly {count} video records")
    template = Path(args.template_dir).resolve(strict=True)
    output = Path(args.output_dir).resolve()
    if output.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    files = list(BASE_FILES) + ["assets/" + name for name in ASSETS]
    for name in files:
        if not (template / name).is_file():
            raise ValueError(f"Template dependency is missing: {name}")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("Install ffmpeg and ffprobe and add them to PATH")
    audio = bound_audio(template, job, job_path.parent, ffprobe)
    grid = [record(item, 3.2, job_path.parent, ffprobe) for item in job["grid"]]
    if len({item["sha256"] for item in grid}) != 9 or len({item["path"] for item in grid}) != 9:
        raise ValueError("Grid requires nine distinct videos; duplicate paths or file contents detected")
    mains = [record(item, seconds, job_path.parent, ffprobe) for item, seconds in zip(job["main"], MAIN_SECONDS)]
    variables = {"title": job["title"], "tagline": job["tagline"]}
    variables.update({f"{group}{i}": f"assets/{group}/{i:02}.mp4"
                      for group, count in (("grid", 9), ("main", 3)) for i in range(1, count + 1)})
    authored = update_html((template / "index.html").read_text(encoding="utf-8-sig"), variables)
    output.mkdir(parents=True, exist_ok=False)  # All validation above happens without output writes.
    for name in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template / name, target)
    (output / "index.html").write_text(authored, encoding="utf-8")
    def encode(entry):
        item, group, index, seconds, width, height = entry
        target = output / variables[f"{group}{index}"]
        target.parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe",
             "-i", item["path"], "-map", "0:v:0", "-t", str(seconds), "-an", "-filter_threads", "1", "-vf",
             item["color_conversion"]["filter"] + "," +
             f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30",
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
             "-map_metadata", "-1",
             "-movflags", "+faststart", str(target)])
        derived = media_info(target, "video", seconds, ffprobe)
        if any(derived.get(key) != value for key, value in {
                "codec": "h264", "pix_fmt": "yuv420p", "color_primaries": "bt709",
                "color_transfer": "bt709", "color_space": "bt709", "color_range": "tv"}.items()):
            raise ValueError(f"SDR normalization did not validate: {target}")
        return {**item, "slot": f"{group}{index}", "derived_path": target.relative_to(output).as_posix(),
                "derived_sha256": sha256(target), "derived_probe": derived,
                "operation": "Color-normalized to true Rec709 SDR before HyperFrames treatment; "
                             "center crop; 30fps; muted; source start=0"}
    entries = [(item, "grid", i, 3.2, 360, 640) for i, item in enumerate(grid, 1)]
    entries += [(item, "main", i, seconds, 1080, 1920) for i, (item, seconds) in enumerate(zip(mains, MAIN_SECONDS), 1)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        provenance = list(pool.map(encode, entries))
    audio_target = output / audio["template_path"]
    audio_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(audio["path"], audio_target)
    derived_hash = sha256(audio_target)
    if derived_hash != audio["sha256"]:
        raise ValueError("Bound BGM changed during preparation; restore the original track and retry")
    audio.update(derived_path=audio["template_path"], derived_sha256=derived_hash,
                 operation="Byte-identical copy of the template-bound 12-second track; no re-encoding or audio changes")
    for name, data in (("variables.json", variables), ("provenance.json", {
            "template_id": "nine-grid-reveal", "duration": 12, "created_at": datetime.now(timezone.utc).isoformat(),
            "videos": provenance, "bgm": audio, "privacy": "Local source paths; review before sharing."})):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", help="JSON job containing title, tagline, nine grid videos and three main videos; BGM is template-bound")
    parser.add_argument("--template-dir", required=True, help="Reusable template folder with bundled font/vendor assets")
    parser.add_argument("--output-dir", required=True, help="New output directory; existing paths are never overwritten")
    try:
        prepare(parser.parse_args())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        sys.exit(2)
