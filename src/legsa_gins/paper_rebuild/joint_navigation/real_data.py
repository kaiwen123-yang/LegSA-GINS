"""BY2 source-time events for the joint navigator, without running navigation.

Only existing code/carrier arrays, calibrated IMU increments, receiver P/V and
allowed raw body fields are read. No reference or PVT-derived heading is read.
Feet are measured only at selected *actual* body epochs. An asynchronous GNSS
event carries contact history as context, never as a new simultaneous foot
measurement. Initialization and physical GNSS factors remain backend duties.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml

from ..body_velocity import iter_messages
from ..carrier_phase.support_arcs import FootForceThreshold, SupportArcTracker, SupportPolicy
from ..carrier_phase.temporal import EpochBlock
from ..horizontal_literature.hartley_h0_h2 import (
    FROZEN_CONTACT_DWELL_SECONDS, FROZEN_CONTACT_OFF_THRESHOLDS,
    FROZEN_CONTACT_ON_THRESHOLDS, NATIVE_FOOT_ORDER,
)
from ..horizontal_literature.hartley_h5 import _parse_allowed_record


@dataclass(frozen=True)
class By2InputConfig:
    body_path: Path
    imu_path: Path
    gnss_path: Path
    carrier_plan_path: Path
    calibration_model_path: Path
    imu_noise_profile_path: Path
    start_s: float = 66.0
    end_s: float = 340.0
    key_dt_s: float = 0.1
    base_time_unix_s: int = 1772784000
    family: str = "GPS_GAL_BDS_DUAL"
    # If absent, use the last valid receiver position at/before start. This
    # chooses a coordinate origin only, not an additional navigation prior.
    origin_blh_deg_m: tuple[float, float, float] | None = None


def ecef_from_blh(blh_deg_m) -> np.ndarray:
    lat, lon = np.radians(np.asarray(blh_deg_m, float)[:2])
    height = float(blh_deg_m[2])
    a, e2 = 6378137.0, 6.6943799901413165e-3
    radius = a / math.sqrt(1.0-e2*math.sin(lat)**2)
    return np.array([(radius+height)*math.cos(lat)*math.cos(lon),
                     (radius+height)*math.cos(lat)*math.sin(lon),
                     (radius*(1.0-e2)+height)*math.sin(lat)])


def ecef_from_ned(blh_deg_m) -> np.ndarray:
    lat, lon = np.radians(np.asarray(blh_deg_m, float)[:2])
    sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    return np.array([[-sl*co, -so, -cl*co],
                     [-sl*so, co, -cl*so], [cl, 0., -sl]])


def _gnss_rows(path: Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            tokens = line.split()
            if len(tokens) != 18:
                raise ValueError(f"GNSS18 width at source line {line_number}")
            # Deliberately do not decode tokens 13,14,17: heading is excluded.
            numbers = np.array([float(x) for x in tokens[:13]])
            flags = [int(tokens[k]) for k in (15, 16)]
            if not np.isfinite(numbers[0]) or any(x not in (0, 1) for x in flags):
                raise ValueError(f"GNSS time/validity at source line {line_number}")
            if rows and numbers[0] <= rows[-1]["time_s"]:
                raise ValueError("GNSS source times must be strictly increasing")
            if flags[0] and (not np.isfinite(numbers[1:7]).all() or np.any(numbers[4:7] <= 0)):
                raise ValueError("valid GNSS position requires finite position and positive sigma")
            if flags[1] and (not np.isfinite(numbers[7:13]).all() or np.any(numbers[10:13] <= 0)):
                raise ValueError("valid GNSS velocity requires finite velocity and positive sigma")
            rows.append(dict(time_s=float(numbers[0]), source_row=line_number,
                             blh=numbers[1:4], position_sigma=numbers[4:7],
                             velocity=numbers[7:10], velocity_sigma=numbers[10:13],
                             position_valid=bool(flags[0]), velocity_valid=bool(flags[1])))
    return rows


def _body_rows(config: By2InputConfig) -> tuple[list[dict], dict]:
    policy = SupportPolicy(tuple(FootForceThreshold(name, on, off) for name, on, off in
        zip(NATIVE_FOOT_ORDER, FROZEN_CONTACT_ON_THRESHOLDS, FROZEN_CONTACT_OFF_THRESHOLDS)),
        FROZEN_CONTACT_DWELL_SECONDS, .05)
    tracker = SupportArcTracker(policy, stream_id="BY2_JOINT_INPUT")
    token_names, counters = {}, [0]*4
    rows, previous_ns, previous_legacy = [], None, None
    previous_arcs = None
    grid_index = 0
    for source_row, message in enumerate(iter_messages(config.body_path), 1):
        ns, _, _, forces, foot_values, _ = _parse_allowed_record(message.splitlines(), source_row)
        t = (ns-config.base_time_unix_s*1_000_000_000)*1e-9
        terminal_imu_only = t > config.end_s
        if previous_ns is not None and ns <= previous_ns:
            raise ValueError(f"nonmonotonic BY2 body source row {source_row}; no silent repair")
        sec, nsec = divmod(ns, 1_000_000_000)
        # Reproduce the frozen increment builder's dt when recovering its
        # rates; retain integer-stamp relative time for actual availability.
        legacy_time = float(sec+nsec*1e-9)-config.base_time_unix_s
        legacy_dt = None if previous_legacy is None else legacy_time-previous_legacy
        if terminal_imu_only:
            # One closing IMU sample is allowed to arrive after the final
            # measurement epoch. Do not advance support or expose its feet.
            rows.append(dict(time_s=t, source_row=source_row, stamp_ns=ns,
                             legacy_time_s=legacy_time, legacy_dt_s=legacy_dt,
                             feet=[], support_states=[], active_arcs=(),
                             selected=False, support_changed=False,
                             terminal_imu_only=True))
            break
        support = tracker.update(t, dict(zip(NATIVE_FOOT_ORDER, forces)), available_time_s=t)
        feet, states = [], []
        points = np.asarray(foot_values, float).reshape(4, 3)*[1., -1., -1.]
        for foot_id, state in enumerate(support.feet):
            arc = None
            if state.token is not None:
                if state.token not in token_names:
                    counters[foot_id] += 1
                    token_names[state.token] = f"BY2_force_{foot_id}_{counters[foot_id]:05d}"
                arc = token_names[state.token]
            states.append(dict(foot_id=foot_id, foot_name=state.foot_id,
                               arc_id=arc, eligible=state.eligible, state=state.state,
                               force=state.force_sdk_units, reasons=state.reasons))
            if state.eligible:
                feet.append(dict(foot_id=foot_id, foot_name=state.foot_id, arc_id=arc,
                                 point_body=points[foot_id].copy(), force=float(forces[foot_id]),
                                 support_eligible=True, source_time_s=t, source_row=source_row,
                                 point_covariance=np.eye(3)*.01**2))
        arcs = tuple(state["arc_id"] for state in states)
        changed = previous_arcs is not None and arcs != previous_arcs
        on_grid = t >= config.start_s+grid_index*config.key_dt_s
        selected = t >= config.start_s and (changed or on_grid)
        if on_grid:
            grid_index = int(math.floor((t-config.start_s)/config.key_dt_s))+1
        rows.append(dict(time_s=t, source_row=source_row, stamp_ns=ns,
                         legacy_time_s=legacy_time, legacy_dt_s=legacy_dt,
                         feet=feet, support_states=states, active_arcs=arcs,
                         selected=selected, support_changed=changed))
        previous_ns, previous_legacy, previous_arcs = ns, legacy_time, arcs
    if not rows or rows[0]["time_s"] >= config.start_s:
        raise ValueError("BY2 input needs an observed body prefix before start")
    return rows, dict(source_rows_read=len(rows), body_prefix_start_time_s=rows[0]["time_s"],
                      force_arcs_seen_include_pre_window_prefix=True,
                      force_arcs_by_foot=dict(zip(NATIVE_FOOT_ORDER, counters)),
                      terminal_imu_only_source_time_s=(rows[-1]["time_s"] if rows[-1].get("terminal_imu_only") else None),
                      selected_body_events=sum(row["selected"] for row in rows),
                      support_change_events=sum(row["selected"] and row["support_changed"] for row in rows))


def _imu_rates(config: By2InputConfig, body: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    saved_tokens = np.loadtxt(config.imu_path, ndmin=2, dtype=str)
    saved = saved_tokens.astype(float)
    if saved.shape[1] != 7 or not np.isfinite(saved).all() or np.any(np.diff(saved[:, 0]) <= 0):
        raise ValueError("calibrated IMU needs finite increasing seven-column increments")
    by_printed_time = {token: i for i, token in enumerate(saved_tokens[:, 0])}
    if len(by_printed_time) != len(saved):
        raise ValueError("calibrated IMU has ambiguous microsecond source keys")
    times, rates, identities, source_noise_intervals = [], [], [], []
    for row in body:
        dt = row["legacy_dt_s"]
        if dt is None or not 0 < dt <= .1:
            continue
        # Match the writer's literal serialization. Multiplication by 1e6
        # before round() is not equivalent at .12g half-microsecond ties.
        key = format(float(format(row["legacy_time_s"], ".12g")), ".6f")
        index = by_printed_time.get(key)
        if index is None:
            raise ValueError(f"body/IMU mapping absent at raw row {row['source_row']}")
        times.append(row["time_s"])
        rates.append(np.r_[saved[index, 4:7]/dt, saved[index, 1:4]/dt])
        identities.append((index+1, row["source_row"]))
        source_noise_intervals.append(dt)
    times, rates, identities = np.asarray(times), np.asarray(rates), np.asarray(identities, dtype=int)
    if not len(times) or times[0] > config.start_s:
        raise ValueError("no calibrated rate available at requested start")
    return times, rates, identities, np.asarray(source_noise_intervals)


def _imu_packet(t0, t1, times, rates, identities, source_noise_intervals,
                source_support_starts):
    """Split saved right-endpoint increments over their actual source intervals.

    ``rates`` were recovered using the original writer's (floating timestamp)
    dt. Scale by that dt / physical support duration so each original increment
    is conserved exactly despite the small timestamp-representation difference.
    The returned source timestamp is the right endpoint: callers must delay
    availability until every used endpoint has arrived. No future sample is
    represented as available at an earlier measurement epoch.
    """
    if t1 == t0:
        return np.empty((0, 7)), np.empty((0, 4)), np.empty((0, 2), dtype=int)
    index = int(np.searchsorted(times, t0, side="right"))
    rows, support, source_rows = [], [], []
    cursor = t0
    while cursor < t1:
        if index >= len(times):
            raise ValueError("IMU interval requires an unobserved closing source sample")
        source_start, source_end = source_support_starts[index], times[index]
        duration = source_end-source_start
        if source_start > cursor or duration <= 0:
            raise ValueError("IMU source does not cover interval; missing integration is not filled")
        boundary = min(t1, source_end)
        physical_rate = rates[index]*(source_noise_intervals[index]/duration)
        rows.append(np.r_[boundary-cursor, physical_rate])
        support.append((cursor, boundary, source_end, source_noise_intervals[index]))
        source_rows.append(identities[index])
        cursor = boundary
        index += 1
    return np.asarray(rows), np.asarray(support), np.asarray(source_rows, dtype=int)


def _noise_metadata(config: By2InputConfig, calibration: dict) -> dict:
    profile = yaml.safe_load(Path(config.imu_noise_profile_path).read_text())
    source = profile["continuous_noise_density_asd"]
    scale = float(calibration["s"])
    def value(name):
        return float(source[name]["value"])
    return dict(
        gyro_noise_density=value("gyro_measurement_white_noise_density"),
        accel_noise_density=scale*value("accelerometer_measurement_white_noise_density"),
        gyro_bias_random_walk=value("gyro_bias_random_walk_density"),
        accel_bias_random_walk=scale*value("accelerometer_bias_random_walk_density"),
        accel_bias_prior_sigma=.03, gyro_bias_prior_sigma=.003,
        imu_noise_source=dict(profile_id=profile["profile_id"], path=str(config.imu_noise_profile_path),
            units="continuous_ASD_not_per_sample_sigma",
            calibrated_accel_density_multiplier=scale, gyro_density_multiplier=1.,
            scale_reason="same_linear_scale_as_calibrated_accelerometer_measurement",
            bias_instability_used_as_initial_sigma=False,
            initial_bias_prior="inherited_joint_prototype_engineering_prior_not_Allan_instability"))


def load_by2_events(config: By2InputConfig) -> dict:
    """Return events/metadata/input_summary; never initialize or call a navigator.

    Each event includes the synthetic schema plus explicit source identities,
    validity, per-event P/V covariance and lever arms. Metadata deliberately
    marks backend initialization, GNSS, support and partial-policy integration
    as still required. A zero-copy event is not an authorization to use old
    synthetic assumptions on field observations.
    """
    if not (math.isfinite(config.start_s) and math.isfinite(config.end_s) and
            config.end_s > config.start_s and math.isfinite(config.key_dt_s) and config.key_dt_s > 0):
        raise ValueError("ordered finite input window and positive key period required")
    gnss = _gnss_rows(config.gnss_path)
    calibration = yaml.safe_load(Path(config.calibration_model_path).read_text())
    origin_source = None
    if config.origin_blh_deg_m is None:
        candidates = [r for r in gnss if r["time_s"] <= config.start_s and r["position_valid"]]
        if not candidates:
            raise ValueError("coordinate origin needs an explicit origin or prior valid receiver position")
        origin_source = candidates[-1]
        origin = origin_source["blh"].copy()
    else:
        origin = np.asarray(config.origin_blh_deg_m, float)
    ecef_origin, rotation = ecef_from_blh(origin), ecef_from_ned(origin)
    for row in gnss:
        local_rotation = rotation.T @ ecef_from_ned(row["blh"])
        row["position_ned"] = rotation.T @ (ecef_from_blh(row["blh"])-ecef_origin) if row["position_valid"] else None
        row["velocity_ned"] = local_rotation @ row["velocity"] if row["velocity_valid"] else None
        row["position_covariance"] = local_rotation @ np.diag(row["position_sigma"]**2) @ local_rotation.T if row["position_valid"] else None
        row["velocity_covariance"] = local_rotation @ np.diag(row["velocity_sigma"]**2) @ local_rotation.T if row["velocity_valid"] else None
    body, body_summary = _body_rows(config)
    if len(body) < 1000 or body[999]["time_s"] > config.start_s:
        raise ValueError("the calibrated first-1000 gyro prefix is not available by requested start")
    imu_times, imu_rates, imu_identities, imu_noise_intervals = _imu_rates(config, body)
    imu_support_starts = np.asarray([body[int(i)-2]["time_s"] for i in imu_identities[:, 1]])
    plan = json.loads(Path(config.carrier_plan_path).read_text())
    if plan["base_time"] != config.base_time_unix_s or plan["sequence"] != "BY2":
        raise ValueError("carrier plan sequence or time origin differs from requested BY2")
    carrier_provider_contract = plan.get("provider_contract")
    if carrier_provider_contract is not None:
        # The carrier geometry reuses this receiver position solely as a LOS
        # anchor. The ordinary GNSS factors below remain its only P/V use.
        source = plan["inputs"]["gnss18"]
        if hashlib.sha256(Path(config.gnss_path).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("carrier LOS anchor and navigation GNSS18 sources differ")
    carrier_rows = [r for r in plan["records"] if config.start_s <= r["time_s"] <= config.end_s]
    gnss_rows = [r for r in gnss if config.start_s <= r["time_s"] <= config.end_s]
    body_events = {r["time_s"]: r for r in body if r["selected"]}
    by_gnss, by_carrier = {r["time_s"]: r for r in gnss_rows}, {r["time_s"]: r for r in carrier_rows}
    if len(by_carrier) != len(carrier_rows):
        raise ValueError("carrier source has duplicate epochs")
    event_times = sorted({config.start_s, config.end_s, *body_events, *by_gnss, *by_carrier})
    body_times = np.array([r["time_s"] for r in body])
    events, previous, built_count, unavailable = [], config.start_s, 0, {}
    lever = np.array([.03, .03, -.30])
    first_carrier = None
    for t in event_times:
        imu, intervals, identities = _imu_packet(previous, t, imu_times, imu_rates,
            imu_identities, imu_noise_intervals, imu_support_starts)
        used_source_indexes = np.searchsorted(imu_times, intervals[:, 2])
        available_time = max(t, float(intervals[:, 2].max())) if len(intervals) else t
        gyro_index = int(np.searchsorted(imu_times, t, side="right")-1)
        gyro_source_dt = float(imu_noise_intervals[gyro_index])
        current_body = body_events.get(t)
        latest_body = body[int(np.searchsorted(body_times, t, side="right")-1)]
        event = dict(time_s=t, available_time_s=available_time, imu=imu, imu_interval_sources=intervals,
            imu_original_support_intervals=np.column_stack((imu_support_starts[used_source_indexes], imu_times[used_source_indexes])),
            imu_original_increments=imu_rates[used_source_indexes]*imu_noise_intervals[used_source_indexes, None],
            gnss_angular_rate_body_rad_s=imu_rates[gyro_index, 3:6].copy(),
            gnss_angular_rate_source_time_s=float(imu_times[gyro_index]),
            last_gyro_source_noise_interval_s=gyro_source_dt,
            source_noise_interval_s=gyro_source_dt,
            imu_source_rows=identities, carrier=None, feet=[] if current_body is None else current_body["feet"],
            foot_measurement_available=current_body is not None,
            active_support_arcs=tuple(x for x in latest_body["active_arcs"] if x is not None),
            support_state_source_time_s=latest_body["time_s"], support_states=latest_body["support_states"],
            latest_foot_observations=latest_body["feet"],
            gnss_position=None, gnss_velocity=None, gnss_position_covariance=None,
            gnss_velocity_covariance=None, gnss_position_valid=None, gnss_velocity_valid=None,
            gnss_position_leverarm_body_m=lever.copy(), gnss_velocity_leverarm_body_m=lever.copy(),
            source_kinds=[])
        if current_body is not None:
            event["source_kinds"].append("body_key_or_support_change")
            event["body_source_row"] = current_body["source_row"]
        if t in by_gnss:
            row = by_gnss[t]
            event.update(gnss_position=row["position_ned"], gnss_velocity=row["velocity_ned"],
                gnss_position_covariance=row["position_covariance"], gnss_velocity_covariance=row["velocity_covariance"],
                gnss_position_valid=row["position_valid"], gnss_velocity_valid=row["velocity_valid"],
                gnss_source_time_s=t, gnss_source_row=row["source_row"],
                gnss_measurement_point="GNSS1_ANTENNA", gnss_pvt_heading_consumed=False)
            event["source_kinds"].append("receiver_pv")
        if t in by_carrier:
            row = by_carrier[t]
            entry = row["families"].get(config.family, {})
            event["source_kinds"].append("raw_code_carrier_slot")
            status = entry.get("status", "MODEL_UNAVAILABLE")
            event["carrier_source"] = dict(time_s=t, status=status,
                reason=entry.get("reason", row.get("spp_failure")), gps_key=row["key"],
                family=config.family, model_file=entry.get("file"))
            if carrier_provider_contract is not None:
                event["carrier_source"].update(provider_contract=carrier_provider_contract,
                    geometry_anchor_source_time_s=row["anchor_decision"]["source_time_s"],
                    geometry_anchor_source_row=row["anchor_decision"]["source_row"])
            if status == "BUILT":
                if entry["metadata"].get("baseline_frame") != "ECEF":
                    raise ValueError("expected original ECEF DD design")
                path = Path(config.carrier_plan_path).parent / entry["file"]
                with np.load(path, allow_pickle=False) as saved:
                    y, A, B, Q = (saved[k].copy() for k in ("y", "A", "B", "Q"))
                code_rows = np.flatnonzero(np.all(A == 0., axis=1))
                meta = dict(entry["metadata"], baseline_frame="NED", original_baseline_frame="ECEF",
                    source="saved_raw_dual_receiver_DD", source_file=str(path), source_time_s=t,
                    code_rows=len(code_rows), code_row_indices=code_rows.tolist(), row_units="m",
                    partial_classification="requires_physical_arc_relation_policy_not_fixed_satellite_count")
                event["carrier"] = EpochBlock(t, y, A, B @ rotation, Q, tuple(entry["ambiguity_labels"]), meta)
                built_count += 1
                first_carrier = t if first_carrier is None else first_carrier
            else:
                unavailable[status] = unavailable.get(status, 0)+1
        events.append(event)
        previous = t
    previous_p = [r for r in gnss if r["time_s"] <= config.start_s and r["position_valid"]]
    previous_v = [r for r in gnss if r["time_s"] <= config.start_s and r["velocity_valid"]]
    def initial_source(rows, field, covariance):
        if not rows:
            return None
        r = rows[-1]
        return dict(source_time_s=r["time_s"], source_row=r["source_row"],
                    value=r[field], covariance=r[covariance], leverarm_body_m=lever.copy(),
                    role="source_context_not_an_extra_factor_or_synchronized_measurement")
    metadata = dict(schema="joint_navigation.BY2_real_inputs.v1", data_mode="real_by2_raw",
        carrier_label_mode="physical_sd_arcs",
        sequence="BY2", base_time_unix_s=config.base_time_unix_s,
        window_s=[config.start_s, config.end_s], key_dt_s=config.key_dt_s,
        baseline_body=np.array([0., -.35, 0.]), body_frame="FRD", world_frame="FIXED_LOCAL_NED",
        gravity_n=np.array([0., 0., float(calibration["g_local_mps2"])]),
        origin_blh_deg_m=origin, origin_ecef_m=ecef_origin, R_ecef_from_ned=rotation,
        origin_source_time_s=None if origin_source is None else origin_source["time_s"],
        origin_role="coordinate_definition_not_independent_navigation_observation",
        imu_row_order=("dt", "ax", "ay", "az", "gx", "gy", "gz"),
        imu_interval_source_columns=("segment_start_s", "segment_end_s", "source_time_s", "source_noise_interval_s"),
        imu_source_noise_interval="original_increment_generation_dt; shared_across_split_or_held_segments_of_one_source_sample",
        last_gyro_source_noise_interval="original_dt_of_explicit_GNSS_angular_rate_source; source_noise_interval_s_is_an_alias",
        gnss_angular_rate_sampling="last_arrived_IMU_source_at_or_before_event; available_for_empty_packet; can_differ_from_last_integration_segment_source",
        imu_sampling="saved_current_sample_times_previous_dt_increments_preserved_over_actual_previous_to_current_source_support",
        imu_original_support_columns=("source_interval_start_s", "source_interval_end_s"),
        imu_original_increment_columns=("dv_x_mps", "dv_y_mps", "dv_z_mps", "dtheta_x_rad", "dtheta_y_rad", "dtheta_z_rad"),
        imu_original_increment_rows="full_saved_source_increment_repeated_for_each_split_segment; source_rows_identify_repeats_not_new_samples",
        imu_availability="event_available_time_is_max_measurement_epoch_and_used_IMU_source_right_endpoints",
        imu_terminal_sample="first_body_row_after_requested_end_is_IMU_only; no_beyond_window_foot_or_support_consumption",
        imu_quadrature_change="none_relative_to_saved_increment_support; fractional_split_conserves_each_source_increment",
        source_arrival_scope="only_IMU_right_endpoint_delay_modeled; actual_GNSS_receiver_arrival_latency_unavailable_and_not_modeled",
        measurement_and_availability_times_separate=True,
        imu_calibration=dict(already_applied=True, flu_to_frd=True, install_rpy_deg=[-1., 0., 0.],
            initial_gyro_mean_samples=1000, accel_scale=float(calibration["s"]),
            initial_gyro_mean_prefix_end_time_s=body[999]["time_s"],
            static_scale_development_dataset="BY2; inherited calibration, not refitted here",
            initial_gyro_mean_uncertainty="shared_prefix_dependence_not_independently_calibrated"),
        foot_sigma=.01, foot_correlation_tau_s=.08,
        foot_noise_model="inherited_stationary_body_frame_AR1_working_model_not_field_calibrated",
        support_eligibility_policy="explicit_provider_hysteresis_tokens_no_second_force_threshold",
        force_on=FROZEN_CONTACT_ON_THRESHOLDS, force_off=FROZEN_CONTACT_OFF_THRESHOLDS,
        force_dwell_s=FROZEN_CONTACT_DWELL_SECONDS, force_max_source_gap_s=.05,
        foot_order=NATIVE_FOOT_ORDER, foot_to_imu_translation_body_m=np.zeros(3),
        foot_origin_assumption="SDK_body_origin_equals_IMU_origin_working_assumption",
        physical_no_slip_certified=False, foot_force_units="uncalibrated_SDK_proxy",
        foot_observations="new_measurement_only_at_its_actual_body_event; latest_feet_are_context_only",
        gnss_measurement_point="GNSS1_ANTENNA", gnss_leverarm_body_m=lever,
        gnss_covariance_policy="per_event_source_sigma_rotated_to_fixed_NED",
        source_noise_assumption="raw_DD_and_receiver_PV_share_GNSS; SDK_foot_IMU_dependence_unknown",
        source_cross_covariance_available=False, independent_streams=False,
        heading_source="raw_code_carrier_EpochBlock_only", PVT_heading_consumed=False,
        carrier_provider_contract=carrier_provider_contract,
        SDK_yaw_consumed=False, SDK_velocity_consumed=False, reference_read=False,
        full_phase_relations_policy="variable_physical_arc_relations_not_synthetic_five_relation_rule",
        initialization=dict(status="BACKEND_POLICY_REQUIRED", first_built_carrier_time_s=first_carrier,
            prior_receiver_position=initial_source(previous_p, "position_ned", "position_covariance"),
            prior_receiver_velocity=initial_source(previous_v, "velocity_ned", "velocity_covariance"),
            simultaneous_pv_carrier_assumed=False, future_carrier_backfilled=False),
        required_backend_support=["asynchronous_initialization", "per_event_PV_covariance_and_antenna_model",
                                  "provider_support_eligibility", "physical_partial_arc_relation_policy"],
        **_noise_metadata(config, calibration))
    packets = [event["imu"] for event in events if len(event["imu"])]
    total_dt = sum(float(np.sum(packet[:, 0])) for packet in packets)
    source_intervals = np.concatenate([event["imu_interval_sources"] for event in events if len(event["imu"])])
    summary = dict(**body_summary, event_count=len(events), first_event_time_s=event_times[0],
        last_event_time_s=event_times[-1], gnss_source_epochs=len(gnss_rows),
        valid_position_epochs=sum(r["position_valid"] for r in gnss_rows),
        valid_velocity_epochs=sum(r["velocity_valid"] for r in gnss_rows),
        carrier_source_slots=len(carrier_rows), carrier_built_epochs=built_count,
        carrier_unavailable_by_status=unavailable, first_built_carrier_time_s=first_carrier,
        foot_measurement_count=sum(len(event["feet"]) for event in events),
        imu_rate_samples_available=len(imu_times), imu_segments=sum(len(packet) for packet in packets),
        integrated_duration_s=total_dt, requested_duration_s=config.end_s-config.start_s,
        maximum_imu_packet_duration_error_s=max(abs(float(np.sum(event["imu"][:, 0]))-(event["time_s"]-(events[i-1]["time_s"] if i else config.start_s))) for i, event in enumerate(events)),
        maximum_IMU_source_minus_segment_start_s=float(np.max(source_intervals[:, 2]-source_intervals[:, 0])),
        maximum_event_IMU_availability_delay_s=max(event["available_time_s"]-event["time_s"] for event in events),
        last_event_available_time_s=events[-1]["available_time_s"],
        all_used_IMU_sources_available_by_event_publication=all(not len(event["imu"]) or np.max(event["imu_interval_sources"][:, 2]) <= event["available_time_s"] for event in events),
        foot_measurements_have_exact_event_time=all(foot["source_time_s"] == event["time_s"] for event in events for foot in event["feet"]),
        coordinate_rotation_orthogonality_error=float(np.max(np.abs(rotation.T@rotation-np.eye(3)))),
        navigation_calls=0, evaluator_calls=0, reference_reads=0,
        source_paths={name: str(getattr(config, name)) for name in (
            "body_path", "imu_path", "gnss_path", "carrier_plan_path", "calibration_model_path", "imu_noise_profile_path")})
    return dict(events=events, metadata=metadata, input_summary=summary)
