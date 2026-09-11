"""P-09c sealed-output evaluation; reference payload stays inside one child.

The archived evaluator is unchanged. Its observer uses the actual evaluation
NAV, full common cleaned reference support and WGS84, without replacing arrays.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import transform_nav, write_transformed_nav
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256, evaluate
from ..manifest import sha256_file

POLICY = "canonical_v2_wgs84_full_support"
ALGORITHM_FAILURE = "ALGORITHM_FAILURE_ALL_YAW_REJECTED"


def _write_json(path, payload):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _resolve(value, reg):
    text = str(value)
    for alias, key in (("<CLEAN_ROOT>", "clean_root"), ("<RAW_ROOT>", "raw_root"), ("<CODE_ROOT>", "code_root")):
        if text == alias or text.startswith(alias + "/"):
            return Path(getattr(reg, key)) / text[len(alias):].lstrip("/")
    path = Path(text)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Evaluation path is not an explicit alias or local absolute path")
    return path


def _ecef(lat, lon, alt):
    lat, lon = np.deg2rad(lat), np.deg2rad(lon)
    sl, cl = np.sin(lat), np.cos(lat)
    radius = 6378137.0 / np.sqrt(1.0 - 6.69437999014e-3 * sl**2)
    return np.column_stack(((radius + alt) * cl * np.cos(lon),
                            (radius + alt) * cl * np.sin(lon),
                            (radius * (1.0 - 6.69437999014e-3) + alt) * sl))


def wgs84_consistency_check(nav, errors, reference):
    """Independent arithmetic on observed arrays; no source opens or fitting."""
    required = ("time", "lat", "lon", "alt", "roll", "pitch", "yaw")
    if not len(nav) or not len(errors) or not len(reference):
        raise ValueError("Empty evaluation/reference support")
    if not np.isfinite(nav[list(required)].to_numpy(float)).all() or not np.isfinite(reference[list(required)].to_numpy(float)).all():
        raise ValueError("Observer received nonfinite common cleaned support")
    nt, t, tt = (frame.time.to_numpy(float) for frame in (nav, errors, reference))
    if np.any(np.diff(nt) <= 0) or np.any(np.diff(tt) < 0):
        raise ValueError("Unordered evaluation or reference support")
    if len(nt) != len(t) or not np.allclose(nt, t, atol=1e-9, rtol=0):
        raise ValueError("Error epochs differ from actual evaluation NAV")
    if t[0] < tt[0] or t[-1] > tt[-1]:
        raise ValueError("Evaluation epochs exceed common reference support")
    reference_llh = [np.interp(t, tt, reference[key].to_numpy(float)) for key in ("lat", "lon", "alt")]
    estimate_xyz = _ecef(*(nav[key].to_numpy(float) for key in ("lat", "lon", "alt")))
    reference_xyz = _ecef(*reference_llh)
    lat0, lon0 = np.deg2rad([reference_llh[0][0], reference_llh[1][0]])
    sl, cl, so, co = np.sin(lat0), np.cos(lat0), np.sin(lon0), np.cos(lon0)
    rotation = np.array([[-so, co, 0.0], [-sl*co, -sl*so, cl], [cl*co, cl*so, sl]])
    expected_enu = (estimate_xyz - reference_xyz) @ rotation.T
    actual_enu = errors[["err_e_m", "err_n_m", "err_u_m"]].to_numpy(float)
    residual = expected_enu - actual_enu
    reference_yaw = np.rad2deg(np.interp(t, tt, np.unwrap(np.deg2rad(reference.yaw.to_numpy(float)))))
    expected_yaw = (nav.yaw.to_numpy(float) - (90 - reference_yaw) % 360 + 180) % 360 - 180
    yaw_residual = (expected_yaw - errors.yaw_err_deg.to_numpy(float) + 180) % 360 - 180
    if not np.isfinite(residual).all() or not np.isfinite(yaw_residual).all():
        raise ValueError("Nonfinite WGS84 consistency residual")
    h = float(np.max(np.hypot(residual[:, 0], residual[:, 1])))
    u, yaw = float(np.max(np.abs(residual[:, 2]))), float(np.max(np.abs(yaw_residual)))
    return {"horizontal_max_m": h, "up_max_m": u, "yaw_max_deg": yaw,
            "matched_epoch_count": len(t), "reference_cleaned_epoch_count": len(tt),
            "position_threshold_m": 0.01, "yaw_threshold_deg": 0.01,
            "passed": h <= 0.01 and u <= 0.01 and yaw <= 0.01,
            "policy": POLICY, "projection": "WGS84 ECEF to ENU at interpolated first reference epoch",
            "reference_support": "full unchanged load_trace return; all seven selected columns jointly cleaned",
            "nav_support": "actual evaluator main NAV after common-support intersection",
            "time_offset_applied": 0.0, "observation_only": True}


def one_evaluation(record, version, contract, reg, output_root, code_commit):
    """Return a Canonical flat row; each invocation has an exclusive output dir.

    record accepts the runtime's native output_root, terminal_status, case_meta
    or source_registry_row, trace pin, window, base_time and baseline_median_m.
    output_root is the current batch scratch root. The controller seals native
    files before calling and handles archive/retention only after this returns.
    """
    if version not in ("v3", "v2"):
        raise ValueError("Only preregistered v3 and v2 are evaluable")
    root = Path(output_root) / "12_OFFLINE_EVALUATION" / version / str(record["run_id"])
    root.mkdir(parents=True, exist_ok=False)
    source_row = dict(record.get("source_registry_row", {}))
    source_row.update({k: v for k, v in record.items() if k not in ("source_registry_row", "case_meta")})
    terminal = record.get("terminal_status", record.get("status", "NOT_EXECUTED"))
    case_meta = record.get("case_meta", record.get("source_registry_row", {}))
    row = {k: source_row.get(k) for k in canonical.IDENTITY_FIELDS}
    row.update({k: record.get(k) for k in ("dataset_id", "data_mode", "controlled_degradation_applied", "config_hash", "raw_source_hashes", "provider_hashes")})
    row.update(protocol_id=contract.get("protocol_id", "CANONICAL_541_PROTOCOL_V2"), chain="CAL",
               code_commit=code_commit, evaluator_version=version, evaluator_contract="evaluator_contract_" + version,
               effective_configuration_id=source_row.get("effective_profile", source_row.get("effective_configuration_id")),
               case_family=source_row.get("case_family", source_row.get("family")),
               degradation_id=source_row.get("degradation_type_id", source_row.get("degradation_id")),
               seed_id=source_row.get("seed_index", source_row.get("seed_id")),
               solver_terminal_status=terminal, technical_failure=terminal not in ("COMPLETED", ALGORITHM_FAILURE),
               algorithm_failure=terminal == ALGORITHM_FAILURE, evaluation_invoked=False,
               evaluation_status="NOT_RUN_ALGORITHM_FAILURE" if terminal == ALGORITHM_FAILURE else "NOT_RUN_TECHNICAL_FAILURE",
               synthetic_data_used=False, semisynthetic_data_used=False, trace_used_online=False,
               reference_is_independent_ground_truth=False, source_row=str(root / "EVALUATION_RESULT.json"),
               evaluation_output_root=str(root), native_run_manifest=str(Path(record["output_root"]) / "RUN_MANIFEST.json"))
    if terminal != "COMPLETED":
        _write_json(root / "EVALUATION_RESULT.json", row)
        return row
    try:
        spec = contract["evaluation"]
        native = Path(record["output_root"])
        nav_path, std_path = native / "KF_GINS_Navresult.nav", native / "KF_GINS_STD.txt"
        seal_path = native / "OUTPUT_SEAL.json"
        seal = json.loads(seal_path.read_text())
        if seal.get("status") != "SEALED_BEFORE_EVALUATION" or seal.get("files") != record.get("output_seal"):
            raise ValueError("Native output must be sealed before offline evaluation")
        source_nav_hash, source_std_hash = sha256_file(nav_path), sha256_file(std_path)
        for path, actual in ((nav_path, source_nav_hash), (std_path, source_std_hash)):
            if seal["files"].get(path.name, {}).get("sha256") != actual:
                raise ValueError("Native sealed NAV/STD changed")
        for key, actual in (("nav_sha256", source_nav_hash), ("std_sha256", source_std_hash)):
            if record.get(key) is not None and record[key] != actual:
                raise ValueError("Native seal mismatch: " + key)
        window = list(map(float, record.get("window", spec["window"])))
        base_time = record.get("base_time", spec["base_time"])
        trace_pin = record.get("trace", spec["trace"])
        evaluator = _resolve(spec["evaluator"]["path"], reg)
        if spec["evaluator"]["sha256"] != EVALUATOR_SHA256:
            raise ValueError("Wrong frozen evaluator contract")
        nav = canonical._read_numeric_table(nav_path).to_numpy(float)
        if not len(nav) or not np.isfinite(nav).all() or np.any(np.diff(nav[:, 1]) <= 0):
            raise ValueError("Nonfinite or unordered native NAV")
        if np.any((nav[:, 1] < window[0]) | (nav[:, 1] > window[1])):
            raise ValueError("Native NAV outside frozen sequence window")
        target = nav_path
        if version == "v3":
            baseline = float(record.get("baseline_median_m", spec["v3_baseline_median_m"]))
            target = root / "EVAL_NAV_V3.nav"
            write_transformed_nav(nav_path, target, transform_nav(nav, baseline))
            row.update(v3_baseline_median_m=baseline, v3_lever_frd_m=[.03, .03-baseline/2, -.30])
        row["evaluation_invoked"] = True
        outcome = evaluate(evaluator=evaluator, trace=_resolve(trace_pin["path"], reg), nav=target, std=std_path,
                           outdir=root / "FROZEN_EVALUATOR", base_time=base_time, window=window,
                           trace_sha256=trace_pin["sha256"], code_root=reg.code_root,
                           raw_root=reg.raw_root, clean_root=reg.clean_root, consistency_policy=POLICY)
        capture = outcome["capture"]
        if capture.get("consistency", {}).get("passed") is not True:
            raise ValueError("P-09c actual EVAL_NAV WGS84 consistency gate failed")
        result = canonical._compute_result(source_row, case_meta, native, root / "FROZEN_EVALUATOR",
                                           capture["reference_epoch_count"], outcome["runtime_seconds"], True)
        count = int(np.sum((nav[:, 1] >= window[0]) & (nav[:, 1] <= window[1])))
        matched = result["matched_epoch_count"]
        result.update(output_epoch_count=count, reference_epoch_count=capture["reference_epoch_count"],
                      unmatched_epoch_count=max(0, count-matched), coverage_ratio=matched/count if count else None)
        row.update(result)
        row.update(evaluation_status="COMPLETED", technical_failure=False, algorithm_failure=False,
                   evaluator_sha256=EVALUATOR_SHA256, native_nav_sha256=source_nav_hash,
                   eval_nav_sha256=sha256_file(target), std_sha256=source_std_hash,
                   evaluator_audit=outcome["audit"], evaluator_consistency=capture["consistency"],
                   error_series_source=str(root / "FROZEN_EVALUATOR" / "error_series.csv.gz"),
                   summary_source=str(root / "FROZEN_EVALUATOR" / "summary.json"),
                   sequence_window_start_s=window[0], sequence_window_end_s=window[1],
                   solver_runtime_seconds=record.get("runtime_seconds", record.get("solver_seconds", result.get("solver_runtime_seconds"))),
                   v3_std_policy=spec.get("v3_std_policy") if version == "v3" else "ORIGINAL_STD",
                   uncertainty_status="UNTRANSPORTED_STD_DIAGNOSTIC_ONLY" if version == "v3" else "DIAGONAL_ONLY_NOT_FULL_NEES")
        if not result["finite_output"]:
            raise ValueError("Nonfinite evaluator output; no metric-driven row deletion")
    except Exception as error:
        # Failed evaluation rows retain identity/audit diagnostics, not partial
        # scientific values that could accidentally enter finite summaries.
        for key in list(row):
            if key.startswith(("east_", "north_", "up_", "down_", "horizontal_", "position_3d_",
                               "roll_", "pitch_", "yaw_", "attitude_", "vertical_", "cep", "pre_",
                               "during_", "post_", "fault_window_", "recovery_", "velocity_")):
                row[key] = None
        row.update(evaluation_status="FAILED_EVALUATOR", technical_failure=True,
                   failure_type=type(error).__name__, failure_message=str(error))
    _write_json(root / "EVALUATION_RESULT.json", row)
    return row
