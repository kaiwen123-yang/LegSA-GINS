"""Integration toy test for N8D factor weight policy review.

中文说明：复用 audit 入口确认 runtime 报告和图像能生成。
"""

import subprocess
import sys


def test_n8d_fgo_factor_weight_policy_review_toy() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8d_fgo_factor_weight_policy_review.py", "--skip-hygiene"], check=True)
