import subprocess
import sys

# 中文说明：compare 与 reject-all 语义不能互相占用文件名。


def test_n8k4_compare_feedback_semantics_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_compare_feedback_semantics.py"], check=True)
