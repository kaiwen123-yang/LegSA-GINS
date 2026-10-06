"""Noiseless/synthetic Wen TC correctness checks; no real-data result output."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from legsa_gins.paper_rebuild.fgo_comparison.wen_ahrs import (
    corrected_body_to_ned, integrate_ahrs, read_raw_quaternions,
)
from legsa_gins.paper_rebuild.fgo_comparison.wen_tc import WenInputError, WenProblem, solve


def _synthetic_graph(n=7, one_system=False):
    """Wide satellite geometry, constant speed, and true nonzero body bias."""
    times = np.arange(n, dtype=float)
    position = np.array([1.1e6, -4.7e6, 4.2e6]) + times[:, None] * [1.2, -.4, .15]
    velocity = np.tile([1.2, -.4, .15], (n, 1))
    bias = np.array([.02, -.03, .04])
    directions = np.array([[1, 1, 1], [-1, 1, 1], [1, -1, 1], [-1, -1, 1],
                           [1, 1, -1], [-1, 1, -1], [1, -1, -1], [-1, -1, -1]], float)
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    satellite = np.tile(position[0] + directions * 2.1e7, (n, 1))
    epoch = np.repeat(np.arange(n), 8)
    # Each constellation spans a tetrahedron; placing each system at one fixed
    # LOS-z would make its clock inseparable from receiver height in this case.
    system = np.zeros(n * 8, int) if one_system else np.tile([0, 1, 1, 0, 1, 0, 0, 1], n)
    clocks = np.column_stack((np.full(n, 1020.), np.full(n, -340.)))
    code = np.linalg.norm(position[epoch] - satellite, axis=1) + clocks[epoch, system]
    rng = np.random.default_rng(10421)
    data = {"time_rel_s": times, "epoch_index": epoch, "system": system,
            "sat_pos_ecef_m": satellite, "pseudorange_m": code, "pr_sigma_m": np.ones(n * 8),
            "initial_position_ecef_m": position + rng.normal(0, 3., (n, 3)),
            "initial_clock_m": clocks + 10.,
            "doppler_velocity_ecef_mps": np.full((n, 3), 1e9)}
    rotation = Rotation.from_euler("xyz", [8, -5, 20], degrees=True).as_matrix()
    ahrs = {"time_rel_s": times.copy(), "delta_velocity_ecef_mps": np.tile(rotation @ bias, (n-1, 1)),
            "bias_integral_ecef_s": np.tile(rotation, (n-1, 1, 1)),
            "lever_velocity_delta_ecef_mps": np.zeros((n-1, 3)), "interval_valid": np.ones(n-1, bool)}
    return data, ahrs, position, velocity, bias


def test_factor_jacobian_and_covariance_units():
    data, ahrs, *_ = _synthetic_graph(4)
    problem = WenProblem(data, ahrs)
    assert problem.config["motion_sigma_m"] == .3
    assert problem.config["bias_between_sigma_mps2"] == .01
    assert problem.config["velocity_link_sigma_mps"] == .15
    x = problem.x0.copy()
    x[:36] += np.random.default_rng(7).normal(0, .1, 36)
    residual, analytic = problem.residual_jacobian(x)
    step = .01  # metre-scale ECEF ranges require a resolvable FD perturbation.
    numeric = np.empty(analytic.shape)
    for j in range(problem.size):
        plus, minus = x.copy(), x.copy()
        plus[j] += step
        minus[j] -= step
        numeric[:, j] = (problem.residual_jacobian(plus, jacobian=False)
                         - problem.residual_jacobian(minus, jacobian=False)) / (2 * step)
    np.testing.assert_allclose(analytic.toarray(), numeric, atol=8e-7, rtol=2e-6)
    assert residual.shape == (32 + 6*3 + 3*3,)


@pytest.mark.parametrize("one_system", [False, True])
def test_noiseless_position_velocity_body_bias_and_clock_recovery(one_system):
    data, ahrs, position, velocity, bias = _synthetic_graph(one_system=one_system)
    result = solve(data, ahrs)
    assert result["converged"], result["optimizer_stop"]
    np.testing.assert_allclose(result["position_ecef_m"], position, atol=2e-4, rtol=0)
    np.testing.assert_allclose(result["velocity_ecef_mps"], velocity, atol=2e-5, rtol=0)
    np.testing.assert_allclose(result["accel_bias_body_mps2"], np.tile(bias, (len(position), 1)), atol=2e-5, rtol=0)
    np.testing.assert_allclose(result["clock_m"][:, 0], 1020., atol=2e-4, rtol=0)
    if one_system:
        assert np.isnan(result["clock_m"][:, 1]).all()
        assert WenProblem(data, ahrs).size == len(position) * 10
    else:
        np.testing.assert_allclose(result["clock_m"][:, 1], -340., atol=2e-4, rtol=0)
    assert result["doppler_factor_count"] == result["dual_yaw_factor_count"] == 0
    assert result["attitude_output"] is False


def test_missing_ins_link_preserves_nodes_and_missing_core_refuses():
    data, ahrs, position, *_ = _synthetic_graph()
    ahrs["interval_valid"][2] = False
    result = solve(data, ahrs)
    assert len(result["position_ecef_m"]) == len(position)
    assert result["missing_ins_interval_count"] == 1
    ahrs["interval_valid"][:] = False
    with pytest.raises(WenInputError, match="no complete AHRS/IMU interval"):
        solve(data, ahrs)


def test_unconverged_iterate_is_provisional_and_not_evaluable():
    data, ahrs, position, *_ = _synthetic_graph()
    result = solve(data, ahrs, {"max_iterations": 1})
    assert result["converged"] is False and result["terminal_status"] == "FAILED"
    assert result["status"].shape == (len(position),)
    assert set(result["status"]) == {"MAX_ITERATIONS_REACHED"}
    assert not result["valid"].any() and result["valid_epoch_count"] == 0
    for name in ("position_ecef_m", "velocity_ecef_mps", "accel_bias_body_mps2", "clock_m"):
        assert np.isnan(result[name]).all()
        assert np.isfinite(result["provisional_" + name]).all()


def test_missing_final_ins_removes_unconstrained_terminal_velocity():
    data, ahrs, position, velocity, _ = _synthetic_graph()
    ahrs["interval_valid"][-1] = False
    problem = WenProblem(data, ahrs)
    result = solve(data, ahrs)
    assert result["terminal_status"] == "COMPLETED"
    assert result["optimized_parameter_count"] == problem.size - 3
    assert result["unconstrained_parameter_columns"] == [57, 58, 59]
    assert np.isnan(result["velocity_ecef_mps"][-1]).all()
    assert result["velocity_valid"].tolist() == [True] * 6 + [False]
    np.testing.assert_allclose(result["position_ecef_m"], position, atol=2e-4, rtol=0)
    np.testing.assert_allclose(result["velocity_ecef_mps"][:-1], velocity[:-1], atol=2e-5, rtol=0)


def test_code_only_at_first_epoch_rejects_drift_gauge_without_prior():
    data, ahrs, position, *_ = _synthetic_graph()
    keep = data["epoch_index"] == 0
    for key in ("epoch_index", "system", "sat_pos_ecef_m", "pseudorange_m", "pr_sigma_m"):
        data[key] = data[key][keep]
    result = solve(data, ahrs)
    assert result["terminal_status"] == "FAILED"
    assert result["status"].tolist() == ["RANK_DEFICIENT_UNDAMPED_GRAPH"] * len(position)
    assert np.isnan(result["position_ecef_m"]).all() and not result["valid"].any()
    assert result["accepted_steps"] == 0 and result["optimized_parameter_count"] == 65
    assert result["initial_observability"]["rank"] == 3
    assert result["initial_observability"]["dimension"] == 9


def test_wxyz_flu_to_installed_frd_and_one_heading_gauge():
    install = Rotation.from_euler("xyz", [-1., 0., 0.], degrees=True).as_matrix()
    d = np.diag([1., -1., -1.])
    desired = Rotation.from_euler("xyz", [[4, -3, 38], [7, 2, 55]], degrees=True).as_matrix()
    alpha = .37
    gauge = Rotation.from_rotvec([0., 0., alpha]).as_matrix()
    raw = d @ gauge.T @ desired @ install @ d
    q = Rotation.from_matrix(raw).as_quat()[:, [3, 0, 1, 2]]
    actual = corrected_body_to_ned(q, alpha)
    np.testing.assert_allclose(actual, desired, atol=1e-14)
    # Rotate a physical raw FLU force to calibrated installed FRD, then to NED.
    raw_force = np.array([.2, -.4, 9.79])
    installed_force = install @ d @ raw_force
    np.testing.assert_allclose(actual @ installed_force, gauge @ d @ raw @ raw_force, atol=1e-14)


def _imu_example(*, rotating=False, missing=False):
    times = np.array([.02, 1.02, 2.02])
    raw = np.arange(0., 2.061, .02)
    if missing:
        raw = raw[(raw < .50) | (raw > .74)]
    dt = np.diff(raw)
    keep = np.flatnonzero((dt > 0) & (dt <= .1)) + 1
    rate = .4 if rotating else 0.
    rotation = Rotation.from_rotvec(np.column_stack((raw * 0., raw * 0., raw * rate))).as_matrix()
    imu = np.zeros((len(keep), 7))
    imu[:, 0] = raw[keep]
    imu[:, 3] = rate * dt[keep-1]
    imu[:, 6] = -9.8 * dt[keep-1]
    return times, raw, rotation, imu


def test_stationary_gravity_and_rotating_rigid_lever():
    for rotating in [False, True]:
        times, raw, rotation, imu = _imu_example(rotating=rotating)
        lever = np.array([.03, .03, -.30])
        result = integrate_ahrs(times=times, imu=imu, raw_times=raw, quaternion_times=raw,
            rotation_ecef_from_body=rotation, gravity_ecef_mps2=[0., 0., 9.8], seed_time_s=0., lever_body_m=lever)
        assert result["interval_valid"].all()
        np.testing.assert_allclose(result["delta_velocity_ecef_mps"], 0., atol=3e-14)
        np.testing.assert_allclose(result["interval_imu_coverage_s"], [1., 1.], atol=1e-14)
        rate = .4 if rotating else 0.
        node_rotation = Rotation.from_rotvec(np.column_stack((times * 0., times * 0., times * rate))).as_matrix()
        expected = np.diff(node_rotation @ np.cross([0., 0., rate], lever), axis=0)
        np.testing.assert_allclose(result["lever_velocity_delta_ecef_mps"], expected, atol=1e-14)


def test_skipped_raw_gap_is_not_integrated_using_neighbor_provider_dt():
    times, raw, rotation, imu = _imu_example(missing=True)
    result = integrate_ahrs(times=times, imu=imu, raw_times=raw, quaternion_times=raw,
        rotation_ecef_from_body=rotation, gravity_ecef_mps2=[0., 0., 9.8], seed_time_s=0., lever_body_m=[0., 0., 0.])
    assert result["interval_valid"].tolist() == [False, True]
    assert result["interval_imu_coverage_s"][0] < .8
    assert result["source_imu_skipped_interval_count"] == 1
    # A wrong interval mapping must fail, not quietly accept a different scale.
    imu[4, 0] += .002
    with pytest.raises(WenInputError, match="current-sample interval sequence"):
        integrate_ahrs(times=times, imu=imu, raw_times=raw, quaternion_times=raw,
            rotation_ecef_from_body=rotation, gravity_ecef_mps2=[0., 0., 9.8], seed_time_s=0., lever_body_m=[0., 0., 0.])


def test_raw_parser_includes_complete_final_imu_without_separator(tmp_path):
    def message(nsec, quat):
        return (f"stamp:\n  sec: 2000000000\n  nanosec: {nsec}\nimu_state:\n"
                f"  quaternion: {quat}\n  gyroscope: [0.0, 0.0, 0.0]\n"
                "  accelerometer:\n  - 0.0\n  - 0.0\n  - 9.8\n"
                "position: [987654321, 987654321, 987654321]\n")
    payload = (message(0, "[1, 0, 0, 0]") + "---\n" + message(2000000, "[0, 0, 0, 0]")
               + "---\n" + message(4000000, "[1.0001, 0, 0, 0]"))
    path = tmp_path / "synthetic_go2.txt"
    path.write_text(payload)
    parsed = read_raw_quaternions(path, 2000000000.)
    assert len(parsed["raw_time_rel_s"]) == 3
    assert len(parsed["quaternion_time_rel_s"]) == 2
    assert parsed["invalid_quaternion_messages"] == 1
    assert parsed["sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    np.testing.assert_allclose(parsed["quaternion_wxyz"], [[1, 0, 0, 0], [1, 0, 0, 0]])


def test_config_pins_dimensions_and_no_machine_paths():
    path = Path(__file__).parents[2] / "configs/paper_rebuild/fgo_comparison/WEN_TC_2021.json"
    text = path.read_text()
    config = json.loads(text)
    for pins in config["frozen_provider_sha256"].values():
        assert all(len(digest) == 64 for digest in pins.values())
    assert "/home/" not in text and "/mnt/" not in text
    assert config["motion_sigma_m"] == .3 and config["velocity_link_sigma_mps"] == .15


# 2026-10-04 paper-contract regression: exact Eq3/25 branch is distinct from
# the inherited high-rate left-bias integration above.
def _paper_graph(n=7):
    data,ahrs,position,velocity,bias=_synthetic_graph(n)
    ahrs["linear_acceleration_body_mps2"]=np.tile(bias,(n,1))
    ahrs["rotation_ned_from_body"]=np.tile(np.eye(3),(n,1,1))
    cfg={"ins_discretization":"RIGHT_ENDPOINT_ACCELERATION_EQ25","bias_endpoint":"RIGHT_EQ3"}
    return data,ahrs,position,velocity,bias,cfg


def test_paper_right_endpoint_nonconstant_bias_jacobian_and_dynamic_R_GL():
    data,ahrs,*_,cfg=_paper_graph(4)
    problem=WenProblem(data,ahrs,cfg)
    x=problem.x0.copy(); x[:36]+=np.random.default_rng(6421).normal(0,.1,36)
    _,analytic=problem.residual_jacobian(x)
    numeric=np.empty(analytic.shape)
    for j in range(problem.size):
        delta=.01
        plus,minus=x.copy(),x.copy(); plus[j]+=delta; minus[j]-=delta
        numeric[:,j]=(problem.residual_jacobian(plus,jacobian=False)-problem.residual_jacobian(minus,jacobian=False))/(2*delta)
    np.testing.assert_allclose(analytic.toarray(),numeric,rtol=2e-6,atol=8e-7)
    offset=problem.m+6*(problem.n-1)
    # INS0 uses b1, and the changing b0 is absent from its first block.
    assert analytic[offset:offset+3,6:9].nnz==0
    assert np.linalg.norm(analytic[offset:offset+3,15:18].toarray())>0


def test_paper_endpoint_noiseless_sensor_equations_recover_full_state():
    data,ahrs,position,velocity,bias,cfg=_paper_graph()
    result=solve(data,ahrs,cfg)
    assert result["converged"] and result["ins_discretization"]=="RIGHT_ENDPOINT_ACCELERATION_EQ25"
    assert result["R_GL_position_dependence"]=="CURRENT_RIGHT_NODE_ECEF_WITH_ANALYTIC_JACOBIAN"
    np.testing.assert_allclose(result["position_ecef_m"],position,rtol=0,atol=2e-4)
    np.testing.assert_allclose(result["velocity_ecef_mps"],velocity,rtol=0,atol=2e-5)
    np.testing.assert_allclose(result["accel_bias_body_mps2"],np.tile(bias,(len(position),1)),rtol=0,atol=2e-5)


def test_wgs84_R_GL_derivative_is_current_position_not_frozen_anchor():
    from legsa_gins.paper_rebuild.fgo_comparison.wen_tc import ned_to_ecef_and_derivative
    p=np.array([[1.1e6,-4.7e6,4.2e6],[1.3e6,-4.2e6,4.0e6]])
    rotation,derivative=ned_to_ecef_and_derivative(p)
    assert not np.array_equal(rotation[0],rotation[1])
    for k in range(3):
        step=np.eye(3)[k]*.1
        numeric=(ned_to_ecef_and_derivative(p+step)[0]-ned_to_ecef_and_derivative(p-step)[0])/.2
        np.testing.assert_allclose(derivative[:,:,:,k],numeric,rtol=1e-7,atol=1e-14)
    np.testing.assert_allclose(rotation @ np.swapaxes(rotation,1,2),np.tile(np.eye(3),(2,1,1)),atol=1e-14)


def test_eq25_endpoint_acceleration_differs_from_high_rate_average():
    times,raw,rotation,imu=_imu_example()
    dt=np.diff(raw)
    imu[:,4]=raw[1:]*dt # linearly changing physical body acceleration
    legacy=integrate_ahrs(times=times,imu=imu,raw_times=raw,quaternion_times=raw,
        rotation_ecef_from_body=rotation,gravity_ecef_mps2=[0,0,9.8],seed_time_s=0,lever_body_m=[0,0,0])
    paper=integrate_ahrs(times=times,imu=imu,raw_times=raw,quaternion_times=raw,
        rotation_ecef_from_body=rotation,gravity_ecef_mps2=[0,0,9.8],seed_time_s=0,lever_body_m=[0,0,0],
        ins_discretization="RIGHT_ENDPOINT_ACCELERATION_EQ25")
    np.testing.assert_allclose(paper["delta_velocity_ecef_mps"][:,0],times[1:]*np.diff(times),atol=1e-14)
    assert np.max(abs(paper["delta_velocity_ecef_mps"][:,0]-legacy["delta_velocity_ecef_mps"][:,0]))>.4
    np.testing.assert_allclose(paper["linear_acceleration_body_mps2"][:,2],0,atol=1e-14)
    assert paper["interval_valid"].all()
