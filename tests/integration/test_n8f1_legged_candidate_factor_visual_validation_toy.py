"""Integration toy for N8F1 visual validation.

中文说明：通过 toy runtime 验证 N8F1 runner 全链路。
"""

import subprocess
import sys


def test_n8f1_legged_candidate_factor_visual_validation_toy() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_legged_candidate_factor_visual_validation.py"], check=True)

