#!/usr/bin/env python3
"""N0 claim-boundary audit.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from pathlib import Path
import sys


REQUIRED_STRINGS = [
    "Forbidden Phase-I Claims",
    "evidence_missing",
    "RTK fixed",
    "FGO feedback",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    claim_boundary = root / "CLAIM_BOUNDARY.md"
    if not claim_boundary.exists():
        print("Claim boundary audit failed. CLAIM_BOUNDARY.md is missing.")
        return 1

    text = claim_boundary.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED_STRINGS if item not in text]
    if missing:
        print("Claim boundary audit failed. Missing required strings:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("Claim boundary audit passed. Required N0 boundary strings are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
