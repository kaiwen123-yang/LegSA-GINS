"""中文说明：测试 N8C no-feedback visual boundary 审计入口。"""

import subprocess
import sys


def test_audit_fgo_no_feedback_visual_boundary() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_no_feedback_visual_boundary.py"], check=True)
