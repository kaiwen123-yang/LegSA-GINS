"""中文说明：N7B3 velocity frame review audit smoke。"""

import subprocess
import sys
from pathlib import Path


def test_go2_velocity_frame_review_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_velocity_frame_review.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
