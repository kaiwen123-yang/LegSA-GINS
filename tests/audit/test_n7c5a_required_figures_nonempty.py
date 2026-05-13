"""Audit test wrapper for N7C5A figure coverage.

中文说明：pytest 包装 N7C5A 必需图像非空审计。
"""

import subprocess
import sys


def test_n7c5a_required_figures_nonempty_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c5a_required_figures_nonempty.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
