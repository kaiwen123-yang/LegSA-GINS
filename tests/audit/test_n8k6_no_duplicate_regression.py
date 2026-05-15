import subprocess
import sys

# 中文说明：N8K6 不能重新引入 duplicate regression。


def test_audit_n8k6_no_duplicate_regression_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_duplicate_regression.py"], check=True)
