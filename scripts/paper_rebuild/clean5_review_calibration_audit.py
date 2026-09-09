#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from legsa_gins.paper_rebuild.clean5_calibrated.audit_recovery import main
if __name__ == '__main__':
    raise SystemExit(main())
