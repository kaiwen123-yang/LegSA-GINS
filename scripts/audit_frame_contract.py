#!/usr/bin/env python3
"""Audit N2 frame convention contract files and hard-rule text.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from pathlib import Path
import sys


REQUIRED_DOC_STRINGS = [
    "Go2 body / IMU frame is FLU",
    "X forward",
    "Y left",
    "Z up",
    "Do not apply a second FLU-to-FRD transform",
]

REQUIRED_FILES = [
    "src/legsa_gins/frames/go2_adapter.py",
    "src/legsa_gins/frames/transforms.py",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    doc = root / "docs/frame_conventions.md"
    if not doc.exists():
        print("Frame contract audit failed. docs/frame_conventions.md is missing.")
        return 1

    text = doc.read_text(encoding="utf-8")
    missing_text = [item for item in REQUIRED_DOC_STRINGS if item not in text]
    missing_files = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing_text or missing_files:
        print("Frame contract audit failed.")
        if missing_text:
            print("Missing required document strings:")
            for item in missing_text:
                print(f"- {item}")
        if missing_files:
            print("Missing required files:")
            for path in missing_files:
                print(f"- {path}")
        return 1

    print("Frame contract audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
