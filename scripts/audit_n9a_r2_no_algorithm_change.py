#!/usr/bin/env python3
"""N9A_R2 no-algorithm-change audit.

中文说明：委托共享审计入口确认本阶段没有改算法文件。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("no_algorithm_change"))
