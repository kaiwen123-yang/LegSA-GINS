import subprocess
import sys

# 中文说明：N8K5 不运行退化矩阵。


def test_audit_n8k5_no_degradation_matrix_run():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_degradation_matrix_run.py"], check=True)
