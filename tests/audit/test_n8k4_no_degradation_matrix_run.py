import subprocess
import sys

# 中文说明：N8K4 测试确认没有运行退化矩阵。


def test_n8k4_no_degradation_matrix_run_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_degradation_matrix_run.py"], check=True)
