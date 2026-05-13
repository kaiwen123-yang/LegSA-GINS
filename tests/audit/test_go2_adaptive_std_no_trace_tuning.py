"""中文说明：测试 N7C3 自适应标准差没有 trace/final_v23 调参路径。"""

import subprocess
import sys


def test_go2_adaptive_std_no_trace_tuning_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_adaptive_std_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
