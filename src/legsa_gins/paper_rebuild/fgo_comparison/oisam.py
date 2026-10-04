"""Independent OiSAM-FGO reproduction (Yang et al., 2025, DOI 00173-w).

Paper mapping: Eq4 -> pinned OB_GINS PreintegrationEarth (paper contract),
legacy CombinedImuFactor retained only under its historical configuration; Eq5 ->
gnss_factor; Eq6 -> marginalize_oldest; Eqs13/14 -> normal_system;
Algorithm1/Figs4-5 -> BandedMatrix/IncrementalQR; Algorithm2 -> OiSAMGraph.step.

GTSAM 4.2 supplies state containers/manifold charts; only the historical
profile uses its preintegration. The paper contract uses pinned OB_GINS. Its
iSAM/iSAM2 solvers are not used. The normal matrix uses 4m scalars per row,
structured Givens rotations, an incremental tail cache and A-JSWR. Nonlinear
relinearization uses actual Ceres through pyceres, as in Algorithm2.
"""
from __future__ import annotations

import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import gtsam

from .oisam_inputs import (ecef_to_llh, ecef_to_ned_rotation, initialization_body_rate, initialization_valid, imu_pieces,
                          llh_to_ecef, position_valid, read_sequence, sha256)

M = 15


class BandedMatrix:
    """Block tridiagonal H plus QR fill, stored in N by 4m, Fig5.

    Row block k stores column blocks k-1 through k+2. During elimination all
    possible fill remains here; accessing a nonzero outside it is an error.
    """
    def __init__(self, nodes, block_size=M):
        self.m = int(block_size)
        self.n = int(nodes) * self.m
        self.data = np.zeros((self.n, 4 * self.m))

    def start(self, row):
        return (row // self.m - 1) * self.m

    def copy(self):
        result = BandedMatrix(self.n // self.m, self.m)
        result.data[:] = self.data
        return result

    def span(self, row, begin, end):
        start = self.start(row)
        if begin < start or end > start + 4 * self.m:
            raise ValueError("OI_QR_BAND_OVERFLOW")
        return self.data[row, begin - start:end - start]

    def add_block(self, row, col, block):
        for j, values in enumerate(np.asarray(block)):
            self.span(row + j, col, col + len(values))[:] += values

    def diagonal(self):
        return np.array([self.data[i, i - self.start(i)] for i in range(self.n)])

    def scaled(self, scale):
        result = self.copy()
        for i in range(self.n):
            a, b = max(0, self.start(i)), min(self.n, self.start(i) + 4 * self.m)
            result.span(i, a, b)[:] *= scale[i] * scale[a:b]
        return result

    def add_diagonal(self, value):
        for i in range(self.n):
            self.data[i, i - self.start(i)] += value

    def dense(self):
        """Small synthetic tests and at-most-two-node marginalization only."""
        out = np.zeros((self.n, self.n))
        for i in range(self.n):
            a, b = max(0, self.start(i)), min(self.n, self.start(i) + 4 * self.m)
            out[i, a:b] = self.span(i, a, b)
        return out


class IncrementalQR:
    """Algorithm1 with prefix-corrected last-two-node cache.

    The published cache description is ambiguous: restoring the raw tail into
    an already eliminated prefix discards prefix transformations. We cache the
    tail AFTER prefix elimination and BEFORE tail elimination. This explicitly
    documented interpretation is checked against complete QR/linear solves.
    """
    def __init__(self, normal: BandedMatrix, rhs, scale=None):
        self.m = normal.m
        self.scale = (1.0 / np.sqrt(np.maximum(normal.diagonal(), 1e-24))
                      if scale is None else np.asarray(scale).copy())
        self.r = normal.scaled(self.scale)
        self.rhs = np.asarray(rhs, float).copy() * self.scale
        self.rotations = 0
        self._eliminate(0)

    def _eliminate(self, begin):
        n, m = self.r.n, self.m
        tail = max(0, n - 2 * m)
        if begin > tail:
            raise ValueError("OI_CACHE_PREFIX_OVERRUN")
        for k in range(begin, n):
            if k == tail:
                self.tail_data = self.r.data[tail:].copy()
                self.tail_rhs = self.rhs[tail:].copy()
            lower_end = min(n, (k // m + 2) * m)
            end = min(n, (k // m + 3) * m)
            for i in range(lower_end - 1, k, -1):
                low = self.r.span(i, k, k + 1)[0]
                if low == 0.0:
                    continue
                high = self.r.span(k, k, k + 1)[0]
                radius = np.hypot(high, low)
                c, s = high / radius, low / radius
                top = self.r.span(k, k, end).copy()
                bottom = self.r.span(i, k, end).copy()
                self.r.span(k, k, end)[:] = c * top + s * bottom
                self.r.span(i, k, end)[:] = -s * top + c * bottom
                self.r.span(i, k, k + 1)[0] = 0.0
                bt, bi = self.rhs[k], self.rhs[i]
                self.rhs[k], self.rhs[i] = c * bt + s * bi, -s * bt + c * bi
                self.rotations += 1

    def append(self, increment: BandedMatrix, rhs):
        """Add only new factors touching previous and newly arriving nodes."""
        old_n = self.r.n
        if increment.n != old_n + self.m:
            raise ValueError("OI_INCREMENT_DIMENSION")
        tail = max(0, old_n - 2 * self.m)
        expanded = BandedMatrix(increment.n // self.m, self.m)
        expanded.data[:old_n] = self.r.data
        expanded.data[tail:old_n] = self.tail_data
        vector = np.zeros(increment.n)
        vector[:old_n] = self.rhs
        vector[tail:old_n] = self.tail_rhs
        new_scale = 1.0 / np.sqrt(np.maximum(increment.diagonal()[old_n:], 1e-24))
        self.scale = np.r_[self.scale, new_scale]
        scaled = increment.scaled(self.scale)
        if np.any(scaled.data[:old_n - self.m] != 0) or np.any(np.asarray(rhs)[:old_n - self.m] != 0):
            raise ValueError("OI_INCREMENT_TOUCHES_OLD_PREFIX")
        expanded.data += scaled.data
        vector += np.asarray(rhs) * self.scale
        self.r, self.rhs = expanded, vector
        self._eliminate(tail)

    def solve(self):
        n, m = self.r.n, self.m
        y = np.zeros(n)
        for i in range(n - 1, -1, -1):
            end = min(n, (i // m + 3) * m)
            row = self.r.span(i, i, end)
            if not np.isfinite(row).all() or abs(row[0]) < 1e-15:
                raise np.linalg.LinAlgError("OI_QR_SINGULAR_OR_NONFINITE")
            y[i] = (self.rhs[i] - row[1:] @ y[i + 1:end]) / row[0]
        result = self.scale * y
        if not np.isfinite(result).all():
            raise np.linalg.LinAlgError("OI_QR_NONFINITE_SOLUTION")
        return result


def keys(index):
    return (gtsam.symbol("x", index), gtsam.symbol("v", index), gtsam.symbol("b", index))


def key_layout(indices):
    result = {}
    for i, index in enumerate(indices):
        for key, offset, width in zip(keys(index), (0, 6, 9), (6, 3, 6)):
            result[key] = (i * M + offset, width)
    return result


def normal_system(factors, values, indices):
    """Eqs13/14, assemble whitened J'J and J'b factor by factor.

    Never allocate the full dense window matrix. A single IMU factor involves
    only two 15-dimensional states; marginalization retains a one-state prior.
    """
    matrix, rhs = BandedMatrix(len(indices)), np.zeros(len(indices) * M)
    layout = key_layout(indices)
    for factor in factors:
        linear = factor.linearize(values)
        jac, target = linear.jacobian()
        cursor, blocks = 0, []
        for key in linear.keys():
            offset, width = layout[key]
            block = jac[:, cursor:cursor + width]
            blocks.append((offset, block))
            rhs[offset:offset + width] += block.T @ target
            cursor += width
        for offset_i, block_i in blocks:
            for offset_j, block_j in blocks:
                matrix.add_block(offset_i, offset_j, block_i.T @ block_j)
    return matrix, rhs


def retract(values, indices, delta):
    vector = gtsam.VectorValues()
    for key, (offset, width) in key_layout(indices).items():
        vector.insert(key, np.asarray(delta[offset:offset + width]))
    return values.retract(vector)


def gnss_factor(index, position_ned, covariance_ned, lever):
    """Eq5, GNSS1 antenna p+R*lever, not IMU position masquerading as GNSS."""
    key = keys(index)[0]
    lever = np.asarray(lever, float)
    x, y, z = lever
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])

    def error(_factor, values, jacobians):
        pose = values.atPose3(key)
        rotation = pose.rotation().matrix()
        if jacobians is not None:
            jacobians[0] = np.c_[-rotation @ cross, rotation]
        return pose.translation() + rotation @ lever - position_ned

    return gtsam.CustomFactor(gtsam.noiseModel.Gaussian.Covariance(covariance_ned), [key], error)


def preintegration_parameters(config, gravity, latitude_rad):
    params = gtsam.PreintegrationCombinedParams.MakeSharedD(float(gravity))
    params.setGyroscopeCovariance(np.eye(3) * config["gyro_white_noise_rad_sqrt_s"] ** 2)
    params.setAccelerometerCovariance(np.diag(np.square(config["accel_white_noise_mps_sqrt_s"])))
    params.setIntegrationCovariance(np.eye(3) * config["integration_covariance_m2ps3"])
    factor = 2.0 / config["bias_correlation_time_s"]
    params.setBiasOmegaCovariance(np.eye(3) * config["gyro_bias_stationary_std_radps"] ** 2 * factor)
    params.setBiasAccCovariance(np.diag(np.square(config["accel_bias_stationary_std_mps2"])) * factor)
    params.setBiasAccOmegaInit(np.eye(6) * config["preintegration_bias_initial_covariance"])
    omega = config["earth_rotation_radps"] * np.array([np.cos(latitude_rad), 0, -np.sin(latitude_rad)])
    params.setOmegaCoriolis(omega)
    # Local normal gravity already includes the centrifugal term at the origin.
    params.setUse2ndOrderCoriolis(False)
    return params, omega


def preintegrate(params, bias, pieces):
    result = gtsam.PreintegratedCombinedMeasurements(params, bias)
    for dt, dtheta, dvel in pieces:
        result.integrateMeasurement(np.asarray(dvel) / dt, np.asarray(dtheta) / dt, float(dt))
    return result


def attitude_trigger(previous, current, thresholds_deg):
    delta = (np.rad2deg(current.rpy() - previous.rpy()) + 180.0) % 360.0 - 180.0
    return bool(np.any(np.abs(delta) > thresholds_deg)), delta


def nonlinear_optimize(factors, initial, indices, config):
    """Algorithm2's Ceres branch; OiSAM incremental QR remains independent."""
    from .ceres_relinearize import optimize
    return optimize(factors, initial, indices, config)


def marginalize_oldest(factors, values, indices):
    """Eq6: Schur-eliminate only factors touching the oldest node.

    Adding the Schur complement of the whole graph would double-count retained
    factors. A chain leaves exactly one 15-dimensional separator state.
    """
    old, nxt = indices[:2]
    old_keys = set(keys(old))
    eliminate = [f for f in factors if old_keys.intersection(f.keys())]
    retained = [f for f in factors if not old_keys.intersection(f.keys())]
    h, b = normal_system(eliminate, values, [old, nxt])
    dense = h.dense()
    aa, ab, bb = dense[:M, :M], dense[:M, M:], dense[M:, M:]
    # Equilibrate the eliminated block to avoid mixing rad, m and tiny bias units.
    scale = 1.0 / np.sqrt(np.maximum(np.diag(aa), 1e-24))
    scaled_aa = aa * scale[:, None] * scale[None, :]
    solved = np.linalg.solve(scaled_aa, np.c_[scale[:, None] * ab, scale * b[:M]])
    solved *= scale[:, None]
    information = bb - ab.T @ solved[:, :M]
    target = b[M:] - ab.T @ solved[:, M]
    information = (information + information.T) / 2.0
    d = 1.0 / np.sqrt(np.maximum(np.diag(information), 1e-24))
    eig, vectors = np.linalg.eigh(information * d[:, None] * d[None, :])
    if eig.min() < -1e-8 * max(1.0, eig.max()):
        raise np.linalg.LinAlgError("MARGINAL_INFORMATION_INDEFINITE")
    eig = np.maximum(eig, 0.0)
    root = np.sqrt(eig)[:, None] * vectors.T
    a = root / d[None, :]
    transformed = vectors.T @ (d * target)
    right = np.divide(transformed, np.sqrt(eig), out=np.zeros(M), where=eig > 1e-14)
    x, v, bias = keys(nxt)
    prior = gtsam.JacobianFactor(x, a[:, :6], v, a[:, 6:9], bias, a[:, 9:],
                                  right, gtsam.noiseModel.Unit.Create(M))
    anchor = gtsam.Values()
    anchor.insert(x, values.atPose3(x))
    anchor.insert(v, values.atVector(v))
    anchor.insert(bias, values.atConstantBias(bias))
    retained.append(gtsam.LinearContainerFactor(prior, anchor))
    reduced = gtsam.Values(values)
    for key in old_keys:
        reduced.erase(key)
    return retained, reduced, indices[1:]


class OiSAMGraph:
    """One continuous IMU segment; no reference or other solution is accepted."""
    def __init__(self, config, row, gravity, *, init_body_rate, seed_piece=None):
        self.config = config
        self.gravity = float(gravity)
        self.last_piece = seed_piece
        self.backend = config.get("preintegration_backend", "GTSAM_LEGACY")
        if self.backend == "OB_GINS_EARTH_PINNED" and seed_piece is None:
            raise ValueError("IMU_UPSTREAM_CONING_SEED_REQUIRED")
        self.origin_llh = row[1:4].copy()
        self.origin = llh_to_ecef(self.origin_llh)
        self.cne = ecef_to_ned_rotation(self.origin_llh)
        self.params, self.omega = preintegration_parameters(config, gravity, np.deg2rad(row[1]))
        roll, pitch = np.deg2rad(config["initial_roll_pitch_deg"])
        rotation = gtsam.Rot3.Ypr(np.deg2rad(row[13]), pitch, roll)
        lever = np.asarray(config["lever_imu_to_gnss1_frd_m"])
        pose = gtsam.Pose3(rotation, -rotation.matrix() @ lever)
        init_body_rate = np.asarray(init_body_rate, float)
        if init_body_rate.shape != (3,) or not np.isfinite(init_body_rate).all():
            raise ValueError("IMU_INVALID_INITIAL_BODY_RATE")
        # The provider velocity belongs to GNSS1, while the graph velocity
        # belongs to the IMU. The calibrated rate already excludes the frozen
        # initial gyro mean; do not add Earth rate or installation again.
        lever_velocity = rotation.matrix() @ np.cross(init_body_rate, lever)
        vel_valid = row[16] > 0.5 and np.isfinite(row[7:13]).all() and np.all(row[10:13] > 0)
        velocity = row[7:10] - lever_velocity if vel_valid else np.zeros(3)
        gyro_bias = -rotation.matrix().T @ self.omega if config["earth_rate_removed_by_preprocessing"] else np.zeros(3)
        bias = gtsam.imuBias.ConstantBias(np.zeros(3), gyro_bias)
        self.values = gtsam.Values()
        x, v, b = keys(0)
        self.values.insert(x, pose)
        self.values.insert(v, velocity)
        self.values.insert(b, bias)
        self.indices = [0]
        attitude_std = np.deg2rad([*config["initial_roll_pitch_std_deg"], row[14]])
        velocity_std = row[10:13] if vel_valid else np.full(3, config["initial_missing_velocity_std_mps"])
        self.initial_velocity = {
            "mode": "GNSS1_velocity_minus_R_omega_cross_lever" if vel_valid else "zero_with_broad_prior_missing_GNSS_velocity",
            "gnss1_velocity_ned_mps": row[7:10].tolist() if vel_valid else None,
            "lever_velocity_ned_mps": lever_velocity.tolist(),
            "imu_velocity_ned_mps": velocity.tolist(), "prior_std_mps": velocity_std.tolist()}
        bias_std = np.r_[config["initial_accelerometer_bias_std_mps2"],
                         np.full(3, config["gyro_bias_stationary_std_radps"])]
        self.factors = [gtsam.PoseRotationPrior3D(x, pose, gtsam.noiseModel.Diagonal.Sigmas(attitude_std)),
                        gnss_factor(0, np.zeros(3), np.diag(row[4:7] ** 2), lever),
                        gtsam.PriorFactorVector(v, velocity, gtsam.noiseModel.Diagonal.Sigmas(velocity_std)),
                        gtsam.PriorFactorConstantBias(b, bias, gtsam.noiseModel.Diagonal.Sigmas(bias_std))]
        # Initial position enters once, at the antenna, separately from the
        # one-time attitude prior. This preserves lever/attitude coupling.
        self.anchors = gtsam.Values(self.values)
        self.qr = None
        self.last_time = float(row[0])
        self.next_index = 1
        self.counts = {"full_relinearizations": 0, "incremental_updates": 0,
                       "initial_qr_builds": 0, "marginalized_nodes": 0,
                       "imu_factors": 0, "gnss_factors": 1, "heading_factors": 0,
                       "initial_attitude_priors": 1,
                       "givens_rotations": 0, "nonlinear_max_iterations": 0,
                       "attitude_triggers": 0, "window_triggers": 0,
                       "nonlinear_converged_calls": 0, "nonlinear_usable_limit_calls": 0}

    def current(self):
        x, v, b = keys(self.indices[-1])
        return self.values.atPose3(x), self.values.atVector(v), self.values.atConstantBias(b)

    def step(self, timestamp, row, pieces):
        before_rotation = self.current()[0].rotation()
        prev = self.indices[-1]
        index = self.next_index
        self.next_index += 1
        xp, vp, bp = keys(prev)
        x, v, b = keys(index)
        prior_bias = self.values.atConstantBias(bp)
        if self.backend == "OB_GINS_EARTH_PINNED":
            from .obgins_preintegration import EarthPreintegration
            pim = EarthPreintegration(self.config, self.origin_llh, self.gravity,
                self.values.atPose3(xp), self.values.atVector(vp), prior_bias,
                self.last_time, pieces, self.last_piece)
            predicted_pose, predicted_velocity, _ = pim.predict()
            new_factors = [pim.factor(keys(prev), keys(index))]
            self.last_piece = pim.last_piece
        elif self.backend == "GTSAM_LEGACY":
            pim = preintegrate(self.params, prior_bias, pieces)
            predicted = pim.predict(gtsam.NavState(self.values.atPose3(xp), self.values.atVector(vp)), prior_bias)
            predicted_pose, predicted_velocity = predicted.pose(), predicted.velocity()
            new_factors = [gtsam.CombinedImuFactor(xp, vp, x, v, bp, b, pim)]
        else:
            raise ValueError("UNKNOWN_PREINTEGRATION_BACKEND")
        for values in (self.values, self.anchors):
            values.insert(x, predicted_pose)
            values.insert(v, predicted_velocity)
            values.insert(b, prior_bias)
        self.indices.append(index)
        self.counts["imu_factors"] += 1
        if position_valid(row):
            p = self.cne @ (llh_to_ecef(row[1:4]) - self.origin)
            cn_current = ecef_to_ned_rotation(row[1:4])
            transform = self.cne @ cn_current.T
            covariance = transform @ np.diag(row[4:7] ** 2) @ transform.T
            new_factors.append(gnss_factor(index, p, covariance, self.config["lever_imu_to_gnss1_frd_m"]))
            self.counts["gnss_factors"] += 1
        self.factors.extend(new_factors)
        length = len(self.indices)
        diagnostics = {"time_rel_s": timestamp, "window_nodes_before": length,
                       "mode": "", "nonlinear_iterations": 0, "attitude_increment_deg": None}
        if length < self.config["window_lower_nodes"]:
            self._relinearize(diagnostics)
            diagnostics["mode"] = "NONLINEAR_WARMUP"
        else:
            if self.qr is None:
                h, rhs = normal_system(self.factors, self.anchors, self.indices)
                self.qr = IncrementalQR(h, rhs)
                self.counts["initial_qr_builds"] += 1
                added_rotations = self.qr.rotations
                diagnostics["mode"] = "OISAM_BUILD"
            else:
                h, rhs = normal_system(new_factors, self.anchors, self.indices)
                old_rotations = self.qr.rotations
                self.qr.append(h, rhs)
                self.counts["incremental_updates"] += 1
                added_rotations = self.qr.rotations - old_rotations
                diagnostics["mode"] = "OISAM_INCREMENTAL"
            self.counts["givens_rotations"] += added_rotations
            self.values = retract(self.anchors, self.indices, self.qr.solve())
            triggered, angles = attitude_trigger(before_rotation, self.current()[0].rotation(),
                                                  self.config["relinearize_attitude_increment_deg"])
            window_trigger = length >= self.config["window_upper_nodes"]
            diagnostics["attitude_increment_deg"] = angles.tolist()
            if triggered or window_trigger:
                self.counts["attitude_triggers"] += int(triggered)
                self.counts["window_triggers"] += int(window_trigger)
                self._relinearize(diagnostics)
                diagnostics["mode"] += "+AJSWR_RELINEARIZE"
                while len(self.indices) >= self.config["window_lower_nodes"]:
                    self.factors, self.values, self.indices = marginalize_oldest(self.factors, self.values, self.indices)
                    self.counts["marginalized_nodes"] += 1
                self.anchors = gtsam.Values(self.values)
                self.qr = None
        self.last_time = timestamp
        diagnostics["window_nodes_after"] = len(self.indices)
        return diagnostics

    def _relinearize(self, diagnostics):
        self.values, result = nonlinear_optimize(self.factors, self.values, self.indices, self.config)
        self.anchors = gtsam.Values(self.values)
        self.qr = None
        self.counts["full_relinearizations"] += 1
        self.counts["nonlinear_max_iterations"] = max(self.counts["nonlinear_max_iterations"], result["iterations"])
        self.counts["givens_rotations"] += result["givens_rotations"]
        diagnostics["nonlinear_iterations"] = result["iterations"]
        self.counts["nonlinear_converged_calls"] += int(result["converged"])
        self.counts["nonlinear_usable_limit_calls"] += int(not result["converged"] and result["solution_usable"])
        diagnostics["nonlinear_status"] = result["termination"]
        diagnostics["nonlinear_converged"] = result["converged"]
        diagnostics["nonlinear_solution_usable"] = result["solution_usable"]
        diagnostics["nonlinear_backend"] = result["backend"]
        diagnostics["ceres_report"] = result["brief_report"]
        diagnostics["cost"] = result["final_cost"]

    def output(self, timestamp, status):
        pose, velocity, _ = self.current()
        ecef = self.origin + self.cne.T @ pose.translation()
        vel = self.cne.T @ velocity
        current_cne = ecef_to_ned_rotation(ecef_to_llh(ecef))
        current_rotation = gtsam.Rot3(current_cne @ self.cne.T @ pose.rotation().matrix())
        angles = np.rad2deg(current_rotation.rpy())
        result = [timestamp, *ecef, *vel, *angles, 1, status]
        if not np.isfinite(result[:10]).all():
            raise np.linalg.LinAlgError("NONFINITE_OUTPUT_STATE")
        return result


STATE_COLUMNS = ["time_rel_s", "x_ecef_m", "y_ecef_m", "z_ecef_m", "vx_ecef_mps",
                 "vy_ecef_mps", "vz_ecef_mps", "roll_deg", "pitch_deg", "yaw_deg", "valid", "status"]


def run_inputs(inputs, config, write_state, write_event, *, graph_factory=None):
    """Execute supplied sensor arrays; shared by production and synthetic tests."""
    graph = None
    segments, failures = [], []
    pending_reason = "INITIAL_SENSOR_ALIGNMENT"
    last_node = None
    finite_count = 0
    aggregate = {}
    fatal_reason = None
    input_failure = None
    maximum_endpoint_wait_s = 0.0

    def close_segment():
        nonlocal graph
        if graph is not None:
            segments[-1]["end_s"] = graph.last_time
            segments[-1]["core_counts"] = dict(graph.counts)
            for key, value in graph.counts.items():
                aggregate[key] = (max(aggregate.get(key, 0), value) if key == 'nonlinear_max_iterations'
                                  else aggregate.get(key, 0) + value)
            graph = None

    initialization_source=config.get("initialization_source", "same_epoch_GNSS1_position_A1_yaw_and_completed_calibrated_IMU_rate")
    uses_a1=config.get("initialization_yaw_role", "A1") == "A1"
    for timestamp, row, expected_second in inputs.nodes:
        if fatal_reason is not None or input_failure is not None:
            unavailable = "AFTER_NUMERICAL_SOLVER_FAILURE" if fatal_reason else "AFTER_INPUT_GAP_NO_REINITIALIZATION"
            write_state([timestamp, *([float("nan")] * 9), 0, unavailable])
            failures.append({"time_rel_s": timestamp, "reason": unavailable})
            write_event({"time_rel_s": timestamp, "expected_second": expected_second,
                         "mode": "UNAVAILABLE", "reason": unavailable})
            last_node = timestamp
            continue
        try:
            if graph is None:
                if not initialization_valid(row):
                    raise ValueError("WAITING_FOR_VALID_POSITION_AND_INITIAL_YAW")
                if not inputs.imu[0, 0] <= timestamp <= inputs.imu[-1, 0]:
                    raise ValueError("IMU_SUPPORT_UNAVAILABLE")
                if last_node is not None:
                    imu_pieces(inputs.imu, last_node, timestamp, config["maximum_imu_interval_s"], inputs.imu_intervals)
                init_body_rate, rate_source = initialization_body_rate(
                    inputs.imu, timestamp, config["maximum_imu_interval_s"], inputs.imu_intervals)
                seed_row = inputs.imu[rate_source["provider_row_index_zero_based"]]
                seed_dt = rate_source["interval_end_rel_s"] - rate_source["interval_start_rel_s"]
                seed_piece = (seed_dt, seed_row[1:4].copy(), seed_row[4:7].copy())
                factory = OiSAMGraph if graph_factory is None else graph_factory
                graph = factory(config, row, config["gravity_mps2"][inputs.sequence],
                                   init_body_rate=init_body_rate, seed_piece=seed_piece)
                segments.append({"segment_id": len(segments) + 1, "start_s": timestamp,
                                 "reason": pending_reason, "initialization_source": initialization_source,
                                 "A1_yaw_initialization_count": int(uses_a1), "initial_yaw_deg": float(row[13]),
                                 "initial_body_rate": rate_source, "initial_velocity": graph.initial_velocity,
                                 "initial_gyro_bias_radps": graph.current()[2].gyroscope().tolist()})
                event = {"time_rel_s": timestamp, "mode": "SEGMENT_INITIALIZATION"}
                status = "INITIALIZED"
                available_time = timestamp
            else:
                pieces = imu_pieces(inputs.imu, graph.last_time, timestamp, config["maximum_imu_interval_s"], inputs.imu_intervals)
                event = graph.step(timestamp, row, pieces)
                status = "OK" if position_valid(row) else "IMU_ONLY_NO_GNSS_POSITION"
                if event.get("nonlinear_converged") is False:
                    status += "_USABLE_NONLINEAR_ITERATION_LIMIT"
                endpoint_times = inputs.imu[:, 0] if inputs.imu_intervals is None else inputs.imu_intervals[:, 1]
                endpoint = int(np.searchsorted(endpoint_times, timestamp, side="left"))
                available_time = max(timestamp, float(endpoint_times[endpoint]))
            maximum_endpoint_wait_s = max(maximum_endpoint_wait_s, available_time - timestamp)
            write_state(graph.output(timestamp, status))
            finite_count += 1
            write_event({**event, "expected_second": expected_second, "segment_id": len(segments),
                         "input_available_time_rel_s": available_time,
                         "imu_endpoint_wait_s": available_time - timestamp})
        except (ValueError, np.linalg.LinAlgError) as exc:
            reason = str(exc)
            if isinstance(exc, np.linalg.LinAlgError):
                # A numerical failure cannot silently become a fresh heading
                # initialization. Keep the remainder unavailable for review.
                fatal_reason = reason
                reason = "NUMERICAL_SOLVER_FAILURE:" + reason
            elif not reason.startswith(("IMU_", "WAITING_FOR_VALID_POSITION_AND_INITIAL_YAW")):
                # Unexpected implementation/shape errors must fail visibly and
                # be repaired, not be mislabeled as paper-method performance.
                raise
            if (graph is not None and fatal_reason is None and
                    config.get("gap_policy") == "strict_single_initialization_no_gap_bridge"):
                input_failure = reason
            close_segment()
            pending_reason = reason
            failures.append({"time_rel_s": timestamp, "reason": reason})
            write_state([timestamp, *([float("nan")] * 9), 0, reason])
            write_event({"time_rel_s": timestamp, "expected_second": expected_second, "mode": "UNAVAILABLE", "reason": reason})
        last_node = timestamp
    close_segment()
    return {"expected_nodes": len(inputs.nodes), "actual_rows": len(inputs.nodes),
            "finite_nodes": finite_count, "unavailable_nodes": len(inputs.nodes) - finite_count,
            "segments": segments, "initialization_count": len(segments),
            "A1_yaw_initialization_count": len(segments)*int(uses_a1),
            "failures": failures, "core_counts": aggregate, "numerical_failure": fatal_reason,
            "mandatory_input_failure": input_failure,
            "maximum_imu_endpoint_wait_s": maximum_endpoint_wait_s}


def run_sequence(roots_path, sequence, out_dir, config_path):
    """Main entry; exclusively creates this run's output, never overwrites it."""
    config_path = Path(config_path)
    config = json.loads(config_path.read_text())
    inputs = read_sequence(roots_path, sequence, config)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("STATES.csv", "SOLVER_EVENTS.jsonl", "RUN_MANIFEST.json"):
        if (out_dir / filename).exists():
            raise FileExistsError(f"REFUSE_EXISTING_RUN_ARTIFACT:{filename}")
    started = time.monotonic()
    with (out_dir / "STATES.csv").open("x", newline="") as states, (out_dir / "SOLVER_EVENTS.jsonl").open("x") as events:
        writer = csv.writer(states, lineterminator="\n")
        writer.writerow(STATE_COLUMNS)

        def event(record):
            events.write(json.dumps(record, allow_nan=False) + "\n")
            events.flush()
            states.flush()

        result = run_inputs(inputs, config, writer.writerow, event)
    roots = json.loads(Path(roots_path).read_text())["aliases"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=roots["<CODE_ROOT>"], text=True).strip()
    flags = {key: False for key in ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
             "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
             "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric")}
    manifest = {"method_id": config["method_id"], "sequence": sequence, "data_mode": "real_clean",
                **flags, "old_runtime_input_count": 0, "code_commit": commit,
                "config_hash": sha256(config_path), "config": config, "inputs": inputs.metadata,
                **result, "terminal_status": ("PARTIAL_NUMERICAL_FAILURE" if result["numerical_failure"] else
                    "INPUT_UNSUPPORTED_IMU_GAP" if result["mandatory_input_failure"] else
                    ("COMPLETED_WITH_USABLE_NONCONVERGED_CALLS" if result["core_counts"].get("nonlinear_usable_limit_calls",0) else
                     "COMPLETED") if result["finite_nodes"] else "NO_FINITE_OUTPUT"),
                "solve_mode": "incremental_window_current_node_1Hz_no_historical_output_revision",
                "future_observations_used_for_past_output": result["maximum_imu_endpoint_wait_s"] > 1e-9,
                "future_gnss_factors_used": False,
                "historical_output_revised": False,
                "output_latency_note": "right-endpoint IMU partial intervals require the recorded next-sample wait; offline wall time is not online worst-case latency",
                "output_point": "IMU",
                "attitude_frame": "FRD_to_current_geodetic_NED", "wall_seconds": time.monotonic() - started,
                "timing_scope": "graph_execution_and_output_excluding_input_load_and_hash_checks",
                "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                             "processor": platform.processor(), "logical_cpus": os.cpu_count()},
                "threads_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
                "dependencies": {"numpy": np.__version__, "gtsam": importlib.metadata.version("gtsam"),
                                 "pyceres": importlib.metadata.version("pyceres")},
                "preintegration_backend": config.get("preintegration_backend", "GTSAM_LEGACY"),
                "upstream_build_receipt": (__import__("legsa_gins.paper_rebuild.fgo_comparison.obgins_preintegration",
                    fromlist=["library"]).library().build_receipt if config.get("preintegration_backend") == "OB_GINS_EARTH_PINNED" else None),
                "implementation_source_sha256": {name: sha256(Path(__file__).parent / name)
                    for name in ("oisam.py", "oisam_inputs.py", "ceres_relinearize.py", "obgins_preintegration.py", "obgins_bridge.cc")},
                "states_sha256": sha256(out_dir / "STATES.csv")}
    (out_dir / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return {key: manifest[key] for key in ("method_id", "sequence", "terminal_status", "wall_seconds",
            "expected_nodes", "actual_rows", "finite_nodes", "unavailable_nodes", "core_counts",
            "A1_yaw_initialization_count", "maximum_imu_endpoint_wait_s")} | {"input_provenance": inputs.metadata,
            "evaluation_window_s": inputs.metadata["evaluation_window_s"],
            "manifest_path": str(out_dir / "RUN_MANIFEST.json"), "states_path": str(out_dir / "STATES.csv")}
