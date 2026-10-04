"""Synthetic fixtures only: no workspace result or real reference is opened."""
from __future__ import annotations

import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import reproduction_evaluation as ev


def _csv(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def _fixture(tmp_path):
    out = tmp_path / "evaluation"; out.mkdir()
    raw = tmp_path / "raw"; raw.mkdir()
    reference = b"time,lat,lon,height,roll,pitch,yaw\n0,0,0,0,0,0,90\n1.4,0,0,0,0,0,90\n"
    (raw / "trace.csv").write_bytes(reference)
    roots = {"<FIXTURE>": str(tmp_path), "<RAW_ROOT>": str(raw), "<CODE_ROOT>": str(Path(__file__).resolve().parents[2])}
    definitions = {"EXT01": {0, 2, 5}, "EXT02": {1, 2, 4, 6, 7}, "EXT03": {0, 1, 3, 4, 5, 7}}
    methods, reused = [], []
    for label in (*ev.METHODS, *("RTKLIB_" + v for v in ev.VARIANTS)):
        valid = definitions.get(label, {0, 2, 4, 6})
        rows = []
        for i, t in enumerate([0, .2, .4, .6, .8, 1., 1.2, 1.4]):
            rows.append({"epoch_index": i, "gps_week": 0, "gps_tow_seconds": t, "time_unix_s": t,
                         "valid": int(i in valid), "body_yaw_deg": (10 + i if i in valid else ""),
                         "ratio_fixed": int(i in {3, 5}) if label == "EXT03" else "",
                         "rtklib_q": (1 if i in valid else 2) if label.startswith("RTKLIB") else "",
                         "acceptance_test_defined": int(label == "EXT03"),
                         "solution_state": "NATIVE_VALID" if i in valid else "ALGORITHM_FAILURE",
                         "failure_code": "" if i in valid else "NO_SOLUTION",
                         "baseline_n_m": .1 if i in valid else "", "baseline_e_m": .2 if i in valid else "",
                         "baseline_d_m": .0 if i in valid else "", "baseline_length_m": .35 if i in valid else ""})
        payload = _csv(rows)
        heading = tmp_path / (label + ".csv"); heading.write_bytes(payload)
        declaration = {"method_id": label, "heading_table": "<FIXTURE>/" + heading.name,
                       "heading_table_sha256": ev.digest(payload)}
        if label in ev.METHODS:
            methods.append(declaration)
        else:
            table = ev.frozen.read_heading_table(payload)
            table.pop("ratio_fixed")  # HX07R uses q1, not an EXT03 paper ratio.
            metrics, series = ev.frozen.heading_metrics(table, np.zeros(8), base_time=0, window=[.4, 1.2], method_id="RTKLIB")
            metrics["heading_table_sha256"] = ev.digest(payload)
            old = {"sequence_id": "BY2", "trace_sha256_observed": ev.digest(reference), "variants": {"RTKLIB": metrics}}
            metrics_path = tmp_path / (label + "_METRICS.json")
            metrics_path.write_text(json.dumps(old))
            error_path = tmp_path / (label + "_ERROR.csv"); error_path.write_bytes(_csv(series))
            declaration.update(metrics_path="<FIXTURE>/" + metrics_path.name, error_path="<FIXTURE>/" + error_path.name)
            reused.append(declaration)
    (tmp_path / "v3.csv").write_bytes(_csv([{"run_id": "FROZEN_FIXTURE", "sequence_id": "BY2", "method_id": "F04",
                 "v3_yaw_rmse_deg": "1.2345678901234567", "v3_matched_epoch_count": "999"}]))
    spec = {"schema": ev.SCHEMA, "sequence_id": "BY2", "methods": methods, "reused_variants": reused,
            "data_mode": "synthetic_unit_test", "synthetic_data_used": True, "semisynthetic_data_used": False,
            "outdir": "<FIXTURE>/evaluation", "trace": "<RAW_ROOT>/trace.csv", "trace_sha256": ev.digest(reference),
            "base_time": 0., "window": [.4, 1.2], "pair_count": 8, "v3_table": "<FIXTURE>/v3.csv"}
    return roots, spec, out


@pytest.mark.parametrize("a,b,key", [("197", "197.0", 197000000),
                                     ("1772784066.1979997", "1772784066.198", 1772784066198000),
                                     ("1.0000005", "1.00000049", 1000000)])
def test_microsecond_keys_are_fixed_decimal_half_even_not_offset_search(a, b, key):
    assert ev.time_key(a) == ev.time_key(b) == key
    assert ev.verify_time_pair([{"time_unix_s": a}, {"time_unix_s": b}]) <= 1e-6


@pytest.mark.parametrize("value", ["NaN", "Infinity", "", "UNKNOWN"])
def test_nonfinite_or_unknown_time_rejected(value):
    with pytest.raises(ev.EvaluationError): ev.time_key(value)


def test_key_collisions_and_reordered_clocks_are_not_silently_deduplicated():
    for times in (["1", "1.0000001"], ["2", "1"]):
        with pytest.raises(ev.EvaluationError):
            ev.index_time_rows([{"time_unix_s": t} for t in times])
    with pytest.raises(ev.EvaluationError):
        ev.verify_time_pair([{"time_unix_s": "1"}, {"time_unix_s": "1.000002"}])


def test_frozen_reference_wrap_interpolation_and_no_extrapolation():
    trace = b"time,lat,lon,height,roll,pitch,yaw\n0,0,0,0,0,0,359\n2,0,0,0,0,0,1\n"
    values = ev.frozen.reference_yaw_ned(trace, [-1, 0, 1, 2, 3])
    assert np.isnan(values[[0, 4]]).all()
    assert np.allclose(values[1:4], [91, 90, 89])


def test_synthetic_full_child_metrics_original_denominators_and_reused_values(tmp_path, monkeypatch):
    roots, spec, out = _fixture(tmp_path)
    reference = ev.expand(spec["trace"], roots)
    original_open = Path.open
    opens = []

    def counted_open(path, *args, **kwargs):
        if path == reference: opens.append(args[0] if args else kwargs.get("mode", "r"))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    receipt = ev.evaluate_child(spec, roots)
    assert receipt["status"] == "NUMERICALLY_COMPLETED"
    assert opens == ["rb"]
    assert receipt["reference_hash_matched"] and receipt["reference_open_count"] == 1
    results = ev.csv_rows((out / "RESULT_ROWS.csv").read_bytes())
    assert len(results) == 21
    own = {(r["method_id"], r["support"]): r for r in results}
    assert own["EXT01", "native_valid"]["paired_epoch_denominator"] == "5"
    assert own["EXT01", "native_valid"]["available_epoch_count"] == "2"
    assert own["EXT01", "native_valid"]["rmse_deg"] == str(float(np.sqrt((12**2 + 15**2) / 2)))
    assert own["EXT01", "ratio_fixed"]["status"] == "NOT_APPLICABLE_NO_ACCEPTANCE_TEST"
    assert own["EXT01", "ratio_fixed"]["scored_count"] == ""
    assert own["EXT03", "ratio_fixed"]["scored_count"] == "2"
    assert own["EXT01", "causal_held"]["scored_count"] == "5"
    errors = ev.csv_rows((out / "ERROR_SERIES.csv").read_bytes())
    assert len(errors) == 15
    held = next(r for r in errors if r["method_id"] == "EXT01" and r["epoch_index"] == "4")
    assert held["valid"] == "0" and held["error_valid_deg"] == ""
    assert held["hold_source_epoch_index"] == "2"
    assert float(held["held_age_s"]) == pytest.approx(.4)
    assert held["reference_yaw_ned_deg"] == "0.0"
    original = json.loads((tmp_path / "RTKLIB_V0_METRICS.json").read_text())
    copied = json.loads((out / "REUSED_METRICS.json").read_text())
    assert copied["RTKLIB_V0"] == original
    assert float(own["RTKLIB_V0", "native_valid"]["rmse_deg"]) == original["variants"]["RTKLIB"]["valid"]["rmse_deg"]
    common = ev.csv_rows((out / "COMMON_SUPPORT.csv").read_bytes())
    all3 = [r for r in common if r["group_id"] == "NEW_ALL3" and r["support"] == "native_valid"]
    assert all(r["status"] == "EMPTY_FINITE_INTERSECTION" and r["common_finite_count"] == "0" and r["rmse_deg"] == "" for r in all3)
    held_common = [r for r in common if r["group_id"] == "ALL7" and r["support"] == "causal_held"]
    assert len(held_common) == 7 and all(r["common_finite_count"] == "5" for r in held_common)
    assert len(json.loads((out / "COMMON_SUPPORT_KEYS.json").read_text())) == 54
    # Missing/invalid yaw remains visible; no value is filled with zero.
    assert sum(r["valid"] == "0" for r in errors) == 7
    assert ev.csv_rows((out / "V3_REFERENCE.csv").read_bytes())[0]["comparison_status"].startswith("DIFFERENT_")


def test_reference_hash_mismatch_retains_failure_without_metrics_or_retry(tmp_path):
    roots, spec, out = _fixture(tmp_path)
    spec["trace_sha256"] = "0" * 64
    with pytest.raises(ev.EvaluationError, match="reference SHA256"):
        ev.evaluate_child(spec, roots)
    receipt = json.loads((out / "CHILD_RECEIPT.json").read_text())
    assert receipt["status"] == "FAILED_RETAINED_NO_RETRY"
    assert receipt["reference_open_attempts"] == receipt["reference_open_count"] == 1
    assert not (out / "HEADING_METRICS.json").exists()
    with pytest.raises(FileExistsError): ev.evaluate_child(spec, roots)


def test_heading_hash_failure_happens_before_reference_open(tmp_path):
    roots, spec, out = _fixture(tmp_path)
    spec["methods"][0]["heading_table_sha256"] = "f" * 64
    with pytest.raises(ev.EvaluationError, match="source SHA256"):
        ev.evaluate_child(spec, roots)
    receipt = json.loads((out / "CHILD_RECEIPT.json").read_text())
    assert receipt["reference_open_count"] == receipt["reference_open_attempts"] == 0


def test_missing_old_variant_does_not_remove_its_common_comparison_slots(tmp_path):
    roots, spec, out = _fixture(tmp_path)
    spec["reused_variants"][0]["error_path"] = "<FIXTURE>/absent.csv"
    receipt = ev.evaluate_child(spec, roots)
    assert receipt["status"] == "NUMERICALLY_COMPLETED" and receipt["reuse_limitations_count"] == 1
    result = ev.csv_rows((out / "RESULT_ROWS.csv").read_bytes())
    quoted = [r for r in result if r["method_id"] == "RTKLIB_V0"]
    assert len(quoted) == 3
    assert all(r["paired_epoch_denominator"] == "5" for r in quoted)
    assert all(r["status"] == "ORIGINAL_METRIC_QUOTED_COMMON_SUPPORT_REJECTED" for r in quoted)
    rows = ev.csv_rows((out / "COMMON_SUPPORT.csv").read_bytes())
    assert any(r["status"] == "MISSING_MEMBER" and r["group_id"] == "EXT01__RTKLIB_V0" for r in rows)


def test_breaks_preserve_invalid_epochs_wrap_jumps_and_physical_time_gaps():
    rows = [{"epoch_index": i, "t_rel_s": t, "valid": valid, "yaw": yaw} for i, t, valid, yaw in
            [(0, 0, "1", 359), (1, .2, "1", 1), (2, .4, "0", 20), (3, .6, "1", 2), (4, 1.0, "1", 3)]]
    x, y = ev.broken_line(rows, "yaw", valid_field="valid", wrap=True)
    assert np.isnan(x).sum() == 2  # wrap and actual 0.4 s gap
    assert np.isnan(y).sum() == 3  # plus invalid native epoch
    assert x[np.isfinite(x)].tolist() == [0, .2, .4, .6, 1.]
    assert y[np.isfinite(x)].tolist()[3:] == [2, 3]  # first points after gaps retained


def test_plot_only_saved_series_no_reference_and_failure_keeps_numeric_receipt(tmp_path, monkeypatch):
    roots, spec, out = _fixture(tmp_path)
    ev.evaluate_child(spec, roots)
    before = (out / "CHILD_RECEIPT.json").read_bytes()
    reference = ev.expand(spec["trace"], roots)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == reference: raise AssertionError("plot reopened reference")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    receipt = ev.plot_saved(out, "BY2")
    assert receipt["status"] == "COMPLETED_VISUAL_REVIEW_PENDING"
    png = (out / "figures/attempt_001/HEADING_COMPARISON.png").read_bytes()
    assert struct.unpack(">I", png[16:20])[0] >= 4096
    assert (out / "figures/attempt_001/HEADING_COMPARISON.pdf").read_bytes().startswith(b"%PDF")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "subplots", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("synthetic render failure")))
    failed = ev.plot_saved(out, "BY2")
    assert failed["status"] == "PLOT_FAILED_NUMERIC_RESULTS_PRESERVED"
    assert (out / "CHILD_RECEIPT.json").read_bytes() == before
    assert (out / "figures/attempt_001/HEADING_COMPARISON.png").read_bytes() == png


def _strace_line(path, mode="O_RDONLY", result=3):
    encoded = "".join("\\x%02x" % x for x in path.encode())
    return f'123 openat(AT_FDCWD, "{encoded}", {mode}|O_CLOEXEC) = {result}\n'


@pytest.mark.parametrize("extra,passed", [("none", True), ("duplicate", False), ("write", False), ("other_raw", False)])
def test_strace_reference_audit_distinguishes_counts_and_forbidden_opens(tmp_path, extra, passed):
    roots = {"<RAW_ROOT>": str(tmp_path)}
    ref = str(tmp_path / "参考.csv")
    lines = '123 execve("\\x70", [], 0x1) = 0\n' + _strace_line(ref, "O_RDWR" if extra == "write" else "O_RDONLY")
    if extra == "duplicate": lines += _strace_line(ref)
    if extra == "other_raw": lines += _strace_line(str(tmp_path / "gnss-raw.csv"))
    audit = ev.audit_reference_opens(lines.encode(), roots, "<RAW_ROOT>/参考.csv")
    assert audit["passed"] == passed
    assert audit["reference_successful_opens"] == (2 if extra == "duplicate" else 1)


def test_one_synthetic_evaluator_subprocess_under_real_strace(tmp_path):
    assert shutil.which("strace"), "test environment must support the declared child audit"
    roots, spec, out = _fixture(tmp_path)
    (tmp_path / "roots.json").write_text(json.dumps({"aliases": roots}))
    (out / "SPEC.json").write_text(json.dumps(spec))
    argv = ["strace", "-f", "-qq", "-xx", "-s", "8192", "-e", "trace=open,openat,execve", "-o", str(out / "audit.strace"),
            sys.executable, "-m", ev.MODULE, "--roots", str(tmp_path / "roots.json"), "--child-spec", str(out / "SPEC.json")]
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"), PYTHONDONTWRITEBYTECODE="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    result = subprocess.run(argv, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    audit = ev.audit_reference_opens((out / "audit.strace").read_bytes(), roots, spec["trace"])
    assert audit["passed"] and audit["successful_execve_count"] == audit["reference_successful_opens"] == 1
    assert json.loads((out / "CHILD_RECEIPT.json").read_text())["synthetic_data_used"] is True


@pytest.mark.parametrize("bad_gate", [None, "incomplete", "wrong_heading", "wrong_pair_count"])
def test_prepare_metadata_only_native_gates(tmp_path, monkeypatch, bad_gate):
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "module.py").write_text("# synthetic fixture\n")
    (repo / "protocol.md").write_text("Synthetic fixture only.\n")
    monkeypatch.setattr(ev, "FROZEN_PINS", {})
    monkeypatch.setattr(ev, "SOURCE_RELATIVE", "module.py")
    monkeypatch.setattr(ev, "PROTOCOL_RELATIVE", "protocol.md")
    roots = {"<CODE_ROOT>": str(repo), "<EXT_REPRO_ROOT>": str(tmp_path / "results"),
             "<CLEAN_ROOT>": str(tmp_path / "clean"), "<RAW_ROOT>": str(tmp_path / "raw")}
    config = tmp_path / "roots.json"; config.write_text(json.dumps({"aliases": roots}))
    input_path = tmp_path / "results/inputs/BY2/INPUT.json"; input_path.parent.mkdir(parents=True)
    payload = json.dumps({"sequence": "BY2", "pair_count": 2, "base_time": 0, "window_seconds": [0, 1]}).encode()
    input_path.write_bytes(payload)
    for method in ev.METHODS:
        run_id = f"BY2__{method}__RAW_REPRO_V1"
        prefix = f"<EXT_REPRO_ROOT>/runs/{run_id}"
        run = {"run_id": run_id, "sequence": "BY2", "method": method, "status": "COMPLETED", "completed_epochs": 2,
               "input_manifest_sha256": ev.digest(payload), "code_commit": "synthetic_fixture", "data_mode": "real_raw",
               **{key: False for key in ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
                                        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric")},
               "outputs": {"HEADING.csv": {"path": prefix + "/HEADING.csv", "sha256": "not_opened_in_prepare"}}}
        if method == "EXT01":
            if bad_gate == "incomplete": run["status"] = "RUNNING"
            elif bad_gate == "wrong_pair_count": run["completed_epochs"] = 1
            elif bad_gate == "wrong_heading": run["outputs"]["HEADING.csv"]["path"] = "<EXT_REPRO_ROOT>/other.csv"
        path = ev.expand(prefix + "/RUN.json", roots); path.parent.mkdir(parents=True); path.write_text(json.dumps(run))
    for variant in ev.VARIANTS:
        prefix = f"<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/BY2_{variant}"
        spec = {"sequence_id": "BY2", "method_id": "RTKLIB", "base_time": 0, "window": [0, 1],
                "trace": "<RAW_ROOT>/does_not_exist.csv", "trace_sha256": "not_opened_in_prepare",
                "outdir": prefix + "/eval/OUTPUT", "variants": [{"label": "RTKLIB", "heading_table": prefix + "/HEADING_TABLE.csv",
                                                                  "heading_table_sha256": "not_opened_in_prepare"}]}
        path = ev.expand(prefix + "/eval/SPEC.json", roots); path.parent.mkdir(parents=True); path.write_text(json.dumps(spec))
    if bad_gate:
        with pytest.raises(ev.EvaluationError): ev.prepare_spec(config, "BY2", verify_committed=False)
    else:
        _, spec = ev.prepare_spec(config, "BY2", verify_committed=False)
        assert spec["trace"] == "<RAW_ROOT>/does_not_exist.csv"
        assert len(spec["methods"]) == 3 and len(spec["reused_variants"]) == 4
    assert not (tmp_path / "results/evaluation").exists()


def test_parent_refuses_existing_output_before_child(tmp_path, monkeypatch):
    roots, spec, out = _fixture(tmp_path)
    roots["<EXT_REPRO_ROOT>"] = str(tmp_path)
    monkeypatch.setattr(ev, "prepare_spec", lambda *_: (roots, spec))
    monkeypatch.setattr(ev.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("child should not run")))
    with pytest.raises(FileExistsError): ev.run("unused_metadata_fixture", "BY2")
    assert not (out / "CHILD_RECEIPT.json").exists()


@pytest.mark.parametrize("corruption", ["swap_valid_same_count", "swap_q_same_count", "reference_mask", "hold_source"])
def test_old_error_mask_corruption_never_enters_common_support(tmp_path, corruption):
    roots, spec, out = _fixture(tmp_path)
    path = tmp_path / "RTKLIB_V0_ERROR.csv"
    errors = ev.csv_rows(path.read_bytes())
    before_count = sum(ev.number(row["error_valid_deg"]) is not None for row in errors)
    if corruption == "swap_valid_same_count":
        for key in ("valid", "error_valid_deg"):
            errors[0][key], errors[1][key] = errors[1][key], errors[0][key]
    elif corruption == "swap_q_same_count":
        errors[0]["rtklib_q"], errors[1]["rtklib_q"] = errors[1]["rtklib_q"], errors[0]["rtklib_q"]
    elif corruption == "reference_mask":
        errors[0]["reference_supported"] = "0"
    else:
        errors[1]["hold_source_epoch_index"] = "7"  # future, noncausal source
    assert sum(ev.number(row["error_valid_deg"]) is not None for row in errors) == before_count
    path.write_bytes(_csv(errors))
    result = ev.evaluate_child(spec, roots)
    assert result["status"] == "NUMERICALLY_COMPLETED" and result["reused_method_count"] == 3
    common = ev.csv_rows((out / "COMMON_SUPPORT.csv").read_bytes())
    assert all(row["status"] == "MISSING_MEMBER" and row["common_finite_count"] == ""
               for row in common if row["group_id"] == "EXT01__RTKLIB_V0")
    saved = ev.csv_rows((out / "REUSED_ERROR_SERIES.csv").read_bytes())
    assert not any(row["method_id"] == "RTKLIB_V0" for row in saved)


@pytest.mark.parametrize("field", ["error_convention", "reference_semantics"])
def test_old_metric_semantics_must_match_frozen_contract(tmp_path, field):
    roots, spec, out = _fixture(tmp_path)
    path = tmp_path / "RTKLIB_V0_METRICS.json"
    old = json.loads(path.read_text())
    old["variants"]["RTKLIB"][field] = "REVERSED_OR_DIFFERENT_SEMANTICS"
    path.write_text(json.dumps(old))
    receipt = ev.evaluate_child(spec, roots)
    assert receipt["reused_method_count"] == 3 and receipt["reuse_limitations_count"] == 1
    common = ev.csv_rows((out / "COMMON_SUPPORT.csv").read_bytes())
    assert all(row["status"] == "MISSING_MEMBER" for row in common if row["group_id"] == "EXT02__RTKLIB_V0")


def test_late_support_failure_is_atomic_and_cannot_leave_common_member(tmp_path, monkeypatch):
    roots, spec, out = _fixture(tmp_path)
    original = ev.support_details
    fired = []

    def late_failure(*args, **kwargs):
        if args[-1] == "RTKLIB_Q1_FIXED" and not fired:
            fired.append(True)
            raise ev.EvaluationError("synthetic late support validation failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(ev, "support_details", late_failure)
    receipt = ev.evaluate_child(spec, roots)
    assert fired and receipt["reused_method_count"] == 3
    rows = ev.csv_rows((out / "COMMON_SUPPORT.csv").read_bytes())
    assert all(row["status"] == "MISSING_MEMBER" for row in rows if row["group_id"] == "EXT03__RTKLIB_V0")


def test_recorded_error_pin_is_verified_and_unknown_pin_is_explicit(tmp_path):
    roots, spec, out = _fixture(tmp_path)
    spec["reused_variants"][0]["error_recorded_pin"] = {"sha256": "0" * 64, "source": "synthetic_historical_pin"}
    receipt = ev.evaluate_child(spec, roots)
    assert receipt["reused_method_count"] == 3
    sources = ev.csv_rows((out / "SOURCE_FILES.csv").read_bytes())
    errors = [row for row in sources if row["role"] == "reused_error_series"]
    assert errors[0]["recorded_pin_matches"] == "False"
    assert all(row["hash_status"] == "NEW_READ_HASH_NOT_HISTORICAL_PIN" for row in errors[1:])


def test_causal_hold_never_backfills_before_first_native_valid():
    times = np.array([0., .2, .4, .6])
    table = {"epoch_index": np.arange(4), "time_unix_s": times,
             "valid": np.array([False, False, True, False]), "body_yaw_deg": np.array([np.nan, np.nan, 15., np.nan])}
    metrics, rows = ev.frozen.heading_metrics(table, np.zeros(4), base_time=0, window=[0, .6], method_id="EXT01")
    assert metrics["denominator_native_paired_epochs_in_window"] == 4
    assert metrics["hold_last_valid"]["count"] == 2
    assert metrics["hold_last_valid"]["no_heading_epochs_before_first_valid"] == 2
    assert all(row["error_hold_deg"] == "" and row["hold_source_epoch_index"] == -1 for row in rows[:2])
    assert rows[2]["error_valid_deg"] == "15.0" and rows[3]["error_hold_deg"] == "15.0"


def test_plot_display_wrap360_status_lanes_preserve_errors_and_large_baseline(tmp_path, monkeypatch):
    # This fixture starts from a saved derived CSV. No evaluator/reference is
    # invoked, even synthetically, for the display-only amendment.
    out = tmp_path / "saved_results"; out.mkdir()
    rows = []
    for method in ev.METHODS:
        for i in range(5):
            rows.append({"method_id": method, "epoch_index": i, "t_rel_s": i * .2,
                         "valid": int(i != 4), "ratio_fixed": int(i == 2) if method == "EXT03" else "",
                         "native_body_yaw_deg": [-179, 179, -1, 1, ""][i],
                         "reference_yaw_ned_deg": [181, 179, 359, 1, 2][i],
                         "error_valid_deg": [20, -20, -179, 179, ""][i],
                         "baseline_n_m": [4000, -.1, .1, .1, ""][i],
                         "baseline_e_m": .2, "baseline_length_m": [5000, .35, .35, .35, ""][i]})
    original = _csv(rows)
    (out / "ERROR_SERIES.csv").write_bytes(original)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_hex
    closed = []
    original_close = plt.close
    monkeypatch.setattr(plt, "close", lambda fig: closed.append(fig))
    result = ev.plot_saved(out, "BY2")
    assert result["status"] == "COMPLETED_VISUAL_REVIEW_PENDING"
    figure = next(fig for fig in closed if hasattr(fig, "axes"))
    try:
        heading, error, state, baseline = figure.axes
        for line in heading.lines[:3]:
            y = line.get_ydata(); x = line.get_xdata()
            assert y[np.isfinite(y)].tolist() == [181, 179, 359, 1]
            assert np.isnan(x).sum() == 1  # only actual 359 -> 1 display wrap
        assert heading.lines[3].get_ydata()[np.isfinite(heading.lines[3].get_ydata())].tolist() == [181, 179, 359, 1, 2]
        for line in error.lines:
            y = line.get_ydata()
            assert y[np.isfinite(y)].tolist() == [20, -20, -179, 179]
        for i, color in enumerate(("#0072b2", "#d55e00", "#009e73")):
            invalid, valid, fixed = state.collections[3*i:3*i+3]
            assert np.allclose(invalid.get_offsets()[:, 1], i - .16)
            assert np.allclose(valid.get_offsets()[:, 1], i)
            assert to_hex(invalid.get_edgecolors()[0]) == "#7f7f7f"
            assert to_hex(valid.get_facecolors()[0]) == color
            if i == 2:
                assert np.allclose(fixed.get_offsets()[:, 1], i + .16)
                assert to_hex(fixed.get_edgecolors()[0]) == "#000000"
        assert max(float(np.nanmax(line.get_ydata())) for line in baseline.lines) == 5000
        assert baseline.get_ylim()[1] > 5000
        assert (out / "ERROR_SERIES.csv").read_bytes() == original
        assert result["source_sha256"] == ev.digest(original)
        assert result["reference_opens"] == result["evaluator_invocations"] == 0
        assert result["plot_implementation"] == "WRAP360_STATUS_LANES_V2"
    finally:
        original_close(figure)

@pytest.mark.parametrize("native_version,native_attempt", [("V1", 1), ("V2", 1), ("V2", 2)])
def test_prepare_requires_explicit_matching_native_version_without_reference_open(tmp_path, monkeypatch, native_version, native_attempt):
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "module.py").write_text("# synthetic metadata fixture\n")
    (repo / "protocol.md").write_text("Synthetic protocol fixture.\n")
    monkeypatch.setattr(ev, "FROZEN_PINS", {})
    monkeypatch.setattr(ev, "V2_FROZEN_PINS", {})
    monkeypatch.setattr(ev, "SOURCE_RELATIVE", "module.py")
    monkeypatch.setattr(ev, "PROTOCOL_RELATIVE", "protocol.md")
    roots = {"<CODE_ROOT>": str(repo), "<EXT_REPRO_ROOT>": str(tmp_path / "results"),
             "<CLEAN_ROOT>": str(tmp_path / "clean"), "<RAW_ROOT>": str(tmp_path / "raw")}
    config = tmp_path / "roots.json"; config.write_text(json.dumps({"aliases": roots}))
    info = {"sequence": "BY2", "pair_count": 2, "base_time": 0, "window_seconds": [0, 1]}
    input_path = tmp_path / "results/inputs/BY2/INPUT.json"; input_path.parent.mkdir(parents=True)
    payload = json.dumps(info).encode(); input_path.write_bytes(payload)
    for method in ev.METHODS:
        identity = ev.native_run_identity("BY2", method, native_version, native_attempt)
        prefix = "<EXT_REPRO_ROOT>/runs/" + identity
        run = {"run_id": identity, "attempt": native_attempt, "sequence": "BY2", "method": method, "status": "COMPLETED", "completed_epochs": 2,
               "input_manifest_sha256": ev.digest(payload), "code_commit": "synthetic_fixture", "data_mode": "real_raw",
               **{key: False for key in ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
                                        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric")},
               "outputs": {"HEADING.csv": {"path": prefix + "/HEADING.csv", "sha256": "never_read_in_prepare"}}}
        path = ev.expand(prefix + "/RUN.json", roots); path.parent.mkdir(parents=True); path.write_text(json.dumps(run))
    for variant in ev.VARIANTS:
        prefix = "<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07R/RUNS/BY2_" + variant
        previous = {"sequence_id": "BY2", "method_id": "RTKLIB", "base_time": 0, "window": [0, 1],
                    "trace": "<RAW_ROOT>/deliberately_nonexistent.csv", "trace_sha256": "never_read_in_prepare",
                    "outdir": prefix + "/eval/OUTPUT", "variants": [{"label": "RTKLIB", "heading_table": prefix + "/HEADING.csv",
                    "heading_table_sha256": "never_read_in_prepare"}]}
        path = ev.expand(prefix + "/eval/SPEC.json", roots); path.parent.mkdir(parents=True); path.write_text(json.dumps(previous))
    _, spec = ev.prepare_spec(config, "BY2", native_version=native_version, native_attempt=native_attempt, verify_committed=False)
    assert spec["native_version"] == native_version and spec["native_attempt"] == native_attempt
    assert all(item["run_id"] == ev.native_run_identity("BY2", item["method_id"], native_version, native_attempt) for item in spec["methods"])
    assert not ev.expand(spec["trace"], roots).exists()
    with pytest.raises((ev.EvaluationError, FileNotFoundError)):
        ev.prepare_spec(config, "BY2", native_version="V2" if native_version == "V1" else "V1", verify_committed=False)
    if native_version == "V2":
        with pytest.raises(FileNotFoundError):
            ev.prepare_spec(config, "BY2", native_version="V2", native_attempt=3, verify_committed=False)
        path = ev.expand(spec["methods"][0]["run_path"], roots)
        broken = json.loads(path.read_text()); broken["attempt"] = native_attempt + 1; path.write_text(json.dumps(broken))
        with pytest.raises(ev.EvaluationError, match="identity gate"):
            ev.prepare_spec(config, "BY2", native_version="V2", native_attempt=native_attempt, verify_committed=False)


def test_evaluation_overlay_rejects_implicit_v1_before_sources_or_outputs():
    with pytest.raises(ev.EvaluationError, match="explicit native V2"):
        ev.run("deliberately_nonexistent", "BY2", allow_source_overlay=True)


@pytest.mark.parametrize("attempt", [0, -1, True, 1.5])
def test_native_identity_rejects_invalid_attempt(attempt):
    with pytest.raises(ev.EvaluationError, match="positive integer"):
        ev.native_run_identity("BY2", "EXT01", "V2", attempt)


def test_retry_identity_requires_explicit_v2_and_preserves_original_defaults():
    assert ev.native_run_identity("BY2", "EXT01", "V1", 1) == "BY2__EXT01__RAW_REPRO_V1"
    assert ev.native_run_identity("BY2", "EXT01", "V2", 2) == "BY2__EXT01__RAW_REPRO_V2__TECH_RETRY_2"
    with pytest.raises(ev.EvaluationError, match="explicit native V2"):
        ev.native_run_identity("BY2", "EXT01", "V1", 2)
