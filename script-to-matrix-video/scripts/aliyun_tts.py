#!/usr/bin/env python3
"""Synthesize scene narration with Alibaba Cloud Bailian CosyVoice.

The script updates project.json after every successful scene so interrupted runs
can resume without paying for completed lines again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any


DEFAULT_VOICE = {
    "provider": "alibaba-cloud-bailian",
    "model": "cosyvoice-v3-flash",
    "voice": "longxiaoxia_v3",
    "speech_rate": 1.0,
    "volume": 50,
    "tail_padding": 0.2,
    "normalize": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to project.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate without calling the API")
    parser.add_argument("--force", action="store_true", help="Regenerate cached scene audio")
    return parser.parse_args()


def load_project(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Project manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid project JSON: {exc}") from exc
    if not isinstance(payload.get("scenes"), list) or not payload["scenes"]:
        raise RuntimeError("project.json must contain a non-empty scenes array")
    return payload


def save_project(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, suffix=".tmp", delete=False
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_output(root: Path, value: str) -> Path:
    candidate = Path(value)
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Audio output must stay inside project folder: {candidate}") from exc
    return candidate


def probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required but was not found on PATH")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise RuntimeError(f"Generated audio has invalid duration: {path}")
    return duration


def normalize_wav(source: Path, destination: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for narration normalization")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        check=True,
    )


def sanitized_error(exc: Exception, api_key: str) -> str:
    message = str(exc).replace(api_key, "***") if api_key else str(exc)
    return message[:1000]


def synthesize(text: str, settings: dict[str, Any], seed: int, api_key: str) -> tuple[bytes, str | None]:
    import dashscope
    from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

    dashscope.api_key = api_key
    synthesizer = SpeechSynthesizer(
        model=settings["model"],
        voice=settings["voice"],
        format=AudioFormat.WAV_48000HZ_MONO_16BIT,
        speech_rate=float(settings["speech_rate"]),
        volume=int(settings["volume"]),
        seed=seed,
    )
    audio = synthesizer.call(text)
    if not audio or len(audio) <= 44:
        raise RuntimeError("CosyVoice returned no usable WAV data")
    return audio, synthesizer.get_last_request_id()


def main() -> int:
    args = parse_args()
    project_path = args.project.resolve()
    root = project_path.parent
    project = load_project(project_path)
    settings = {**DEFAULT_VOICE, **project.get("voice", {})}
    project["voice"] = settings

    required = ("model", "voice", "speech_rate", "volume", "tail_padding")
    missing = [key for key in required if settings.get(key) is None]
    if missing:
        raise RuntimeError(f"Missing voice settings: {', '.join(missing)}")

    plans: list[dict[str, Any]] = []
    for index, scene in enumerate(project["scenes"], start=1):
        scene_id = str(scene.get("id") or f"s{index:02d}")
        scene["id"] = scene_id
        text = str(scene.get("text") or "").strip()
        if not text:
            raise RuntimeError(f"Scene {scene_id} has no narration text")
        audio_value = str(scene.get("audio") or f"assets/audio/{scene_id}.wav")
        audio_path = resolve_output(root, audio_value)
        scene["audio"] = audio_path.relative_to(root).as_posix()
        text_hash = stable_hash(text)
        settings_hash = stable_hash(
            {
                "model": settings["model"],
                "voice": settings["voice"],
                "speech_rate": settings["speech_rate"],
                "volume": settings["volume"],
                "normalize": bool(settings.get("normalize", True)),
                "format": "wav-48000hz-mono-16bit",
            }
        )
        cached = (
            not args.force
            and audio_path.exists()
            and scene.get("tts_text_sha256") == text_hash
            and scene.get("tts_settings_sha256") == settings_hash
        )
        plans.append(
            {
                "scene": scene,
                "scene_id": scene_id,
                "text": text,
                "audio_path": audio_path,
                "text_hash": text_hash,
                "settings_hash": settings_hash,
                "cached": cached,
                "seed": int(scene.get("tts_seed", 20260822 + index)),
            }
        )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "model": settings["model"],
                    "voice": settings["voice"],
                    "scenes": [
                        {"id": item["scene_id"], "cached": item["cached"], "output": str(item["audio_path"])}
                        for item in plans
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if any(not item["cached"] for item in plans) and not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    completed = 0
    reused = 0
    for item in plans:
        scene = item["scene"]
        audio_path: Path = item["audio_path"]
        if item["cached"]:
            duration = probe_duration(audio_path)
            scene.update(
                {
                    "audio_duration": round(duration, 3),
                    "duration": round(duration + float(settings["tail_padding"]), 3),
                    "tts_status": "cached",
                }
            )
            reused += 1
            save_project(project_path, project)
            continue

        audio_path.parent.mkdir(parents=True, exist_ok=True)
        last_error = ""
        for attempt in range(1, 4):
            try:
                audio, request_id = synthesize(item["text"], settings, item["seed"], api_key)
                with tempfile.NamedTemporaryFile(dir=audio_path.parent, suffix=".wav", delete=False) as handle:
                    raw_path = Path(handle.name)
                    handle.write(audio)
                try:
                    if bool(settings.get("normalize", True)):
                        normalized_path = raw_path.with_name(f"{raw_path.stem}-normalized.wav")
                        normalize_wav(raw_path, normalized_path)
                        os.replace(normalized_path, audio_path)
                    else:
                        os.replace(raw_path, audio_path)
                    duration = probe_duration(audio_path)
                finally:
                    raw_path.unlink(missing_ok=True)
                    raw_path.with_name(f"{raw_path.stem}-normalized.wav").unlink(missing_ok=True)
                scene.update(
                    {
                        "tts_text_sha256": item["text_hash"],
                        "tts_settings_sha256": item["settings_hash"],
                        "tts_seed": item["seed"],
                        "tts_request_id": request_id,
                        "audio_duration": round(duration, 3),
                        "duration": round(duration + float(settings["tail_padding"]), 3),
                        "tts_status": "generated",
                    }
                )
                scene.pop("tts_error", None)
                completed += 1
                save_project(project_path, project)
                break
            except Exception as exc:  # keep retry boundary around API and media validation
                last_error = sanitized_error(exc, api_key)
                if attempt < 3:
                    time.sleep(attempt)
        else:
            scene["tts_status"] = "failed"
            scene["tts_error"] = last_error
            save_project(project_path, project)
            raise RuntimeError(f"Scene {item['scene_id']} failed after 3 attempts: {last_error}")

    print(json.dumps({"ok": True, "generated": completed, "reused": reused, "project": str(project_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000]}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
