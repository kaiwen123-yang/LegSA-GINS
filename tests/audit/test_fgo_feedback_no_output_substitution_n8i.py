"""Audit test for N8I no output substitution.

中文说明：N8I feedback 仍必须进入 EKF update，不能直接覆盖 NAV。
"""

import subprocess
import sys


def test_audit_fgo_feedback_no_output_substitution_n8i():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_no_output_substitution_n8i.py"], check=True)
