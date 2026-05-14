"""Audit test for Raw Doppler solver residual injection.

中文说明：运行 Raw Doppler solver residual 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_raw_doppler_solver_residual() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_raw_doppler_solver_residual.py"], check=True)
