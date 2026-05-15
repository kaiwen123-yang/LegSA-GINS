"""Audit wrapper for N8H visual validation.

中文说明：通过脚本审计 N8H 图像验证报告。
"""

import subprocess
import sys


def test_n8h_fgo_feedback_visual_validation_audit():
    subprocess.run([sys.executable, "scripts/audit_n8h_fgo_feedback_visual_validation.py"], check=True)
