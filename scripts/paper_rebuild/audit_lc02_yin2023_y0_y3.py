#!/usr/bin/env python3
"""CLI bridge for the bounded LC02 Yin-2023 Y0--Y3 audit."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from legsa_gins.paper_rebuild.horizontal_literature.lc02_y0_y3_audit import main


if __name__ == "__main__":
    raise SystemExit(main())
