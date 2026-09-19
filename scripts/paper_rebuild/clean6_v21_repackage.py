#!/usr/bin/env python3
"""Continue only P13 packaging from the sealed finalization source ledger."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean6_sensor_v21.repackage import main

if __name__ == '__main__':
    main()
