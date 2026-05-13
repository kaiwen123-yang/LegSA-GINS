"""N7B4 audit 测试：contact probability 不允许 trace/final_v23 tuning。"""

import subprocess
import sys


def test_go2_contact_probability_no_trace_tuning_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_contact_probability_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
