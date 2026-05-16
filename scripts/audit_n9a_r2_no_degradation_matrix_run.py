#!/usr/bin/env python3
"""N9A_R2 no-degradation-matrix audit.

中文说明：委托共享审计入口确认本阶段没有运行 N9B 退化矩阵。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("no_degradation_matrix_run"))
