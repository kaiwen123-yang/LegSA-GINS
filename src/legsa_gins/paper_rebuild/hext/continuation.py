"""H-EXT-03: classify sealed native output and consume only unused evaluation slots.

There is deliberately no native runner import or native/provider action here.
Trace payloads remain restricted to the frozen evaluator child.
"""
from __future__ import annotations

import csv
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import zipfile

import numpy as np
import pandas as pd
import yaml

from . import execution as io
from .sequence_paths import load_sequence_paths, alias_path
from ..manifest import sha256_file

ATTEMPT = "H_EXT_03"
PREREG_SUBJECT = "prereg(hext): H-EXT-03 bounded continuation authorization and contract v1.1"
V1_ZIP_SHA256 = "efb64041e5add0b8d47542e446ae80abe3e038a9bdc0ee1d9620f4216764cc15"
V1_ZIP_BYTES = 1084956510
TEXT_NAV_COLUMNS = {"method_id", "covariance_coordinate", "covariance_state_order"}
BOUNDS = {"position_displacement_m": 1e4, "speed_mps": 50.0, "height_displacement_m": 1e3}
AUTHORIZED_CHANGED_OLD_SOURCES = {
    "configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml",
    *("src/legsa_gins/paper_rebuild/hext/" + name for name in (
        "aggregate.py", "figures.py", "external_evaluation.py", "legsa_gap_diagnostic.py")),
}


def stage_roots():
    seq = load_sequence_paths("BY2")
    return seq, seq.hext_scratch / ATTEMPT, seq.output_root


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list))
                             else value for key, value in row.items()})


def _check_file(path, expected):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise RuntimeError("HARD_STOP_IDENTITY_MISSING_OR_SYMLINK: " + str(path))
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("HARD_STOP_IDENTITY_MISMATCH: " + str(path))
    return actual


def _finite_json_number(value):
    value = float(value)
    return value if math.isfinite(value) else "NONFINITE"


def bounded_native_output(nav, *, expected_sha256):
    """D8 on every full-rate native NAV.csv row in its original fixed NED frame.

    All numeric columns, including covariance, must be finite. Bounds use vector
    norms, with equality allowed. No epoch is removed and no evaluator NAV is
    substituted for native full-rate output. CSV data row 1 is physical line 2.
    """
    nav = Path(nav)
    digest = _check_file(nav, expected_sha256)
    with nav.open(encoding="utf-8", newline="") as stream:
        fields = next(csv.reader(stream))
    needed = {"time_seconds", "absolute_time_unix_seconds", "north_m", "east_m", "down_m",
              "vn_mps", "ve_mps", "vd_mps"}
    if not needed.issubset(fields):
        raise RuntimeError("HARD_STOP_NATIVE_NAV_SCHEMA")
    numeric = [field for field in fields if field not in TEXT_NAV_COLUMNS]
    first_position = None
    count, finite_count, first_violation = 0, 0, None
    maxima = {key: 0.0 for key in BOUNDS}
    for chunk in pd.read_csv(nav, usecols=numeric, dtype=float, chunksize=16384):
        if not len(chunk):
            continue
        values = chunk.to_numpy(float)
        finite_rows = np.isfinite(values).all(axis=1)
        finite_count += int(finite_rows.sum())
        position = chunk[["north_m", "east_m", "down_m"]].to_numpy(float)
        velocity = chunk[["vn_mps", "ve_mps", "vd_mps"]].to_numpy(float)
        if first_position is None:
            first_position = position[0].copy()
        with np.errstate(over="ignore", invalid="ignore"):
            delta = position - first_position
            observed = {"position_displacement_m": np.hypot.reduce(delta, axis=1),
                        "speed_mps": np.hypot.reduce(velocity, axis=1),
                        "height_displacement_m": np.abs(delta[:, 2])}
        violated = ~finite_rows
        for key, bound in BOUNDS.items():
            data = observed[key]
            finite = data[np.isfinite(data)]
            if len(finite):
                maxima[key] = max(maxima[key], float(np.max(finite)))
            violated |= ~np.isfinite(data) | (data > bound)
        indices = np.flatnonzero(violated)
        if first_violation is None and len(indices):
            i = int(indices[0])
            reasons = (["NONFINITE_NUMERIC_NATIVE_ROW"] if not finite_rows[i] else [])
            reasons.extend(key for key, limit in BOUNDS.items()
                           if not math.isfinite(float(observed[key][i])) or observed[key][i] > limit)
            first_violation = {
                "data_row_one_based": count + i + 1, "csv_line_one_based": count + i + 2,
                "time_seconds": _finite_json_number(chunk.iloc[i]["time_seconds"]),
                "absolute_time_unix_seconds": _finite_json_number(chunk.iloc[i]["absolute_time_unix_seconds"]),
                "reasons": reasons,
                "nonfinite_columns": [key for key in numeric if not math.isfinite(float(chunk.iloc[i][key]))],
                **{key: _finite_json_number(data[i]) for key, data in observed.items()},
            }
        count += len(chunk)
    passed = count > 0 and first_violation is None
    if not count:
        first_violation = {"reasons": ["EMPTY_NATIVE_NAV"]}
    return {"passed": passed, "native_status": "COMPLETED" if passed else "ALGORITHM_FAILURE_DIVERGED",
            "failure_classification": "NONE" if passed else "ALGORITHM_FAILURE_DIVERGED",
            "source_nav": str(nav), "source_nav_sha256": digest, "row_count": count,
            "all_numeric_rows_finite": finite_count == count and count > 0,
            "finite_row_count": finite_count, "numeric_columns_checked": numeric,
            "position_frame": "original_native_fixed_NED_m", "bounds": BOUNDS,
            "first_violation": first_violation, "maxima": maxima,
            "max_position_displacement_m": maxima["position_displacement_m"],
            "max_speed_mps": maxima["speed_mps"],
            "max_height_displacement_m": maxima["height_displacement_m"],
            "native_invocation_count": 0, "evaluator_invocation_count": 0, "trace_open_count": 0}


def original_ledger(archive):
    with (Path(archive) / "99_HARD_STOP/EVALUATION_LEDGER.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    keys = [(r["sequence_id"] + "__" + r["method_id"] + "__" + r["start_convention"], r["version"]) for r in rows]
    statuses = [r["status"] for r in rows]
    if (len(keys) != 28 or len(set(keys)) != 28 or statuses.count("COMPLETED") != 16
            or statuses.count("FAILED_EVALUATOR_CONSISTENCY") != 1 or statuses.count("NOT_RUN_HARD_STOP") != 11):
        raise RuntimeError("HARD_STOP_ORIGINAL_LEDGER_TOPOLOGY")
    return dict(zip(keys, rows))


def validate_continuation_authorization(contract, ledger):
    allowed = {key for key, row in ledger.items() if row["status"] == "NOT_RUN_HARD_STOP"}
    registered = [(row["run_id"], row["version"]) for row in contract.get("continuation_remaining_slots", [])]
    if (contract.get("schema_version") != "hext.external_sequences.contract.v1.1"
            or contract.get("task") != "H-EXT-03"
            or contract.get("authorization") != "H-EXT-03 prompt 2026-09-16"
            or contract.get("execution_authorized") is not True
            or contract.get("budget", {}).get("native") != 0
            or contract.get("budget", {}).get("evaluator") != 11
            or len(registered) != 11 or set(registered) != allowed):
        raise RuntimeError("HARD_STOP_H03_AUTHORIZATION_OR_SLOT_SCOPE")
    return allowed


def _read_native_records(archive):
    records = _read(Path(archive) / "99_HARD_STOP/NATIVE_EXECUTION_RECORDS.json")
    if len(records) != 14 or len({r["run_id"] for r in records}) != 14:
        raise RuntimeError("HARD_STOP_ORIGINAL_NATIVE_TOPOLOGY")
    return records


def _verify_old_package(seq, archive, prereg):
    local = yaml.safe_load((seq.code_root / "configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml").read_text())["paths"]
    package = Path(local["handoff_root"]) / "hext_three_sequences_handoff.zip"
    _check_file(package, V1_ZIP_SHA256)
    if package.stat().st_size != V1_ZIP_BYTES:
        raise RuntimeError("HARD_STOP_V1_PACKAGE_SIZE")
    preserved = {}
    with zipfile.ZipFile(package) as bundle:
        if len(bundle.infolist()) != 570:
            raise RuntimeError("HARD_STOP_V1_MEMBER_COUNT")
        manifest = json.loads(bundle.read("MEMBER_MANIFEST.json"))
        for member in manifest["members"]:
            name = member["name"]
            if not name.startswith("STAGE/"):
                continue
            relative = Path(name).relative_to("STAGE")
            if ".." in relative.parts or relative.is_absolute():
                raise RuntimeError("HARD_STOP_V1_MANIFEST_PATH")
            path = archive / relative
            _check_file(path, member["sha256"])
            if path.stat().st_size != member["size_bytes"]:
                raise RuntimeError("HARD_STOP_V1_MEMBER_SIZE")
            preserved[relative.as_posix()] = member["sha256"]
    io.write_json(prereg / "PRESERVED_H02_STAGE_FILES.json", preserved)
    return {"path": str(package), "sha256": V1_ZIP_SHA256, "bytes": V1_ZIP_BYTES,
            "member_count": 570, "stage_files_verified": len(preserved),
            "historical_stop_and_failed_evaluation_unchanged": True}


def preflight():
    """Read-only evidence classification plus new H03 metadata; zero runtime calls."""
    from .figures import verify_frozen_v21
    from .probe import dependencies
    seq, scratch, archive = stage_roots()
    ledger = original_ledger(archive)
    validate_continuation_authorization(yaml.safe_load((seq.code_root / io.CONTRACT).read_text()), ledger)
    out = scratch / "03_CONTINUATION/PREREG"
    out.mkdir(parents=True, exist_ok=False)
    package = _verify_old_package(seq, archive, out)
    old_freeze = _read(archive / "03_PREREG/CODE_FREEZE.json")
    for relative, expected in old_freeze["source_hashes"].items():
        if relative not in AUTHORIZED_CHANGED_OLD_SOURCES:
            _check_file(seq.code_root / relative, expected)
    deps = dependencies(seq)
    if any(isinstance(value, dict) and value.get("matches") is False for value in deps.values()):
        raise RuntimeError("HARD_STOP_FROZEN_DEPENDENCY")
    v2 = seq.clean_root / "stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/13_AGGREGATE_SEQUENCES/v2/UNIQUE_EVALUATION_RESULTS.csv"
    _check_file(v2, "6c5a165eaf68bf762cbc803466b4496a5b522dba968785115db9d0338990044d")
    deps["v21_sequences_v2"] = {"path": str(v2), "sha256": sha256_file(v2), "matches": True}
    io.write_json(out / "DEPENDENCIES.json", deps)
    before = _read(archive / "99_HARD_STOP/FROZEN_FIGURES_POST_STOP.json")
    verify_frozen_v21(before, seq.clean_root / "stages/CLEAN6_PUBLICATION_FIGURES/figures/v21")
    io.write_json(out / "FROZEN_FIGURES_PRE.json", before)
    records, gates = _read_native_records(archive), []
    for record in records:
        native = _read(record["native_summary_path"])
        root = Path(record["native_root"])
        for filename, expected in native["file_hashes"].items():
            _check_file(root / filename, expected)
        gate = bounded_native_output(root / "NAV.csv", expected_sha256=native["file_hashes"]["NAV.csv"])
        gate.update(run_id=record["run_id"], sequence_id=record["sequence_id"],
                    method_id=record["configuration_id"], start_convention=record["start_mode"],
                    sealed_evaluator_nav_sha256=native["file_hashes"]["EXACT_EVALUATOR_INPUT.nav"])
        gates.append(gate)
    retrospective = [{"run_id": gate["run_id"], "version": version, "passed": gate["passed"]}
                     for gate in gates for version in ("v3", "v2")
                     if ledger[(gate["run_id"], version)]["status"] == "COMPLETED"]
    io.write_json(out / "BOUNDED_OUTPUT_GATE.json", gates)
    _write_csv(out / "BOUNDED_OUTPUT_GATE.csv", gates)
    io.write_json(out / "D8_RETROSPECTIVE.json", {"evaluations_checked": len(retrospective),
        "all_passed": all(r["passed"] for r in retrospective), "rows": retrospective,
        "existing_completed_evaluations_modified": False})
    result = {"status": "PASS_H03_PREFLIGHT", "package": package, "native_reused": 14,
              "native_invocation_count": 0, "evaluator_invocation_count": 0, "trace_open_count": 0,
              "bounded_native_count": sum(g["passed"] for g in gates),
              "diverged_native_count": sum(not g["passed"] for g in gates),
              "completed_evaluations_retrospective": retrospective}
    io.write_json(out / "PREFLIGHT.json", result)
    return result


def freeze_receipt():
    seq, scratch, archive = stage_roots()
    out = scratch / "03_CONTINUATION/PREREG"
    preflight_result = _read(out / "PREFLIGHT.json")
    if preflight_result["status"] != "PASS_H03_PREFLIGHT":
        raise RuntimeError("HARD_STOP_PREFLIGHT_REQUIRED")
    subject = subprocess.check_output(["git", "log", "-1", "--format=%s"], cwd=seq.code_root, text=True).strip()
    if subject != PREREG_SUBJECT:
        raise RuntimeError("HARD_STOP_H03_PREREG_COMMIT_REQUIRED")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=seq.code_root, text=True).strip()
    old = _read(archive / "03_PREREG/CODE_FREEZE.json")
    paths = {seq.code_root / relative for relative in old["source_hashes"]}
    paths.update((seq.code_root / "src/legsa_gins/paper_rebuild/hext").glob("*.py"))
    paths.update((seq.code_root / "scripts/paper_rebuild").glob("hext*.py"))
    paths.add(seq.code_root / io.CONTRACT)
    hashes = {path.relative_to(seq.code_root).as_posix(): sha256_file(path) for path in sorted(paths)}
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *hashes], cwd=seq.code_root).returncode:
        raise RuntimeError("HARD_STOP_UNCOMMITTED_EXECUTION_SOURCE")
    result = {"code_freeze": commit, "contract_sha256": sha256_file(seq.code_root / io.CONTRACT),
              "source_hashes": hashes, "native_budget": 0, "evaluator_budget": 11,
              "authorized_original_not_run_slots": 11, "automatic_retry_allowed": False,
              "authorization": "H-EXT-03 prompt 2026-09-16", "original_code_freeze": old["code_freeze"]}
    io.write_json(out / "CODE_FREEZE.json", result)
    io.archive_batch(out, archive / "03_CONTINUATION/PREREG", scratch / "ARCHIVE_LEDGER.jsonl", "H03_PREREG")
    return result


def assert_freeze():
    seq, scratch, _ = stage_roots()
    result = _read(scratch / "03_CONTINUATION/PREREG/CODE_FREEZE.json")
    for relative, expected in result["source_hashes"].items():
        _check_file(seq.code_root / relative, expected)
    return result


def reserve_evaluator_slot(ledger_path, *, run_id, version, allowed_slots, budget=11):
    """Fsync a launch reservation before invocation; an interrupted slot is spent."""
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    key = (run_id, version)
    if key not in allowed_slots:
        raise RuntimeError("HARD_STOP_NOT_AN_ORIGINAL_UNUSED_SLOT")
    with ledger_path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        prior = [json.loads(line) for line in stream.read().splitlines()]
        if any((entry["run_id"], entry["version"]) == key for entry in prior):
            raise RuntimeError("HARD_STOP_ALREADY_ATTEMPTED_NO_RETRY")
        if len(prior) >= budget:
            raise RuntimeError("HARD_STOP_EVALUATOR_BUDGET")
        row = {"event": "EVALUATOR_LAUNCH_RESERVED", "run_id": run_id, "version": version,
               "invocation_ordinal": len(prior) + 1, "retry_count": 0}
        stream.write(json.dumps(row) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return row


def _classification_payload(record, version, gate, historical, code_commit):
    row = {"sequence_id": record["sequence_id"], "dataset_id": record["sequence_id"],
           "method_id": record["configuration_id"], "run_id": record["run_id"],
           "start_convention": record["start_mode"], "evaluator_contract": "evaluator_contract_" + version,
           "status": "NOT_RUN_ALGORITHM_FAILURE", "evaluation_status": "NOT_RUN_ALGORITHM_FAILURE",
           "native_status": "ALGORITHM_FAILURE_DIVERGED", "failure_classification": "ALGORITHM_FAILURE_DIVERGED",
           "evaluation_invoked": False, "metrics_admitted": False, "code_commit": code_commit,
           "source_nav_sha256": gate["sealed_evaluator_nav_sha256"],
           "historical_evaluation_status": historical["status"],
           "historical_evaluation_source": historical["source"],
           "historical_evaluation_source_sha256": historical["source_sha256"],
           "reason": "D7/D8 native output unbounded; this continuation does not invoke an evaluator"}
    return {"row": row, "body_frame_bias": {**row, "status": "NOT_RUN_ALGORITHM_FAILURE"},
            "audit": {"passed": True, "trace_open_count": 0, "evaluation_invoked": False,
                      "audit_role": "D8_CLASSIFICATION_ONLY_NO_EVALUATOR"}, "bounded_gate": gate}


def _verify_preserved(seq, scratch, archive):
    for relative, expected in _read(scratch / "03_CONTINUATION/PREREG/PRESERVED_H02_STAGE_FILES.json").items():
        _check_file(archive / relative, expected)
    from .figures import verify_frozen_v21
    before = _read(scratch / "03_CONTINUATION/PREREG/FROZEN_FIGURES_PRE.json")
    return verify_frozen_v21(before, seq.clean_root / "stages/CLEAN6_PUBLICATION_FIGURES/figures/v21")


def run_evaluation_matrix():
    from .external_evaluation import evaluate
    seq, scratch, archive = stage_roots()
    freeze = assert_freeze()
    if (scratch / "EVALUATOR_LAUNCH_LEDGER.jsonl").exists() or (scratch / "EXECUTION_RECORDS.json").exists():
        raise RuntimeError("HARD_STOP_CONTINUATION_ALREADY_STARTED_NO_AUTOMATIC_RETRY")
    ledger = original_ledger(archive)
    allowed = validate_continuation_authorization(yaml.safe_load((seq.code_root / io.CONTRACT).read_text()), ledger)
    gates = {r["run_id"]: r for r in _read(scratch / "03_CONTINUATION/PREREG/BOUNDED_OUTPUT_GATE.json")}
    records = _read_native_records(archive)
    calibrated = yaml.safe_load((seq.code_root / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_EXECUTION_CONTRACT.yaml").read_text())
    evaluator = Path(calibrated["evaluator"]["path"].replace("<CLEAN_ROOT>", str(seq.clean_root)))
    _check_file(evaluator, calibrated["evaluator"]["sha256"])
    for name in ("BY2", "BY2H", "BY2O"):
        io.raw_checkpoint(load_sequence_paths(name), scratch / "EVALUATION_RAW_CHECKPOINTS" / (name + "_PRE.json"))
    counts = {"native_actual": 0, "native_reused": 14, "evaluator_actual": 0, "reused_evaluations": 0,
              "skipped_algorithm_failure_slots": 0, "new_unavailable_evaluation_failed": 0,
              "historical_failed_evaluator_invocations": 1, "historical_evaluator_actual": 17,
              "native_budget": 0, "evaluator_budget": 11, "prereg_identity_native": 0,
              "prereg_identity_evaluator": 0, "evaluator_retry_count": 0}
    for record in records:
        current, gate = load_sequence_paths(record["sequence_id"]), gates[record["run_id"]]
        native_root = Path(record["native_root"])
        _check_file(native_root / "NAV.csv", gate["source_nav_sha256"])
        nav = native_root / "EXACT_EVALUATOR_INPUT.nav"
        _check_file(nav, gate["sealed_evaluator_nav_sha256"])
        paper_start = "CONTRACT_START" if current.sequence_id == "BY2H" else "FILE_START"
        record.update(native_status=gate["native_status"], failure_classification=gate["failure_classification"],
                      bounded_gate=gate, manuscript_start_mode=paper_start,
                      manuscript_row=record["start_mode"] == paper_start and record["configuration_id"] == "LC01-S",
                      evaluation_dispositions={})
        for version in ("v3", "v2"):
            assert_freeze()
            original = ledger[(record["run_id"], version)]
            if original["status"] == "COMPLETED":
                source = archive / "07_OFFLINE_EVALUATION" / version / record["run_id"] / "EVALUATION_RESULT.json"
                _check_file(source, original["source_sha256"])
                record["evaluations"][version] = str(source)
                record["evaluation_dispositions"][version] = "REUSED_H02_COMPLETED"
                counts["reused_evaluations"] += 1
                continue
            if not gate["passed"]:
                relative = Path("03_CONTINUATION/CLASSIFICATIONS") / record["run_id"] / version
                payload = _classification_payload(record, version, gate, original, freeze["code_freeze"])
                io.write_json(scratch / relative / "EVALUATION_RESULT.json", payload)
                io.archive_batch(scratch / relative, archive / relative, scratch / "ARCHIVE_LEDGER.jsonl",
                                 record["run_id"] + "_" + version + "_D7")
                record["evaluations"][version] = str(archive / relative / "EVALUATION_RESULT.json")
                record["evaluation_dispositions"][version] = "NEW_H03_D7_CLASSIFICATION"
                counts["skipped_algorithm_failure_slots"] += 1
                continue
            if original["status"] != "NOT_RUN_HARD_STOP":
                raise RuntimeError("HARD_STOP_PREVIOUS_FAILED_EVALUATOR_MUST_NOT_BE_RETRIED")
            relative = Path("07_OFFLINE_EVALUATION") / version / record["run_id"]
            transform_relative = Path("06_V3_NAV_INPUTS") / record["run_id"]
            if (archive / relative).exists() or (scratch / relative).exists():
                raise RuntimeError("HARD_STOP_EVALUATION_DESTINATION_EXISTS")
            if version == "v3" and ((archive / transform_relative).exists() or (scratch / transform_relative).exists()):
                raise RuntimeError("HARD_STOP_TRANSFORM_DESTINATION_EXISTS")
            reserve_evaluator_slot(scratch / "EVALUATOR_LAUNCH_LEDGER.jsonl", run_id=record["run_id"],
                                   version=version, allowed_slots=allowed)
            counts["evaluator_actual"] += 1
            identity = {"sequence_id": current.sequence_id, "method_id": record["configuration_id"],
                        "run_id": record["run_id"], "code_commit": freeze["code_freeze"],
                        "start_convention": record["start_mode"]}
            result = evaluate(sequence=current, evaluator=evaluator, nav=nav,
                expected_nav_sha256=gate["sealed_evaluator_nav_sha256"], outdir=scratch / relative,
                version=version, identity=identity,
                nav_input_root=scratch / transform_relative if version == "v3" else None,
                consistency_failure_policy="D12_BOUNDED_UNAVAILABLE", bounded_gate=gate)
            io.archive_batch(scratch / relative, archive / relative, scratch / "ARCHIVE_LEDGER.jsonl",
                             record["run_id"] + "_" + version)
            if version == "v3":
                io.archive_batch(scratch / transform_relative, archive / transform_relative,
                                 scratch / "ARCHIVE_LEDGER.jsonl", record["run_id"] + "_V3_INPUT")
            record["evaluations"][version] = str(archive / relative / "EVALUATION_RESULT.json")
            record["evaluation_dispositions"][version] = "NEW_H03_EVALUATED"
            if result["row"].get("evaluation_status") == "UNAVAILABLE_EVALUATION_FAILED":
                counts["new_unavailable_evaluation_failed"] += 1
            io._journal(scratch, {"event": "EVALUATOR_COMPLETED_ARCHIVED", "run_id": record["run_id"],
                                 "version": version, "trace_open_count": result["audit"]["trace_open_count"],
                                 "status": result["row"].get("evaluation_status", "COMPLETED")})
            print("H03_EVALUATOR_COMPLETED", record["run_id"], version, flush=True)
    for name in ("BY2", "BY2H", "BY2O"):
        io.raw_checkpoint(load_sequence_paths(name), scratch / "EVALUATION_RAW_CHECKPOINTS" / (name + "_POST.json"))
    _verify_preserved(seq, scratch, archive)
    assert_freeze()
    counts["total_evaluator_actual_including_h02"] = counts["historical_evaluator_actual"] + counts["evaluator_actual"]
    counts["total_evaluation_terminal_slots"] = sum(len(r["evaluations"]) for r in records)
    io.write_json(scratch / "EXECUTION_RECORDS.json", records)
    out = scratch / "03_CONTINUATION/EXECUTION"
    io.write_json(out / "EXECUTION_RECORDS.json", records)
    io.write_json(out / "BUDGET_LEDGER.json", counts)
    io.archive_batch(out, archive / "03_CONTINUATION/EXECUTION", scratch / "ARCHIVE_LEDGER.jsonl", "H03_EXECUTION")
    io.archive_batch(scratch / "EVALUATION_RAW_CHECKPOINTS", archive / "03_CONTINUATION/EVALUATION_RAW_CHECKPOINTS",
                     scratch / "ARCHIVE_LEDGER.jsonl", "H03_RAW_PRE_POST")
    return {"status": "COMPLETED_H03_EVALUATION_SLOTS", "budget": counts}
