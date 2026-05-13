import subprocess
import sys


def test_audit_fgo_go2_candidate_factor_boundaries() -> None:
    """中文说明：验证 Go2 candidate factors 只保持 diagnostic。"""
    subprocess.run([sys.executable, "scripts/audit_fgo_go2_candidate_factor_boundaries.py"], check=True)
