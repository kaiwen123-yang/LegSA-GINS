"""Audit test for real Raw Doppler toggle.

中文说明：运行 raw_doppler_off 真实 toggle 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_raw_doppler_toggle_real() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_raw_doppler_toggle_real.py"], check=True)
