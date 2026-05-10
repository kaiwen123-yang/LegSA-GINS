import subprocess


def test_n6b_source_aware_policy_refinement_audit():
    # 中文说明：测试入口只调用审计脚本，不生成 Git-tracked runtime artifact。
    proc = subprocess.run(
        ["python3", "scripts/audit_n6b_source_aware_policy_refinement.py"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
