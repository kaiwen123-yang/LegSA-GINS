"""Audit test that N8C2 candidate contribution is not fabricated.

中文说明：运行候选因子贡献不伪造审计入口。
"""

import subprocess
import sys


def test_audit_fgo_factor_contribution_not_fabricated() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_factor_contribution_not_fabricated.py"], check=True)
