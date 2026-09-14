"""Validate this saved template and prepared local media without rendering."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def probe(path):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, **options,
    )
    return json.loads(result.stdout)["streams"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root, media_dir=None, bundle_only=False):
    spec = json.loads((root / "template.json").read_text(encoding="utf-8"))
    for asset in [*spec["fixedOpening"], spec["referenceAudio"]]:
        path = root / asset["path"]
        require(path.is_file(), f"Missing bound asset: {asset['path']}")
        require(digest(path) == asset["sha256"], f"Bound asset changed: {asset['path']}")
        streams = probe(path)
        if "frames" in asset:
            video = next(s for s in streams if s["codec_type"] == "video")
            require((video["width"], video["height"]) == (720, 776), "Opening crop/subtitle area changed")
            require(int(video["nb_frames"]) == asset["frames"] and video["r_frame_rate"] == "30/1", "Opening timing changed")
        else:
            require(any(s["codec_type"] == "audio" and float(s.get("duration", 0)) >= 17.25 for s in streams), "Bound audio too short")
    for name in ("index.html", "index.motion.json", "frame.md", "package.json", "hyperframes.json", "assets/fonts/NotoSansSC-Variable.ttf", "assets/fonts/OFL-NotoSansSC.txt", "assets/vendor/gsap.min.js", "compositions/components/whip-pan-cut.html"):
        require((root / name).is_file(), f"Missing runtime file: {name}")
    if bundle_only:
        return "Bundle valid; four replaceable videos still required before render."
    identities = set()
    for name in spec["mediaPolicy"]["files"]:
        path = (media_dir or root / "assets/media") / name
        require(path.is_file(), f"Supply prepared video: {name}")
        video = next(s for s in probe(path) if s["codec_type"] == "video")
        require(video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p", f"Prepare H.264/yuv420p: {name}")
        require(video["r_frame_rate"] == "30/1" and video.get("sample_aspect_ratio") == "1:1", f"Prepare 30fps, SAR1:1: {name}")
        require(float(video.get("duration", 0)) >= 6 - 0.001, f"Need at least 6 seconds: {name}")
        require(video.get("color_transfer") == "bt709" and video.get("color_primaries") == "bt709" and video.get("color_space") == "bt709", f"Prepare Rec.709 SDR, not retagged HDR: {name}")
        identities.add(digest(path))
    require(len(identities) == 4, "Four different prepared source files required")
    return "Bundle and four prepared sources valid; run HyperFrames check and visual review."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-only", action="store_true")
    parser.add_argument("--media-dir", type=Path, help="Optional directory holding prepared 00–03.mp4 for validation only")
    args = parser.parse_args()
    try:
        print(validate(Path(__file__).resolve().parent, args.media_dir, args.bundle_only))
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Template validation failed: {error}\n")
