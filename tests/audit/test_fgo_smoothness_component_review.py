"""Audit test for N8C2 smoothness component review.

中文说明：运行 smoothness component 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_smoothness_component_review() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_smoothness_component_review.py"], check=True)
