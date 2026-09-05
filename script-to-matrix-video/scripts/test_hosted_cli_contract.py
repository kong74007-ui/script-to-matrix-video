#!/usr/bin/env python3
"""Validate the zero-cost hosted template-video Skill contract and examples."""

from __future__ import annotations

import json
from pathlib import Path
import re


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parent
REFERENCE = SKILL_ROOT / "references" / "hosted-template-cli.md"
ALLOWED_FIELDS = {"top_text", "bottom_text", "template_id", "font_family", "voiceover", "count"}
ALLOWED_VOICEOVER_FIELDS = {"text", "voice", "voice_scope", "speed"}


def validate_request(payload: dict, *, batch: bool) -> None:
    assert isinstance(payload, dict)
    assert set(payload) <= ALLOWED_FIELDS
    assert 2 <= len(payload["top_text"].strip()) <= 60
    assert 2 <= len(payload["bottom_text"].strip()) <= 80
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", payload["template_id"])
    if batch:
        assert 2 <= payload.get("count", 0) <= 5
    else:
        assert "count" not in payload
    voiceover = payload.get("voiceover")
    assert isinstance(voiceover, dict)
    assert set(voiceover) <= ALLOWED_VOICEOVER_FIELDS
    assert {"text", "voice"} <= set(voiceover)
    assert 1 <= len(voiceover["text"].strip()) <= 120
    assert 1 <= len(voiceover["voice"].strip()) <= 128
    assert voiceover.get("voice_scope") in {"public", "personal"}
    assert not isinstance(voiceover.get("speed"), bool)
    assert 0.5 <= float(voiceover.get("speed", 1.0)) <= 2.0


def main() -> int:
    reference = REFERENCE.read_text(encoding="utf-8")
    examples = [
        json.loads(value)
        for value in re.findall(r"```json\s*([\s\S]*?)```", reference)
    ]
    assert len(examples) == 2
    validate_request(examples[0], batch=False)
    validate_request(examples[1], batch=True)

    for command in (
        "hq version --json",
        "hq status --json",
        "hq run matrix-template-capability --json",
        "hq run matrix-template-templates --json",
        "hq run voices --json",
        "hq run matrix-template-generate",
        "hq run matrix-template-batch-generate",
    ):
        assert command in reference
    for invariant in (
        "0.15.4", "ready=true", "quote_token", "batch_result_pending",
        "batch_id", "不得提供或修改批次身份字段",
    ):
        assert invariant in reference

    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    agent = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    assert "references/hosted-template-cli.md" in skill
    assert "主站路径" in agent and "逐镜口播" in agent
    assert "v1.9.0" in readme and "HQ CLI 0.15.4" in readme
    print("hosted template CLI contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
