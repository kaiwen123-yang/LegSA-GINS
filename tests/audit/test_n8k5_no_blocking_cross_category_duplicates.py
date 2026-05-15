import subprocess
import sys

# 中文说明：阻塞跨类别 duplicate 必须清零。


def test_audit_n8k5_no_blocking_cross_category_duplicates():
    subprocess.run([sys.executable, "scripts/audit_n8k5_no_blocking_cross_category_duplicates.py"], check=True)
