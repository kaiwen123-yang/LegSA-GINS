"""中文说明：测试 N8A2 不是 output-only yaw 修正。"""

import subprocess
import sys


def test_audit_fgo_no_output_only_yaw_fix() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_no_output_only_yaw_fix.py"], check=True)
