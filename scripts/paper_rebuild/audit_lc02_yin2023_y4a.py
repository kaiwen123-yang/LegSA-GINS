#!/usr/bin/env python3
"""CLI bridge for bounded LC02 Yin-2023 Y4A source closure."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from legsa_gins.paper_rebuild.horizontal_literature.lc02_y4a_reproducibility_closure import main


if __name__ == "__main__":
    raise SystemExit(main())
