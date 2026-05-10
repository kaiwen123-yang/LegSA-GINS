import subprocess


def test_source_aware_n6b_real_ekf_activation_audit():
    # 中文说明：确认 scaled R 进入 EKFUpdate，而不是只写 manifest。
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_n6b_real_ekf_activation.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
