"""中文说明：调用 N4H4D clean replay parity audit。"""

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_legsa_v23_clean_replay_parity_audit_passes():
    result = subprocess.run(
        [sys.executable, "scripts/audit_legsa_v23_clean_replay_parity.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "N4H4D LegSA-v23 clean replay parity audit passed" in result.stdout
