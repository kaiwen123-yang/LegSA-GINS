from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature.ext05_pavlasek import (
    MEKF_STATUS,
    ExtendedPose,
    PavlasekIEKF,
    PavlasekFilterError,
    continuous_error_matrices,
    left_invariant_error_components,
    measurement_jacobian,
    process_drift_matrix,
    rotation_to_rpy_ned_frd_deg,
    se23_exp,
    skew,
    so3_exp,
    so3_log,
    stacked_position_covariance,
    van_loan_discretize,
)
from legsa_gins.paper_rebuild.horizontal_literature.ext05_provider import (
    BASELINE_BODY_FRD_M,
    IMU_INSTALL_RPY_DEG,
    LEVER_IMU_TO_RECEIVER1_FRD_M,
    ImuSample,
    _imu_only_messages,
    calibrate_static_imu,
    euler_rpy_deg_to_matrix,
    fixed_ecef_to_ned_rotation,
    initial_attitude_from_gravity_and_baseline,
    local_normal_gravity_mps2,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml"


def _pose(C: np.ndarray | None = None) -> ExtendedPose:
    return ExtendedPose(
        np.eye(3) if C is None else C,
        np.array([0.2, -0.1, 0.05]),
        np.array([2.0, -1.0, 0.3]),
    )


def _filter(*, two_receiver: bool, pose: ExtendedPose | None = None) -> PavlasekIEKF:
    return PavlasekIEKF(
        _pose() if pose is None else pose,
        np.diag([0.2] * 3 + [0.1] * 3 + [0.3] * 3),
        receiver1_from_imu_body_m=LEVER_IMU_TO_RECEIVER1_FRD_M,
        receiver2_from_receiver1_body_m=BASELINE_BODY_FRD_M,
        gyro_psd=[4.0e-4, 4.0e-4, 3.24e-4],
        accelerometer_psd=[2.89e-2, 2.25e-2, 5.76e-2],
        gravity_ned_mps2=[0.0, 0.0, 9.8017],
        two_receiver=two_receiver,
    )


def test_contract_records_exact_equations_frames_and_mekf_waiver():
    payload = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert payload["methods"]["primary"] == "EXT05A_PAVLASEK_TWO_RECEIVER_IEKF"
    assert payload["methods"]["appendix_baseline"]["status"] == MEKF_STATUS
    assert payload["methods"]["appendix_baseline"]["human_waiver"] is True
    assert payload["frames_and_geometry"]["attitude_direction"] == "C_nb_body_to_NED"
    assert payload["frames_and_geometry"]["left_invariant_error"] == "X_true_inverse_X_hat"
    assert payload["equation_to_code"]["equation_10_page_3_update_side"].startswith("ExtendedPose.right_correct")
    assert payload["equation_to_code"]["equations_15_16_pdf_page_4"].startswith("ext05_provider")
    assert payload["equation_to_code"]["equations_17_19_pdf_page_4"] == "PavlasekIEKF.propagate"
    assert payload["equation_to_code"]["equation_24_pdf_page_4"] == "ExtendedPose.matrix"
    assert payload["equation_to_code"]["equation_26_pdf_page_4"] == "process_drift_matrix"
    assert "not_reused_on_BY2" in payload["equation_to_code"]["equations_41_43_pdf_page_6"]
    assert payload["methods"]["appendix_baseline"]["id"] == "EXT05B_PAVLASEK_TWO_RECEIVER_MEKF_APPENDIX_EXACT"
    assert "STACKED_ABSOLUTE_RELATIVE_MEASUREMENT_CROSS_COVARIANCE_OMITTED" in payload["methods"]["appendix_baseline"]["defects"]
    assert payload["native_gate"]["trace_open_count"] == 0


def test_skew_and_so3_exponential():
    a = np.array([0.2, -0.3, 0.4])
    b = np.array([-1.0, 0.5, 2.0])
    assert np.allclose(skew(a) @ b, np.cross(a, b))
    C = so3_exp(a)
    assert np.allclose(C.T @ C, np.eye(3), atol=1e-14)
    assert np.linalg.det(C) == pytest.approx(1.0, abs=1e-14)


def test_se23_exponential_uses_so3_left_jacobian_columns():
    tangent = np.array([0.2, -0.1, 0.3, 1.0, 2.0, -0.5, -1.0, 0.4, 0.2])
    C, v, r = se23_exp(tangent)
    # Numerical integral of Exp(s*phi) rho ds is the SE_2(3) column.
    grid = (np.arange(20000) + 0.5) / 20000.0
    v_numeric = sum(so3_exp(s * tangent[:3]) @ tangent[3:6] for s in grid) / len(grid)
    r_numeric = sum(so3_exp(s * tangent[:3]) @ tangent[6:9] for s in grid) / len(grid)
    assert np.allclose(v, v_numeric, atol=2e-10)
    assert np.allclose(r, r_numeric, atol=2e-10)
    assert np.allclose(C, so3_exp(tangent[:3]))


def _compose(left: ExtendedPose, right: ExtendedPose) -> ExtendedPose:
    return ExtendedPose(
        left.C_nb @ right.C_nb,
        left.velocity_ned_mps + left.C_nb @ right.velocity_ned_mps,
        left.position_ned_m + left.C_nb @ right.position_ned_m,
    )


def test_paper_process_is_group_affine():
    X1 = _pose(so3_exp([0.2, -0.1, 0.05]))
    X2 = ExtendedPose(so3_exp([-0.1, 0.3, 0.2]), [0.4, 0.2, -0.1], [-0.2, 0.5, 0.9])
    identity = ExtendedPose(np.eye(3), np.zeros(3), np.zeros(3))
    omega = np.array([0.1, -0.2, 0.3])
    force = np.array([0.5, -1.0, -9.5])
    gravity = np.array([0.0, 0.0, 9.8])
    product = _compose(X1, X2)
    lhs = process_drift_matrix(product, omega, force, gravity)
    rhs = (
        process_drift_matrix(X1, omega, force, gravity) @ X2.matrix()
        + X1.matrix() @ process_drift_matrix(X2, omega, force, gravity)
        - X1.matrix() @ process_drift_matrix(identity, omega, force, gravity) @ X2.matrix()
    )
    assert np.allclose(lhs, rhs, atol=2e-14)


def test_eq31_eq32_are_state_estimate_independent():
    omega = [0.2, -0.3, 0.4]
    force = [1.0, -2.0, -9.0]
    A, L = continuous_error_matrices(omega, force)
    assert np.allclose(A[:3, :3], -skew(omega))
    assert np.allclose(A[3:6, :3], -skew(force))
    assert np.allclose(A[3:6, 3:6], -skew(omega))
    assert np.allclose(A[6:9, 3:6], np.eye(3))
    assert np.allclose(A[6:9, 6:9], -skew(omega))
    assert np.allclose(L[:3, :3], -np.eye(3))
    assert np.allclose(L[3:6, 3:6], -np.eye(3))


def test_eq27_eq29_left_invariant_error_components():
    true = ExtendedPose(so3_exp([0.1, -0.2, 0.3]), [1.0, 2.0, 3.0], [-2.0, 0.4, 1.0])
    delta = np.array([0.02, -0.01, 0.03, 0.4, -0.2, 0.1, -0.3, 0.5, 0.2])
    dC, dv, dr = se23_exp(delta)
    estimate = ExtendedPose(
        true.C_nb @ dC,
        true.velocity_ned_mps + true.C_nb @ dv,
        true.position_ned_m + true.C_nb @ dr,
    )
    C_error, v_error, r_error = left_invariant_error_components(true, estimate)
    assert np.allclose(C_error, dC)
    assert np.allclose(v_error, dv)
    assert np.allclose(r_error, dr)


def test_van_loan_matches_closed_form_random_walk():
    A = np.zeros((9, 9))
    L = np.zeros((9, 6))
    L[:6, :] = np.eye(6)
    Qc = np.diag(np.arange(1.0, 7.0))
    Phi, Qd = van_loan_discretize(A, L, Qc, 0.02)
    expected = np.zeros((9, 9))
    expected[:6, :6] = Qc * 0.02
    assert np.allclose(Phi, np.eye(9))
    assert np.allclose(Qd, expected, atol=1e-15)


def test_two_position_covariance_has_all_four_required_blocks():
    R1 = np.diag([0.04, 0.09, 0.16])
    R2 = np.diag([0.25, 0.36, 0.49])
    covariance = stacked_position_covariance(R1, R2)
    assert np.array_equal(covariance[:3, :3], R1)
    assert np.array_equal(covariance[:3, 3:], -R1)
    assert np.array_equal(covariance[3:, :3], -R1)
    assert np.array_equal(covariance[3:, 3:], R1 + R2)


def test_two_position_covariance_direct_monte_carlo_all_blocks():
    rng = np.random.Generator(np.random.PCG64(20260816))
    R1 = np.array([[0.04, 0.01, 0.0], [0.01, 0.09, -0.005], [0.0, -0.005, 0.16]])
    R2 = np.array([[0.25, -0.02, 0.01], [-0.02, 0.36, 0.0], [0.01, 0.0, 0.49]])
    count = 300_000
    n1 = rng.multivariate_normal(np.zeros(3), R1, count)
    n2 = rng.multivariate_normal(np.zeros(3), R2, count)
    samples = np.column_stack((n1, n2 - n1))
    empirical = np.cov(samples, rowvar=False, ddof=1)
    expected = stacked_position_covariance(R1, R2)
    for rows, columns in ((slice(0, 3), slice(0, 3)), (slice(0, 3), slice(3, 6)), (slice(3, 6), slice(0, 3)), (slice(3, 6), slice(3, 6))):
        assert np.allclose(empirical[rows, columns], expected[rows, columns], rtol=0.025, atol=0.002)


def test_left_invariant_measurement_linearization_eq37():
    true = ExtendedPose(so3_exp([0.1, -0.05, 0.4]), [0.0, 0.0, 0.0], [2.0, 1.0, -0.2])
    delta = np.array([2e-7, -3e-7, 1e-7, 0.0, 0.0, 0.0, 4e-7, -2e-7, 3e-7])
    dC, dv, dr = se23_exp(delta)
    estimate = ExtendedPose(
        true.C_nb @ dC,
        true.velocity_ned_mps + true.C_nb @ dv,
        true.position_ned_m + true.C_nb @ dr,
    )
    filter_ = _filter(two_receiver=True, pose=estimate)
    p1 = true.position_ned_m + true.C_nb @ LEVER_IMU_TO_RECEIVER1_FRD_M
    p2 = p1 + true.C_nb @ BASELINE_BODY_FRD_M
    diagnostics = filter_.update(p1, np.eye(3), receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=np.eye(3))
    H = measurement_jacobian(LEVER_IMU_TO_RECEIVER1_FRD_M, BASELINE_BODY_FRD_M, two_receiver=True)
    assert np.allclose(diagnostics.innovation, H @ delta, atol=2e-13)


def test_update_applies_negative_correction_on_right():
    estimate = ExtendedPose(so3_exp([0.0, 0.0, 0.08]), np.zeros(3), np.array([0.2, -0.1, 0.05]))
    before = np.linalg.norm(estimate.position_ned_m) + abs(rotation_to_rpy_ned_frd_deg(estimate.C_nb)[2])
    filter_ = _filter(two_receiver=True, pose=estimate)
    true = ExtendedPose(np.eye(3), np.zeros(3), np.zeros(3))
    p1 = true.position_ned_m + true.C_nb @ LEVER_IMU_TO_RECEIVER1_FRD_M
    p2 = p1 + true.C_nb @ BASELINE_BODY_FRD_M
    filter_.update(p1, np.eye(3) * 1e-6, receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=np.eye(3) * 1e-6)
    after = np.linalg.norm(filter_.pose.position_ned_m) + abs(rotation_to_rpy_ned_frd_deg(filter_.pose.C_nb)[2])
    assert after < before


def test_complete_update_matches_exp_minus_kz_and_joseph_covariance():
    pose = ExtendedPose(so3_exp([0.05, -0.03, 0.2]), [0.3, -0.1, 0.2], [1.0, 2.0, -0.4])
    filter_ = _filter(two_receiver=True, pose=pose)
    prior_C = filter_.pose.C_nb.copy()
    prior_v = filter_.pose.velocity_ned_mps.copy()
    prior_r = filter_.pose.position_ned_m.copy()
    prior_P = filter_.covariance.copy()
    p1 = prior_r + prior_C @ LEVER_IMU_TO_RECEIVER1_FRD_M + np.array([0.03, -0.02, 0.01])
    p2 = p1 + prior_C @ BASELINE_BODY_FRD_M + np.array([-0.01, 0.04, -0.02])
    R1 = np.diag([0.01, 0.02, 0.03])
    R2 = np.diag([0.04, 0.05, 0.06])
    H = measurement_jacobian(LEVER_IMU_TO_RECEIVER1_FRD_M, BASELINE_BODY_FRD_M, two_receiver=True)
    M = np.zeros((6, 6)); M[:3, :3] = prior_C.T; M[3:, 3:] = prior_C.T
    Rz = M @ stacked_position_covariance(R1, R2) @ M.T
    z = np.concatenate((prior_C.T @ (p1 - (prior_r + prior_C @ LEVER_IMU_TO_RECEIVER1_FRD_M)), prior_C.T @ ((p2 - p1) - prior_C @ BASELINE_BODY_FRD_M)))
    S = H @ prior_P @ H.T + Rz
    K = np.linalg.solve(S, H @ prior_P).T
    delta = K @ z
    expected = ExtendedPose(prior_C, prior_v, prior_r)
    expected.right_correct(delta)
    I_KH = np.eye(9) - K @ H
    expected_P = I_KH @ prior_P @ I_KH.T + K @ Rz @ K.T
    diagnostics = filter_.update(p1, R1, receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=R2)
    assert np.allclose(diagnostics.innovation, z)
    assert np.allclose(filter_.pose.C_nb, expected.C_nb, atol=2e-15)
    assert np.allclose(filter_.pose.velocity_ned_mps, expected.velocity_ned_mps, atol=2e-15)
    assert np.allclose(filter_.pose.position_ned_m, expected.position_ned_m, atol=2e-15)
    assert np.allclose(filter_.covariance, expected_P, atol=2e-15)
    assert np.all(np.isfinite(filter_.covariance))
    assert np.min(np.linalg.eigvalsh(filter_.covariance)) >= -1e-12


def test_covariance_and_measurement_covariance_validation_fail_closed():
    bad = np.eye(9); bad[0, 0] = -1.0
    with pytest.raises(PavlasekFilterError, match="positive semidefinite"):
        PavlasekIEKF(ExtendedPose(np.eye(3), np.zeros(3), np.zeros(3)), bad, receiver1_from_imu_body_m=LEVER_IMU_TO_RECEIVER1_FRD_M, receiver2_from_receiver1_body_m=BASELINE_BODY_FRD_M, gyro_psd=[1, 1, 1], accelerometer_psd=[1, 1, 1], gravity_ned_mps2=[0, 0, 9.8], two_receiver=False)
    filter_ = _filter(two_receiver=False)
    nonsymmetric = np.eye(3); nonsymmetric[0, 1] = 0.1
    with pytest.raises(PavlasekFilterError, match="symmetric"):
        filter_.update([2, -1, 0.3], nonsymmetric)
    negative = np.eye(3); negative[2, 2] = -0.1
    with pytest.raises(PavlasekFilterError, match="positive semidefinite"):
        stacked_position_covariance(np.eye(3), negative)


def _propagate_truth(pose: ExtendedPose, omega: np.ndarray, force: np.ndarray, gravity: float, dt: float) -> None:
    acceleration = pose.C_nb @ so3_exp(0.5 * dt * omega) @ force + np.array([0.0, 0.0, gravity])
    pose.position_ned_m = pose.position_ned_m + pose.velocity_ned_mps * dt + 0.5 * acceleration * dt * dt
    pose.velocity_ned_mps = pose.velocity_ned_mps + acceleration * dt
    pose.C_nb = pose.C_nb @ so3_exp(dt * omega)


def test_full_synthetic_paper_model_recovers_extended_pose():
    gravity = 9.8017
    truth = ExtendedPose(np.eye(3), np.array([0.2, -0.1, 0.05]), np.array([1.0, -0.5, 0.2]))
    estimate = ExtendedPose(so3_exp([0.03, -0.02, math.radians(25.0)]), [-0.1, 0.2, 0.0], [1.5, -0.9, 0.5])
    filter_ = _filter(two_receiver=True, pose=estimate)
    filter_.gravity = np.array([0.0, 0.0, gravity])
    R = np.eye(3) * 4e-4
    dt = 0.02
    for index in range(800):
        time_value = index * dt
        omega = np.array([0.08 * math.sin(0.7 * time_value), 0.06 * math.cos(0.4 * time_value), 0.12])
        inertial_acceleration = np.array([0.4 * math.sin(0.3 * time_value), 0.3 * math.cos(0.2 * time_value), 0.15 * math.sin(0.5 * time_value)])
        force = truth.C_nb.T @ (inertial_acceleration - np.array([0.0, 0.0, gravity]))
        _propagate_truth(truth, omega, force, gravity, dt)
        filter_.propagate(omega, force, dt)
        if index % 5 == 0:
            p1 = truth.position_ned_m + truth.C_nb @ LEVER_IMU_TO_RECEIVER1_FRD_M
            p2 = p1 + truth.C_nb @ BASELINE_BODY_FRD_M
            filter_.update(p1, R, receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=R)
    attitude_error = np.linalg.norm(so3_log(truth.C_nb.T @ filter_.pose.C_nb))
    assert math.degrees(attitude_error) < 1.0
    assert np.linalg.norm(filter_.pose.position_ned_m - truth.position_ned_m) < 0.03
    assert np.linalg.norm(filter_.pose.velocity_ned_mps - truth.velocity_ned_mps) < 0.03


def test_large_initial_yaw_error_converges_with_two_receivers():
    truth = ExtendedPose(np.eye(3), np.zeros(3), np.zeros(3))
    filter_ = _filter(two_receiver=True, pose=ExtendedPose(so3_exp([0.0, 0.0, math.radians(60.0)]), np.zeros(3), np.zeros(3)))
    R = np.eye(3) * 1e-5
    p1 = truth.position_ned_m + truth.C_nb @ LEVER_IMU_TO_RECEIVER1_FRD_M
    p2 = p1 + truth.C_nb @ BASELINE_BODY_FRD_M
    for _ in range(100):
        filter_.update(p1, R, receiver2_position_ned_m=p2, receiver2_covariance_ned_m2=R)
    yaw = rotation_to_rpy_ned_frd_deg(filter_.pose.C_nb)[2]
    yaw_error = (yaw + 180.0) % 360.0 - 180.0
    assert abs(yaw_error) < 0.2


def test_single_receiver_is_exact_paper_ablation():
    H = measurement_jacobian(LEVER_IMU_TO_RECEIVER1_FRD_M, BASELINE_BODY_FRD_M, two_receiver=False)
    assert H.shape == (3, 9)
    assert np.array_equal(H[:, :3], skew(LEVER_IMU_TO_RECEIVER1_FRD_M))
    assert np.array_equal(H[:, 6:9], -np.eye(3))
    filter_ = _filter(two_receiver=False)
    p1 = filter_.pose.position_ned_m + filter_.pose.C_nb @ LEVER_IMU_TO_RECEIVER1_FRD_M
    diagnostics = filter_.update(p1, np.eye(3) * 0.01)
    assert diagnostics.predicted_relative_ned_m is None
    assert diagnostics.innovation.shape == (3,)


def test_receiver_spacing_increases_attitude_information():
    R = np.eye(6) * 0.01
    information = []
    for spacing in (0.1, 0.35, 1.8):
        H = measurement_jacobian(LEVER_IMU_TO_RECEIVER1_FRD_M, [0.0, -spacing, 0.0], two_receiver=True)
        information.append(float(np.trace((H.T @ np.linalg.inv(R) @ H)[:3, :3])))
    assert information[0] < information[1] < information[2]


def test_fixed_ned_origin_and_physical_baseline_sign():
    origin = np.array([-2171613.3982, 4385611.7675, 4076721.9435])
    Cne = fixed_ecef_to_ned_rotation(origin)
    assert np.allclose(Cne @ Cne.T, np.eye(3), atol=1e-14)
    first_baseline = np.array([0.00818756, -0.35094770, -0.00128632])
    attitude, audit = initial_attitude_from_gravity_and_baseline(
        [0.0, 0.0, -9.8], first_baseline
    )
    predicted = attitude @ BASELINE_BODY_FRD_M
    assert np.dot(predicted[:2], first_baseline[:2]) > 0.0
    assert audit["yaw_ned_deg"] == pytest.approx(
        (math.degrees(math.atan2(first_baseline[1], first_baseline[0])) + 90.0) % 360.0
    )


def test_flu_to_frd_then_active_installation_order():
    install = euler_rpy_deg_to_matrix(*IMU_INSTALL_RPY_DEG)
    value_flu = np.array([1.0, 2.0, 3.0])
    expected = install @ np.array([1.0, -2.0, -3.0])
    assert np.allclose(install @ np.diag([1.0, -1.0, -1.0]) @ value_flu, expected)


def test_imu_only_parser_does_not_parse_quaternion_rpy_or_yaw(tmp_path):
    source = tmp_path / "by2.txt"
    source.write_text(
        """stamp:\n  sec: 10\n  nanosec: 20\nimu_state:\n  quaternion:\n    - THIS_MUST_NOT_BE_PARSED\n  gyroscope:\n    - 0.1\n    - 0.2\n    - 0.3\n  accelerometer:\n    - 1\n    - 2\n    - 3\n  rpy:\n    - ALSO_NOT_PARSED\nyaw_speed: NOT_PARSED\n---\n""",
        encoding="utf-8",
    )
    rows = list(_imu_only_messages(source))
    assert len(rows) == 1
    assert rows[0][0] == pytest.approx(10.00000002)
    assert np.array_equal(rows[0][1], [0.1, 0.2, 0.3])
    assert np.array_equal(rows[0][2], [1.0, 2.0, 3.0])


def test_imu_only_parser_accepts_ros2_same_indent_list_markers(tmp_path):
    source = tmp_path / "by2.txt"
    source.write_text(
        "stamp:\n  sec: 1\n  nanosec: 2\nimu_state:\n  gyroscope:\n  - 1\n  - 2\n  - 3\n  accelerometer:\n  - 4\n  - 5\n  - 6\n---\n",
        encoding="utf-8",
    )
    row = next(iter(_imu_only_messages(source)))
    assert np.array_equal(row[1], [1.0, 2.0, 3.0])
    assert np.array_equal(row[2], [4.0, 5.0, 6.0])


def test_input_only_static_calibration_and_gravity_sign():
    latitude, height = 39.9848298525, 41.779992
    gravity = local_normal_gravity_mps2(latitude, height)
    samples = tuple(
        ImuSample(
            100.0 + index * 0.01,
            np.array([0.01, -0.002, 0.003]),
            np.array([0.0, 0.0, -gravity]),
        )
        for index in range(601)
    )
    calibration = calibrate_static_imu(samples, latitude_deg=latitude, height_m=height)
    assert calibration.used_preregistered_initial_interval
    assert np.allclose(calibration.gyro_bias_frd_radps, [0.01, -0.002, 0.003])
    attitude, audit = initial_attitude_from_gravity_and_baseline(
        calibration.mean_specific_force_frd_mps2, [0.0, -0.35, 0.0]
    )
    assert np.allclose(attitude @ calibration.mean_specific_force_frd_mps2 + [0.0, 0.0, gravity], 0.0, atol=1e-12)
    assert audit["roll_deg"] == pytest.approx(0.0)
    assert audit["pitch_deg"] == pytest.approx(0.0)


def test_bias_free_static_propagation_remains_stationary():
    gravity = 9.8017
    filter_ = _filter(two_receiver=True, pose=ExtendedPose(np.eye(3), np.zeros(3), np.zeros(3)))
    filter_.gravity = np.array([0.0, 0.0, gravity])
    for _ in range(25):
        filter_.propagate([0.0, 0.0, 0.0], [0.0, 0.0, -gravity], 0.004)
    assert np.linalg.norm(filter_.pose.position_ned_m) < 1e-12
    assert np.linalg.norm(filter_.pose.velocity_ned_mps) < 1e-12
