import subprocess
import sys

# 中文说明：N8K6 不能让 applicable placeholder 回归。


def test_audit_n8k6_no_placeholder_regression_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_placeholder_regression.py"], check=True)
