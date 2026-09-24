"""HX-02 relative-pose evaluator: synthetic trajectories with known gauge offsets and drift rates."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext import hx02_relative_pose_evaluation as ev

BASE = 1_700_000_000.0
WINDOW = (10.0, 70.0)
LAT0, LON0, H0 = 40.0, 116.0, 30.0
SPEED = 1.5
B_MED = 0.356191491865984


def _rz(angle_rad):
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _enu_to_llh(enu):
    origin = ev.geodetic_to_ecef(np.array([LAT0]), np.array([LON0]), np.array([H0]))[0]
    lat0, lon0 = math.radians(LAT0), math.radians(LON0)
    rotation = np.array([[-math.sin(lon0), math.cos(lon0), 0.0],
                         [-math.sin(lat0) * math.cos(lon0), -math.sin(lat0) * math.sin(lon0), math.cos(lat0)],
                         [math.cos(lat0) * math.cos(lon0), math.cos(lat0) * math.sin(lon0), math.sin(lat0)]])
    x, y, z = (origin + np.asarray(enu) @ rotation).T
    lon = np.arctan2(y, x)
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1.0 - ev.WGS84_E2))
    for _ in range(12):
        n = ev.WGS84_A / np.sqrt(1.0 - ev.WGS84_E2 * np.sin(lat) ** 2)
        h = p / np.cos(lat) - n
        lat = np.arctan2(z, p * (1.0 - ev.WGS84_E2 * n / (n + h)))
    n = ev.WGS84_A / np.sqrt(1.0 - ev.WGS84_E2 * np.sin(lat) ** 2)
    return np.degrees(lat), np.degrees(lon), p / np.cos(lat) - n


def _truth(t_rel, turn_rate_deg_s):
    """Reference antenna-midpoint ENU position (origin at the window start) and ENU yaw (rad)."""
    t = np.asarray(t_rel, dtype=float) - WINDOW[0]
    theta0 = math.radians(30.0)
    omega = math.radians(turn_rate_deg_s)
    theta = theta0 + omega * t
    if omega == 0.0:
        east, north = SPEED * t * math.cos(theta0), SPEED * t * math.sin(theta0)
    else:
        radius = SPEED / omega
        east = radius * (np.sin(theta) - math.sin(theta0))
        north = -radius * (np.cos(theta) - math.cos(theta0))
    return np.column_stack((east, north, 0.02 * t)), theta


def _trace_bytes(turn_rate_deg_s):
    t_rel = np.round(np.arange(WINDOW[0] - 2.0, WINDOW[1] + 2.0001, 0.1), 6)
    enu, theta = _truth(t_rel, turn_rate_deg_s)
    lat, lon, height = _enu_to_llh(enu)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", "lat", "lon", "height", "processed_lat", "processed_lon", "processed_height",
                     "yaw", "pitch", "roll"])
    for k, value in enumerate(t_rel):
        yaw_deg = (math.degrees(theta[k]) + 180.0) % 360.0 - 180.0
        writer.writerow([repr(BASE + value), repr(lat[k]), repr(lon[k]), repr(height[k]), "0", "0", "0",
                         repr(yaw_deg), "0", "0"])
    return out.getvalue().encode()


def _nav_bytes(turn_rate_deg_s, *, psi0_deg, translation, yaw_error_enu_rad=None, position_error=None):
    """Hartley NAV at the IMU (FLU body, own world frame) whose antenna-midpoint pose, once the
    gauge (psi0, translation) is applied, equals the reference plus the injected errors."""
    t_rel = np.round(np.arange(WINDOW[0] - 1.0, WINDOW[1] + 1.0001, 0.005), 6)
    enu, theta = _truth(t_rel, turn_rate_deg_s)
    eps = np.zeros(t_rel.size) if yaw_error_enu_rad is None else yaw_error_enu_rad(t_rel)
    error = np.zeros((t_rel.size, 3)) if position_error is None else position_error(t_rel, enu)
    gauge = _rz(math.radians(psi0_deg))
    lever = ev.lever_flu(B_MED)
    out = io.StringIO()
    names = ["timestamp_ns", "row_index", "state_role"] + [f"r{i}{j}" for i in range(3) for j in range(3)] + [
        "vx", "vy", "vz", "px", "py", "pz"]
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(names)
    for k, value in enumerate(t_rel):
        rotation = gauge.T @ _rz(theta[k] + eps[k])
        poi = gauge.T @ (enu[k] + error[k] - np.asarray(translation))
        imu = poi - rotation @ lever
        writer.writerow([int(round((BASE + value) * 1e9)), k, "POSTERIOR", *[repr(v) for v in rotation.ravel()],
                         "0", "0", "0", *[repr(v) for v in imu]])
    return out.getvalue().encode()


def _spec(**extra):
    return {"sequence_id": "SYN", "base_time": BASE, "window": list(WINDOW), "baseline_median_m": B_MED,
            "alignment_branch": "HARTLEY_S", **extra}


def test_lever_is_frozen_frd_transform_in_flu():
    assert ev.lever_flu(B_MED) == pytest.approx([0.03, -(0.03 - 0.5 * B_MED), 0.30])


def test_gauge_offsets_are_recovered_exactly_and_leave_no_error():
    trace = _trace_bytes(2.0)
    nav = _nav_bytes(2.0, psi0_deg=57.0, translation=(5.0, -3.0, 2.0))
    result = ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": nav})
    alignment = result["alignment"]
    assert alignment["yaw_offset_deg"] == pytest.approx(57.0, abs=1e-6)
    assert alignment["translation_enu_m"] == pytest.approx([5.0, -3.0, 2.0], abs=1e-5)
    assert alignment["window_seconds"] == [10.0, 20.0]
    assert alignment["epochs"] == 101
    metrics = result["branches"]["HARTLEY_S"]
    assert metrics["scored_epochs"] == 601
    assert metrics["horizontal_rmse_m"] < 1e-5 and metrics["up_rmse_m"] < 1e-5 and metrics["yaw_rmse_deg"] < 1e-5
    assert metrics["reference_path_length_m"] == pytest.approx(SPEED * 60.0, rel=1e-4)


def test_known_heading_drift_rate_is_recovered():
    rate_deg_per_min = 3.0
    # NED yaw error +r (deg/min) from the window start = ENU yaw perturbation of -r
    injected = lambda t: -np.radians(rate_deg_per_min * (np.asarray(t) - WINDOW[0]) / 60.0)  # noqa: E731
    trace = _trace_bytes(2.0)
    nav = _nav_bytes(2.0, psi0_deg=-120.0, translation=(1.0, 2.0, 0.5), yaw_error_enu_rad=injected)
    result = ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": nav})
    metrics = result["branches"]["HARTLEY_S"]
    assert metrics["heading_drift_deg_per_min"] == pytest.approx(rate_deg_per_min, abs=1e-4)
    # the 10 s alignment absorbs the mean injected yaw over its epochs (0.25 deg), nothing more
    assert result["alignment"]["yaw_offset_deg"] == pytest.approx(-120.0 + 0.25, abs=1e-4)


def test_known_position_drift_rate_follows_the_registered_ols_definition():
    k = 0.02  # 2 m per 100 m of reference path, along the path (scale error)
    trace = _trace_bytes(0.0)
    nav = _nav_bytes(0.0, psi0_deg=10.0, translation=(0.0, 0.0, 0.0),
                     position_error=lambda t, enu: k * (enu - enu[np.argmin(np.abs(np.asarray(t) - WINDOW[0]))]))
    result = ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": nav})
    metrics = result["branches"]["HARTLEY_S"]
    # independent computation: aligned error = k (s - mean_s over the alignment window) on a straight path
    grid = ev.target_grid(WINDOW)
    s = SPEED * (grid - WINDOW[0])
    s_align = s[grid <= WINDOW[0] + 10.0 + 1e-9].mean()
    expected = 100.0 * np.polyfit(s, k * np.abs(s - s_align), 1)[0]
    assert metrics["position_drift_m_per_100m"] == pytest.approx(expected, rel=1e-4)
    assert metrics["position_drift_m_per_100m"] == pytest.approx(100.0 * k, rel=0.05)
    assert metrics["heading_drift_deg_per_min"] == pytest.approx(0.0, abs=1e-6)


def test_one_primary_alignment_is_applied_unchanged_to_the_other_branch():
    trace = _trace_bytes(2.0)
    primary = _nav_bytes(2.0, psi0_deg=40.0, translation=(3.0, 1.0, 0.0))
    other = _nav_bytes(2.0, psi0_deg=45.0, translation=(3.0, 1.0, 0.0))  # a different own-frame gauge
    result = ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": primary, "HARTLEY_LIT": other})
    assert result["alignment"]["branch"] == "HARTLEY_S"
    assert result["alignment"]["yaw_offset_deg"] == pytest.approx(40.0, abs=1e-6)
    lit = result["branches"]["HARTLEY_LIT"]
    assert lit["yaw_rmse_deg"] == pytest.approx(5.0, abs=1e-4)
    assert lit["horizontal_rmse_m"] > 0.1


def test_no_extrapolation_and_alignment_needs_bracketed_epochs():
    trace = _trace_bytes(2.0)
    late = _nav_bytes(2.0, psi0_deg=0.0, translation=(0.0, 0.0, 0.0))
    rows = late.decode().splitlines()
    kept = [rows[0]] + [row for row in rows[1:] if int(row.split(",")[0]) >= int(round((BASE + 30.0) * 1e9))]
    with pytest.raises(ev.RelativePoseError, match="alignment window"):
        ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": ("\n".join(kept) + "\n").encode()})
    shifted = [rows[0]] + [row for row in rows[1:] if int(row.split(",")[0]) >= int(round((BASE + 15.0) * 1e9))]
    result = ev.evaluate_payloads(_spec(), trace, {"HARTLEY_S": ("\n".join(shifted) + "\n").encode()})
    assert result["branches"]["HARTLEY_S"]["unsupported_grid_epochs"] == 50
    assert result["alignment"]["epochs"] == 51


def test_child_entry_opens_reference_once_and_checks_hashes(tmp_path):
    trace = tmp_path / "reference.csv"
    trace.write_bytes(_trace_bytes(2.0))
    nav = tmp_path / "NAV.csv"
    nav.write_bytes(_nav_bytes(2.0, psi0_deg=12.0, translation=(0.0, 0.0, 0.0)))
    spec = _spec(outdir=str(tmp_path / "out"), trace=str(trace),
                 trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
                 branches={"HARTLEY_S": {"nav": str(nav), "nav_sha256": hashlib.sha256(nav.read_bytes()).hexdigest()}})
    result = ev.evaluate(spec)
    assert result["trace_open_count_in_child"] == 1
    written = json.loads((tmp_path / "out" / "RELATIVE_POSE_METRICS.json").read_text())
    assert written["branches"]["HARTLEY_S"]["scored_epochs"] == 601
    assert (tmp_path / "out" / "RELATIVE_POSE_ERROR_SERIES_HARTLEY_S.csv").is_file()
    with pytest.raises(ev.RelativePoseError, match="reference SHA-256"):
        ev.evaluate(dict(spec, outdir=str(tmp_path / "out2"), trace_sha256="0" * 64))
