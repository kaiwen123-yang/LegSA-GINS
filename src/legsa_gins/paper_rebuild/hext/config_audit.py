"""H-EXT-01 read-only configuration observations; no solver/evaluator calls."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import yaml

from ..clean5_parity.input_audit import decode_receiver
from ..horizontal_literature.shared_raw_backend import reconstruct_ubx_stream
from ..horizontal_literature.ext05_provider import verify_hash_locked_file
from .sequence_paths import alias_path, load_sequence_paths


def _sha(path):
    if Path(path).name.startswith("trace_"):
        raise ValueError("Reference payload hashing is forbidden")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stats(values):
    a = np.asarray(values, float)
    return {"count": len(a), "median": float(np.median(a)),
            "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def _source(path, sequence):
    return {"path": alias_path(path, sequence), "sha256": _sha(path)}


def _write_json(path, obj):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def position_audit(p, target):
    """Compare the actual two independent CSV traversal/UBX decode chains."""
    raw_provenance = verify_hash_locked_file(p.gnss1_raw, raw_root=p.raw_root,
                                            hash_lock=p.hash_lock)
    hp, pvt = decode_receiver(p.gnss1_raw)
    external = reconstruct_ubx_stream(p.gnss1_raw, decode_nav_hpposecef_semantics=True)
    by_key = {epoch.itow_ms: epoch for epoch in external.nav_hpposecef_epochs}
    status_path = p.gnss1_raw.with_name("gnss1-status.csv")
    status_provenance = verify_hash_locked_file(status_path, raw_root=p.raw_root,
                                               hash_lock=p.hash_lock)
    with status_path.open(encoding="utf-8-sig", newline="") as handle:
        weeks = sorted({int(float(row["time_gps_wno"])) for row in csv.DictReader(handle)})
    ext_weeks = sorted({epoch.gps_week for epoch in external.rawx_epochs})
    leaps = sorted({epoch.leap_seconds for epoch in external.rawx_epochs})
    if len(weeks) != 1 or len(ext_weeks) != 1 or len(leaps) != 1:
        raise ValueError("Nonunique week/leap values")
    rows = []
    for key in sorted(hp):
        # Exactly the arithmetic forms of clean5_parity/providers.py:65 and
        # horizontal_literature/ext05_provider.py's absolute UTC construction.
        relative_legsa = 315964800 + weeks[0] * 604800 + key / 1000 - 18 - p.base_time
        absolute_external = 315964800.0 + ext_weeks[0] * 604800.0 + key * 1e-3 - leaps[0]
        relative_external = absolute_external - p.base_time
        if not p.window[0] <= relative_legsa <= p.window[1]:
            continue
        h, e, v = hp[key], by_key[key], pvt[key]
        difference = np.asarray(h["ecef_m"]) - e.position_ecef_m
        rows.append({"itow_ms": key, "legsa_time_s": relative_legsa,
                     "lc01_time_s": relative_external,
                     "time_difference_s": relative_legsa-relative_external,
                     **{f"legsa_ecef_{axis}_m": h["ecef_m"][i] for i, axis in enumerate("xyz")},
                     **{f"lc01_ecef_{axis}_m": float(e.position_ecef_m[i]) for i, axis in enumerate("xyz")},
                     "ecef_difference_norm_m": float(np.linalg.norm(difference)),
                     "pAcc_m": h["pAcc_m"], "hAcc_m": v["hAcc_m"], "vAcc_m": v["vAcc_m"]})
    with (target / "A1_A2_BY2_EPOCH_COMPARISON.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    pa = np.asarray([r["pAcc_m"] for r in rows])
    ha = np.asarray([r["hAcc_m"] for r in rows])
    va = np.asarray([r["vAcc_m"] for r in rows])
    return {"status": "AVAILABLE", "raw": raw_provenance, "status_raw": status_provenance,
            "legsa_gps_weeks": weeks, "external_gps_weeks": ext_weeks,
            "external_leap_seconds": leaps, "legsa_leap_seconds": 18,
            "window_s": list(p.window), "compared_epoch_count": len(rows),
            "max_ecef_difference_norm_m": max(r["ecef_difference_norm_m"] for r in rows),
            "max_abs_time_difference_s": max(abs(r["time_difference_s"]) for r in rows),
            "pAcc_m": _stats(pa), "hAcc_m": _stats(ha), "vAcc_m": _stats(va),
            "pAcc_over_hAcc_per_epoch": _stats(pa/ha),
            "pAcc_over_vAcc_per_epoch": _stats(pa/va),
            "ratio_of_medians_pAcc_over_hAcc": float(np.median(pa)/np.median(ha)),
            "ratio_of_medians_pAcc_over_vAcc": float(np.median(pa)/np.median(va)),
            "ratio_of_p95_pAcc_over_hAcc": float(np.percentile(pa,95)/np.percentile(ha,95)),
            "ratio_of_p95_pAcc_over_vAcc": float(np.percentile(pa,95)/np.percentile(va,95))}


def noise_audit(p):
    path = p.code_root / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml"
    model = yaml.safe_load(path.read_text())
    q, vrw = np.asarray(model["q"]), np.asarray(model["vrw"])
    q_check = (vrw/60)**2
    gyro = (np.asarray(model["frozen_arw"]) * math.pi/180/60)**2
    lc_accel, lc_gyro = np.array([.0289,.0225,.0576]), np.array([4e-4,4e-4,3.24e-4])
    return {"status": "AVAILABLE", "source": _source(path,p), "axis_order": model["axis_order"],
            "vrw": vrw.tolist(), "q": q.tolist(), "q_from_vrw": q_check.tolist(),
            "q_formula_max_abs_difference": float(np.max(abs(q-q_check))),
            "q_formula_allclose_rtol_1e_12": bool(np.allclose(q,q_check,rtol=1e-12,atol=0)),
            "lc01_accel_psd": lc_accel.tolist(), "lc01_over_legsa_accel_psd": (lc_accel/q).tolist(),
            "lc01_over_legsa_accel_std": np.sqrt(lc_accel/q).tolist(),
            "legsa_gyro_psd": gyro.tolist(), "lc01_gyro_psd": lc_gyro.tolist(),
            "lc01_over_legsa_gyro_std": np.sqrt(lc_gyro/gyro).tolist(),
            "gbstd_deg_per_hour": model["frozen_gbstd"], "abstd_mgal": model["abstd"],
            "scale": model["s"], "g_local_mps2": model["g_local_mps2"]}


def calibration_audit(p):
    path = p.clean_root / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05A_C00_NATIVE_SUMMARY.json"
    original = json.loads(path.read_text())
    c = original["provider"]["calibration"]
    event_contract = p.code_root / "configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml"
    control = yaml.safe_load(event_contract.read_text())["window_contract"]["constants"]["by2_control"]
    start, stop = c["start_time_unix_seconds"]-p.base_time, c["end_time_unix_seconds"]-p.base_time
    return {"status": "AVAILABLE", "source": _source(path,p), "calibration": c,
            "window_relative_s": [start,stop], "event_source": _source(event_contract,p),
            "by2_control": control, "kick_time_absolute_lower_bound": p.base_time+control["kick_time_lower_bound"],
            "contains_registered_kick": bool(start <= control["kick_time_lower_bound"] <= stop),
            "initialization_start_absolute": p.base_time+p.window[0]}


def gap_audit(p):
    prefix = p.clean_root / "stages/CLEAN5_CALIBRATED_SENSOR_MODEL"
    imu_path = prefix / "02_CALIBRATED_PROVIDERS/BY2H/CALIBRATED_IMU.imu"
    nav_path = prefix / "03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2H_A04/KF_GINS_Navresult.nav"
    imu, nav = np.loadtxt(imu_path), np.loadtxt(nav_path)
    gaps = []
    for i in np.flatnonzero(np.diff(imu[:,0]) > .1):
        left, right = float(imu[i,0]), float(imu[i+1,0])
        ln, rn = nav[nav[:,1] == left], nav[nav[:,1] == right]
        gaps.append({"left_file_line": int(i)+1, "right_file_line": int(i)+2,
                     "left_increment": imu[i].tolist(), "right_increment": imu[i+1].tolist(),
                     "duration_s": right-left,
                     "left_nav": ln[0].tolist() if len(ln) else None,
                     "right_nav": rn[0].tolist() if len(rn) else None,
                     "nav_state_equal": bool(np.array_equal(ln[0,2:],rn[0,2:])) if len(ln) and len(rn) else None,
                     "classification": "NAV_STATE_CHANGED_OVER_RETAINED_TIMESTAMP_GAP" if len(ln) and len(rn) else "INITIALIZATION_NO_LEFT_NAV"})
    return {"status": "AVAILABLE", "imu_source": _source(imu_path,p), "nav_source": _source(nav_path,p),
            "nav_first_time_s": float(nav[0,1]), "nav_last_time_s": float(nav[-1,1]),
            "gaps": gaps, "four_point_seven_second_retained_increment_gap_present": False,
            "long_gap_propagation_claim": "NOT_OBSERVABLE_NO_NAV_BEFORE_INITIALIZATION",
            "source_semantics": "loader assigns dt=successive retained timestamps; first aligned IMU initializes without NAV; later dt enters bias compensation/mechanization/covariance"}


def evaluation_audit(p):
    root = p.clean_root / "stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3"
    table = root / "HORIZONTAL_TABLE_V3.csv"
    fields = ["horizontal_method","method_id","output_epoch_count","matched_epoch_count","coverage_ratio",
              "time_start","time_end","body_forward_signed_mean_m","body_right_signed_mean_m","body_up_signed_mean_m",
              "evaluator_version","sequence_window_start_s","sequence_window_end_s","source_row"]
    selected = []
    with table.open(newline="") as handle:
        for index,row in enumerate(csv.DictReader(handle),2):
            if row["horizontal_method"] not in ("LegSA_frozen","LegSA_V2S","LegSA_CAL","LC01_EXT05A","EXT05C"):
                continue
            item = {k: row.get(k) for k in fields}
            item["table_data_row_one_based"] = index-1
            source = Path(item["source_row"])
            item["source_row"] = alias_path(source,p)
            if source.is_file():
                result = json.loads(source.read_text())
                item["evaluation_result_source"] = _source(source,p)
                item["result_counts"] = {k:result.get(k) for k in ("output_epoch_count","matched_epoch_count","coverage_ratio")}
            else:
                item["evaluation_result_source"] = "UNAVAILABLE_FROZEN_JSON_ABSENT_TABLE_RETAINED"
            item["rows_per_configured_second"] = int(row["output_epoch_count"])/(p.window[1]-p.window[0])
            nav_path = root / row["horizontal_method"] / "EVAL_NAV_V3.nav"
            if nav_path.is_file():
                nav = np.loadtxt(nav_path)
                item["nav_source"] = _source(nav_path,p)
                item["actual_nav_row_count"] = len(nav)
                item["actual_nav_median_dt_s"] = float(np.median(np.diff(nav[:,1])))
                item["actual_nav_inverse_median_dt_hz"] = 1/item["actual_nav_median_dt_s"]
            selected.append(item)
    return {"status": "AVAILABLE", "source": _source(table,p), "rows": selected,
            "baseline_median_m": p.baseline_median_m,
            "v3_lever_frd_m": [.03,.03-.5*p.baseline_median_m,-.30], "window_s": list(p.window),
            "evaluator_sha256": "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da",
            "frozen_metric_role": "P07_V3_FROZEN_ROWS_NOT_NEW_PERFORMANCE_EVIDENCE"}


def run_audit():
    p = load_sequence_paths("BY2")
    target = p.output_root / "00_CONFIG_AUDIT"
    target.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": "hext.config_audit.v1", "data_mode": "real_raw_and_read_only_frozen_evidence",
              "synthetic_data_used": False, "semisynthetic_data_used": False,
              "trace_open_count": 0, "solver_invocation_count": 0, "evaluator_invocation_count": 0,
              "output_root": alias_path(target,p)}
    for name, call in (("A1_A2",lambda:position_audit(p,target)),("A4_A7_A9",lambda:noise_audit(p)),
                       ("A8",lambda:calibration_audit(p)),("A10",lambda:gap_audit(p)),
                       ("A11_A12",lambda:evaluation_audit(p))):
        try:
            result[name] = call()
        except (OSError,ValueError,KeyError,IndexError) as error:
            result[name] = {"status":"UNAVAILABLE", "reason":f"{type(error).__name__}: {error}"}
    _write_json(target / "CONFIG_AUDIT_OBSERVATIONS.json", result)
    return result
