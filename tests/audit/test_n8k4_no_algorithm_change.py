import subprocess
import sys

# 中文说明：N8K4 测试确认没有算法改动声明。


def test_n8k4_no_algorithm_change_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_algorithm_change.py"], check=True)
