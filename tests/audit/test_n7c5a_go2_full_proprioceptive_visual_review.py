"""Audit test wrapper for N7C5A visual review.

中文说明：pytest 包装 N7C5A 图像复核审计脚本。
"""

import subprocess
import sys


def test_n7c5a_go2_full_proprioceptive_visual_review_audit():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_n7c5a_go2_full_proprioceptive_visual_review.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
