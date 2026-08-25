#!/usr/bin/env python3
"""Connect, inspect, search, and fetch assets from a Huangque-style media library.

The tool reads index.jsonl from a local library root or over SSH. Connection
settings may come from command-line arguments, environment variables, or the
per-user material-library profile. Remote mode uses the machine's existing SSH
key/agent; passwords are intentionally not accepted or stored.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any


SEARCH_FIELDS = {
    "标签": 6,
    "素材名称": 5,
    "一级场景": 4,
    "二级场景": 4,
    "使用环节": 3,
    "情绪氛围": 3,
    "画面主体": 2,
    "行业": 2,
    "server_relative_path": 1,
}

DEFAULT_CONFIG_PATH = Path.home() / ".codex" / "script-to-matrix-video" / "material-library.json"


def add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        help=(
            "Connection profile; defaults to MATRIX_MATERIAL_LIBRARY_CONFIG or "
            f"{DEFAULT_CONFIG_PATH}"
        ),
    )
    parser.add_argument(
        "--root",
        help="Local library root; defaults to MATRIX_MATERIAL_LIBRARY_ROOT",
    )
    parser.add_argument(
        "--host",
        help="SSH host; defaults to MATRIX_MATERIAL_LIBRARY_HOST",
    )
    parser.add_argument(
        "--user",
        help="SSH user; defaults to MATRIX_MATERIAL_LIBRARY_USER",
    )
    parser.add_argument(
        "--remote-root",
        help="Remote library root; defaults to MATRIX_MATERIAL_LIBRARY_REMOTE_ROOT",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect_parser = subparsers.add_parser(
        "connect", help="Validate and save this machine's material-library connection"
    )
    connect_source = connect_parser.add_mutually_exclusive_group(required=True)
    connect_source.add_argument("--root", help="Local or mounted material-library root")
    connect_source.add_argument("--host", help="SSH host or configured SSH alias")
    connect_parser.add_argument("--user", help="SSH user; omit when the SSH alias defines it")
    connect_parser.add_argument("--remote-root", help="Absolute material-library path on the SSH host")
    connect_parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Profile to write; defaults to {DEFAULT_CONFIG_PATH}",
    )

    inspect_parser = subparsers.add_parser("inspect", help="Summarize the material index")
    add_source_args(inspect_parser)

    search_parser = subparsers.add_parser("search", help="Search approved material metadata")
    add_source_args(search_parser)
    search_parser.add_argument("--query", required=True, help="Space-separated semantic keywords")
    search_parser.add_argument("--type", choices=["图片", "视频", "BGM"], help="Material type")
    search_parser.add_argument("--orientation", choices=["竖屏", "横屏", "方形"], help="Visual orientation")
    search_parser.add_argument("--status", default="可使用", help="Required status; use 'any' to disable")
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum results")

    fetch_parser = subparsers.add_parser("fetch", help="Copy one indexed asset into a project")
    add_source_args(fetch_parser)
    fetch_parser.add_argument("--record-id", required=True, help="Exact record_id from search results")
    fetch_parser.add_argument("--destination", type=Path, required=True, help="Local destination directory")
    fetch_parser.add_argument("--status", default="可使用", help="Required status")
    return parser.parse_args()


def read_connection_profile(args: argparse.Namespace) -> dict[str, Any]:
    explicit = args.config or os.getenv("MATRIX_MATERIAL_LIBRARY_CONFIG")
    config_path = Path(explicit).expanduser() if explicit else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        if explicit:
            raise RuntimeError(f"Material-library config not found: {config_path}")
        return {}
    try:
        profile = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read material-library config: {config_path}: {exc}") from exc
    if not isinstance(profile, dict):
        raise RuntimeError("Material-library config must contain a JSON object")
    forbidden = {"password", "ssh_password", "private_key", "private_key_data"}
    if forbidden.intersection(profile):
        raise RuntimeError("Material-library config must not contain passwords or private keys")
    return profile


def normalize_source(
    local_value: str | None,
    host: str | None,
    user: str | None,
    remote_root: str | None,
) -> tuple[Path | None, str | None, str | None]:
    if local_value:
        root = Path(local_value).expanduser().resolve()
        return root, None, None
    if not host or not remote_root:
        raise RuntimeError(
            "Set --root, configure SSH host and remote_root, or create the per-user connection profile"
        )
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", host):
        raise RuntimeError("SSH host contains unsupported characters")
    if user and not re.fullmatch(r"[A-Za-z0-9._-]+", user):
        raise RuntimeError("SSH user contains unsupported characters")
    if not PurePosixPath(remote_root).is_absolute():
        raise RuntimeError("Remote library root must be an absolute POSIX path")
    return None, f"{user}@{host}" if user else host, remote_root.rstrip("/")


def source_config(args: argparse.Namespace) -> tuple[Path | None, str | None, str | None]:
    profile = read_connection_profile(args)
    return normalize_source(
        args.root or os.getenv("MATRIX_MATERIAL_LIBRARY_ROOT") or profile.get("root"),
        args.host or os.getenv("MATRIX_MATERIAL_LIBRARY_HOST") or profile.get("host"),
        args.user or os.getenv("MATRIX_MATERIAL_LIBRARY_USER") or profile.get("user"),
        args.remote_root
        or os.getenv("MATRIX_MATERIAL_LIBRARY_REMOTE_ROOT")
        or profile.get("remote_root"),
    )


def remote_cat(target: str, path: str) -> bytes:
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("ssh is required for remote material-library access")
    result = subprocess.run(
        [ssh, target, f"cat -- {shlex.quote(path)}"],
        capture_output=True,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"Could not read remote material-library file: {details}")
    return result.stdout


def read_index_from_source(
    source: tuple[Path | None, str | None, str | None]
) -> list[dict[str, Any]]:
    local_root, target, remote_root = source
    if local_root:
        index_path = local_root / "index.jsonl"
        try:
            payload = index_path.read_bytes()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Material index not found: {index_path}") from exc
    else:
        assert target and remote_root
        payload = remote_cat(target, f"{remote_root}/index.jsonl")
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(payload.decode("utf-8-sig").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid index.jsonl line {line_number}: {exc}") from exc
        if isinstance(record, dict):
            records.append(record)
    if not records:
        raise RuntimeError("Material index is empty")
    return records


def read_index(args: argparse.Namespace) -> tuple[list[dict[str, Any]], tuple[Path | None, str | None, str | None]]:
    source = source_config(args)
    return read_index_from_source(source), source


def orientation(record: dict[str, Any]) -> str:
    explicit = str(record.get("画面方向") or "").strip()
    if explicit:
        return explicit
    try:
        width = float(record.get("宽度") or 0)
        height = float(record.get("高度") or 0)
    except (TypeError, ValueError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    if abs(width - height) / max(width, height) < 0.08:
        return "方形"
    return "竖屏" if height > width else "横屏"


def query_terms(value: str) -> list[str]:
    terms = [item.lower() for item in re.split(r"[\s,，、;；|/]+", value) if item.strip()]
    return list(dict.fromkeys(terms))


def search_score(record: dict[str, Any], terms: list[str]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for term in terms:
        term_score = 0
        for field, weight in SEARCH_FIELDS.items():
            value = str(record.get(field) or "").lower()
            if term in value:
                term_score += weight
        if term_score:
            matched.append(term)
            score += term_score
    if terms and len(matched) == len(terms):
        score += 5
    return score, matched


def safe_relative_path(record: dict[str, Any]) -> PurePosixPath:
    raw = str(record.get("server_relative_path") or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe server_relative_path in record {record.get('record_id')}")
    return path


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ok": True,
        "total": len(records),
        "types": dict(Counter(str(item.get("素材类型") or "未分类") for item in records)),
        "statuses": dict(Counter(str(item.get("状态") or "未设置") for item in records)),
        "orientations": dict(Counter(orientation(item) or "未设置" for item in records)),
    }


def inspect_command(args: argparse.Namespace) -> dict[str, Any]:
    records, _ = read_index(args)
    return summarize_records(records)


def connect_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.root and (args.user or args.remote_root):
        raise RuntimeError("--user and --remote-root may only be used with --host")
    if args.host and not args.remote_root:
        raise RuntimeError("--remote-root is required with --host")
    source = normalize_source(args.root, args.host, args.user, args.remote_root)
    records = read_index_from_source(source)
    local_root, _, remote_root = source
    if local_root:
        profile = {"root": str(local_root)}
        source_kind = "local"
    else:
        profile = {"host": args.host, "remote_root": remote_root}
        if args.user:
            profile["user"] = args.user
        source_kind = "ssh"

    profile_path = args.profile.expanduser().resolve()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = profile_path.with_name(f"{profile_path.name}.tmp")
    temporary_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_path, profile_path)

    result = summarize_records(records)
    result.update(
        {
            "connected": True,
            "source": source_kind,
            "profile": str(profile_path),
        }
    )
    return result


def search_command(args: argparse.Namespace) -> dict[str, Any]:
    records, _ = read_index(args)
    terms = query_terms(args.query)
    if not terms:
        raise RuntimeError("Search query must contain at least one keyword")
    ranked: list[tuple[int, dict[str, Any], list[str]]] = []
    for record in records:
        if args.status != "any" and str(record.get("状态") or "") != args.status:
            continue
        if args.type and str(record.get("素材类型") or "") != args.type:
            continue
        if args.orientation and orientation(record) != args.orientation:
            continue
        score, matched = search_score(record, terms)
        if score > 0:
            ranked.append((score, record, matched))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("素材名称") or "")))
    results = []
    for score, record, matched in ranked[: max(1, min(100, args.limit))]:
        results.append(
            {
                "record_id": record.get("record_id"),
                "name": record.get("素材名称"),
                "type": record.get("素材类型"),
                "status": record.get("状态"),
                "orientation": orientation(record),
                "category": [record.get("一级场景"), record.get("二级场景")],
                "tags": record.get("标签"),
                "usage": record.get("使用环节"),
                "mood": record.get("情绪氛围"),
                "duration_seconds": record.get("时长秒"),
                "relative_path": record.get("server_relative_path"),
                "score": score,
                "matched_terms": matched,
            }
        )
    return {"ok": True, "query": args.query, "count": len(results), "results": results}


def fetch_command(args: argparse.Namespace) -> dict[str, Any]:
    records, source = read_index(args)
    record = next((item for item in records if str(item.get("record_id") or "") == args.record_id), None)
    if not record:
        raise RuntimeError(f"record_id not found: {args.record_id}")
    if args.status != "any" and str(record.get("状态") or "") != args.status:
        raise RuntimeError(
            f"Material status is {record.get('状态')!r}; required status is {args.status!r}"
        )
    relative = safe_relative_path(record)
    destination_dir = args.destination.expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / relative.name
    local_root, target, remote_root = source
    if local_root:
        source_path = (local_root / Path(*relative.parts)).resolve()
        try:
            source_path.relative_to(local_root)
        except ValueError as exc:
            raise RuntimeError(f"Material path escapes library root: {source_path}") from exc
        if not source_path.is_file():
            raise RuntimeError(f"Indexed material file is missing: {source_path}")
        shutil.copy2(source_path, destination)
    else:
        assert target and remote_root
        payload = remote_cat(target, f"{remote_root}/{relative.as_posix()}")
        destination.write_bytes(payload)
    return {
        "ok": True,
        "record_id": args.record_id,
        "status": record.get("状态"),
        "source_relative_path": relative.as_posix(),
        "destination": str(destination),
        "size_bytes": destination.stat().st_size,
    }


def main() -> int:
    args = parse_args()
    if args.command == "connect":
        result = connect_command(args)
    elif args.command == "inspect":
        result = inspect_command(args)
    elif args.command == "search":
        result = search_command(args)
    else:
        result = fetch_command(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:3000]}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
