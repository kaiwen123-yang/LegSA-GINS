"""Audit test wrapper for N7C6 no-trace/final_v23 tuning boundary.

中文说明：pytest 包装 N7C6 无 trace/final_v23 调参审计。
"""

import subprocess
import sys


def test_go2_proprioceptive_joint_no_trace_tuning_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_proprioceptive_joint_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
