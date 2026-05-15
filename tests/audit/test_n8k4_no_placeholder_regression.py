import subprocess
import sys

# 中文说明：N8K4 不能让 applicable placeholder 回归。


def test_n8k4_no_placeholder_regression_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_placeholder_regression.py"], check=True)
