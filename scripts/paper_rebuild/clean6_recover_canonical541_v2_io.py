#!/usr/bin/env python3
"""Run the explicitly authorized controller I/O recovery entrypoint."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean6_canonical_v2.io_recovery import main

if __name__ == '__main__':
    raise SystemExit(main())
