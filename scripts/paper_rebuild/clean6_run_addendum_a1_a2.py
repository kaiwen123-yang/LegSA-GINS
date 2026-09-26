#!/usr/bin/env python3
"""Invoke the preregistered addendum without modifying or rerunning the core."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean6_addendum.runner import main

if __name__ == '__main__':
    raise SystemExit(main())
