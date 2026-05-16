#!/usr/bin/env python3
"""N9A_R2 no-placeholder audit.

中文说明：委托共享审计入口防止用文字占位图冒充 applicable figure。
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legsa_gins.reporting.n9a_r2_audit_checks import main

raise SystemExit(main("no_placeholder_for_applicable_plots"))
