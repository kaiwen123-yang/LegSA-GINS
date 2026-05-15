"""Audit wrapper for N8H variant ablation.

中文说明：通过脚本审计 feedback variant ablation。
"""

import subprocess
import sys


def test_fgo_feedback_variant_ablation_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_variant_ablation.py"], check=True)
