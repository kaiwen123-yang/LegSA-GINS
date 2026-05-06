#!/usr/bin/env python3
"""N0 claim-boundary audit."""

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
