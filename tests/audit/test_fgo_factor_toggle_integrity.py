"""Audit test for N8C2 factor toggle integrity.

中文说明：运行 factor toggle integrity 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_factor_toggle_integrity() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_factor_toggle_integrity.py"], check=True)
