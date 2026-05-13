import subprocess
import sys


def test_audit_fgo_no_feedback_boundary() -> None:
    """中文说明：验证 FGO 无反馈边界。"""
    subprocess.run([sys.executable, "scripts/audit_fgo_no_feedback_boundary.py"], check=True)
