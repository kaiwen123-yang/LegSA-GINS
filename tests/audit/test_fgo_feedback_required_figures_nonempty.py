"""Audit wrapper for N8H required figures.

中文说明：通过脚本审计 N8H 必需图像非空。
"""

import subprocess
import sys


def test_fgo_feedback_required_figures_nonempty_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_required_figures_nonempty.py"], check=True)
