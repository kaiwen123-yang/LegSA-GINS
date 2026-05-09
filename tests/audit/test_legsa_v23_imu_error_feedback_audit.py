import subprocess
import sys
from pathlib import Path


# 中文说明：调用 D6 audit 脚本，覆盖禁用项、toy run 和本地路径泄漏检查。
def test_audit_legsa_v23_imu_error_feedback_audit():
    repo = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/audit_legsa_v23_imu_error_feedback_audit.py"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr[-2000:] + completed.stdout[-2000:]
