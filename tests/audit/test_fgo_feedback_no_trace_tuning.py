"""中文说明：审计 N8G 不用 trace/final_v23 调反馈参数。"""

import subprocess
import sys


def test_fgo_feedback_no_trace_tuning_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_no_trace_tuning.py"], check=True)
