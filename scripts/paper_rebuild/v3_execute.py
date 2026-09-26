#!/usr/bin/env python3
"""Frozen protocol v3 preparation, identity gates, and complete matrix."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.protocol_v3.controller import main
if __name__ == '__main__':
    main()
