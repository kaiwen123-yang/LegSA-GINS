#!/usr/bin/env python3
"""V3-01-R append-only continuation with G-only compact runtime archives."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.protocol_v3.resume_storage import main

if __name__ == "__main__":
    main()
