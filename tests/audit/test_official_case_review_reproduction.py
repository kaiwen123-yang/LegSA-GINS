"""中文说明：N4R audit 测试只检查脚本可运行。"""

import subprocess
import sys
from pathlib import Path


def test_official_case_review_reproduction_audit_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/audit_official_case_review_reproduction.py")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
