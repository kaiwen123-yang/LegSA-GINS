#!/usr/bin/env python3
"""Export the 28 protocol-v2.1 figures from the sealed P13 handoff."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.publication.protocol_v21_render import main

if __name__ == '__main__':
    raise SystemExit(main())
