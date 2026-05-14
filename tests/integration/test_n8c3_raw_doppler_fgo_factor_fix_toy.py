"""Integration toy test for N8C3 Raw Doppler factor fix.

中文说明：复用 N8C3 audit runner，验证 toy runtime 可完整生成报告。
"""

import subprocess
import sys


def test_n8c3_raw_doppler_fgo_factor_fix_toy() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8c3_raw_doppler_fgo_factor_fix.py", "--skip-hygiene"], check=True)
