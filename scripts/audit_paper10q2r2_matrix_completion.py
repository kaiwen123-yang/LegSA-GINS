#!/usr/bin/env python3
"""Audit Q2R2 matrix completion status."""

import csv
from pathlib import Path


def main(stage_root: str) -> int:
    path = Path(stage_root, "05_EXECUTION", "PAPER10Q2R2_ROW_EXECUTION_STATUS.csv")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 600:
        raise SystemExit(f"expected 600 planned rows, got {len(rows)}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1]))
