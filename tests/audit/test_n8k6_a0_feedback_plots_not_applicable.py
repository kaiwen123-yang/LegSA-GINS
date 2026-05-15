import subprocess
import sys

# 中文说明：A0 feedback-specific 图必须记录为 not-applicable。


def test_audit_n8k6_a0_feedback_plots_not_applicable_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_a0_feedback_plots_not_applicable.py"], check=True)
