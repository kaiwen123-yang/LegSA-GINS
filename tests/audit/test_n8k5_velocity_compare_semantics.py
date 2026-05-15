import subprocess
import sys

# 中文说明：velocity compare 不能复用 velocity residual 图语义。


def test_audit_n8k5_velocity_compare_semantics():
    subprocess.run([sys.executable, "scripts/audit_n8k5_velocity_compare_semantics.py"], check=True)
