"""中文说明：case_review 测试只构造临时产物，不声明真实性能。"""

import json

from legsa_gins.evaluation.case_review_report import generate_case_review


def test_case_review_contains_reference_context_and_flags(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for name in ["LegSA_NAV.nav", "LegSA_STD.csv", "EVAL_NAV.csv"]:
        (run_dir / name).write_text("header\n1 2 3\n", encoding="utf-8")
    (run_dir / "RUN_MANIFEST.json").write_text(
        json.dumps(
            {
                "phase": "N4F",
                "algorithm_name": "LegSA-GINS-filter-core-BY2-trial",
                "body_imu_source": "go2_body_state_diagnostic_converted_to_imu_increment",
                "receiver_imu_as_body_imu": False,
                "trace_solver_input": False,
                "raw_doppler_claim": False,
                "numerical_performance_claim": False,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "BY2_INPUT_MANIFEST.json").write_text("{}", encoding="utf-8")
    (tmp_path / "BY2_FILTER_TRIAL_MANIFEST.json").write_text(
        json.dumps({"selected_receiver_source": "gnss2", "trace_solver_input": False}),
        encoding="utf-8",
    )
    (tmp_path / "summary.json").write_text(
        json.dumps(
            {
                "count": 120,
                "evidence_status": "diagnostic_aligned",
                "horizontal_rmse_m": 10.0,
                "horizontal_p95_m": 12.0,
                "horizontal_max_m": 20.0,
                "up_rmse_m": 2.0,
                "roll_rmse_deg": 1.0,
                "pitch_rmse_deg": 1.0,
                "yaw_rmse_deg": 5.0,
                "yaw_p95_deg": 6.0,
            }
        ),
        encoding="utf-8",
    )

    classification = generate_case_review(
        output_path=tmp_path / "case_review.md",
        run_dir=run_dir,
        input_manifest_path=tmp_path / "BY2_INPUT_MANIFEST.json",
        trial_manifest_path=tmp_path / "BY2_FILTER_TRIAL_MANIFEST.json",
        summary_path=tmp_path / "summary.json",
    )

    text = (tmp_path / "case_review.md").read_text(encoding="utf-8")
    assert "dual_final_v23 horizontal_rmse_m = 0.353" in text
    assert "numerical_performance_claim: false" in text
    assert "trace_solver_input: false" in text
    assert classification["runtime_pass"] is True
    assert classification["comparable_generated"] is True
    assert classification["final_v23_close"] is False

