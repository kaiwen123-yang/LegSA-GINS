#!/usr/bin/env python3
"""N9A_R2 metric-bar semantics audit.

中文说明：委托共享审计入口检查 RMSE/P95/max 必须是真柱状图。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("metric_bar_semantics"))
