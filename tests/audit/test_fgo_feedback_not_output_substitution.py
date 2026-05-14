"""中文说明：审计 FGO feedback 不是 output-only correction 或 NAV 覆盖。"""

import subprocess
import sys


def test_fgo_feedback_not_output_substitution_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_not_output_substitution.py"], check=True)
