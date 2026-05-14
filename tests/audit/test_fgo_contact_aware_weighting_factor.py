"""Audit test for N8F contact-aware weighting.

中文说明：运行 contact 权重层边界审计。
"""

import subprocess
import sys


def test_audit_fgo_contact_aware_weighting_factor() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_contact_aware_weighting_factor.py"], check=True)
