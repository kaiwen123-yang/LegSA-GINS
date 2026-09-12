"""Fail-closed effect and source-isolation validation for provider packages."""

from __future__ import annotations

import json
import math
from typing import Any, Iterable, Mapping

import numpy as np

from .matrix_spec import WINDOW_END_S, WINDOW_START_S, load_type_registry
from .provider_generator import (
    COMPONENT_RNG_NAMES, D57_ORIGINAL_ROW_ID, ProviderBundle, ProviderTable, SOLVER_SOURCE_IDS,
    _bool, _finite, apply_degradation, compose_solver_gnss18,
)
from .seed_anchor import place_interval, place_repeated_d07, stable_component_rngs
from ..evaluator import _geodetic_delta_ned


class EffectValidationError(ValueError):
    pass


NO_ACTIVE_PATH_TYPES = frozenset({"D29", "D40", "D55", "D56"})


def expected_changed_tables(type_id: str, seed_index: str | None = None) -> frozenset[str]:
    n = int(type_id[1:]) if type_id != "CLEAN" else 0
    if n == 0: return frozenset()
    if n <= 4 or n == 7 or 13 <= n <= 28: return frozenset({"gnss_position"})
    if n == 5: return frozenset({"gnss_position", "receiver_velocity"})
    if n == 6: return frozenset({"gnss_position", "receiver_velocity", "dual_yaw"})
    if 8 <= n <= 12: return frozenset({"gnss_position", "receiver_velocity", "dual_yaw"})
    if n == 29: return frozenset({"source_quality_metadata"})
    if 30 <= n <= 40: return frozenset({"dual_yaw"})
    if n == 41:
        # GNSS1/GNSS2 antenna noise belongs to the baseline/yaw generation chain;
        # the solver position provider is deliberately isolated.
        return frozenset({"dual_yaw"})
    if 42 <= n <= 45: return frozenset({"receiver_velocity"})
    if 46 <= n <= 50: return frozenset({"raw_doppler"})
    if n in (51, 52): return frozenset({"go2_rp"})
    if n in (53, 54): return frozenset({"go2_hv"})
    if n in (55, 56): return frozenset({"source_quality_metadata"})
    if n == 57: return frozenset(SOLVER_SOURCE_IDS)
    if n == 58: return frozenset({"gnss_position", "dual_yaw"})
    if n == 59: return frozenset({"gnss_position", "raw_doppler"})
    if n == 60: return frozenset({"gnss_position", "receiver_velocity", "dual_yaw", "raw_doppler"})
    raise EffectValidationError(f"unknown type: {type_id}")


def _strict_monotonic(table: ProviderTable) -> bool:
    times = [_finite(row["time"]) for row in table.rows]
    return all(right > left for left, right in zip(times, times[1:]))


def _finite_table(table: ProviderTable) -> bool:
    numeric_names = {
        "time", "lat_deg", "lon_deg", "height_m", "std_n_m", "std_e_m", "std_d_m",
        "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "yaw_deg", "yaw_std_deg",
        "baseline_n_m", "baseline_e_m", "baseline_d_m", "baseline_length_m", "rel_acc_m",
        "roll_rad", "pitch_rad", "std_roll_rad", "std_pitch_rad",
    }
    try:
        for row in table.rows:
            for field in numeric_names.intersection(row):
                _finite(row[field])
    except (ValueError, TypeError, EffectValidationError):
        return False
    return True


def local_position_deltas(base: ProviderTable, generated: ProviderTable) -> np.ndarray:
    if len(base.rows) != len(generated.rows):
        raise EffectValidationError("position row count changed")
    values = []
    for left, right in zip(base.rows, generated.rows):
        values.append(_geodetic_delta_ned(
            _finite(right["lat_deg"]), _finite(right["lon_deg"]), _finite(right["height_m"]),
            _finite(left["lat_deg"]), _finite(left["lon_deg"]), _finite(left["height_m"]),
        ))
    return np.asarray(values, dtype=float)


def _valid_vector(table: ProviderTable) -> np.ndarray:
    return np.asarray([_bool(row.get("valid", row.get("update_flag", 1))) for row in table.rows])


def _numeric_matrix(table: ProviderTable, fields: tuple[str, ...]) -> np.ndarray:
    return np.asarray([[_finite(row[field]) for field in fields] for row in table.rows], dtype=float)


def _changed_rows(left: np.ndarray, right: np.ndarray, tolerance: float = 1e-8) -> np.ndarray:
    return np.flatnonzero(np.any(np.abs(right - left) > tolerance, axis=1) if left.ndim == 2 else np.abs(right - left) > tolerance)


def _type_specific_checks(base: ProviderBundle, generated: ProviderBundle,
                          case: Mapping[str, Any],
                          components: Iterable[Mapping[str, Any]]) -> list[tuple[str, bool, str]]:
    """Independently recompute the effect; never trust the handler ledger."""

    type_id = str(case["degradation_type_id"])
    if type_id == "CLEAN":
        return [("clean_reference_hash_identity", base.hashes() == generated.hashes(), "all tables byte-identical")]
    n = int(type_id[1:]); checks: list[tuple[str, bool, str]] = []
    replay_rngs = stable_component_rngs(int(case["seed_value"]), COMPONENT_RNG_NAMES)
    component_rows = tuple(components)
    component_by_operation = {
        str(row.get("component")): {**dict(row.get("details") or {}), **row}
        for row in component_rows
    }
    pos0, pos1 = base.tables["gnss_position"], generated.tables["gnss_position"]
    vel0, vel1 = base.tables["receiver_velocity"], generated.tables["receiver_velocity"]
    yaw0, yaw1 = base.tables["dual_yaw"], generated.tables["dual_yaw"]
    raw0, raw1 = base.tables["raw_doppler"], generated.tables["raw_doppler"]
    rp0, rp1 = base.tables["go2_rp"], generated.tables["go2_rp"]
    hv0, hv1 = base.tables["go2_hv"], generated.tables["go2_hv"]
    if 1 <= n <= 7 or n in (30, 31, 42, 46):
        target_pairs = ([(pos0, pos1)] if n <= 4 or n == 7 else
                        [(pos0, pos1), (vel0, vel1)] if n == 5 else
                        [(pos0, pos1), (vel0, vel1), (yaw0, yaw1)] if n == 6 else
                        [(yaw0, yaw1)] if n in (30, 31) else
                        [(vel0, vel1)] if n == 42 else [(raw0, raw1)])
        duration = {1: 3, 2: 5, 3: 10, 4: 20, 5: 10, 6: 20, 30: 5, 31: 20, 42: 20, 46: 20}.get(n)
        intervals = place_repeated_d07(float(case["anchor_time_s"])) if n == 7 else (
            place_interval(float(case["anchor_time_s"]), float(duration)),)
        for ordinal, (before, after) in enumerate(target_pairs):
            times = _numeric_matrix(before, ("time",))[:, 0]
            expected = _valid_vector(before) & np.logical_or.reduce(
                [(times >= start) & (times < end) for start, end in intervals])
            observed = _valid_vector(before) & ~_valid_vector(after)
            checks.append((f"outage_{ordinal}_exact_half_open_mask", np.array_equal(observed, expected),
                           f"expected={np.count_nonzero(expected)};actual={np.count_nonzero(observed)};intervals={intervals}"))
            checks.append((f"outage_{ordinal}_preexisting_invalid_preserved",
                           np.all(~_valid_vector(before) <= ~_valid_vector(after)), "base invalid epochs remain invalid"))
    elif 8 <= n <= 10:
        target = {8: 5.0, 9: 2.0, 10: 1.0}[n]
        for name, before, after in (("position", pos0, pos1), ("velocity", vel0, vel1), ("yaw", yaw0, yaw1)):
            valid = np.flatnonzero(_valid_vector(before)); bt = _numeric_matrix(before, ("time",))[:, 0]
            rate = 1 / np.median(np.diff(bt[valid])); expected = _valid_vector(before).copy()
            if rate > target + 1e-9:
                phase = float(case["anchor_time_s"]) % (1.0 / target)
                slots = np.floor((bt[valid] - phase) * target + 1e-9).astype(np.int64)
                keep_positions = np.unique(slots, return_index=True)[1]
                expected[valid] = False; expected[valid[keep_positions]] = True
            checks.append((f"downsample_{name}_exact_phase_mask", np.array_equal(_valid_vector(after), expected),
                           f"input_rate={rate:.6g};target={target};kept={np.count_nonzero(expected)}"))
    elif n in (11, 12):
        ratio = 0.30 if n == 11 else 0.60
        for name, before, after in (("position", pos0, pos1), ("velocity", vel0, vel1), ("yaw", yaw0, yaw1)):
            expected = round(ratio * np.count_nonzero(_valid_vector(before))); actual = np.count_nonzero(_valid_vector(before) & ~_valid_vector(after))
            checks.append((f"dropout_{name}_exact_count", actual == expected, f"expected={expected};actual={actual}"))
    elif 13 <= n <= 22 or n in (27, 59):
        delta = local_position_deltas(pos0, pos1); h = np.linalg.norm(delta[:, :2], axis=1); up = -delta[:, 2]
        changed = np.flatnonzero(np.linalg.norm(delta, axis=1) > 1e-5)
        if n in (13, 14, 15, 27, 59):
            hs, vs = {13: (.5, 1), 14: (1.5, 2.5), 15: (3, 5), 27: (3, 5), 59: (3, 5)}[n]
            checks.extend((("position_noise_n_component_sigma", abs(float(np.std(delta[:, 0])) - hs) <= max(.15, .2 * hs), f"observed={np.std(delta[:,0])}"),
                           ("position_noise_e_component_sigma", abs(float(np.std(delta[:, 1])) - hs) <= max(.15, .2 * hs), f"observed={np.std(delta[:,1])}"),
                           ("position_noise_vertical_sigma", abs(float(np.std(up)) - vs) <= max(.2, .2 * vs), f"observed={np.std(up)}")))
        elif n in (16, 17):
            hm, vm = {16: (1.5, .5), 17: (3, 1)}[n]
            checks.extend((("static_bias_horizontal", np.allclose(h, hm, atol=2e-3), f"median={np.median(h)}"),
                           ("static_bias_vertical", np.allclose(np.abs(up), vm, atol=2e-3), f"median={np.median(np.abs(up))}")))
        elif n == 18:
            times = _numeric_matrix(pos0, ("time",))[:, 0]; before_window = times <= WINDOW_START_S
            after_window = times >= WINDOW_END_S
            checks.extend((("drift_zero_through_window_start", np.all(np.linalg.norm(delta[before_window], axis=1) < 1e-4), f"rows={np.count_nonzero(before_window)}"),
                           ("drift_horizontal_full_from_window_end", np.allclose(h[after_window], 3, atol=2e-3), f"rows={np.count_nonzero(after_window)}"),
                           ("drift_vertical_full_from_window_end", np.allclose(np.abs(up[after_window]), 1, atol=2e-3), f"rows={np.count_nonzero(after_window)}")))
        elif n == 19:
            component = component_by_operation.get("position_sinusoidal_multipath", {})
            phase = float(component.get("phase_rad", math.nan))
            times = _numeric_matrix(pos0, ("time",))[:, 0]; angle = times / 30.0 + phase
            expected = np.column_stack((2*np.cos(angle), 2*np.sin(angle), -.5*np.sin(angle)))
            checks.extend((("sinusoid_exact_preserved_period_phase", np.allclose(delta, expected, atol=2e-3), f"period={60*math.pi}"),
                           ("sinusoid_NE_quadrature", abs(float(np.mean(delta[:,0]*delta[:,1]))) < .25, "quadrature rotation"),
                           ("sinusoid_horizontal_constant_magnitude", np.allclose(h, 2, atol=2e-3), f"range={np.min(h)},{np.max(h)}"),
                           ("sinusoid_vertical_amplitude", abs(float(np.max(np.abs(up))) - .5) < .02, f"max={np.max(np.abs(up))}")))
        elif n in (20, 21):
            ratio, hm, vm = {20: (.02, 2, 1), 21: (.05, 4, 2)}[n]
            checks.extend((("position_spike_exact_count", len(changed) == round(ratio * len(pos0.rows)), f"changed={len(changed)}"),
                           ("position_spike_horizontal_magnitude", np.allclose(h[changed], hm, atol=2e-3), f"target={hm}"),
                           ("position_spike_vertical_magnitude", np.allclose(np.abs(up[changed]), vm, atol=2e-3), f"target={vm}")))
        elif n == 22:
            contiguous = len(changed) in range(3, 6) and np.all(np.diff(changed) == 1)
            checks.extend((("position_burst_length_contiguous", bool(contiguous), f"changed={changed.tolist()}"),
                           ("position_burst_horizontal_magnitude", np.allclose(h[changed], 8, atol=2e-3), "target=8m"),
                           ("position_burst_vertical_magnitude", np.allclose(np.abs(up[changed]), 4, atol=2e-3), "target=4m")))
    if n in (23, 24, 25, 26, 28):
        factor = {23: 1.5, 24: 2.5, 25: 4, 26: .25, 28: 4}[n]
        before = _numeric_matrix(pos0, ("std_n_m", "std_e_m", "std_d_m")); after = _numeric_matrix(pos1, ("std_n_m", "std_e_m", "std_d_m"))
        values0 = _numeric_matrix(pos0, ("lat_deg", "lon_deg", "height_m")); values1 = _numeric_matrix(pos1, ("lat_deg", "lon_deg", "height_m"))
        checks.extend((("position_std_ratio", np.allclose(after / before, factor, atol=1e-7), f"factor={factor}"),
                       ("position_value_unchanged", np.array_equal(values0, values1), "lat/lon/height exact")))
    if n == 27:
        std0 = _numeric_matrix(pos0, ("std_n_m", "std_e_m", "std_d_m")); std1 = _numeric_matrix(pos1, ("std_n_m", "std_e_m", "std_d_m"))
        checks.append(("bad_position_optimistic_std_ratio", np.allclose(std1/std0, .25, atol=1e-7), "factor=.25"))
    if n == 29:
        checks.extend((("status_only_position_bytes_unchanged", pos0.sha256() == pos1.sha256(), "position values/std/valid exact"),
                       ("status_only_solver_sources_unchanged", all(base.tables[name].sha256() == generated.tables[name].sha256() for name in SOLVER_SOURCE_IDS), "no active C++ metadata path")))
    if 30 <= n <= 40:
        y0 = _numeric_matrix(yaw0, ("yaw_deg",))[:, 0]; y1 = _numeric_matrix(yaw1, ("yaw_deg",))[:, 0]; diff = (y1 - y0 + 180) % 360 - 180
        if n in (32, 33, 38):
            sigma = {32: 1, 33: 5, 38: 10}[n]; checks.append(("yaw_noise_sigma", abs(float(np.std(diff)) - sigma) <= max(.2, .2 * sigma), f"observed={np.std(diff)}"))
        if n in (34, 35):
            ratio = .05 if n == 34 else .10; changed = np.flatnonzero(np.abs(diff) > 1e-8)
            checks.extend((("yaw_spike_exact_count", len(changed) == round(ratio * len(y0)), f"changed={len(changed)}"),
                           ("yaw_spike_wrap_magnitude", np.allclose(np.abs(diff[changed]), 10, atol=2e-7), "magnitude=10")))
        if n in (36, 37, 38):
            factor = {36: 1.5, 37: 3, 38: .25}[n]
            std0 = _numeric_matrix(yaw0, ("yaw_std_deg",))[:, 0]; std1 = _numeric_matrix(yaw1, ("yaw_std_deg",))[:, 0]
            checks.append(("yaw_std_ratio", np.allclose(std1 / std0, factor, atol=1e-7), f"factor={factor}"))
        if n == 39:
            dropped = _valid_vector(yaw0) & ~_valid_vector(yaw1); transitions = np.diff(np.r_[False, dropped, False].astype(int)); runs = list(zip(np.flatnonzero(transitions == 1), np.flatnonzero(transitions == -1)))
            nonadjacent = all(right[0] - left[1] >= 1 for left, right in zip(runs, runs[1:]))
            checks.append(("baseline_three_quality_bursts", len(runs) == 3 and nonadjacent and all(2 <= end - start <= 4 for start, end in runs), f"runs={runs}"))
        if n == 40:
            length0 = _numeric_matrix(yaw0, ("baseline_length_m",))[:,0]; length1 = _numeric_matrix(yaw1, ("baseline_length_m",))[:,0]
            std0 = _numeric_matrix(yaw0, ("yaw_std_deg",))[:, 0]
            std1 = _numeric_matrix(yaw1, ("yaw_std_deg",))[:, 0]
            component = component_by_operation.get("baseline_length_jitter_relacc", {})
            checks.extend((("baseline_jitter_yaw_unchanged", np.array_equal(y0, y1), "yaw direction preserved"),
                           ("baseline_jitter_sigma_preserved", abs(float(np.std(length1-length0))-.03) < .008, f"observed={np.std(length1-length0)}"),
                           ("baseline_jitter_minimum", np.all(length1 >= .01), f"min={np.min(length1)}"),
                           ("baseline_relacc_field_absent", "rel_acc_m" not in yaw1.fields, "fresh schema has no rel_acc_m"),
                           ("baseline_relacc_unit_alias_forbidden", np.array_equal(std0, std1), "yaw std unchanged; no metre-to-degree substitution"),
                           ("baseline_relacc_no_active_path_declared", component.get("rel_acc_no_active_path") is True, "unavailable rel_acc is audit-only"),
                           ("baseline_solver_runtime_input_invariant", compose_solver_gnss18(base) == compose_solver_gnss18(generated), "18-column runtime input unchanged"),
                           ("baseline_relacc_solver_mapping_declared", component.get("solver_visible_mapping") == "none_audit_only_baseline_metadata", "no active solver mapping")))
    if n == 41:
        bn = _numeric_matrix(yaw1, ("baseline_n_m", "baseline_e_m")); expected_yaw = (np.rad2deg(np.arctan2(bn[:, 1], bn[:, 0])) + 90 + 180) % 360 - 180; actual = _numeric_matrix(yaw1, ("yaw_deg",))[:, 0]
        delta = _numeric_matrix(yaw1, ("baseline_n_m", "baseline_e_m", "baseline_d_m")) - _numeric_matrix(yaw0, ("baseline_n_m", "baseline_e_m", "baseline_d_m"))
        checks.extend((("asymmetric_geometry_recomputed", np.allclose(((actual - expected_yaw + 180) % 360) - 180, 0, atol=1e-6), "GNSS2-GNSS1 + fixed 90deg"),
                       ("asymmetric_horizontal_component_sigma", all(abs(float(np.std(delta[:,axis]))-3) < .65 for axis in (0,1)), f"std={np.std(delta,axis=0)}"),
                       ("asymmetric_vertical_component_sigma", abs(float(np.std(delta[:,2]))-2) < .45, f"std={np.std(delta[:,2])}"),
                       ("asymmetric_position_provider_invariant", pos0.sha256() == pos1.sha256(), "single position input unchanged")))
    if n in (43, 44, 45, 47, 48, 49, 50):
        before, after = (vel0, vel1) if n in (43, 44, 45) else (raw0, raw1)
        delta = _numeric_matrix(after, ("vn", "ve", "vd")) - _numeric_matrix(before, ("vn", "ve", "vd")); norm = np.linalg.norm(delta, axis=1); changed = np.flatnonzero(norm > 1e-8)
        if n in (43, 45, 47, 49):
            expected_noise = replay_rngs["noise_velocity"].normal(0.0, .5, (len(before.rows), 3))
            checks.append(("velocity_noise_all_axes_exact_seed_replay",
                           np.allclose(delta, expected_noise, atol=2e-9, rtol=0),
                           "named noise_velocity substream; vn/ve/vd exact"))
        if n in (44, 48):
            magnitude = 2 if n == 44 else 1.5; checks.extend((("velocity_spike_exact_count", len(changed) == round(.02 * len(before.rows)), f"changed={len(changed)}"), ("velocity_spike_magnitude", np.allclose(norm[changed], magnitude, atol=1e-7), f"target={magnitude}")))
        if n == 50: checks.extend((("raw_conflict_horizontal_magnitude", np.allclose(np.linalg.norm(delta[:, :2], axis=1), 1, atol=1e-8), "raw offset=1m/s"), ("receiver_conflict_unchanged", vel0.sha256() == vel1.sha256(), "receiver unchanged")))
        if n in (45, 49):
            std0 = _numeric_matrix(before, ("std_vn", "std_ve", "std_vd")); std1 = _numeric_matrix(after, ("std_vn", "std_ve", "std_vd"))
            checks.append(("velocity_optimistic_std_ratio", np.allclose(std1/std0, .25, atol=1e-7), "factor=.25"))
    if n in (51, 52):
        r0 = _numeric_matrix(rp0, ("roll_rad", "pitch_rad")); r1 = _numeric_matrix(rp1, ("roll_rad", "pitch_rad")); delta = r1 - r0
        if n == 51:
            dropped = _valid_vector(rp0) & ~_valid_vector(rp1); remain = _valid_vector(rp0) & _valid_vector(rp1)
            noise_deg = np.rad2deg(delta[remain])
            checks.extend((("go2_rp_exact_half_dropout", np.count_nonzero(dropped) == round(.5 * np.count_nonzero(_valid_vector(rp0))), "drop exactly 50% valid"),
                           ("go2_rp_remaining_roll_noise_sigma", abs(float(np.std(noise_deg[:,0]))-3) < .65, f"observed={np.std(noise_deg[:,0])}"),
                           ("go2_rp_remaining_pitch_noise_sigma", abs(float(np.std(noise_deg[:,1]))-3) < .65, f"observed={np.std(noise_deg[:,1])}")))
        else: checks.append(("go2_rp_bias_vector_2deg", np.allclose(np.linalg.norm(delta, axis=1), math.radians(2), atol=1e-8), "constant vector"))
    if n in (53, 54):
        h0 = _numeric_matrix(hv0, ("vn", "ve")); h1 = _numeric_matrix(hv1, ("vn", "ve"))
        if n == 53:
            expected_noise = replay_rngs["noise_velocity"].normal(0.0, 1.0, (len(hv0.rows), 2))
            checks.append(("go2_hv_noise_both_axes_exact_seed_replay",
                           np.allclose(h1 - h0, expected_noise, atol=2e-9, rtol=0),
                           "named noise_velocity substream; N/E exact"))
        else:
            seed = int(str(case["seed_index"])[-2:]); scale = 1.5 if seed <= 3 or seed == 8 else 1.0
            ratio = .5 if seed >= 4 else 0.0; dropped = _valid_vector(hv0) & ~_valid_vector(hv1)
            checks.extend((("go2_hv_seed_group_scale", np.allclose(h1, h0*scale, atol=1e-8), f"scale={scale}"),
                           ("go2_hv_seed_group_dropout", np.count_nonzero(dropped) == round(ratio*np.count_nonzero(_valid_vector(hv0))), f"ratio={ratio}")))
    if n in (55, 56):
        metadata = generated.tables["source_quality_metadata"]; field = "audit_go2_metadata"; changed = sum(bool(row.get(field)) for row in metadata.rows); ratio = .35 if n == 55 else .30
        values = [row.get(field) for row in metadata.rows if row.get(field)]
        allowed = ({"contact_uncertain_mode_gait_unknown"} if n == 55 else {"high_high", "low_low"})
        seed = int(str(case["seed_index"])[-2:])
        pattern_ok = set(values).issubset(allowed)
        if n == 56 and seed != 8:
            pattern_ok = pattern_ok and set(values) == ({"high_high"} if seed % 2 == 0 else {"low_low"})
        if n == 56 and seed == 8: pattern_ok = pattern_ok and set(values) == allowed
        checks.extend((("audit_metadata_exact_ratio", changed == round(ratio * len(metadata.rows)), f"changed={changed}"),
                       ("audit_metadata_seed_pattern", pattern_ok, f"values={sorted(set(values))}")))
    if n == 57:
        medians = []
        latency_rows = {
            str(row.get("affected_source")): {**dict(row.get("details") or {}), **row}
            for row in component_rows if row.get("component") == "latency_jitter"
        }
        for name in ("gnss_position", "receiver_velocity", "dual_yaw", "raw_doppler", "go2_rp", "go2_hv"):
            generated_table = generated.tables[name]
            by_identity = {
                int(row[D57_ORIGINAL_ROW_ID]): float(row["time"])
                for row in generated_table.rows
            }
            if set(by_identity) != set(range(len(base.tables[name].rows))):
                raise EffectValidationError(f"D57 original-row identity closure failed: {name}")
            generated_in_original_order = np.asarray(
                [by_identity[index] for index in range(len(base.tables[name].rows))], dtype=float,
            )
            delta = generated_in_original_order - _numeric_matrix(base.tables[name], ("time",))[:,0]
            row = latency_rows.get(name, {}); latency = float(row.get("latency_s", math.nan)); jmax = float(row.get("jitter_max_s", math.nan))
            residual = delta-latency; medians.append(float(np.median(delta)))
            checks.extend(((f"latency_jitter_{name}_law", .1 <= latency <= .3 and .02 <= jmax <= .05 and np.min(residual) >= -jmax-1e-9 and np.max(residual) <= jmax+1e-9, f"latency={latency};jmax={jmax};residual={np.min(residual)},{np.max(residual)}"),
                           (f"latency_jitter_{name}_monotonic", _strict_monotonic(generated_table), "stable sorted")))
        checks.append(("latency_source_substreams_independent", len({round(value, 6) for value in medians}) == 6, f"medians={medians}"))
    if n in (58, 60):
        duration = 10 if n == 58 else 20
        start, end = place_interval(float(case["anchor_time_s"]), duration)
        # Every solver-visible value perturbation is confined to degradation; following 20s stays clean.
        recovery_mask = (_numeric_matrix(pos1, ("time",))[:,0] >= end) & (_numeric_matrix(pos1, ("time",))[:,0] < end + 20)
        p0 = _numeric_matrix(pos0, ("lat_deg", "lon_deg", "height_m")); p1 = _numeric_matrix(pos1, ("lat_deg", "lon_deg", "height_m"))
        pvalid0, pvalid1 = _valid_vector(pos0), _valid_vector(pos1)
        checks.extend((("recovery_interval_position_value_clean", np.array_equal(p0[recovery_mask], p1[recovery_mask]), "20s post interval"),
                       ("recovery_interval_position_valid_clean", np.array_equal(pvalid0[recovery_mask], pvalid1[recovery_mask]), "20s post interval validity")))
        if n == 58:
            times = _numeric_matrix(pos0, ("time",))[:,0]; interval_mask = (times >= start) & (times < end)
            checks.append(("D58_position_exact_outage", np.array_equal(_valid_vector(pos0)&interval_mask, _valid_vector(pos0)&~_valid_vector(pos1)), "10s half-open"))
            ytime = _numeric_matrix(yaw0, ("time",))[:,0]; candidates = _valid_vector(yaw0)&(ytime>=start)&(ytime<end)
            diff = (_numeric_matrix(yaw1,("yaw_deg",))[:,0]-_numeric_matrix(yaw0,("yaw_deg",))[:,0]+180)%360-180
            changed = np.abs(diff)>1e-8
            y_recovery = (ytime >= end) & (ytime < end + 20)
            ystd0 = _numeric_matrix(yaw0, ("yaw_std_deg",))[:, 0]
            ystd1 = _numeric_matrix(yaw1, ("yaw_std_deg",))[:, 0]
            checks.extend((("D58_yaw_spike_exact_count", np.count_nonzero(changed)==round(.1*np.count_nonzero(candidates)), f"changed={np.count_nonzero(changed)}"),
                           ("D58_yaw_spike_magnitude", np.allclose(np.abs(diff[changed]),10,atol=2e-7), "10deg"),
                           ("D58_yaw_spikes_confined", not np.any(changed & ~candidates), "outside interval unchanged"),
                           ("D58_yaw_std_valid_unchanged", np.array_equal(ystd0, ystd1) and np.array_equal(_valid_vector(yaw0), _valid_vector(yaw1)), "only yaw values spike"),
                           ("D58_recovery_yaw_exact_clean", np.array_equal(diff[y_recovery], np.zeros(np.count_nonzero(y_recovery))), "20s yaw recovery exact")))
        else:
            for label,before,after,std_fields in (("position",pos0,pos1,("std_n_m","std_e_m","std_d_m")),("receiver",vel0,vel1,("std_vn","std_ve","std_vd")),("raw",raw0,raw1,("std_vn","std_ve","std_vd")),("yaw",yaw0,yaw1,("yaw_std_deg",))):
                times=_numeric_matrix(before,("time",))[:,0]; mask=(times>=start)&(times<end)
                s0=_numeric_matrix(before,std_fields); s1=_numeric_matrix(after,std_fields)
                checks.append((f"D60_{label}_std_interval_factor",np.allclose(s1[mask]/s0[mask],.25,atol=1e-7) and np.array_equal(s1[~mask],s0[~mask]),"factor=.25 only during"))
            ptimes = _numeric_matrix(pos0, ("time",))[:, 0]; pmask = (ptimes >= start) & (ptimes < end)
            pd = local_position_deltas(pos0, pos1)
            pcount = int(np.count_nonzero(pmask)); prng = replay_rngs["noise_position"]
            expected_position = np.column_stack((
                prng.normal(0.0, 3.0, pcount), prng.normal(0.0, 3.0, pcount),
                -prng.normal(0.0, 5.0, pcount),
            ))
            checks.extend((("D60_position_noise_exact_seed_replay", np.allclose(pd[pmask], expected_position, atol=3e-5, rtol=0), "named noise_position substream; WGS84 roundtrip tolerance"),
                           ("D60_position_values_outside_interval_unchanged", np.array_equal(p0[~pmask], p1[~pmask]), "exact outside interval")))
            ytime = _numeric_matrix(yaw0, ("time",))[:, 0]; ymask = (ytime >= start) & (ytime < end)
            ydiff = (_numeric_matrix(yaw1, ("yaw_deg",))[:, 0] - _numeric_matrix(yaw0, ("yaw_deg",))[:, 0] + 180) % 360 - 180
            expected_yaw = replay_rngs["noise_yaw"].normal(0.0, 10.0, int(np.count_nonzero(ymask)))
            checks.extend((("D60_yaw_noise_exact_seed_replay", np.allclose(ydiff[ymask], expected_yaw, atol=2e-8, rtol=0), "named noise_yaw substream"),
                           ("D60_yaw_values_outside_interval_unchanged", np.allclose(ydiff[~ymask], 0, atol=1e-10), "exact outside interval")))
            for label, before, after, rng_name in (("receiver", vel0, vel1, "noise_velocity:receiver"),
                                                    ("raw", raw0, raw1, "noise_velocity:raw_doppler")):
                times = _numeric_matrix(before, ("time",))[:, 0]; mask = (times >= start) & (times < end)
                v0 = _numeric_matrix(before, ("vn", "ve", "vd")); v1 = _numeric_matrix(after, ("vn", "ve", "vd")); delta = v1 - v0
                expected_velocity = replay_rngs[rng_name].normal(0.0, .5, (int(np.count_nonzero(mask)), 3))
                checks.extend(((f"D60_{label}_velocity_noise_exact_seed_replay", np.allclose(delta[mask], expected_velocity, atol=2e-9, rtol=0), f"named {rng_name} substream"),
                               (f"D60_{label}_values_outside_interval_unchanged", np.array_equal(v0[~mask], v1[~mask]), "exact outside interval")))
    if n == 59:
        diff = _numeric_matrix(raw1,("vn","ve","vd"))-_numeric_matrix(raw0,("vn","ve","vd"))
        pd = local_position_deltas(pos0, pos1)
        prng = replay_rngs["noise_position"]; pcount = len(pos0.rows)
        expected_position = np.column_stack((
            prng.normal(0.0, 3.0, pcount), prng.normal(0.0, 3.0, pcount),
            -prng.normal(0.0, 5.0, pcount),
        ))
        pstd0 = _numeric_matrix(pos0, ("std_n_m", "std_e_m", "std_d_m")); pstd1 = _numeric_matrix(pos1, ("std_n_m", "std_e_m", "std_d_m"))
        checks.extend((("D59_position_noise_exact_seed_replay", np.allclose(pd, expected_position, atol=3e-5, rtol=0), "named noise_position substream"),
                       ("D59_position_std_unchanged", np.array_equal(pstd0, pstd1), "good reported std preserved"),
                       ("D59_raw_horizontal_conflict",np.allclose(np.linalg.norm(diff[:,:2],axis=1),1,atol=1e-8) and np.allclose(diff[:,2],0,atol=1e-10),"1m/s horizontal"),
                       ("D59_receiver_unchanged",vel0.sha256()==vel1.sha256(),"receiver exact"),
                       ("D59_good_yaw_unchanged",yaw0.sha256()==yaw1.sha256(),"yaw exact")))
    return checks


def validate_case_effect(
    *, base: ProviderBundle, generated: ProviderBundle, case: Mapping[str, Any],
    components: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    type_id = str(case["degradation_type_id"])
    component_rows = tuple(components)
    expected = expected_changed_tables(type_id, str(case.get("seed_index", "seed_00")))
    before = base.hashes(); after = generated.hashes()
    observed = frozenset(key for key in before if before[key] != after[key])
    detail: list[dict[str, Any]] = []

    def add(check: str, passed: bool, message: str) -> None:
        detail.append({"check": check, "passed": bool(passed), "detail": message})

    # 中文说明：每个 case 从同一 immutable base 以同一 seed 静态重放一次。
    # 这里只调用纯 provider handler，不启动 solver，也不读取 trace。
    replayed, replay_components, replay_semantics = apply_degradation(base, case)
    component_json = json.dumps(
        list(component_rows), sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    replay_component_json = json.dumps(
        replay_components, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    add("seed_replay_exact",
        replayed.hashes() == generated.hashes() and component_json == replay_component_json,
        "same immutable base + PCG64 seed reproduces table hashes/components exactly")
    add("seed_replay_trace_free", replay_semantics.get("trace_read_count", 0) == 0,
        "static provider replay opens no trace")

    idempotent_allowed = type_id in {"D08", "D09", "D10"}
    add("affected_source_changed_as_expected", observed == expected or (idempotent_allowed and observed.issubset(expected)),
        f"expected={sorted(expected)} observed={sorted(observed)}")
    unchanged = set(before) - set(expected)
    add("unaffected_source_unchanged", all(before[key] == after[key] for key in unchanged),
        f"unchanged_count={sum(before[key] == after[key] for key in unchanged)}/{len(unchanged)}")
    for source, table in generated.tables.items():
        add(f"{source}:timestamp_monotonic", _strict_monotonic(table), "strictly increasing")
        add(f"{source}:finite", _finite_table(table), "all solver numeric fields finite")
    add("trace_forbidden", case.get("trace_eval_only") is True, "trace_eval_only=true")
    add("algorithm_output_forbidden", case.get("final_v23_output_solver_input_allowed") is False and case.get("legsa_output_solver_input_allowed") is False, "both solver-input flags false")
    add("raw_mutation_false", base.raw_input_hashes == generated.raw_input_hashes, "immutable raw hashes unchanged")
    add("go2_not_truth", case.get("go2_truth_claim_allowed") is False, "Go2 remains weak prior/diagnostic")
    add("component_ledger_schema", all(row.get("status") == "PASS" for row in component_rows), "ledger is supporting, not validation authority")
    for check, passed, message in _type_specific_checks(base, generated, case, component_rows):
        add(check, bool(passed), message)
    if type_id in {f"D{value:02d}" for value in range(13, 23)} | {"D27", "D41", "D58", "D59", "D60"}:
        deltas = local_position_deltas(base.tables["gnss_position"], generated.tables["gnss_position"])
        add("position_local_frame_roundtrip", bool(np.all(np.isfinite(deltas))),
            f"max_local_3d_m={float(np.max(np.linalg.norm(deltas, axis=1))):.9g}")
    if type_id in {"D34", "D35"}:
        left = np.asarray([_finite(row["yaw_deg"]) for row in base.tables["dual_yaw"].rows])
        right = np.asarray([_finite(row["yaw_deg"]) for row in generated.tables["dual_yaw"].rows])
        diff = (right - left + 180.0) % 360.0 - 180.0
        nonzero = np.abs(diff) > 1e-8
        add("yaw_spike_magnitude_10deg", bool(np.allclose(np.abs(diff[nonzero]), 10.0, atol=2e-7)),
            f"changed={int(np.count_nonzero(nonzero))}")
    if type_id == "D40":
        left = [row["yaw_deg"] for row in base.tables["dual_yaw"].rows]
        right = [row["yaw_deg"] for row in generated.tables["dual_yaw"].rows]
        add("baseline_direction_preserved", left == right, "solver-visible yaw values unchanged")
    if type_id in {"D29", "D55", "D56"}:
        add("no_active_path", observed == {"source_quality_metadata"}, "audit-only metadata changed; solver tables identical")
    if type_id == "D40":
        add("no_active_path", observed == {"dual_yaw"},
            "only audit baseline metadata changed; composed solver input is invariant")
    passed = all(row["passed"] for row in detail)
    return {
        "case_id": case["case_id"], "degradation_type_id": type_id,
        "effect_validation_rule_id": case["effect_validation_rule_id"],
        "passed": passed, "expected_changed_tables": sorted(expected),
        "observed_changed_tables": sorted(observed), "no_active_path": type_id in NO_ACTIVE_PATH_TYPES,
        "trace_used": False, "raw_mutation": False, "detail_rows": detail,
    }


def validate_handler_closure() -> None:
    from .provider_generator import HANDLERS
    expected = {f"D{index:02d}" for index in range(1, 61)}
    if set(HANDLERS) != expected:
        raise EffectValidationError("provider handler registry is not D01..D60")
    if len(load_type_registry()) != 60:
        raise EffectValidationError("type registry count mismatch")
