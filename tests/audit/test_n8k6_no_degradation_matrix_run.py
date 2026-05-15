import subprocess
import sys

# 中文说明：N8K6 测试确认没有运行退化矩阵。


def test_audit_n8k6_no_degradation_matrix_run_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_no_degradation_matrix_run.py"], check=True)
