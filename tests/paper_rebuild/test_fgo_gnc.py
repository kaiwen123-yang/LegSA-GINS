"""Synthetic correctness only; no real-data provider or reference is opened."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.fgo_comparison.gnc import (
    EQ21_SQUARED_GM,
    EQ22_PRINTED_DIAGNOSTIC,
    _prepare_graph,
    eq22_printed_weight,
    gm_loss,
    gnc_weight,
    solve,
)


def _synthetic(n: int = 8, systems: int = 2, outlier: float = 0, measurement_noise: bool = False) -> tuple[dict, np.ndarray, np.ndarray]:
    """Exact known trajectory, independent per-epoch raw-observation WLS."""
    time = np.arange(n, dtype=float) * 0.7
    p0 = np.array([-2689400.0, -4297050.0, 3853600.0])
    velocity = np.array([1.2, -0.4, 0.7])
    position = p0 + time[:, None] * velocity
    rng = np.random.default_rng(20432)
    directions = rng.normal(size=(16, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    satellite = p0 + 2.1e7 * directions
    system = np.arange(16) % systems
    clocks = np.column_stack((70000.0 + 20 * time, -30000.0 + 10 * time))
    epoch = np.repeat(np.arange(n), len(satellite))
    satellites = np.tile(satellite, (n, 1))
    all_systems = np.tile(system, n)
    pseudorange = np.linalg.norm(satellites - position[epoch], axis=1) + clocks[epoch, all_systems]
    # One repeated biased measurement; the remaining independently directed
    # pseudoranges determine an unambiguous, otherwise noiseless trajectory.
    pseudorange[np.arange(n) * len(satellite) + 2] += outlier
    noise_rng = np.random.default_rng(423)
    if measurement_noise:
        pseudorange += noise_rng.normal(0, 1.5, len(pseudorange))
    initial_position = np.empty((n, 3))
    initial_clock = np.full((n, 2), np.nan)
    for k in range(n):
        measured = pseudorange[k * len(satellite) : (k + 1) * len(satellite)]
        state = np.r_[[-2800000.0, -4500000.0, 4000000.0], np.zeros(systems)]
        for _ in range(30):
            delta = state[:3] - satellite
            ranges = np.linalg.norm(delta, axis=1)
            design = np.zeros((len(satellite), 3 + systems))
            design[:, :3] = delta / ranges[:, None]
            design[np.arange(len(satellite)), 3 + system] = 1
            innovation = measured - ranges - state[3 + system]
            step = np.linalg.lstsq(design, innovation, rcond=None)[0]
            state += step
            if np.max(np.abs(step)) < 1e-6:
                break
        initial_position[k] = state[:3]
        initial_clock[k, :systems] = state[3:]
    covariance = np.array([[0.05, 0.01, -0.006], [0.01, 0.04, 0.003], [-0.006, 0.003, 0.06]])
    data = {
        "time_rel_s": time,
        "epoch_index": epoch,
        "sat_pos_ecef_m": satellites,
        "pseudorange_m": pseudorange,
        "pr_sigma_m": np.full(len(epoch), 1.5),
        "system": all_systems,
        "initial_position_ecef_m": initial_position,
        "initial_clock_m": initial_clock,
        "doppler_velocity_ecef_mps": np.tile(velocity, (n, 1)),
        "doppler_covariance": np.tile(covariance, (n, 1, 1)),
        "spp_valid": np.ones(n, dtype=bool),
    }
    if measurement_noise:
        data["doppler_velocity_ecef_mps"] += noise_rng.normal(0, .03, (n, 3))
    return data, position, clocks


@pytest.mark.parametrize("theta", [1.0, 7.0, 120.0])
def test_squared_weight_is_eq21_stationary_point_and_recovers_gm(theta):
    residual = np.array([0.0, 0.7, -4.0, 80.0])
    a = theta * 2.0**2
    weight = gnc_weight(residual, theta, 2.0)
    # Directly differentiate the paper's outlier-process objective, instead
    # of merely repeating the weight formula under test.
    derivative = residual**2 + a * (1 - 1 / np.sqrt(weight))
    assert np.max(np.abs(derivative)) < 1e-10
    joint = weight * residual**2 + a * (np.sqrt(weight) - 1) ** 2
    np.testing.assert_allclose(joint, gm_loss(residual, theta, 2.0), rtol=1e-13, atol=1e-13)
    for multiplier in [0.5, 1.5]:
        alternative = np.minimum(weight * multiplier, 1)
        alternative_cost = alternative * residual**2 + a * (np.sqrt(alternative) - 1) ** 2
        assert np.all(joint <= alternative_cost + 1e-12)


def test_noiseless_position_and_independent_clocks_without_attitude_state():
    data, truth, clocks = _synthetic()
    input_copy = {key: value.copy() for key, value in data.items()}
    result = solve(data)
    assert result["terminal_status"] == "COMPLETED", result["components"]
    assert result["valid"].all()
    np.testing.assert_allclose(result["position_ecef_m"], truth, atol=1e-5, rtol=0)
    np.testing.assert_allclose(result["clock_m"], clocks, atol=1e-5, rtol=0)
    assert "yaw" not in result and "roll" not in result and "pitch" not in result
    assert result["components"][0]["variable_count"] == len(truth) * 5
    assert max(item["theta"] for item in result["iterations"]) < 1
    assert result["components"][0]["theta_final"] < 1
    assert result["iterations"][-1]["converged"]
    for key in data:
        np.testing.assert_array_equal(data[key], input_copy[key])


def test_single_system_does_not_allocate_an_unobserved_clock():
    data, truth, clocks = _synthetic(systems=1)
    result = solve(data)
    assert result["valid"].all()
    assert result["components"][0]["variable_count"] == len(truth) * 4
    np.testing.assert_allclose(result["position_ecef_m"], truth, atol=1e-5, rtol=0)
    np.testing.assert_allclose(result["clock_m"][:, 0], clocks[:, 0], atol=1e-5, rtol=0)
    assert np.isnan(result["clock_m"][:, 1]).all()


def test_analytic_jacobian_matches_finite_difference_with_full_doppler_covariance():
    data, _, _ = _synthetic(n=3)
    whitening = np.array([np.linalg.solve(np.linalg.cholesky(c), np.eye(3)) for c in data["doppler_covariance"][:-1]])
    graph = _prepare_graph(data, np.arange(3), np.ones(len(data["epoch_index"]), dtype=bool), whitening)
    state = graph.initial_state.copy()
    state[:9] += np.linspace(-3, 4, 9)
    _, analytic = graph.residual_jacobian(state)
    numerical = np.empty(analytic.shape)
    epsilon = 0.05
    for col in range(len(state)):
        step = np.zeros_like(state)
        step[col] = epsilon
        plus, _ = graph.residual_jacobian(state + step)
        minus, _ = graph.residual_jacobian(state - step)
        numerical[:, col] = (plus - minus) / (2 * epsilon)
    np.testing.assert_allclose(analytic.toarray(), numerical, rtol=2e-6, atol=1e-7)
    # Whitened squared norm must equal e.T @ inv(cov) @ e, with the full
    # off-diagonal covariance rather than its diagonal or inverse std twice.
    e = np.array([0.4, -0.2, 0.8])
    np.testing.assert_allclose(np.sum((whitening[0] @ e)**2), e @ np.linalg.solve(data["doppler_covariance"][0], e))


def test_outlier_is_downweighted_by_actual_gnc_continuation():
    data, truth, _ = _synthetic(n=10, outlier=100.0)
    initial_error = np.linalg.norm(data["initial_position_ecef_m"] - truth, axis=1).mean()
    result = solve(data)
    assert result["terminal_status"] == "COMPLETED", result["components"]
    final_error = np.linalg.norm(result["position_ecef_m"] - truth, axis=1).mean()
    assert initial_error > 5
    assert final_error < 0.01
    outliers = np.arange(10) * 16 + 2
    inliers = np.ones(len(result["weights"]), dtype=bool)
    inliers[outliers] = False
    assert np.max(result["weights"][outliers]) < 1e-5
    assert np.min(result["weights"][inliers]) > 0.99
    history = result["weight_history"]
    np.testing.assert_array_equal(history[0]["weights"], 1)
    theta = [row["theta"] for row in result["iterations"]]
    assert theta[0] > 100 and 1 <= theta[-1] < 1.4
    for previous, current in zip(theta[:-1], theta[1:]):
        assert current == previous / 1.4
    assert len(set(theta)) > 10
    assert result["components"][0]["theta_final"] == theta[-1] / 1.4
    assert result["components"][0]["final_alternations"] == 0
    assert all(row["phase"] == "ALGORITHM1_STEP2_STEP3" for row in result["iterations"])
    np.testing.assert_allclose(result["weights"], gnc_weight(result["residuals"], theta[-1], 2), rtol=1e-13)
    np.testing.assert_array_equal(result["state_solve_weights"], history[-2]["weights"])
    np.testing.assert_array_equal(result["weights"], history[-1]["weights"])
    assert not np.array_equal(result["state_solve_weights"], result["weights"])


def test_noisy_batch_converges_without_ecef_cancellation_line_search_failure():
    # The literal observed-minus-20,000 km-range subtraction used to make
    # a numerically converged robust iterate fail its final line search.
    # Stable range increments must solve the same physical objective.
    data, truth, _ = _synthetic(n=250, outlier=100, measurement_noise=True)
    result = solve(data)
    assert result["terminal_status"] == "COMPLETED", result["components"]
    assert result["valid_epoch_count"] == 250
    assert np.mean(np.linalg.norm(result["position_ecef_m"] - truth, axis=1)) < 1
    assert result["components"][0]["theta_final"] < 1
    assert 1 <= result["components"][0]["theta_last_solved"] < 1.4
    assert result["iterations"][-1]["converged"]
    assert result["components"][0]["final_weight_consistency_max_abs"] <= 1e-6
    predicted = np.linalg.norm(data["sat_pos_ecef_m"] - result["position_ecef_m"][data["epoch_index"]], axis=1) + result["clock_m"][data["epoch_index"], data["system"]]
    np.testing.assert_allclose(result["residuals_m"], data["pseudorange_m"] - predicted, atol=2e-8, rtol=0)


def test_missing_pseudoranges_preserve_epoch_and_use_only_doppler_link():
    data, truth, _ = _synthetic(n=7)
    keep = data["epoch_index"] != 3
    for key in ("epoch_index", "sat_pos_ecef_m", "pseudorange_m", "pr_sigma_m", "system"):
        data[key] = data[key][keep]
    data["spp_valid"][3] = False
    data["initial_position_ecef_m"][3] = np.nan
    data["initial_clock_m"][3] = np.nan
    result = solve(data)
    assert result["expected_epoch_count"] == 7
    assert result["valid_epoch_count"] == 7
    assert result["valid"][3]
    assert np.isnan(result["clock_m"][3]).all()
    np.testing.assert_allclose(result["position_ecef_m"], truth, atol=1e-5, rtol=0)


def test_missing_doppler_and_unobservable_component_do_not_get_fallback_prior():
    data, truth, _ = _synthetic(n=6, systems=1)
    # Last three epochs have only one range each.  Their clock absorbs that
    # range entirely; a Doppler-connected run still has a 3D translation gauge.
    keep = (data["epoch_index"] < 3) | (np.arange(len(data["epoch_index"])) % 16 == 0)
    for key in ("epoch_index", "sat_pos_ecef_m", "pseudorange_m", "pr_sigma_m", "system"):
        data[key] = data[key][keep]
    data["doppler_velocity_ecef_mps"][2] = np.nan
    result = solve(data)
    assert result["terminal_status"] == "PARTIAL"
    np.testing.assert_array_equal(result["valid"], [1, 1, 1, 0, 0, 0])
    np.testing.assert_allclose(result["position_ecef_m"][:3], truth[:3], atol=1e-5, rtol=0)
    assert np.isnan(result["position_ecef_m"][3:]).all()
    assert np.all(result["status"][3:] == "RANK_DEFICIENT_GNSS_COMPONENT")
    assert result["expected_epoch_count"] == 6
    assert len(result["weights"]) == len(data["epoch_index"])
    assert not result["doppler_edge_valid"][2]


def test_no_raw_wls_anchor_never_promotes_a_reference_or_zero_seed():
    data, _, _ = _synthetic(n=4)
    data["spp_valid"][:] = False
    result = solve(data)
    assert result["terminal_status"] == "FAILED"
    assert not result["valid"].any()
    assert np.isnan(result["position_ecef_m"]).all()
    assert np.all(result["status"] == "NO_RAW_WLS_INITIALIZATION_IN_COMPONENT")
    assert np.all(result["observation_status"] == "NO_RAW_WLS_INITIALIZATION_IN_COMPONENT")


def test_limit_is_a_failure_not_a_completed_low_iteration_run():
    data, _, _ = _synthetic(n=5, outlier=100)
    result = solve(data, {"max_continuation_iterations": 1})
    assert result["terminal_status"] == "FAILED"
    assert np.all(result["status"] == "MAX_CONTINUATION_ITERATIONS")
    assert np.isnan(result["position_ecef_m"]).all()
    assert len(result["iterations"]) == 1


def test_bad_covariance_breaks_edge_and_nonmonotonic_time_is_rejected():
    data, _, _ = _synthetic(n=4)
    data["doppler_covariance"][1, 0, 0] = -1
    result = solve(data)
    assert result["valid"].all()
    assert len(result["components"]) == 2
    assert not result["doppler_edge_valid"][1]
    data["time_rel_s"][2] = data["time_rel_s"][1]
    with pytest.raises(ValueError, match="strictly increasing"):
        solve(data)


def test_committed_configuration_uses_fixed_paper_parameters():
    path = Path(__file__).resolve().parents[2] / "configs/paper_rebuild/fgo_comparison/GNC_PAPER_CONTRACT_20261004.json"
    config = json.loads(path.read_text())
    data, truth, _ = _synthetic(n=3)
    result = solve(data, config)
    assert result["valid"].all()
    np.testing.assert_allclose(result["position_ecef_m"], truth, atol=1e-5, rtol=0)
    assert config["c_gm"] == 2
    assert config["theta_divisor"] == 1.4
    assert config["weight_equation_variant"] == EQ21_SQUARED_GM


def test_printed_eq22_is_not_the_eq21_stationary_weight_or_same_gm_cost():
    residual = np.array([0., .7, -4., 80.])
    theta, c = 3., 2.
    printed = eq22_printed_weight(residual, theta, c)
    stationary = gnc_weight(residual, theta, c)
    a = theta * c ** 2
    derivative = residual ** 2 + a * (1 - 1 / np.sqrt(printed))
    assert np.all((printed >= 0) & (printed <= 1))
    assert np.max(np.abs(derivative)) > 1
    printed_joint = printed * residual ** 2 + a * (np.sqrt(printed) - 1) ** 2
    stationary_joint = stationary * residual ** 2 + a * (np.sqrt(stationary) - 1) ** 2
    assert np.all(printed_joint[1:] > stationary_joint[1:])


def test_eq22_diagnostic_is_explicit_and_does_not_claim_gm_auxiliary_optimality():
    data, _, _ = _synthetic(n=5, outlier=30.)
    result = solve(data, {"weight_equation_variant": EQ22_PRINTED_DIAGNOSTIC})
    assert result["terminal_status"] == "COMPLETED", result["components"]
    assert result["weight_equation"] == EQ22_PRINTED_DIAGNOSTIC
    assert "NOT_GM_AUXILIARY_OPTIMUM" in result["solve_mode"]
    assert all(row["surrogate_cost"] is None for row in result["iterations"])
    last = result["iterations"][-1]
    np.testing.assert_allclose(result["weights"], eq22_printed_weight(result["residuals"], last["theta"], 2), rtol=1e-13)
    assert last["auxiliary_cost_eq19_after_update"] > last["gm_cost_eq18_diagnostic"]


def test_eq23_initial_theta_is_not_floored_and_step_order_has_no_extra_solve():
    data, _, _ = _synthetic(n=3, measurement_noise=True)
    whitening = np.array([np.linalg.solve(np.linalg.cholesky(c), np.eye(3)) for c in data["doppler_covariance"][:-1]])
    graph = _prepare_graph(data, np.arange(3), np.ones(len(data["epoch_index"]), dtype=bool), whitening)
    initial, _ = graph.residual_jacobian(graph.initial_state)
    theta = 3 * np.max(initial[:graph.n_observation] ** 2) / 4
    result = solve(data)
    component = result["components"][0]
    assert component["theta_initial"] == theta
    actual = result["iterations"]
    expected=[]
    while True:
        expected.append(theta)
        theta /= 1.4
        if theta < 1:break
    assert [row["theta"] for row in actual] == expected
    assert len(result["weight_history"]) == len(expected)+1
    for row in actual:
        assert row["theta_after_reduction"] == row["theta"] / 1.4
        assert not row["updated_weights_applied_to_this_state"]
        np.testing.assert_allclose(row["auxiliary_cost_eq19_after_update"], row["surrogate_cost"], rtol=1e-13)
    assert component["theta_final"] == theta
    assert component["termination"] == "ALGORITHM1_THETA_LT_ONE_AFTER_REDUCTION"


def test_zero_eq23_exact_optimum_has_no_invented_floor_or_iteration():
    data, truth, clocks = _synthetic(n=1)
    data["initial_position_ecef_m"] = truth.copy()
    data["initial_clock_m"] = clocks.copy()
    result = solve(data)
    assert result["valid"].all()
    component = result["components"][0]
    assert component["theta_initial"] == 0
    assert component["theta_final"] == 0
    assert component["outer_iterations"] == 0
    assert component["termination"] == "ZERO_INITIAL_OBJECTIVE_EXACT_SOLUTION"
    np.testing.assert_array_equal(result["weights"], 1)
    np.testing.assert_array_equal(result["position_ecef_m"], truth)


def test_zero_eq23_with_nonzero_doppler_objective_is_undefined_not_fabricated_success():
    data, truth, clocks = _synthetic(n=2)
    data["initial_position_ecef_m"][:] = truth[0]
    data["initial_clock_m"][:] = clocks[0]
    data["sat_pos_ecef_m"][16:] = data["sat_pos_ecef_m"][:16]
    data["pseudorange_m"][16:] = data["pseudorange_m"][:16]
    result = solve(data)
    assert result["terminal_status"] == "FAILED"
    assert np.all(result["status"] == "UNDEFINED_EQ23_INITIAL_THETA")
    assert np.isnan(result["position_ecef_m"]).all()


def test_legacy_theta_one_extension_and_nonpaper_divisor_are_rejected():
    data, _, _ = _synthetic(n=2)
    with pytest.raises(ValueError, match="legacy theta-one"):
        solve(data, {"max_final_alternations": 1})
    with pytest.raises(ValueError, match="theta_divisor=1.4"):
        solve(data, {"theta_divisor": 1.5})
