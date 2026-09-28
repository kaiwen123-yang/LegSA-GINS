#!/usr/bin/env python3
"""Single-purpose Canonical-541 evaluation-only entry point."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legsa_gins.paper_rebuild.canonical541.offline_eval_aggregate import main


if __name__ == "__main__":
    raise SystemExit(main())
