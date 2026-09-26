"""HX-02 heading evaluator: synthetic sequences with known errors and known gaps."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext.hx02_heading_evaluation import (
    evaluate,
    heading_metrics,
    read_heading_table,
    reference_yaw_ned,
)

BASE = 1_700_000_000.0
# Unix-scale times carry ~2.4e-7 s representation error, i.e. <1e-6 deg at 3 deg/s.
TOL = 1e-5


def _trace_bytes(times, yaw_ned_deg):
    """Synthetic reference with the frozen column set; yaw stored as ENU (yaw_enu = 90 - yaw_ned)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", "lat", "lon", "height", "processed_lat", "processed_lon", "processed_height",
                     "yaw", "pitch", "roll"])
    for t, yaw in zip(times, yaw_ned_deg):
        writer.writerow([repr(t), "40.0", "116.0", "30.0", "40.0", "116.0", "30.0", repr((90.0 - yaw) % 360.0), "0", "0"])
    return out.getvalue().encode()


def _table_bytes(times, yaw, valid, extra=None):
    out = io.StringIO()
    columns = ["epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s", "valid", "body_yaw_deg"] + list(extra or {})
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for index, (t, y, v) in enumerate(zip(times, yaw, valid)):
        row = {"epoch_index": index, "gps_week": 2408, "gps_tow_seconds": repr(100.0 + index * 0.2),
               "time_unix_s": repr(t), "valid": int(v), "body_yaw_deg": repr(y) if v else ""}
        for name, values in (extra or {}).items():
            row[name] = values[index]
        writer.writerow(row)
    return out.getvalue().encode()


def _case():
    # 5 Hz epochs from t=0 to 20 s relative; window [2, 18] -> 81 epochs.
    rel = np.round(np.arange(0.0, 20.0001, 0.2), 6)
    times = BASE + rel
    truth = (10.0 + 3.0 * rel) % 360.0                      # reference NED yaw
    error = np.where(rel < 10.0, 2.0, -4.0)                 # known method error
    yaw = (truth + error) % 360.0
    valid = np.ones(rel.size, dtype=bool)
    valid[(rel >= 0.0) & (rel < 3.0)] = False               # nothing valid before 3.0 s
    valid[(rel > 12.0) & (rel < 14.0)] = False              # a 2 s gap inside the window
    trace_times = BASE + np.arange(-1.0, 21.0001, 0.1)
    trace_truth = (10.0 + 3.0 * (trace_times - BASE)) % 360.0
    return rel, times, truth, error, yaw, valid, trace_times, trace_truth


def test_reference_semantics_and_no_extrapolation():
    trace_times = BASE + np.array([0.0, 1.0, 2.0])
    payload = _trace_bytes(trace_times, [359.0, 1.0, 3.0])
    ref = reference_yaw_ned(payload, [BASE - 0.5, BASE + 0.5, BASE + 2.0, BASE + 2.5])
    assert math.isnan(ref[0]) and math.isnan(ref[3])
    assert ref[1] == pytest.approx(0.0, abs=1e-9)          # unwrap across 360 -> 0
    assert ref[2] == pytest.approx(3.0, abs=1e-9)


def test_four_registered_metrics_on_known_errors_and_gaps():
    rel, times, truth, error, yaw, valid, trace_times, trace_truth = _case()
    table = read_heading_table(_table_bytes(times, yaw, valid))
    reference = reference_yaw_ned(_trace_bytes(trace_times, trace_truth), table["time_unix_s"])
    metrics, series = heading_metrics(table, reference, base_time=BASE, window=(2.0, 18.0), method_id="SYN")
    window = (rel >= 2.0) & (rel <= 18.0)
    assert metrics["denominator_native_paired_epochs_in_window"] == int(window.sum()) == 81
    expected_valid = valid & window
    assert metrics["valid_epochs_in_window"] == int(expected_valid.sum())
    assert metrics["availability"] == pytest.approx(expected_valid.sum() / 81)
    errors = error[expected_valid]
    assert metrics["valid"]["rmse_deg"] == pytest.approx(math.sqrt(np.mean(errors ** 2)), abs=TOL)
    assert metrics["valid"]["max_absolute_deg"] == pytest.approx(4.0, abs=TOL)
    # hold: epochs 2.0..2.8 s have no earlier valid value -> no-heading, not zero
    assert metrics["hold_last_valid"]["no_heading_epochs_before_first_valid"] == 5
    held = []
    last = None
    for r, t_ok, e, y in zip(rel, valid, error, yaw):
        if t_ok:
            last = y
        if 2.0 <= r <= 18.0 and last is not None:
            held.append(((last - (10.0 + 3.0 * r)) + 180.0) % 360.0 - 180.0)
    held = np.asarray(held)
    assert metrics["hold_last_valid"]["held_epochs_in_window"] == held.size == 76
    assert metrics["hold_last_valid"]["rmse_deg"] == pytest.approx(math.sqrt(np.mean(held ** 2)), abs=TOL)
    assert metrics["hold_last_valid"]["max_absolute_deg"] == pytest.approx(np.max(np.abs(held)), abs=TOL)
    # gap 12.0 -> 14.0 s: last valid 12.0, next valid 14.0 -> max gap 2.0 s, two valid segments
    assert metrics["valid_segments"]["segment_count"] == 2
    assert metrics["valid_segments"]["maximum_gap_seconds"] == pytest.approx(2.0, abs=1e-6)
    assert metrics["valid"]["circular_bias_deg"] == pytest.approx(
        math.degrees(math.atan2(np.mean(np.sin(np.radians(errors))), np.mean(np.cos(np.radians(errors))))), abs=TOL)
    assert len(series) == 81


def test_wrap_safe_errors_near_180_and_zero_accepted_is_not_zero_error():
    rel = np.round(np.arange(0.0, 4.0001, 0.2), 6)
    times = BASE + rel
    yaw = np.full(rel.size, -179.0 % 360.0)  # reference 179 deg: wrap-safe error +2 deg
    table = read_heading_table(_table_bytes(times, yaw, np.ones(rel.size, dtype=bool)))
    ref = reference_yaw_ned(_trace_bytes(BASE + np.arange(-1, 6, 0.5), np.full(14, 179.0)), table["time_unix_s"])
    metrics, _ = heading_metrics(table, ref, base_time=BASE, window=(0.0, 4.0), method_id="WRAP")
    assert metrics["valid"]["rmse_deg"] == pytest.approx(2.0, abs=1e-9)
    empty = read_heading_table(_table_bytes(times, yaw, np.zeros(rel.size, dtype=bool)))
    metrics, _ = heading_metrics(empty, ref, base_time=BASE, window=(0.0, 4.0), method_id="NONE")
    assert metrics["availability"] == 0.0
    assert metrics["valid"]["rmse_deg"] is None
    assert metrics["hold_last_valid"]["no_heading_epochs_before_first_valid"] == rel.size


def test_ratio_and_rtklib_flags_are_reported_separately():
    rel = np.round(np.arange(0.0, 2.0001, 0.2), 6)
    times = BASE + rel
    truth = np.full(rel.size, 50.0)
    yaw = truth + 1.0
    valid = np.array([1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 1], dtype=bool)
    q = [1, 1, 1, 2, 2, 1, 1, -1, 1, 1, 1]
    ratio = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    ref = reference_yaw_ned(_trace_bytes(BASE + np.arange(-1, 3, 0.5), np.full(8, 50.0)), times)
    table = read_heading_table(_table_bytes(times, yaw, valid, {"rtklib_q": q, "ratio_fixed": ratio}))
    # rtklib q2 rows keep their yaw even though they are not valid
    table["body_yaw_deg"][[3, 4]] = 51.0
    metrics, _ = heading_metrics(table, ref, base_time=BASE, window=(0.0, 2.0), method_id="FLAGS")
    assert metrics["q1_fixed"]["count"] == 8 and metrics["q2_float"]["count"] == 2
    assert metrics["q2_float"]["errors"]["rmse_deg"] == pytest.approx(1.0)
    assert metrics["ratio_fixed"]["count"] == 3
    assert metrics["availability"] == pytest.approx(8 / 11)


def test_child_entry_reads_reference_once_and_checks_hashes(tmp_path):
    rel, times, truth, error, yaw, valid, trace_times, trace_truth = _case()
    table = tmp_path / "table.csv"
    table.write_bytes(_table_bytes(times, yaw, valid))
    trace = tmp_path / "reference.csv"
    trace.write_bytes(_trace_bytes(trace_times, trace_truth))
    spec = {"method_id": "SYN", "sequence_id": "SYN", "base_time": BASE, "window": [2.0, 18.0],
            "trace": str(trace), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
            "outdir": str(tmp_path / "out"),
            "variants": [{"label": "A", "heading_table": str(table),
                          "heading_table_sha256": hashlib.sha256(table.read_bytes()).hexdigest()}]}
    result = evaluate(spec)
    assert result["trace_open_count_in_child"] == 1
    assert json.loads((tmp_path / "out" / "HEADING_METRICS.json").read_text())["variants"]["A"]["availability"] > 0
    assert (tmp_path / "out" / "HEADING_ERROR_SERIES_A.csv").is_file()
    bad = dict(spec, outdir=str(tmp_path / "out2"), trace_sha256="0" * 64)
    with pytest.raises(RuntimeError, match="reference SHA-256"):
        evaluate(bad)
