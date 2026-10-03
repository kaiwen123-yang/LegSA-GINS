"""Synthetic correctness checks only; no real provider/reference is opened."""
import json
from pathlib import Path

import numpy as np
import pytest

gtsam = pytest.importorskip("gtsam")

from legsa_gins.paper_rebuild.fgo_comparison.oisam import (
    BandedMatrix, IncrementalQR, OiSAMGraph, attitude_trigger, gnss_factor,
    keys, key_layout, normal_system, preintegrate, preintegration_parameters,
    retract, run_inputs, nonlinear_optimize,
)
from legsa_gins.paper_rebuild.fgo_comparison.oisam_inputs import (
    SequenceInput, ecef_to_llh, exact_imu_intervals, imu_pieces, select_nodes,
)


def config():
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "configs/paper_rebuild/fgo_comparison/OISAM_2025.json").read_text())


def gnss_row(timestamp, valid=True):
    row = np.array([timestamp, 40.0, 116.0, 40.0, .02, .02, .03,
                    0., 0., 0., .05, .05, .05, 20., 1.5, 1., 1., 1.])
    if not valid:
        row[15] = 0
    return row


def static_imu(end=8., dt=.01, gravity=9.801554354839126):
    time = np.arange(round(end / dt) + 1) * dt
    out = np.zeros((len(time), 7))
    out[:, 0], out[:, 6] = time, -gravity * dt
    return out


def test_incremental_structured_qr_equals_full_normal_solution():
    rng = np.random.default_rng(76231)
    m, nodes = 3, 2
    matrix = BandedMatrix(nodes, m)
    matrix.add_block(0, 0, np.eye(m) * 3)
    j = rng.normal(size=(8, 2 * m))
    matrix.add_block(0, 0, j.T @ j + np.eye(2 * m))
    rhs = rng.normal(size=nodes * m)
    dense = matrix.dense()
    qr = IncrementalQR(matrix, rhs)
    np.testing.assert_allclose(qr.solve(), np.linalg.solve(dense, rhs), rtol=1e-10, atol=1e-10)
    for nodes in range(3, 9):
        inc = BandedMatrix(nodes, m)
        j = rng.normal(size=(8, 2 * m))
        block = j.T @ j + np.eye(2 * m)
        inc.add_block((nodes - 2) * m, (nodes - 2) * m, block)
        vector = np.zeros(nodes * m)
        vector[-2 * m:] = rng.normal(size=2 * m)
        expanded = np.zeros((nodes * m, nodes * m))
        expanded[:-m, :-m] = dense
        dense = expanded + inc.dense()
        rhs = np.r_[rhs, np.zeros(m)] + vector
        before = qr.rotations
        qr.append(inc, vector)
        np.testing.assert_allclose(qr.solve(), np.linalg.solve(dense, rhs), rtol=1e-10, atol=1e-10)
        full = BandedMatrix(nodes, m)
        for i in range(nodes):
            for k in range(max(0, i - 1), min(nodes, i + 2)):
                full.add_block(i * m, k * m, dense[i * m:(i + 1) * m, k * m:(k + 1) * m])
        np.testing.assert_allclose(qr.solve(), IncrementalQR(full, rhs).solve(), atol=1e-10)
        assert qr.r.data.shape == (nodes * m, 4 * m)
        assert qr.rotations - before < 9 * m * m


def test_gnss_lever_factor_sign_and_finite_difference():
    rotation = gtsam.Rot3.Ypr(.6, -.1, .2)
    pose = gtsam.Pose3(rotation, np.array([4., 8., -2.]))
    lever = np.array([.03, .03, -.3])
    measurement = pose.translation() + rotation.matrix() @ lever
    covariance = np.diag([.04, .09, .16])
    factor = gnss_factor(0, measurement, covariance, lever)
    values = gtsam.Values()
    values.insert(keys(0)[0], pose)
    a, b = factor.linearize(values).jacobian()
    assert a.shape == (3, 6)
    np.testing.assert_allclose(b, 0, atol=1e-12)
    expected = np.zeros_like(a)
    epsilon = 1e-6
    for i in range(6):
        delta = np.eye(6)[i] * epsilon
        plus, minus = pose.retract(delta), pose.retract(-delta)
        predicted_plus = plus.translation() + plus.rotation().matrix() @ lever
        predicted_minus = minus.translation() + minus.rotation().matrix() @ lever
        expected[:, i] = (predicted_plus - predicted_minus) / (2 * epsilon) / np.sqrt(np.diag(covariance))
    np.testing.assert_allclose(a, expected, rtol=1e-7, atol=1e-7)


def test_preintegration_residual_bias_and_manifold_jacobian():
    cfg = config()
    cfg["earth_rotation_radps"] = 0.0
    params, _ = preintegration_parameters(cfg, 9.8, .7)
    bias = gtsam.imuBias.ConstantBias(np.array([.02, -.03, .01]), np.array([.001, -.002, .003]))
    pieces = [(.01, np.array([.001, -.002, .2]) * .01,
               np.array([.3, -.1, -9.8]) * .01) for _ in range(100)]
    pim = preintegrate(params, bias, pieces)
    pose = gtsam.Pose3(gtsam.Rot3.Ypr(.1, -.03, .05), np.array([1., 2., 3.]))
    velocity = np.array([2., .3, -.2])
    next_state = pim.predict(gtsam.NavState(pose, velocity), bias)
    values = gtsam.Values()
    for idx, p, v in ((0, pose, velocity), (1, next_state.pose(), next_state.velocity())):
        x, vel, b = keys(idx)
        values.insert(x, p)
        values.insert(vel, v)
        values.insert(b, bias)
    x0, v0, b0 = keys(0)
    x1, v1, b1 = keys(1)
    factor = gtsam.CombinedImuFactor(x0, v0, x1, v1, b0, b1, pim)
    residual = factor.evaluateError(pose, velocity, next_state.pose(), next_state.velocity(), bias, bias)
    assert residual.shape == (15,)
    np.testing.assert_allclose(residual, 0, atol=1e-12)
    linear = factor.linearize(values)
    a, target = linear.jacobian()
    np.testing.assert_allclose(target, 0, atol=1e-8)
    whitening = gtsam.noiseModel.Gaussian.Covariance(pim.preintMeasCov())
    numerical = np.zeros_like(a)
    epsilon = 2e-7
    column = 0
    layout = key_layout([0, 1])
    for key in linear.keys():
        offset, width = layout[key]
        for local in range(width):
            delta = np.zeros(30)
            delta[offset + local] = epsilon
            plus, minus = retract(values, [0, 1], delta), retract(values, [0, 1], -delta)

            def error(val):
                return whitening.whiten(factor.evaluateError(val.atPose3(x0), val.atVector(v0),
                    val.atPose3(x1), val.atVector(v1), val.atConstantBias(b0), val.atConstantBias(b1)))

            numerical[:, column] = (error(plus) - error(minus)) / (2 * epsilon)
            column += 1
    np.testing.assert_allclose(a, numerical, rtol=3e-4, atol=2e-3)
    # Nonzero gyro/accelerometer bias sensitivity really exists in the factor.
    assert np.linalg.norm(a[:, -12:]) > 0


def test_earth_rate_removed_static_input_does_not_rotate_attitude():
    cfg = config()
    row = gnss_row(0.)
    graph = OiSAMGraph(cfg, row, cfg["gravity_mps2"]["BY2"])
    p0, v0, bias = graph.current()
    np.testing.assert_allclose(bias.gyroscope(), -p0.rotation().matrix().T @ graph.omega)
    imu = static_imu(1.)
    pim = preintegrate(graph.params, bias, imu_pieces(imu, 0., 1., .1))
    predicted = pim.predict(gtsam.NavState(p0, v0), bias)
    # First-order Earth model: attitude cancellation is exact for a fixed body.
    np.testing.assert_allclose(predicted.attitude().rpy(), p0.rotation().rpy(), atol=1e-10)
    assert np.linalg.norm(predicted.velocity()) < .001


def test_ajsw_qr_marginalization_and_static_noiseless_sequence():
    cfg = config()
    cfg.update(window_lower_nodes=3, window_upper_nodes=5, earth_rotation_radps=0.0)
    imu = static_imu(8.)
    rows = [gnss_row(float(i)) for i in range(9)]
    graph = OiSAMGraph(cfg, rows[0], cfg["gravity_mps2"]["BY2"])
    events = []
    for row in rows[1:]:
        events.append(graph.step(row[0], row, imu_pieces(imu, graph.last_time, row[0], .1)))
        output = graph.output(row[0], "OK")
        assert np.isfinite(output[:10]).all()
        np.testing.assert_allclose(graph.current()[1], 0, atol=1e-7)
        np.testing.assert_allclose(graph.current()[0].rotation().rpy(), np.deg2rad([0, 0, 20]), atol=1e-7)
    assert graph.counts["incremental_updates"] >= 2
    assert graph.counts["window_triggers"] >= 1
    assert graph.counts["marginalized_nodes"] >= 3
    assert len(graph.indices) < 5
    assert graph.counts["heading_factors"] == 0
    assert all(e["nonlinear_iterations"] <= 20 for e in events)


def test_missing_imu_creates_nan_and_registered_independent_restart():
    cfg = config()
    cfg["earth_rotation_radps"] = 0.0
    imu = static_imu(4.)
    imu = imu[(imu[:, 0] <= 1.) | (imu[:, 0] >= 1.3)]
    with pytest.raises(ValueError, match="IMU_GAP"):
        imu_pieces(imu, 1., 2., .1)
    nodes = [(float(i), gnss_row(float(i)), i) for i in range(5)]
    inputs = SequenceInput("BY2", np.vstack([n[1] for n in nodes]), imu, nodes, {})
    outputs, events = [], []
    result = run_inputs(inputs, cfg, outputs.append, events.append)
    assert len(outputs) == result["expected_nodes"] == 5
    assert outputs[2][-2] == 0 and np.isnan(outputs[2][1:10]).all()
    assert outputs[3][-2] == 1 and outputs[3][-1] == "INITIALIZED"
    assert result["A1_yaw_initialization_count"] == 2
    assert result["segments"][1]["start_s"] == 3.
    assert result["segments"][1]["reason"].startswith("IMU_GAP")


def test_missing_gnss_does_not_fabricate_position_factor():
    cfg = config()
    cfg["earth_rotation_radps"] = 0.0
    graph = OiSAMGraph(cfg, gnss_row(0.), cfg["gravity_mps2"]["BY2"])
    graph.step(1., None, imu_pieces(static_imu(1.), 0., 1., .1))
    assert graph.counts["gnss_factors"] == 1  # initial sensor position only
    assert graph.counts["imu_factors"] == 1
    assert np.isfinite(graph.output(1., "IMU_ONLY")[:10]).all()


def test_node_timestamps_and_attitude_thresholds_are_not_retuned():
    cfg = config()
    assert (cfg["window_lower_nodes"], cfg["window_upper_nodes"]) == (30, 40)
    assert cfg["nonlinear_max_iterations"] == 20
    rows = np.vstack([gnss_row(t) for t in (.05, .95, 2.05, 4.05)])
    nodes = select_nodes(rows, 4.1, .100001)
    assert [n[0] for n in nodes] == [.95, 2.05, 3., 4.05]
    assert nodes[2][1] is None
    trigger, delta = attitude_trigger(gtsam.Rot3.Ypr(np.deg2rad(179), 0, 0),
                                      gtsam.Rot3.Ypr(np.deg2rad(-179), 0, 0), np.array([3, 3, 15]))
    assert not trigger
    np.testing.assert_allclose(delta, [0., 0., 2.], atol=1e-10)


def test_nonzero_acceleration_known_states_through_incremental_and_schur():
    cfg = config()
    cfg.update(window_lower_nodes=3, window_upper_nodes=5, earth_rotation_radps=0.0)
    graph = OiSAMGraph(cfg, gnss_row(0.), cfg["gravity_mps2"]["BY2"])
    pose0 = graph.current()[0]
    acceleration = np.array([.4, -.2, .1])
    specific = pose0.rotation().matrix().T @ (acceleration - np.array([0, 0, cfg["gravity_mps2"]["BY2"]]))
    imu = static_imu(9.)
    imu[:, 4:7] = specific * .01
    lever = np.asarray(cfg["lever_imu_to_gnss1_frd_m"])
    for second in range(1, 10):
        expected_position = pose0.translation() + .5 * acceleration * second ** 2
        antenna = expected_position + pose0.rotation().matrix() @ lever
        row = gnss_row(float(second))
        row[1:4] = ecef_to_llh(graph.origin + graph.cne.T @ antenna)
        graph.step(float(second), row, imu_pieces(imu, second - 1., float(second), .1))
        np.testing.assert_allclose(graph.current()[0].translation(), expected_position, atol=2e-6)
        np.testing.assert_allclose(graph.current()[1], acceleration * second, atol=2e-6)
    assert graph.counts["incremental_updates"] > 0
    assert graph.counts["marginalized_nodes"] > 0


def test_actual_ceres_relinearization_and_nonzero_pose_chart_jacobian():
    from legsa_gins.paper_rebuild.fgo_comparison.ceres_relinearize import GTSAMCost
    cfg = config()
    graph = OiSAMGraph(cfg, gnss_row(0.), cfg["gravity_mps2"]["BY2"])
    perturbed = retract(graph.values, graph.indices,
                        np.r_[.02, -.03, .04, .3, -.2, .1, np.zeros(9)])
    solved, report = nonlinear_optimize(graph.factors, perturbed, graph.indices, cfg)
    assert report["backend"] == "Ceres" and report["ceres_version"] == "2.2.0"
    assert 0 < report["iterations"] <= 20
    assert report["final_cost"] < report["initial_cost"] * 1e-8
    np.testing.assert_allclose(solved.atPose3(keys(0)[0]).localCoordinates(graph.current()[0]), 0, atol=2e-6)
    cost = GTSAMCost(graph.factors[1], graph.values)  # antenna factor
    parameter = np.r_[.02, -.03, .04, .3, -.2, .1, np.zeros(9)]
    residual, jacobian = np.zeros(3), np.zeros(45)
    assert cost.Evaluate([parameter], residual, [jacobian])
    numerical = np.zeros((3, 15))
    for i in range(15):
        d = np.eye(15)[i] * 1e-6
        plus, minus = np.zeros(3), np.zeros(3)
        cost.Evaluate([parameter + d], plus, None)
        cost.Evaluate([parameter - d], minus, None)
        numerical[:, i] = (plus - minus) / 2e-6
    np.testing.assert_allclose(jacobian.reshape(3, 15), numerical, atol=2e-7, rtol=2e-7)


def test_raw_dt_restores_rounded_provider_intervals_without_gap_filling():
    raw = np.array([0., .0040004, .0080011, .5000003, .5040012])
    dt = np.diff(raw)
    retained = np.flatnonzero((dt > 0) & (dt <= .1)) + 1
    imu = np.zeros((3, 7))
    imu[:, 0] = np.round(raw[retained], 6)
    imu[:, 3] = .2 * dt[retained - 1]
    imu[:, 4:7] = dt[retained - 1, None] * [1., 2., 3.]
    intervals = exact_imu_intervals(imu, raw)
    parts = imu_pieces(imu, 0., .006, .1, intervals)
    np.testing.assert_allclose(sum(p[2] for p in parts), .006 * np.array([1., 2., 3.]), atol=1e-15)
    np.testing.assert_allclose(sum(p[1][2] for p in parts), .006 * .2, atol=1e-15)
    with pytest.raises(ValueError, match="IMU_GAP"):
        imu_pieces(imu, .006, .502, .1, intervals)
    parts = imu_pieces(imu, .5000003, .5040012, .1, intervals)
    np.testing.assert_allclose(parts[0][2], imu[-1, 4:7], atol=1e-15)
    wrong = imu.copy()
    wrong[0, 0] += 1e-4
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        exact_imu_intervals(wrong, raw)
