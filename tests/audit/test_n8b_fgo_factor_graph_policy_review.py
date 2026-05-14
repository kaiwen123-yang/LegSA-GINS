"""中文说明：测试 N8B runner 审计入口。"""

import subprocess
import sys


def test_audit_n8b_fgo_factor_graph_policy_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8b_fgo_factor_graph_policy_review.py"], check=True)
