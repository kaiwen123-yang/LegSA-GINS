"""中文说明：测试 N8B no trace/final_v23 tuning 审计入口。"""

import subprocess
import sys


def test_audit_fgo_policy_no_trace_tuning() -> None:
    subprocess.run([sys.executable, "scripts/audit_fgo_policy_no_trace_tuning.py"], check=True)
