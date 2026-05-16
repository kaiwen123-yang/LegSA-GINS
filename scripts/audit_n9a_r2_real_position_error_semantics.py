#!/usr/bin/env python3
"""N9A_R2 position-error semantics audit.

中文说明：委托共享审计入口检查位置误差必须来自真实 EVAL/NAV。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("real_position_error_semantics"))
