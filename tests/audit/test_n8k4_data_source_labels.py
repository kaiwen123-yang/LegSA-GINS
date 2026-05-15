import subprocess
import sys

# 中文说明：derived/surrogate 数据来源标签必须存在。


def test_n8k4_data_source_labels_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_data_source_labels.py"], check=True)
