import subprocess
import sys

# 中文说明：N8K6 测试确认没有算法改动声明。


def test_audit_n8k6_no_algorithm_change_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_algorithm_change.py"], check=True)
