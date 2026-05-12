"""中文说明：N7B2 threshold 不能从 trace/final_v23 调参。"""

import subprocess
import sys
from pathlib import Path


def test_go2_contact_threshold_no_trace_tuning_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_contact_threshold_no_trace_tuning.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
