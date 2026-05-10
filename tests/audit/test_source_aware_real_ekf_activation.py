import subprocess
from pathlib import Path


def test_source_aware_real_ekf_activation_audit():
    # 中文说明：确认 R scale 在 EKFUpdate 前生效，而不是只写 manifest。
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_real_ekf_activation.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
