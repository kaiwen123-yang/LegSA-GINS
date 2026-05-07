#!/usr/bin/env python3
"""Audit that raw data files are not present in the working tree.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from pathlib import Path
import sys


FORBIDDEN_EXTENSIONS = {
    ".bag",
    ".ubx",
    ".obs",
    ".nav",
    ".rnx",
    ".rtcm",
    ".bin",
    ".raw",
    ".pcap",
}

SKIP_DIRS = {".git", "__pycache__"}


def find_forbidden_files(root: Path) -> list[Path]:
    forbidden: list[Path] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            forbidden.append(path.relative_to(root))
    return sorted(forbidden)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    forbidden = find_forbidden_files(root)
    if forbidden:
        print("Raw data audit failed. Forbidden files found:")
        for path in forbidden:
            print(f"- {path}")
        return 1
    print("Raw data audit passed. No forbidden raw-data files found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
