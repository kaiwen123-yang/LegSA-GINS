"""Audit test for no trace tuning in N8D.

中文说明：权重策略不能使用 trace 调参。
"""

import subprocess
import sys


def test_audit_fgo_weight_policy_no_trace_tuning() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_weight_policy_no_trace_tuning.py"], check=True)
