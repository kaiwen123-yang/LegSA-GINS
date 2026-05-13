import subprocess
import sys


def test_audit_fgo_no_trace_or_finalv23_input() -> None:
    """中文说明：验证 trace/final_v23 不作为 FGO factor 输入。"""
    subprocess.run([sys.executable, "scripts/audit_fgo_no_trace_or_finalv23_input.py"], check=True)
