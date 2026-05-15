"""Audit test for N8I gate not over-loose.

中文说明：default gate 全接受且有 spike 时，必须给出保守 gate 或阻断决策。
"""

import subprocess
import sys


def test_audit_fgo_feedback_gate_not_overloose():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_gate_not_overloose.py"], check=True)
