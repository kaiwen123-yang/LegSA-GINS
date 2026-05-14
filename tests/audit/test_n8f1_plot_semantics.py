"""Audit test for N8F1 plot semantics.

中文说明：运行 N8F1 plot semantic guard 审计。
"""

import subprocess
import sys


def test_audit_n8f1_plot_semantics() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_plot_semantics.py"], check=True)

