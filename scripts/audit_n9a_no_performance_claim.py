#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# 中文说明：N9A 声明边界审计禁止论文性能和 outperform final_v23 声明。

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.reporting.n9a_audit_checks import main

if __name__ == "__main__":
    raise SystemExit(main("no_performance_claim"))
