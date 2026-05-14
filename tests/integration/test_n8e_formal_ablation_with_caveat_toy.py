"""Integration toy test for N8E formal ablation with caveat.

中文说明：复用 toy 审计确认 runtime 报告和图像能生成。
"""

import subprocess
import sys


def test_n8e_formal_ablation_with_caveat_toy() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_formal_ablation_with_caveat.py", "--skip-hygiene"], check=True)
