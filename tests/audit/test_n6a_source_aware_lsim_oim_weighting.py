import subprocess
from pathlib import Path


def test_n6a_source_aware_lsim_oim_weighting_audit():
    # 中文说明：审计脚本会运行 toy source-aware trace，验证四类 source 均被覆盖。
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["python3", "scripts/audit_n6a_source_aware_lsim_oim_weighting.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
