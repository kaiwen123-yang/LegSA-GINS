import subprocess
import sys


def test_audit_n7c6a_go2_joint_factor_final_review() -> None:
    """中文说明：通过脚本审计 N7C6A final review toy workflow。"""
    subprocess.run([sys.executable, "scripts/audit_n7c6a_go2_joint_factor_final_review.py"], check=True)
