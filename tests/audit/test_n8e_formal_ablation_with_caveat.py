"""Audit test for N8E formal ablation with caveat.

中文说明：运行 N8E toy 审计入口。
"""

import subprocess
import sys


def test_audit_n8e_formal_ablation_with_caveat() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_formal_ablation_with_caveat.py"], check=True)
