"""中文说明：audit 测试验证 N3D 中文注释覆盖，不依赖 raw data，不做性能结论。"""

import subprocess
import sys
from pathlib import Path


def test_chinese_comments_audit_passes():
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/audit_chinese_comments.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout
