"""Audit test for Raw Doppler Jacobian contract.

中文说明：运行 Raw Doppler Jacobian contract 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_raw_doppler_jacobian_contract() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_raw_doppler_jacobian_contract.py"], check=True)
