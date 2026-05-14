"""中文说明：测试 N8B candidate factor diagnostic boundary 审计入口。"""

import subprocess
import sys


def test_audit_fgo_candidate_factor_boundaries_n8b() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_candidate_factor_boundaries_n8b.py"], check=True)
