"""Audit test for N8F1 visual validation.

中文说明：运行 N8F1 总体 toy 审计。
"""

import subprocess
import sys


def test_audit_n8f1_legged_candidate_factor_visual_validation() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py"], check=True)

