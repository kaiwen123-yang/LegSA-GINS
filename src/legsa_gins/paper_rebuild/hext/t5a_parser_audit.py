"""T5a-R A0 inventory of frozen runtime syntax and native option echoes.

Only runtime YAML, ARCHIVE_RECEIPT, sampled native RUN_MANIFEST and frozen
aggregate identity projections are used. Performance fields are never retained.
This report-only audit neither executes a process nor opens data providers.
"""
from __future__ import annotations

import csv
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re

from .t5a_config_fidelity import audit_flat_config, audit_config_to_echo, decode_echo

ALIAS = "<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21"
PROFILES = ("F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09")


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _plain_path(path):
    path = Path(path).absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("A0 path traversal/symlink refused")
    return path


def _inventory(root):
    """One metadata-only scandir walk; no glob/rglob or subprocess traversal."""
    stack, configs, receipts, echoes, tables, skipped, errors = [root], [], set(), set(), [], [], []
    directories = 0
    while stack:
        parent = stack.pop()
        directories += 1
        if directories % 1000 == 0:
            print(f"T5a-R A0 inventory directories={directories} configs={len(configs)}",flush=True)
        try:
            with os.scandir(parent) as entries:
                for item in entries:
                    path = Path(item.path)
                    if item.is_symlink():
                        skipped.append(str(path.relative_to(root)))
                    elif item.is_dir(follow_symlinks=False):
                        stack.append(path)
                    elif item.is_file(follow_symlinks=False):
                        if "RUNTIME_CONFIG" in item.name and item.name.endswith(".yaml"):
                            configs.append(path)
                        elif item.name == "ARCHIVE_RECEIPT.json": receipts.add(path)
                        elif item.name == "RUN_MANIFEST.json": echoes.add(path)
                        elif item.name == "UNIQUE_EVALUATION_RESULTS.csv" and "20_FINALIZE" in path.parts and "v3" in path.parts: tables.append(path)
        except OSError as error:
            if isinstance(error,PermissionError): raise
            errors.append(dict(path=ALIAS+"/"+str(parent.relative_to(root)), reason=str(error)))
    return sorted(configs), receipts, echoes, sorted(tables), dict(directories_scanned=directories,
        symlinks_not_followed=sorted(skipped), inaccessible_directories=errors,
        inventory_complete_within_root=not skipped and not errors)


def _csv(path, rows, fallback):
    keys = list(dict.fromkeys(key for row in rows for key in row)) or fallback
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, keys)
        writer.writeheader(); writer.writerows(rows)


def run_parser_audit(v21_root, sequence_rows, output_root, code_freeze):
    """Inventory all retained runtime YAML and sample all 33 sequence profiles.

    Input/parse/receipt gaps become explicit report rows. Six execution-input
    identity gates remain the runtime controller's separate responsibility.
    output_root must be a new directory outside the frozen v2.1 root.
    """
    root, output = _plain_path(v21_root), _plain_path(output_root)
    if output == root or root in output.parents or output in root.parents:
        raise ValueError("A0 output must be outside protected frozen root")
    if output.exists(): raise FileExistsError("Preserve previous A0 output")
    if not re.fullmatch(r"[0-9a-f]{40}", str(code_freeze)):
        raise ValueError("A0 requires full code-freeze commit")
    sequence_rows = list(sequence_rows)
    paths, receipt_paths, echo_paths, tables, coverage = _inventory(root)
    clean_root = root.parent.parent
    receipt_cache, config_rows, config_bytes, path_rows = {}, [], {}, {}
    external_allowed, reference_records, reference_gaps = set(), list(sequence_rows), []
    table_projections = []

    def alias(path):
        return ALIAS+"/"+path.relative_to(root).as_posix() if root in path.parents else "<CLEAN_ROOT>/"+path.relative_to(clean_root).as_posix()

    def resolve(value):
        text = str(value)
        if text.startswith("<CLEAN_ROOT>/"): text = str(clean_root)+text[len("<CLEAN_ROOT>"):]
        path = _plain_path(text)
        if clean_root not in path.parents: raise ValueError("Referenced metadata must remain below CLEAN_ROOT")
        return path

    projection_keys = ("dataset_id","method_id","run_id","config_hash","output_root","native_run_manifest","archive_receipt")
    for table_path in tables:
        try:
            payload = table_path.read_bytes()
            projected = [{key:record.get(key,"") for key in projection_keys}
                         for record in csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))]
            reference_records.extend(projected)
            table_projections.append(dict(path=alias(table_path),sha256=_sha(payload),projected_rows=len(projected),projected_fields=list(projection_keys)))
        except (OSError,ValueError,UnicodeError) as error:
            if isinstance(error,PermissionError): raise
            reference_gaps.append(dict(path=alias(table_path),reason=str(error)))
    directories_seen = set()
    for record in reference_records:
        try:
            native = resolve(record["native_run_manifest"]) if record.get("native_run_manifest") else None
            directory = native.parent if native is not None else resolve(record["output_root"]) if record.get("output_root") else None
            if directory is None or root in directory.parents or directory in directories_seen: continue
            directories_seen.add(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False): continue
                    path = Path(entry.path)
                    if "RUNTIME_CONFIG" in entry.name and entry.name.endswith(".yaml"):
                        paths.append(path);external_allowed.add(path)
                    elif entry.name == "RUN_MANIFEST.json": echo_paths.add(path);external_allowed.add(path)
            if record.get("archive_receipt"):
                receipt = resolve(record["archive_receipt"])
                receipt_paths.add(receipt);external_allowed.add(receipt)
            else:
                for parent in (directory,directory.parent):
                    receipt=parent/"ARCHIVE_RECEIPT.json"
                    if receipt.is_file() and not receipt.is_symlink():receipt_paths.add(receipt);external_allowed.add(receipt)
        except (OSError,ValueError,TypeError) as error:
            if isinstance(error,PermissionError): raise
            reference_gaps.append(dict(run_id=str(record.get("run_id","")),reason=str(error)))
    paths = sorted(set(paths))
    checked_parents = {root,clean_root}

    def read(path):
        checked = Path(path).absolute()
        for item in (checked,*checked.parents):
            if item not in checked_parents:
                if item.is_symlink():raise ValueError("A0 metadata symlink refused")
                if item != checked:checked_parents.add(item)
        if (root not in checked.parents and checked not in external_allowed) or not (
            "RUNTIME_CONFIG" in checked.name and checked.name.endswith(".yaml")
            or checked.name in ("ARCHIVE_RECEIPT.json", "RUN_MANIFEST.json")):
            raise PermissionError("A0 input role is outside runtime metadata")
        return checked.read_bytes()

    def receipt_check(path, digest):
        receipt_path = next((parent/"ARCHIVE_RECEIPT.json" for parent in path.parents
                             if parent/"ARCHIVE_RECEIPT.json" in receipt_paths), None)
        result = dict(receipt_path="", receipt_sha256="", receipt_member="", receipt_expected_sha256="",
                      receipt_status="UNAVAILABLE_NO_RECEIPT", receipt_reason="")
        if receipt_path is None: return result
        result.update(receipt_path=alias(receipt_path), receipt_member=path.relative_to(receipt_path.parent).as_posix())
        try:
            if receipt_path not in receipt_cache:
                payload = read(receipt_path)
                receipt_cache[receipt_path] = (_sha(payload), decode_echo(payload))
            checksum, receipt = receipt_cache[receipt_path]
            result["receipt_sha256"] = checksum
            member = receipt.get("retained_files", {}).get(result["receipt_member"])
            if member is None:
                result["receipt_status"] = "UNAVAILABLE_MEMBER_NOT_REGISTERED"
            else:
                expected = member.get("sha256")
                result.update(receipt_expected_sha256=expected,
                              receipt_status="PASS" if digest == expected else "MISMATCH")
        except (OSError, ValueError, TypeError, KeyError) as error:
            if isinstance(error,PermissionError): raise
            result.update(receipt_status="UNAVAILABLE_RECEIPT_READ_OR_SCHEMA", receipt_reason=str(error))
        return result

    for ordinal,path in enumerate(paths,1):
        if ordinal % 500 == 0:print(f"T5a-R A0 audited configs={ordinal}/{len(paths)}",flush=True)
        row = dict(config_path=alias(path), config_sha256="", size_bytes="", parse_status="UNAVAILABLE",
                   compatible_field_count=0, mismatch_field_count=0, unavailable_field_count=0,
                   audit_rows_json="[]", reason="")
        try:
            payload = read(path); digest = _sha(payload); audit = audit_flat_config(payload)
            config_bytes[path] = payload
            counts = Counter(str(item.get("status", "UNAVAILABLE")) for item in audit.get("rows", []))
            row.update(config_sha256=digest, size_bytes=len(payload), parse_status=audit["status"],
                       compatible_field_count=counts.get("COMPATIBLE", 0), mismatch_field_count=counts.get("MISMATCH", 0),
                       unavailable_field_count=sum(n for status,n in counts.items() if status.startswith("UNAVAILABLE")),
                       field_status_counts_json=json.dumps(counts, sort_keys=True),
                       recorded_rows_policy="MISMATCH_FINDINGS_ONLY_ALL_FIELDS_COUNTED",
                       audit_rows_json=json.dumps(audit.get("differences", []), ensure_ascii=False, allow_nan=False),
                       reason=audit.get("reason", ""), **receipt_check(path,digest))
        except (OSError, ValueError, TypeError, KeyError) as error:
            if isinstance(error,PermissionError): raise
            row.update(reason=str(error), receipt_status="UNAVAILABLE_CONFIG_READ_OR_SCHEMA")
        config_rows.append(row); path_rows[path] = row

    supplied = {}
    for record in sequence_rows:
        dataset, method = str(record.get("dataset_id", record.get("sequence_id", ""))), str(record.get("method_id", ""))
        if dataset in ("BY2", "BY2H", "BY2O") and method in PROFILES:
            supplied.setdefault((dataset, method), []).append(record)
    sample_rows = []
    for dataset in ("BY2", "BY2H", "BY2O"):
        for method in PROFILES:
            records = supplied.get((dataset,method), [])
            row = dict(dataset_id=dataset, method_id=method, run_id="", config_path="", config_sha256="",
                       metadata_config_hash="", metadata_config_identity="UNAVAILABLE", echo_path="", echo_sha256="",
                       status="UNAVAILABLE_SEQUENCE_METADATA", legacy_f01=(method=="F01"), reason="",
                       echoed_field_count=0, mismatch_field_count=0, unavailable_field_count=0,
                       rows_json="[]", not_directly_represented_config_keys_json="[]")
            identities = {(str(r.get("run_id", "")),str(r.get("config_hash", ""))) for r in records}
            if len(identities) != 1:
                row["reason"] = "Missing metadata" if not identities else "Conflicting sequence metadata identities"
                sample_rows.append(row); continue
            run_id, expected = next(iter(identities)); row.update(run_id=run_id,metadata_config_hash=expected)
            matches = [p for p in paths if run_id in p.parts and path_rows[p]["config_sha256"] == expected]
            run_candidates = [p for p in paths if run_id in p.parts]
            canonical = root/"RETAINED_RUNS"/run_id/"P13_cycle010_attempt01/solver/PROTOCOL_V21_RUNTIME_CONFIG.yaml"
            try:
                referenced_echo = resolve(records[0]["native_run_manifest"]) if records[0].get("native_run_manifest") else None
            except (OSError,ValueError,TypeError) as error:
                if isinstance(error,PermissionError):raise
                row.update(status="UNAVAILABLE_REFERENCE_PATH",reason=str(error));sample_rows.append(row);continue
            preferred = [p for p in matches if referenced_echo is not None and p.parent == referenced_echo.parent]
            if len(preferred)==1:canonical=preferred[0]
            path = canonical if canonical in matches else matches[0] if len(matches)==1 else None
            if path is None:
                row.update(status="MISMATCH_METADATA_CONFIG_HASH" if run_candidates and not matches else "UNAVAILABLE_CONFIG_OUTSIDE_ROOT_OR_NOT_RETAINED" if not matches else "UNAVAILABLE_AMBIGUOUS_CONFIG",
                           observed_config_hashes_json=json.dumps([path_rows[p]["config_sha256"] for p in run_candidates]),
                           reason="No unique hash-matching runtime config in v2.1 root or explicitly referenced provenance directories")
                sample_rows.append(row); continue
            echo = path.parent/"RUN_MANIFEST.json"
            row.update(config_path=alias(path),config_sha256=path_rows[path]["config_sha256"],metadata_config_identity="PASS",
                       echo_path=alias(echo),config_receipt_status=path_rows[path].get("receipt_status","UNAVAILABLE"))
            if echo not in echo_paths:
                row.update(status="UNAVAILABLE_NATIVE_ECHO",reason="Frozen native RUN_MANIFEST is not retained")
                sample_rows.append(row); continue
            try:
                payload = read(echo); digest = _sha(payload); native = decode_echo(payload)
                audit = audit_config_to_echo(config_bytes[path],native)
                check = receipt_check(echo,digest)
                counts = Counter(str(item.get("status", "UNAVAILABLE")) for item in audit.get("rows", []))
                status = "UNAVAILABLE_ECHO_FIELDS" if audit["status"] == "AVAILABLE" and audit.get("missing_fields") else audit["status"]
                row.update(status=status,echo_audit_passed=audit.get("passed",False),echo_sha256=digest,native_schema=native.get("schema_version", ""),
                           echo_top_level_key_count=len(native),echoed_field_count=len(audit.get("rows", [])),
                           mismatch_field_count=counts.get("MISMATCH",0),
                           unavailable_field_count=sum(n for status,n in counts.items() if status.startswith("UNAVAILABLE")),
                           field_status_counts_json=json.dumps(counts,sort_keys=True),
                           rows_json=json.dumps(audit.get("rows", []),ensure_ascii=False,allow_nan=False),
                           not_directly_represented_config_keys_json=json.dumps(audit.get("not_directly_represented_config_keys", [])),
                           numeric_roundtrip_relative_tolerance=audit.get("numeric_roundtrip_relative_tolerance"),
                           numeric_roundtrip_absolute_tolerance=audit.get("numeric_roundtrip_absolute_tolerance"),
                           hard_gate_b_uses_no_tolerance=True,reason=audit.get("reason", ""),
                           **{"echo_"+key:value for key,value in check.items()})
            except (OSError, ValueError, TypeError, KeyError) as error:
                if isinstance(error,PermissionError):raise
                row.update(status="UNAVAILABLE_ECHO_READ_OR_SCHEMA",reason=str(error))
            sample_rows.append(row)
    output.mkdir(parents=True,exist_ok=False)
    _csv(output/"A0_CONFIGS.csv",config_rows,["config_path","parse_status"])
    _csv(output/"A0_ECHO_SAMPLE.csv",sample_rows,["dataset_id","method_id","status"])
    summary = dict(task="T5a-R",phase="A0",status="REPORT_COMPLETE" if coverage["inventory_complete_within_root"] else "REPORT_PARTIAL_INVENTORY",
        code_freeze=code_freeze,report_only=True,data_mode="frozen_runtime_metadata_read_only",
        synthetic_data_used=False,semisynthetic_data_used=False,solver_invocation_count=0,evaluator_invocation_count=0,
        native_invocation_count=0,raw_open_count=0,trace_open_count=0,provider_payload_open_count=0,
        scope_root=ALIAS,inventory_scope="Every *RUNTIME_CONFIG*.yaml below v2.1 root plus frozen metadata-referenced external runtime directories; no unrelated legacy tree walk",
        config_count=len(config_rows),config_parse_status_counts=dict(Counter(r["parse_status"] for r in config_rows)),
        config_receipt_status_counts=dict(Counter(r.get("receipt_status","UNAVAILABLE") for r in config_rows)),
        echo_sample_required_count=33,echo_sample_row_count=len(sample_rows),
        echo_sample_status_counts=dict(Counter(r["status"] for r in sample_rows)),
        echo_receipt_status_counts=dict(Counter(r.get("echo_receipt_status","UNAVAILABLE_NOT_SAMPLED") for r in sample_rows)),
        expected_sequence_profiles={dataset:list(PROFILES) for dataset in ("BY2","BY2H","BY2O")},
        metadata_projection_tables=table_projections,metadata_reference_gaps=reference_gaps,
        external_reference_directory_count=len(directories_seen),external_runtime_config_count=sum(root not in path.parents for path in paths),
        scope_limitations=["F01/reused configs outside v2.1 root are inspected only through explicit frozen aggregate or sequence metadata references; missing references remain unavailable.",
            "Receipt files have observed SHA identities; member hashes are checked when registered; absent receipts remain explicit.",
            "A0 parser/roundtrip mismatches are report-only; Gate a and exact native-echo Gate b remain separate execution requirements."],
        **coverage,products={name:_sha((output/name).read_bytes()) for name in ("A0_CONFIGS.csv","A0_ECHO_SAMPLE.csv")})
    with (output/"A0_SUMMARY.json").open("x",encoding="utf-8") as stream:
        json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")
    return summary
