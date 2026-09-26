#!/usr/bin/env python3
"""Run the preregistered P-09c protocol from the active code freeze."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean6_canonical_v2.runner import main
if __name__ == '__main__':
    raise SystemExit(main())
