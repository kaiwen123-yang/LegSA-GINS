"""中文说明：审计测试验证 N7C5 Go2 本体候选挖掘不使用 trace/final_v23 调参。"""

import subprocess
import sys


def test_go2_proprioceptive_no_trace_tuning_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_proprioceptive_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
