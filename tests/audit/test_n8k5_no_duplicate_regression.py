import subprocess
import sys

# 中文说明：N8K5 不允许 duplicate regression。


def test_audit_n8k5_no_duplicate_regression():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_duplicate_regression.py"], check=True)
