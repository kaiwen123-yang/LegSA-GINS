"""中文说明：测试 N8A1 visual yaw delta 审计脚本入口。"""

import subprocess
import sys


def test_audit_fgo_visual_yaw_delta() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_visual_yaw_delta.py"], check=True)
