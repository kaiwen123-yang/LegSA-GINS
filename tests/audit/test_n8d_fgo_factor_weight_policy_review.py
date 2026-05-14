"""Audit test for N8D factor weight policy review.

中文说明：运行 N8D toy 审计入口。
"""

import subprocess
import sys


def test_audit_n8d_fgo_factor_weight_policy_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8d_fgo_factor_weight_policy_review.py"], check=True)
