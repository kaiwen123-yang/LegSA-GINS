"""Audit test for N8J no output substitution.

中文说明：N8J feedback 不允许直接替换 NAV。
"""

import subprocess
import sys


def test_audit_n8j_no_output_substitution():
    subprocess.run([sys.executable, "scripts/audit_n8j_no_output_substitution.py"], check=True)
