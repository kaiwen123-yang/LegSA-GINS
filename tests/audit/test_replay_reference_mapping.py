"""中文说明：pytest wrapper for N4H2D replay reference mapping audit。"""

from pathlib import Path
import subprocess
import sys


def test_replay_reference_mapping_audit_script_passes() -> None:
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo / "scripts/audit_replay_reference_mapping.py")],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "passed" in result.stdout
