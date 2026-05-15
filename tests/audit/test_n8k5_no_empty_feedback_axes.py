import subprocess
import sys

# 中文说明：无 feedback rows 的图必须是 documented not-applicable。


def test_audit_n8k5_no_empty_feedback_axes():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_empty_feedback_axes.py"], check=True)
