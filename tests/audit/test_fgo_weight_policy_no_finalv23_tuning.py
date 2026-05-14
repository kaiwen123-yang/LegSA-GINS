"""Audit test for no final_v23 tuning in N8D.

中文说明：final_v23 不能进入权重选择。
"""

import subprocess
import sys


def test_audit_fgo_weight_policy_no_finalv23_tuning() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_weight_policy_no_finalv23_tuning.py"], check=True)
