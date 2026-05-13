import subprocess
import sys


def test_audit_n7c6_metric_semantics() -> None:
    """中文说明：验证 N7C6A metric namespace guard。"""
    subprocess.run([sys.executable, "scripts/audit_n7c6_metric_semantics.py"], check=True)
