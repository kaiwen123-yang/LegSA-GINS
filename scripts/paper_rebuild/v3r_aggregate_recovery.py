#!/usr/bin/env python3
"""Recover final protocol-v3 reports from sealed ledgers; zero scientific calls."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.protocol_v3.aggregate_recovery import main

if __name__ == "__main__":
    raise SystemExit(main())
