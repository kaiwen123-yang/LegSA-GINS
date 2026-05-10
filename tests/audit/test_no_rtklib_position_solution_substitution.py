import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


# 中文说明：直接运行审计脚本，确保 RTKLIB position solution 不进入 solver。


def test_no_rtklib_position_solution_substitution_audit():
    subprocess.run(["python3", "scripts/audit_no_rtklib_position_solution_substitution.py"], cwd=ROOT, check=True)
