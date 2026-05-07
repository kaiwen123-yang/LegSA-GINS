"""中文说明：N4G toy integration 不依赖真实 BY2 路径。"""

import json
import subprocess
import sys


def test_by2_filter_trial_toy_generates_outputs(tmp_path):
    output_dir = tmp_path / "trial"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_by2_filter_core_trial.py",
            "--toy",
            "--output-dir",
            str(output_dir),
            "--max-filter-epochs",
            "140",
            "--run-heading-offset-candidates",
            "--imu-propagation-modes",
            "gyro_only_zero_dvel,quaternion_gravity_compensated",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    for rel_path in [
        "alignment/EVENT_NORMALIZATION_REPORT.json",
        "imu/UNITREE_IMU_SEMANTICS_REPORT.json",
        "HEADING_OFFSET_CANDIDATE_REPORT.json",
        "IMU_PROPAGATION_MODE_REPORT.json",
        "N4G_GAP_SCREEN_SUMMARY.json",
    ]:
        assert (output_dir / rel_path).exists(), rel_path

    trial_dir = output_dir / "trial_gyro_only_zero_dvel_no_offset"
    for rel_path in [
        "run/LegSA_NAV.nav",
        "run/LegSA_STD.csv",
        "run/EVAL_NAV.csv",
        "run/RUN_MANIFEST.json",
        "evaluation/error_series.csv",
        "evaluation/summary.json",
        "evaluation/gate_report.json",
        "evaluation/gap_screen.json",
        "case_review.md",
        "BY2_FILTER_TRIAL_MANIFEST.json",
    ]:
        assert (trial_dir / rel_path).exists(), rel_path

    summary = json.loads((trial_dir / "evaluation/summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (trial_dir / "BY2_FILTER_TRIAL_MANIFEST.json").read_text(encoding="utf-8")
    )
    run_manifest = json.loads(
        (trial_dir / "run/RUN_MANIFEST.json").read_text(encoding="utf-8")
    )
    gap_summary = json.loads((output_dir / "N4G_GAP_SCREEN_SUMMARY.json").read_text(encoding="utf-8"))
    case_review = (trial_dir / "case_review.md").read_text(encoding="utf-8")

    assert summary["count"] > 100
    assert manifest["trace_solver_input"] is False
    assert manifest["trace_used_for_alignment"] is False
    assert manifest["clock_sync_claim"] is False
    assert manifest["physical_time_offset_claim"] is False
    assert manifest["raw_doppler_claim"] is False
    assert manifest["numerical_performance_claim"] is False
    assert run_manifest["receiver_imu_as_body_imu"] is False
    assert run_manifest["go2_prior_claim"] is False
    assert run_manifest["event_normalized_time_axis"] is True
    assert gap_summary["formal_heading_offset_selected"] is False
    assert "primary_benchmark: dual_final_v23_reference_context" in case_review
