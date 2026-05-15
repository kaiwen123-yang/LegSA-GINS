import subprocess
import sys

# 中文说明：feedback delta compare 不能复用 observation quality timeline。


def test_audit_n8k5_feedback_compare_semantics():
    subprocess.run([sys.executable, "scripts/audit_n8k5_feedback_compare_semantics.py"], check=True)
