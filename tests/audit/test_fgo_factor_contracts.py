import subprocess
import sys


def test_audit_fgo_factor_contracts() -> None:
    """中文说明：验证 N8A factor registry 合同。"""
    subprocess.run([sys.executable, "scripts/audit_fgo_factor_contracts.py"], check=True)
