"""中文说明：测试 N8C runner 审计入口。"""

import subprocess
import sys


def test_audit_n8c_no_feedback_fgo_visual_validation() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8c_no_feedback_fgo_visual_validation.py"], check=True)
