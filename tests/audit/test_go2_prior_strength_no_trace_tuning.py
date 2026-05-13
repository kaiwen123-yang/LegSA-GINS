"""中文说明：审计测试确认 N7C4 prior 强度扫描没有 trace/final_v23 调参路径。"""

import subprocess
import sys


def test_go2_prior_strength_no_trace_tuning_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_prior_strength_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
