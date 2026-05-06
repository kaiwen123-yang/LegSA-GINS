import subprocess
import sys
from pathlib import Path


def test_final_v23_oracle_check_passes_for_valid_manifest(tmp_path):
    root = Path(__file__).resolve().parents[2]
    writer = root / "baseline/final_v23_wrapper/scripts/write_final_v23_manifest.py"
    oracle = root / "evaluation/oracle/final_v23_oracle_check.py"
    output_dir = tmp_path / "manifest"

    subprocess.run(
        [
            sys.executable,
            str(writer),
            "--output-dir",
            str(output_dir),
            "--dataset-name",
            "dummy_dataset",
            "--final-v23-root",
            "/tmp/nonexistent_final_v23",
            "--dry-run",
        ],
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            str(oracle),
            "--manifest",
            str(output_dir / "RUN_MANIFEST.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "passed" in result.stdout
