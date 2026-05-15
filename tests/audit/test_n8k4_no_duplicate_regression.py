import subprocess
import sys

# 中文说明：N8K4 不能因语义修复重新引入 duplicate。


def test_n8k4_no_duplicate_regression_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_duplicate_regression.py"], check=True)
