"""中文说明：audit 测试验证工程边界，不依赖 raw data，也不产生 numerical performance claim。
"""

import subprocess
import sys
from pathlib import Path


def test_frame_contract_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_frame_contract.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
