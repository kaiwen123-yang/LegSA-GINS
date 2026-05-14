"""中文说明：测试 yaw smoothness wrap 审计入口。"""

import subprocess
import sys


def test_audit_fgo_yaw_smoothness_wrap() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_yaw_smoothness_wrap.py"], check=True)
