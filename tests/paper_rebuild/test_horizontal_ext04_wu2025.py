import math
import os
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import ext04_wu2025 as ext04
from legsa_gins.paper_rebuild.horizontal_literature.ext01_clambda import (
    RTKLIBLambdaBridge,
    joint_gls,
    search_strict_lambda,
)
from legsa_gins.paper_rebuild.horizontal_literature.ext04_wu2025 import (
    BASELINE_LENGTH_M,
    PRIMARY_POLICY,
    SEARCH_BUDGET_CLOCK,
    AmbiguityIdentity,
    AmbiguityQuality,
    DDObservationBlock,
    Wu2025Error,
    attitude_from_ned_baseline,
    build_observation_model,
    decide_far,
    decide_par,
    deterministic_removal_order,
    evaluate_gates,
    evaluate_subset,
    subset_observation_model,
)
from legsa_gins.paper_rebuild.horizontal_literature.phase4_runner import (
    _best_by_sv,
    _best_common_by_sv,
    _decision_row,
)
from legsa_gins.paper_rebuild.horizontal_literature.shared_raw_backend import (
    RawxEpoch,
    RawxMeasurement,
    SignalIdentity,
)


@pytest.fixture(scope="module")
def lambda_bridge():
    path = os.environ.get("LEGSA_RTKLIB_LAMBDA_BRIDGE")
    if not path:
        local = (
            Path(__file__).resolve().parents[2]
            / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"
        )
        if local.is_file():
            value = yaml.safe_load(local.read_text(encoding="utf-8"))
            path = value.get("paths", {}).get("horizontal_literature_lambda_library")
    if not path:
        pytest.skip("LEGSA_RTKLIB_LAMBDA_BRIDGE is not configured")
    if not Path(path).is_file():
        pytest.skip("configured RTKLIB LAMBDA bridge is absent")
    return RTKLIBLambdaBridge(path)


BASELINE = np.array([0.21, 0.28, 0.0])
LOS = {
    "pivot": np.array([0.0, 0.0, 1.0]),
    "s1": np.array([1.0, 0.0, 0.0]),
    "s2": np.array([0.0, 1.0, 0.0]),
    "s3": np.array([0.0, 0.0, -1.0]),
}


def _block(
    constellation, frequency, pivot, satellites, wavelength, ambiguity,
    *, phase_bias_cycles=0.0, cno=(48.0, 46.0, 44.0),
):
    geometry = {
        pivot: LOS["pivot"],
        **{satellite: LOS[f"s{index + 1}"] for index, satellite in enumerate(satellites)},
    }
    rows = np.asarray([
        -(geometry[satellite] - geometry[pivot]) for satellite in satellites
    ])
    code = rows @ BASELINE
    phase = code + wavelength * (
        np.asarray(ambiguity, dtype=float) + phase_bias_cycles
    )
    count = len(satellites)
    covariance = np.diag(np.concatenate((
        1.0e-4 * np.asarray([1.0, 1.3, 1.7])[:count],
        1.0e-6 * np.asarray([1.0, 1.2, 1.5])[:count],
    )))
    return DDObservationBlock(
        constellation, frequency, pivot, tuple(satellites), wavelength,
        geometry, code, phase, covariance,
        dict(zip(satellites, cno, strict=True)),
        {satellite: math.radians(70 - 10 * index)
         for index, satellite in enumerate(satellites)},
        {satellite: f"{constellation}:{frequency}:{satellite}"
         for satellite in satellites},
    )


def _gps_blocks(*, phase_bias_cycles=0.0):
    satellites = ("G02", "G03", "G04")
    return (
        _block("GPS", "GPS_L1", "G01", satellites, 0.1902936728,
               (5, -3, 2), phase_bias_cycles=phase_bias_cycles),
        _block("GPS", "GPS_L2", "G01", satellites, 0.2442102134,
               (-1, 4, 7), phase_bias_cycles=phase_bias_cycles),
    )


def _bds_blocks(*, phase_bias_cycles=0.0):
    satellites = ("C07", "C08", "C09")
    return (
        _block("BDS", "BDS_B1", "C06", satellites, 0.1920394863,
               (3, 1, -2), phase_bias_cycles=phase_bias_cycles),
        _block("BDS", "BDS_B2", "C06", satellites, 0.2483493696,
               (6, -4, 2), phase_bias_cycles=phase_bias_cycles),
    )


@pytest.mark.parametrize("blocks", [_gps_blocks(), _bds_blocks()])
def test_noise_free_dual_frequency_far_recovers_integer_baseline_and_attitude(
    blocks, lambda_bridge,
):
    model = build_observation_model(blocks)
    expected = np.concatenate([
        np.rint((np.asarray(block.phase_dd_m) - np.asarray(block.code_dd_m))
                / block.wavelength_m).astype(int)
        for block in blocks
    ])
    evaluated = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=lambda_bridge,
        strict=True, timeout_seconds=10.0,
    )
    assert evaluated.search_certified
    np.testing.assert_array_equal(evaluated.best.ambiguity, expected)
    np.testing.assert_allclose(evaluated.best.baseline, BASELINE, atol=1e-8)
    assert np.linalg.norm(evaluated.best.baseline) == pytest.approx(
        BASELINE_LENGTH_M, abs=1e-10,
    )
    attitude = attitude_from_ned_baseline(evaluated.best.baseline)
    assert attitude.baseline_yaw_deg == pytest.approx(
        math.degrees(math.atan2(BASELINE[1], BASELINE[0])), abs=1e-7,
    )
    assert attitude.body_yaw_deg == pytest.approx(143.1301023542, abs=1e-7)
    assert attitude.pitch_deg == pytest.approx(0.0, abs=1e-8)


def test_noise_free_gps_bds_far_uses_separate_pivots(lambda_bridge):
    blocks = _gps_blocks() + _bds_blocks()
    model = build_observation_model(blocks)
    evaluated = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=lambda_bridge,
        strict=True, timeout_seconds=10.0,
    )
    assert evaluated.search_certified
    np.testing.assert_allclose(evaluated.best.baseline, BASELINE, atol=1e-8)
    assert {identity.pivot[0] for identity in model.ambiguity_identities} == {"G", "C"}
    assert all(
        (identity.constellation == "GPS") == identity.pivot.startswith("G")
        for identity in model.ambiguity_identities
    )


def test_strict_search_matches_brute_force_and_ext01_core(lambda_bridge):
    model = build_observation_model((_gps_blocks()[0],))
    strict = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=lambda_bridge,
        strict=True, timeout_seconds=10.0,
    )
    brute = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=None, strict=False,
    )
    floating = joint_gls(
        model.observation_m, model.ambiguity_design_m,
        model.baseline_design, model.covariance_m2,
    )
    ext01 = search_strict_lambda(
        floating, lambda_bridge, BASELINE_LENGTH_M, 8, None, 10.0,
    )
    assert strict.search_certificate.global_optimum_certified
    assert strict.search_certificate.candidate_cap_applied is False
    assert strict.search_certificate.configured_node_limit is None
    np.testing.assert_array_equal(strict.best.ambiguity, brute.best.ambiguity)
    np.testing.assert_array_equal(strict.best.ambiguity, ext01.best.ambiguity)
    assert strict.best.objective == pytest.approx(brute.best.objective, abs=1e-10)
    assert strict.best.objective == pytest.approx(ext01.best.objective, abs=1e-12)
    assert strict.second.objective == pytest.approx(ext01.second.objective, abs=1e-12)


def test_ext04_search_budget_uses_process_cpu_time_not_wall_scheduling(monkeypatch):
    observed = {}

    def fake_search(*_args, **_kwargs):
        started = ext04._ext01_core.time.perf_counter()
        time.sleep(0.03)
        observed["budget_delta"] = ext04._ext01_core.time.perf_counter() - started
        return "sentinel"

    original_clock = ext04._ext01_core.time
    monkeypatch.setattr(ext04, "search_strict_lambda", fake_search)
    cpu_readings = iter((100.0, 100.0))
    monkeypatch.setattr(ext04.time, "process_time", lambda: next(cpu_readings))
    wall_started = time.perf_counter()
    result = ext04._strict_search_process_cpu_budget(None, None, 0.350, 1.0)
    wall_delta = time.perf_counter() - wall_started
    assert result == "sentinel"
    assert SEARCH_BUDGET_CLOCK == "PARENT_PROCESS_CPU_TIME"
    assert wall_delta >= 0.025
    assert observed["budget_delta"] < 0.01
    assert ext04._ext01_core.time is original_clock


def test_uncertified_timeout_blanks_solution_facing_heading_fields():
    model = build_observation_model((_gps_blocks()[0],))
    certified = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=None, strict=False,
    )
    certificate = replace(
        certified.search_certificate,
        termination_reason="SEARCH_TIMEOUT",
        global_optimum_certified=False,
        runtime_budget_exhausted=True,
    )
    timeout = replace(
        certified, search_certificate=certificate,
        quality_metrics=None, failure_code="SEARCH_TIMEOUT",
    )
    decision = decide_far((timeout,))
    epoch = RawxEpoch(100.0, 2200, 18, 0, 1, ())
    row = _decision_row(
        decision, system_mode="GPS_DUAL_FREQUENCY", epoch_index=7,
        epoch=epoch, full_ambiguity_count=model.ambiguity_count,
        mode_runtime_seconds=0.5,
    )
    assert row["solution_state"] == "INVALID"
    assert row["failure_code"] == "SEARCH_TIMEOUT"
    assert row["float_ambiguities_cycles"] is not None
    assert all(row[field] is None for field in (
        "integer_ambiguities", "baseline_n_m", "baseline_e_m", "baseline_d_m",
        "baseline_length_m", "baseline_yaw_deg", "body_yaw_deg", "pitch_deg",
        "best_objective", "second_objective", "second_over_best",
        "best_over_second", "unconstrained_conditional_baseline_ned_m",
        "unconstrained_conditional_baseline_norm_m",
        "baseline_validation_residual_m", "posterior_residual_statistic",
        "posterior_p_value", "code_residual_rms_m", "phase_residual_rms_m",
        "residual_vector_m", "ambiguity_log_determinant",
        "ADOP_ambiguity_dimension", "ADOP_cycles",
    ))


def test_quality_metrics_dof_adop_and_unconstrained_validation():
    model = build_observation_model((_gps_blocks()[0],))
    evaluated = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=None, strict=False,
    )
    metrics = evaluated.quality_metrics
    assert metrics.degrees_of_freedom == model.observation_m.size - 2
    sign, logdet = np.linalg.slogdet(evaluated.float_solution.covariance_aa)
    assert sign > 0
    assert metrics.ambiguity_log_determinant == pytest.approx(logdet)
    assert metrics.adop_cycles == pytest.approx(
        math.exp(logdet / (2 * model.ambiguity_count))
    )
    assert metrics.unconstrained_conditional_baseline_norm_m == pytest.approx(0.350)
    assert metrics.baseline_validation_residual_m == pytest.approx(0.0, abs=1e-8)
    assert metrics.chi_square_p_value == pytest.approx(1.0)


def test_far_failure_then_par_success_policy_state():
    model = build_observation_model((_gps_blocks()[0],))
    base = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=None, strict=False,
    )
    failed_metrics = replace(base.quality_metrics, second_over_best=1.0)
    passed_metrics = replace(
        base.quality_metrics, second_over_best=10.0,
        baseline_validation_residual_m=0.0, chi_square_p_value=1.0,
        adop_cycles=0.01,
    )
    first = replace(base, quality_metrics=failed_metrics)
    second = replace(base, quality_metrics=passed_metrics)
    decision = decide_par((first, second), PRIMARY_POLICY)
    assert decision.solution_state == "PAR_ACCEPTED"
    assert decision.accepted


def test_deterministic_declared_removal_order():
    model = build_observation_model((_gps_blocks()[0],))
    base = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=None, strict=False,
    )
    identities = model.ambiguity_identities
    quality = (
        AmbiguityQuality(0, identities[0], "z", 30.0, 0.5, 1.0, 1.0),
        AmbiguityQuality(1, identities[1], "a", 20.0, 0.8, 1.0, 1.0),
        AmbiguityQuality(2, identities[2], "b", 20.0, 0.4, 2.0, 3.0),
    )
    ordered = deterministic_removal_order(replace(base, ambiguity_quality=quality))
    assert [item.source_index for item in ordered] == [2, 1, 0]
    assert deterministic_removal_order(replace(base, ambiguity_quality=quality)) == ordered


def test_pivot_change_and_subset_identity_alignment():
    first = build_observation_model((_gps_blocks()[0],))
    changed = _block(
        "GPS", "GPS_L1", "G02", ("G01", "G03", "G04"),
        0.1902936728, (1, 2, 3),
    )
    second = build_observation_model((changed,))
    assert {item.pivot for item in first.ambiguity_identities} == {"G01"}
    assert {item.pivot for item in second.ambiguity_identities} == {"G02"}
    subset = subset_observation_model(first, (2, 0))
    assert subset.source_ambiguity_indices == (2, 0)
    assert subset.ambiguity_identities == (
        first.ambiguity_identities[2], first.ambiguity_identities[0],
    )
    phase_indices = [
        value for kind, value in zip(subset.row_kinds, subset.row_ambiguity_indices)
        if kind == "PHASE"
    ]
    assert phase_indices == [1, 0]


def _raw_measurement(*, half_cycle_valid, sig_id=0):
    status = 0x01 | 0x02 | (0x04 if half_cycle_valid else 0)
    return RawxMeasurement(
        SignalIdentity(0, 3, sig_id, 0), 22_000_000.0, 110_000_000.0,
        -1000.0, 1000, 45, 3, 2, 3, status,
    )


def test_half_cycle_exclusion_is_fail_closed():
    invalid = RawxEpoch(1.0, 2000, 18, 0, 1, (_raw_measurement(half_cycle_valid=False),))
    valid = RawxEpoch(1.0, 2000, 18, 0, 1, (_raw_measurement(half_cycle_valid=True),))
    assert _best_by_sv(invalid, "GPS_L1") == {}
    assert set(_best_by_sv(valid, "GPS_L1")) == {3}


def test_two_receiver_signal_selection_requires_exact_raw_identity():
    left = RawxEpoch(
        1.0, 2000, 18, 0, 1,
        (_raw_measurement(half_cycle_valid=True, sig_id=3),),
    )
    mismatch = RawxEpoch(
        1.0, 2000, 18, 0, 1,
        (_raw_measurement(half_cycle_valid=True, sig_id=4),),
    )
    matched = RawxEpoch(
        1.0, 2000, 18, 0, 1,
        (_raw_measurement(half_cycle_valid=True, sig_id=3),),
    )
    assert _best_common_by_sv(left, mismatch, "GPS_L2") == {}
    assert set(_best_common_by_sv(left, matched, "GPS_L2")) == {3}


def test_fractional_bias_stress_is_detected_not_calibrated():
    biased = build_observation_model((
        _gps_blocks(phase_bias_cycles=0.25)[0],
    ))
    evaluated = evaluate_subset(
        biased, biased.source_ambiguity_indices, bridge=None, strict=False,
    )
    gates = evaluate_gates(evaluated, PRIMARY_POLICY)
    assert evaluated.quality_metrics.chi_square_p_value < 0.01
    assert not gates.accepted


def test_cross_system_dd_identity_is_forbidden():
    with pytest.raises(Wu2025Error, match="cross-system"):
        AmbiguityIdentity("GPS", "G02", "GPS_L1", "C01")
