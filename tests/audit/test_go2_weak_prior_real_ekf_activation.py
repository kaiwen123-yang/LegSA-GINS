"""中文说明：real EKF activation audit 至少验证 toy EKFUpdate 链路。"""

import subprocess
import sys
from pathlib import Path


def test_go2_weak_prior_real_ekf_activation_audit_passes():
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts/audit_go2_weak_prior_real_ekf_activation.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
