#!/usr/bin/env python3
"""N9A_R2 compare-output requirement audit.

中文说明：委托共享审计入口检查比较图必须有足够真实算法输出。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("compare_requires_algorithm_outputs"))
