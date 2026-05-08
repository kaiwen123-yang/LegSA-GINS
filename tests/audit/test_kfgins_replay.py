"""中文说明：N4H2 replay audit 只验证已提交报告和边界，不读取真实 raw 输出。"""

import subprocess
import sys
from pathlib import Path


def test_kfgins_replay_audit_passes():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(root / "scripts/audit_kfgins_replay.py")],
        cwd=root,
        check=True,
    )
