"""中文说明：N4H2C deep parity audit 测试只运行 toy audit 脚本。"""

import subprocess
import sys
from pathlib import Path


def test_final_v23_deep_parity_audit_passes():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(root / "scripts/audit_final_v23_deep_parity.py")],
        cwd=root,
        check=True,
    )
