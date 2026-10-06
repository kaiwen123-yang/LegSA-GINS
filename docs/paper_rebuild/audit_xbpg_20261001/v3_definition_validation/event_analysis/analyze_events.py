#!/usr/bin/env python3
"""Single-slot, read-only observer analysis. No native/evaluator/provider imports.

Real streams are admitted only from CANDIDATE_QUEUE after receipt gates. Each
stream has one complete binary read, a streaming SHA256, and an immutable cache.
Comparisons read caches, never re-open an event payload. Source byte offsets keep
all original full matrices inspectable without copying the entire event stream.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SCHEMA = "V3_DEFINITION_EVENT_CACHE_1"
NIS_ABS, NIS_REL = 1e-9, 1e-8
R_ABS, R_REL = 1e-10, 1e-10
SYMMETRY_REL, PIVOT_TOL = 1e-10, 1e-12
SNAPSHOT_FIELDS = ("dz", "H", "dx_before", "P_before", "base_R")
COUNTERS = ("gnss_update_count", "position_update_count", "velocity_update_count",
            "yaw_attempt_count", "yaw_reject_count", "sa_active_evaluation_count",
            "raw_doppler_update_count", "rp_update_count", "hv_update_count")
STATE_UNITS = {"position_blh_rad_m": "rad,rad,m", "velocity_ned_mps": "m/s",
               "rpy_rad": "rad", "Cbn": "dimensionless", "qbn_wxyz": "dimensionless",
               "gyr_bias": "rad/s", "acc_bias": "m/s^2", "gyr_scale": "dimensionless",
               "acc_scale": "dimensionless", "antlever_m": "m"}
GOOD_P = "POSITIVE_DEFINITE_WITHIN_FIXED_NUMERIC_DIAGNOSTIC"


def clean_json(value):
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, np.generic):
        return clean_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value


def js(value):
    return json.dumps(clean_json(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def write_json(path, value):
    path.write_text(json.dumps(clean_json(value), ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def scalar_close(a, b, nis=False):
    a, b = finite(a), finite(b)
    if a is None or b is None:
        return False
    at, rt = (NIS_ABS, NIS_REL) if nis else (R_ABS, R_REL)
    return abs(a - b) <= at + rt * abs(b)


def matrix(x):
    if not isinstance(x, dict) or x.get("layout") != "row_major":
        raise ValueError("MATRIX_SCHEMA_OR_LAYOUT")
    rows, cols = x["rows"], x["cols"]
    if not isinstance(rows, int) or not isinstance(cols, int) or rows <= 0 or cols <= 0:
        raise ValueError("MATRIX_DIMENSION")
    if len(x["data"]) != rows * cols:
        raise ValueError("MATRIX_DATA_LENGTH")
    return np.asarray(x["data"], dtype=np.float64).reshape(rows, cols)


def inverse_frozen(a):
    """Frozen partial-pivot Gauss-Jordan cutoff; small measurement matrices only."""
    n = len(a)
    w = np.concatenate([a.copy(), np.eye(n)], axis=1).tolist()
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(w[i][c]))
        if abs(w[p][c]) < 1e-15:
            raise ValueError("SINGULAR_FROZEN_1E_15_CUTOFF")
        w[c], w[p] = w[p], w[c]
        d = w[c][c]
        w[c] = [v / d for v in w[c]]
        for i in range(n):
            if i != c:
                q = w[i][c]
                w[i] = [u - q * v for u, v in zip(w[i], w[c])]
    out = np.asarray([row[n:] for row in w])
    if not np.isfinite(out).all():
        raise ValueError("NONFINITE_INVERSE")
    return out


def covariance_health(p):
    """Same fixed definition as common/covariance_diagnostics.hpp; diagnostic copy."""
    r = dict(dimension=p.shape[0], square=p.ndim == 2 and p.shape[0] == p.shape[1],
             status="NOT_CHECKED", all_finite=False, positive_diagonal=False,
             normalization_attempted=False, normalized_finite=False,
             symmetry_tested=False, symmetric_within_tolerance=False,
             cholesky_attempted=False, positive_definite_diagnostic=False,
             pivots=[], nonfinite_flat_indices=[], nonpositive_diagonal_indices=[],
             min_diagonal=None, max_normalized_abs=None, max_normalized_asymmetry=None,
             symmetry_threshold=None, min_pivot=None, pivot_threshold=PIVOT_TOL,
             diagnostic_symmetrization_only=True, jitter_or_clipping=False,
             filter_matrix_modified=False)
    if not r["square"] or not p.size:
        r["status"] = "INVALID_SHAPE"
        return r
    r["nonfinite_flat_indices"] = np.flatnonzero(~np.isfinite(p.ravel())).tolist()
    d = np.diag(p)
    r["nonpositive_diagonal_indices"] = np.flatnonzero(~np.isfinite(d) | (d <= 0)).tolist()
    r["all_finite"] = not r["nonfinite_flat_indices"]
    r["positive_diagonal"] = not r["nonpositive_diagonal_indices"]
    if np.isfinite(d).any():
        r["min_diagonal"] = float(np.min(d[np.isfinite(d)]))
    if not r["all_finite"]:
        r["status"] = "NONFINITE_MATRIX"
        return r
    if not r["positive_diagonal"]:
        r["status"] = "NONPOSITIVE_DIAGONAL"
        return r
    r["normalization_attempted"] = True
    with np.errstate(all="ignore"):
        c = p / np.sqrt(d)[:, None] / np.sqrt(d)[None, :]
    r["normalized_finite"] = bool(np.isfinite(c).all())
    if not r["normalized_finite"]:
        r["status"] = "NONFINITE_NORMALIZATION"
        return r
    r["max_normalized_abs"] = float(np.max(np.abs(c)))
    r["max_normalized_asymmetry"] = float(np.max(np.abs(c - c.T)))
    r["symmetry_threshold"] = SYMMETRY_REL * max(1.0, r["max_normalized_abs"])
    r["symmetry_tested"] = True
    r["symmetric_within_tolerance"] = r["max_normalized_asymmetry"] <= r["symmetry_threshold"]
    if not r["symmetric_within_tolerance"]:
        r["status"] = "ASYMMETRIC"
        return r
    r["cholesky_attempted"] = True
    l = np.zeros_like(c)
    for i in range(len(c)):
        for j in range(i):
            q = 0.5 * c[i, j] + 0.5 * c[j, i]
            # Keep C++ serial subtraction order at the fixed pivot boundary.
            for k in range(j):
                q -= l[i, k] * l[j, k]
            l[i, j] = q / l[j, j]
        q = c[i, i]
        for k in range(i):
            q -= l[i, k] * l[i, k]
        r["pivots"].append(float(q))
        if not math.isfinite(q):
            r["status"] = "NONFINITE_CHOLESKY"
            return r
        r["min_pivot"] = min(r["pivots"])
        if q < -PIVOT_TOL:
            r["status"] = "CHOLESKY_NEGATIVE_PIVOT_RISK"
            return r
        if q <= PIVOT_TOL:
            r["status"] = "NEAR_SINGULAR_NUMERICALLY_UNRESOLVED"
            return r
        l[i, i] = math.sqrt(q)
    r.update(status=GOOD_P, positive_definite_diagnostic=True)
    return r


def vector_diff(a, b):
    """Exact binary64 first difference; no cross-unit scalar state distance."""
    av, bv = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if av.shape != bv.shape:
        return dict(status="SHAPE_DIFFERENT", baseline_shape=bv.shape, candidate_shape=av.shape)
    if not np.isfinite(av).all() or not np.isfinite(bv).all():
        return dict(status="NONFINITE_UNRESOLVED", candidate=av, baseline=bv)
    d = av - bv
    return dict(status="EXACTLY_EQUAL" if np.array_equal(av, bv) else "DIFFERENT",
                max_abs_delta=float(np.max(np.abs(d))) if d.size else 0.0, delta=d.tolist())


def state_diff(a, b):
    out = {}
    for name, unit in STATE_UNITS.items():
        if name not in a or name not in b:
            out[name] = {"status": "MISSING_FIELD", "unit": unit}
            continue
        av, bv = a[name], b[name]
        if name == "Cbn" and isinstance(av, dict) and isinstance(bv, dict):
            av, bv = matrix(av), matrix(bv)
        out[name] = dict(vector_diff(av, bv), unit=unit)
    return out


def scaled_matrix_matches(actual, base, scale):
    if actual.shape != base.shape or finite(scale) is None:
        return False
    for a, b in zip(actual.ravel(), base.ravel()):
        if not math.isfinite(a) or not math.isfinite(b):
            return False
        if b == 0:
            if a != 0:
                return False
        elif not scalar_close(a / b, scale):
            return False
    return True


def analyze_sa(snapshot, begin, candidate_id, config):
    out = {"validation_status": "UNAVAILABLE", "expected_basis": "conditional_nu" if candidate_id == "N12_ONLY" else "raw_dz"}
    checks = {}
    try:
        checks["same_pre_policy_snapshot"] = begin is not None and all(begin[k] == snapshot[k] for k in SNAPSHOT_FIELDS)
        dz, dx = np.asarray(snapshot["dz"], dtype=float), np.asarray(snapshot["dx_before"], dtype=float)
        h, p, r = (matrix(snapshot[k]) for k in ("H", "P_before", "base_R"))
        if h.shape != (len(dz), len(dx)) or p.shape != (len(dx), len(dx)) or r.shape != (len(dz), len(dz)):
            raise ValueError("SA_DIMENSION_MISMATCH")
        if not all(np.isfinite(v).all() for v in (dz, dx, h, p, r)):
            raise ValueError("NONFINITE_SA_SNAPSHOT")
        hdx, hph = h @ dx, h @ p @ h.T
        nu = dz - hdx
        si, inverse_error = None, None
        try:
            si = inverse_frozen(hph + r)
        except ValueError as exc:
            inverse_error = str(exc)
        raw_nis = max(0.0, float(dz @ si @ dz)) if si is not None else None
        conditional_nis = max(0.0, float(nu @ si @ nu)) if si is not None else None
        actual = nu if candidate_id == "N12_ONLY" else dz
        expected_nis = conditional_nis if candidate_id == "N12_ONLY" else raw_nis
        recorded, result = snapshot["innovation"], snapshot["result"]
        uses_cov = bool(recorded["used_innovation_covariance"])
        expected_uses_cov = bool(config["use_innovation_covariance"]) and si is not None and len(dz) > 0
        fallback = float(np.linalg.norm(actual)) / math.sqrt(max(1e-12, float(np.trace(r) + np.trace(hph))))
        normalized = math.sqrt(expected_nis / len(dz)) if expected_uses_cov else fallback
        checks.update(dof=recorded["dof"] == len(dz), uses_cov=uses_cov == expected_uses_cov,
                      normalized=scalar_close(normalized, recorded["normalized_innovation"], True),
                      residual_norm=scalar_close(float(np.linalg.norm(actual)), recorded["residual_norm"], True),
                      base_R_trace=scalar_close(float(np.trace(r)), recorded["base_R_trace"], True),
                      hph_trace=scalar_close(float(np.trace(hph)), recorded["hph_trace"], True))
        if expected_uses_cov:
            checks["nis"] = scalar_close(expected_nis, recorded["nis"], True)
        if "residual_vector" in recorded:
            rv = np.asarray(recorded["residual_vector"], dtype=float)
            checks["logged_residual_vector"] = rv.shape == actual.shape and all(scalar_close(a, b, True) for a, b in zip(actual, rv))
        if snapshot.get("qm_active_scaling"):
            raise ValueError("QM_ACTIVE_OUTSIDE_REGISTERED_QUEUE")
        effect_scale = result["combined_R_scale"] if snapshot["source_enabled"] else 1.0
        checks["sa_effective_R"] = scaled_matrix_matches(matrix(snapshot["effective_R"]), r, effect_scale)
        out.update(raw_dz=dz.tolist(), Hdx_before=hdx.tolist(), conditional_nu=nu.tolist(),
                   raw_nis=raw_nis, conditional_nis=conditional_nis,
                   recomputed_actual_nis=expected_nis if expected_uses_cov else None,
                   recomputed_actual_normalized=normalized, fallback_normalized=fallback,
                   inverse_status="AVAILABLE" if si is not None else inverse_error,
                   recorded_innovation=recorded, recorded_result=result,
                   metadata=snapshot["metadata"], source_enabled=snapshot["source_enabled"],
                   sa_effective_R=snapshot["effective_R"], base_R=snapshot["base_R"],
                   validation_status="VALIDATED" if all(checks.values()) else "VALIDATION_FAILED")
    except (ValueError, KeyError, TypeError, FloatingPointError) as exc:
        out["unavailable_reason"] = type(exc).__name__ + ":" + str(exc)
    out["checks"] = checks
    return clean_json(out)


def time_windows(value):
    t = finite(value)
    scopes = ["FULL_STREAM"]
    if t is not None and 66.0 <= t <= 340.0:
        scopes.append("FULL_RUN_66_340_CLOSED")
    if t is not None and 196.2 <= t < 216.2:
        scopes.append("FIXED_196_2_216_2_HALF_OPEN")
    return scopes


def file_stat(path):
    s = path.stat()
    return {k: getattr(s, k) for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns")}


def forbid_symlinks(path):
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError("SYMLINK_FORBIDDEN")


def open_db(path, readonly=False):
    if readonly:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(path)
        db.executescript("""
        CREATE TABLE measurement(stable_key TEXT, attempt INTEGER PRIMARY KEY, event_seq INTEGER, data TEXT);
        CREATE INDEX measurement_key ON measurement(stable_key);
        CREATE TABLE imu(imu_key TEXT PRIMARY KEY, imu_seq INTEGER, time REAL, data TEXT);
        CREATE TABLE gnss(gnss_seq INTEGER PRIMARY KEY, time REAL, data TEXT);
        CREATE TABLE special(event_seq INTEGER PRIMARY KEY, event TEXT, data TEXT);
        CREATE TABLE covariance(event_seq INTEGER, event TEXT, data TEXT);
        """)
    db.row_factory = sqlite3.Row
    return db


def pointer(event, path, offset, size):
    return dict(source_path=path, source_line=event["event_seq"], event_seq=event["event_seq"],
                event=event["event"], run_id=event["run_id"], byte_offset=offset, byte_length=size)


def rp_qualification(snapshot):
    aux = snapshot.get("auxiliary_candidates", {}).get("go2_roll_pitch", {})
    row = aux.get("selected_input", {})
    # Original Go2WeakPriorFactor::isActive is source_status plus positive stds.
    try:
        positive_stds = float(row["std_roll_rad"]) > 0 and float(row["std_pitch_rad"]) > 0
    except (ValueError, KeyError, TypeError):
        positive_stds = False
    return bool(aux.get("config_enabled") and aux.get("solver_enabled") and aux.get("match_found")
                and row.get("source_status") == "active" and positive_stds)


def scan_stream(source, output, *, source_alias, run_id, candidate_id="BASELINE", group="UNKNOWN", identity=None, data_mode=None):
    """Public pure analysis API; caller owns admission. Never retries a partial cache."""
    source, output = Path(source), Path(output)
    forbid_symlinks(source)
    forbid_symlinks(output)
    before = file_stat(source)
    code_sha = sha(Path(__file__))
    receipt_path = output / "SCAN_RECEIPT.json"
    if output.exists():
        if not receipt_path.is_file():
            raise ValueError("EXISTING_PARTIAL_CACHE_NO_AUTOMATIC_RESCAN")
        receipt = json.loads(receipt_path.read_text())
        if any((receipt.get("stream_status") != "COMPLETE", receipt.get("source_stat") != before,
                receipt.get("analyzer_sha256") != code_sha, receipt.get("source_path") != source_alias,
                receipt.get("run_id") != run_id, receipt.get("candidate_id") != candidate_id)):
            raise ValueError("CACHE_IDENTITY_OR_STAT_CHANGED_NO_AUTOMATIC_RESCAN")
        return dict(receipt, cache_reused=True, event_payload_opens_this_call=0, payload_open_attempts_this_call=0)
    output.mkdir(parents=True, exist_ok=False)
    db = open_db(output / "cache.sqlite")
    counts, sa_status = collections.Counter(), collections.Counter()
    window_counts = collections.Counter()
    source_stats = {}
    cov_summary = {}
    anomalies = []
    config, attempt, sa_begin, ekf_before, imu = None, None, None, None, None
    begin_seen = end_seen = False
    last_seq, total_bytes = 0, 0
    digest = hashlib.sha256()
    last_context = {}
    previous_counters = {}
    first_keys = set()
    started = time.time()
    index_file = (output / "EVENT_INDEX.csv").open("w", newline="", encoding="utf-8")
    index = csv.DictWriter(index_file, fieldnames=["event_seq", "event", "source", "imu_seq", "gnss_input_seq",
                                                "measurement_attempt_seq", "measurement_time", "byte_offset", "byte_length"], lineterminator="\n")
    index.writeheader()
    key_file = (output / "KEY_SNAPSHOTS.jsonl").open("w", encoding="utf-8")

    def add_anomaly(kind, ref, detail):
        anomalies.append(dict(kind=kind, pointer=ref, detail=detail))

    def save_key(event, ref, category):
        key = (category, event.get("data", {}).get("context", {}).get("source", ""))
        if key not in first_keys:
            first_keys.add(key)
            key_file.write(js(dict(category=category, pointer=ref, original_event=event)) + "\n")

    def add_cov(report, event, ref):
        kind = "ALL_IMU_END_CANDIDATE" if event["event"] == "COVARIANCE_HEALTH" else "EKF_SNAPSHOT_BASELINE_ONLY"
        s = cov_summary.setdefault(kind, dict(count=0, status_counts={}, first_anomaly=None,
                                              max_normalized_asymmetry=None, min_pivot=None))
        s["count"] += 1
        status = report["status"]
        s["status_counts"][status] = s["status_counts"].get(status, 0) + 1
        for field, fn in (("max_normalized_asymmetry", max), ("min_pivot", min)):
            value = finite(report.get(field))
            if value is not None:
                s[field] = value if s[field] is None else fn(s[field], value)
        if status != GOOD_P and s["first_anomaly"] is None:
            s["first_anomaly"] = dict(pointer=ref, report=report)
            save_key(event, ref, "FIRST_COVARIANCE_ANOMALY")
        db.execute("INSERT INTO covariance VALUES(?,?,?)", (event["event_seq"], event["event"], js(dict(pointer=ref, report=report))))

    def finish_imu():
        nonlocal imu
        if imu is None:
            return
        if imu.get("initialized"):
            if imu.get("state") is None:
                add_anomaly("IMU_END_STATE_MISSING", imu["opportunity_pointer"], "No PROPAGATION_AFTER/FEEDBACK_AFTER state")
            else:
                if finite(imu["state"].get("time")) is None or abs(float(imu["state"]["time"]) - imu["time"]) > 1e-9:
                    add_anomaly("IMU_END_STATE_TIME_MISMATCH", imu["state_pointer"], dict(state_time=imu["state"].get("time"), imu_time=imu["time"]))
                imu["end_boundary"] = "COVARIANCE_HEALTH" if imu.get("health_pointer") else "NEXT_IMU_INPUT_OR_OPPORTUNITY_OR_EOF"
                if candidate_id != "BASELINE" and not imu.get("health_pointer"):
                    add_anomaly("CANDIDATE_IMU_HEALTH_MISSING", imu["opportunity_pointer"], imu["imu_seq"])
                db.execute("INSERT INTO imu VALUES(?,?,?,?)", (js([imu["imu_seq"], imu["time"]]), imu["imu_seq"], imu["time"], js(imu)))
        imu = None

    def finish_attempt():
        nonlocal attempt, sa_begin, ekf_before
        if attempt is None:
            return
        if "decision" not in attempt:
            add_anomaly("MEASUREMENT_DECISION_MISSING", attempt["attempt_pointer"], attempt["source"])
            attempt["decision"] = {"accepted": None, "reason": "MISSING_DECISION"}
        ekf = attempt.get("ekf", {})
        accepted = attempt["decision"].get("accepted")
        if accepted is not None and bool(accepted) != bool(ekf.get("after_pointer")):
            add_anomaly("ACCEPTANCE_EKF_DISAGREEMENT", attempt.get("decision_pointer", attempt["attempt_pointer"]), accepted)
        if attempt.get("sa") and ekf:
            a, b = attempt["sa"].get("sa_effective_R"), ekf.get("R")
            attempt["sa_effective_R_equals_actual_EKF_R"] = a == b
            if a != b:
                add_anomaly("SA_EFFECTIVE_R_TO_ACTUAL_R_MISMATCH", ekf["before_pointer"], "actual R taken only from EKF_BEFORE")
        stats = source_stats.setdefault(attempt["source"], dict(attempts=0, actual_accepted=0, actual_EKF_updates=0,
                    SA_evaluations=0, SA_active_evaluations=0, policy_accepted=0, observed_numeric_ranges={}))
        stats["attempts"] += 1
        stats["actual_accepted"] += int(accepted is True)
        stats["actual_EKF_updates"] += int(bool(ekf.get("after_pointer")))
        if "sa" in attempt:
            sa = attempt["sa"]
            stats["SA_evaluations"] += 1
            stats["SA_active_evaluations"] += int(sa.get("source_enabled") is True)
            stats["policy_accepted"] += int(sa.get("recorded_result", {}).get("accepted") is True)
            vals = {k: sa.get(k) for k in ("raw_nis", "conditional_nis", "recomputed_actual_nis")}
            vals.update({k: sa.get("recorded_result", {}).get(k) for k in ("lsim_R_scale", "oim_R_scale", "combined_R_scale")})
            for name, value in vals.items():
                number = finite(value)
                if number is not None:
                    rng = stats["observed_numeric_ranges"].setdefault(name, dict(finite_count=0, min=number, max=number))
                    rng["finite_count"] += 1
                    rng["min"], rng["max"] = min(rng["min"], number), max(rng["max"], number)
        for scope in time_windows(attempt["measurement_time"]):
            window_counts[(scope, attempt["source"], "attempt")] += 1
            window_counts[(scope, attempt["source"], "accepted")] += int(accepted is True)
            window_counts[(scope, attempt["source"], "not_accepted")] += int(accepted is False)
            window_counts[(scope, attempt["source"], "actual_EKF_update")] += int(bool(ekf.get("after_pointer")))
            window_counts[(scope, attempt["source"], "SA_evaluation")] += int("sa" in attempt)
        key = js([attempt["gnss_input_seq"], attempt["source"], attempt["measurement_time"]])
        db.execute("INSERT INTO measurement VALUES(?,?,?,?)", (key, attempt["attempt"], attempt["attempt_pointer"]["event_seq"], js(attempt)))
        attempt, sa_begin, ekf_before = None, None, None

    stream_error = None
    physical_eof_reached = False
    payload_open_attempts = 0
    payload_opened = False
    try:
        payload_open_attempts = 1
        with source.open("rb") as f:
            payload_opened = True
            for line in f:
                offset = total_bytes
                total_bytes += len(line)
                digest.update(line)
                if end_seen:
                    raise ValueError("DATA_AFTER_OBSERVER_END")
                if not line.endswith(b"\n"):
                    raise ValueError("INCOMPLETE_JSONL_LAST_LINE")
                event = json.loads(line)
                seq, kind = event["event_seq"], event["event"]
                if seq != last_seq + 1 or event["run_id"] != run_id:
                    raise ValueError("EVENT_SEQUENCE_OR_RUN_ID_MISMATCH")
                last_seq = seq
                counts[kind] += 1
                ref = pointer(event, source_alias, offset, len(line))
                if kind == "OBSERVER_BEGIN":
                    if begin_seen or seq != 1 or event["data"].get("schema") != "V3_MECHANISM_OBSERVER_1":
                        raise ValueError("INVALID_BEGIN")
                    begin_seen = True
                    continue
                if not begin_seen:
                    raise ValueError("MISSING_BEGIN")
                if kind == "OBSERVER_END":
                    if event["data"].get("prior_event_count") != seq - 1:
                        raise ValueError("END_PRIOR_COUNT_MISMATCH")
                    finish_attempt()
                    finish_imu()
                    end_seen = True
                    continue
                c, s = event["data"]["context"], event["data"]["snapshot"]
                last_context = c
                for name in COUNTERS:
                    if name in c:
                        if not isinstance(c[name], int) or c[name] < previous_counters.get(name, 0):
                            raise ValueError("NONMONOTONE_OR_INVALID_ACTUAL_COUNTER:" + name)
                        previous_counters[name] = c[name]
                index.writerow(dict(event_seq=seq, event=kind, source=c.get("source"), imu_seq=c.get("imu_seq"),
                                    gnss_input_seq=c.get("gnss_input_seq"), measurement_attempt_seq=c.get("measurement_attempt_seq"),
                                    measurement_time=c.get("measurement_time"), byte_offset=offset, byte_length=len(line)))
                if kind == "CONFIGURATION":
                    if config is not None:
                        raise ValueError("DUPLICATE_CONFIGURATION")
                    config = s
                if kind == "CANDIDATE_DEFINITION":
                    if candidate_id == "BASELINE" or s.get("candidate_id") != candidate_id:
                        raise ValueError("CANDIDATE_DEFINITION_IDENTITY_MISMATCH")
                    db.execute("INSERT INTO special VALUES(?,?,?)", (seq, kind, js(dict(pointer=ref, context=c, snapshot=s))))
                if kind == "IMU_INPUT":
                    finish_imu()
                if kind == "IMU_OPPORTUNITY":
                    finish_imu()
                    imu = dict(imu_seq=c["imu_seq"], time=c["imu_current_time"], initialized=s["initialized"],
                               opportunity_pointer=ref, res=s.get("res", c.get("res")), state=None,
                               propagation_count=0, feedback_count=0, split_count=0)
                if imu is not None and c.get("imu_seq") == imu["imu_seq"]:
                    imu["counters"] = {k: c[k] for k in COUNTERS if k in c}
                    if kind in ("PROPAGATION_AFTER", "FEEDBACK_AFTER"):
                        imu["state"], imu["state_pointer"] = s["state"], ref
                    for event_kind, field in (("PROPAGATION_AFTER", "propagation_count"), ("FEEDBACK_AFTER", "feedback_count"), ("IMU_SPLIT_AFTER", "split_count")):
                        if kind == event_kind:
                            imu[field] += 1
                    if kind == "COVARIANCE_HEALTH":
                        if imu.get("health_pointer"):
                            raise ValueError("DUPLICATE_IMU_HEALTH")
                        imu["health_pointer"] = ref
                if kind == "GNSS_INPUT":
                    effective = s["effective"]
                    all_invalid = not any(effective.get(k) for k in ("has_position", "has_velocity", "has_yaw"))
                    db.execute("INSERT INTO gnss VALUES(?,?,?)", (c["gnss_input_seq"], effective["time"], js(dict(pointer=ref,
                        gnss_input_seq=c["gnss_input_seq"], measurement_time=effective["time"], all_flags_false=all_invalid,
                        rp_preinnovation_qualified=rp_qualification(s), snapshot=s))))
                if kind.startswith("RP_ONLY_"):
                    db.execute("INSERT INTO special VALUES(?,?,?)", (seq, kind, js(dict(pointer=ref, context=c, snapshot=s))))
                    for scope in time_windows(s.get("gnss_event_time")):
                        window_counts[(scope, "RP_ONLY_SCHEDULER", kind)] += 1
                if kind == "MEASUREMENT_ATTEMPT":
                    if attempt is not None:
                        finish_attempt()
                    attempt = dict(attempt=c["measurement_attempt_seq"], gnss_input_seq=c["gnss_input_seq"],
                                   source=c["source"], measurement_time=c["measurement_time"], imu_seq=c["imu_seq"],
                                   attempt_pointer=ref, counters_before={k: c[k] for k in COUNTERS if k in c})
                if kind in ("SA_EVALUATION_BEGIN", "SA_EVALUATION", "EKF_BEFORE", "EKF_AFTER", "MEASUREMENT_DECISION", "MEASUREMENT_SELECTED"):
                    if attempt is None or attempt["attempt"] != c["measurement_attempt_seq"] or attempt["source"] != c["source"]:
                        raise ValueError("MEASUREMENT_EVENT_OUTSIDE_CURRENT_ATTEMPT")
                if kind == "MEASUREMENT_SELECTED":
                    attempt.update(selected_row_id=c["row_id"], selected_pointer=ref, selected_input=s)
                if kind == "SA_EVALUATION_BEGIN":
                    if sa_begin is not None:
                        raise ValueError("DUPLICATE_SA_BEGIN_IN_ATTEMPT")
                    sa_begin = s
                    attempt["sa_begin_pointer"] = ref
                if kind == "SA_EVALUATION":
                    if config is None:
                        raise ValueError("SA_WITHOUT_CONFIGURATION")
                    if "sa" in attempt or s["metadata"]["source"] != attempt["source"]:
                        raise ValueError("SA_SOURCE_OR_MULTIPLICITY_MISMATCH")
                    attempt["sa"] = analyze_sa(s, sa_begin, candidate_id, config)
                    attempt["sa_pointer"] = ref
                    sa_status[attempt["sa"]["validation_status"]] += 1
                    save_key(event, ref, "FIRST_SA_BY_SOURCE")
                    if attempt["sa"]["validation_status"] != "VALIDATED":
                        save_key(event, ref, "FIRST_SA_VALIDATION_PROBLEM")
                if kind == "EKF_BEFORE":
                    if "ekf" in attempt:
                        raise ValueError("DUPLICATE_EKF_IN_MEASUREMENT_ATTEMPT")
                    ekf_before = s
                    attempt["ekf"] = dict(before_pointer=ref, R=s["R"], dz=s["dz"], H=s["H"],
                                           dx_before=s["dx_before"], state_before=s["state"])
                    if candidate_id == "BASELINE":
                        add_cov(covariance_health(matrix(s["P_before"])), event, ref)
                if kind == "EKF_AFTER":
                    if ekf_before is None or "after_pointer" in attempt["ekf"]:
                        raise ValueError("EKF_AFTER_PAIR_ERROR")
                    e = attempt["ekf"]
                    e.update(after_pointer=ref, actual_innovation=s["actual_innovation"], actual_Hdx=s["actual_Hdx"],
                             actual_delta=s["actual_delta"], dx_after=s["dx_after"], state_after=s["state"])
                    checks = {}
                    try:
                        hdx = matrix(ekf_before["H"]) @ np.asarray(ekf_before["dx_before"], dtype=float)
                        nu = np.asarray(ekf_before["dz"], dtype=float) - hdx
                        checks["actual_nu"] = len(nu) == len(s["actual_innovation"]) and all(scalar_close(a, b, True) for a, b in zip(nu, s["actual_innovation"]))
                        checks["actual_Hdx"] = len(hdx) == len(s["actual_Hdx"]) and all(scalar_close(a, b, True) for a, b in zip(hdx, s["actual_Hdx"]))
                        inv = inverse_frozen(matrix(s["actual_S"]))
                        e["post_R_actual_nis"] = max(0.0, float(nu @ inv @ nu))
                    except (ValueError, KeyError, TypeError) as exc:
                        checks["available"] = False
                        e["validation_unavailable_reason"] = str(exc)
                    e["checks"] = checks
                    if not all(checks.values()):
                        add_anomaly("EKF_NUMERIC_VALIDATION_FAILED", ref, checks)
                    if candidate_id == "BASELINE":
                        add_cov(covariance_health(matrix(s["P_after"])), event, ref)
                    save_key(event, ref, "FIRST_EKF_AFTER_BY_SOURCE")
                if kind == "MEASUREMENT_DECISION":
                    attempt.update(decision=s, decision_pointer=ref, counters_after={k: c[k] for k in COUNTERS if k in c})
                    finish_attempt()
                if kind == "COVARIANCE_HEALTH":
                    if candidate_id == "BASELINE":
                        raise ValueError("BASELINE_UNEXPECTED_NEW_COVARIANCE_HOOK")
                    required = s.get("dimension") == 21 and s.get("filter_matrix_modified") is False and s.get("jitter_or_clipping") is False and s.get("pivot_threshold") == PIVOT_TOL
                    if not required:
                        add_anomaly("COVARIANCE_DIAGNOSTIC_CONTRACT", ref, s)
                    add_cov(s, event, ref)
                if seq % 10000 == 0:
                    db.commit()
            physical_eof_reached = True
        if not end_seen:
            raise ValueError("MISSING_OBSERVER_END")
        if config is None:
            raise ValueError("MISSING_CONFIGURATION")
        if candidate_id != "BASELINE" and counts["CANDIDATE_DEFINITION"] != 1:
            raise ValueError("MISSING_OR_DUPLICATE_CANDIDATE_DEFINITION")
        if file_stat(source) != before or total_bytes != before["st_size"]:
            raise ValueError("SOURCE_CHANGED_DURING_SINGLE_SCAN")
    except Exception as exc:
        stream_error = type(exc).__name__ + ":" + str(exc)
    finally:
        db.commit()
        index_file.close()
        key_file.close()
    duplicates = [dict(r) for r in db.execute("SELECT stable_key,COUNT(*) AS n FROM measurement GROUP BY stable_key HAVING COUNT(*)>1")]
    if duplicates:
        anomalies.append(dict(kind="AMBIGUOUS_STABLE_MEASUREMENT_KEYS", keys=duplicates))
    source_counter = {"receiver_position": "position_update_count", "receiver_velocity": "velocity_update_count",
                      "raw_doppler_velocity": "raw_doppler_update_count", "go2_attitude_roll_pitch": "rp_update_count",
                      "go2_horizontal_velocity": "hv_update_count"}
    for name, counter in source_counter.items():
        actual = source_stats.get(name, {}).get("actual_EKF_updates", 0)
        if counter in last_context and actual != last_context[counter]:
            anomalies.append(dict(kind="ACTUAL_UPDATE_COUNTER_MISMATCH", source=name, counted_EKF=actual,
                                  final_recorded_counter=last_context[counter], field=counter))
    try:
        after = file_stat(source)
    except OSError:
        after = {"status": "UNAVAILABLE_AFTER_READ"}
    complete_stable_read = physical_eof_reached and total_bytes == before["st_size"] and before == after
    summary = dict(schema=SCHEMA, source_path=source_alias, source_stat=before,
                   source_stat_after=after, source_sha256=digest.hexdigest() if complete_stable_read else None,
                   bytes_read_sha256=digest.hexdigest(), hash_scope="FULL_STABLE_FILE" if complete_stable_read else "PARTIAL_OR_UNSTABLE_READ_BYTES_ONLY",
                   analyzer_sha256=code_sha,
                   run_id=run_id, candidate_id=candidate_id, group=group, identity_gate=identity,
                   stream_status="COMPLETE" if stream_error is None else "INCOMPLETE_OR_INVALID",
                   stream_error=stream_error, events_read=last_seq, bytes_read=total_bytes,
                   complete_payload_scan_count=int(complete_stable_read), event_payload_opens_this_call=int(payload_opened),
                   payload_open_attempts_this_call=payload_open_attempts, physical_eof_reached=physical_eof_reached,
                   complete_valid_stream=stream_error is None and end_seen, cache_reused=False,
                   numpy_version=np.__version__, numeric_library_threads=1,
                   data_mode=data_mode or ("synthetic_fixture_only" if group == "SYNTHETIC" else "UNKNOWN_NOT_PROVIDED"),
                   synthetic_data_used=group == "SYNTHETIC", semisynthetic_data_used=data_mode == "semisynthetic",
                   elapsed_seconds=time.time() - started, event_counts=dict(counts), sa_validation_counts=dict(sa_status),
                   covariance=cov_summary, diagnostic_anomalies=anomalies, final_actual_counters={k: last_context.get(k) for k in COUNTERS},
                   configuration=config, matching_rule="gnss_input_seq/source/exact_measurement_time; duplicates unresolved",
                   source_summaries=source_stats,
                   imu_comparison="same imu_seq and actual current IMU time; last propagation/feedback state; no interpolation",
                   acceptance_rule="MEASUREMENT_DECISION plus completed EKF_AFTER; SA accepted is policy acceptance only",
                   actual_R_rule="EKF_BEFORE.R only", raw_provider_reference_reads=0,
                   new_native_calls=0, evaluator_calls=0, provider_calls=0,
                   numeric_tolerances=dict(nis_abs=NIS_ABS, nis_rel=NIS_REL, R_abs=R_ABS, R_rel=R_REL,
                                           covariance_symmetry_rel=SYMMETRY_REL, covariance_pivot=PIVOT_TOL))
    summary["analysis_status"] = ("STREAM_INVALID" if stream_error else "VALIDATION_FAILED" if anomalies or sa_status["VALIDATION_FAILED"] or sa_status["UNAVAILABLE"] else "VALIDATED")
    rows = [dict(window=w, source=s, measure=m, count=n, time_axis="measurement_time_or_RP_gnss_event_time")
            for (w, s, m), n in sorted(window_counts.items())]
    summary["update_counts_by_window"] = rows
    write_csv(output / "UPDATE_COUNTS.csv", rows, ["window", "source", "measure", "count", "time_axis"])
    write_json(output / "SCAN_RECEIPT.json", summary)
    export_cache_csv(db, output)
    db.close()
    summary["cache_stat"] = file_stat(output / "cache.sqlite")
    write_json(output / "SCAN_RECEIPT.json", summary)
    return summary


def write_csv(path, rows, fields):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        w.writeheader()
        for row in rows:
            w.writerow({k: js(v) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})


def export_cache_csv(db, output):
    def measurement_rows():
        for r in db.execute("SELECT * FROM measurement ORDER BY event_seq"):
            d = json.loads(r["data"])
            yield dict(stable_key=r["stable_key"], attempt=r["attempt"], event_seq=r["event_seq"], source=d["source"],
                       gnss_input_seq=d["gnss_input_seq"], measurement_time=d["measurement_time"],
                       actual_accepted=d["decision"]["accepted"], actual_EKF_update=bool(d.get("ekf", {}).get("after_pointer")),
                       sa_validation=d.get("sa", {}).get("validation_status", "NO_SA_CALL"), record=d)
    write_csv(output / "MEASUREMENTS.csv", measurement_rows(), ["stable_key", "attempt", "event_seq", "source", "gnss_input_seq", "measurement_time", "actual_accepted", "actual_EKF_update", "sa_validation", "record"])
    write_csv(output / "RP_ONLY_EVENTS.csv", (dict(event_seq=r["event_seq"], event=r["event"], record=json.loads(r["data"]))
        for r in db.execute("SELECT * FROM special WHERE event LIKE 'RP_ONLY_%' ORDER BY event_seq")), ["event_seq", "event", "record"])


def read_cache(path, expected=None):
    receipt = json.loads((path / "SCAN_RECEIPT.json").read_text())
    if receipt.get("schema") != SCHEMA or receipt.get("analyzer_sha256") != sha(Path(__file__)):
        raise ValueError("CACHE_SCHEMA_OR_ANALYZER_PIN_MISMATCH")
    if expected is not None and any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError("CACHE_REGISTERED_OBJECT_IDENTITY_MISMATCH")
    if receipt["stream_status"] != "COMPLETE":
        raise ValueError("CANNOT_COMPARE_INCOMPLETE_STREAM")
    if receipt.get("cache_stat") != file_stat(path / "cache.sqlite"):
        raise ValueError("CACHE_DATABASE_CHANGED")
    return open_db(path / "cache.sqlite", True), receipt


def compare_caches(candidate, baseline, output, *, expected_candidate=None, expected_baseline=None):
    output = Path(output)
    forbid_symlinks(output)
    cdb, cs = read_cache(Path(candidate), expected_candidate)
    bdb, bs = read_cache(Path(baseline), expected_baseline)
    if cs["candidate_id"] not in {"N12_ONLY", "N16_ONLY", "N09_RP_ONLY"} or bs["candidate_id"] != "BASELINE":
        raise ValueError("CACHE_COMPARISON_SIDE_IDENTITY_MISMATCH")
    if cs.get("data_mode") != "synthetic_fixture_only" and cs["run_id"] != cs["candidate_id"] + "__" + bs["run_id"]:
        raise ValueError("CACHE_CANDIDATE_BASELINE_RUN_ID_MISMATCH")
    output.mkdir(parents=True, exist_ok=False)
    first, counts, snapshots = {}, collections.Counter(), []

    def retain_first(category, record):
        if category not in first:
            first[category] = record
            for side in ("candidate", "baseline"):
                d = record.get(side)
                if d:
                    pointers = {k: v for k, v in d.items() if k.endswith("pointer")}
                    if d.get("ekf"):
                        pointers.update({"ekf_" + k: v for k, v in d["ekf"].items() if k.endswith("pointer")})
                    snapshots.append(dict(category=category, side=side, pointers=pointers))

    def comparisons():
        for row in cdb.execute("SELECT * FROM measurement ORDER BY event_seq"):
            cd = json.loads(row["data"])
            matches = list(bdb.execute("SELECT * FROM measurement WHERE stable_key=?", (row["stable_key"],)))
            self_count = cdb.execute("SELECT COUNT(*) FROM measurement WHERE stable_key=?", (row["stable_key"],)).fetchone()[0]
            rec = dict(stable_key=row["stable_key"], candidate=cd, baseline=None, status="ADDED_CANDIDATE_MEASUREMENT", differences={})
            if len(matches) > 1 or self_count > 1:
                rec["status"] = "AMBIGUOUS_DUPLICATE_KEY"
            elif not matches:
                retain_first("FIRST_ADDED_MEASUREMENT", rec)
                if cd["decision"].get("accepted"):
                    retain_first("FIRST_ADDED_ACCEPTED_UPDATE", rec)
            else:
                bd = json.loads(matches[0]["data"])
                rec.update(baseline=bd, status="PAIRED")
                dif = rec["differences"]
                if cd["decision"].get("accepted") != bd["decision"].get("accepted"):
                    dif["actual_acceptance"] = dict(candidate=cd["decision"], baseline=bd["decision"])
                    retain_first("FIRST_ACTUAL_ACCEPTANCE_DIFFERENCE", rec)
                ce, be = cd.get("ekf"), bd.get("ekf")
                if bool(ce) != bool(be):
                    dif["actual_EKF_presence"] = dict(candidate=bool(ce), baseline=bool(be))
                    retain_first("FIRST_ACTUAL_UPDATE_PRESENCE_DIFFERENCE", rec)
                if ce and be:
                    if ce["R"] != be["R"]:
                        d = vector_diff(matrix(ce["R"]), matrix(be["R"]))
                        d["within_fixed_R_tolerance"] = all(scalar_close(a, b) for a, b in zip(matrix(ce["R"]).ravel(), matrix(be["R"]).ravel())) if matrix(ce["R"]).shape == matrix(be["R"]).shape else False
                        dif["actual_R"] = d
                        retain_first("FIRST_ACTUAL_R_EXACT_DIFFERENCE", rec)
                        if not d["within_fixed_R_tolerance"]:
                            retain_first("FIRST_ACTUAL_R_ABOVE_FIXED_TOLERANCE", rec)
                    for field in ("dx_before", "actual_delta", "dx_after", "actual_innovation"):
                        d = vector_diff(ce[field], be[field])
                        if d["status"] != "EXACTLY_EQUAL":
                            dif[field] = d
                            retain_first("FIRST_" + field.upper() + "_DIFFERENCE", rec)
                    if ce["state_before"] != be["state_before"]:
                        dif["state_before"] = dict(same_recorded_state_time=ce["state_before"].get("time") == be["state_before"].get("time"), fields=state_diff(ce["state_before"], be["state_before"]))
                        retain_first("FIRST_MATCHED_UPDATE_STATE_DIFFERENCE", rec)
                if cd.get("sa") and bd.get("sa"):
                    dif["recorded_SA_summary"] = {side: {k: d["sa"].get(k) for k in ("expected_basis", "raw_nis", "conditional_nis", "recorded_innovation", "recorded_result", "source_enabled")} for side, d in (("candidate", cd), ("baseline", bd))}
            counts[rec["status"]] += 1
            yield dict(stable_key=rec["stable_key"], status=rec["status"], candidate_event=cd["attempt_pointer"]["event_seq"],
                       baseline_event=rec["baseline"]["attempt_pointer"]["event_seq"] if rec["baseline"] else "",
                       source=cd["source"], gnss_input_seq=cd["gnss_input_seq"], measurement_time=cd["measurement_time"], record=rec)
        for row in bdb.execute("SELECT * FROM measurement ORDER BY event_seq"):
            if cdb.execute("SELECT COUNT(*) FROM measurement WHERE stable_key=?", (row["stable_key"],)).fetchone()[0] == 0:
                bd = json.loads(row["data"])
                counts["BASELINE_MEASUREMENT_ABSENT_IN_CANDIDATE"] += 1
                yield dict(stable_key=row["stable_key"], status="BASELINE_MEASUREMENT_ABSENT_IN_CANDIDATE", candidate_event="", baseline_event=row["event_seq"],
                           source=bd["source"], gnss_input_seq=bd["gnss_input_seq"], measurement_time=bd["measurement_time"], record=dict(baseline=bd, candidate=None))
    write_csv(output / "MEASUREMENT_COMPARISON.csv", comparisons(), ["stable_key", "status", "candidate_event", "baseline_event", "source", "gnss_input_seq", "measurement_time", "record"])
    first_added = first.get("FIRST_ADDED_ACCEPTED_UPDATE", {}).get("candidate")
    first_added_attempt = first.get("FIRST_ADDED_MEASUREMENT", {}).get("candidate")
    imu_counts = collections.Counter()

    def imu_rows():
        for row in cdb.execute("SELECT * FROM imu ORDER BY imu_seq"):
            cd = json.loads(row["data"])
            br = bdb.execute("SELECT data FROM imu WHERE imu_key=?", (row["imu_key"],)).fetchone()
            if br is None:
                imu_counts["NO_EXACT_COMMON_IMU_KEY"] += 1
                yield dict(imu_seq=cd["imu_seq"], time=cd["time"], status="NO_EXACT_COMMON_IMU_KEY", details={"candidate": cd})
                continue
            bd = json.loads(br["data"])
            fields = state_diff(cd["state"], bd["state"])
            status = "EXACTLY_EQUAL" if all(v["status"] == "EXACTLY_EQUAL" for v in fields.values()) else "DIFFERENT_OR_UNRESOLVED"
            imu_counts[status] += 1
            details = dict(candidate=cd, baseline=bd, state_delta=fields, same_recorded_state_time=cd["state"]["time"] == bd["state"]["time"],
                           propagation_counts=dict(candidate=cd["propagation_count"], baseline=bd["propagation_count"]),
                           split_counts=dict(candidate=cd["split_count"], baseline=bd["split_count"]),
                           feedback_counts=dict(candidate=cd["feedback_count"], baseline=bd["feedback_count"]))
            if status != "EXACTLY_EQUAL":
                retain_first("FIRST_COMMON_IMU_END_STATE_DIFFERENCE", details)
            if first_added and cd["imu_seq"] >= first_added["imu_seq"]:
                retain_first("FIRST_COMMON_IMU_AFTER_ADDED_ACCEPTED_UPDATE", details)
                if status != "EXACTLY_EQUAL":
                    retain_first("FIRST_COMMON_IMU_DIFFERENCE_AFTER_ADDED_UPDATE", details)
            if first_added_attempt and cd["imu_seq"] >= first_added_attempt["imu_seq"]:
                retain_first("FIRST_COMMON_IMU_AFTER_ADDED_ATTEMPT", details)
                if status != "EXACTLY_EQUAL":
                    retain_first("FIRST_COMMON_IMU_DIFFERENCE_AFTER_ADDED_ATTEMPT", details)
            yield dict(imu_seq=cd["imu_seq"], time=cd["time"], status=status, details=details)
    write_csv(output / "IMU_STATE_COMPARISON.csv", imu_rows(), ["imu_seq", "time", "status", "details"])
    rp_counts = collections.Counter()

    def rp_rows():
        for row in bdb.execute("SELECT * FROM gnss ORDER BY gnss_seq"):
            b = json.loads(row["data"])
            if not b["all_flags_false"] or not b["rp_preinnovation_qualified"]:
                continue
            matched = []
            for cr in cdb.execute("SELECT data FROM measurement WHERE stable_key=?", (js([row["gnss_seq"], "go2_attitude_roll_pitch", row["time"]]),)):
                matched.append(json.loads(cr["data"]))
            actual = [d for d in matched if d["decision"].get("accepted") and d.get("ekf", {}).get("after_pointer")]
            for window in time_windows(row["time"]):
                rp_counts[(window, "baseline_invalid_prequalified_GNSS_inputs")] += 1
                rp_counts[(window, "candidate_actual_accepted_GNSS_inputs")] += int(bool(actual))
                rp_counts[(window, "candidate_RP_attempts")] += len(matched)
            yield dict(gnss_input_seq=row["gnss_seq"], measurement_time=row["time"], candidate_RP_attempts=len(matched),
                       actual_accepted_updates=len(actual), baseline_pointer=b["pointer"], candidate_records=matched,
                       qualification_is_not_acceptance=True)
    write_csv(output / "ORIGINAL_RP_OPPORTUNITIES.csv", rp_rows(), ["gnss_input_seq", "measurement_time", "candidate_RP_attempts", "actual_accepted_updates", "baseline_pointer", "candidate_records", "qualification_is_not_acceptance"])
    summary = dict(schema=SCHEMA, candidate_run_id=cs["run_id"], baseline_run_id=bs["run_id"], candidate_id=cs["candidate_id"],
                   candidate_source=cs["source_path"], baseline_source=bs["source_path"],
                   candidate_sha256=cs["source_sha256"], baseline_sha256=bs["source_sha256"],
                   candidate_analysis_status=cs["analysis_status"], baseline_analysis_status=bs["analysis_status"],
                   analysis_status="VALIDATED" if cs["analysis_status"] == bs["analysis_status"] == "VALIDATED" and not counts["AMBIGUOUS_DUPLICATE_KEY"] else "REVIEW_REQUIRED",
                   measurement_counts=dict(counts), common_IMU_counts=dict(imu_counts), first_differences=first,
                   original_RP_opportunities=[dict(window=w, measure=m, count=n) for (w, m), n in sorted(rp_counts.items())],
                   raw_event_payload_opens_this_comparison=0, native_calls=0, evaluator_calls=0,
                   covariance_coverage=dict(candidate=cs["covariance"], baseline=bs["covariance"]),
                   data_mode=cs.get("data_mode", "UNKNOWN"), synthetic_data_used=cs.get("synthetic_data_used"),
                   semisynthetic_data_used=cs.get("semisynthetic_data_used"),
                   source_summaries=dict(candidate=cs.get("source_summaries"), baseline=bs.get("source_summaries")),
                   update_counts_by_window=dict(candidate=cs.get("update_counts_by_window"), baseline=bs.get("update_counts_by_window")),
                   actual_final_counters=dict(candidate=cs["final_actual_counters"], baseline=bs["final_actual_counters"]),
                   NAV_comparison="NOT_REQUESTED_SEPARATE_PAYLOAD_NO_INFERRED_NAV_RESULT",
                   limits=["Actual R means EKF_BEFORE.R; policy acceptance is separate.",
                           "Added update has no baseline intermediate state. No interpolation or global event-seq pairing.",
                           "N09 res3 may split propagation even if RP is rejected; split and feedback counts remain separate.",
                           "State differences are exact binary64 diagnostics, not error against a reference.",
                           "Covariance failures are numeric diagnostics, not a proof of strict indefiniteness."])
    write_json(output / "SUMMARY.json", summary)
    write_csv(output / "FIRST_DIVERGENCE_SNAPSHOT_INDEX.csv", snapshots, ["category", "side", "pointers"])
    cdb.close()
    bdb.close()
    return summary


def resolve(value, aliases):
    for alias in sorted(aliases, key=len, reverse=True):
        if value == alias or value.startswith(alias + "/"):
            base = Path(aliases[alias]).resolve()
            tail = value[len(alias):].lstrip("/")
            path = base / tail
            forbid_symlinks(path)
            if not path.resolve().is_relative_to(base):
                raise ValueError("ALIAS_ESCAPE")
            return path
    raise ValueError("UNREGISTERED_ALIAS")


def exactly_one_native(value):
    """Receipts historically use both 1 and '1'; bool/float/UNKNOWN are not counts."""
    return (type(value) is int and value == 1) or (type(value) is str and value == "1")


def baseline_gate(out, run_id):
    receipt = json.loads((out / "REPLAY_RECEIPT.json").read_text())
    access = json.loads((out / "ACCESS_REVIEW.json").read_text())
    required = dict(slot=receipt.get("slot_id") == run_id + "__observed", status=receipt.get("status") == "COMPLETED_BYTE_IDENTICAL",
                    access=receipt.get("access_passed") is True and access.get("passed") is True,
                    manifest=receipt.get("scientific_manifest_match") is True, exit=receipt.get("exit_code") == 0,
                    native_count=exactly_one_native(receipt.get("native_exec_count")) and exactly_one_native(access.get("native_exec_count")),
                    identity=receipt.get("observer_identity_status") == "BYTE_IDENTICAL",
                    outputs=len(receipt.get("output_comparisons", [])) == 5 and all(x.get("status") == "BYTE_IDENTICAL" for x in receipt["output_comparisons"]))
    if not all(required.values()):
        raise ValueError("BASELINE_GATE:" + js(required))
    return dict(checks=required, receipt_sha256=sha(out / "REPLAY_RECEIPT.json"), access_sha256=sha(out / "ACCESS_REVIEW.json"))


def candidate_gate(out, item):
    receipt = json.loads((out / "CANDIDATE_RECEIPT.json").read_text())
    access = json.loads((out / "ACCESS_REVIEW.json").read_text())
    required = dict(slot=receipt.get("slot_id") == item["slot_id"], status=receipt.get("status") == "COMPLETED",
                    access=receipt.get("access_passed") is True and access.get("passed") is True,
                    native_count=exactly_one_native(receipt.get("native_exec_count")) and exactly_one_native(access.get("native_exec_count")),
                    exit=receipt.get("exit_code") == 0, config=receipt.get("config_sha256") == item["original_config_sha256"],
                    outputs=len(receipt.get("output_hashes", [])) == 5 and all(x.get("candidate_sha256") for x in receipt["output_hashes"]))
    if not all(required.values()):
        raise ValueError("CANDIDATE_GATE:" + js(required))
    return dict(checks=required, receipt_sha256=sha(out / "CANDIDATE_RECEIPT.json"), access_sha256=sha(out / "ACCESS_REVIEW.json"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["scan", "compare"])
    p.add_argument("--roots", type=Path, required=True)
    p.add_argument("--candidate-id", choices=["N12_ONLY", "N16_ONLY", "N09_RP_ONLY"], required=True)
    p.add_argument("--run-id", required=True)
    args = p.parse_args(argv)
    aliases = json.loads(args.roots.read_text())["aliases"]
    with (BASE / "CANDIDATE_QUEUE.csv").open(newline="") as f:
        queue = list(csv.DictReader(f))
    choices = [x for x in queue if x["candidate_id"] == args.candidate_id and x["baseline_run_id"] == args.run_id]
    if len(choices) != 1:
        raise ValueError("EXACTLY_ONE_REGISTERED_SLOT_REQUIRED")
    item = choices[0]
    cache_root = resolve("<VALIDATION_ROOT>/analysis/event_cache", aliases)
    baseline_cache = cache_root / ("BASELINE__" + args.run_id)
    candidate_cache = cache_root / item["slot_id"]
    if args.command == "scan":
        candidate_out = resolve(item["candidate_outputs"], aliases)
        baseline_source = resolve(item["baseline_events"], aliases)
        # Both admission gates precede any potentially large event read.
        ci, bi = candidate_gate(candidate_out, item), baseline_gate(baseline_source.parent.parent, args.run_id)
        b = scan_stream(baseline_source, baseline_cache, source_alias=item["baseline_events"], run_id=args.run_id,
                        group=item["group"], identity=bi, data_mode=item["data_mode"])
        c = scan_stream(candidate_out / "observer/events.jsonl", candidate_cache, source_alias=item["candidate_outputs"] + "/observer/events.jsonl",
                        run_id=item["slot_id"], candidate_id=args.candidate_id, group=item["group"], identity=ci, data_mode=item["data_mode"])
        print(js(dict(baseline_status=b["analysis_status"], candidate_status=c["analysis_status"], baseline_cache_reused=b["cache_reused"],
                      baseline_payload_opens=b["event_payload_opens_this_call"], candidate_payload_opens=c["event_payload_opens_this_call"])))
        return 0 if b["analysis_status"] == c["analysis_status"] == "VALIDATED" else 2
    summary = compare_caches(candidate_cache, baseline_cache, resolve("<VALIDATION_ROOT>/analysis/comparisons/" + item["slot_id"], aliases),
        expected_candidate=dict(run_id=item["slot_id"], candidate_id=args.candidate_id, source_path=item["candidate_outputs"] + "/observer/events.jsonl"),
        expected_baseline=dict(run_id=args.run_id, candidate_id="BASELINE", source_path=item["baseline_events"]))
    public = HERE / "summaries" / item["slot_id"]
    public.mkdir(parents=True, exist_ok=False)
    # Only compact summary/offset index is public; detailed event rows stay external.
    compact = {k: v for k, v in summary.items() if k != "first_differences"}
    compact["first_difference_categories"] = list(summary["first_differences"])
    compact["complete_summary"] = "<VALIDATION_ROOT>/analysis/comparisons/" + item["slot_id"] + "/SUMMARY.json"
    write_json(public / "SUMMARY.json", compact)
    index_source = resolve("<VALIDATION_ROOT>/analysis/comparisons/" + item["slot_id"] + "/FIRST_DIVERGENCE_SNAPSHOT_INDEX.csv", aliases)
    (public / index_source.name).write_bytes(index_source.read_bytes())
    print(js(dict(status=summary["analysis_status"], measurement_counts=summary["measurement_counts"], common_IMU_counts=summary["common_IMU_counts"])))
    return 0 if summary["analysis_status"] == "VALIDATED" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(js(dict(status="STOPPED", error=type(exc).__name__ + ":" + str(exc))), file=sys.stderr)
        sys.exit(2)
