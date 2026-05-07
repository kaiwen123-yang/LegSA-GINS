"""中文说明：N4F audit 测试验证 toy trial 和边界 manifest，不依赖真实 BY2。"""

import subprocess
import sys
from pathlib import Path


def test_by2_filter_core_trial_audit_passes():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/audit_by2_filter_core_trial.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout

