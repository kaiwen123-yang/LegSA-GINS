import subprocess
import sys

# 中文说明：N8K5 不允许 placeholder regression。


def test_audit_n8k5_no_placeholder_regression():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_placeholder_regression.py"], check=True)
