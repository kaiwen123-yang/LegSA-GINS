import subprocess
import sys

# 中文说明：feedback applicability 必须按 spec role 判定。


def test_audit_n8k6_feedback_applicability_by_spec_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_feedback_applicability_by_spec.py"], check=True)
