import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n9b0b_audit_script_passes(tmp_path):
    runtime_root = tmp_path / "n9b0b_audit_runtime"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "audit_n9b0b_degradation_runner_precheck.py"),
            "--runtime-root",
            str(runtime_root),
            "--write-runtime",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "audit_n9b0b_degradation_runner_precheck passed" in completed.stdout
    assert not list(runtime_root.rglob("*.png"))
    assert not list(runtime_root.rglob("*.npy"))
    assert not list(runtime_root.rglob("*.npz"))
