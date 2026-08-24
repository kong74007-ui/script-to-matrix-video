#!/usr/bin/env python3
"""Check the local runtime needed by script-to-matrix-video."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import shutil
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-tts",
        action="store_true",
        help="Treat DashScope and DASHSCOPE_API_KEY as required instead of optional",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []

    version = sys.version_info
    python_ok = version >= (3, 10)
    print(f"[{'OK' if python_ok else 'FAIL'}] Python {version.major}.{version.minor}.{version.micro}")
    if not python_ok:
        failures.append("Python 3.10 or newer is required")

    for executable in ("ffmpeg", "ffprobe"):
        path = shutil.which(executable)
        print(f"[{'OK' if path else 'FAIL'}] {executable}: {path or 'not found on PATH'}")
        if not path:
            failures.append(f"{executable} is required on PATH")

    try:
        dashscope_version = importlib.metadata.version("dashscope")
        print(f"[OK] dashscope {dashscope_version}")
    except importlib.metadata.PackageNotFoundError:
        status = "FAIL" if args.require_tts else "OPTIONAL"
        print(f"[{status}] dashscope is not installed")
        if args.require_tts:
            failures.append("Install the packages from requirements.txt for Alibaba narration")

    has_key = bool(os.environ.get("DASHSCOPE_API_KEY"))
    key_status = "OK" if has_key else ("FAIL" if args.require_tts else "OPTIONAL")
    print(f"[{key_status}] DASHSCOPE_API_KEY: {'configured' if has_key else 'not configured'}")
    if args.require_tts and not has_key:
        failures.append("DASHSCOPE_API_KEY is required when narration is enabled")

    if failures:
        print("\nEnvironment is not ready:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("\nEnvironment is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
