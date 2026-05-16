#!/usr/bin/env python3
"""N9A_R2 consistency STD requirement audit.

中文说明：委托共享审计入口检查一致性图必须来自 STD/covariance。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("consistency_requires_std"))
