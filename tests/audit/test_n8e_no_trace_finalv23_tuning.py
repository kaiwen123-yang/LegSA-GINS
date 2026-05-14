"""Audit test for N8E no trace/final_v23 tuning.

中文说明：运行 N8E 禁用 trace/final_v23 调权审计入口。
"""

import subprocess
import sys


def test_audit_n8e_no_trace_finalv23_tuning() -> None:
    subprocess.run([sys.executable, "scripts/audit_n8e_no_trace_finalv23_tuning.py"], check=True)
