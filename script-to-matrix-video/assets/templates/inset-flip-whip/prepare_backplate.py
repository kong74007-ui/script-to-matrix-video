"""Run inside a populated job: python prepare_backplate.py. Requires ffmpeg/ffprobe."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from gpu_runtime import accelerate_ffmpeg

ROOT = Path(__file__).resolve().parent
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(args):
    args = accelerate_ffmpeg(args)
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          encoding="utf-8", creationflags=FLAGS).stdout


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                           "-show_streams", "-of", "json", str(path)]))["streams"][0]


def main():
    meta = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
    audio = meta["referenceAudio"]
    if hashlib.sha256((ROOT / audio["path"]).read_bytes()).hexdigest() != audio["sha256"]:
        raise ValueError("Bound BGM checksum mismatch; restore the bundled music.")
    seen = set()
    slots = meta["media"]
    for number in range(7):
        path = ROOT / f"assets/media/{number:02}.mp4"
        info = probe(path)
        required = max(end - start + offset for start, end, source_id, offset in
                       zip(slots["starts"], slots["ends"], slots["sources"], slots["offsets"])
                       if source_id == number)
        if float(info.get("duration", 0)) + 0.001 < required:
            raise ValueError(f"{path.name}: needs at least {required:.3f}s; prepare five seconds when possible.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            raise ValueError("Use seven distinct approved source videos, not duplicate files.")
        seen.add(digest)
        if info.get("pix_fmt") != "yuv420p" or info.get("color_transfer") != "bt709":
            raise ValueError(f"{path.name}: prepare tagged Rec.709 SDR/yuv420p first; do not relabel HDR.")
    recipe = json.loads((ROOT / "opening-treatment.json").read_text(encoding="utf-8"))
    source, output = ROOT / recipe["source"], ROOT / recipe["output"]
    source_info = probe(source)
    # Always rebuild from 00.mp4, never a previous derivative: no stale media0 or cumulative grading.
    with tempfile.TemporaryDirectory(prefix="inset-backplate-", dir=output.parent) as scratch:
        candidate = Path(scratch) / "candidate.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
             "-vf", recipe["fallbackFilter"], "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "fast", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
             "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(candidate)])
        result = probe(candidate)
        for key in ("width", "height", "nb_frames", "r_frame_rate"):
            if result.get(key) != source_info.get(key):
                raise ValueError(f"Backplate changed {key}; source preparation required.")
        candidate.replace(output)
    print("Ready: matching same-time, same-framing backplate; neutral after 1.1s.")
    print("Replace videos only at documented 00..06 paths; do not override media0 in variables.json.")


if __name__ == "__main__":
    main()
