#!/usr/bin/env python3
"""Finalize sealed P-13 tables and handoff; no native/evaluator/provider calls."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from legsa_gins.paper_rebuild.clean6_sensor_v21.finalize import main

if __name__ == '__main__':
    main()
