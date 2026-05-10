import subprocess


def test_source_aware_n6b_no_trace_tuning_audit():
    # 中文说明：确认 N6B 策略没有从 trace/final_v23 输出调权。
    proc = subprocess.run(
        ["python3", "scripts/audit_source_aware_n6b_no_trace_tuning.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
