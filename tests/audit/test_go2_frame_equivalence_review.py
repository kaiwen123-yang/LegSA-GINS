"""N7B5 audit 测试：frame equivalence 不使用 trace/final_v23 tuning。"""

import subprocess
import sys


def test_go2_frame_equivalence_review_audit_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_go2_frame_equivalence_review.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
