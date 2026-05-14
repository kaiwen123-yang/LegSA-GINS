"""Audit test for N8E no feedback/substitution.

中文说明：运行 N8E 禁用 FGO 反馈/替换审计入口。
"""

import subprocess
import sys


def test_audit_n8e_no_feedback_substitution() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_no_feedback_substitution.py"], check=True)
