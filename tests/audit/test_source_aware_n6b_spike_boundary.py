import subprocess


def test_source_aware_n6b_spike_boundary_audit():
    # 中文说明：spike 只允许事后审计，不允许进入策略。
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_n6b_spike_boundary.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
