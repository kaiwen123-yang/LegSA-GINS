"""中文说明：N4H4C audit wrapper，确保量测更新闭环和禁用边界可复验。"""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_n4h4c_audit_script_passes():
    result = subprocess.run(
        ["python3", "scripts/audit_n4h4c_gnss_update_feedback.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "N4H4C GNSS update EKF feedback audit passed" in result.stdout
