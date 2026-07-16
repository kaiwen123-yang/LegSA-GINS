#!/usr/bin/env python3
"""CLI wrapper for CLEAN1R2R1 exact-tag/active-port clean parity."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.final_v23_clean_parity import main


if __name__ == "__main__":
    raise SystemExit(main())
