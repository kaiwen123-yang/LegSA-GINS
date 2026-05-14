"""Audit test for N8C3 Raw Doppler factor fix.

中文说明：运行 N8C3 toy 审计入口。
"""

import subprocess
import sys


def test_audit_n8c3_raw_doppler_fgo_factor_fix() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8c3_raw_doppler_fgo_factor_fix.py"], check=True)
