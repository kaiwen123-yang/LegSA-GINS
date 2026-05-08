"""中文说明：N4H1 toy integration 不依赖真实 BY2 或 final_v23 本地路径。"""

import json
import subprocess
import sys


def test_final_v23_input_source_audit_toy(tmp_path):
    output_dir = tmp_path / "audit"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_final_v23_input_source_audit.py",
            "--toy",
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    for rel_path in [
        "PROCESS_DATA_SOURCE_MAP.json",
        "FINAL_V23_INPUT_SOURCE_REPORT.json",
        "FINAL_V23_YAW_CHAIN_REPORT.json",
        "final_v23_input_source_chain_review.md",
    ]:
        assert (output_dir / rel_path).exists(), rel_path

    input_report = json.loads((output_dir / "FINAL_V23_INPUT_SOURCE_REPORT.json").read_text())
    yaw_report = json.loads((output_dir / "FINAL_V23_YAW_CHAIN_REPORT.json").read_text())
    review = (output_dir / "final_v23_input_source_chain_review.md").read_text()

    assert input_report["trace_solver_input"] is False
    assert input_report["final_v23_is_proposed"] is False
    assert input_report["position_source_status"] == "matched_gnss1_status"
    assert input_report["position_std_source_status"] == "matched_pos_acc_h_pos_acc_v"
    assert yaw_report["yaw_column_source_status"] == "matched_a1_dual_diff"
    assert "runtime actual input" in review
    assert "upstream generation fields" in review
    assert "trace_solver_input: false" in review
