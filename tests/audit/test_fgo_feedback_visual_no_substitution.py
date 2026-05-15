"""Audit wrapper for N8H visual no-substitution guard.

中文说明：通过脚本审计图像和 hook 均非 output substitution。
"""

import subprocess
import sys


def test_fgo_feedback_visual_no_substitution_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_visual_no_substitution.py"], check=True)
