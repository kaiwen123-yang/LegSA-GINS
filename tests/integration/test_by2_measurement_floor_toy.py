"""中文说明：N4H0 toy integration 只验证 measurement floor 报告链路。"""

import json
import subprocess
import sys


def test_by2_measurement_floor_toy_generates_reports(tmp_path):
    output_dir = tmp_path / "floor"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_by2_measurement_floor_sanity.py",
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
        "GNSS1_MEASUREMENT_FLOOR_EVAL_NAV.csv",
        "GNSS2_MEASUREMENT_FLOOR_EVAL_NAV.csv",
        "GNSS1_MEASUREMENT_FLOOR_SUMMARY.json",
        "GNSS2_MEASUREMENT_FLOOR_SUMMARY.json",
        "HEADING_FLOOR_CANDIDATE_REPORT.json",
        "MEASUREMENT_FLOOR_SANITY_REPORT.json",
        "measurement_floor_case_review.md",
    ]:
        assert (output_dir / rel_path).exists(), rel_path

    report = json.loads((output_dir / "MEASUREMENT_FLOOR_SANITY_REPORT.json").read_text())
    heading_report = json.loads((output_dir / "HEADING_FLOOR_CANDIDATE_REPORT.json").read_text())
    case_review = (output_dir / "measurement_floor_case_review.md").read_text()

    assert report["trace_solver_input"] is False
    assert report["proposed_solver_output"] is False
    assert report["numerical_performance_claim"] is False
    assert heading_report["formal_heading_offset_selected"] is False
    assert "primary_benchmark: dual_final_v23_reference_context" in case_review
    assert "proposed_solver_output: false" in case_review
    assert "formal performance achieved" not in case_review
