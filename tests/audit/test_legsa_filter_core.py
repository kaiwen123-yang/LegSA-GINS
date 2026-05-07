"""中文说明：audit 测试验证 N4 C++ filter core 文件和边界，不依赖 raw data。"""

import subprocess
import sys
from pathlib import Path


def test_legsa_filter_core_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_legsa_filter_core.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
