"""Audit test for no smoothness deletion shortcut.

中文说明：删除 smoothness 只能是 diagnostic-only。
"""

import subprocess
import sys


def test_audit_fgo_no_smoothness_deletion_shortcut() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_no_smoothness_deletion_shortcut.py"], check=True)
