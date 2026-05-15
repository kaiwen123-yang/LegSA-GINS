"""Audit test for N8I feedback ablation reports.

中文说明：通过 toy 审计入口验证 N8I 报告合同。
"""

import subprocess
import sys


def test_audit_n8i_feedback_ablation_gate_covariance():
    subprocess.run([sys.executable, "scripts/audit_n8i_feedback_ablation_gate_covariance.py"], check=True)
