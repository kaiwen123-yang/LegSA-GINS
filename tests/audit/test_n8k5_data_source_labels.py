import subprocess
import sys

# 中文说明：derived/surrogate 数据来源必须保留标签。


def test_audit_n8k5_data_source_labels():
    subprocess.run([sys.executable, "scripts/audit_n8k5_data_source_labels.py"], check=True)
