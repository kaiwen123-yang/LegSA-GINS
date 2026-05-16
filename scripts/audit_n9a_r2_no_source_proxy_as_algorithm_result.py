#!/usr/bin/env python3
"""N9A_R2 source/proxy exclusion audit.

中文说明：委托共享审计入口防止 source/proxy 被当成算法结果。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("no_source_proxy_as_algorithm_result"))
