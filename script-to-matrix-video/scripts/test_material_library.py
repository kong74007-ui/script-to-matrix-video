#!/usr/bin/env python3
"""Zero-network regression checks for first-run material-library connection."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


SCRIPT = Path(__file__).with_name("material_library.py")


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="matrix-material-library-") as temporary:
        root = Path(temporary)
        library = root / "library"
        library.mkdir()
        (library / "sample.mp4").write_bytes(b"test-media")
        record = {
            "record_id": "test-video-1",
            "素材名称": "测试视频",
            "素材类型": "视频",
            "状态": "可使用",
            "server_relative_path": "sample.mp4",
            "画面方向": "竖屏",
        }
        (library / "index.jsonl").write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        profile = root / "profile" / "material-library.json"

        connected = run("connect", "--root", str(library), "--profile", str(profile))
        assert connected.returncode == 0, connected.stderr
        connected_payload = json.loads(connected.stdout)
        assert connected_payload["ok"] is True
        assert connected_payload["connected"] is True
        assert connected_payload["total"] == 1
        assert json.loads(profile.read_text(encoding="utf-8")) == {
            "root": str(library.resolve())
        }

        inspected = run("inspect", "--config", str(profile))
        assert inspected.returncode == 0, inspected.stderr
        inspected_payload = json.loads(inspected.stdout)
        assert inspected_payload["total"] == 1
        assert inspected_payload["statuses"] == {"可使用": 1}

        missing = run(
            "connect",
            "--root",
            str(root / "missing-library"),
            "--profile",
            str(root / "missing-profile.json"),
        )
        assert missing.returncode != 0
        assert not (root / "missing-profile.json").exists()

    print("material-library connection checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
