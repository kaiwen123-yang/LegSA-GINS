import subprocess
import sys


def test_audit_n7c6_ready_to_merge() -> None:
    """中文说明：验证 N7C6A ready-to-merge 决策门禁。"""
    subprocess.run([sys.executable, "scripts/audit_n7c6_ready_to_merge.py"], check=True)
