#!/usr/bin/env python3
"""Audit Q2R2 claim boundary files."""

from pathlib import Path


def main(stage_root: str) -> int:
    forbidden = Path(stage_root, "08_CLAIM_BOUNDARY", "Q2R2_FORBIDDEN_CLAIMS.md").read_text(encoding="utf-8")
    for token in ["exact reproduction", "universal superiority", "BY3 yaw generalization", "XB high-precision severe-GNSS"]:
        if token not in forbidden:
            raise SystemExit(f"missing forbidden token: {token}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1]))
