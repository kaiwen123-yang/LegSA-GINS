"""HX-02 heading-only evaluator child.

Run only as a registered evaluator subprocess (``python -m`` under strace). The
child opens the reference trace exactly once, read-only, checks its SHA-256 on
the same bytes, and writes nothing but a metrics JSON and a per-epoch error
series CSV. Reference yaw follows the frozen evaluator semantics:
``wrap360(90 - interp(unwrap(yaw_ENU)))`` with interpolation only inside the
trace support (no extrapolation). Statistics reuse the Phase-2 helpers.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ..horizontal_literature.phase2_runner import (
    _circular_statistics_deg,
    _continuity_metrics,
    _wrap180,
    _wrap360,
    _wrapsafe_error_metrics,
)

SCHEMA = "hx02.heading_evaluation.v1"
REQUIRED_TRACE_COLUMNS = ("time", "lat", "lon", "height", "roll", "pitch", "yaw")
HEADING_TABLE_COLUMNS = ("epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s", "valid", "body_yaw_deg")
OPTIONAL_FLAG_COLUMNS = ("ratio_fixed", "rtklib_q")


class HeadingEvaluationError(RuntimeError):
    """Fail-closed heading evaluation contract violation."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_heading_table(payload: bytes) -> dict[str, np.ndarray]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    missing = [name for name in HEADING_TABLE_COLUMNS if name not in (reader.fieldnames or [])]
    if missing:
        raise HeadingEvaluationError(f"heading table lacks columns {missing}")
    rows = list(reader)
    if not rows:
        raise HeadingEvaluationError("heading table is empty")
    table: dict[str, np.ndarray] = {
        "epoch_index": np.asarray([int(r["epoch_index"]) for r in rows], dtype=np.int64),
        "gps_week": np.asarray([int(r["gps_week"]) for r in rows], dtype=np.int64),
        "gps_tow_seconds": np.asarray([float(r["gps_tow_seconds"]) for r in rows], dtype=float),
        "time_unix_s": np.asarray([float(r["time_unix_s"]) for r in rows], dtype=float),
        "valid": np.asarray([r["valid"] == "1" for r in rows], dtype=bool),
        "body_yaw_deg": np.asarray([float(r["body_yaw_deg"]) if r["body_yaw_deg"] not in ("", "nan") else math.nan
                                    for r in rows], dtype=float),
    }
    for name in OPTIONAL_FLAG_COLUMNS:
        if name in (reader.fieldnames or []):
            table[name] = np.asarray([int(r[name]) if r[name] != "" else -1 for r in rows], dtype=np.int64)
    if np.any(np.diff(table["time_unix_s"]) <= 0.0) or np.any(np.diff(table["epoch_index"]) <= 0):
        raise HeadingEvaluationError("heading table must be strictly chronological with increasing epoch indices")
    if np.any(table["valid"] & ~np.isfinite(table["body_yaw_deg"])):
        raise HeadingEvaluationError("valid heading epoch without a finite body yaw")
    return table


def reference_yaw_ned(trace_payload: bytes, query_unix_s: Sequence[float]) -> np.ndarray:
    """Frozen-evaluator yaw semantics; NaN outside the trace support (no extrapolation)."""
    reader = csv.DictReader(io.StringIO(trace_payload.decode("utf-8-sig")))
    missing = [name for name in REQUIRED_TRACE_COLUMNS if name not in (reader.fieldnames or [])]
    if missing:
        raise HeadingEvaluationError(f"reference lacks columns {missing}")
    rows = list(reader)
    times = np.asarray([float(r["time"]) for r in rows], dtype=float)
    yaw_enu = np.asarray([float(r["yaw"]) for r in rows], dtype=float)
    if times.size < 2 or not np.isfinite(times).all() or not np.isfinite(yaw_enu).all() or np.any(np.diff(times) <= 0.0):
        raise HeadingEvaluationError("reference time/yaw stream is invalid")
    unwrapped = np.degrees(np.unwrap(np.radians(yaw_enu)))
    query = np.asarray(query_unix_s, dtype=float)
    result = np.full(query.shape, math.nan)
    inside = (query >= times[0]) & (query <= times[-1])
    if np.any(inside):
        interpolated = np.interp(query[inside], times, unwrapped)
        result[inside] = [_wrap360(90.0 - float(value)) for value in interpolated]
    return result


def _abs_stats(errors: np.ndarray) -> dict[str, Any]:
    if errors.size == 0:
        return {"count": 0, "rmse_deg": None, "max_absolute_deg": None, "p95_absolute_deg": None,
                "mae_deg": None, "circular_bias_deg": None}
    absolute = np.abs(errors)
    circular = _circular_statistics_deg(errors)
    return {"count": int(errors.size), "rmse_deg": float(np.sqrt(np.mean(errors ** 2))),
            "max_absolute_deg": float(np.max(absolute)), "p95_absolute_deg": float(np.quantile(absolute, 0.95)),
            "mae_deg": float(np.mean(absolute)), "circular_bias_deg": _wrap180(float(circular["circular_mean_deg"]))}


def heading_metrics(table: Mapping[str, np.ndarray], reference_ned_deg: np.ndarray, *, base_time: float,
                    window: Sequence[float], method_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """All registered heading metrics from one native heading table and one reference column."""
    start, end = map(float, window)
    times = np.asarray(table["time_unix_s"], dtype=float)
    relative = times - float(base_time)
    in_window = (relative >= start) & (relative <= end)
    denominator = int(np.count_nonzero(in_window))
    if denominator == 0:
        raise HeadingEvaluationError("native paired-epoch table has no epoch inside the window")
    valid = np.asarray(table["valid"], dtype=bool)
    yaw = np.asarray(table["body_yaw_deg"], dtype=float)
    finite_yaw = np.isfinite(yaw)
    if np.any(valid & ~finite_yaw):
        raise HeadingEvaluationError("valid heading epoch without a finite body yaw")
    reference = np.asarray(reference_ned_deg, dtype=float)
    bracketed = np.isfinite(reference)
    valid_window = valid & in_window
    scored = valid_window & bracketed
    errors = np.asarray([_wrap180(float(a) - float(b)) for a, b in zip(yaw[scored], reference[scored])], dtype=float)
    indices = [int(i) for i in np.asarray(table["epoch_index"])[scored]]
    valid_metrics = _wrapsafe_error_metrics(errors, indices, times[scored].tolist(), valid_denominator=denominator)
    valid_continuity = _continuity_metrics([int(i) for i in np.asarray(table["epoch_index"])[valid_window]],
                                           times[valid_window].tolist())
    # Hold the last method-native valid yaw (causal, from the native start); epochs
    # before the first valid value are no-heading epochs, never scored as zero.
    held = np.full(times.shape, math.nan)
    held_source = np.full(times.shape, -1, dtype=np.int64)
    last_yaw, last_index = math.nan, -1
    for position in range(times.size):
        if valid[position]:
            last_yaw, last_index = float(yaw[position]), int(table["epoch_index"][position])
        held[position], held_source[position] = last_yaw, last_index
    hold_available = in_window & np.isfinite(held)
    no_heading = in_window & ~np.isfinite(held)
    hold_scored = hold_available & bracketed
    hold_errors = np.asarray([_wrap180(float(a) - float(b)) for a, b in zip(held[hold_scored], reference[hold_scored])],
                             dtype=float)
    metrics: dict[str, Any] = {
        "schema": SCHEMA, "method_id": method_id,
        "window_seconds": [start, end], "base_time": float(base_time),
        "denominator_native_paired_epochs_in_window": denominator,
        "valid_epochs_in_window": int(np.count_nonzero(valid_window)),
        "availability": int(np.count_nonzero(valid_window)) / denominator,
        "valid_epochs_without_reference_support": int(np.count_nonzero(valid_window & ~bracketed)),
        "valid": {**_abs_stats(errors), "wrapsafe": valid_metrics},
        "valid_segments": {"segment_count": valid_continuity["segment_count"],
                           "longest_segment_epochs": valid_continuity["longest_segment_epochs"],
                           "maximum_gap_seconds": valid_continuity["maximum_gap_seconds"],
                           "definition": valid_continuity["continuity_definition"]},
        "hold_last_valid": {
            **_abs_stats(hold_errors),
            "held_epochs_in_window": int(np.count_nonzero(hold_available)),
            "no_heading_epochs_before_first_valid": int(np.count_nonzero(no_heading)),
            "held_epochs_without_reference_support": int(np.count_nonzero(hold_available & ~bracketed)),
            "hold_source": "CAUSAL_LAST_METHOD_NATIVE_VALID_EPOCH_FROM_NATIVE_START",
        },
        "reference_semantics": "wrap360(90-interp(unwrap(yaw_ENU))) inside trace support; no extrapolation",
        "error_convention": "wrap180(method_body_yaw_ned - reference_body_yaw_ned)",
    }
    flags: dict[str, np.ndarray] = {name: np.asarray(table[name]) for name in OPTIONAL_FLAG_COLUMNS if name in table}
    if "ratio_fixed" in flags:
        ratio = (flags["ratio_fixed"] == 1) & valid_window
        ratio_scored = ratio & bracketed & finite_yaw
        ratio_errors = np.asarray([_wrap180(float(a) - float(b)) for a, b in zip(yaw[ratio_scored], reference[ratio_scored])])
        metrics["ratio_fixed"] = {"count": int(np.count_nonzero(ratio)), "rate": int(np.count_nonzero(ratio)) / denominator,
                                  **{"errors": _abs_stats(ratio_errors)}}
    if "rtklib_q" in flags:
        q = flags["rtklib_q"]
        for label, value in (("q1_fixed", 1), ("q2_float", 2)):
            mask = (q == value) & in_window
            mask_scored = mask & bracketed & finite_yaw
            mask_errors = np.asarray([_wrap180(float(a) - float(b)) for a, b in zip(yaw[mask_scored], reference[mask_scored])])
            metrics[label] = {"count": int(np.count_nonzero(mask)), "rate": int(np.count_nonzero(mask)) / denominator,
                              "errors": _abs_stats(mask_errors)}
    series = []
    for position in np.flatnonzero(in_window):
        error_valid = _wrap180(float(yaw[position]) - float(reference[position])) if scored[position] else None
        error_hold = (_wrap180(float(held[position]) - float(reference[position])) if hold_scored[position] else None)
        row = {"epoch_index": int(table["epoch_index"][position]), "time_unix_s": repr(float(times[position])),
               "t_rel_s": repr(float(relative[position])), "valid": int(valid[position]),
               "reference_supported": int(bracketed[position]),
               "error_valid_deg": "" if error_valid is None else repr(error_valid),
               "hold_available": int(hold_available[position]), "hold_source_epoch_index": int(held_source[position]),
               "error_hold_deg": "" if error_hold is None else repr(error_hold)}
        for name, values in flags.items():
            row[name] = int(values[position])
        series.append(row)
    return metrics, series


def evaluate(spec: Mapping[str, Any]) -> dict[str, Any]:
    """One reference open for all declared variants (e.g. EXT04 FAR and primary PAR)."""
    outdir = Path(spec["outdir"])
    outdir.mkdir(parents=True, exist_ok=False)
    tables = {}
    for variant in spec["variants"]:
        payload = Path(variant["heading_table"]).read_bytes()
        if sha256_bytes(payload) != variant["heading_table_sha256"]:
            raise HeadingEvaluationError(f"{variant['label']} heading table SHA-256 mismatch")
        tables[variant["label"]] = read_heading_table(payload)
    with open(spec["trace"], "rb") as handle:  # the single reference open of this child
        trace_payload = handle.read()
    trace_sha256 = sha256_bytes(trace_payload)
    if trace_sha256 != spec["trace_sha256"]:
        raise HeadingEvaluationError("reference SHA-256 mismatch")
    references = {label: reference_yaw_ned(trace_payload, table["time_unix_s"]) for label, table in tables.items()}
    del trace_payload
    result: dict[str, Any] = {"schema": SCHEMA, "method_id": spec["method_id"], "sequence_id": spec["sequence_id"],
                              "trace_sha256_observed": trace_sha256, "trace_open_count_in_child": 1, "variants": {}}
    for variant in spec["variants"]:
        label = variant["label"]
        metrics, series = heading_metrics(tables[label], references[label], base_time=float(spec["base_time"]),
                                          window=spec["window"], method_id=label)
        metrics["heading_table_sha256"] = variant["heading_table_sha256"]
        result["variants"][label] = metrics
        columns = list(series[0].keys()) if series else ["epoch_index"]
        with (outdir / f"HEADING_ERROR_SERIES_{label}.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(series)
    with (outdir / "HEADING_METRICS.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    evaluate(spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
