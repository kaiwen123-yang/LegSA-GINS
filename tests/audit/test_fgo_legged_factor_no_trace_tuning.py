"""Audit test for N8F no trace/final_v23 tuning.

中文说明：运行 trace/final_v23 不调权审计。
"""

import subprocess
import sys


def test_audit_fgo_legged_factor_no_trace_tuning() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_legged_factor_no_trace_tuning.py"], check=True)
