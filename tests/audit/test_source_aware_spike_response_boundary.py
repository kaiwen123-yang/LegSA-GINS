import subprocess
from pathlib import Path


def test_source_aware_spike_response_boundary_audit():
    # 中文说明：N5D1 spike 时间只能用于事后 sentinel 审计。
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_spike_response_boundary.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
