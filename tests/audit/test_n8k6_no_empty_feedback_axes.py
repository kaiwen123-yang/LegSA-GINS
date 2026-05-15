import subprocess
import sys

# 中文说明：N8K6 不能产生空 feedback 坐标轴回归。


def test_audit_n8k6_no_empty_feedback_axes_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_empty_feedback_axes.py"], check=True)
