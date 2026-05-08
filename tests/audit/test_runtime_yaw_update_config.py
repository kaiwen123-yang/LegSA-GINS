"""中文说明：pytest wrapper for N4H2C runtime yaw audit script。"""

from pathlib import Path
import subprocess
import sys


def test_runtime_yaw_update_config_audit_script_passes() -> None:
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo / "scripts/audit_runtime_yaw_update_config.py")],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "passed" in result.stdout
