#!/usr/bin/env python3
"""Read-only BY2 sensor/published-state closure; never run navigation or evaluation.

The original increment reconstruction is an offline right-endpoint diagnostic.
Its source lookahead is reported, not hidden as a causal estimator. SO(3)
preintegration and body-axis sums are separate outputs. Published states at
successive times are separate causal estimates, not one batch posterior.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import gtsam
import numpy as np
import yaml

from legsa_gins.paper_rebuild.joint_navigation import real_data
from legsa_gins.paper_rebuild.joint_navigation.real_data import (
    By2InputConfig, _body_rows, _gnss_rows, _imu_rates,
    ecef_from_blh, ecef_from_ned,
)


def vector(row, name, value, axes=("x", "y", "z")):
    row.update({f"{name}_{axis}": float(v) for axis, v in zip(axes, value)})


def stats(values):
    a = np.asarray(values, float)
    return dict(count=len(a), mean=a.mean(axis=0).tolist(),
                rms=np.sqrt(np.mean(a*a, axis=0)).tolist(),
                std_ddof1=a.std(axis=0, ddof=1).tolist(),
                max_abs=np.max(np.abs(a), axis=0).tolist(),
                norm_rms=float(np.sqrt(np.mean(np.sum(a*a, axis=1)))),
                norm_max=float(np.max(np.linalg.norm(a, axis=1))))


def columns(rows, name, axes=("x", "y", "z")):
    return [[r[f"{name}_{axis}"] for axis in axes] for r in rows]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def causal_zoh_packet(t0, t1, times, rates, identities, source_noise_intervals):
    """Frozen BY04 quadrature, retained after the live adapter is corrected."""
    index = int(np.searchsorted(times, t0, side="right")-1)
    rows, support, source_rows = [], [], []
    cursor = t0
    while cursor < t1:
        boundary = min(t1, times[index+1]) if index+1 < len(times) else t1
        rows.append(np.r_[boundary-cursor, rates[index]])
        support.append((cursor, boundary, times[index], source_noise_intervals[index]))
        source_rows.append(identities[index])
        cursor = boundary
        if index+1 < len(times) and cursor == times[index+1]:
            index += 1
    return np.asarray(rows), np.asarray(support), np.asarray(source_rows, dtype=int)


def write_readout(output, summary):
    def fmt(values):
        return "["+", ".join(f"{v:.6g}" for v in values)+"]"
    w = summary["whole_window_preintegration"]
    rotation = np.array([w["relative_rotation_log_rad_"+a] for a in "xyz"])
    dv = np.array([w["preintegrated_dv_difference_initial_body_mps_"+a] for a in "xyz"])
    d = summary["interval_statistics"]
    lines = [
        "# BY shared physical closure — completed without new navigation",
        "",
        "Inputs: existing BY04 U0/U1 causal published states and their original calibrated IMU/body timestamps/GNSS P/V. No reference, testset, navigation, evaluation, parameter fit, or parameter change.",
        "",
        f"Window {w['time_start_s']}–{w['time_end_s']} s; 51 P/V epochs, 50 intervals; 30 published P/V-epoch states per arm and 29 subsequent 0.2 s closures per arm.",
        "",
        "## Measured scales",
        "",
        "| Quantity | Actual result |",
        "|---|---|",
        f"| P/V internal dp/dt − v-average, N/E/D RMS | {fmt(d['pv_dpdt_minus_vavg_mps']['rms'])} m/s |",
        f"| P/V internal closure mean | {fmt(d['pv_dpdt_minus_vavg_mps']['mean'])} m/s |",
        f"| 0.2 s original-vs-ZOH SO(3) rotation difference, norm RMS/max | {np.degrees(d['relative_rotation_log_rad']['norm_rms']):.6g} / {np.degrees(d['relative_rotation_log_rad']['norm_max']):.6g} deg |",
        f"| 0.2 s initial-body-frame preintegrated delta-v difference, norm RMS/max | {d['preintegrated_dv_difference_initial_body_mps']['norm_rms']:.6g} / {d['preintegrated_dv_difference_initial_body_mps']['norm_max']:.6g} m/s |",
        f"| Full 10 s SO(3) relative rotation log | {fmt(np.degrees(rotation))} deg; norm {np.degrees(np.linalg.norm(rotation)):.6g} deg |",
        f"| Full 10 s delta-v difference, common initial body frame | {fmt(dv)} m/s; norm {np.linalg.norm(dv):.6g} m/s |",
        "",
        "The full-window delta-v is recomputed with accumulated attitude. It is not the sum of 0.2 s vectors in changing start frames, and it is not an observed navigation velocity error. The rotation is Log(deltaR_original^-1 deltaR_ZOH), not a sum of gyro components.",
        "",
        "## Source of the quadrature difference",
        "",
        "The calibrated source stores d_k = r_k * previous_dt_k. BY04 divides by that previous interval, then holds r_k through next_dt_k. Thus each interior source is reweighted by next_dt_k − previous_dt_k. On nonuniform body timestamps this is more than the endpoint effect of a constant sampling delay.",
        "",
    ]
    weights = summary["quadrature_source_weighting"]
    lines += [
        f"Actual source dt percentiles [min, 1%, 50%, 99%, max]: {fmt(weights['source_interval_ms_percentiles'])} ms.",
        f"Full-window body-axis gyro-sum difference: {fmt(np.degrees(weights['all']['gyro_difference_rad']))} deg. Interior contribution: {fmt(np.degrees(weights['interior']['gyro_difference_rad']))} deg; boundary contribution: {fmt(np.degrees(weights['boundary']['gyro_difference_rad']))} deg. These are algebraic body-axis sums only; the separate SO(3) result is above.",
        f"Legacy floating timestamp dt versus integer timestamp dt differs by at most {summary['source_contract']['legacy_vs_integer_interval_max_abs_s']*1e6:.6g} microseconds; it does not explain the approximately 3 degree interior X-axis change.",
        f"Offline original-interval reconstruction needs at most {summary['source_contract']['original_lookahead_max_s']*1000:.6g} ms of endpoint availability beyond a P/V epoch; at 106 s it needs {w['original_lookahead_s']*1000:.6g} ms. This reconstruction is not presented as an immediate causal output.",
        "",
        "## Existing conditional states and local closure",
        "",
        "| Arm | Final ba, body xyz (m/s²) | Final R-transpose g (m/s²) | Final ba − R-transpose g (m/s²) | Lever velocity norm RMS/max (m/s) | Original / ZOH antenna delta-v residual norm RMS (m/s) |",
        "|---|---|---|---|---|---|",
    ]
    for arm in ("U0", "U1"):
        st = summary["state_statistics"][arm]
        last = st["last"]
        closure = summary["online_closure_statistics"][arm]
        vals = [fmt([last[name+"_"+a] for a in "xyz"]) for name in ("ba_mps2", "Rt_g_mps2", "ba_minus_Rt_g_mps2")]
        lines.append(f"| {arm} | {' | '.join(vals)} | {st['lever_velocity_mps']['norm_rms']:.6g} / {st['lever_velocity_mps']['norm_max']:.6g} | {closure['original_antenna_dv_residual_mps']['norm_rms']:.6g} / {closure['causal_zoh_antenna_dv_residual_mps']['norm_rms']:.6g} |")
    lines += [
        "",
        "Both arms retain almost the same effective body force ba − R-transpose g. Their large ba estimates accompany gravity projection changes, so the values cannot be identified as physical accelerometer bias from these outputs alone. Successive published bias estimates also re-estimate history; their difference is not an independently measured random-walk increment.",
        "",
        f"The {np.degrees(np.linalg.norm(rotation)):.4g} degree integration-induced rotation discrepancy corresponds to a gravity-projection scale of about {np.linalg.norm(summary['gravity_n_mps2'])*np.sin(np.linalg.norm(rotation)):.4g} m/s². It is large enough to affect the shared tilt/bias compensation. This establishes priority for fixing increment semantics, not proof that it explains the full yaw/navigation error.",
        "",
        "The short 0.2 s antenna delta-v residual does not decrease when the same already-estimated start state is reused with original increments. That does not refute the accumulated attitude effect: these states were solved under ZOH, and this diagnostic does not re-estimate them. It also leaves shared dynamic residuals unresolved. The lever-velocity increment has about 0.1604 m/s norm RMS, so antenna velocity semantics/filtering remain physically material.",
        "",
        "These closures use each interval-start causal published R/b, propagate R through that interval, add gravity and the two endpoint lever velocities, then compare GNSS delta-v. They are not residuals evaluated at one unified batch posterior and are not calibrated likelihood tests. Small reported local yaw sigma is conditional on the current model; it does not cover the quadrature change or unresolved nonlinear modes.",
        "",
        "## Relation to existing calibration",
        "",
        f"Registered static accelerometer ASD is {summary['registered_static_accel_ASD_mps2_sqrtHz']:.8g} m/s²/sqrt(Hz); its acceleration-white-only 0.2 s delta-v sigma is {summary['static_white_accel_only_delta_v_sigma_at_0p2s_mps']:.8g} m/s. GNSS velocity noise, attitude error, lever dynamics, and shared temporal dependence also enter the present closure, so this scalar is not a complete closure sigma.",
        f"Existing CLEAN5 dynamic residual q_NED = {fmt(summary['prior_dynamic_calibration']['q_NED_m2ps3'])} m²/s³ was obtained with {summary['prior_dynamic_calibration']['rotation']}. Its c is explicitly a GNSS velocity diagnostic. The approximately 0.12–0.19 m/s per-axis residual scale here is comparable to the earlier 0.2 s dynamic closure scale, but neither q nor that residual can be relabeled as independent body white noise. No value is fitted or applied here.",
        "",
        "Next physical correction: preserve original dtheta/dv and their [t_previous,t_source] support. Consume them only after t_source is available; observations inside a source interval keep their original measurement epochs and are processed with an explicitly delayed availability time. Then compare matched U0/U1 under that single input correction before changing dynamic noise or foot models.",
        "",
        "Tables: gnss_interval_closure.csv; online_state_terms.csv; online_antenna_dv_closure.csv. summary.json records definitions, source hashes, original endpoint lookahead, and all statistics.",
    ]
    correction_file = output/"INPUT_CORRECTION_CONSERVATION.json"
    if correction_file.exists():
        correction = json.loads(correction_file.read_text())
        lines += ["", "## Implemented input correction", "",
                  "The adapter now preserves saved increments over actual source support and carries their right-endpoint availability separately from measurement time. The original GNSS/body measurement epochs and support selection are unchanged.",
                  f"The subsequent real-input-only assembly kept {correction['event_count']} events and {correction['integrated_duration_s']} s integration. Maximum algebraic increment conservation error: {correction['max_abs_increment_conservation_error']:.6g}; full-source fractional allocation error: {correction['maximum_full_source_fraction_error']:.6g}. No navigation was run by this check.",
                  f"Across all asynchronous events, the maximum IMU availability delay is {correction['max_availability_delay_s']*1000:.6g} ms (the earlier 5.309 ms figure covers only P/V epochs). Final measurement epoch {correction['final_measurement_time_s']} s is available at {correction['final_available_time_s']} s. No beyond-window foot observation is consumed. Actual GNSS receiver arrival latency remains unmodeled.",
                  "The nonuniform-interval and endpoint-availability unit check is tests/paper_rebuild/test_joint_real_imu_support.py. INPUT_CORRECTION_CONSERVATION.json contains the separate actual-input conservation result."]
    (output/"READOUT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--u0-run", type=Path, required=True)
    parser.add_argument("--u1-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = {"U0": args.u0_run, "U1": args.u1_run}
    statuses = {arm: json.loads((p/"run_status.json").read_text()) for arm, p in runs.items()}
    if statuses["U0"]["input_config"] != statuses["U1"]["input_config"]:
        raise ValueError("closure requires the same recorded physical input configuration")
    metadata = json.loads((args.u1_run/"sensor_metadata.json").read_text())
    config_data = statuses["U1"]["input_config"]
    config = By2InputConfig(**{k: Path(v) if k.endswith("_path") else v
                              for k, v in config_data.items()})
    nav = {arm: [json.loads(line) for line in (p/"navigation.jsonl").open()]
           for arm, p in runs.items()}
    states = {arm: {r["time_s"]: r for r in rows if r["rpy_rad"][0] is not None}
              for arm, rows in nav.items()}
    event_times = np.asarray([r["time_s"] for r in nav["U1"]])
    gravity = np.asarray(metadata["gravity_n"], float)
    lever = np.asarray(metadata["gnss_leverarm_body_m"], float)
    origin = np.asarray(metadata["origin_ecef_m"], float)
    world_rotation = np.asarray(metadata["R_ecef_from_ned"], float)
    gnss = [r for r in _gnss_rows(config.gnss_path)
            if config.start_s <= r["time_s"] <= config.end_s
            and r["position_valid"] and r["velocity_valid"]]
    for r in gnss:
        r["p"] = world_rotation.T @ (ecef_from_blh(r["blh"])-origin)
        r["v"] = world_rotation.T @ ecef_from_ned(r["blh"]) @ r["velocity"]

    # Read an extra 50 ms solely to close the last offline right-end interval.
    # Only its actual necessary closing sample enters the diagnostic.
    body, _ = _body_rows(replace(config, end_s=config.end_s+.05))
    times, rates, identities, legacy_dt = _imu_rates(config, body)
    starts = np.asarray([body[int(i)-2]["time_s"] for i in identities[:, 1]])
    original_dt = times-starts
    increments = rates*legacy_dt[:, None]
    original_rates = increments/original_dt[:, None]

    params = gtsam.PreintegrationParams(gravity)
    params.setAccelerometerCovariance(np.eye(3)*metadata["accel_noise_density"]**2)
    params.setGyroscopeCovariance(np.eye(3)*metadata["gyro_noise_density"]**2)
    params.setIntegrationCovariance(np.eye(3)*1e-10)

    def integrate(packet, bias=None):
        b = np.zeros(6) if bias is None else np.asarray(bias, float)
        pim = gtsam.PreintegratedImuMeasurements(
            params, gtsam.imuBias.ConstantBias(b[:3], b[3:]))
        for sample in packet:
            pim.integrateMeasurement(sample[1:4], sample[4:7], float(sample[0]))
        return pim

    def packet(t0, t1, mode):
        # Preserve every actual estimator event split for both quadratures.
        cuts = np.r_[t0, event_times[(event_times > t0) & (event_times < t1)], t1]
        pieces, required_source_time = [], t0
        for a, b in zip(cuts[:-1], cuts[1:]):
            if mode == "causal_zoh":
                part, sources, _ = causal_zoh_packet(a, b, times, rates, identities, legacy_dt)
                pieces.extend(part)
                required_source_time = max(required_source_time, sources[:, 2].max())
            else:
                indexes = np.flatnonzero((times > a) & (starts < b))
                for index in indexes:
                    overlap = min(times[index], b)-max(starts[index], a)
                    pieces.append(np.r_[overlap, original_rates[index]])
                    required_source_time = max(required_source_time, times[index])
        result = np.asarray(pieces)
        if not np.isclose(result[:, 0].sum(), t1-t0, rtol=0, atol=1e-11):
            raise ValueError("source intervals do not cover the diagnostic interval")
        return result, max(0., required_source_time-t1)

    def gyro(t):
        index = int(np.searchsorted(times, t, side="right")-1)
        return rates[index, 3:], times[index]

    def compare_packets(t0, t1):
        old, lookahead = packet(t0, t1, "original")
        zoh, _ = packet(t0, t1, "causal_zoh")
        p_old, p_zoh = integrate(old), integrate(zoh)
        out = dict(time_start_s=t0, time_end_s=t1, dt_s=t1-t0,
                   original_lookahead_s=lookahead,
                   original_segment_count=len(old), causal_segment_count=len(zoh))
        for name, data in [("original", old), ("causal_zoh", zoh)]:
            vector(out, name+"_body_axis_accel_sum_mps", np.sum(data[:, :1]*data[:, 1:4], axis=0))
            vector(out, name+"_body_axis_gyro_sum_rad", np.sum(data[:, :1]*data[:, 4:7], axis=0))
        vector(out, "body_axis_accel_sum_difference_mps", np.sum(zoh[:, :1]*zoh[:, 1:4], axis=0)-np.sum(old[:, :1]*old[:, 1:4], axis=0))
        vector(out, "body_axis_gyro_sum_difference_rad", np.sum(zoh[:, :1]*zoh[:, 4:7], axis=0)-np.sum(old[:, :1]*old[:, 4:7], axis=0))
        vector(out, "original_preintegrated_dv_initial_body_mps", p_old.deltaVij())
        vector(out, "causal_preintegrated_dv_initial_body_mps", p_zoh.deltaVij())
        vector(out, "preintegrated_dv_difference_initial_body_mps", p_zoh.deltaVij()-p_old.deltaVij())
        vector(out, "relative_rotation_log_rad", gtsam.Rot3.Logmap(p_old.deltaRij().between(p_zoh.deltaRij())))
        return out, {"original": old, "causal_zoh": zoh}

    intervals, state_rows, arm_rows = [], [], []
    for left, right in zip(gnss[:-1], gnss[1:]):
        t0, t1 = left["time_s"], right["time_s"]
        row, packets = compare_packets(t0, t1)
        dt = t1-t0
        vector(row, "pv_dpdt_minus_vavg_mps", (right["p"]-left["p"])/dt-(right["v"]+left["v"])/2, ("n", "e", "d"))
        vector(row, "gnss_velocity_increment_mps", right["v"]-left["v"], ("n", "e", "d"))
        intervals.append(row)
        for arm, by_time in states.items():
            if t0 not in by_time:
                continue
            state = by_time[t0]
            rotation = gtsam.Rot3.RzRyRx(*state["rpy_rad"])
            bias = np.asarray(state["bias"])
            lever_start = rotation.matrix() @ np.cross(gyro(t0)[0]-bias[3:], lever)
            out = dict(arm=arm, time_start_s=t0, time_end_s=t1, dt_s=dt)
            for name, data in packets.items():
                pim = integrate(data, bias)
                end_rotation = rotation.compose(pim.deltaRij()).matrix()
                lever_end = end_rotation @ np.cross(gyro(t1)[0]-bias[3:], lever)
                body_dv = rotation.matrix() @ pim.deltaVij()+gravity*dt
                predicted_dv = body_dv+lever_end-lever_start
                residual = right["v"]-left["v"]-predicted_dv
                vector(out, name+"_predicted_antenna_dv_mps", predicted_dv, ("n", "e", "d"))
                vector(out, name+"_antenna_dv_residual_mps", residual, ("n", "e", "d"))
                vector(out, name+"_lever_dv_mps", lever_end-lever_start, ("n", "e", "d"))
            arm_rows.append(out)

    for r in gnss:
        t = r["time_s"]
        for arm, by_time in states.items():
            if t not in by_time:
                continue
            state = by_time[t]
            rotation = gtsam.Rot3.RzRyRx(*state["rpy_rad"]).matrix()
            bias = np.asarray(state["bias"])
            gravity_body = rotation.T @ gravity
            omega, source_time = gyro(t)
            out = dict(arm=arm, time_s=t, gyro_source_time_s=source_time,
                       yaw_local_conditional_sigma_rad=state["yaw_conditional_std_rad"],
                       gnss_innovation_nis=state["gnss_innovation_nis"])
            vector(out, "rpy_rad", state["rpy_rad"], ("roll", "pitch", "yaw"))
            vector(out, "ba_mps2", bias[:3])
            vector(out, "bg_radps", bias[3:])
            vector(out, "Rt_g_mps2", gravity_body)
            vector(out, "ba_minus_Rt_g_mps2", bias[:3]-gravity_body)
            vector(out, "lever_velocity_mps", rotation @ np.cross(omega-bias[3:], lever), ("n", "e", "d"))
            vector(out, "published_antenna_v_minus_gnss_v_mps", np.asarray(state["v"])+rotation @ np.cross(omega-bias[3:], lever)-r["v"], ("n", "e", "d"))
            vector(out, "published_antenna_p_minus_gnss_p_m", np.asarray(state["p"])+rotation @ lever-r["p"], ("n", "e", "d"))
            state_rows.append(out)

    whole, _ = compare_packets(config.start_s, config.end_s)
    next_times = np.r_[times[1:], np.inf]
    original_weights = np.maximum(0., np.minimum(times, config.end_s)-np.maximum(starts, config.start_s))*legacy_dt/original_dt
    zoh_weights = np.maximum(0., np.minimum(next_times, config.end_s)-np.maximum(times, config.start_s))
    active = (original_weights > 0) | (zoh_weights > 0)
    interior = active & (starts >= config.start_s) & (next_times <= config.end_s)
    weighting = dict(source_interval_ms_percentiles=np.percentile(original_dt[active]*1000, [0, 1, 50, 99, 100]).tolist(),
                     percentile_levels=[0, 1, 50, 99, 100])
    for name, mask in [("all", active), ("interior", interior), ("boundary", active & ~interior)]:
        diff = (((zoh_weights-original_weights)[:, None])*rates)[mask].sum(axis=0)
        weighting[name] = dict(source_count=int(mask.sum()), accel_difference_mps=diff[:3].tolist(), gyro_difference_rad=diff[3:].tolist())
    calibration = yaml.safe_load(config.calibration_model_path.read_text())
    selected_imu = (times > config.start_s) & (starts < config.end_s)
    summary = dict(
        schema="joint_navigation.BY2_shared_sensor_closure.v1",
        status="COMPLETED_NO_NEW_NAVIGATION",
        navigation_calls=0, evaluation_calls=0, reference_reads=0, testset_reads=0,
        config=config_data, runs={arm: str(p) for arm, p in runs.items()},
        source_sha256={str(p/name): sha256(p/name) for p in runs.values()
                       for name in ("run_status.json", "navigation.jsonl", "sensor_metadata.json")},
        diagnostic_source_sha256={str(Path(__file__).resolve()): sha256(__file__),
                                  real_data.__file__: sha256(real_data.__file__)},
        source_contract=dict(
            PV="receiver antenna P and velocity rotated into the recorded fixed local NED",
            original="saved calibrated increments assigned to their original previous-to-current body interval; fractional endpoint overlap preserves whole increments",
            causal_zoh="same adapter rate reconstruction and past-only hold; actual event splits preserved",
            original_lookahead_max_s=max(r["original_lookahead_s"] for r in intervals),
            body_requested_read_end_s=config.end_s+.05,
            body_last_read_source_time_s=body[-1]["time_s"],
            comparison_ZOH="frozen_BY04_previous_sample_formula_in_this_script_not_live_adapter_packet",
            legacy_vs_integer_interval_max_abs_s=float(np.max(np.abs(legacy_dt[selected_imu]-original_dt[selected_imu]))),
            preintegration="kinematic mean calculation only; no new graph, optimization, covariance fit, or navigation run",
            body_axis_sums="algebraic sums of vectors expressed in changing body axes; not navigation-frame cumulative errors",
            rotation_difference="Log(deltaR_original^-1 deltaR_causal); accumulated SO(3), not summed gyro components",
            velocity_difference="deltaV_causal-deltaV_original in their common interval-initial body frame; whole-window result recomputed, not sum of 0.2s outputs",
            online_closure="0.2s antenna delta-v predicted from each interval-start causal published R and constant bias; endpoint rotation propagated through IMU; not a unified posterior ImuFactor residual",
            cross_covariance="unknown temporal/PV/IMU/shared-GNSS dependence; no NIS or white-noise identification from these closures"),
        counts=dict(gnss_epochs=len(gnss), intervals=len(intervals),
                    online_state_rows=len(state_rows), online_closure_rows=len(arm_rows)),
        interval_statistics=dict(
            pv_dpdt_minus_vavg_mps=stats(columns(intervals, "pv_dpdt_minus_vavg_mps", ("n", "e", "d"))),
            body_axis_accel_sum_difference_mps=stats(columns(intervals, "body_axis_accel_sum_difference_mps")),
            body_axis_gyro_sum_difference_rad=stats(columns(intervals, "body_axis_gyro_sum_difference_rad")),
            preintegrated_dv_difference_initial_body_mps=stats(columns(intervals, "preintegrated_dv_difference_initial_body_mps")),
            relative_rotation_log_rad=stats(columns(intervals, "relative_rotation_log_rad"))),
        whole_window_preintegration=whole, quadrature_source_weighting=weighting,
        gravity_n_mps2=gravity.tolist(),
        state_statistics={}, online_closure_statistics={},
        prior_dynamic_calibration=dict(
            path=str(config.calibration_model_path), q_NED_m2ps3=calibration["q"],
            c_NED_m2ps2=calibration["c"], c_role=calibration["c_role"],
            rotation=calibration["rotation"],
            lag_200ms=[r for r in calibration["lag_variances"] if r["lag_ms"] == 200],
            scope="historical residual scale under a different recorded attitude source; not transferable body white noise, not applied here"),
        registered_static_accel_ASD_mps2_sqrtHz=metadata["accel_noise_density"],
        static_white_accel_only_delta_v_sigma_at_0p2s_mps=metadata["accel_noise_density"]*np.sqrt(.2),
    )
    for arm in runs:
        selected = [r for r in state_rows if r["arm"] == arm]
        summary["state_statistics"][arm] = {name: stats(columns(selected, name, axes))
            for name, axes in [("ba_mps2", ("x", "y", "z")), ("Rt_g_mps2", ("x", "y", "z")),
                               ("ba_minus_Rt_g_mps2", ("x", "y", "z")),
                               ("lever_velocity_mps", ("n", "e", "d")),
                               ("published_antenna_v_minus_gnss_v_mps", ("n", "e", "d")),
                               ("published_antenna_p_minus_gnss_p_m", ("n", "e", "d"))]}
        summary["state_statistics"][arm]["first"] = selected[0]
        summary["state_statistics"][arm]["last"] = selected[-1]
        selected = [r for r in arm_rows if r["arm"] == arm]
        summary["online_closure_statistics"][arm] = {name: stats(columns(selected, name, ("n", "e", "d")))
            for name in ("original_antenna_dv_residual_mps", "causal_zoh_antenna_dv_residual_mps",
                         "original_lever_dv_mps", "causal_zoh_lever_dv_mps")}
    matched = {arm: {r["time_s"]: r for r in state_rows if r["arm"] == arm} for arm in runs}
    common = sorted(set(matched["U0"]) & set(matched["U1"]))
    summary["U1_minus_U0_paired_state_statistics"] = {
        name: stats([[matched["U1"][t][f"{name}_{axis}"]-matched["U0"][t][f"{name}_{axis}"]
                      for axis in axes] for t in common])
        for name, axes in [("ba_mps2", ("x", "y", "z")), ("Rt_g_mps2", ("x", "y", "z")),
                           ("ba_minus_Rt_g_mps2", ("x", "y", "z")),
                           ("lever_velocity_mps", ("n", "e", "d"))]}
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output/"gnss_interval_closure.csv", intervals)
    write_csv(args.output/"online_state_terms.csv", state_rows)
    write_csv(args.output/"online_antenna_dv_closure.csv", arm_rows)
    (args.output/"summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
    write_readout(args.output, summary)
    print(json.dumps(dict(output=str(args.output), counts=summary["counts"],
                         interval_statistics=summary["interval_statistics"],
                         online_closure_statistics=summary["online_closure_statistics"],
                         whole_window_preintegration=whole), indent=2))


if __name__ == "__main__":
    main()
