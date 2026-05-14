"""中文说明：测试 N8A2 runner 审计入口。"""

import subprocess
import sys


def test_audit_n8a2_fgo_yaw_convention_fix() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8a2_fgo_yaw_convention_fix.py"], check=True)
