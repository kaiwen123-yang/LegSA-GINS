import subprocess
import sys

# 中文说明：N8K6 A0 feedback applicability 审计脚本 toy fallback 必须通过。


def test_audit_n8k6_a0_feedback_applicability_toy():
    subprocess.run([sys.executable, "scripts/audit_n8k6_a0_feedback_applicability.py"], check=True)
