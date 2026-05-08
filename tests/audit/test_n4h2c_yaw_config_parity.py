"""中文说明：N4H2C audit test 只检查计划边界，不运行 replay 或 solver。"""

import subprocess
import sys
from pathlib import Path


def test_n4h2c_yaw_config_parity_audit_passes():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(root / "scripts/audit_n4h2c_yaw_config_parity.py")],
        cwd=root,
        check=True,
    )
