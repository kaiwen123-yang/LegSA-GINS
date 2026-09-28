#!/usr/bin/env python3
"""Render the protocol-v2 publication registry from the sealed combined handoff."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.publication.protocol_v2_render import main

if __name__ == "__main__":
    raise SystemExit(main())
