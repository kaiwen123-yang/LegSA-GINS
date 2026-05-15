import subprocess
import sys

# 中文说明：N8K5 不改算法。


def test_audit_n8k5_no_algorithm_change():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_algorithm_change.py"], check=True)
