"""中文说明：N4H1 audit 测试调用独立 audit 脚本。"""

import subprocess
import sys


def test_final_v23_input_source_chain_audit_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/audit_final_v23_input_source_chain.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
