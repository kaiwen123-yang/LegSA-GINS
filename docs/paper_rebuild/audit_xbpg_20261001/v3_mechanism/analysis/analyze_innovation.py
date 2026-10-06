#!/usr/bin/env python3
"""Offline, same-snapshot N12/N16 arithmetic; never executes a scientific entry.

Input: only the selected new observer events.jsonl, the registered queue and local
root mapping. Event CSV/full selected snapshots remain under <MECHANISM_ROOT>.
--publish-compact also writes a small summary/index under this analysis directory.
The command refuses existing output directories; it never rewrites observer logs.

Frozen ca73 references (not current working-tree policy):
  source_aware/source_aware_policy.cpp:179 cap, 239 LSIM, 554 OIM, 650 evaluate;
  kf_gins/gi_engine.cpp:1451 applySourceAwareWeighting, 1180-1201 HV 2D/999;
  common/types.cpp:172 multiply, 232 inverse (partial pivot, cutoff 1e-15).
MECHANISM_PROTOCOL.md fixes the tolerances below before real replay.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

FROZEN_COMMIT = "ca73cb1fb48a020fd2a450d79e520562c34eeb24"
NIS_ABS, NIS_REL = 1e-9, 1e-8
SCALE_ABS, SCALE_REL, HDX_NONZERO = 1e-10, 1e-10, 1e-12
D2R = math.pi / 180.0
ALPHA = {"receiver_position": .00003, "receiver_velocity": .04,
         "dual_antenna_yaw": .03, "raw_doppler_velocity": .35,
         "go2_attitude_roll_pitch": .02, "go2_horizontal_velocity": .03}
CAP_KEY = dict(zip(ALPHA, ("position_cap", "receiver_velocity_cap", "yaw_cap",
                          "raw_doppler_cap", "rp_cap", "hv_cap")))
POLICIES = {"n6b_conservative_innovation_covariance", "clean_v1_conservative_innovation_covariance"}
FAMILIES = {"", "n6b_conservative_quadratic", "clean_v1_conservative_quadratic"}
SNAPSHOT_KEYS = ("dz", "H", "dx_before", "P_before", "base_R")
FIELDS = ("source_path source_line_1based source_byte_offset source_line_bytes run_id event_seq "
          "measurement_attempt_seq sa_seq source row_id measurement_time fixed_window "
          "same_snapshot status unavailable_reason validation_checks_json source_enabled "
          "qm_active_scaling recorded_reason_codes_json recorded_accepted recorded_rejected "
          "dof Hdx_json Hdx_max_abs Hdx_nonzero nu_json S_json "
          "recorded_nis dz_nis_recomputed innovation_nis nis_changed "
          "recorded_normalized dz_normalized innovation_normalized "
          "dz_oim_normalized innovation_oim_normalized boundary_crossings_json boundary_status "
          "source_cap effective_cap frozen_alpha observed_alpha_available observed_alpha "
          "old_oim_multiplier new_oim_multiplier old_formula_raw_scale new_formula_raw_scale "
          "old_oim_capped new_oim_capped old_lsim new_lsim old_combined new_combined "
          "oim_raw_changed oim_capped_changed oim_cap_masked lsim_masked "
          "n12_classification shadow_final_R_changed shadow_policy_acceptance_changed "
          "actual_R_json old_expected_R_json n12_shadow_R_json "
          "metadata_std_xyz_json lsim_components_json n16_eligible n16_ineligible_reason "
          "n16_old_std_max n16_shadow_std_max n16_old_lsim n16_shadow_lsim "
          "n16_old_combined n16_shadow_combined n16_lsim_changed n16_shadow_final_R_changed "
          "n16_classification n16_shadow_lsim_components_json n16_shadow_R_json "
          "actual_R_mutated shadow_decision_applied closedloop_not_tested").split()


def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("nonfinite matrix/innovation value")
    return value


def close(a, b, kind="scale"):
    absolute, relative = (NIS_ABS, NIS_REL) if kind == "nis" else (SCALE_ABS, SCALE_REL)
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= absolute + relative * abs(b)


def vector(value):
    if not isinstance(value, list) or not value:
        raise ValueError("empty or non-list vector")
    return [finite(x) for x in value]


def matrix(value):
    if value["layout"] != "row_major":
        raise ValueError("matrix layout is not row_major")
    rows, cols = value["rows"], value["cols"]
    if type(rows) is not int or type(cols) is not int or rows < 1 or cols < 1:
        raise ValueError("invalid matrix dimensions")
    values = vector(value["data"])
    if len(values) != rows * cols:
        raise ValueError("matrix length mismatch")
    return [values[i * cols:(i + 1) * cols] for i in range(rows)]


def dot(a, b):
    if len(a) != len(b):
        raise ValueError("dot dimension mismatch")
    result = 0.0
    for x, y in zip(a, b):
        result += x * y
    return result


def matvec(a, b):
    return [dot(row, b) for row in a]


def multiply(a, b):
    if len(a[0]) != len(b):
        raise ValueError("matrix product dimension mismatch")
    return [[dot(row, column) for column in zip(*b)] for row in a]


def inverse(a):
    """Same partial-pivot Gauss-Jordan convention/cutoff as frozen types.cpp."""
    n = len(a)
    if any(len(row) != n for row in a):
        raise ValueError("inverse requires square matrix")
    work = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) < 1e-15:
            raise ValueError("singular matrix at frozen 1e-15 pivot cutoff")
        work[col], work[pivot] = work[pivot], work[col]
        divisor = work[col][col]
        for j in range(2 * n):
            work[col][j] /= divisor
        for row in range(n):
            if row != col:
                factor = work[row][col]
                for j in range(2 * n):
                    work[row][j] -= factor * work[col][j]
    result = [row[n:] for row in work]
    if not all(math.isfinite(x) for row in result for x in row):
        raise ValueError("nonfinite inverse")
    return result


def scaled(a, factor):
    return [[x * factor for x in row] for row in a]


def matrix_close(a, b):
    return len(a) == len(b) and all(len(x) == len(y) and all(close(v, w) for v, w in zip(x, y))
                                   for x, y in zip(a, b))


def matrix_scale_matches(actual, base, factor):
    """Use preregistered dimensionless scale tolerance, not an R-unit epsilon."""
    if len(actual) != len(base) or any(len(x) != len(y) for x, y in zip(actual, base)):
        return False
    return all((value == 0.0 if original == 0.0 else close(value / original, factor))
               for row, original_row in zip(actual, base) for value, original in zip(row, original_row))


def scaled_R_changed(base, old_scale, new_scale):
    return any(value != 0.0 for row in base for value in row) and not close(new_scale, old_scale)


def cap(value, config, source):
    maximum = min(max(1.0, finite(config["global_cap"])), max(1.0, finite(config[CAP_KEY[source]])))
    return min(max(1.0, value if math.isfinite(value) else maximum), maximum)


def enabled(config, source):
    return bool(config["enable_source_aware_weighting"] and config["mode"] != "off"
                and config["sources"][source]["enabled"])


def oim(normalized, config, source):
    """Raw quadratic then cap; multiplier applies only to alpha*delta^2."""
    delta = max(0.0, normalized - finite(config["deadband"]))
    multiplier = 1.6 if normalized > config["strong"] else 1.2 if normalized > config["moderate"] else 1.0
    raw = 1.0 + (ALPHA[source] * multiplier) * delta * delta
    return dict(raw=raw, capped=cap(raw, config, source), multiplier=multiplier,
                rejected=bool(config["reject_extreme"] and normalized > 10.0))


def lsim(metadata, config, source, remove_vertical_maxstd=False):
    """Exact N6B/clean_v1 LSIM, optionally remove ONLY HV maxStd D contribution.

    finiteStd still checks the original three values. All other metadata and
    readiness conditions remain unchanged, including a possible non-std maximum.
    """
    std = [float(x) for x in metadata["std_xyz"]]
    if len(std) != 3:
        raise ValueError("std_xyz must have three original metadata components")
    std_max = max(abs(x) for x in (std[:2] if remove_vertical_maxstd else std))
    components = []
    def add(reason, value):
        components.append({"reason": reason, "raw_scale": value})
    if not metadata["valid"]:
        add("lsim_invalid_source", max(1.0, config[CAP_KEY[source]]))
        return dict(scale=cap(components[-1]["raw_scale"], config, source), rejected=True,
                    std_max=std_max, components=components)
    if not metadata["covariance_available"]:
        add("lsim_covariance_missing", 1.5)
    if not all(math.isfinite(x) and x > 0 for x in std):
        add("lsim_std_nonfinite_or_missing", 1.5)
    dt = abs(float(metadata["time_diff_sec"]))
    if dt > .08:
        add("lsim_time_alignment_suspicious", 2.5 if dt > .25 else 1.5)
    if metadata["quality_flag"] not in ("nominal", "available"):
        add("lsim_quality_flag_suspicious", 1.5)
    if config["source_aware_go2_readiness_lsim_enabled"] and metadata["go2_readiness_metadata_available"]:
        state = metadata["go2_motion_state"]
        for condition, key, reason in (
            (metadata["go2_in_place_turn"] or state == "IN_PLACE_TURN", "source_aware_go2_in_place_turn_scale", "GO2_IN_PLACE_TURN"),
            (metadata["go2_impact_or_rough"] or state == "IMPACT_OR_ROUGH", "source_aware_go2_impact_or_rough_scale", "GO2_IMPACT_OR_ROUGH"),
            (metadata["go2_readiness_low"] or not metadata["go2_readiness_flag"] or
             (math.isfinite(float(metadata["go2_readiness_score"])) and float(metadata["go2_readiness_score"]) < .5),
             "source_aware_go2_readiness_low_scale", "GO2_READINESS_LOW"),
            (state in ("", "UNKNOWN"), "source_aware_go2_motion_unknown_scale", "GO2_MOTION_UNKNOWN")):
            if condition:
                add(reason, finite(config[key]))
    rejected = False
    if source in ("raw_doppler_velocity", "go2_attitude_roll_pitch", "go2_horizontal_velocity") and metadata["provider_status"] != "available":
        reason = {"raw_doppler_velocity": "lsim_raw_doppler_provider_unavailable",
                  "go2_attitude_roll_pitch": "lsim_go2_attitude_prior_unavailable",
                  "go2_horizontal_velocity": "lsim_go2_horizontal_velocity_unavailable"}[source]
        add(reason, max(1.0, config[CAP_KEY[source]]))
        rejected = True
    if source == "receiver_position":
        if std_max > 50: add("lsim_receiver_position_std_extreme", 5.0)
        elif std_max > 25: add("lsim_receiver_position_std_high", 2.0)
    elif source == "receiver_velocity":
        if std_max > 6: add("lsim_receiver_velocity_std_extreme", 4.0)
        elif std_max > 3: add("lsim_receiver_velocity_std_high", 2.0)
    elif source == "dual_antenna_yaw":
        if not metadata["rel_valid"] or not metadata["ant_valid"] or metadata["ant_state"] != "available":
            add("lsim_dual_yaw_antenna_state_suspicious", 2.0)
        if float(metadata["yaw_std_rad"]) > 30.0 * D2R: add("lsim_dual_yaw_std_extreme", 6.0)
        elif float(metadata["yaw_std_rad"]) > 15.0 * D2R: add("lsim_dual_yaw_std_high", 2.0)
    elif source == "raw_doppler_velocity" and not rejected:
        count = metadata["sat_count"]
        if 0 < count < 5: add("lsim_raw_doppler_sat_count_very_low", 3.0)
        elif 0 < count < 8: add("lsim_raw_doppler_sat_count_low", 1.5)
        if std_max > 2: add("lsim_raw_doppler_std_extreme", 4.0)
        elif std_max > 1: add("lsim_raw_doppler_std_high", 2.0)
        if metadata["spike_candidate"]: add("lsim_solver_visible_spike_candidate", 1.25)
    elif source == "go2_attitude_roll_pitch" and not rejected and float(metadata["yaw_std_rad"]) > 15.0 * D2R:
        add("lsim_go2_attitude_std_high", 2.0)
    elif source == "go2_horizontal_velocity" and not rejected and std_max > 10:
        add("lsim_go2_horizontal_velocity_std_high", 2.0)
    raw = max([1.0] + [x["raw_scale"] for x in components])
    return dict(scale=cap(raw, config, source), rejected=rejected, std_max=std_max, components=components)


def policy(metadata, config, source, normalized, remove_vertical_maxstd=False):
    formula = oim(normalized, config, source)
    result = dict(formula=formula, lsim=1.0, oim=1.0, combined=1.0,
                  rejected=False, components=[], std_max=None)
    if not enabled(config, source):
        return result
    masks = config["sources"][source]
    if config["mode"] in ("lsim_only", "lsim_oim") and masks["lsim_enabled"]:
        old = lsim(metadata, config, source, remove_vertical_maxstd)
        result.update(lsim=old["scale"], rejected=old["rejected"], components=old["components"], std_max=old["std_max"])
    if config["mode"] in ("oim_only", "lsim_oim") and masks["oim_enabled"]:
        result["oim"] = formula["capped"]
        result["rejected"] = result["rejected"] or formula["rejected"]
    result["combined"] = cap(max(result["lsim"], result["oim"]), config, source)
    return result


def boundary_crossings(old, new, dof, config):
    """Translate each normalized gate to dof*t^2; reuse fixed NIS tolerance."""
    results = []
    for name in ("deadband", "moderate", "strong"):
        threshold = finite(config[name])
        if (old > threshold) != (new > threshold):
            target = dof * threshold * threshold
            ambiguous = close(dof * old * old, target, "nis") or close(dof * new * new, target, "nis")
            results.append({"gate": name, "threshold": threshold,
                            "status": "BOUNDARY_AMBIGUOUS" if ambiguous else "CROSSED"})
    return results


def blank_row(event, source_path, line, offset, length):
    context = event.get("data", {}).get("context", {})
    row = dict.fromkeys(FIELDS, "")
    row.update(source_path=source_path, source_line_1based=line, source_byte_offset=offset,
               source_line_bytes=length, run_id=event.get("run_id", ""), event_seq=event.get("event_seq", ""),
               source=context.get("source", ""), measurement_attempt_seq=context.get("measurement_attempt_seq", ""),
               sa_seq=context.get("sa_seq", ""), row_id=context.get("row_id", ""),
               actual_R_mutated=False, shadow_decision_applied=False, closedloop_not_tested=True)
    return row


def analyze_event(event, config, begin_snapshot, source_path="<SYNTHETIC>/events.jsonl", line=1, offset=0, length=0, group="C00"):
    row = blank_row(event, source_path, line, offset, length)
    checks = {}
    try:
        snapshot = event["data"]["snapshot"]
        metadata, original, observed = snapshot["metadata"], snapshot["innovation"], snapshot["result"]
        source = metadata["source"]
        if source not in ALPHA or config["policy_version"] not in POLICIES or config["method_family"] not in FAMILIES:
            raise ValueError("unsupported source/policy/method family")
        if config["mode"] not in ("off", "lsim_only", "oim_only", "lsim_oim"):
            raise ValueError("unsupported source-aware mode")
        checks["source_context"] = source == row["source"]
        checks["same_snapshot"] = begin_snapshot is not None and all(begin_snapshot[k] == snapshot[k] for k in SNAPSHOT_KEYS)
        row["same_snapshot"] = checks["same_snapshot"]
        row.update(source_enabled=snapshot["source_enabled"], qm_active_scaling=snapshot["qm_active_scaling"],
                   recorded_reason_codes_json=js(observed["reason_codes"]), recorded_accepted=observed["accepted"],
                   recorded_rejected=observed["rejected"], metadata_std_xyz_json=js(metadata["std_xyz"]),
                   recorded_nis=original["nis"], recorded_normalized=original["normalized_innovation"], dof=original["dof"])
        if snapshot["qm_active_scaling"]:
            raise ValueError("QM_ACTIVE_SCALING_NOT_MODELED")
        if not original["used_innovation_covariance"] or not config["use_innovation_covariance"]:
            raise ValueError("ORIGINAL_FALLBACK_NOT_SAME_NIS_DEFINITION")
        dz, dx = vector(snapshot["dz"]), vector(snapshot["dx_before"])
        h, p, r, actual = (matrix(snapshot[k]) for k in ("H", "P_before", "base_R", "effective_R"))
        n, m = len(dx), len(dz)
        if len(h) != m or len(h[0]) != n or len(p) != n or len(p[0]) != n or len(r) != m or len(r[0]) != m:
            raise ValueError("snapshot matrix/vector dimension mismatch")
        hdx = matvec(h, dx)
        nu = [a - b for a, b in zip(dz, hdx)]
        hph = multiply(multiply(h, p), [list(x) for x in zip(*h)])
        s = [[a + b for a, b in zip(x, y)] for x, y in zip(hph, r)]
        si = inverse(s)
        old_nis, new_nis = (max(0.0, dot(v, matvec(si, v))) for v in (dz, nu))
        old_normal, new_normal = math.sqrt(old_nis / m), math.sqrt(new_nis / m)
        trace_r, trace_hph = sum(r[i][i] for i in range(m)), sum(hph[i][i] for i in range(m))
        def oim_normal(normalized, v):
            return normalized if normalized > 0 else math.sqrt(dot(v, v)) / math.sqrt(max(1e-12, trace_r + trace_hph))
        old_input, new_input = oim_normal(old_normal, dz), oim_normal(new_normal, nu)
        old = policy(metadata, config, source, old_input)
        new = policy(metadata, config, source, new_input)
        checks.update(dof=original["dof"] == m,
                      old_nis=close(old_nis, finite(original["nis"]), "nis"),
                      normalized=close(m * old_normal * old_normal, m * finite(original["normalized_innovation"]) ** 2, "nis"),
                      base_R_trace=close(trace_r, finite(original["base_R_trace"]), "nis"),
                      hph_trace=close(trace_hph, finite(original["hph_trace"]), "nis"),
                      innovation_cov_trace=close(trace_r + trace_hph, finite(original["innovation_cov_trace"]), "nis"),
                      source_enabled=enabled(config, source) == snapshot["source_enabled"],
                      source_cap=close(max(1.0, config[CAP_KEY[source]]), finite(observed["source_cap"])),
                      old_lsim=close(old["lsim"], finite(observed["lsim_R_scale"])),
                      old_oim=close(old["oim"], finite(observed["oim_R_scale"])),
                      old_combined=close(old["combined"], finite(observed["combined_R_scale"])),
                      old_policy_rejected=old["rejected"] == observed["rejected"],
                      old_policy_accepted=(not old["rejected"]) == observed["accepted"])
        expected = scaled(r, old["combined"])
        shadow = scaled(r, new["combined"])
        checks["effective_R"] = matrix_scale_matches(actual, r, old["combined"])
        if observed["oim_alpha_available"]:
            checks.update(alpha=close(ALPHA[source], finite(observed["oim_alpha"])),
                          multiplier=close(old["formula"]["multiplier"], finite(observed["oim_multiplier"])),
                          raw_scale=close(old["formula"]["raw"], finite(observed["oim_raw_scale"])))
        crossings = boundary_crossings(old_input, new_input, m, config)
        ambiguous = any(x["status"] == "BOUNDARY_AMBIGUOUS" for x in crossings)
        raw_changed = not close(old["formula"]["raw"], new["formula"]["raw"])
        capped_changed = not close(old["oim"], new["oim"])
        active_oim = enabled(config, source) and config["mode"] in ("oim_only", "lsim_oim") and config["sources"][source]["oim_enabled"]
        cap_masked = active_oim and raw_changed and not capped_changed and (
            not close(old["formula"]["raw"], old["formula"]["capped"]) or
            not close(new["formula"]["raw"], new["formula"]["capped"]))
        changed_r = scaled_R_changed(r, old["combined"], new["combined"])
        lsim_masked = active_oim and capped_changed and not changed_r and old["lsim"] >= max(old["oim"], new["oim"])
        classification = ("SA_DISABLED_SHADOW_NOT_APPLIED" if not enabled(config, source) else
                          "OIM_MASKED_BY_CONFIGURATION" if not active_oim else
                          "BOUNDARY_AMBIGUOUS" if ambiguous else
                          "SHADOW_FINAL_R_CHANGED" if changed_r else
                          "OIM_CHANGE_MASKED_BY_LSIM" if lsim_masked else
                          "RAW_OIM_CHANGE_MASKED_BY_CAP" if cap_masked else
                          "NIS_CHANGED_NO_FINAL_R_CHANGE" if not close(new_nis, old_nis, "nis") else
                          "NO_MATERIAL_NIS_OR_R_CHANGE")
        row.update(dof=m, Hdx_json=js(hdx), Hdx_max_abs=max(abs(x) for x in hdx),
                   Hdx_nonzero=any(abs(x) > HDX_NONZERO for x in hdx), nu_json=js(nu), S_json=js(s),
                   recorded_nis=original["nis"], dz_nis_recomputed=old_nis, innovation_nis=new_nis,
                   nis_changed=not close(new_nis, old_nis, "nis"), recorded_normalized=original["normalized_innovation"],
                   dz_normalized=old_normal, innovation_normalized=new_normal,
                   dz_oim_normalized=old_input, innovation_oim_normalized=new_input,
                   boundary_crossings_json=js(crossings), boundary_status="BOUNDARY_AMBIGUOUS" if ambiguous else "CLEAR",
                   source_cap=config[CAP_KEY[source]], effective_cap=min(max(1.0, config["global_cap"]), max(1.0, config[CAP_KEY[source]])),
                   frozen_alpha=ALPHA[source], observed_alpha_available=observed["oim_alpha_available"],
                   observed_alpha=observed["oim_alpha"], old_oim_multiplier=old["formula"]["multiplier"],
                   new_oim_multiplier=new["formula"]["multiplier"], old_formula_raw_scale=old["formula"]["raw"],
                   new_formula_raw_scale=new["formula"]["raw"], old_oim_capped=old["oim"], new_oim_capped=new["oim"],
                   old_lsim=old["lsim"], new_lsim=new["lsim"], old_combined=old["combined"], new_combined=new["combined"],
                   oim_raw_changed=raw_changed, oim_capped_changed=capped_changed, oim_cap_masked=cap_masked,
                   lsim_masked=lsim_masked, n12_classification=classification,
                   shadow_final_R_changed=changed_r, shadow_policy_acceptance_changed=old["rejected"] != new["rejected"],
                   actual_R_json=js(actual), old_expected_R_json=js(expected), n12_shadow_R_json=js(shadow),
                   lsim_components_json=js(old["components"]))
        time = finite(metadata["time"])
        row["measurement_time"] = time
        row["fixed_window"] = ("outside" if not 66 <= time <= 340 else
                               "full" if group not in ("A1", "A2") else
                               "before" if time < 196.2 else "during" if time < 216.2 else "after")
        n16_reasons = []
        if source != "go2_horizontal_velocity": n16_reasons.append("NOT_HV")
        if not enabled(config, source): n16_reasons.append("SA_DISABLED")
        if config["mode"] not in ("lsim_only", "lsim_oim") or not config["sources"][source]["lsim_enabled"]:
            n16_reasons.append("LSIM_DISABLED")
        std = [float(x) for x in metadata["std_xyz"]]
        if not (config["hv_vertical_disabled"] and config["hv_mode"] == "horizontal_2d" and m == 2):
            n16_reasons.append("NOT_VERTICAL_DISABLED_2D")
        if len(std) != 3 or std[2] != 999.0: n16_reasons.append("NO_EXACT_999_METADATA_SENTINEL")
        if len(std) != 3 or not all(math.isfinite(x) and x > 0 for x in std[:2]):
            n16_reasons.append("INVALID_HORIZONTAL_STD")
        elif m != 2 or not matrix_scale_matches(r, [[std[0] ** 2, 0.0], [0.0, std[1] ** 2]], 1.0):
            n16_reasons.append("TWO_DIMENSIONAL_BASE_R_NOT_ESTABLISHED")
        row.update(n16_eligible=not n16_reasons, n16_ineligible_reason=";".join(n16_reasons), n16_classification="NOT_ELIGIBLE")
        if not n16_reasons:
            without_d = policy(metadata, config, source, old_input, remove_vertical_maxstd=True)
            shadow16 = scaled(r, without_d["combined"])
            lsim16_changed = not close(old["lsim"], without_d["lsim"])
            r16_changed = scaled_R_changed(r, old["combined"], without_d["combined"])
            row.update(n16_old_std_max=old["std_max"], n16_shadow_std_max=without_d["std_max"],
                       n16_old_lsim=old["lsim"], n16_shadow_lsim=without_d["lsim"],
                       n16_old_combined=old["combined"], n16_shadow_combined=without_d["combined"],
                       n16_lsim_changed=lsim16_changed, n16_shadow_final_R_changed=r16_changed,
                       n16_classification="SHADOW_FINAL_R_CHANGED" if r16_changed else
                       "LSIM_CHANGE_MASKED_BY_OIM_OR_CAP" if lsim16_changed else "MAXSTD_REMOVED_OTHER_LSIM_OR_CAP_UNCHANGED",
                       n16_shadow_lsim_components_json=js(without_d["components"]), n16_shadow_R_json=js(shadow16))
        row["status"] = "VALIDATED_SAME_SNAPSHOT" if all(checks.values()) else "OLD_SNAPSHOT_VALIDATION_FAILED"
        if not all(checks.values()):
            row["unavailable_reason"] = ";".join(k for k, value in checks.items() if not value)
            row["n12_classification"] = row["n16_classification"] = "UNCLASSIFIABLE_VALIDATION_FAILED"
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, OverflowError) as error:
        row.update(status="UNAVAILABLE_SNAPSHOT", unavailable_reason=type(error).__name__ + ": " + str(error),
                   n12_classification="UNCLASSIFIABLE", n16_classification="UNCLASSIFIABLE")
    row["validation_checks_json"] = js(checks)
    return row


def analyze_stream(stream, source_path, run_id, output, group="C00"):
    """One sequential read; no raw/provider/error-series access or scientific call."""
    config, begin_seen, end_seen = None, False, False
    pending, summary, exemplars = {}, defaultdict(Counter), []
    event_counts, sequence, line_number, stream_error = Counter(), 0, 0, ""
    csv_path, snapshot_path = output / "SA_EVENT_ANALYSIS.csv", output / "KEY_SNAPSHOTS.jsonl"
    seen_example_categories = set()
    with csv_path.open("x", encoding="utf-8", newline="") as csv_file, snapshot_path.open("xb") as snapshots:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        while True:
            offset = stream.tell()
            raw = stream.readline()
            if not raw: break
            line_number += 1
            try:
                event = json.loads(raw)
                if event["run_id"] != run_id or event["event_seq"] != sequence + 1 or end_seen:
                    raise ValueError("event run/sequence/footer ordering mismatch")
                sequence = event["event_seq"]
                kind = event["event"]
                event_counts[kind] += 1
                if kind == "OBSERVER_BEGIN":
                    if sequence != 1 or event["data"]["schema"] != "V3_MECHANISM_OBSERVER_1":
                        raise ValueError("observer schema/begin mismatch")
                    begin_seen = True
                elif kind == "OBSERVER_END":
                    if event["data"]["prior_event_count"] != sequence - 1:
                        raise ValueError("footer count mismatch")
                    end_seen = True
                elif kind == "CONFIGURATION":
                    if config is not None: raise ValueError("duplicate configuration")
                    config = event["data"]["snapshot"]
                elif kind == "SA_EVALUATION_BEGIN":
                    key = event["data"]["context"]["sa_seq"]
                    if key in pending: raise ValueError("duplicate pending SA sequence")
                    pending[key] = event["data"]["snapshot"]
                elif kind == "SA_EVALUATION":
                    key = event["data"]["context"]["sa_seq"]
                    row = analyze_event(event, config, pending.pop(key, None), source_path, line_number, offset, len(raw), group)
                    writer.writerow(row)
                    count = summary[(row["source"], row["fixed_window"])]
                    count["SA_EVALUATION_count"] += 1
                    count["status:" + row["status"]] += 1
                    count["n12:" + row["n12_classification"]] += 1
                    count["n16:" + row["n16_classification"]] += 1
                    if row["status"] == "VALIDATED_SAME_SNAPSHOT":
                        for field in ("Hdx_nonzero", "nis_changed", "oim_raw_changed", "oim_capped_changed", "oim_cap_masked", "lsim_masked",
                                      "shadow_final_R_changed", "shadow_policy_acceptance_changed", "n16_eligible", "n16_lsim_changed", "n16_shadow_final_R_changed"):
                            if row[field] is True: count[field] += 1
                    category = (row["source"], row["n12_classification"], row["n16_classification"])
                    # First-in-event-order example per category, at most 24 total;
                    # not selected by magnitude or a preferred outcome.
                    if category not in seen_example_categories and len(exemplars) < 24:
                        seen_example_categories.add(category)
                        snapshots.write(raw)
                        exemplars.append({k: row[k] for k in ("source_path", "source_line_1based", "source_byte_offset", "source_line_bytes",
                                          "run_id", "event_seq", "source", "n12_classification", "n16_classification")})
            except (KeyError, ValueError, TypeError) as error:
                stream_error = f"line {line_number}: {type(error).__name__}: {error}"
                break
    complete = begin_seen and end_seen and not pending and not stream_error and config is not None
    validated_events = sum(count["status:VALIDATED_SAME_SNAPSHOT"] for count in summary.values())
    failed_events = sum(count["status:OLD_SNAPSHOT_VALIDATION_FAILED"] for count in summary.values())
    unavailable_events = sum(count["status:UNAVAILABLE_SNAPSHOT"] for count in summary.values())
    all_validated = complete and validated_events > 0 and validated_events == event_counts["SA_EVALUATION"]
    analysis_status = ("VALIDATED" if all_validated else "NO_SA_EVENTS" if complete and not event_counts["SA_EVALUATION"]
                       else "VALIDATION_FAILED")
    result = dict(stream_status="COMPLETE" if complete else "INCOMPLETE_EVENT_STREAM", analysis_status=analysis_status, run_id=run_id,
                  source_path=source_path, lines_read=line_number, event_counts=dict(event_counts),
                  pending_SA_begin_count=len(pending), stream_error=stream_error,
                  source_commit=FROZEN_COMMIT, created_utc=datetime.now(timezone.utc).isoformat(),
                  validation_only=True, actual_R_mutated=False, shadow_decision_applied=False, closedloop_not_tested=True,
                  native_calls=0, evaluator_calls=0, provider_calls=0, reference_reads=0, retained_error_series_reads=0,
                  rolling_history_recomputed=False, tolerances=dict(nis_abs=NIS_ABS, nis_rel=NIS_REL,
                      scale_abs=SCALE_ABS, scale_rel=SCALE_REL, Hdx_nonzero=HDX_NONZERO),
                  boundary_rule="normalized gates mapped to dof*threshold^2 and compared with fixed NIS tolerance",
                  R_comparison_rule="nonzero base_R entries compared by dimensionless scale with fixed scale tolerance; zero entries exact",
                  rows=[dict(source=key[0], fixed_window=key[1], counts=dict(count)) for key, count in sorted(summary.items())],
                  key_snapshot_selection="first event per source/N12/N16 category, at most 24; full events remain external",
                  key_snapshot_count=len(exemplars), configuration=config,
                  validated_SA_events=validated_events,
                  failed_SA_events=failed_events, unavailable_SA_events=unavailable_events,
                  unavailable_or_failed_SA_events=event_counts["SA_EVALUATION"] - validated_events,
                  all_SA_events_validated=all_validated)
    return result, exemplars


def analysis_exit_code(summary):
    return 0 if summary["analysis_status"] == "VALIDATED" else 2


def check_replay_identity(receipt, access, run_id, variant):
    """Gate historical attribution before opening any real observer event file."""
    required = {
        "slot_id": receipt.get("slot_id") == run_id + "__" + variant,
        "status": receipt.get("status") == "COMPLETED_BYTE_IDENTICAL",
        "access_passed": receipt.get("access_passed") is True and access.get("passed") is True,
        "scientific_manifest_match": receipt.get("scientific_manifest_match") is True,
        "one_native": str(receipt.get("native_exec_count")) == "1" and str(access.get("native_exec_count")) == "1",
        "exit_code": receipt.get("exit_code") == 0,
        "output_comparisons": len(receipt.get("output_comparisons", [])) == 5 and
            all(x.get("status") == "BYTE_IDENTICAL" for x in receipt.get("output_comparisons", [])),
        "identity_status": receipt.get("history_identity_status" if variant == "original" else
                                       "observer_identity_status") == "BYTE_IDENTICAL",
    }
    if not all(required.values()):
        raise ValueError("REPLAY_IDENTITY_NOT_ESTABLISHED:" + variant + ":" + ";".join(k for k, v in required.items() if not v))
    return required


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument("--publish-compact", action="store_true")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    base = repo / "docs/paper_rebuild/audit_xbpg_20261001/v3_mechanism"
    with (base / "DIAGNOSTIC_QUEUE.csv").open(encoding="utf-8", newline="") as stream:
        rows = [x for x in csv.DictReader(stream) if x["run_id"] == args.run_id]
    if len(rows) != 1 or rows[0]["source_commit"] != FROZEN_COMMIT:
        raise SystemExit("run is not uniquely registered at the frozen source")
    aliases = json.loads((repo / "configs/paper_rebuild/V3_MECHANISM_ROOTS.local.json").read_text())["aliases"]
    root = Path(aliases["<MECHANISM_ROOT>"]).resolve()
    identity = {}
    for variant in ("original", "observed"):
        directory = root / "replays" / args.run_id / variant
        receipt = json.loads((directory / "REPLAY_RECEIPT.json").read_text())
        access = json.loads((directory / "ACCESS_REVIEW.json").read_text())
        identity[variant] = check_replay_identity(receipt, access, args.run_id, variant)
    events = root / "replays" / args.run_id / "observed/observer/events.jsonl"
    if not events.is_file() or not events.resolve().is_relative_to(root):
        raise SystemExit("registered observer event file is absent or outside mechanism root")
    output = root / "analysis" / args.run_id / "innovation"
    compact = base / "analysis" / args.run_id
    if output.exists() or (args.publish_compact and compact.exists()):
        raise SystemExit("refusing existing analysis outputs; review previous receipt")
    output.mkdir(parents=True)
    source_alias = f"<MECHANISM_ROOT>/replays/{args.run_id}/observed/observer/events.jsonl"
    with events.open("rb") as stream:
        summary, examples = analyze_stream(stream, source_alias, args.run_id, output, rows[0]["group"])
    summary.update(data_mode=rows[0]["data_mode"], synthetic_data_used=rows[0]["synthetic_data_used"] == "True",
                   semisynthetic_data_used=rows[0]["semisynthetic_data_used"] == "True",
                   identity_gate_checks=identity, historical_attribution_requires_complete_event_stream=True,
                   event_csv=f"<MECHANISM_ROOT>/analysis/{args.run_id}/innovation/SA_EVENT_ANALYSIS.csv",
                   complete_key_snapshots=f"<MECHANISM_ROOT>/analysis/{args.run_id}/innovation/KEY_SNAPSHOTS.jsonl")
    (output / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.publish_compact:
        compact.mkdir()
        (compact / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        fields = list(examples[0]) if examples else ["source_path", "run_id", "event_seq"]
        with (compact / "KEY_SNAPSHOT_INDEX.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader(); writer.writerows(examples)
    print(js({"run_id": args.run_id, "stream_status": summary["stream_status"], "analysis_status": summary["analysis_status"],
              "SA_events": summary["event_counts"].get("SA_EVALUATION", 0), "failed_SA_events": summary["failed_SA_events"],
              "unavailable_SA_events": summary["unavailable_SA_events"],
              "event_csv": summary["event_csv"], "actual_R_mutated": False, "closedloop_not_tested": True}))
    # Write both detailed and compact evidence before a failing analysis exits.
    raise SystemExit(analysis_exit_code(summary))


if __name__ == "__main__":
    main()
