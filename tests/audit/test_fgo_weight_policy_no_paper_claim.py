"""Audit test for no N8D paper claim.

中文说明：N8D 只是工程诊断。
"""

import subprocess
import sys


def test_audit_fgo_weight_policy_no_paper_claim() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_weight_policy_no_paper_claim.py"], check=True)
