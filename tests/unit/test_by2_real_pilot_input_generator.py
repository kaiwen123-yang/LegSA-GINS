from pathlib import Path

from legsa_gins.reporting.by2_real_pilot_input_generator import (
    PILOT_CASE_IDS,
    _apply_downsample,
    _apply_outage,
    _apply_position_noise,
    _apply_position_spikes,
    _apply_yaw_noise,
    default_runtime_root,
    run_real_pilot_input_precheck,
    validate_n9b1a_result,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_runtime_root_uses_n9b_audit_folder():
    assert default_runtime_root(ROOT).parts[-2] == "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"


def test_outage_removes_inclusive_approved_interval():
    rows = [[205.0, 0, 0, 0, 1, 1, 1], [206.2, 0, 0, 0, 1, 1, 1], [211.2, 0, 0, 0, 1, 1, 1], [212.0, 0, 0, 0, 1, 1, 1]]
    kept, mask = _apply_outage(rows)
    assert len(kept) == 2
    assert sum(1 for row in mask if row["removed"]) == 2


def test_downsample_blocks_low_native_cadence():
    rows = [[float(i), 0, 0, 0, 1, 1, 1] for i in range(10)]
    output, mask, blocker = _apply_downsample(rows, "B_gnss_downsample_2Hz")
    assert output == rows
    assert mask == []
    assert blocker["blocked_stage"] == "low_native_cadence"


def test_seeded_degradations_are_deterministic():
    rows7 = [[55.0 + i, 39.0, 116.0, 40.0, 1.0, 1.0, 1.0] for i in range(5)]
    first, values = _apply_position_noise(rows7, 0)
    second, values2 = _apply_position_noise(rows7, 0)
    assert first == second
    assert values == values2
    spikes, spike_values = _apply_position_spikes(rows7, 0)
    assert len(spikes) == len(rows7)
    assert all(row["seed"] == 0 for row in spike_values)
    rows15 = [[55.0 + i, 39.0, 116.0, 40.0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 10.0, 1.5] for i in range(5)]
    yawed, yaw_values = _apply_yaw_noise(rows15, 0)
    assert yawed[0][13] != rows15[0][13]
    assert len(yaw_values) == len(rows15)


def test_precheck_writes_runtime_without_solver_outputs(tmp_path):
    runtime_root = tmp_path / "n9b1a"
    result = run_real_pilot_input_precheck(ROOT, runtime_root=runtime_root, write_outputs=True)
    validation = validate_n9b1a_result(
        runtime_root,
        result["degraded_input_index"],
        result["random_value_index"],
        result["solver_command_plan_index"],
        True,
    )
    assert validation["status"] == "pass"
    assert {row["case_id"] for row in result["degraded_input_index"]} == set(PILOT_CASE_IDS)
    j_algorithms = {
        row["algorithm"]
        for row in result["solver_command_plan_index"]
        if row["case_id"] == "J_go2_horizontal_velocity_missing"
    }
    assert {"Go2_joint_EKF", "selected_feedback_EKF"} <= j_algorithms
    assert result["decision_report"]["ready_for_solver_execution"] is False
    assert result["decision_report"]["ready_for_N9B2_execution"] is False
    if result["decision_report"]["blockers"]:
        assert result["decision_report"]["status"] == "N9B1A_degraded_input_generation_failed"
        assert result["decision_report"]["recommended_next_stage"] == "fix_input_generation"
    assert not list(runtime_root.rglob("NAV*"))
    assert not list(runtime_root.rglob("STD*"))
    assert not list(runtime_root.rglob("EVAL_NAV*"))
    assert not list(runtime_root.rglob("RUN_MANIFEST*"))
    assert not list(runtime_root.rglob("*.png"))
