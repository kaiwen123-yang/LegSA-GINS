import subprocess
import sys

# 中文说明：N8K5 不做 paper performance claim。


def test_audit_n8k5_no_performance_claim():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_performance_claim.py"], check=True)
