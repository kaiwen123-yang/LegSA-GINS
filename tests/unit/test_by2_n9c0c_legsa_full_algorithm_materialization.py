from pathlib import Path

from legsa_gins.reporting.by2_algorithm_runner import (
    ALGORITHM_SPECS,
    FORMAL_ALGORITHMS,
    build_algorithm_config_text,
)
from legsa_gins.reporting.by2_n9c0c_legsa_full_algorithm_materialization import (
    ALGORITHM_ID,
    _config_flag_row,
    _parse_config_values,
)


ROOT = Path(__file__).resolve().parents[2]


def test_legsa_full_ekf_is_distinct_formal_algorithm_mapping():
    assert ALGORITHM_ID in FORMAL_ALGORITHMS
    assert ALGORITHM_SPECS[ALGORITHM_ID].component_flags == {
        "raw_doppler": True,
        "source_aware": True,
        "go2_joint": True,
        "feedback": True,
    }
    assert ALGORITHM_SPECS["selected_feedback_EKF"].component_flags == {
        "raw_doppler": False,
        "source_aware": False,
        "go2_joint": False,
        "feedback": True,
    }
    assert ALGORITHM_SPECS["Go2_joint_EKF"].component_flags["feedback"] is False


def test_legsa_full_ekf_generated_config_enables_all_intended_flags(tmp_path):
    config_text = build_algorithm_config_text(
        ROOT,
        ALGORITHM_ID,
        tmp_path / "out",
        {
            "imupath": "/clean/CLEAN_STATUS_YAW.imu",
            "gnsspath": "/clean/CLEAN_STATUS_YAW.gnss",
        },
    )
    assert "enable_raw_doppler: true" in config_text
    assert "enable_source_aware_weighting: true" in config_text
    assert "enable_go2_attitude_weak_prior: true" in config_text
    assert "enable_go2_horizontal_velocity_prior: true" in config_text
    assert "enable_go2_proprioceptive_joint_factor: true" in config_text
    assert "enable_fgo_feedback: true" in config_text
    assert "fgo_feedback_velocity_enabled: true" in config_text
    assert "fgo_feedback_attitude_enabled: true" in config_text
    assert "trace_solver_input: false" in config_text
    assert "final_v23_output_solver_input: false" in config_text
    assert "output_only_correction: false" in config_text
    assert "paper_performance_claim: false" in config_text


def test_n9c0c_config_flag_parser_requires_same_case_feedback(tmp_path):
    config = tmp_path / "runtime_config.yaml"
    config.write_text(
        "\n".join(
            [
                "enable_raw_doppler: true",
                "enable_source_aware_weighting: true",
                "enable_go2_attitude_weak_prior: true",
                "enable_go2_horizontal_velocity_prior: true",
                "enable_go2_proprioceptive_joint_factor: true",
                "enable_fgo_feedback: true",
                "same_case_feedback_required: true",
                "trace_solver_input: false",
                "final_v23_solver_input: false",
                "output_only_correction: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    values = _parse_config_values(config)
    row = _config_flag_row(
        type(
            "Case",
            (),
            {
                "case_id": "A_outage_20s",
                "stage_group": "minimum_cases",
                "feedback_observations": tmp_path / "FGO_FEEDBACK_OBSERVATIONS.csv",
                "source_config": config,
            },
        )(),
        config,
        values,
    )
    assert row["raw_doppler_enabled"] is True
    assert row["source_aware_enabled"] is True
    assert row["go2_legged_aux_enabled"] is True
    assert row["selected_feedback_enabled"] is True
    assert row["same_case_feedback_required"] is True
    assert row["trace_solver_input"] is False
    assert row["final_v23_solver_input"] is False
    assert row["output_substitution"] is False
