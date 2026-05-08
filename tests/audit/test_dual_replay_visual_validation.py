"""中文说明：调用 N4H2E audit 脚本，确认输出 passed。"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_dual_replay_visual_validation():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audit_dual_replay_visual_validation.py")],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert "passed" in result.stdout
