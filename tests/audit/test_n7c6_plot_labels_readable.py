import subprocess
import sys


def test_audit_n7c6_plot_labels_readable() -> None:
    """中文说明：验证长 variant label 的可读性审计。"""
    subprocess.run([sys.executable, "scripts/audit_n7c6_plot_labels_readable.py"], check=True)
