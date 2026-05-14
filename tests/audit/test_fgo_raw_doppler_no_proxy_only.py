"""Audit test that Raw Doppler is not proxy-only.

中文说明：运行 Raw Doppler no-proxy-only 审计入口。
"""

import subprocess
import sys


def test_audit_fgo_raw_doppler_no_proxy_only() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_raw_doppler_no_proxy_only.py"], check=True)
