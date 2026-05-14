"""Integration toy for N8F legged candidate factor activation.

中文说明：通过 toy runtime 验证 N8F runner 全链路。
"""

import subprocess
import sys


def test_n8f_legged_candidate_factor_activation_toy() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f_legged_candidate_factor_activation.py"], check=True)
