"""Audit test for N8E no performance claim.

中文说明：运行 N8E 无性能 claim 审计入口。
"""

import subprocess
import sys


def test_audit_n8e_no_performance_claim() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_no_performance_claim.py"], check=True)
