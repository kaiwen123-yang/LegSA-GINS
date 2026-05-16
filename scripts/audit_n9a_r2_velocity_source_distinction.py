#!/usr/bin/env python3
"""N9A_R2 velocity-source distinction audit.

中文说明：委托共享审计入口检查速度来源不能混成同一条 proxy。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("velocity_source_distinction"))
