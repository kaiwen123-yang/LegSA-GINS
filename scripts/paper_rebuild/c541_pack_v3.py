#!/usr/bin/env python3
"""Pack the completed protocol-v2 full matrix, preserving v3/v2 identities."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.clean6_canonical_v2.pack import main

if __name__ == "__main__":
    raise SystemExit(main())
