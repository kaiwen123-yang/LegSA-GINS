from scripts.experiments.run_by3c_position_up_degradation_batch0_to_batch3 import (
    CaseSpec,
    apply_downsample,
    apply_position_noise,
    apply_position_spike,
    apply_position_std_inflation,
    effect_validation,
    validate_case_scope,
)


def _rows(count: int = 6) -> list[list[float]]:
    return [
        [float(i), 30.0 + i * 1e-5, 120.0 + i * 1e-5, 5.0 + i, 0.1, 0.2, 0.3, 1.0, 2.0, 3.0, 0.01, 0.02, 0.03, 45.0, 1.5]
        for i in range(count)
    ]


def test_case_scope_excludes_forbidden_families() -> None:
    cases = [CaseSpec("BY3_normal_repeat_accepted_sources", "normal", "normal", 0)]
    cases.extend(CaseSpec(f"A_outage_{duration}s", "A_outage", f"{duration}s", 1) for duration in [3, 5, 10, 20])
    cases.extend(CaseSpec(f"B_downsample_every{ratio}", "B_downsample", f"every{ratio}", 1) for ratio in [2, 5, 10])
    cases.extend(CaseSpec(f"E_position_std_inflation_x{factor}", "E_position_std_inflation", f"x{factor}", 1) for factor in [2, 5, 10])
    cases.extend(CaseSpec(f"C_position_noise_{sev}_seed{seed}", "C_position_noise", sev, 2, seed) for sev in ["mild", "medium", "strong"] for seed in range(10))
    cases.extend(CaseSpec(f"D_position_spike_{sev}_seed{seed}", "D_position_spike", sev, 3, seed) for sev in ["mild", "medium", "strong"] for seed in range(10))

    validate_case_scope(cases)


def test_position_std_inflation_changes_only_std_columns() -> None:
    rows = _rows()
    degraded = apply_position_std_inflation(rows, 5.0)

    assert degraded[0][4:7] == [0.5, 1.0, 1.5]
    assert degraded[0][1:4] == rows[0][1:4]
    assert degraded[0][7:15] == rows[0][7:15]
    assert effect_validation(CaseSpec("E_position_std_inflation_x5", "E_position_std_inflation", "x5", 1), rows, degraded, rows, degraded, {})[
        "effect_validation_passed"
    ]


def test_random_position_noise_is_deterministic_and_preserves_yaw_velocity() -> None:
    rows = _rows(10)
    degraded_a, payload_a = apply_position_noise(rows, seed=3, horizontal_sigma_m=1.5, vertical_sigma_m=2.5)
    degraded_b, payload_b = apply_position_noise(rows, seed=3, horizontal_sigma_m=1.5, vertical_sigma_m=2.5)

    assert payload_a == payload_b
    assert degraded_a == degraded_b
    assert any(degraded_a[i][1:4] != rows[i][1:4] for i in range(len(rows)))
    assert all(degraded_a[i][7:15] == rows[i][7:15] for i in range(len(rows)))


def test_position_spike_records_triggers_and_downsample_ratio() -> None:
    rows = _rows(20)
    downsampled, meta = apply_downsample(rows, 5)
    degraded, payload = apply_position_spike(rows, seed=0, probability=1.0, horizontal_magnitude_m=4.0, vertical_magnitude_m=2.0)

    assert [row[0] for row in downsampled] == [0.0, 5.0, 10.0, 15.0]
    assert meta["kept_rule"] == "zero_based_index_mod_5_eq_0"
    assert payload["summary"]["triggered_count"] == 20
    assert all(degraded[i][13:15] == rows[i][13:15] for i in range(len(rows)))
