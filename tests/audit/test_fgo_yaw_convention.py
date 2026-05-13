"""中文说明：测试 yaw convention 审计脚本入口。"""

import subprocess
import sys


def test_audit_fgo_yaw_convention() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_yaw_convention.py"], check=True)
