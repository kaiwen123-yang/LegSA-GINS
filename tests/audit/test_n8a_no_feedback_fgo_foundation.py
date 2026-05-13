import subprocess
import sys


def test_audit_n8a_no_feedback_fgo_foundation() -> None:
    """中文说明：运行 N8A foundation toy 审计。"""
    subprocess.run([sys.executable, "scripts/audit_n8a_no_feedback_fgo_foundation.py"], check=True)
