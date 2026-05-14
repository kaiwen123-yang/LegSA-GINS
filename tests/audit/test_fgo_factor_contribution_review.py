"""中文说明：测试 N8C factor contribution 审计入口。"""

import subprocess
import sys


def test_audit_fgo_factor_contribution_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_factor_contribution_review.py"], check=True)
