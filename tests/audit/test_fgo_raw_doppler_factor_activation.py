"""Audit test for N8C2 raw Doppler factor activation.

中文说明：运行 Raw Doppler activation 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_raw_doppler_factor_activation() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_raw_doppler_factor_activation.py"], check=True)
