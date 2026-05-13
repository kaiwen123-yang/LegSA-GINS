"""中文说明：测试 N8A1 runner 审计脚本。"""

import subprocess
import sys


def test_audit_n8a1_fgo_yaw_delta_policy_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8a1_fgo_yaw_delta_policy_review.py"], check=True)
