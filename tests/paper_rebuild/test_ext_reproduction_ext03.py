"""Synthetic arithmetic/input-history tests; no raw data or reference opened."""
from dataclasses import replace
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import ext03_yang2024 as core
from legsa_gins.paper_rebuild.horizontal_literature import reproduction_ext03 as adapter
from legsa_gins.paper_rebuild.horizontal_literature import shared_raw_backend as raw


BASELINE = np.array([0.21, 0.28, 0.0])


def _blocks():
    result = []
    for system, frequency, wavelength in (
        ("GPS", "GPS_L1", .190293672798), ("GPS", "GPS_L2", .244210213425),
        ("BDS", "BDS_B1", .192039486310), ("BDS", "BDS_B2", .248349369585),
    ):
        prefix = "G" if system == "GPS" else "C"
        los = {prefix + "01": np.array([.8, 0., .6]),
               prefix + "02": np.array([0., .8, .6]),
               prefix + "03": np.array([.6, .6, np.sqrt(.28)])}
        h = -np.array([los[prefix + sv] - los[prefix + "01"] for sv in ("02", "03")])
        code = h @ BASELINE
        phase = code + wavelength * np.array([2., -1.])
        q = np.array([[.020, .006], [.006, .025]])
        covariance = np.block([[q, np.eye(2)*.00002], [np.eye(2)*.00002, q*.01]])
        result.append(core.DDObservationBlock(system, frequency, prefix + "01",
            (prefix + "02", prefix + "03"), wavelength, los, code, phase, covariance))
    return tuple(result)


def _epoch(tow, l2_signal=3):
    measurements = []
    for gnss, signal in ((0, 0), (0, l2_signal), (3, 0), (3, 2)):
        for sv in (1, 2, 3):
            identity = raw.SignalIdentity(gnss, sv, signal, 0)
            code = 23_000_000.0 + sv * 10
            measurements.append(raw.RawxMeasurement(identity, code,
                code / raw.wavelength_m(identity) + sv, 0., int(tow*1000), 45, 1, 1, 1, 7))
    return raw.RawxEpoch(tow, 2400, 18, 0, 1, tuple(measurements))


class _Provider:
    def __init__(self, fail_calls=()):
        self.calls = []
        self.fail_calls = set(fail_calls)

    def pntpos_rawx_epoch(self, epoch, navsys, seed):
        index = len(self.calls)
        self.calls.append((epoch, navsys, np.array(seed, copy=True)))
        position = np.array([6378137., 0., 0.])
        if index % 2:
            position += [0., .28, .21]
        accepted = index + 1 not in self.fail_calls
        return raw.RtklibPntPosResult(accepted, 0, position if accepted else None,
            None, None, None, 5 if accepted else 0, 6, 12, 12, "synthetic")


def _lambda_result(floating, covariance, library, ratio=4.0):
    first = np.rint(floating).astype(np.int64)
    second = first.copy()
    second[0] += 1
    return core.MLAMBDAResult(first, second, 1.0, ratio, ratio, False, False, True, None)


@pytest.fixture
def synthetic_engine(monkeypatch):
    monkeypatch.setattr(adapter.backend, "build_dual_frequency_blocks",
        lambda e1, e2, provider, p1, p2: (_blocks(), [{"synthetic_geometry": True}]))
    monkeypatch.setattr(core, "mlambda_resolve", _lambda_result)
    return adapter.ReproductionEXT03Engine(_Provider(), "synthetic-library-not-opened")


def test_same_linearization_pseudo_sequential_reverse_and_stacked_match():
    rng = np.random.default_rng(831)
    x = np.array([.19, .27, .03, 2.1, -1.2])
    a = rng.normal(size=(5, 5))
    p = a @ a.T + np.eye(5)*.4
    h = rng.normal(size=(4, 5))
    z = h @ x + np.array([.01, -.02, .03, -.04])
    r = np.full((4, 4), .004) + np.eye(4)*.01
    linearization = core.baseline_constraint_linearization(None, BASELINE, None)
    forward_x, forward_p, _, _ = core._kalman_update(x, p, z, h, r)
    forward_x, forward_p, _ = core.constraint_update(forward_x, forward_p, linearization)
    reverse_x, reverse_p, _ = core.constraint_update(x, p, linearization)
    reverse_x, reverse_p, _, _ = core._kalman_update(reverse_x, reverse_p, z, h, r)
    hp = np.zeros((1, 5)); hp[0, :3] = BASELINE/np.linalg.norm(BASELINE)
    stacked_h = np.vstack([h, hp])
    stacked_r = np.zeros((5, 5)); stacked_r[:4, :4] = r; stacked_r[-1, -1] = .010**2
    stacked_z = np.r_[z, .350]
    stacked_x, stacked_p, _, _ = core._kalman_update(x, p, stacked_z, stacked_h, stacked_r)
    # Independent information-form oracle, same b0/prior, not relinearized.
    oracle_p = np.linalg.inv(np.linalg.inv(p) + stacked_h.T @ np.linalg.solve(stacked_r, stacked_h))
    oracle_x = oracle_p @ (np.linalg.solve(p, x) + stacked_h.T @ np.linalg.solve(stacked_r, stacked_z))
    for actual_x, actual_p in ((forward_x, forward_p), (reverse_x, reverse_p), (stacked_x, stacked_p)):
        np.testing.assert_allclose(actual_x, oracle_x, rtol=0, atol=2e-10)
        np.testing.assert_allclose(actual_p, oracle_p, rtol=0, atol=2e-10)


def test_process_orders_dd_then_pseudo_then_lambda(monkeypatch):
    calls = []
    original = core._kalman_update
    def update(x, p, z, h, r):
        calls.append(("update", len(z)))
        return original(x, p, z, h, r)
    def resolver(x, p, library):
        calls.append(("lambda", len(x)))
        return _lambda_result(x, p, library)
    monkeypatch.setattr(core, "_kalman_update", update)
    monkeypatch.setattr(core, "mlambda_resolve", resolver)
    model = core.build_dd_observation(_blocks())
    result = core.process_epoch(None, 1., model, adapter.CONFIG, spp_baseline_ned_m=BASELINE,
                                lambda_bridge_path="synthetic")
    assert calls == [("update", 16), ("update", 1), ("lambda", 8)]
    assert result.constraint_diagnostics.constraint_linearization_source == "RAW_PSEUDORANGE_SPP_BASELINE_DIFFERENCE"


def test_pivot_transforms_full_qba_and_cross_frequency_covariance():
    old = tuple(core.AmbiguityIdentity("GPS", sat, freq, "G01")
                for freq in ("GPS_L1", "GPS_L2") for sat in ("G02", "G03"))
    target = tuple(core.AmbiguityIdentity("GPS", sat, freq, "G02")
                   for freq in ("GPS_L1", "GPS_L2") for sat in ("G01", "G03"))
    rng = np.random.default_rng(197)
    a = rng.normal(size=(7, 7)); p = a @ a.T + np.eye(7)
    x = np.array([.21, .28, .02, 2., -1., 4., 3.])
    state = core.EXT03State(1., x, p, old)
    change = np.array([[-1., 0.], [-1., 1.]])
    transform = np.eye(7); transform[3:5, 3:5] = change; transform[5:7, 5:7] = change
    actual, diagnostics = core.reconcile_ambiguity_state(state, target)
    expected_p = transform @ p @ transform.T
    np.testing.assert_allclose(actual.state, transform @ x, rtol=0, atol=1e-14)
    np.testing.assert_allclose(actual.covariance, expected_p, rtol=0, atol=1e-14)
    assert np.any(expected_p[:3, 3:] != 0) and np.any(expected_p[3:5, 5:7] != 0)
    assert diagnostics.pivot_transform_count == 2 and diagnostics.reset_ambiguity_count == 0


def test_slip_reset_removes_only_affected_cross_covariance():
    ids = core.build_dd_observation(_blocks()).ambiguity_identities
    rng = np.random.default_rng(254)
    a = rng.normal(size=(11, 11)); p = a @ a.T + np.eye(11)
    x = np.arange(11, dtype=float)
    old = core.EXT03State(1., x, p, ids)
    actual, diagnostics = core.reconcile_ambiguity_state(old, ids, [ids[1]], {ids[1]: -7.})
    retained = [index for index in range(11) if index != 4]
    np.testing.assert_array_equal(actual.covariance[np.ix_(retained, retained)], p[np.ix_(retained, retained)])
    assert actual.state[4] == -7. and actual.covariance[4, 4] == 900.
    assert np.count_nonzero(actual.covariance[4, retained]) == 0
    assert diagnostics.reset_ambiguity_count == 1


@pytest.mark.parametrize("ratio,expected", [(3., True), (np.nextafter(3., 0.), False)])
def test_ratio_three_boundary_uses_two_candidates(monkeypatch, ratio, expected):
    def resolver(x, p, library):
        return _lambda_result(x, p, library, ratio)
    monkeypatch.setattr(core, "mlambda_resolve", resolver)
    result = core.process_epoch(None, 1., core.build_dd_observation(_blocks()), adapter.CONFIG,
                                spp_baseline_ned_m=BASELINE, lambda_bridge_path="synthetic")
    assert result.paper_ratio_fixed is expected
    assert result.mlambda_diagnostics.second_integer is not None
    assert (result.fixed_baseline_ned_m is not None) is expected


def test_native_lambda_two_candidates_match_independent_enumeration():
    path = os.environ.get("EXT_REPRO_LAMBDA_LIBRARY")
    if not path:
        pytest.skip("explicit pinned native lambda path is required for this synthetic native test")
    assert Path(path).is_file()
    x = np.array([1.17, -2.31]); p = np.array([[.8, .24], [.24, .6]])
    actual = core.mlambda_resolve(x, p, path)
    candidates = []
    for integer in itertools.product(range(-3, 5), range(-6, 3)):
        difference = x - np.array(integer)
        candidates.append((float(difference @ np.linalg.solve(p, difference)), integer))
    candidates.sort()
    assert tuple(actual.best_integer) == candidates[0][1]
    assert tuple(actual.second_integer) == candidates[1][1]
    assert actual.best_objective == pytest.approx(candidates[0][0], rel=1e-13)
    assert actual.second_objective == pytest.approx(candidates[1][0], rel=1e-13)
    assert actual.ratio == pytest.approx(candidates[1][0]/candidates[0][0], rel=1e-13)


def test_first_epoch_without_fixed_then_previous_fixed_is_not_current_output(synthetic_engine, monkeypatch):
    engine = synthetic_engine
    ratios = iter((2., 4., 2.))
    monkeypatch.setattr(core, "mlambda_resolve", lambda x, p, library: _lambda_result(x, p, library, next(ratios)))
    first = engine.step(_epoch(1.), _epoch(1.))
    assert first["solution_state"] == "float" and first["fixed_baseline_ned_m"] is None
    assert first["constraint_diagnostics"]["constraint_linearization_source"] == "RAW_PSEUDORANGE_SPP_BASELINE_DIFFERENCE"
    assert first["slip"]["method_state_initialization"] is True
    second = engine.step(_epoch(2.), _epoch(2.))
    third = engine.step(_epoch(3.), _epoch(3.))
    assert second["paper_ratio_fixed"] and not third["paper_ratio_fixed"]
    assert third["fixed_baseline_ned_m"] is None
    assert third["baseline_ned_m"] == third["float_baseline_ned_m"]
    assert third["constraint_diagnostics"]["b0_ned_m"] == second["fixed_baseline_ned_m"]
    assert third["state"]["previous_fixed_baseline_ned_m"] == second["fixed_baseline_ned_m"]
    json.dumps([first, second, third], allow_nan=False)


def test_spp2_failure_preserves_kf_and_spp1_seed_at_old_update_point(synthetic_engine):
    engine = synthetic_engine
    first = engine.step(_epoch(1.), _epoch(1.))
    previous_state = engine.state
    engine.provider.fail_calls.add(4)
    failed = engine.step(_epoch(2.), _epoch(2.))
    assert failed["solution_state"] == "invalid" and failed["failure_code"] == "GNSS2_PNTPOS_REJECTED"
    assert failed["state_updated"] is False and engine.state is previous_state
    assert failed["baseline_ned_m"] is None and failed["state"]["epoch_time_s"] == 1.
    assert len(engine.raw_tracking_memory) == 24
    # New input adapter observes raw flags before SPP, even when SPP2 fails.
    assert all(value[0] == 2000 for value in engine.raw_tracking_memory.values())
    third = engine.step(_epoch(3.), _epoch(3.))
    assert third["kf_diagnostics"]["dt_s"] == 2.
    np.testing.assert_array_equal(engine.provider.calls[4][2], engine.spp_previous[0])
    assert first["paper_ratio_fixed"] and third["previous_state_epoch_time_s"] == 1.
    json.dumps(failed, allow_nan=False)


def test_failure_after_tracking_keeps_kf_and_retains_updated_raw_memory(synthetic_engine, monkeypatch):
    engine = synthetic_engine
    engine.step(_epoch(1.), _epoch(1.))
    previous = engine.state
    def fail(*args):
        raise core.Yang2024Error("synthetic native search failure", code="LAMBDA_SEARCH_FAILED")
    monkeypatch.setattr(core, "mlambda_resolve", fail)
    failed = engine.step(_epoch(2.), _epoch(2.))
    assert failed["failure_code"] == "LAMBDA_SEARCH_FAILED" and engine.state is previous
    assert all(value[0] == 2000 for value in engine.raw_tracking_memory.values())
    assert failed["dd_audit"]["design"] and failed["baseline_ned_m"] is None


def test_stage_evidence_distinguishes_spp_failure_from_unknown_core_progress(synthetic_engine, monkeypatch):
    engine = synthetic_engine
    engine.provider.fail_calls.add(2)
    spp_failed = engine.step(_epoch(1.), _epoch(1.))
    before = spp_failed["stage_evidence"]
    assert before["SPP"]["GNSS1"] == {"attempted": True, "returned": True, "accepted": True}
    assert before["SPP"]["GNSS2"] == {"attempted": True, "returned": True, "accepted": False}
    assert before["DD_MODEL_BUILT"] is False and before["CORE_PROCESS_CALLED"] is False
    internal = ("float_solution_returned", "mlambda_attempted", "mlambda_completed",
                "mlambda_result_returned", "two_candidates_returned")
    assert all(before[name] is False for name in internal)
    def fail_core(*args, **kwargs):
        raise core.Yang2024Error("synthetic core MLAMBDA failure; no partial stage receipt", code="LAMBDA_SEARCH_FAILED")
    monkeypatch.setattr(core, "process_epoch", fail_core)
    core_failed = engine.step(_epoch(2.), _epoch(2.))
    after = core_failed["stage_evidence"]
    assert core_failed["failure_code"] == "LAMBDA_SEARCH_FAILED"
    assert core_failed["state_updated"] is False
    assert after["DD_MODEL_BUILT"] is True and after["CORE_PROCESS_CALLED"] is True
    assert after["internal_stage_status"] == "UNKNOWN_CORE_CALL_NOT_RETURNED"
    assert all(after[name] is None for name in internal)
    assert after["unknown_reason"]
    json.dumps([spp_failed, core_failed], allow_nan=False)
    evidence_directory = os.environ.get("EXT_REPRO_TEST_EVIDENCE_DIR")
    if evidence_directory:
        evidence = {"data_mode": "synthetic_tests", "synthetic_data_used": True,
                    "semisynthetic_data_used": False, "spp_failure": spp_failed, "core_failure": core_failed}
        with (Path(evidence_directory)/"EXT03_STAGE_FAILURE_EXAMPLES.json").open("x") as stream:
            json.dump(evidence, stream, indent=2, allow_nan=False)
            stream.write("\n")


def test_success_stage_evidence_uses_returned_candidates_even_when_ratio_rejected(synthetic_engine, monkeypatch):
    engine = synthetic_engine
    monkeypatch.setattr(core, "mlambda_resolve", lambda x, p, library: _lambda_result(x, p, library, 2.))
    result = engine.step(_epoch(1.), _epoch(1.))
    assert result["paper_ratio_fixed"] is False and result["solution_state"] == "float"
    stage = result["stage_evidence"]
    assert all(stage[name] is True for name in (
        "DD_MODEL_BUILT", "CORE_PROCESS_CALLED", "float_solution_returned",
        "mlambda_attempted", "mlambda_completed", "mlambda_result_returned", "two_candidates_returned"))
    assert stage["MLAMBDA_failure_code"] is None and stage["unknown_reason"] is None


def test_exact_signal_switch_resets_affected_frequency_and_survives_failed_update(synthetic_engine, monkeypatch):
    engine = synthetic_engine
    engine.step(_epoch(1.), _epoch(1.))
    def fail(*args):
        raise core.Yang2024Error("synthetic failed switch", code="LAMBDA_SEARCH_FAILED")
    monkeypatch.setattr(core, "mlambda_resolve", fail)
    failed = engine.step(_epoch(2., l2_signal=4), _epoch(2., l2_signal=4))
    assert len(failed["signal_switches"]) == 3
    monkeypatch.setattr(core, "mlambda_resolve", _lambda_result)
    result = engine.step(_epoch(3., l2_signal=4), _epoch(3., l2_signal=4))
    assert len(result["signal_switches"]) == 3
    affected = result["slip"]["affected_identities"]
    assert len(affected) == 2 and {item["frequency"] for item in affected} == {"GPS_L2"}
    assert result["state_diagnostics"]["reset_ambiguity_count"] == 2
    assert result["slip"]["actual_carrier_lli_tracking_event_count"] == 3
    assert engine.step(_epoch(4., l2_signal=4), _epoch(4., l2_signal=4))["signal_switches"] == []


def _tracking_bit(epoch, bit, valid, sv=2, sig=3):
    return replace(epoch, measurements=tuple(
        replace(m, locktime_ms=1000, tracking_status=(m.tracking_status | bit) if valid else (m.tracking_status & ~bit))
        if (m.identity.gnss_id, m.identity.sv_id, m.identity.sig_id) == (0, sv, sig) else m
        for m in epoch.measurements))


@pytest.mark.parametrize("bit,category", [(2, "actual_carrier_lli_tracking_discontinuities"),
                                         (4, "half_cycle_state_changes")])
def test_invalid_then_valid_without_lock_drop_retains_raw_event(synthetic_engine, monkeypatch, bit, category):
    engine = synthetic_engine
    engine.step(_epoch(1.), _epoch(1.))
    def blocks(first, second, provider, p1, p2):
        result = list(_blocks())
        if not any(m.identity == raw.SignalIdentity(0, 2, 3, 0) for m in first.measurements):
            for index in (0, 1):
                block = result[index]
                result[index] = replace(block, satellites=("G03",), code_dd_m=block.code_dd_m[[1]],
                    phase_dd_m=block.phase_dd_m[[1]], covariance_code_phase_m2=block.covariance_code_phase_m2[np.ix_([1, 3], [1, 3])])
        return tuple(result), []
    monkeypatch.setattr(adapter.backend, "build_dual_frequency_blocks", blocks)
    invalid_input = _tracking_bit(_epoch(2.), bit, False)
    second = engine.step(invalid_input, invalid_input)
    assert second["solution_state"] != "invalid"
    assert len(second["tracking_pending_after"][category]) == 2
    valid_input = _tracking_bit(_epoch(3.), bit, True)
    third = engine.step(valid_input, valid_input)
    assert third["state_diagnostics"]["reset_ambiguity_count"] == 1
    assert len(third["slip"]["affected_identities"]) == 1
    assert third["slip"]["affected_identities"][0]["frequency"] == "GPS_L2"
    assert all(not events for events in third["tracking_pending_after"].values())
    assert third["slip"]["receiver_locktime_reset_event_count"] == 0


def test_invalid_raw_flags_during_spp_failure_are_not_consumed(synthetic_engine):
    engine = synthetic_engine
    engine.step(_epoch(1.), _epoch(1.))
    previous = engine.state
    engine.provider.fail_calls.add(4)
    invalid_input = _tracking_bit(_epoch(2.), 2, False)
    failed = engine.step(invalid_input, invalid_input)
    assert failed["failure_code"] == "GNSS2_PNTPOS_REJECTED" and engine.state is previous
    assert len(failed["tracking_pending_after"]["actual_carrier_lli_tracking_discontinuities"]) == 2
    valid_input = _tracking_bit(_epoch(3.), 2, True)
    recovered = engine.step(valid_input, valid_input)
    assert recovered["slip"]["actual_carrier_lli_tracking_event_count"] == 1
    assert recovered["state_diagnostics"]["reset_ambiguity_count"] == 1
    assert all(not events for events in recovered["tracking_pending_after"].values())


def test_unmodeled_exact_component_pending_is_not_dropped_or_applied(synthetic_engine):
    engine = synthetic_engine
    def epoch(tow, valid):
        current = _epoch(tow)
        other = replace(current.measurements[3], identity=raw.SignalIdentity(0, 2, 4, 0),
                        cno_dbhz=30, locktime_ms=1000, tracking_status=7 if valid else 5)
        return replace(current, measurements=current.measurements + (other,))
    engine.step(epoch(1., True), epoch(1., True))
    for tow, valid in ((2., False), (3., True)):
        result = engine.step(epoch(tow, valid), epoch(tow, valid))
        assert result["slip"]["actual_carrier_lli_tracking_event_count"] == 0
        assert len(result["tracking_pending_after"]["actual_carrier_lli_tracking_discontinuities"]) == 2
        assert result["signal_switches"] == []


def test_normal_continuous_tracking_creates_no_extra_raw_resets(synthetic_engine):
    engine = synthetic_engine
    for tow in (1., 2., 3.):
        result = engine.step(_epoch(tow), _epoch(tow))
        assert result["raw_tracking_audit"]["observed_raw_measurement_count"] == 24
        assert result["raw_tracking_audit"]["events"] == []
        assert all(not events for events in result["tracking_pending_after"].values())
        assert result["slip"]["actual_carrier_lli_tracking_event_count"] == 0
        assert result["slip"]["receiver_locktime_reset_event_count"] == 0
        assert result["slip"]["half_cycle_state_change_event_count"] == 0
        assert result["slip"]["receiver_clock_reset_event_count"] == 0


@pytest.mark.parametrize("kind", ["time_pair", "week_pair", "duplicate", "week_rollover"])
def test_pairing_and_chronology_fail_before_spp_history_mutation(synthetic_engine, kind):
    engine = synthetic_engine
    engine.step(_epoch(1.), _epoch(1.))
    first, second = _epoch(2.), _epoch(2.)
    if kind == "time_pair":
        second = _epoch(2.1)
    elif kind == "week_pair":
        second = replace(second, gps_week=2401)
    elif kind == "duplicate":
        first = second = _epoch(1.)
    else:
        first = second = replace(first, gps_week=2401)
    with pytest.raises((raw.RawBackendError, core.Yang2024Error)):
        engine.step(first, second)
    assert len(engine.provider.calls) == 2 and engine.epoch_index == 1
    assert engine.previous_tow == 1.


def test_single_primary_registry_corrects_only_new_geometry_provenance():
    registry = adapter.parameter_registry()
    length = [row for row in registry if row["parameter"] == "baseline_length"]
    assert len(length) == 1 and length[0]["value"] == .350
    assert length[0]["source"] == "PROJECT_PHYSICAL_CONTRACT"
    assert length[0]["paper_disclosed_value"] is False
    assert next(row for row in core.STOCHASTIC_PARAMETER_REGISTRY if row.parameter == "baseline_length").source == "paper-disclosed"
    sigma = [row for row in registry if row["parameter"] == "baseline_length_sigma"]
    assert len(sigma) == 1 and sigma[0]["value"] == .010
    assert all(row["primary_or_sensitivity"] == "primary" for row in registry)
    assert all(row["trace_tuned"] is False for row in registry)
    assert {row["parameter"] for row in registry if row["paper_disclosed_value"]} == {
        "initial_baseline_variance", "initial_ambiguity_variance", "ratio_threshold"}


def test_json_diagnostics_preserve_nonfinite_tokens_not_false_zero():
    payload = adapter._jsonable({"values": np.array([np.nan, np.inf, -np.inf]), "missing": None})
    assert payload == {"values": ["NaN", "+Infinity", "-Infinity"], "missing": None}
    json.dumps(payload, allow_nan=False)
