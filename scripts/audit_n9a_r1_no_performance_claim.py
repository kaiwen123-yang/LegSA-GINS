#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# 中文说明：N9A_R1 claim 审计只允许边界说明，不允许论文性能结论。

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.n9a_r1_audit_checks import main

if __name__ == "__main__":
    raise SystemExit(main("no_performance_claim"))
