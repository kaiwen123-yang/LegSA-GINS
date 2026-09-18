"""Synthetic-only reporting fixtures; no native/evaluator/reference input."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from legsa_gins.paper_rebuild.hext import t5a_reporting as report

FREEZE = "a" * 40
MATRIX = {sequence: {"configurations": ["F02", "F04"],
                     "variants": ["R1", "R5"] + (["R1F", "R5F"] if sequence == "BY2O" else [])}
          for sequence in report.SEQUENCES}
WINDOWS = {"BY2": [66., 340.], "BY2H": [413., 683.], "BY2O": [3186., 3563.]}


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return _sha(payload)


def _json(path, payload):
    return _write(path, json.dumps(payload).encode())


def _csv_bytes(rows, fields=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields or list(dict.fromkeys(key for row in rows for key in row)))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _frozen_row(sequence, profile, version, source="UNAVAILABLE"):
    row = dict.fromkeys(report.TABLE_FIELDS, "UNAVAILABLE")
    row.update(sequence_id=sequence, method_id=profile, config="NOT_APPLICABLE_V21",
               start_convention=report.FROZEN, evaluator_contract="evaluator_contract_" + version,
               evaluation_status="COMPLETED", failure_classification="NONE", code_commit="f" * 40,
               h_rmse_m="1.230000000000000", yaw_rmse_deg="2.50000000", matched_epoch_count="7",
               output_epoch_count="7", coverage_ratio="1.00000000", error_series_source=source,
               main_row="True", manuscript_row="True", notes='{"result_reused": true}')
    return row


def _errors(sequence="BY2O", offset=0.):
    times = ([3186., 3369.94, 3411.95, 3440., 3495.94, 3508.94, 3563.]
             if sequence == "BY2O" else np.linspace(*WINDOWS[sequence], 7))
    row = np.arange(1., 8.) + offset
    return pd.DataFrame({"time": times, "horizontal_err_m": row / 10,
                         "position_3d_err_m": row / 9, "err_u_m": -row / 20,
                         "yaw_err_deg": row - 4, "roll_err_deg": row / 5, "pitch_err_deg": -row / 7})


def test_frozen_tokens_and_decimal_deltas_survive_and_absent_slots_are_unavailable():
    rows = [(index, _frozen_row(sequence, profile, "v3"))
            for index, (sequence, profile) in enumerate(((s, p) for s in report.SEQUENCES for p in report.PROFILES), 2)]
    payload = {"row": {"sequence_id": "BY2", "configuration_id": "F02", "variant": "R1",
                        "evaluator_contract": "evaluator_contract_v3", "evaluation_status": "COMPLETED",
                        "h_rmse_m": "1.240000000000000", "yaw_rmse_deg": "2.0", "coverage_ratio": "0.5",
                        "matched_epoch_count": "5", "output_epoch_count": "6"},
               "audit": {"passed": True, "trace_open_count": 1}, "body_frame_bias": {}}
    result = report.sensitivity_rows(rows, [payload], MATRIX, "v3")
    assert len(result) == 22
    frozen = result[0]
    assert all(frozen[field] == rows[0][1][field] for field in report.TABLE_FIELDS)
    candidate = result[1]
    assert candidate["delta_h_rmse_m"] == "0.010000000000000"
    assert candidate["delta_matched_epoch_count"] == "-2"
    assert candidate["delta_coverage_ratio"] == "-0.50000000"
    assert candidate["delta_body_forward_bias_m"] == "UNAVAILABLE"
    assert result[2]["evaluation_status"] == "NOT_RUN"
    assert result[2]["h_rmse_m"] == result[2]["delta_h_rmse_m"] == "UNAVAILABLE"
    payload["audit"]["passed"] = False
    with pytest.raises(ValueError, match="capture/disposition"):
        report.sensitivity_rows(rows, [payload], MATRIX, "v3")


def test_unavailable_capture_never_leaks_stale_metrics_or_bias():
    rows = [(index, _frozen_row(sequence, profile, "v3"))
            for index, (sequence, profile) in enumerate(((s, p) for s in report.SEQUENCES for p in report.PROFILES), 2)]
    payload = {"row": {"sequence_id": "BY2", "configuration_id": "F02", "variant": "R1",
                        "evaluator_contract": "evaluator_contract_v3", "evaluation_status": "UNAVAILABLE_EVALUATION_FAILED",
                        "h_rmse_m": 0., "body_forward_bias_m": 0.},
               "body_frame_bias": {"forward_signed_mean_m": 0.}}
    row = report.sensitivity_rows(rows, [payload], MATRIX, "v3")[1]
    assert row["h_rmse_m"] == row["body_forward_bias_m"] == row["delta_h_rmse_m"] == "UNAVAILABLE"


def test_segment_closed_union_and_complement_use_all_error_rows():
    rows = report.derive_segments(_errors(), profile="F02", variant="R1", version="v3",
                                  window=WINDOWS["BY2O"], source="synthetic")
    indexed = {row["segment_id"]: row for row in rows}
    assert [indexed[key]["count"] for key in report.REGIONS] == [7, 2, 2, 4, 3]
    assert indexed["inside_union"]["count"] + indexed["outside"]["count"] == indexed["full"]["count"]
    assert indexed["inside_union"]["yaw_median_absolute_deg"] == 1.5
    assert indexed["outside"]["yaw_rmse_deg"] == pytest.approx(np.sqrt(6.))


def test_gating_counts_keep_accounting_failure_visible_without_substitution():
    log = pd.DataFrame({"gnss_time": [3369.94, 3400., 3500., 3520.], "yaw_update": [1, 1, 1, 0],
                        "yaw_mode": ["NORMAL", "DOWNWEIGHT", "REJECT", "NONE"]})
    rows = report.gating_rows(log, sequence="BY2O", profile="F02", variant="R1", window=WINDOWS["BY2O"], source="synthetic")
    assert rows[0]["attempted"] == 3 and rows[0]["accepted"] == 2 and rows[0]["rejected"] == 1
    assert all(row["accounting_consistent"] for row in rows)
    log.loc[3, "yaw_mode"] = "NORMAL"
    rows = report.gating_rows(log, sequence="BY2O", profile="F02", variant="R1", window=WINDOWS["BY2O"], source="synthetic")
    assert rows[0]["status"] == "UNAVAILABLE_ACCOUNTING_MISMATCH"
    assert rows[0]["accepted"] == 3


def test_sources_reject_trace_raw_symlink_and_hash_mismatch_before_use(tmp_path):
    sources = report.Sources({"raw_root": tmp_path / "raw", "t5a_scratch": tmp_path / "scratch"})
    with pytest.raises(PermissionError):
        sources.read(tmp_path / "raw" / "source.csv")
    with pytest.raises(PermissionError):
        sources.read(tmp_path / "trace_secret.csv")
    path = tmp_path / "scratch" / "allowed.csv"
    _write(path, b"synthetic")
    with pytest.raises(ValueError, match="SHA-256"):
        sources.read(path, "0" * 64)
    alias = sources.alias(path)
    assert sources.resolve(alias) == path
    assert sources.alias_values({"metric": "1.23000000", "path": str(path)}) == {"metric": "1.23000000", "path": "<T5A_SCRATCH>/allowed.csv"}


def _synthetic_attempt(tmp_path, monkeypatch):
    scratch, clean, code = tmp_path / "scratch", tmp_path / "clean", tmp_path / "code"
    scratch.mkdir()
    root = clean / "stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES"
    runtime_specs, h04_sources, frozen_tables, frozen_segments = {}, [], {"v3": [], "v2": []}, []
    for sequence in report.SEQUENCES:
        errors = _errors(sequence)
        for profile in report.PROFILES:
            run_id = sequence + "_" + profile
            attempt = clean / "retained" / run_id
            config = {"enable_multi_state_qm": False, "enable_qa_fallback": False}
            cfg_hash = _write(attempt / "solver/PROTOCOL_V21_RUNTIME_CONFIG.yaml", yaml.safe_dump(config).encode())
            runtime_specs[run_id] = {"run_id": run_id, "sha256": cfg_hash}
            retained = {}
            log = pd.DataFrame({"gnss_time": errors.time, "yaw_update": [1] * len(errors), "yaw_mode": ["NORMAL"] * len(errors)})
            log_name = "solver/PORT_GNSS_UPDATE_TRACE.csv.gz"
            retained[log_name] = {"sha256": _write(attempt / log_name, gzip.compress(log.to_csv(index=False).encode(), mtime=0))}
            for version in ("v3", "v2"):
                name = "evaluation/" + version + "/error_series.csv.gz"
                retained[name] = {"sha256": _write(attempt / name, gzip.compress(errors.to_csv(index=False).encode(), mtime=0))}
                frozen_tables[version].append(_frozen_row(sequence, profile, version, str(attempt / name)))
                if sequence == "BY2O":
                    rows = report.derive_segments(errors, profile=profile, variant=report.FROZEN, version=version,
                                                  window=WINDOWS[sequence], source="<CLEAN_ROOT>/synthetic_frozen_errors")
                    frozen_segments.extend(rows)
            receipt = attempt / "ARCHIVE_RECEIPT.json"
            digest = _json(receipt, {"retained_files": retained})
            h04_sources.append({"path": str(receipt), "sha256": digest})
    pins = {}
    for version, rows in frozen_tables.items():
        pins[version] = _write(root / "08_AGGREGATE" / ("HORIZONTAL_TABLE_" + version.upper() + "_THREE_SEQUENCES.csv"), _csv_bytes(rows, report.TABLE_FIELDS))
    monkeypatch.setattr(report, "PINS", pins)
    manifest_path = root / "11_READONLY_CLOSEOUT_H_EXT_04L/DATA_MANIFEST.json"
    manifest_sha = _json(manifest_path, {"sources": h04_sources})
    segment_path = root / "11_READONLY_CLOSEOUT_H_EXT_04L/BY2O_SEGMENT_SUMMARY.csv"
    segment_sha = _write(segment_path, _csv_bytes(frozen_segments))
    contract = {"matrix": MATRIX, "definitions": {"D1": {"windows_s": WINDOWS}},
                "frozen": {"hext04l_data_manifest": {"path": str(manifest_path), "sha256": manifest_sha},
                           "hext04l_segments": {"path": str(segment_path), "sha256": segment_sha},
                           "runtime_configs": runtime_specs,
                           "runtime_config_template": str(clean / "retained/<RUN_ID>/solver/PROTOCOL_V21_RUNTIME_CONFIG.yaml")}}
    contract_path = code / "contract.yaml"
    contract_sha = _write(contract_path, yaml.safe_dump(contract).encode())
    local_path = code / "local.yaml"
    _write(local_path, yaml.safe_dump({"paths": {"t5a_scratch": str(scratch), "clean_root": str(clean), "code_root": str(code), "raw_root": str(tmp_path / "raw")}}).encode())
    evaluations, natives, diagnostics = [], [], []
    for sequence in report.SEQUENCES:
        errors = _errors(sequence, .1)
        for profile in report.PROFILES:
            for variant in MATRIX[sequence]["variants"]:
                native = scratch / "03_NATIVE" / sequence / profile / variant
                config_hash = _write(native / "T5A_RUNTIME_CONFIG.yaml", b"enable_multi_state_qm: false\nenable_qa_fallback: false\n")
                log = pd.DataFrame({"gnss_time": errors.time, "yaw_update": [1] * len(errors), "yaw_mode": ["NORMAL"] * len(errors)})
                log_hash = _write(native / "PORT_GNSS_UPDATE_TRACE.csv", log.to_csv(index=False).encode())
                natives.append({"sequence_id": sequence, "configuration_id": profile, "variant": variant,
                                "output_root": str(native), "config_hash": config_hash,
                                "file_hashes": {"PORT_GNSS_UPDATE_TRACE.csv": log_hash}})
                for version in ("v3", "v2"):
                    eval_root = scratch / "04_EVAL" / version / sequence / profile / variant
                    error_path = eval_root / "FROZEN_EVALUATOR/error_series.csv"
                    error_payload = errors.to_csv(index=False).encode()
                    digest = _write(error_path, error_payload)
                    compressed_digest = _write(error_path.with_suffix(".csv.gz"), gzip.compress(error_payload, mtime=0))
                    _json(eval_root / "OUTPUT_SEAL.json", {"files": {
                        "FROZEN_EVALUATOR/error_series.csv": digest,
                        "FROZEN_EVALUATOR/error_series.csv.gz": compressed_digest}})
                    row = {**_frozen_row(sequence, profile, version), "configuration_id": profile, "variant": variant,
                           "h_rmse_m": "1.24", "error_series_source": str(error_path.parent), "code_commit": FREEZE}
                    evaluations.append({"row": row, "audit": {"passed": True, "trace_open_count": 1}, "body_frame_bias": {}})
        diagnostic_path = scratch / "02_PROVIDER_TABLES" / sequence / "D4/SOURCE_CONSISTENCY.json"
        _json(diagnostic_path, {"source_consistency_rows": [
            {"category": "delta", "scope": "evaluation_window", "quality": "all", "count": 7, "mean_deg": .1},
            {"category": "timing", "scope": "evaluation_window", "quality": "all", "count": 7, "mean_s": .01}],
            "histograms": [{"scope": "evaluation_window", "quality": "all", "bin_left_deg": low,
                            "bin_right_deg": high, "count": count} for low, high, count in ((-180, 0, 3), (0, 180, 4))]})
        diagnostics.append({"sequence_id": sequence, "path": str(diagnostic_path)})
    _json(scratch / "07_HANDOFF/EXECUTION_SUMMARY.json", {
        "status": "COMPLETED_SYNTHETIC_FIXTURE", "code_commit": FREEZE, "contract_sha256": contract_sha,
        "data_mode": "synthetic", "synthetic_data_used": True, "semisynthetic_data_used": False,
        "native": natives, "evaluations": evaluations, "diagnostics": diagnostics})
    return scratch, contract_path, local_path


def test_complete_synthetic_aggregation_is_22_rows_per_version_with_verified_full_series(tmp_path, monkeypatch):
    scratch, contract, local = _synthetic_attempt(tmp_path, monkeypatch)
    result = report.aggregate_t5a(scratch, code_freeze=FREEZE, contract_path=contract, local_paths_path=local)
    assert result["synthetic_data_used"] is True
    assert result["table_rows"] == {"v3": 22, "v2": 22}
    assert result["segment_rows"] == 100 and result["gating_rows"] == 74 and result["yaw_series_rows"] == 44
    assert result["trace_open_count"] == result["native_invocation_count"] == result["evaluator_invocation_count"] == 0
    output = scratch / "05_AGGREGATE"
    for name, digest in result["files_sha256"].items():
        assert _sha((output / name).read_bytes()) == digest
    table = report._csv((output / "SENSITIVITY_TABLE_V3.csv").read_bytes())
    assert table[0]["h_rmse_m"] == "1.230000000000000"
    assert table[1]["delta_h_rmse_m"] == "0.010000000000000"
    for path in output.rglob("*.csv"):
        assert str(tmp_path) not in path.read_text()
    with pytest.raises(FileExistsError):
        report.aggregate_t5a(scratch, code_freeze=FREEZE, contract_path=contract, local_paths_path=local)


def test_histogram_selects_complete_evaluation_window_and_all_carrier_qualities():
    diagnostic = {"histograms": [
        {"scope": "evaluation_window", "quality": "all", "bin_left_deg": -1, "bin_right_deg": 0, "count": 3},
        {"scope": "full_provider", "quality": "all", "bin_left_deg": -1, "bin_right_deg": 0, "count": 4},
        {"scope": "evaluation_window", "quality": "both_fixed", "bin_left_deg": -1, "bin_right_deg": 0, "count": 2}]}
    rows = report._histogram_records("BY2O", diagnostic)
    assert len(rows) == 1 and rows[0]["count"] == 3


def test_dual_error_exports_verify_both_hashes_and_exact_decompression_before_gzip_selection(tmp_path):
    root = tmp_path / "evaluation"
    directory = root / "FROZEN_EVALUATOR"
    plain, compressed = directory / "error_series.csv", directory / "error_series.csv.gz"
    payload = b"time,yaw_err_deg\n1,2\n"
    pins = {"FROZEN_EVALUATOR/error_series.csv": _write(plain, payload),
            "FROZEN_EVALUATOR/error_series.csv.gz": _write(compressed, gzip.compress(payload, mtime=0))}
    sources = report.Sources({"t5a_scratch": tmp_path})
    selected = report._one_error_path(directory, sources=sources, seal=pins, seal_root=root)
    assert selected == compressed
    assert set(sources.hashes) == {plain, compressed}
    assert report._one_error_path(plain) == plain  # Explicit frozen filename remains authoritative.
    bad_pins = {**pins, "FROZEN_EVALUATOR/error_series.csv": "0" * 64}
    with pytest.raises(ValueError, match="SHA-256"):
        report._one_error_path(directory, sources=report.Sources({}), seal=bad_pins, seal_root=root)
    pins["FROZEN_EVALUATOR/error_series.csv.gz"] = _write(compressed, gzip.compress(b"time,yaw_err_deg\n1,3\n", mtime=0))
    with pytest.raises(ValueError, match="byte mismatch"):
        report._one_error_path(directory, sources=report.Sources({}), seal=pins, seal_root=root)
