"""Audit test for N8F legged factor Jacobian contracts.

中文说明：运行足式候选因子 Jacobian 合同审计。
"""

import subprocess
import sys


def test_audit_fgo_legged_factor_jacobian_contracts() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_legged_factor_jacobian_contracts.py"], check=True)
