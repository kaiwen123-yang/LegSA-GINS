"""中文说明：调用 startup transient audit 脚本并确认 passed。"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_startup_transient_audit():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_startup_transient_audit.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert "passed" in result.stdout
