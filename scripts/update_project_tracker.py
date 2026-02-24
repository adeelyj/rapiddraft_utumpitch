#!/usr/bin/env python3
"""Append dated commit summaries to rapid_craft_project_tracker.md."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER_PATH = REPO_ROOT / "rapid_craft_project_tracker.md"
COMMIT_MARKER_RE = re.compile(r"<!--\s*commit:([0-9a-f]{40})\s*-->")
HEADER = """# Rapid Craft Project Tracker

Append-only project change tracker.
Each line below is generated from git commits and includes date + summary.

## Change Log
"""


def _run_git_log() -> list[tuple[str, str, str, str]]:
    cmd = [
        "git",
        "log",
        "--reverse",
        "--date=short",
        "--pretty=format:%H%x1f%h%x1f%ad%x1f%s",
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commits: list[tuple[str, str, str, str]] = []
    for raw_line in result.stdout.splitlines():
        full_hash, short_hash, commit_date, subject = raw_line.split("\x1f", maxsplit=3)
        commits.append((full_hash, short_hash, commit_date, subject.strip()))
    return commits


def _ensure_tracker_file() -> None:
    if TRACKER_PATH.exists():
        return
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_PATH.write_text(HEADER, encoding="utf-8", newline="\n")


def _existing_commit_hashes() -> set[str]:
    if not TRACKER_PATH.exists():
        return set()
    content = TRACKER_PATH.read_text(encoding="utf-8")
    return {match.group(1) for match in COMMIT_MARKER_RE.finditer(content)}


def _append_entries(entries: list[tuple[str, str, str, str]]) -> None:
    if not entries:
        return
    with TRACKER_PATH.open("a", encoding="utf-8", newline="\n") as tracker_file:
        if TRACKER_PATH.stat().st_size > 0:
            tracker_file.write("\n")
        for full_hash, short_hash, commit_date, subject in entries:
            tracker_file.write(f"- {commit_date} | `{short_hash}` | {subject}\n")
            tracker_file.write(f"  <!-- commit:{full_hash} -->\n")


def main() -> int:
    try:
        _ensure_tracker_file()
        existing_hashes = _existing_commit_hashes()
        new_entries = [
            commit
            for commit in _run_git_log()
            if commit[0] not in existing_hashes
        ]
        _append_entries(new_entries)
        print(
            f"Tracker updated: {len(new_entries)} entr"
            f"{'y' if len(new_entries) == 1 else 'ies'} appended."
        )
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Failed to read git history: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
