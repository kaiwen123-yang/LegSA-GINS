import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_external_source_contract_audit_script_passes():
    result = subprocess.run(
        ["python3", "scripts/source_audit/audit_external_source_contract.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout
