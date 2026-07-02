#!/usr/bin/env python3
"""Audit that Q2R2 blocked rows are not promoted to main-text claims."""

from pathlib import Path


def main(stage_root: str) -> int:
    text = Path(stage_root, "03_METHOD_SELECTION", "DUAL_METHOD_SELECTED_3_TO_5.csv").read_text(encoding="utf-8")
    if "PAPER_DERIVED_POLICY_BASELINE,true" in text:
        raise SystemExit("policy baseline promoted")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1]))
