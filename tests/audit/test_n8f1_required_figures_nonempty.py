"""Audit test for N8F1 required figures.

中文说明：运行 N8F1 图像非空审计。
"""

import subprocess
import sys


def test_audit_n8f1_required_figures_nonempty() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8f1_required_figures_nonempty.py"], check=True)

