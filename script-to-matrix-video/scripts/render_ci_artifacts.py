#!/usr/bin/env python3
"""Build a contact sheet from retained reference previews; no retired preset rendering."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    pack = Path(__file__).resolve().parents[1] / "assets/templates/reference-typography-17"
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["templates"]
    previews = [(pack / item["example_jpg"]).resolve() for item in entries]
    if not previews or not all(path.is_file() for path in previews):
        raise RuntimeError("Retained template previews missing")
    filters = [f"[{i}:v]scale=180:320,setsar=1[p{i}]" for i in range(len(previews))]
    labels = "".join(f"[p{i}]" for i in range(len(previews)))
    positions = "|".join(f"{i % 6 * 180}_{i // 6 * 320}" for i in range(len(previews)))
    filters.append(labels + f"xstack=inputs={len(previews)}:layout={positions}:fill=black[v]")
    sheet = output / "retained-reference-contact-sheet.png"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    *[part for path in previews for part in ("-i", str(path))],
                    "-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                    "-map", "[v]", "-frames:v", "1", str(sheet)], check=True,
                   **({"creationflags": subprocess.CREATE_NO_WINDOW} if __import__("os").name == "nt" else {}))
    report = {"ok": True, "artifact_kind": "existing_reference_preview_contact_sheet",
              "contact_sheet": str(sheet), "template_ids": [item["id"] for item in entries],
              "reference_count": len(entries),
              "note": "Actual low-level rendering is exercised by test_template_catalog.py; motion/BGM tests run separately."}
    (output / "artifact-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
