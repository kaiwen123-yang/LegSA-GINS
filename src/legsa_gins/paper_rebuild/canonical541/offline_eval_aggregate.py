"""Evaluation-only Canonical-541 runner.

This module deliberately consumes only the two terminal registries plus each
run's NAV, STD, and RUN_MANIFEST.  It never invokes the solver, hashes payloads,
revalidates an output seal, renders plots, or packages evidence.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import json
import math
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml

from ..evidence import BY2_TRACE_RELATIVE_PATH


ATTEMPT_NAME = ".attempt_20260808T200855P0800"
EXPECTED_UNIQUE = 5951
EXPECTED_LOGICAL = 7033
BASE_TIME = 1772784000.0
WINDOW_START = 66.0
WINDOW_END = 340.0
TERMINAL_PASS = (
    "PASS_CANONICAL541_OFFLINE_EVALUATION_AND_AGGREGATE_READY_FOR_SEPARATE_PLOTTING"
)

AXIS_STAT_NAMES = (
    "signed_mean",
    "bias",
    "signed_median",
    "standard_deviation",
    "rmse",
    "mae",
    "median_absolute_error",
    "p50_absolute",
    "p75_absolute",
    "p90_absolute",
    "p95_absolute",
    "p99_absolute",
    "max_absolute",
    "final_signed_error",
    "final_absolute_error",
    "iae",
    "ise",
)
NORM_STAT_NAMES = (
    "rmse",
    "mean",
    "median",
    "mae",
    "p50",
    "p75",
    "p90",
    "p95",
    "p99",
    "max",
    "final",
    "iae",
    "ise",
)
WINDOW_STAT_NAMES = ("rmse", "mean", "median", "p90", "p95", "p99", "max")
SIGMA_STAT_NAMES = (
    "sigma_mean",
    "sigma_median",
    "sigma_p90",
    "sigma_p95",
    "sigma_p99",
    "sigma_max",
    "z_signed_mean",
    "z_rmse",
    "abs_z_p95",
    "abs_z_max",
    "coverage_1sigma",
    "coverage_2sigma",
    "coverage_3sigma",
    "calibration_ratio",
    "abs_error_sigma_pearson",
    "abs_error_sigma_spearman",
    "diagonal_normalized_squared_error_mean",
)

IDENTITY_FIELDS = (
    "run_id",
    "run_order",
    "execution_key",
    "case_id",
    "method_id",
    "matrix",
    "effective_configuration_id",
    "role",
    "case_family",
    "degradation_id",
    "seed_id",
    "output_root",
    "evaluation_status",
    "technical_failure",
    "algorithm_failure",
    "finite_output",
    "solver_returncode",
    "solver_runtime_seconds",
    "evaluation_runtime_seconds",
    "evaluation_invoked",
    "reference_identity",
    "reference_is_independent_ground_truth",
)

MODULE_SCALARS = {
    "gnss_position_update_count": "position_update_count",
    "receiver_velocity_update_count": "receiver_velocity_update_count",
    "dual_yaw_update_count": "dual_yaw_update_count",
    "dual_yaw_attempt_count": "dual_yaw_attempt_count",
    "dual_yaw_accepted_count": "dual_yaw_accepted_count",
    "scheme_c_normal_count": "yaw_NORMAL",
    "scheme_c_downweight_count": "yaw_DOWNWEIGHT",
    "scheme_c_reject_count": "yaw_REJECT",
    "raw_doppler_available_count": "raw_doppler_epoch_count",
    "raw_doppler_update_count": "raw_doppler_update_count",
    "raw_doppler_reject_count": "raw_doppler_reject_count",
    "raw_doppler_sat_count_min": "raw_doppler_sat_count_min",
    "raw_doppler_sat_count_median": "raw_doppler_sat_count_median",
    "raw_doppler_sat_count_max": "raw_doppler_sat_count_max",
    "raw_doppler_residual_p95_mps": "raw_doppler_residual_p95",
    "source_aware_evaluation_count": "source_aware_evaluation_count",
    "source_aware_changed_weight_count": "source_aware_weight_changed_count",
    "go2_rp_update_count": "go2_roll_pitch_update_count",
    "go2_rp_reject_count": "go2_attitude_weak_prior_reject_count",
    "go2_rp_residual_roll_p95_rad": "go2_attitude_prior_residual_roll_p95_rad",
    "go2_rp_residual_pitch_p95_rad": "go2_attitude_prior_residual_pitch_p95_rad",
    "go2_hv_update_count": "go2_horizontal_velocity_update_count",
    "go2_hv_reject_count": "go2_velocity_prior_reject_count",
    "gnss_rows_missing_or_invalid_count": "gnss_rows_skipped_unexpectedly",
    "raw_doppler_invalid_source_count": "raw_doppler_factor_invalid_epoch_count",
}

MODULE_JSON = {
    "source_aware_update_count_by_source_json": "source_aware_update_count_by_source",
    "source_aware_reject_count_by_source_json": "source_aware_reject_count_by_source",
    "source_aware_scale_stats_by_source_json": "source_aware_R_scale_stats_by_source",
    "source_aware_scale_p50_p95_max_by_source_json": "source_aware_R_scale_p50_p95_max_by_source",
    "scheme_c_action_count_by_source_json": "qm_action_count_by_source",
    "scheme_c_normal_count_by_source_json": "qm_normal_count_by_source",
    "scheme_c_downweight_count_by_source_json": "qm_downweight_count_by_source",
    "scheme_c_reject_count_by_source_json": "qm_reject_count_by_source",
    "go2_hv_confidence_counts_json": "go2_horizontal_velocity_prior_confidence_counts",
}

PAIRWISE_DEFINITIONS = (
    ("full_vs_strong", "F04", "F03"),
    ("strong_vs_basic", "F03", "F02"),
    ("basic_vs_single", "F02", "F01"),
    ("full_vs_no_RD", "F04", "A03"),
    ("full_vs_no_SA", "F04", "A04"),
    ("full_vs_no_RP", "F04", "A05"),
    ("full_vs_no_HV", "F04", "A06"),
    ("full_vs_no_Go2", "F04", "A07"),
    ("RD_only_vs_strong", "A08", "F03"),
    ("SA_only_vs_strong", "A09", "F03"),
)

PAIRWISE_METRICS = (
    "horizontal_rmse_m",
    "position_3d_rmse_m",
    "east_rmse_m",
    "north_rmse_m",
    "up_rmse_m",
    "yaw_rmse_deg",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "horizontal_p95_m",
    "position_3d_p95_m",
    "yaw_p95_absolute_deg",
    "fault_window_horizontal_rmse_m",
    "post_window_horizontal_rmse_m",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (np.bool_, bool)):
        return "true" if bool(value) else "false"
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return "" if not math.isfinite(float(value)) else float(value)
    return value


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _percentile(values: np.ndarray, q: float) -> float | None:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.percentile(values, q)) if values.size else None


def _integral(time_s: np.ndarray, values: np.ndarray, squared: bool = False) -> float | None:
    mask = np.isfinite(time_s) & np.isfinite(values)
    if not np.any(mask):
        return None
    t = np.asarray(time_s[mask], dtype=float)
    v = np.asarray(values[mask], dtype=float)
    order = np.argsort(t)
    t, v = t[order], v[order]
    if squared:
        v = np.square(v)
    else:
        v = np.abs(v)
    if v.size == 1:
        return 0.0
    return float(np.trapz(v, t))


def _axis_stats(time_s: np.ndarray, values: np.ndarray) -> dict[str, float | None]:
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(values)
    finite = values[mask]
    if not finite.size:
        return {name: None for name in AXIS_STAT_NAMES}
    absolute = np.abs(finite)
    return {
        "signed_mean": float(np.mean(finite)),
        "bias": float(np.mean(finite)),
        "signed_median": float(np.median(finite)),
        "standard_deviation": float(np.std(finite, ddof=0)),
        "rmse": float(np.sqrt(np.mean(np.square(finite)))),
        "mae": float(np.mean(absolute)),
        "median_absolute_error": float(np.median(absolute)),
        "p50_absolute": float(np.percentile(absolute, 50)),
        "p75_absolute": float(np.percentile(absolute, 75)),
        "p90_absolute": float(np.percentile(absolute, 90)),
        "p95_absolute": float(np.percentile(absolute, 95)),
        "p99_absolute": float(np.percentile(absolute, 99)),
        "max_absolute": float(np.max(absolute)),
        "final_signed_error": float(finite[-1]),
        "final_absolute_error": float(absolute[-1]),
        "iae": _integral(time_s, values, False),
        "ise": _integral(time_s, values, True),
    }


def _norm_stats(time_s: np.ndarray, values: np.ndarray) -> dict[str, float | None]:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if not finite.size:
        return {name: None for name in NORM_STAT_NAMES}
    absolute = np.abs(finite)
    return {
        "rmse": float(np.sqrt(np.mean(np.square(finite)))),
        "mean": float(np.mean(finite)),
        "median": float(np.median(finite)),
        "mae": float(np.mean(absolute)),
        "p50": float(np.percentile(absolute, 50)),
        "p75": float(np.percentile(absolute, 75)),
        "p90": float(np.percentile(absolute, 90)),
        "p95": float(np.percentile(absolute, 95)),
        "p99": float(np.percentile(absolute, 99)),
        "max": float(np.max(absolute)),
        "final": float(absolute[-1]),
        "iae": _integral(time_s, values, False),
        "ise": _integral(time_s, values, True),
    }


def _put_stats(row: dict[str, Any], prefix: str, unit: str, stats: Mapping[str, Any]) -> None:
    for name, value in stats.items():
        row[f"{prefix}_{name}_{unit}"] = value


def _read_numeric_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=r"\s+", engine="python", header=None, comment="%")


def _read_error_series(directory: Path) -> pd.DataFrame:
    plain = directory / "error_series.csv"
    compressed = directory / "error_series.csv.gz"
    if plain.is_file():
        return pd.read_csv(plain, encoding="utf-8-sig")
    if compressed.is_file():
        return pd.read_csv(compressed, encoding="utf-8-sig", compression="gzip")
    raise FileNotFoundError(f"missing error series under {directory}")


def _complete_eval_dir(eval_root: Path, run_id: str) -> Path | None:
    for directory in (eval_root / "PER_RUN" / run_id, eval_root / run_id):
        if not (directory / "summary.json").is_file():
            continue
        if (directory / "error_series.csv").is_file() or (directory / "error_series.csv.gz").is_file():
            return directory
    return None


def _run_exact_evaluator(
    *, run_id: str, output_root: Path, eval_root: Path, evaluator: Path,
    trace: Path, timeout_seconds: int,
) -> tuple[Path, float]:
    per_run = eval_root / "PER_RUN"
    per_run.mkdir(parents=True, exist_ok=True)
    work = eval_root / ".work"
    work.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{run_id}.", dir=str(work)))
    started = time.monotonic()
    command = [
        sys.executable,
        str(evaluator),
        "--trace", str(trace),
        "--nav", str(output_root / "KF_GINS_Navresult.nav"),
        "--std", str(output_root / "KF_GINS_STD.txt"),
        "--outdir", str(staging),
        "--base_time", str(BASE_TIME),
        "--yaw_truth_mode", "enu",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_seconds,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        },
    )
    runtime = time.monotonic() - started
    (staging / "evaluator_stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"exact evaluator returncode={completed.returncode}: {(completed.stdout or '')[-2000:]}")
    if not (staging / "summary.json").is_file() or not (staging / "error_series.csv").is_file():
        raise RuntimeError("exact evaluator did not produce summary.json and error_series.csv")
    compressed = staging / "error_series.csv.gz"
    with (staging / "error_series.csv").open("rb") as source, gzip.open(compressed, "wb", compresslevel=6) as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
    (staging / "error_series.csv").unlink()
    target_dir = per_run / run_id
    if target_dir.exists():
        preserved = per_run / f".{run_id}.incomplete.{int(time.time())}.{os.getpid()}"
        os.replace(target_dir, preserved)
    os.replace(staging, target_dir)
    return target_dir, runtime


def _event_window(case_meta: Mapping[str, Any]) -> tuple[float | None, float | None]:
    anchor = _float(case_meta.get("anchor_time_s"))
    try:
        params = json.loads(str(case_meta.get("degradation_parameters_json") or "{}"))
    except json.JSONDecodeError:
        params = {}
    start = None
    for key in ("start_s", "start_time_s", "fault_start_s", "outage_start_s"):
        start = _float(params.get(key))
        if start is not None:
            break
    if start is None:
        start = anchor
    end = None
    for key in ("end_s", "end_time_s", "fault_end_s", "outage_end_s"):
        end = _float(params.get(key))
        if end is not None:
            break
    duration = None
    for key in ("duration_s", "fault_duration_s", "outage_duration_s"):
        duration = _float(params.get(key))
        if duration is not None:
            break
    if end is None and start is not None and duration is not None:
        end = start + duration
    if start is None or end is None or end <= start:
        return None, None
    return start, end


def _correlation(x: np.ndarray, y: np.ndarray, spearman: bool = False) -> float | None:
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = np.asarray(x[mask], dtype=float), np.asarray(y[mask], dtype=float)
    if x.size < 3 or np.std(x) == 0 or np.std(y) == 0:
        return None
    if spearman:
        x = pd.Series(x).rank(method="average").to_numpy()
        y = pd.Series(y).rank(method="average").to_numpy()
    value = float(np.corrcoef(x, y)[0, 1])
    return value if math.isfinite(value) else None


def _sigma_stats(error: np.ndarray, sigma: np.ndarray) -> dict[str, float | None]:
    mask = np.isfinite(error) & np.isfinite(sigma) & (sigma > 0)
    e, s = np.asarray(error[mask], dtype=float), np.asarray(sigma[mask], dtype=float)
    if not e.size:
        return {name: None for name in SIGMA_STAT_NAMES}
    z = e / s
    mean_sigma = float(np.mean(s))
    error_rmse = float(np.sqrt(np.mean(np.square(e))))
    return {
        "sigma_mean": mean_sigma,
        "sigma_median": float(np.median(s)),
        "sigma_p90": float(np.percentile(s, 90)),
        "sigma_p95": float(np.percentile(s, 95)),
        "sigma_p99": float(np.percentile(s, 99)),
        "sigma_max": float(np.max(s)),
        "z_signed_mean": float(np.mean(z)),
        "z_rmse": float(np.sqrt(np.mean(np.square(z)))),
        "abs_z_p95": float(np.percentile(np.abs(z), 95)),
        "abs_z_max": float(np.max(np.abs(z))),
        "coverage_1sigma": float(np.mean(np.abs(z) <= 1)),
        "coverage_2sigma": float(np.mean(np.abs(z) <= 2)),
        "coverage_3sigma": float(np.mean(np.abs(z) <= 3)),
        "calibration_ratio": error_rmse / mean_sigma if mean_sigma > 0 else None,
        "abs_error_sigma_pearson": _correlation(np.abs(e), s, False),
        "abs_error_sigma_spearman": _correlation(np.abs(e), s, True),
        "diagonal_normalized_squared_error_mean": float(np.mean(np.square(z))),
    }


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _compute_result(
    registry: Mapping[str, Any], case_meta: Mapping[str, Any], output_root: Path,
    eval_dir: Path, reference_epoch_count: int, evaluation_runtime: float | None,
    evaluation_invoked: bool,
) -> dict[str, Any]:
    nav_path = output_root / "KF_GINS_Navresult.nav"
    std_path = output_root / "KF_GINS_STD.txt"
    manifest_path = output_root / "RUN_MANIFEST.json"
    for required in (nav_path, std_path, manifest_path):
        if not required.is_file():
            raise FileNotFoundError(str(required))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = _read_error_series(eval_dir)
    required_error = (
        "time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m",
        "position_3d_err_m", "roll_err_deg", "pitch_err_deg", "yaw_err_deg",
    )
    missing = [name for name in required_error if name not in errors.columns]
    if missing:
        raise ValueError(f"error series missing fields: {missing}")
    arrays = {name: pd.to_numeric(errors[name], errors="coerce").to_numpy(dtype=float) for name in required_error}
    t = arrays["time"]
    nav = _read_numeric_table(nav_path)
    nav_t = pd.to_numeric(nav.iloc[:, 1], errors="coerce").to_numpy(dtype=float)
    nav_window = (nav_t >= WINDOW_START) & (nav_t <= WINDOW_END)
    output_epoch_count = int(np.sum(nav_window))
    core = np.column_stack([arrays[name] for name in required_error[1:]])
    finite_rows = np.isfinite(core).all(axis=1) & np.isfinite(t)
    nonfinite_rows = ~finite_rows
    dt = np.diff(t[np.isfinite(t)])
    dt = dt[np.isfinite(dt) & (dt >= 0)]
    row: dict[str, Any] = {
        "run_id": registry.get("run_id"),
        "run_order": registry.get("run_order"),
        "execution_key": registry.get("execution_key"),
        "case_id": registry.get("case_id"),
        "method_id": registry.get("method_id"),
        "matrix": registry.get("matrix"),
        "effective_configuration_id": registry.get("effective_profile"),
        "role": "unique_execution",
        "case_family": registry.get("case_family"),
        "degradation_id": registry.get("degradation_type_id"),
        "seed_id": registry.get("seed_index"),
        "output_root": str(output_root),
        "evaluation_status": "COMPLETED",
        "technical_failure": False,
        "algorithm_failure": False,
        "finite_output": bool(np.all(finite_rows)),
        "solver_returncode": manifest.get("solver_returncode"),
        "solver_runtime_seconds": manifest.get("runtime_seconds"),
        "evaluation_runtime_seconds": evaluation_runtime,
        "evaluation_invoked": evaluation_invoked,
        "reference_identity": "Fixposition_same_source_offline_reference",
        "reference_is_independent_ground_truth": False,
        "output_epoch_count": output_epoch_count,
        "reference_epoch_count": reference_epoch_count,
        "matched_epoch_count": int(len(errors)),
        "unmatched_epoch_count": max(0, output_epoch_count - int(len(errors))),
        "coverage_ratio": (float(len(errors)) / output_epoch_count) if output_epoch_count else None,
        "finite_epoch_count": int(np.sum(finite_rows)),
        "finite_ratio": float(np.mean(finite_rows)) if finite_rows.size else None,
        "time_start": float(np.nanmin(t)) if np.any(np.isfinite(t)) else None,
        "time_end": float(np.nanmax(t)) if np.any(np.isfinite(t)) else None,
        "duration_sec": float(np.nanmax(t) - np.nanmin(t)) if np.any(np.isfinite(t)) else None,
        "median_dt_sec": float(np.median(dt)) if dt.size else None,
        "p95_dt_sec": float(np.percentile(dt, 95)) if dt.size else None,
        "max_gap_sec": float(np.max(dt)) if dt.size else None,
        "first_nonfinite_time": float(t[np.flatnonzero(nonfinite_rows)[0]]) if np.any(nonfinite_rows) else None,
        "reference_velocity_supported": False,
        "velocity_metrics_reason": "unsupported_by_reference",
    }
    axis_specs = (
        ("east", "m", arrays["err_e_m"]),
        ("north", "m", arrays["err_n_m"]),
        ("up", "m", arrays["err_u_m"]),
        ("down", "m", -arrays["err_u_m"]),
        ("roll", "deg", arrays["roll_err_deg"]),
        ("pitch", "deg", arrays["pitch_err_deg"]),
        ("yaw", "deg", arrays["yaw_err_deg"]),
    )
    for prefix, unit, values in axis_specs:
        _put_stats(row, prefix, unit, _axis_stats(t, values))
    attitude_norm = np.sqrt(
        np.square(arrays["roll_err_deg"]) + np.square(arrays["pitch_err_deg"]) + np.square(arrays["yaw_err_deg"])
    )
    norm_specs = (
        ("horizontal", "m", arrays["horizontal_err_m"]),
        ("position_3d", "m", arrays["position_3d_err_m"]),
        ("attitude_norm", "deg", attitude_norm),
    )
    for prefix, unit, values in norm_specs:
        _put_stats(row, prefix, unit, _norm_stats(t, values))
    row["cep50_m"] = row.get("horizontal_p50_m")
    row["cep95_m"] = row.get("horizontal_p95_m")
    row["vertical_p50_m"] = row.get("up_p50_absolute_m")
    row["vertical_p95_m"] = row.get("up_p95_absolute_m")
    row["vertical_p99_m"] = row.get("up_p99_absolute_m")
    row["vertical_max_m"] = row.get("up_max_absolute_m")

    # Velocity comparison is intentionally unsupported: this reference does not
    # provide a frozen velocity contract.  Emit the full schema as NA.
    for prefix, unit in (
        ("velocity_east", "mps"), ("velocity_north", "mps"),
        ("velocity_up", "mps"), ("horizontal_velocity", "mps"),
        ("velocity_3d", "mps"),
    ):
        names = AXIS_STAT_NAMES if prefix in {"velocity_east", "velocity_north", "velocity_up"} else NORM_STAT_NAMES
        for name in names:
            row[f"{prefix}_{name}_{unit}"] = None

    std = _read_numeric_table(std_path)
    if std.shape[1] < 10:
        raise ValueError(f"STD has {std.shape[1]} columns, expected at least 10")
    std_t = pd.to_numeric(std.iloc[:, 0], errors="coerce").to_numpy(dtype=float)
    std_specs = (
        ("north", "m", arrays["err_n_m"], 1),
        ("east", "m", arrays["err_e_m"], 2),
        ("up", "m", arrays["err_u_m"], 3),
        ("down", "m", -arrays["err_u_m"], 3),
        ("roll", "deg", arrays["roll_err_deg"], 7),
        ("pitch", "deg", arrays["pitch_err_deg"], 8),
        ("yaw", "deg", arrays["yaw_err_deg"], 9),
    )
    std_valid_time = np.isfinite(std_t)
    for prefix, unit, error, column in std_specs:
        raw_sigma = pd.to_numeric(std.iloc[:, column], errors="coerce").to_numpy(dtype=float)
        mask = std_valid_time & np.isfinite(raw_sigma)
        if np.sum(mask) >= 2:
            order = np.argsort(std_t[mask])
            sigma = np.interp(t, std_t[mask][order], raw_sigma[mask][order])
            stats = _sigma_stats(error, sigma)
        else:
            stats = {name: None for name in SIGMA_STAT_NAMES}
        _put_stats(row, prefix, unit, stats)
    for prefix in ("velocity_north", "velocity_east", "velocity_up"):
        for name in SIGMA_STAT_NAMES:
            row[f"{prefix}_{name}_mps"] = None

    start, end = _event_window(case_meta)
    row["degradation_window_start_s"] = start
    row["degradation_window_end_s"] = end
    row["degradation_window_identified"] = start is not None and end is not None
    segments: dict[str, np.ndarray] = {
        "pre": np.zeros(len(t), dtype=bool),
        "during": np.zeros(len(t), dtype=bool),
        "post": np.zeros(len(t), dtype=bool),
    }
    if start is not None and end is not None:
        segments = {"pre": t < start, "during": (t >= start) & (t <= end), "post": t > end}
    for segment_name, segment_mask in segments.items():
        for metric_name, unit, values in (
            ("horizontal", "m", arrays["horizontal_err_m"]),
            ("position_3d", "m", arrays["position_3d_err_m"]),
            ("yaw", "deg", arrays["yaw_err_deg"]),
        ):
            segment_values = np.where(segment_mask, values, np.nan)
            stats = _norm_stats(t, segment_values)
            for stat in WINDOW_STAT_NAMES:
                row[f"{segment_name}_{metric_name}_{stat}_{unit}"] = stats.get(stat)
    row["fault_window_peak_horizontal_m"] = row.get("during_horizontal_max_m")
    row["fault_window_peak_3d_m"] = row.get("during_position_3d_max_m")
    row["fault_window_peak_yaw_deg"] = row.get("during_yaw_max_deg")
    row["fault_window_horizontal_rmse_m"] = row.get("during_horizontal_rmse_m")
    row["fault_window_3d_rmse_m"] = row.get("during_position_3d_rmse_m")
    row["fault_window_yaw_rmse_deg"] = row.get("during_yaw_rmse_deg")
    row["post_window_horizontal_rmse_m"] = row.get("post_horizontal_rmse_m")
    row["post_window_3d_rmse_m"] = row.get("post_position_3d_rmse_m")
    row["post_window_yaw_rmse_deg"] = row.get("post_yaw_rmse_deg")
    pre_median = row.get("pre_horizontal_median_m")
    post_peak = row.get("post_horizontal_max_m")
    row["post_window_overshoot_horizontal_m"] = (
        float(post_peak) - float(pre_median) if post_peak is not None and pre_median is not None else None
    )
    post_mask = segments["post"]
    row["post_recovery_horizontal_residual_mean_m"] = (
        float(np.nanmean(np.where(post_mask, arrays["horizontal_err_m"], np.nan))) if np.any(post_mask) else None
    )
    row["post_recovery_yaw_residual_bias_deg"] = (
        float(np.nanmean(np.where(post_mask, arrays["yaw_err_deg"], np.nan))) if np.any(post_mask) else None
    )
    row["recovery_time_sec"] = None
    row["recovery_reason"] = "no_frozen_recovery_rule" if start is not None else "no_identifiable_event_window"

    for output_name, manifest_name in MODULE_SCALARS.items():
        row[output_name] = manifest.get(manifest_name)
    evaluation_count = _float(row.get("source_aware_evaluation_count"))
    changed_count = _float(row.get("source_aware_changed_weight_count"))
    row["source_aware_touch_rate"] = (
        changed_count / evaluation_count if evaluation_count and changed_count is not None else None
    )
    for output_name, manifest_name in MODULE_JSON.items():
        row[output_name] = _json_or_none(manifest.get(manifest_name))
    return row


def _worker(task: Mapping[str, Any]) -> dict[str, Any]:
    registry = task["registry"]
    run_id = str(registry["run_id"])
    output_root = Path(str(registry["output_root"]))
    eval_root = Path(str(task["eval_root"]))
    started = time.monotonic()
    try:
        eval_dir = _complete_eval_dir(eval_root, run_id) if task["resume"] else None
        invoked = eval_dir is None
        evaluation_runtime: float | None = None
        if eval_dir is None:
            eval_dir, evaluation_runtime = _run_exact_evaluator(
                run_id=run_id,
                output_root=output_root,
                eval_root=eval_root,
                evaluator=Path(str(task["evaluator"])),
                trace=Path(str(task["trace"])),
                timeout_seconds=int(task["timeout_seconds"]),
            )
        row = _compute_result(
            registry,
            task["case_meta"],
            output_root,
            eval_dir,
            int(task["reference_epoch_count"]),
            evaluation_runtime,
            invoked,
        )
        if row.get("evaluation_runtime_seconds") is None and invoked:
            row["evaluation_runtime_seconds"] = time.monotonic() - started
        return {"ok": True, "row": row}
    except Exception as exc:  # worker failures become explicit rows in EVALUATION_FAILURES.csv
        return {
            "ok": False,
            "failure": {
                "run_id": run_id,
                "case_id": registry.get("case_id"),
                "method_id": registry.get("method_id"),
                "output_root": str(output_root),
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
                "failed_at": _utc_now(),
            },
        }


def _format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "unknown"
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _status_payload(
    *, service_name: str, started_at: str, started_mono: float, jobs: int,
    completed: int, success: int, failed: int, pending: int,
    completion_times: deque[float], last: Mapping[str, Any] | None,
    phase: str = "UNIQUE_OFFLINE_EVALUATION", logical_completed: int = 0,
    aggregate_phase: str = "NOT_STARTED", terminal_status: str = "RUNNING",
) -> dict[str, Any]:
    now = time.monotonic()
    elapsed = now - started_mono
    while completion_times and completion_times[0] < now - 120:
        completion_times.popleft()
    if len(completion_times) >= 2:
        span = max(1e-9, completion_times[-1] - completion_times[0])
        rate = (len(completion_times) - 1) * 60 / span
    elif elapsed > 0 and completed:
        rate = completed * 60 / elapsed
    else:
        rate = 0.0
    eta = pending / (rate / 60) if rate > 0 else None
    running = min(jobs, pending)
    return {
        "phase": phase,
        "service_name": service_name,
        "pid": os.getpid(),
        "started_at": started_at,
        "heartbeat_time": _utc_now(),
        "jobs": jobs,
        "unique_total": EXPECTED_UNIQUE,
        "unique_completed": completed,
        "unique_success": success,
        "unique_failed": failed,
        "running": running,
        "pending": pending,
        "logical_total": EXPECTED_LOGICAL,
        "logical_completed": logical_completed,
        "runs_per_minute_rolling": round(rate, 3),
        "elapsed_seconds": round(elapsed, 3),
        "eta_seconds": round(eta, 3) if eta is not None else None,
        "last_completed_run_id": (last or {}).get("run_id", ""),
        "last_completed_case_id": (last or {}).get("case_id", ""),
        "last_completed_method_id": (last or {}).get("method_id", ""),
        "aggregate_phase": aggregate_phase,
        "terminal_status": terminal_status,
    }


def _write_progress(eval_root: Path, status: Mapping[str, Any], force_print: bool = False) -> None:
    total = int(status["unique_total"])
    completed = int(status["unique_completed"])
    percent = completed * 100 / total if total else 0.0
    text = "\n".join(
        [
            "Canonical-541 Offline Evaluation",
            "--------------------------------",
            f"phase: {status['phase']}",
            f"completed: {completed} / {total} ({percent:.2f}%)",
            f"running: {status['running']}",
            f"failed: {status['unique_failed']}",
            f"pending: {status['pending']}",
            f"rate: {float(status['runs_per_minute_rolling']):.1f} runs/min",
            f"elapsed: {_format_duration(float(status['elapsed_seconds']))}",
            f"ETA: {_format_duration(_float(status['eta_seconds']))}",
            f"last run: {status['last_completed_run_id']}",
            f"last case: {status['last_completed_case_id']}",
            f"last method: {status['last_completed_method_id']}",
            f"heartbeat: {status['heartbeat_time']}",
            "",
        ]
    )
    _atomic_json(eval_root / "EVALUATION_STATUS.json", status)
    _atomic_text(eval_root / "EVALUATION_PROGRESS.txt", text)
    if force_print:
        print(
            f"[EVAL] {completed}/{total} {percent:.2f}% | running={status['running']} | "
            f"failed={status['unique_failed']} | rate={float(status['runs_per_minute_rolling']):.1f}/min | "
            f"ETA={_format_duration(_float(status['eta_seconds']))} | "
            f"last={status['last_completed_run_id']} {status['last_completed_case_id']} "
            f"{status['last_completed_method_id']}",
            flush=True,
        )


def _is_numeric_field(rows: Sequence[Mapping[str, Any]], field: str) -> bool:
    seen = False
    for row in rows[: min(len(rows), 1000)]:
        value = row.get(field)
        if value in (None, ""):
            continue
        if _float(value) is None:
            return False
        seen = True
    return seen


def _numeric_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return []
    excluded = set(IDENTITY_FIELDS) | {"run_order"}
    return [field for field in rows[0] if field not in excluded and _is_numeric_field(rows, field)]


def _higher_is_better(metric: str) -> bool:
    return any(token in metric for token in ("coverage", "finite_ratio", "evaluable_rate", "pass_ratio"))


def _summary_rows(
    rows: Sequence[Mapping[str, Any]], group_fields: Sequence[str], metrics: Sequence[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(field, "")) for field in group_fields)].append(row)
    output: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        group = grouped[group_key]
        finite_count = sum(str(row.get("finite_output", "")).lower() == "true" for row in group)
        evaluable_count = sum(str(row.get("evaluation_status", "")) == "COMPLETED" for row in group)
        failure_count = len(group) - evaluable_count
        for metric in metrics:
            samples = [(row, _float(row.get(metric))) for row in group]
            samples = [(row, value) for row, value in samples if value is not None]
            values = np.asarray([value for _, value in samples], dtype=float)
            base: dict[str, Any] = {field: value for field, value in zip(group_fields, group_key)}
            base.update(
                {
                    "metric_name": metric,
                    "count": len(group),
                    "finite_count": finite_count,
                    "finite_rate": finite_count / len(group) if group else None,
                    "evaluable_count": evaluable_count,
                    "evaluable_rate": evaluable_count / len(group) if group else None,
                    "failure_count": failure_count,
                    "failure_rate": failure_count / len(group) if group else None,
                    "non_null_count": len(values),
                }
            )
            for name in ("mean", "std", "median", "iqr", "p10", "p25", "p75", "p90", "p95", "p99", "min", "max"):
                base[name] = None
            base["worst_run_id"] = None
            base["worst_case_id"] = None
            if values.size:
                base.update(
                    {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values, ddof=0)),
                        "median": float(np.median(values)),
                        "iqr": float(np.percentile(values, 75) - np.percentile(values, 25)),
                        "p10": float(np.percentile(values, 10)),
                        "p25": float(np.percentile(values, 25)),
                        "p75": float(np.percentile(values, 75)),
                        "p90": float(np.percentile(values, 90)),
                        "p95": float(np.percentile(values, 95)),
                        "p99": float(np.percentile(values, 99)),
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                    }
                )
                worst_index = int(np.argmin(values) if _higher_is_better(metric) else np.argmax(values))
                worst = samples[worst_index][0]
                base["worst_run_id"] = worst.get("run_id")
                base["worst_case_id"] = worst.get("case_id")
            output.append(base)
    return output


def _fields_union(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    return fields


def _write_named_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    _write_csv(path, rows, _fields_union(rows) if rows else ["status"])


def _pairwise(logical: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    index = {(str(row.get("case_id")), str(row.get("method_id"))): row for row in logical}
    case_rows: list[dict[str, Any]] = []
    case_ids = sorted({str(row.get("case_id")) for row in logical})
    for comparison, candidate_id, reference_id in PAIRWISE_DEFINITIONS:
        for case_id in case_ids:
            candidate = index.get((case_id, candidate_id))
            reference = index.get((case_id, reference_id))
            if not candidate or not reference:
                continue
            for metric in PAIRWISE_METRICS:
                cv, rv = _float(candidate.get(metric)), _float(reference.get(metric))
                if cv is None or rv is None:
                    continue
                delta = cv - rv
                relative = delta / abs(rv) * 100 if rv != 0 else None
                case_rows.append(
                    {
                        "comparison": comparison,
                        "candidate_method_id": candidate_id,
                        "reference_method_id": reference_id,
                        "metric_name": metric,
                        "case_id": case_id,
                        "degradation_id": candidate.get("degradation_id"),
                        "case_family": candidate.get("case_family"),
                        "seed_id": candidate.get("seed_id"),
                        "candidate_value": cv,
                        "reference_value": rv,
                        "delta_candidate_minus_reference": delta,
                        "relative_change_percent": relative,
                        "candidate_better": delta < -1e-12,
                        "tie": abs(delta) <= 1e-12,
                    }
                )
    summary: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        grouped[(row["comparison"], row["metric_name"], "overall", "ALL")].append(row)
        grouped[(row["comparison"], row["metric_name"], "family", str(row["case_family"]))].append(row)
    for key in sorted(grouped):
        comparison, metric, scope, family = key
        group = grouped[key]
        delta = np.asarray([float(row["delta_candidate_minus_reference"]) for row in group])
        relative = np.asarray([float(row["relative_change_percent"]) for row in group if row["relative_change_percent"] is not None])
        win = int(np.sum(delta < -1e-12)); tie = int(np.sum(np.abs(delta) <= 1e-12)); loss = int(np.sum(delta > 1e-12))
        by_degradation: dict[str, list[float]] = defaultdict(list)
        for row in group:
            by_degradation[str(row["degradation_id"])].append(float(row["delta_candidate_minus_reference"]))
        consistencies = []
        for values in by_degradation.values():
            pos = sum(v > 1e-12 for v in values); neg = sum(v < -1e-12 for v in values); ties = len(values) - pos - neg
            consistencies.append(max(pos, neg, ties) / len(values))
        worst = group[int(np.argmax(delta))]; best = group[int(np.argmin(delta))]
        summary.append(
            {
                "comparison": comparison,
                "metric_name": metric,
                "scope": scope,
                "family": family,
                "paired_sample_count": len(group),
                "mean_delta_candidate_minus_reference": float(np.mean(delta)),
                "median_delta_candidate_minus_reference": float(np.median(delta)),
                "std_delta": float(np.std(delta, ddof=0)),
                "p10_delta": float(np.percentile(delta, 10)),
                "p90_delta": float(np.percentile(delta, 90)),
                "mean_relative_change_percent": float(np.mean(relative)) if relative.size else None,
                "median_relative_change_percent": float(np.median(relative)) if relative.size else None,
                "win_count": win,
                "tie_count": tie,
                "loss_count": loss,
                "win_rate": win / len(group),
                "seed_direction_consistency": float(np.mean(consistencies)) if consistencies else None,
                "worst_negative_case": worst["case_id"],
                "best_positive_case": best["case_id"],
                "delta_definition": "candidate_minus_reference; negative_is_better",
            }
        )
    seed_rows: list[dict[str, Any]] = []
    seed_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        seed_groups[(str(row["degradation_id"]), row["comparison"], row["metric_name"])].append(row)
    for key in sorted(seed_groups):
        degradation, comparison, metric = key
        group = seed_groups[key]
        delta = np.asarray([float(row["delta_candidate_minus_reference"]) for row in group])
        pos = int(np.sum(delta > 1e-12)); neg = int(np.sum(delta < -1e-12)); tie = len(delta) - pos - neg
        seed_rows.append(
            {
                "degradation_id": degradation,
                "comparison": comparison,
                "metric_name": metric,
                "valid_seed_count": len(delta),
                "positive_delta_count": pos,
                "negative_delta_count": neg,
                "tie_count": tie,
                "direction_consistency_ratio": max(pos, neg, tie) / len(delta),
                "mean_paired_delta": float(np.mean(delta)),
                "median_paired_delta": float(np.median(delta)),
                "std_paired_delta": float(np.std(delta, ddof=0)),
                "min_paired_delta": float(np.min(delta)),
                "max_paired_delta": float(np.max(delta)),
                "delta_definition": "candidate_minus_reference; negative_is_better",
            }
        )
    return case_rows, summary, seed_rows


def _coverage_report(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    output: list[dict[str, Any]] = []
    excluded = set(IDENTITY_FIELDS)
    for metric in rows[0]:
        if metric in excluded:
            continue
        non_null = sum(row.get(metric) not in (None, "") for row in rows)
        reason = ""
        if metric.startswith("velocity_") or metric.startswith("horizontal_velocity_"):
            reason = "unsupported_by_reference"
        elif metric == "recovery_time_sec":
            reason = "no_frozen_recovery_rule"
        elif non_null == 0 and ("count" in metric or "runtime" in metric or "residual" in metric):
            reason = "not_recorded_in_RUN_MANIFEST"
        elif non_null == 0:
            reason = "not_supported_or_not_applicable"
        if metric.startswith(("north_", "east_", "up_", "down_", "horizontal_", "position_3d_", "roll_", "pitch_", "yaw_", "attitude_")):
            source = "exact evaluator error_series.csv plus KF_GINS_STD.txt"
        elif metric.startswith(("output_epoch", "reference_epoch", "matched_", "unmatched_", "coverage_", "finite_", "time_", "duration_", "median_dt", "p95_dt", "max_gap")):
            source = "KF_GINS_Navresult.nav plus exact evaluator error_series.csv"
        elif metric in MODULE_SCALARS or metric in MODULE_JSON or "count" in metric:
            source = "RUN_MANIFEST.json"
        else:
            source = "derived from permitted evaluation inputs"
        output.append(
            {
                "metric_name": metric,
                "supported": non_null > 0,
                "source_fields": source,
                "non_null_rows": non_null,
                "total_rows": len(rows),
                "coverage_ratio": non_null / len(rows),
                "unsupported_reason": reason,
            }
        )
    return output


def _logical_rows(logical_registry: Sequence[Mapping[str, Any]], unique: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_run = {str(row["run_id"]): row for row in unique}
    output: list[dict[str, Any]] = []
    for logical in logical_registry:
        source = by_run.get(str(logical.get("run_id")))
        if source is None:
            raise RuntimeError(f"logical row references missing unique run {logical.get('run_id')}")
        row = dict(source)
        row.update(
            {
                "logical_id": logical.get("logical_id"),
                "logical_order": logical.get("logical_order"),
                "method_id": logical.get("method_id"),
                "method_name": logical.get("method_name"),
                "effective_configuration_id": logical.get("effective_profile"),
                "role": "logical_alias" if str(logical.get("execution_alias")).lower() == "true" else "logical_result",
                "execution_alias": logical.get("execution_alias"),
                "alias_of": logical.get("alias_of"),
                "case_family": logical.get("case_family"),
                "degradation_id": logical.get("degradation_type_id"),
                "degradation_type_name": logical.get("degradation_type_name"),
                "seed_id": logical.get("seed_index"),
            }
        )
        output.append(row)
    return output


def _aggregate(
    *, aggregate_root: Path, unique: list[dict[str, Any]], logical: list[dict[str, Any]],
    wall_start: float, service_name: str,
) -> None:
    aggregate_root.mkdir(parents=True, exist_ok=True)
    numeric_unique = _numeric_fields(unique)
    numeric_logical = _numeric_fields(logical)
    summary_spec = (
        ("UNIQUE_METHOD_SUMMARY.csv", unique, ("method_id", "effective_configuration_id"), numeric_unique, "METHOD_SUMMARY"),
        ("LOGICAL_METHOD_SUMMARY.csv", logical, ("method_id", "effective_configuration_id"), numeric_logical, "LOGICAL_METHOD_SUMMARY"),
        ("CASE_SUMMARY.csv", logical, ("case_id",), numeric_logical, "CASE_SUMMARY"),
        ("DEGRADATION_TYPE_SUMMARY.csv", logical, ("degradation_id", "method_id"), numeric_logical, "DEGRADATION_TYPE_SUMMARY"),
        ("FAMILY_SUMMARY.csv", logical, ("case_family", "method_id"), numeric_logical, "FAMILY_SUMMARY"),
    )
    for filename, rows, groups, metrics, label in summary_spec:
        _write_named_csv(aggregate_root / filename, _summary_rows(rows, groups, metrics))
        print(f"[AGGREGATE] {label} complete", flush=True)

    pair_cases, pair_summary, seed_summary = _pairwise(logical)
    _write_named_csv(aggregate_root / "PAIRWISE_CASE_LEVEL.csv", pair_cases)
    print("[AGGREGATE] PAIRWISE_CASE_LEVEL complete", flush=True)
    _write_named_csv(aggregate_root / "PAIRWISE_SUMMARY.csv", pair_summary)
    print("[AGGREGATE] PAIRWISE_SUMMARY complete", flush=True)
    _write_named_csv(aggregate_root / "SEED_SUMMARY.csv", seed_summary)
    print("[AGGREGATE] SEED_SUMMARY complete", flush=True)

    recovery_fields = [
        field for field in numeric_logical
        if field.startswith(("pre_", "during_", "post_", "fault_window_")) or field in {"recovery_time_sec"}
    ]
    recovery_rows = [row for row in logical if str(row.get("degradation_id")) in {"D58", "D60"}]
    _write_named_csv(
        aggregate_root / "RECOVERY_SUMMARY.csv",
        _summary_rows(recovery_rows, ("degradation_id", "method_id"), recovery_fields),
    )
    print("[AGGREGATE] RECOVERY_SUMMARY complete", flush=True)

    uncertainty_metrics = [
        field for field in numeric_logical
        if any(token in field for token in (
            "coverage_1sigma", "coverage_2sigma", "coverage_3sigma", "z_rmse",
            "calibration_ratio", "abs_error_sigma_pearson", "abs_error_sigma_spearman",
            "diagonal_normalized_squared_error",
        ))
    ]
    uncertainty_rows: list[dict[str, Any]] = []
    for dimension in ("method_id", "case_family", "degradation_id", "seed_id"):
        rows = _summary_rows(logical, (dimension,), uncertainty_metrics)
        for row in rows:
            row["group_dimension"] = dimension
            row["group_value"] = row.pop(dimension)
        uncertainty_rows.extend(rows)
    _write_named_csv(aggregate_root / "UNCERTAINTY_CALIBRATION_SUMMARY.csv", uncertainty_rows)
    print("[AGGREGATE] UNCERTAINTY_CALIBRATION_SUMMARY complete", flush=True)

    module_metrics = [field for field in numeric_logical if field in MODULE_SCALARS or field == "source_aware_touch_rate"]
    module_rows = _summary_rows(logical, ("method_id", "case_family"), module_metrics)
    _write_named_csv(aggregate_root / "MODULE_ACTION_SUMMARY.csv", module_rows)
    print("[AGGREGATE] MODULE_ACTION_SUMMARY complete", flush=True)

    runtime_metrics = [field for field in ("solver_runtime_seconds", "evaluation_runtime_seconds") if field in numeric_unique]
    runtime_rows: list[dict[str, Any]] = []
    for groups in (("method_id",), ("case_family",), ("method_id", "case_family")):
        runtime_rows.extend(_summary_rows(unique, groups, runtime_metrics))
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    runtime_rows.append(
        {
            "method_id": "ALL",
            "case_family": "ALL",
            "metric_name": "total_wall_time_seconds",
            "count": len(unique),
            "mean": time.monotonic() - wall_start,
            "total_cpu_time_seconds": float(usage.ru_utime + usage.ru_stime),
        }
    )
    _write_named_csv(aggregate_root / "RUNTIME_SUMMARY.csv", runtime_rows)
    print("[AGGREGATE] RUNTIME_SUMMARY complete", flush=True)

    coverage = _coverage_report(unique)
    _write_named_csv(aggregate_root / "METRIC_COVERAGE_REPORT.csv", coverage)
    print("[AGGREGATE] METRIC_COVERAGE_REPORT complete", flush=True)

    final_summary = {
        "terminal_status": TERMINAL_PASS,
        "service_name": service_name,
        "unique_evaluated": len(unique),
        "logical_evaluated": len(logical),
        "evaluation_failures": 0,
        "aggregate_completed": True,
        "plotting_executed": False,
        "png_count": 0,
        "pdf_count": 0,
        "reference_identity": "Fixposition-derived same-source offline evaluation reference",
        "reference_is_independent_ground_truth": False,
        "yaw_contract": "unwrap reference then wrap360(90-yaw_trace_enu); wrap-safe residual",
        "alignment_or_search_used": False,
        "recovery_rule": "no new threshold invented; recovery_time_sec is NA without a frozen rule",
        "diagonal_consistency_note": "diagonal consistency diagnostic, not full-covariance NEES",
        "completed_at": _utc_now(),
    }
    _atomic_json(aggregate_root / "FINAL_EVALUATION_SUMMARY.json", final_summary)
    status = dict(final_summary)
    _atomic_json(aggregate_root / "EVALUATION_AND_AGGREGATE_STATUS.json", status)
    print("[AGGREGATE] FINAL_EVALUATION_SUMMARY complete", flush=True)


def _field_definitions(eval_root: Path) -> None:
    text = """# Canonical-541 offline evaluation field definitions

The exact archived evaluator is called unchanged with `base_time=1772784000.0`
and `yaw_truth_mode=enu`. Its yaw contract unwraps the reference yaw before
interpolation, applies `wrap360(90-yaw_trace_enu)`, and uses a wrap-safe angular
residual. No time, sign, axis, ninety-degree, constant-offset, rigid-alignment,
output-correction, or metric-driven epoch search is performed.

The Fixposition trace is a same-source offline comparison reference. It is not
independent ground truth. Velocity metrics are NA because the frozen reference
does not supply a supported velocity contract.

ENU signed fields use East, North, Up. NED equivalents use North, East, Down,
where Down is exactly `-Up`. IAE and ISE are trapezoidal time integrals over the
matched finite samples. Percentile fields for signed axes are percentiles of
absolute error; norm percentiles are percentiles of the nonnegative norm.

STD consistency fields use only the diagonal standard deviations present in
`KF_GINS_STD.txt`. `diagonal_normalized_squared_error_mean` is a diagonal
consistency diagnostic, not full-covariance NEES. Correlations compare absolute
error with predicted sigma.

Pre/during/post windows come only from the canonical logical registry's frozen
anchor and degradation parameters. `recovery_time_sec` remains NA when no
frozen recovery rule exists; no paper threshold is invented here.

Pairwise deltas are `candidate - reference`; for lower-is-better error metrics,
a negative delta means the candidate is better.
"""
    _atomic_text(eval_root / "FIELD_DEFINITIONS.md", text)


def _load_resume(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not path.is_file():
        return {}, []
    rows, fields = _read_csv(path)
    deduplicated: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("run_id") and row.get("evaluation_status") == "COMPLETED":
            deduplicated[str(row["run_id"])] = row
    if len(deduplicated) != len(rows):
        _write_csv(path, (deduplicated[key] for key in sorted(deduplicated)), fields)
    return deduplicated, fields


def _reference_count(trace: Path) -> int:
    frame = pd.read_csv(trace, usecols=lambda name: str(name).lower() in {"time", "aligned_time", "stamp", "timestamp"})
    if frame.shape[1] != 1:
        frame = pd.read_csv(trace)
        candidates = [column for column in frame.columns if "time" in str(column).lower() or "stamp" in str(column).lower()]
        if not candidates:
            raise ValueError("reference has no time field")
        values = pd.to_numeric(frame[candidates[0]], errors="coerce")
    else:
        values = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
    if float(values.dropna().median()) > 1e9:
        values = values - BASE_TIME
    return int(((values >= WINDOW_START) & (values <= WINDOW_END)).sum())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical-541 offline evaluation and aggregation only")
    parser.add_argument("--attempt-root", required=True)
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--exact-evaluator", required=True)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.jobs != 16:
        raise SystemExit("this authorized run requires --jobs 16")
    if not args.resume:
        raise SystemExit("this authorized run requires --resume")
    if not args.no_plots:
        raise SystemExit("this evaluation-only run requires --no-plots")
    attempt = Path(args.attempt_root).resolve(strict=True)
    if attempt.name != ATTEMPT_NAME:
        raise SystemExit(f"unexpected attempt root: {attempt}")
    config_path = Path(args.local_config).resolve(strict=True)
    evaluator = Path(args.exact_evaluator).resolve(strict=True)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw_root = Path(config["paths"]["raw_root"]).resolve(strict=True)
    trace = (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    unique_registry_path = attempt / "11_OUTPUT_SEAL" / "UNIQUE_RUN_TERMINAL_REGISTRY.csv"
    logical_registry_path = attempt / "11_OUTPUT_SEAL" / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv"
    unique_registry, _ = _read_csv(unique_registry_path)
    logical_registry, _ = _read_csv(logical_registry_path)
    if len(unique_registry) != EXPECTED_UNIQUE or len(logical_registry) != EXPECTED_LOGICAL:
        raise SystemExit(
            f"registry cardinality mismatch: unique={len(unique_registry)} logical={len(logical_registry)}"
        )
    if len({row["run_id"] for row in unique_registry}) != EXPECTED_UNIQUE:
        raise SystemExit("unique registry contains duplicate run_id")
    case_meta: dict[str, dict[str, Any]] = {}
    for row in logical_registry:
        case_meta.setdefault(str(row["case_id"]), dict(row))

    eval_root = attempt / "12_OFFLINE_EVALUATION"
    aggregate_root = attempt / "13_AGGREGATE"
    eval_root.mkdir(parents=True, exist_ok=True)
    aggregate_root.mkdir(parents=True, exist_ok=True)
    _field_definitions(eval_root)
    reference_epoch_count = _reference_count(trace)
    results_path = eval_root / "UNIQUE_EVALUATION_RESULTS.csv"
    completed_rows, existing_fields = _load_resume(results_path)
    failures_path = eval_root / "EVALUATION_FAILURES.csv"
    failure_fields = ("run_id", "case_id", "method_id", "output_root", "failure_type", "failure_message", "failed_at")
    if not failures_path.exists():
        _write_csv(failures_path, [], failure_fields)

    # Missing evaluations are submitted before the 240 legacy completed folders,
    # ensuring all 16 pool workers begin with real exact-evaluator invocations.
    remaining = [row for row in unique_registry if str(row["run_id"]) not in completed_rows]
    remaining.sort(key=lambda row: (_complete_eval_dir(eval_root, str(row["run_id"])) is not None, int(row["run_order"])))
    started_at = _utc_now()
    wall_start = time.monotonic()
    completion_times: deque[float] = deque()
    last: dict[str, Any] | None = None
    success = len(completed_rows)
    failed = 0
    completed = success
    status = _status_payload(
        service_name=args.service_name, started_at=started_at, started_mono=wall_start,
        jobs=args.jobs, completed=completed, success=success, failed=failed,
        pending=len(remaining), completion_times=completion_times, last=last,
    )
    _write_progress(eval_root, status, True)

    result_handle = None
    result_writer = None
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(
                    _worker,
                    {
                        "registry": dict(registry),
                        "case_meta": case_meta.get(str(registry["case_id"]), {}),
                        "eval_root": str(eval_root),
                        "evaluator": str(evaluator),
                        "trace": str(trace),
                        "timeout_seconds": args.timeout_seconds,
                        "reference_epoch_count": reference_epoch_count,
                        "resume": True,
                    },
                ): registry
                for registry in remaining
            }
            outstanding = set(futures)
            last_heartbeat = 0.0
            first_printed = completed > 0
            while outstanding:
                done, outstanding = concurrent.futures.wait(
                    outstanding, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    payload = future.result()
                    completed += 1
                    completion_times.append(time.monotonic())
                    if payload["ok"]:
                        row = payload["row"]
                        run_id = str(row["run_id"])
                        completed_rows[run_id] = row
                        success += 1
                        last = row
                        if result_writer is None:
                            fields = existing_fields or list(row.keys())
                            if not existing_fields:
                                result_handle = results_path.open("w", encoding="utf-8-sig", newline="")
                                result_writer = csv.DictWriter(result_handle, fieldnames=fields, extrasaction="ignore")
                                result_writer.writeheader()
                            else:
                                missing_fields = [field for field in row if field not in existing_fields]
                                if missing_fields:
                                    raise RuntimeError(f"resume CSV schema lacks fields: {missing_fields[:10]}")
                                result_handle = results_path.open("a", encoding="utf-8-sig", newline="")
                                result_writer = csv.DictWriter(result_handle, fieldnames=fields, extrasaction="ignore")
                        result_writer.writerow({key: _csv_value(row.get(key)) for key in result_writer.fieldnames})
                        result_handle.flush(); os.fsync(result_handle.fileno())
                    else:
                        failure = payload["failure"]
                        failed += 1
                        with failures_path.open("a", encoding="utf-8-sig", newline="") as handle:
                            writer = csv.DictWriter(handle, fieldnames=failure_fields, extrasaction="ignore")
                            writer.writerow(failure)
                            handle.flush(); os.fsync(handle.fileno())
                        last = failure
                    status = _status_payload(
                        service_name=args.service_name, started_at=started_at, started_mono=wall_start,
                        jobs=args.jobs, completed=completed, success=success, failed=failed,
                        pending=len(outstanding), completion_times=completion_times, last=last,
                    )
                    _atomic_json(eval_root / "EVALUATION_STATUS.json", status)
                    if not first_printed:
                        _write_progress(eval_root, status, True)
                        first_printed = True
                        last_heartbeat = time.monotonic()
                now = time.monotonic()
                if now - last_heartbeat >= 10:
                    status = _status_payload(
                        service_name=args.service_name, started_at=started_at, started_mono=wall_start,
                        jobs=args.jobs, completed=completed, success=success, failed=failed,
                        pending=len(outstanding), completion_times=completion_times, last=last,
                    )
                    _write_progress(eval_root, status, True)
                    last_heartbeat = now
    finally:
        if result_handle is not None:
            result_handle.close()

    if failed:
        status = _status_payload(
            service_name=args.service_name, started_at=started_at, started_mono=wall_start,
            jobs=args.jobs, completed=completed, success=success, failed=failed, pending=0,
            completion_times=completion_times, last=last, terminal_status="FAILED_EVALUATION",
        )
        _write_progress(eval_root, status, True)
        return 1
    if len(completed_rows) != EXPECTED_UNIQUE:
        raise RuntimeError(f"unique completion mismatch: {len(completed_rows)} != {EXPECTED_UNIQUE}")
    unique_rows = [completed_rows[run_id] for run_id in sorted(completed_rows)]
    result_fields = list(unique_rows[0].keys())
    _write_csv(results_path, unique_rows, result_fields)
    print(f"[EVAL COMPLETE] {len(unique_rows)}/{EXPECTED_UNIQUE}", flush=True)

    logical_rows = _logical_rows(logical_registry, unique_rows)
    if len(logical_rows) != EXPECTED_LOGICAL:
        raise RuntimeError(f"logical completion mismatch: {len(logical_rows)} != {EXPECTED_LOGICAL}")
    logical_path = eval_root / "LOGICAL_EVALUATION_RESULTS.csv"
    _write_csv(logical_path, logical_rows, list(logical_rows[0].keys()))
    print(f"[LOGICAL COMPLETE] {len(logical_rows)}/{EXPECTED_LOGICAL}", flush=True)

    aggregate_status = _status_payload(
        service_name=args.service_name, started_at=started_at, started_mono=wall_start,
        jobs=args.jobs, completed=EXPECTED_UNIQUE, success=EXPECTED_UNIQUE, failed=0, pending=0,
        completion_times=completion_times, last=last, phase="COMPREHENSIVE_AGGREGATION",
        logical_completed=EXPECTED_LOGICAL, aggregate_phase="RUNNING",
    )
    _write_progress(eval_root, aggregate_status, True)
    _aggregate(
        aggregate_root=aggregate_root,
        unique=unique_rows,
        logical=logical_rows,
        wall_start=wall_start,
        service_name=args.service_name,
    )
    terminal = _status_payload(
        service_name=args.service_name, started_at=started_at, started_mono=wall_start,
        jobs=args.jobs, completed=EXPECTED_UNIQUE, success=EXPECTED_UNIQUE, failed=0, pending=0,
        completion_times=completion_times, last=last, phase="COMPLETE",
        logical_completed=EXPECTED_LOGICAL, aggregate_phase="COMPLETED", terminal_status=TERMINAL_PASS,
    )
    terminal["running"] = 0
    _write_progress(eval_root, terminal, True)
    print(TERMINAL_PASS, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
