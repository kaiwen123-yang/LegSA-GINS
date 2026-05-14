"""中文说明：审计 feedback window 不使用未来数据。"""

import subprocess
import sys


def test_fgo_feedback_no_future_data_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_no_future_data.py"], check=True)
