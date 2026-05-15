"""Audit test for N8J runtime output boundary.

中文说明：runtime NAV/STD/EVAL/RUN_MANIFEST 生成但不提交。
"""

import subprocess
import sys


def test_audit_n8j_runtime_outputs_boundary():
    subprocess.run([sys.executable, "scripts/audit_n8j_runtime_outputs_boundary.py"], check=True)
