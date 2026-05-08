"""中文说明：N4H4B audit 测试锁定预测传播边界，不验证性能。"""

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/audit_n4h4b_ins_mechanization_predict.py"


def test_n4h4b_ins_mechanization_predict_audit_passes():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "N4H4B INS mechanization and EKF predict audit passed." in completed.stdout
