"""Prepare the saved bilingual-stagger-salon template; no ASR, TTS or generation."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

SKILL = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets/templates/bilingual-stagger-salon"
FONT_FILES = ("MaShanZheng-Regular.ttf", "NotoSerifSC-Variable.ttf",
              "OFL-MaShanZheng.txt", "OFL-NotoSerifSC.txt")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    value = float(value)
    require(math.isfinite(value), "Timing must be finite")
    return value


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return json.loads(result.stdout)


def source(base, value):
    path = Path(value)
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    require(path.is_file(), "Missing input: " + str(path))
    return path


def validate(task, base):
    profile = task.get("render_profile", "gpu-hdr")
    require(profile in ("gpu-hdr", "sdr-compat"), "Unknown render profile")
    fps = number(task.get("fps", 30))
    require(fps in (30, 60), "FPS must be 30 or 60; do not invent intermediate frames")
    require(task.get("bgm") in (None, False, "none"), "This template has no BGM; create a separate customization")
    voice = source(base, task["voice"])
    vp = probe(voice)
    require(any(s["codec_type"] == "audio" for s in vp["streams"]), "Voice has no audio stream")
    audio_duration = number(vp["format"]["duration"])
    require(audio_duration > 0, "Voice is empty")
    duration = number(task.get("duration", math.ceil((audio_duration + .6) * fps) / fps))
    require(duration >= audio_duration, "Do not truncate narration")
    require(duration - audio_duration <= 2, "Tail hold must be at most 2 seconds")
    require(abs(duration * fps - round(duration * fps)) < .001, "Duration must align to output fps")
    media = task["media"]
    require(len(media) >= 3, "At least three distinct real videos are required")
    prepared = []
    hashes = set()
    for i, item in enumerate(media):
        require(item.get("source_type") in ("client", "library"), "Only client/library media allowed")
        if item["source_type"] == "library":
            require(item.get("status") == "可使用" and item.get("record_id"), "Library approval and record_id required")
        path = source(base, item["path"])
        hasher = hashlib.sha256()
        with path.open('rb') as source_file:
            for block in iter(lambda: source_file.read(1024 * 1024), b''):
                hasher.update(block)
        digest = hasher.hexdigest()
        require(digest not in hashes, "Duplicate media contents")
        hashes.add(digest)
        p = probe(path)
        streams = [s for s in p["streams"] if s["codec_type"] == "video"]
        require(len(streams) == 1, "Expected one video stream")
        stream = streams[0]
        require(stream.get("codec_name") in ("h264", "hevc", "prores"), "Unsupported source video codec")
        hdr = stream.get("color_transfer") in ("arib-std-b67", "smpte2084") and stream.get("color_primaries") == "bt2020"
        if profile == "sdr-compat":
            require(stream.get("color_transfer") == "bt709" and stream.get("color_space") == "bt709",
                    "SDR compatibility profile requires real Rec.709 SDR")
        elif hdr:
            require(any(bit in stream.get("pix_fmt", "") for bit in ("10", "12", "16")), "HDR source must retain high bit depth")
        else:
            require(stream.get("color_primaries") == "bt709", "Untagged source needs color review")
        rotation = next((s.get("rotation", 0) for s in stream.get("side_data_list", []) if "rotation" in s), 0)
        width, height = stream.get("width", 0), stream.get("height", 0)
        if abs(round(rotation)) % 180 == 90:
            width, height = height, width
        require(width >= (1080 if profile == "gpu-hdr" else 720) and height >= (1920 if profile == "gpu-hdr" else 1280),
                "Use original portrait resolution, including rotation metadata; no 720p proxies for HDR")
        start = number(item.get("start", round(i * duration / len(media), 6)))
        end = number(item.get("end", duration if i == len(media)-1 else
                              round((i+1) * duration / len(media) + .18, 6)))
        offset = number(item.get("offset", 0))
        require(0 <= start < end <= duration and offset >= 0, "Invalid media window")
        require(end - start > .18, "Media window too short")
        require(offset + end - start <= number(p["format"]["duration"]) + .02, "Media source too short")
        if i == 0:
            require(start == 0, "First video must begin at zero")
        else:
            require(abs(prepared[-1]["end"] - start - .18) < .002,
                    "Adjacent clips must overlap by 0.18 seconds")
        prepared.append(dict(item, path=path, start=start, end=end, offset=offset, sha256=digest, hdr=hdr))
    require(profile != "gpu-hdr" or any(item["hdr"] for item in prepared), "No genuine HDR source: cannot recover HDR from SDR proxies")
    require(abs(prepared[-1]["end"] - duration) < .002, "Final video must reach output end")
    cues = []
    for i, raw in enumerate(task["cues"]):
        cue = dict(raw)
        text = cue["text"]
        require(isinstance(text, str) and 0 < len(text) <= 10, "Split captions into at most 10 characters")
        require(isinstance(cue.get("en"), str) and 0 < len(cue["en"]) <= 48, "English caption missing/too long")
        times = [number(t) for t in cue["times"]]
        end = duration if cue["end"] == "end" else number(cue["end"])
        require(len(times) == len(text), "One timestamp per Unicode code point required")
        require(times == sorted(times) and times[0] >= 0 and times[-1] + .20 <= end + .001
                and end <= duration, "Invalid caption times or no settling time")
        require(cue.get("row", 0) in (0, 1), "Caption row must be 0 or 1")
        accents = cue.get("yellow", [])
        require(all(isinstance(v, int) and 0 <= v < len(text) for v in accents), "Invalid accent index")
        cues.append(dict(cue, id="c%02d" % (i+1), times=times, end=end, row=cue.get("row", 0)))
    require(bool(cues), "Timed captions are required")
    for row in (0, 1):
        ordered = sorted((c for c in cues if c["row"] == row), key=lambda c: c["times"][0])
        for a, b in zip(ordered, ordered[1:]):
            require(a["end"] <= b["times"][0] + .055, "Held captions collide on the same row")
    titles = task["titles"]
    require(bool(titles), "At least one title required")
    for t in titles:
        require(t.get("style", "main") in ("main", "subtitle"), "Unknown title style")
        require(isinstance(t["text"], str) and 0 < len(t["text"]) <= 10, "Short title required")
        end = duration if t["end"] == "end" else number(t["end"])
        require(0 <= number(t["start"]) < end <= duration and end-number(t["start"]) >= .5,
                "Invalid title interval")
    return voice, audio_duration, duration, prepared, cues, titles


def prepare(task_file, output, validate_only=False):
    task_file = Path(task_file).resolve()
    task = json.loads(task_file.read_text(encoding="utf-8-sig"))
    voice, audio_duration, duration, media, cues, titles = validate(task, task_file.parent)
    if validate_only:
        return {"valid": True, "duration": duration, "media_count": len(media)}
    output = Path(output).resolve()
    require(not output.exists(), "Output already exists; choose a new job directory")
    for name in FONT_FILES:
        require((SKILL/"assets/fonts"/name).is_file(), "Missing bundled font or license: " + name)
    output.mkdir(parents=True)
    (output/"assets/fonts").mkdir(parents=True)
    (output/"assets/media").mkdir()
    shutil.copytree(TEMPLATE/"assets/vendor", output/"assets/vendor")
    for name in FONT_FILES:
        shutil.copy2(SKILL/"assets/fonts"/name, output/"assets/fonts"/name)
    voice_path = "assets/voice" + voice.suffix.lower()
    shutil.copy2(voice, output/voice_path)
    blocks, moves = [], []
    for i, item in enumerate(media):
        path = "assets/media/%02d%s" % (i, item["path"].suffix.lower())
        shutil.copy2(item["path"], output/path)
        s, d = item["start"], item["end"] - item["start"]
        later = " later" if i else ""
        blocks.append(f'<div class="shot"><div class="camera{later}" id="cam-{i}" data-layout-allow-overflow=""><video id="media-{i}" class="clip" data-start="{s}" data-duration="{d}" data-media-start="{item["offset"]}" data-track-index="{i+1}" src="{path}" muted playsinline></video></div></div>')
        if i:
            moves.append(f"gsap.set('#cam-{i}',{{opacity:0,scale:1}});")
        scale = 1.025 if i == len(media)-1 else 1.03
        moves.append(f"tl.fromTo('#cam-{i}',{{scale:1}},{{scale:{scale},duration:{d},ease:'none',immediateRender:false}},{s});")
        if i:
            moves.append(f"tl.fromTo('#cam-{i}',{{opacity:0}},{{opacity:1,duration:.18,ease:'none',immediateRender:false}},{s});")
    title_html, title_moves = [], []
    for i, t in enumerate(titles):
        s = number(t["start"])
        end = duration if t["end"] == "end" else number(t["end"])
        subtitle = t.get("style") == "subtitle"
        cls = " subtitle" if subtitle else ""
        title_html.append(f'<div id="heading-{i}-clip" class="clip headline{cls}" data-start="{s}" data-duration="{end-s}" data-track-index="{20+int(subtitle)}"><div id="heading-{i}" class="title-visual">{html.escape(t["text"])}</div></div>')
        # When held to the end, exit is outside the render window.
        exit_time = duration+.3 if end == duration else end
        x = number(t.get("entrance_x", 0 if subtitle else 42))
        title_moves.append(f"title('#heading-{i}',{s},{exit_time},{x});")
    replacements = {
        "__MEDIA_HTML__": "\n".join(blocks), "__MEDIA_MOTION__": "\n".join(moves),
        "__TITLE_HTML__": "\n".join(title_html), "__TITLE_MOTION__": "\n".join(title_moves),
        "__DURATION__": str(duration), "__VOICE_DURATION__": str(audio_duration),
        "__VOICE_PATH__": voice_path, "__FPS__": str(int(task.get("fps", 30)))}
    markup = (TEMPLATE/"index.html.in").read_text(encoding="utf-8")
    for token, value in replacements.items():
        markup = markup.replace(token, value)
    (output/"index.html").write_text(markup, encoding="utf-8")
    (output/"captions.js").write_text("window.CAPTION_CUES = "+json.dumps(cues, ensure_ascii=False)+";\n", encoding="utf-8")
    for name in ("package.json", "hyperframes.json"):
        shutil.copy2(TEMPLATE/name, output/name)
    shutil.copy2(SKILL/"scripts/render_gpu_hdr.py", output/"render_gpu_hdr.py")
    shutil.copy2(SKILL/"scripts/hyperframes_hdr_patch.py", output/"hyperframes_hdr_patch.py")
    if task.get("render_profile", "gpu-hdr") == "sdr-compat":
        package = json.loads((output/"package.json").read_text(encoding="utf-8"))
        package["scripts"]["render"] = "npx --yes hyperframes@0.8.38 render --sdr --quality delivery --fps " + str(int(task.get("fps", 30)))
        (output/"package.json").write_text(json.dumps(package), encoding="utf-8")
    (output/"meta.json").write_text(json.dumps({"id":output.name,"name":output.name}),encoding="utf-8")
    (output/"index.motion.json").write_text(json.dumps({"duration":duration,"assertions":[
        {"kind":"appearsBy","selector":"#heading-0","bySec":number(titles[0]["start"])+.4},
        *({"kind":"staysInFrame","selector":"#"+cue["id"]} for cue in cues)]}),encoding="utf-8")
    provenance = {"template_id":"bilingual-stagger-salon","bgm":None,"voice":str(voice),
                  "duration":duration,"media":media,"render_profile":task.get("render_profile", "gpu-hdr"),
                  "notes":"Private job provenance; do not publish; original bytes copied without tone mapping"}
    (output/"provenance.private.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    return {"valid":True,"project":str(output),"duration":duration,"media_count":len(media)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.task, args.output, args.validate_only), ensure_ascii=False))
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print("Preparation failed: "+str(exc), file=sys.stderr)
        sys.exit(1)
