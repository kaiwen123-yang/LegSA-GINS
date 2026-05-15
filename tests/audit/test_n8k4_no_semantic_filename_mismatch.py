import subprocess
import sys

# 中文说明：semantic filename mismatch 修复后必须清零。


def test_n8k4_no_semantic_filename_mismatch_audit_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k4_no_semantic_filename_mismatch.py"], check=True)
