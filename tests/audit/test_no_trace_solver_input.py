"""中文说明：audit 测试验证 trace 不进入 solver/proposed input，只允许 evaluation-only。"""

import subprocess
import sys
from pathlib import Path


def test_no_trace_solver_input_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_no_trace_solver_input.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
