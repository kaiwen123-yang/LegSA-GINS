"""中文说明：调用 N4H4D1 first-epoch diagnostics audit。"""

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_n4h4d1_first_epoch_diagnostics_audit():
    result = subprocess.run(
        [sys.executable, "scripts/audit_legsa_v23_first_epoch_diagnostics.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "N4H4D1 first-epoch diagnostics audit passed." in result.stdout

