"""中文说明：N4H1P process_data compat audit 测试调用独立审计脚本。"""

import subprocess
import sys


def test_process_data_compat_generation_audit_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/audit_process_data_compat_generation.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
