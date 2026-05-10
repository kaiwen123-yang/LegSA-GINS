import subprocess
from pathlib import Path


def test_source_aware_no_trace_tuning_audit():
    # 中文说明：N6A 权重策略不得从 trace 或 final_v23 输出反向调参。
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_no_trace_tuning.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
