"""中文说明：审计 FGO feedback 真实进入 C++ EKFUpdate 路径。"""

import subprocess
import sys


def test_fgo_feedback_to_ekf_update_audit():
    subprocess.run([sys.executable, "scripts/audit_fgo_feedback_to_ekf_update.py"], check=True)
