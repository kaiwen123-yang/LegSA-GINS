import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import ext03_yang2024 as ext03


def _los():
    values = {
        "01": [0.8, 0.0, 0.6],
        "02": [0.0, 0.8, 0.6],
        "03": [-0.8, 0.0, 0.6],
        "04": [0.0, -0.8, 0.6],
        "05": [0.6, 0.6, np.sqrt(0.28)],
    }
    return {key: np.asarray(value, dtype=float) / np.linalg.norm(value) for key, value in values.items()}


def _block(constellation, frequency, wavelength, pivot="01", satellites=("02", "03", "04", "05"),
           baseline=np.array([0.21, 0.28, 0.0]), ambiguities=(2, -1, 3, 1), noise=1e-5):
    los = _los()
    rows = np.asarray([-(los[satellite] - los[pivot]) for satellite in satellites])
    code = rows @ baseline
    phase = code + wavelength * np.asarray(ambiguities)
    count = len(satellites)
    # Dense shared-pivot blocks and a small code/phase cross correlation.
    code_cov = np.full((count, count), noise**2 * 0.2)
    code_cov[np.diag_indices(count)] = noise**2
    phase_cov = np.full((count, count), noise**2 * 0.1)
    phase_cov[np.diag_indices(count)] = noise**2 * 0.5
    cross = np.eye(count) * noise**2 * 0.02
    covariance = np.block([[code_cov, cross], [cross.T, phase_cov]])
    prefix = "G" if constellation == "GPS" else "C"
    return ext03.DDObservationBlock(
        constellation, frequency, prefix + pivot,
        tuple(prefix + item for item in satellites), wavelength,
        {prefix + key: value for key, value in los.items()}, code, phase,
        covariance,
    )


def _dual(constellation):
    if constellation == "GPS":
        blocks = (
            _block("GPS", "L1CA_SIG0", 0.190293672798),
            _block("GPS", "L2CL_SIG3", 0.244210213425, ambiguities=(-2, 4, 1, -3)),
        )
    else:
        blocks = (
            _block("BDS", "B1I_D1_SIG0", 0.192039486310),
            _block("BDS", "B2I_D1_SIG2", 0.248349369585, ambiguities=(-2, 4, 1, -3)),
        )
    return ext03.build_dd_observation(blocks)


class _BruteLambdaBridge:
    def __init__(self, _path):
        pass

    def candidates(self, floating, covariance, count):
        floating = np.asarray(floating)
        weight = np.linalg.inv(covariance)
        centers = np.rint(floating).astype(int)
        radius = 2
        candidates = []
        for integer in itertools.product(*(range(item - radius, item + radius + 1) for item in centers)):
            integer = np.asarray(integer, dtype=np.int64)
            delta = floating - integer
            candidates.append(SimpleNamespace(
                ambiguity=integer,
                ambiguity_objective=float(delta @ weight @ delta),
            ))
        candidates.sort(key=lambda item: (item.ambiguity_objective, tuple(item.ambiguity)))
        return candidates[:count]


@pytest.mark.parametrize("constellation", ["GPS", "BDS"])
def test_dual_frequency_noise_free_equations_and_integer_recovery(monkeypatch, constellation):
    model = _dual(constellation)
    assert model.design.shape == (16, 11)
    assert all(identity.constellation == constellation for identity in model.ambiguity_identities)
    assert np.count_nonzero(model.covariance_m2 - np.diag(np.diag(model.covariance_m2))) > 0
    monkeypatch.setattr(ext03, "RTKLIBLambdaBridge", _BruteLambdaBridge)
    result = ext03.process_epoch(
        None, 1.0, model, ext03.EXT03Config("CONSTRAINED"),
        spp_baseline_ned_m=np.array([0.21, 0.28, 0.0]),
        lambda_bridge_path="synthetic-pinned-bridge",
    )
    expected = np.array([2, -1, 3, 1, -2, 4, 1, -3])
    np.testing.assert_array_equal(result.mlambda_diagnostics.best_integer, expected)
    np.testing.assert_allclose(result.fixed_baseline_ned_m, [0.21, 0.28, 0.0], atol=2e-5)
    assert result.paper_ratio_fixed
    assert result.ambiguity_correctness_known is False
    assert result.solution_state == "paper_ratio_fixed"


def test_combined_stacks_separate_gps_and_bds_blocks_and_pivots():
    blocks = (
        _block("GPS", "L1CA_SIG0", 0.190293672798),
        _block("GPS", "L2CL_SIG3", 0.244210213425),
        _block("BDS", "B1I_D1_SIG0", 0.192039486310),
        _block("BDS", "B2I_D1_SIG2", 0.248349369585),
    )
    model = ext03.build_dd_observation(blocks)
    assert model.design.shape == (32, 19)
    assert {item.constellation for item in model.ambiguity_identities} == {"GPS", "BDS"}
    assert {item.pivot for item in model.ambiguity_identities if item.constellation == "GPS"} == {"G01"}
    assert {item.pivot for item in model.ambiguity_identities if item.constellation == "BDS"} == {"C01"}
    # Block diagonal covariance means no invented inter-system weighting/correlation.
    assert np.count_nonzero(model.covariance_m2[:16, 16:]) == 0


def test_dd_phase_minus_code_initializer_matches_non_iflc_rtklib_cycles():
    model = _dual("GPS")
    expected = np.array([2, -1, 3, 1, -2, 4, 1, -3], dtype=float)
    actual = np.asarray([
        model.phase_minus_code_initial_ambiguity_cycles[identity]
        for identity in model.ambiguity_identities
    ])
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=2e-15)


def test_constraint_jacobian_finite_difference_and_covariance_reduction():
    rng = np.random.default_rng(42)
    for baseline in rng.normal(size=(100, 3)):
        baseline *= 0.35 / np.linalg.norm(baseline)
        linearization = ext03.baseline_constraint_linearization(None, None, baseline)
        epsilon = 1e-7
        finite_difference = np.asarray([
            (np.linalg.norm(baseline + epsilon * np.eye(3)[axis])
             - np.linalg.norm(baseline - epsilon * np.eye(3)[axis])) / (2 * epsilon)
            for axis in range(3)
        ])
        np.testing.assert_allclose(linearization.jacobian_baseline, finite_difference, atol=2e-9)
    state = np.array([0.2, 0.25, 0.02, 1.1])
    covariance = np.diag([0.2, 0.2, 0.2, 2.0])
    linearization = ext03.baseline_constraint_linearization(None, None, state[:3])
    _, constrained, diagnostics = ext03.constraint_update(state, covariance, linearization)
    assert diagnostics.constraint_applied
    assert diagnostics.constraint_nis >= 0.0
    assert np.trace(constrained[:3, :3]) < np.trace(covariance[:3, :3])

    correlated = covariance.copy()
    correlated[0, 3] = correlated[3, 0] = 0.15
    before = state.copy()
    updated, _, correlated_diagnostics = ext03.constraint_update(
        state, correlated, linearization
    )
    assert correlated_diagnostics.constraint_update_norm == pytest.approx(
        np.linalg.norm(updated[:3] - before[:3])
    )
    assert correlated_diagnostics.constraint_ambiguity_update_norm_cycles == pytest.approx(
        np.linalg.norm(updated[3:] - before[3:])
    )
    assert correlated_diagnostics.constraint_ambiguity_update_norm_cycles > 0.0
    assert correlated_diagnostics.constraint_update_norm != pytest.approx(
        np.linalg.norm(updated - before)
    )


def test_constraint_b0_hierarchy_and_no_valid_point():
    fixed = np.array([0.35, 0.0, 0.0])
    spp = np.array([0.0, 0.35, 0.0])
    floating = np.array([0.0, 0.0, 0.35])
    assert ext03.baseline_constraint_linearization(fixed, spp, floating).source == "PREVIOUS_SUCCESSFULLY_RATIO_FIXED_BASELINE"
    assert ext03.baseline_constraint_linearization(None, spp, floating).source == "RAW_PSEUDORANGE_SPP_BASELINE_DIFFERENCE"
    assert ext03.baseline_constraint_linearization(None, None, floating).source == "CURRENT_FINITE_FLOAT_BASELINE"
    skipped = ext03.baseline_constraint_linearization(None, [np.nan, 0, 0], [0, 0, 0])
    assert not skipped.applied
    assert skipped.source == "NO_VALID_CONSTRAINT_LINEARIZATION_POINT"


def test_recursive_kf_matches_batch_oracle_and_is_deterministic():
    model = _dual("GPS")
    config = ext03.EXT03Config(
        "UNCONSTRAINED", baseline_process_sigma_m_sqrt_s=0.0,
        ambiguity_process_sigma_cycles_sqrt_s=0.0,
        baseline_prediction_mode="DIAGNOSTIC_IDENTITY_RANDOM_WALK",
    )
    baseline0 = np.array([0.18, 0.30, 0.01])
    first = ext03.process_epoch(None, 1.0, model, config, spp_baseline_ned_m=baseline0)
    second = ext03.process_epoch(first.state, 1.2, model, config)
    repeated_first = ext03.process_epoch(None, 1.0, model, config, spp_baseline_ned_m=baseline0)
    repeated_second = ext03.process_epoch(repeated_first.state, 1.2, model, config)
    np.testing.assert_array_equal(second.state.state, repeated_second.state.state)
    np.testing.assert_array_equal(second.state.covariance, repeated_second.state.covariance)

    prior_mean = np.concatenate((baseline0, np.zeros(8)))
    prior_covariance = np.diag([900.0] * 3 + [900.0] * 8)
    stacked_h = np.vstack((model.design, model.design))
    stacked_y = np.concatenate((model.observation_m, model.observation_m))
    stacked_r = np.block([
        [model.covariance_m2, np.zeros_like(model.covariance_m2)],
        [np.zeros_like(model.covariance_m2), model.covariance_m2],
    ])
    precision = np.linalg.inv(prior_covariance) + stacked_h.T @ np.linalg.solve(stacked_r, stacked_h)
    information = np.linalg.solve(prior_covariance, prior_mean) + stacked_h.T @ np.linalg.solve(stacked_r, stacked_y)
    batch = np.linalg.solve(precision, information)
    np.testing.assert_allclose(second.state.state, batch, atol=2e-7)


def test_pivot_transform_reindex_appearance_disappearance_and_reset():
    old_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G01")
        for satellite in ("G02", "G03", "G04")
    )
    state = ext03.initialize_state(1.0, old_ids)
    x = state.state.copy()
    x[3:] = [10.0, 14.0, 18.0]
    covariance = state.covariance.copy()
    covariance[3:, 3:] = np.array([[4, 1, 1], [1, 5, 2], [1, 2, 6]], dtype=float)
    state = ext03.EXT03State(1.0, x, covariance, old_ids)
    new_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G03")
        for satellite in ("G01", "G02", "G04", "G05")
    )
    transformed, diagnostics = ext03.reconcile_ambiguity_state(
        state, new_ids, reset_identities=(new_ids[2],)
    )
    # New pivot is G03: N_01^03=-N_03^01 and N_02^03=N_02^01-N_03^01.
    np.testing.assert_allclose(transformed.state[3:5], [-14.0, -4.0])
    assert transformed.state[5] == 0.0  # affected-only explicit reset
    assert transformed.state[6] == 0.0  # new satellite
    assert transformed.covariance[6, 6] == ext03.INITIAL_AMBIGUITY_VARIANCE_CYCLES2
    assert diagnostics.pivot_change_count == 1
    assert diagnostics.pivot_transform_count == 1
    assert diagnostics.pivot_reinitialization_count == 0
    assert diagnostics.reasons[0].reason == "PIVOT_CHANGE_TRANSFORMED"
    assert diagnostics.reset_ambiguity_count == 1
    assert diagnostics.new_ambiguity_count == 1
    assert diagnostics.removed_ambiguity_count == 0
    np.testing.assert_allclose(transformed.covariance, transformed.covariance.T)
    assert np.min(np.linalg.eigvalsh(transformed.covariance)) >= -1e-10


def test_state_management_add_remove_reset_categories_are_disjoint():
    old_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G01")
        for satellite in ("G02", "G03", "G04")
    )
    state = ext03.initialize_state(1.0, old_ids)
    new_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G01")
        for satellite in ("G02", "G03", "G05")
    )
    _, diagnostics = ext03.reconcile_ambiguity_state(
        state, new_ids, reset_identities=(new_ids[1],)
    )
    assert diagnostics.new_ambiguity_count == 1  # G05 appearance only
    assert diagnostics.removed_ambiguity_count == 1  # G04 disappearance only
    assert diagnostics.reset_ambiguity_count == 1  # retained G03 arc only
    assert diagnostics.pivot_change_count == 0


def test_untransformable_pivot_change_is_explicitly_reinitialized():
    old_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G01")
        for satellite in ("G02", "G03", "G04")
    )
    state = ext03.initialize_state(1.0, old_ids)
    new_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G05")
        for satellite in ("G01", "G02", "G03")
    )
    initial = {identity: 20.0 + index for index, identity in enumerate(new_ids)}
    result, diagnostics = ext03.reconcile_ambiguity_state(
        state, new_ids, initial_ambiguity_cycles=initial
    )
    np.testing.assert_allclose(result.state[3:], [20.0, 21.0, 22.0])
    assert diagnostics.pivot_change_count == 1
    assert diagnostics.pivot_transform_count == 0
    assert diagnostics.pivot_reinitialization_count == 1
    assert diagnostics.reasons[0].reason == "PIVOT_CHANGE_REINITIALIZED"


def test_new_and_reset_states_use_phase_code_mean_with_900_cycle2_variance():
    old_ids = (
        ext03.AmbiguityIdentity("GPS", "G02", "L1CA_SIG0", "G01"),
        ext03.AmbiguityIdentity("GPS", "G03", "L1CA_SIG0", "G01"),
    )
    state = ext03.initialize_state(1.0, old_ids)
    values = state.state.copy()
    values[3:] = [11.0, 12.0]
    state = ext03.EXT03State(1.0, values, state.covariance, old_ids)
    new_identity = ext03.AmbiguityIdentity("GPS", "G04", "L1CA_SIG0", "G01")
    target = old_ids + (new_identity,)
    initialized, diagnostics = ext03.reconcile_ambiguity_state(
        state, target, reset_identities=(old_ids[1],),
        initial_ambiguity_cycles={old_ids[1]: -3.25, new_identity: 7.5},
    )
    np.testing.assert_allclose(initialized.state[3:], [11.0, -3.25, 7.5])
    np.testing.assert_allclose(
        np.diag(initialized.covariance)[4:],
        [ext03.INITIAL_AMBIGUITY_VARIANCE_CYCLES2] * 2,
    )
    assert (diagnostics.new_ambiguity_count, diagnostics.removed_ambiguity_count,
            diagnostics.reset_ambiguity_count) == (1, 0, 1)


def test_lli_gf_mw_and_prior_dd_reset_only_affected_states():
    identities = (
        ext03.AmbiguityIdentity("GPS", "G02", "L1CA_SIG0", "G01"),
        ext03.AmbiguityIdentity("GPS", "G03", "L1CA_SIG0", "G01"),
        ext03.AmbiguityIdentity("GPS", "G04", "L2CL_SIG3", "G01"),
    )
    previous = ext03.TrackingMemory(
        geometry_free_m={("GPS", "G02"): 1.0},
        melbourne_wubbena_m={("GPS", "G03"): 2.0},
        estimated_dd_ambiguity_cycles={identities[2]: 4.0},
    )
    tracking = ext03.EpochTrackingInput(
        actual_carrier_lli_tracking_discontinuities=frozenset(
            {ext03.SignalIdentity("GPS", "G02", "L1CA_SIG0")}
        ),
        geometry_free_m={("GPS", "G02"): 1.06},
        melbourne_wubbena_m={("GPS", "G03"): 12.01},
        estimated_dd_ambiguity_cycles={identities[2]: 4.251},
    )
    result = ext03.detect_cycle_slips(identities, tracking, previous)
    assert result.affected_identities == identities
    assert (
        result.actual_carrier_lli_tracking_event_count,
        result.geometry_free_count,
        result.melbourne_wubbena_count,
        result.prior_dd_count,
    ) == (1, 1, 1, 1)
    reasons = dict(result.reasons)
    assert reasons[identities[0]] == (
        "ACTUAL_CARRIER_LLI_OR_TRACKING_VALIDITY_DISCONTINUITY",
        "GEOMETRY_FREE_JUMP",
    )
    assert reasons[identities[1]] == ("MELBOURNE_WUBBENA_JUMP",)
    assert reasons[identities[2]] == ("PRIOR_DD_AMBIGUITY_INCONSISTENCY",)


def test_dual_frequency_gf_and_mw_events_reset_both_frequency_states():
    identities = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, frequency, "G01")
        for satellite in ("G02", "G03")
        for frequency in ("L1CA_SIG0", "L2CL_SIG3")
    )
    previous = ext03.TrackingMemory(
        geometry_free_m={("GPS", "G02"): 1.0},
        melbourne_wubbena_m={("GPS", "G03"): 5.0},
    )
    tracking = ext03.EpochTrackingInput(
        geometry_free_m={("GPS", "G02"): 1.051},
        melbourne_wubbena_m={("GPS", "G03"): 15.01},
    )
    result = ext03.detect_cycle_slips(identities, tracking, previous)
    assert result.affected_identities == identities
    reasons = dict(result.reasons)
    assert all(reasons[item] == ("GEOMETRY_FREE_JUMP",) for item in identities[:2])
    assert all(reasons[item] == ("MELBOURNE_WUBBENA_JUMP",) for item in identities[2:])


def test_prior_dd_contract_requires_finite_estimated_ambiguity_identity_values():
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.EpochTrackingInput(estimated_dd_ambiguity_cycles={"raw_phase_minus_code": 3.0})
    assert caught.value.code == "INVALID_ESTIMATED_DD_AMBIGUITY_INPUT"


def test_tracking_input_rejects_noncanonical_or_nonfinite_signal_gf_mw():
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.EpochTrackingInput(
            actual_carrier_lli_tracking_discontinuities=frozenset({"G02-L1"})
        )
    assert caught.value.code == "INVALID_SIGNAL_EVENT_INPUT"
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.EpochTrackingInput(geometry_free_m={("gps", "G02"): 1.0})
    assert caught.value.code == "INVALID_TRACKING_COMBINATION_INPUT"
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.EpochTrackingInput(melbourne_wubbena_m={("BDS", "G02"): np.inf})
    assert caught.value.code == "INVALID_TRACKING_COMBINATION_INPUT"


def test_first_epoch_initialization_is_not_classified_as_cycle_slip():
    identity = ext03.AmbiguityIdentity("GPS", "G02", "L1CA_SIG0", "G01")
    tracking = ext03.EpochTrackingInput(
        actual_carrier_lli_tracking_discontinuities=frozenset({identity.signal}),
        receiver_locktime_resets=frozenset({identity.signal}),
        half_cycle_state_changes=frozenset({identity.signal}),
        receiver_clock_reset_events=frozenset({identity.signal}),
        geometry_free_m={("GPS", "G02"): 100.0},
        estimated_dd_ambiguity_cycles={identity: 8.0},
    )
    result = ext03.detect_cycle_slips(
        (identity,), tracking, ext03.TrackingMemory(), method_state_initialization=True
    )
    assert result.method_state_initialization
    assert result.affected_identities == ()
    assert (
        result.actual_carrier_lli_tracking_event_count,
        result.receiver_locktime_reset_event_count,
        result.half_cycle_state_change_event_count,
        result.receiver_clock_reset_event_count,
        result.geometry_free_count,
        result.prior_dd_count,
    ) == (0, 0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("field_name", "reason"),
    (
        (
            "actual_carrier_lli_tracking_discontinuities",
            "ACTUAL_CARRIER_LLI_OR_TRACKING_VALIDITY_DISCONTINUITY",
        ),
        ("receiver_locktime_resets", "RECEIVER_LOCKTIME_RESET"),
        (
            "half_cycle_state_changes",
            "HALF_CYCLE_VALIDITY_OR_SUBHALFCYC_CHANGE",
        ),
        ("receiver_clock_reset_events", "RECEIVER_CLOCK_RESET_EVENT"),
    ),
)
def test_receiver_tracking_event_categories_have_distinct_stable_reasons(field_name, reason):
    identity = ext03.AmbiguityIdentity("GPS", "G02", "L1CA_SIG0", "G01")
    tracking = ext03.EpochTrackingInput(
        **{field_name: frozenset({identity.signal})}
    )
    result = ext03.detect_cycle_slips((identity,), tracking, ext03.TrackingMemory())
    assert result.affected_identities == (identity,)
    assert dict(result.reasons)[identity] == (reason,)
    assert "CYCLE_SLIP" not in reason


def test_receiver_tracking_categories_form_one_affected_ambiguity_reset_union():
    identity = ext03.AmbiguityIdentity("BDS", "C02", "B1I_SIG0", "C01")
    signal = identity.signal
    tracking = ext03.EpochTrackingInput(
        actual_carrier_lli_tracking_discontinuities=frozenset({signal}),
        receiver_locktime_resets=frozenset({signal}),
        half_cycle_state_changes=frozenset({signal}),
        receiver_clock_reset_events=frozenset({signal}),
    )
    result = ext03.detect_cycle_slips((identity,), tracking, ext03.TrackingMemory())
    assert result.affected_identities == (identity,)
    assert (
        result.actual_carrier_lli_tracking_event_count,
        result.receiver_locktime_reset_event_count,
        result.half_cycle_state_change_event_count,
        result.receiver_clock_reset_event_count,
    ) == (1, 1, 1, 1)
    assert dict(result.reasons)[identity] == (
        "ACTUAL_CARRIER_LLI_OR_TRACKING_VALIDITY_DISCONTINUITY",
        "HALF_CYCLE_VALIDITY_OR_SUBHALFCYC_CHANGE",
        "RECEIVER_CLOCK_RESET_EVENT",
        "RECEIVER_LOCKTIME_RESET",
    )


def test_prior_dd_memory_transforms_with_pivot_or_reports_unavailable():
    old_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G01")
        for satellite in ("G02", "G03", "G04")
    )
    previous = ext03.TrackingMemory(
        estimated_dd_ambiguity_cycles=dict(zip(old_ids, (10.0, 14.0, 18.0), strict=True))
    )
    new_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G03")
        for satellite in ("G01", "G02", "G04")
    )
    transformed_prior = (-14.0, -4.0, 4.0)
    tracking = ext03.EpochTrackingInput(
        estimated_dd_ambiguity_cycles={
            identity: value + (0.3 if index == 1 else 0.0)
            for index, (identity, value) in enumerate(zip(new_ids, transformed_prior, strict=True))
        }
    )
    result = ext03.detect_cycle_slips(new_ids, tracking, previous)
    assert result.affected_identities == (new_ids[1],)
    assert result.prior_dd_count == 1
    assert result.detector_unavailable_reasons == ()

    unavailable_ids = tuple(
        ext03.AmbiguityIdentity("GPS", satellite, "L1CA_SIG0", "G05")
        for satellite in ("G01", "G02")
    )
    unavailable = ext03.detect_cycle_slips(
        unavailable_ids,
        ext03.EpochTrackingInput(
            estimated_dd_ambiguity_cycles={identity: 1.0 for identity in unavailable_ids}
        ),
        previous,
    )
    assert unavailable.prior_dd_count == 0
    assert len(unavailable.detector_unavailable_reasons) == len(unavailable_ids)
    assert {reason for _, reason in unavailable.detector_unavailable_reasons} == {
        "PRIOR_DD_UNAVAILABLE_PIVOT_CHANGE_REINITIALIZED"
    }
    identity = ext03.AmbiguityIdentity("GPS", "G02", "L1CA_SIG0", "G01")
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.EpochTrackingInput(estimated_dd_ambiguity_cycles={identity: np.nan})
    assert caught.value.code == "INVALID_ESTIMATED_DD_AMBIGUITY_INPUT"


def test_public_prior_dd_basis_mapper_accepts_previous_state_vector_mapping():
    old_ids = tuple(
        ext03.AmbiguityIdentity("BDS", satellite, "B1I_SIG0", "C01")
        for satellite in ("C02", "C03", "C04")
    )
    prior_state_vector = dict(zip(old_ids, (5.0, 8.0, 12.0), strict=True))
    target_ids = tuple(
        ext03.AmbiguityIdentity("BDS", satellite, "B1I_SIG0", "C03")
        for satellite in ("C01", "C02", "C04")
    )
    mapped, unavailable = ext03.map_prior_dd_ambiguities_to_target_basis(
        target_ids, prior_state_vector
    )
    assert unavailable == ()
    assert mapped == {
        target_ids[0]: -8.0,
        target_ids[1]: -3.0,
        target_ids[2]: 4.0,
    }

    untransformable = (
        ext03.AmbiguityIdentity("BDS", "C01", "B1I_SIG0", "C05"),
    )
    mapped, unavailable = ext03.map_prior_dd_ambiguities_to_target_basis(
        untransformable, prior_state_vector
    )
    assert mapped == {}
    assert unavailable == (
        (untransformable[0], "PRIOR_DD_UNAVAILABLE_PIVOT_CHANGE_REINITIALIZED"),
    )


def test_mlambda_ratio_matches_brute_force_and_threshold_semantics(monkeypatch):
    monkeypatch.setattr(ext03, "RTKLIBLambdaBridge", _BruteLambdaBridge)
    floating = np.array([2.02, -0.98])
    covariance = np.array([[0.04, 0.01], [0.01, 0.09]])
    result = ext03.mlambda_resolve(floating, covariance, "synthetic-pinned-bridge")
    np.testing.assert_array_equal(result.best_integer, [2, -1])
    assert result.ratio == pytest.approx(result.second_objective / result.best_objective)
    assert result.ratio > ext03.RATIO_THRESHOLD
    assert result.candidate_returned
    below = ext03.mlambda_resolve([0.49], [[1.0]], "synthetic-pinned-bridge")
    assert below.ratio < ext03.RATIO_THRESHOLD


def test_zero_best_mlambda_is_infinite_decision_without_non_rfc_number(monkeypatch):
    monkeypatch.setattr(ext03, "RTKLIBLambdaBridge", _BruteLambdaBridge)
    result = ext03.mlambda_resolve([2.0, -1.0], [[1.0, 0.0], [0.0, 1.0]], "bridge")
    assert result.ratio is None
    assert result.ratio_is_infinite
    assert result.zero_best_objective
    payload = {
        "ratio": result.ratio,
        "ratio_is_infinite": result.ratio_is_infinite,
        "zero_best_objective": result.zero_best_objective,
        "best_objective": result.best_objective,
        "second_objective": result.second_objective,
    }
    encoded = json.dumps(payload, allow_nan=False)
    assert "Infinity" not in encoded and "NaN" not in encoded


def test_zero_best_infinite_ratio_flag_is_accepted_by_process_epoch(monkeypatch):
    model = _dual("GPS")
    exact = ext03.MLAMBDAResult(
        np.array([2, -1, 3, 1, -2, 4, 1, -3]), np.zeros(8, dtype=int),
        0.0, 1.0, None, True, True, True, None,
    )
    monkeypatch.setattr(ext03, "mlambda_resolve", lambda *args, **kwargs: exact)
    result = ext03.process_epoch(
        None, 1.0, model, ext03.EXT03Config("UNCONSTRAINED"),
        spp_baseline_ned_m=np.array([0.21, 0.28, 0.0]), lambda_bridge_path="bridge",
    )
    assert result.paper_ratio_fixed


def test_attitude_and_registry_contracts():
    attitude = ext03.ned_attitude([0.21, 0.28, 0.0])
    assert attitude.baseline_length_m == pytest.approx(0.350)
    assert attitude.baseline_heading_deg == pytest.approx(53.1301023542)
    assert attitude.body_yaw_deg == pytest.approx(143.1301023542)
    assert attitude.pitch_deg == pytest.approx(0.0)
    assert all(item.trace_tuned is False for item in ext03.STOCHASTIC_PARAMETER_REGISTRY)
    process = next(item for item in ext03.STOCHASTIC_PARAMETER_REGISTRY
                   if item.parameter == "ambiguity_process_noise")
    assert process.value == 1.0e-4
    assert process.unit == "cycle/sqrt(s)"
    requirements = {item.requirement: item.implementation_contract for item in ext03.PAPER_MODEL_REGISTRY}
    assert requirements["troposphere"] == "SAASTAMOINEN_CORRECTION"
    assert requirements["constraint_spp_input"] == "GNSS2_MINUS_GNSS1_RAW_SPP_BASELINE_ONLY"
    assert ext03.SENSITIVITY_BASELINE_SIGMAS_M == (0.001, 0.005, 0.010, 0.020, 0.050)
    assert set(ext03.ADAPTER_STOCHASTIC_REGISTRY_REQUIRED_PARAMETERS) == {
        "code_measurement_sigma_model", "phase_measurement_sigma_model",
        "gps_system_weight", "bds_system_weight", "shared_pivot_covariance_model",
    }


def test_nonzero_pitch_sign_follows_paper_ned_equation():
    down = ext03.ned_attitude([0.3, 0.0, 0.1])
    up = ext03.ned_attitude([0.3, 0.0, -0.1])
    assert down.pitch_deg < 0.0
    assert up.pitch_deg > 0.0


def test_nonchronological_epoch_fails_closed():
    model = _dual("GPS")
    spp = np.array([0.21, 0.28, 0.0])
    state = ext03.process_epoch(
        None, 2.0, model, ext03.EXT03Config("UNCONSTRAINED"),
        spp_baseline_ned_m=spp,
    ).state
    with pytest.raises(ext03.Yang2024Error) as caught:
        ext03.process_epoch(
            state, 2.0, model, ext03.EXT03Config("UNCONSTRAINED"),
            spp_baseline_ned_m=spp,
        )
    assert caught.value.code == "NON_CHRONOLOGICAL_EPOCH"


def test_pinned_non_iflc_ambiguity_process_noise_is_directly_cycle_domain(monkeypatch):
    model = _dual("GPS")
    dimension = 3 + len(model.ambiguity_identities)
    previous = ext03.EXT03State(
        10.0,
        np.concatenate(([0.21, 0.28, 0.0], np.zeros(dimension - 3))),
        np.eye(dimension) * 7.0,
        model.ambiguity_identities,
    )
    captured = []

    def no_measurement_update(state, covariance, observation, design, measurement_covariance):
        captured.append(covariance.copy())
        return (
            state.copy(), covariance.copy(), np.zeros(observation.size),
            np.eye(observation.size),
        )

    monkeypatch.setattr(ext03, "_kalman_update", no_measurement_update)
    ext03.process_epoch(
        previous, 14.0, model, ext03.EXT03Config("UNCONSTRAINED"),
        spp_baseline_ned_m=np.array([0.21, 0.28, 0.0]),
    )
    predicted = captured[0]
    expected = 7.0 + (1.0e-4**2) * 4.0
    np.testing.assert_allclose(np.diag(predicted)[3:], expected, rtol=0.0, atol=1e-15)
    # Both GPS frequencies receive the same cycle^2 increment; no wavelength
    # division is present in the pinned non-IFLC mapping.
    assert len(set(np.diag(predicted)[3:].tolist())) == 1


def test_process_epoch_seeds_phase_code_means_but_not_prior_dd_memory(monkeypatch):
    model = _dual("GPS")
    captured = []

    def capture_initial_state(state, covariance, observation, design, measurement_covariance):
        captured.append(state.copy())
        return state.copy(), covariance.copy(), np.zeros(observation.size), np.eye(observation.size)

    monkeypatch.setattr(ext03, "_kalman_update", capture_initial_state)
    result = ext03.process_epoch(
        None, 1.0, model, ext03.EXT03Config("UNCONSTRAINED"),
        spp_baseline_ned_m=np.array([0.21, 0.28, 0.0]),
    )
    expected = np.asarray([
        model.phase_minus_code_initial_ambiguity_cycles[identity]
        for identity in model.ambiguity_identities
    ])
    np.testing.assert_allclose(captured[0][3:], expected)
    assert result.state.tracking_memory.estimated_dd_ambiguity_cycles == {}


def test_primary_rtklib_moving_base_prediction_tracks_rotating_spp_baseline():
    state = None
    headings = []
    for epoch, angle in enumerate(np.linspace(0.0, np.pi / 2.0, 9)):
        baseline = 0.35 * np.array([np.cos(angle), np.sin(angle), 0.0])
        model = ext03.build_dd_observation((
            _block("GPS", "L1CA_SIG0", 0.190293672798, baseline=baseline),
            _block("GPS", "L2CL_SIG3", 0.244210213425, baseline=baseline,
                   ambiguities=(-2, 4, 1, -3)),
        ))
        result = ext03.process_epoch(
            state, 10.0 + 0.2 * epoch, model,
            ext03.EXT03Config("CONSTRAINED"),
            spp_baseline_ned_m=baseline,
        )
        state = result.state
        headings.append(result.float_attitude.baseline_heading_deg)
    np.testing.assert_allclose(headings, np.degrees(np.linspace(0.0, np.pi / 2.0, 9)), atol=0.02)


def test_independent_variant_parallelism_one_vs_sixteen_is_deterministic():
    model = _dual("GPS")
    spp = np.array([0.21, 0.28, 0.0])

    def run_variant(index):
        state = None
        rows = []
        for epoch in range(5):
            result = ext03.process_epoch(
                state, 100.0 + 0.2 * epoch, model,
                ext03.EXT03Config(
                    "CONSTRAINED" if index % 2 else "UNCONSTRAINED",
                    baseline_sigma_m=ext03.SENSITIVITY_BASELINE_SIGMAS_M[
                        index % len(ext03.SENSITIVITY_BASELINE_SIGMAS_M)
                    ],
                ),
                spp_baseline_ned_m=spp,
            )
            state = result.state
            rows.append(np.concatenate((state.state, state.covariance.ravel())))
        return np.concatenate(rows)

    sequential = [run_variant(index) for index in range(16)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        parallel = list(pool.map(run_variant, range(16)))
    for left, right in zip(sequential, parallel, strict=True):
        np.testing.assert_array_equal(left, right)
