#!/usr/bin/env python3
"""Read existing V3 ledgers and retained metadata without importing project code.

This collector does not run scientific programs, read raw/reference inputs,
recompute metrics, extract payload archives, or modify retained evidence.
All writes are restricted to the explicitly supplied collection directory.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import time


MISSING = "__FIELD_ABSENT__"
FILE_FIELDS = [
    "category", "source_path", "source_row_key", "read_status", "retention_status",
    "archive_path", "archive_member", "recorded_sha256", "verified_sha256",
    "row_count", "columns", "sequence_scope", "method_scope", "case_scope",
    "version_scope", "notes", "size_bytes", "receipt_source", "original_path",
]
IDENTITY = ["run_id", "sequence_id", "dataset_id", "domain", "case_id", "case_family",
            "degradation_type_id", "seed_index", "method_id", "configuration_id",
            "effective_profile", "data_mode", "synthetic_data_used", "semisynthetic_data_used"]


def load_paths(path):
    """Parse only the flat paths mapping used by the ignored local YAML."""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"  ([a-zA-Z0-9_]+):\s*(.*?)\s*", line)
        if match:
            result[match[1]] = match[2].strip("\"'")
    for key in ("code_root", "clean_root", "protocol_v3_scratch", "audit_source_worktree"):
        if key not in result:
            raise ValueError("Required local root is missing: " + key)
    return result


def json_text(value):
    """Preserve original JSON number tokens read as Decimal."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(str(k), ensure_ascii=False) + ":" + json_text(v)
                              for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(json_text(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Collector:
    def __init__(self, paths, output, phase):
        self.code = Path(paths["code_root"])
        self.root = Path(paths["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
        self.output = output.resolve()
        approved = self.code / "docs/paper_rebuild/audit_xbpg_20261001/v3_results"
        if self.output != approved.resolve():
            raise ValueError("Output must be the approved v3_results directory")
        self.aliases = [(str(self.root), "<V3_ROOT>")]
        self.aliases += [(value.rstrip("/"), "<" + key.upper() + ">") for key, value in paths.items()
                         if value.startswith("/") and key.endswith(("root", "scratch", "archive", "worktree"))]
        self.aliases.sort(key=lambda item: len(item[0]), reverse=True)
        self.phase = phase
        self.files = []
        self.read_counts = collections.Counter()
        self.conflicts = []
        self.outputs = []
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "run_statistics").mkdir(exist_ok=True)

    def alias(self, value):
        text = str(value)
        for root, alias in self.aliases:
            text = text.replace(root, alias)
        return text

    def cell(self, value):
        if isinstance(value, (dict, list)):
            return self.alias(json_text(value))
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        return self.alias(value)

    def resolve(self, value):
        text = str(value)
        for root, alias in self.aliases:
            if text == alias or text.startswith(alias + "/"):
                return Path(root + text[len(alias):])
        raise ValueError("Source does not use a configured alias: " + text)

    def source_row(self, path, category, **extra):
        row = {"category": category, "source_path": self.alias(path),
               "read_status": "INDEX_ONLY_NOT_CHECKED", "retention_status": "unknown"}
        row.update(extra)
        return row

    def read_json(self, path, category, recorded="", scope=None):
        row = self.source_row(path, category, recorded_sha256=recorded)
        if scope:
            row.update(scope)
        try:
            data = path.read_bytes()
            value = json.loads(data, parse_float=Decimal)
            row.update(read_status="READ_COMPLETE_JSON", retention_status="PRESENT",
                       size_bytes=len(data), verified_sha256=hashlib.sha256(data).hexdigest(),
                       row_count=len(value) if isinstance(value, list) else 1,
                       columns=";".join(value if isinstance(value, dict) else
                                        (value[0] if value and isinstance(value[0], dict) else [])))
            if recorded and row["verified_sha256"] != recorded:
                row["notes"] = "RECORDED_HASH_DIFFERS_FROM_CURRENT_READ"
            return value, row
        except FileNotFoundError:
            row.update(read_status="MISSING", retention_status="EXPECTED_NOT_FOUND")
            return None, row
        except (OSError, ValueError) as error:
            row.update(read_status="READ_ERROR", notes=str(error))
            return None, row

    def write_csv(self, name, rows, fields=None):
        path = self.output / name
        if fields is None:
            fields = list(dict.fromkeys(k for row in rows for k in row))
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="raise")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: self.cell(row[key]) if key in row else MISSING for key in fields})
        self.outputs.append({"path": self.alias(path), "row_count": len(rows), "column_count": len(fields),
                             "size_bytes": path.stat().st_size})

    def read_csv(self, path, category):
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
        self.files.append(self.source_row(path, category, read_status="READ_COMPLETE_CSV",
                          retention_status="PRESENT", row_count=len(rows), columns=";".join(reader.fieldnames)))
        return rows

    def compact_file_rows(self, rows):
        """Dictionary repeated schemas; run identity scopes join losslessly by run_id."""
        schemas = {}
        result = []
        for original in rows:
            row = {key: "" if value == MISSING else value for key, value in original.items()}
            columns = row.get("columns", "")
            if columns:
                if columns not in schemas:
                    schemas[columns] = "S" + str(len(schemas) + 1).zfill(4)
                row["columns"] = "SCHEMA:" + schemas[columns]
            if row.get("source_row_key"):
                version = row.get("version_scope", "").rsplit("/", 1)[-1]
                receipt = row.get("receipt_source", "")
                if "#/" in receipt:
                    row["receipt_source"] = "@" + version + "_archive_receipt#" + receipt.split("#", 1)[1]
                # These dimensions are exact joins to the unique native index key.
                row["sequence_scope"] = "@"
                row["method_scope"] = "@"
                row["case_scope"] = "@"
                notes = row.get("notes", "")
                if notes.startswith("Hash is recorded unless verified_sha256 is populated; source member="):
                    row["notes"] = "N1" + (";CONFLICT_PRESENT_BUT_RECEIPT_SAYS_RELEASED" if "CONFLICT_PRESENT_BUT_RECEIPT_SAYS_RELEASED" in notes else "")
            result.append({key: row.get(key, "") for key in FILE_FIELDS})
        self.write_csv("run_statistics/FILE_SCHEMA_INDEX.csv", [
            {"schema_id": identifier, "columns": columns, "meaning": "Exact columns/header JSON-key string from the named input file; no result value conversion"}
            for columns, identifier in schemas.items()])
        return result

    def export_section(self, evaluations, section, prefix):
        groups = collections.defaultdict(list)
        for index, record in enumerate(evaluations):
            identity = record["row"]
            version = identity["evaluator_contract"].removeprefix("evaluator_contract_")
            value = record.get(section, {})
            row = {"source_path": "<V3_ROOT>/FINAL_EVALUATION_RECORDS.json",
                   "source_row_key": identity["run_id"] + "|" + version,
                   "source_json_pointer": "/" + str(index) + "/" + section}
            if section != "row":
                row.update({"identity_" + k: identity.get(k, MISSING) for k in IDENTITY})
                row["section_present"] = section in record
            for key, v in value.items():
                # Device-specific raw provenance remains readable at its exact JSON pointer.
                # All scalar result values and metric names are transcribed verbatim.
                row[key] = ("SOURCE_JSON_POINTER:" + row["source_path"] + "#" + row["source_json_pointer"] + "/" + key
                            if key == "raw_source_hashes" else v)
            part = identity["method_id"] if section == "row" and identity["domain"] == "CORE" else ""
            groups[(identity["domain"], version, part)].append(row)
        for (domain, version, part), rows in sorted(groups.items()):
            suffix = "_" + part if part else ""
            self.write_csv("run_statistics/" + prefix + "_" + domain + "_" + version + suffix + ".csv", rows)

    def export_retained_metadata(self):
        """Transcribe extra existing evaluator statistics omitted by the row ledger."""
        locator_check = self.normalize_file_index()
        with (self.output / "RUN_RESULT_FILES.csv").open(encoding="utf-8", newline="") as stream:
            sources = [row for row in csv.DictReader(stream)
                       if row["category"] in ["evaluator_summary", "evaluator_capture", "matched_trajectory_manifest"]
                       and row["read_status"] == "READ_COMPLETE_JSON"]
        with (self.output / "V3_RUN_RESULT_INDEX.csv").open(encoding="utf-8", newline="") as stream:
            native_index = {row["run_id"]: row for row in csv.DictReader(stream)}
        groups = collections.defaultdict(list)
        checks = collections.Counter()
        differences = []
        mapping = set()

        def flatten(value, prefix=""):
            result = {}
            for key, child in value.items():
                escaped = key.replace("~", "~0").replace("/", "~1")
                pointer = prefix + "/" + escaped
                if isinstance(child, dict):
                    result.update(flatten(child, pointer))
                else:
                    result[pointer] = child
            return result

        def read(source):
            value, row = self.read_json(self.resolve(source["source_path"]), source["category"], source["verified_sha256"])
            return source, value, row

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for source, value, read_row in pool.map(read, sources):
                checks[source["category"] + ":" + read_row["read_status"]] += 1
                if read_row.get("verified_sha256") != source["verified_sha256"]:
                    differences.append({"source_path": source["source_path"], "first_read_sha256": source["verified_sha256"],
                                        "second_read_sha256": read_row.get("verified_sha256", "unknown")})
                if not isinstance(value, dict):
                    continue
                native = native_index[source["source_row_key"]]
                version = source["version_scope"].rsplit("/", 1)[-1]
                row = {"source_path": source["source_path"], "source_row_key": native["run_id"] + "|" + version,
                       "source_json_pointer": "", "run_id": native["run_id"], "domain": native["domain"],
                       "sequence_id": native["sequence_id"], "case_id": native["case_id"],
                       "method_id": native["method_id"], "evaluator_version": version,
                       "metadata_read_status": read_row["read_status"]}
                row.update(flatten(value))
                category = source["category"].upper()
                groups[(category, native["domain"], version)].append(row)
                mapping.update((category, key) for key in row if key.startswith("/"))
        for (category, domain, version), rows in sorted(groups.items()):
            rows.sort(key=lambda row: row["run_id"])
            self.write_csv("run_statistics/" + category + "_" + domain + "_" + version + ".csv", rows)
        self.write_csv("run_statistics/EVALUATOR_METADATA_COLUMN_MAP.csv", [
            {"table_family": category, "column": column, "original_json_pointer": column,
             "value_rule": "Original source value; scalar tokens preserved; arrays compact JSON; no metric computation"}
            for category, column in sorted(mapping)])
        summary_path = self.output / "RUN_COLLECTION_SUMMARY.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["semisynthetic_data_used"] = True
        summary["semisynthetic_data_generated"] = False
        summary["synthetic_data_generated"] = False
        summary["data_mode_note"] = "Existing real and semisynthetic result rows are used; no new synthetic data or performance experiment is generated. Original source-row flags are preserved."
        summary["additional_evaluator_metadata_transcription"] = {
            "source_file_count": len(sources), "read_counts": dict(checks),
            "second_read_hash_differences": differences,
            "reason": "Existing evaluator summary pass ratios, convergence and 3sigma fields are not all present in final row records; all are transcribed without recomputation.",
        }
        summary["receipt_locator_validation"] = locator_check
        replaced = {row["path"] for row in self.outputs}
        summary["outputs"] = [row for row in summary["outputs"] if row["path"] not in replaced] + self.outputs
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes_path = self.output / "RUN_COLLECTION_NOTES.md"
        notes = notes_path.read_text(encoding="utf-8")
        notes = notes.replace("`run_statistics/EVALUATION_{CORE,SEQUENCE,ADDENDUM}_{v3,v2}.csv`",
                              "`run_statistics/EVALUATION_CORE_{v3,v2}_{method_id}.csv` (541 rows per method) and `EVALUATION_{SEQUENCE,ADDENDUM}_{v3,v2}.csv`")
        notes = notes.replace("`RUN_RESULT_FILES.csv` records the files actually read",
                              "The shared `V3_RESULT_FILES.csv` includes the files actually read")
        extra = "\n## Evaluator metadata transcription\n\n`EVALUATOR_SUMMARY_*` preserves every existing evaluator `summary.json` field, including pass ratios, convergence and diagonal 3sigma diagnostics that the final row ledger does not repeat. `EVALUATOR_CAPTURE_*` preserves the archived capture-consistency metadata. Slash-prefixed columns are exact JSON pointers into each row's source file; `EVALUATOR_METADATA_COLUMN_MAP.csv` documents them. Missing JSON fields stay `__FIELD_ABSENT__` and null stays null. These tables contain the actually existing evaluator metadata only: failed non-invoked slots remain visible in the full run and evaluation indexes, without invented summaries. The additional read compared source hashes with the first collection read and computed no performance metric.\n"
        if "\n## Evaluator metadata transcription\n" in notes:
            notes = notes.split("\n## Evaluator metadata transcription\n", 1)[0]
        extra += "\nFor the compact file inventory, `SCHEMA:Snnnn` resolves through `run_statistics/FILE_SCHEMA_INDEX.csv`. Scope `@` joins `source_row_key` (run_id) to `V3_RUN_RESULT_INDEX.csv`; `@native_archive_receipt`, `@v3_archive_receipt`, and `@v2_archive_receipt` mean the exact receipt field in that same run-index row. The suffix is an RFC6901 JSON pointer, with slash and tilde escaped. Note `N1` means a historical recorded hash is not a new hash verification unless `verified_sha256` is populated. `original_path` is the historical source-member path. A released member's `source_path` is the receipt-relative storage locator checked for absence, not an assertion that a retained G: copy was ever created. Only PRESENT or GZIP_PAYLOAD_PRESENT_HEADER_READ asserts a current payload. Empty optional inventory metadata fields do not mean numeric zero.\n"
        extra += ("\n`RUN_RESULT_FILES.csv` is the ignored local intermediate generated by this collector. "
                  "The shared canonical `V3_RESULT_FILES.csv` includes all " + format(summary["file_index_rows"], ",") +
                  " rows from that intermediate together with the separately collected source-table and archive records. "
                  "Source paths, statuses, hashes and dictionary references are preserved in that merge.\n")
        notes_path.write_text(notes + extra, encoding="utf-8")
        print(json.dumps(summary["additional_evaluator_metadata_transcription"]), flush=True)

    def normalize_file_index(self):
        """Validate exact receipt members, RFC6901 pointers, and compact repeated fields."""
        path = self.output / "RUN_RESULT_FILES.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        # A completed compact index already has exact @run_index receipt locators.
        if rows and any(row.get("receipt_source", "").startswith("@") for row in rows):
            return {"status": "EXACT_LOCATORS_ALREADY_NORMALIZED", "file_rows": len(rows)}
        receipt_paths = sorted({row["receipt_source"].split("#", 1)[0] for row in rows
                                if "#/" in row.get("receipt_source", "")})
        receipts = {}
        failed_receipts = []
        receipt_hash_differences = []
        first_hashes = {row["source_path"]: row["verified_sha256"] for row in rows
                        if row.get("category", "").endswith("_archive_receipt")}
        def read(alias):
            value, metadata = self.read_json(self.resolve(alias), "receipt_locator_validation")
            return alias, value, metadata
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            for alias, value, metadata in pool.map(read, receipt_paths):
                if first_hashes.get(alias) and first_hashes[alias] != metadata.get("verified_sha256"):
                    receipt_hash_differences.append(alias)
                if isinstance(value, dict):
                    receipts[alias] = value
                else:
                    failed_receipts.append(alias)
        checked, unresolved = 0, []
        for row in rows:
            locator = row.get("receipt_source", "")
            if "#/" not in locator:
                continue
            alias, pointer = locator.split("#", 1)
            match = re.search(r"source member=([^;]+)", row.get("notes", ""))
            member = match.group(1) if match else pointer.split("/", 2)[-1].replace("~1", "/").replace("~0", "~")
            receipt = receipts.get(alias, {})
            found = next(((group, key) for key in [member, member + ".gz"]
                          for group in ["files", "discarded_payloads", "omitted_payload_hashes"]
                          if key in receipt.get(group, {})), None)
            if found is None:
                unresolved.append({"source_path": row["source_path"], "receipt_source": locator, "member": member})
                continue
            group, key = found
            escaped = key.replace("~", "~0").replace("/", "~1")
            row["receipt_source"] = alias + "#/" + group + "/" + escaped
            checked += 1
        self.write_csv("RUN_RESULT_FILES.csv", self.compact_file_rows(rows), FILE_FIELDS)
        return {"status": "PASS" if not unresolved and not failed_receipts and not receipt_hash_differences else "PARTIAL_UNRESOLVED_LOCATORS",
                "receipt_files_read": len(receipts), "exact_member_locators_checked": checked,
                "unresolved_locators": unresolved, "unread_receipts": failed_receipts,
                "second_read_hash_differences": receipt_hash_differences}

    def inspect_slot(self, native, evals):
        """Read exact retained metadata and receipt-referenced payload headers only."""
        run_id = native["run_id"]
        files, conflicts = [], []
        values = {}
        scope = {"source_row_key": run_id, "sequence_scope": native["sequence_id"],
                 "method_scope": native["method_id"], "case_scope": native["case_id"],
                 "version_scope": "PROTOCOL_V3"}
        for kind, record in [("native", native)] + list(evals.items()):
            scope_here = dict(scope, version_scope="PROTOCOL_V3/" + kind)
            root = Path(record["archive_output_root"])
            receipt_path = Path(record["archive_receipt"])
            receipt, receipt_row = self.read_json(receipt_path, kind + "_archive_receipt", scope=scope_here)
            files.append(receipt_row)
            values[kind + "_archive_receipt_read_status"] = receipt_row["read_status"]
            if not isinstance(receipt, dict):
                continue
            retained = receipt.get("files", {})
            discarded = {**receipt.get("omitted_payload_hashes", {}), **receipt.get("discarded_payloads", {})}
            logical = sorted(set(retained) | set(discarded))
            values[kind + "_receipt_original_member_count"] = len(logical)
            if kind == "native":
                wanted = {
                    "V3_NATIVE_SUMMARY.json": ("native_result", True),
                    "RUN_MANIFEST.json": ("native_manifest", True),
                    "OUTPUT_SEAL.json": ("native_output_seal", True),
                    "V3_RUNTIME_CONFIG.yaml": ("runtime_config", False),
                    "KF_GINS_Navresult.nav": ("nav_full_sampling", False),
                    "KF_GINS_STD.txt": ("std_full_sampling", False),
                    "EVAL_NAV.csv": ("native_eval_nav", False),
                    "NATIVE_OPENAT.strace": ("native_access_log", False),
                }
            else:
                wanted = {
                    "EVALUATION_RESULT.json": ("evaluation_result", True),
                    "OUTPUT_SEAL.json": ("evaluation_output_seal", True),
                    "FROZEN_EVALUATOR/summary.json": ("evaluator_summary", True),
                    "FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json": ("evaluator_capture", True),
                    "FROZEN_EVALUATOR/EVALUATOR_STRACE_AUDIT.json": ("evaluation_access_audit", True),
                    "FROZEN_EVALUATOR/error_series.csv": ("error_series", False),
                    "FROZEN_EVALUATOR/MATCHED_TRAJECTORY.csv": ("matched_trajectory", False),
                    "EVAL_NAV_V3.nav": ("evaluator_nav", False),
                    "FROZEN_EVALUATOR/EVALUATOR_OPENAT.strace": ("evaluator_access_log", False),
                }
                # The receipt is authoritative for any alternate matched/sparse filename.
                for name in logical:
                    if "MATCHED_TRAJECTORY" in name and name.endswith(".json"):
                        wanted[name] = ("matched_trajectory_manifest", True)
                    elif "MATCHED_TRAJECTORY" in name and not name.endswith(".gz"):
                        wanted[name] = ("matched_trajectory", False)
                    if "sparse" in name.lower() and "nav" in name.lower():
                        wanted[name] = ("sparse_nav", False)
            seen_physical = set()
            for member, (category, read_all) in wanted.items():
                located = next(((group, key, receipt[group][key]) for key in [member, member + ".gz"]
                                for group in ["files", "discarded_payloads", "omitted_payload_hashes"]
                                if key in receipt.get(group, {})), None)
                detail = located[2] if located else None
                status_prefix = kind + "_" + category
                if detail is None:
                    known_generated = member in native.get("file_hashes", {}) if kind == "native" else False
                    failed_before_output = (native["status"] == "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT" if kind == "native"
                                            else not record["row"].get("evaluation_invoked", False))
                    status = ("NOT_GENERATED_AFTER_FAILURE" if failed_before_output else
                              "NOT_REGISTERED_FOR_THIS_SLOT" if not known_generated else "INDEXED_ONLY_UNCONFIRMED")
                    # v2 uses native NAV directly; no separate transformed NAV is required.
                    if kind == "v2" and category == "evaluator_nav":
                        status = "NOT_APPLICABLE_V2_USES_NATIVE_NAV"
                    values[status_prefix + "_path"] = "unknown"
                    values[status_prefix + "_status"] = status
                    continue
                stored = detail.get("storage_relative_path", member)
                path = root / stored
                if str(path) in seen_physical:
                    continue
                seen_physical.add(str(path))
                row = self.source_row(path, category, **scope_here)
                group, exact_member, _ = located
                escaped_member = exact_member.replace("~", "~0").replace("/", "~1")
                row.update(receipt_source=self.alias(receipt_path) + "#/" + group + "/" + escaped_member,
                           recorded_sha256=detail.get("sha256", detail.get("source_sha256", "")),
                           original_path=self.alias(Path(receipt.get("source_root", str(root))) / member),
                           notes="Hash is recorded unless verified_sha256 is populated; source member=" + member)
                released = group in ("discarded_payloads", "omitted_payload_hashes")
                values[status_prefix + "_path"] = self.alias(path)
                values[status_prefix + "_recorded_source_sha256"] = detail.get("source_sha256", "unknown")
                try:
                    info = path.stat()
                    row.update(size_bytes=info.st_size, retention_status="PRESENT", read_status="PRESENT_METADATA_ONLY")
                    if released:
                        row["notes"] += "; CONFLICT_PRESENT_BUT_RECEIPT_SAYS_RELEASED"
                        conflicts.append({"run_id": run_id, "version": kind, "field": category,
                                          "source_a": self.alias(path), "source_b": self.alias(receipt_path),
                                          "value_a": "PRESENT", "value_b": "RELEASED_BY_RECEIPT"})
                    if read_all:
                        value, read_row = self.read_json(path, category, row["recorded_sha256"], scope_here)
                        row.update(read_row)
                        if category in ("native_result", "evaluation_result") and value is not None:
                            original = native if kind == "native" else record["row"]
                            observed = value if kind == "native" else value.get("row", {})
                            compare_keys = list(observed) if kind != "native" else [k for k in IDENTITY + ["status", "terminal_status", "config_hash", "nav_sha256", "std_sha256", "native_counters"] if k in observed]
                            differences = [k for k in compare_keys if observed.get(k, MISSING) != original.get(k, MISSING)]
                            values[kind + "_individual_ledger_differences"] = len(differences)
                            for key in differences:
                                conflicts.append({"run_id": run_id, "version": kind, "field": key,
                                                  "source_a": self.alias(path) + ("#/row/" if kind != "native" else "#/") + key,
                                                  "source_b": "<V3_ROOT>/FINAL_" + ("RUN" if kind == "native" else "EVALUATION") + "_RECORDS.json",
                                                  "value_a": self.cell(observed.get(key, MISSING)),
                                                  "value_b": self.cell(original.get(key, MISSING))})
                    elif category == "runtime_config":
                        data = path.read_bytes()
                        data.decode("utf-8")
                        row.update(read_status="READ_COMPLETE_TEXT", verified_sha256=hashlib.sha256(data).hexdigest())
                    elif category in ("error_series", "matched_trajectory", "sparse_nav", "nav_full_sampling", "std_full_sampling", "native_eval_nav", "evaluator_nav"):
                        opener = gzip.open if path.suffix == ".gz" else open
                        with opener(path, "rt", encoding="utf-8") as stream:
                            header = stream.readline().strip()
                        row.update(read_status="READ_HEADER_ONLY", columns=header, row_count="unknown")
                        if path.suffix == ".gz":
                            row.update(archive_path=self.alias(path), archive_member=member,
                                       retention_status="GZIP_PAYLOAD_PRESENT_HEADER_READ")
                    # Raw strace contents are intentionally not opened.
                except FileNotFoundError:
                    row.update(read_status="NOT_PRESENT",
                               retention_status="RELEASED_BY_RECORDED_POLICY" if released else "EXPECTED_NOT_FOUND")
                except (OSError, UnicodeError) as error:
                    row.update(read_status="READ_ERROR", notes=str(error))
                values[status_prefix + "_status"] = row["retention_status"]
                values[status_prefix + "_read_status"] = row["read_status"]
                files.append(row)
            # These post-archive result/retention records are outside the original seal.
            # Listing only this exact ledger-selected slot does not search other result roots.
            try:
                extra_names = {path.name for path in root.iterdir() if path.is_file()}
            except OSError:
                extra_names = set()
            for extra_name in ["V3R_NATIVE_RECORD.json", "V3R_EVALUATION_RECORD.json", "COMPACT_RELEASE.json"]:
                if extra_name not in extra_names:
                    continue
                value, extra_row = self.read_json(root / extra_name, kind + "_post_archive_record", scope=scope_here)
                files.append(extra_row)
                if value is None or extra_name == "COMPACT_RELEASE.json":
                    continue
                observed = value if kind == "native" else value.get("row", {})
                original = native if kind == "native" else record["row"]
                keys = IDENTITY + ["status", "terminal_status", "config_hash", "nav_sha256", "std_sha256", "native_counters"] if kind == "native" else list(observed)
                for key in keys:
                    if key in observed and observed[key] != original.get(key, MISSING):
                        conflicts.append({"run_id": run_id, "version": kind, "field": key,
                                          "source_a": self.alias(root / extra_name) + ("#/row/" if kind != "native" else "#/") + key,
                                          "source_b": "<V3_ROOT>/FINAL_" + ("RUN" if kind == "native" else "EVALUATION") + "_RECORDS.json",
                                          "value_a": self.cell(observed[key]), "value_b": self.cell(original.get(key, MISSING))})
        return values, files, conflicts

    def run(self):
        npath, epath = self.root / "FINAL_RUN_RECORDS.json", self.root / "FINAL_EVALUATION_RECORDS.json"
        regpath = self.root / "00_CONTROL/ORIGINAL_V3_METADATA/00_PREREGISTRATION/REGISTRY.json"
        natives, meta = self.read_json(npath, "final_native_ledger", "c8fd55b3895643a48a06c084b1b3d438ba7a12f5802703510f4b9887fd48ab92")
        self.files.append(meta)
        evaluations, meta = self.read_json(epath, "final_evaluation_ledger", "4c0bbaec5b4aa14f22ca45ff966cc1e9d03824a2afef08133b0e42bfec81e319")
        self.files.append(meta)
        registry, meta = self.read_json(regpath, "frozen_run_registry", "c89813daff415f6afbc723e954555bd8256b9d7f5221e49d56a02948552c1222")
        self.files.append(meta)
        if not all(isinstance(value, list) for value in [natives, evaluations, registry]):
            raise ValueError("Required final ledger or frozen registry could not be fully read")
        retention_rows = self.read_csv(self.code / "docs/paper_rebuild/v3/ERROR_SERIES_RETENTION_INDEX.csv", "retention_index")
        retention = {row["run_id"]: row for row in retention_rows}
        for name in ["ARCHIVE_RECONCILIATION.csv", "PURGE_LEDGER_20260919.csv"]:
            self.read_csv(self.code / "docs/paper_rebuild/v3" / name, "historical_storage_record")
        for name in ["REGISTRY_GATE.json", "REGISTRY_FILE_SEAL.json"]:
            _, meta = self.read_json(regpath.parent / name, "frozen_registry_gate")
            self.files.append(meta)
        for name in ["00_CONTROL/RETENTION_POLICY.json", "00_CONTROL/FIRST_EIGHT_BATCHES_RETENTION_RELEASE_SUMMARY.json"]:
            _, meta = self.read_json(self.root / name, "storage_policy")
            self.files.append(meta)
        nmap, emap, rmap = {}, collections.defaultdict(dict), {}
        duplicate_n, duplicate_e, duplicate_r = [], [], []
        for i, row in enumerate(registry):
            if row["run_id"] in rmap:
                duplicate_r.append(row["run_id"])
            rmap[row["run_id"]] = (i, row)
        for i, row in enumerate(natives):
            if row["run_id"] in nmap:
                duplicate_n.append(row["run_id"])
            nmap[row["run_id"]] = (i, row)
        for i, record in enumerate(evaluations):
            row = record["row"]
            version = row["evaluator_contract"].removeprefix("evaluator_contract_")
            if version in emap[row["run_id"]]:
                duplicate_e.append(row["run_id"] + "|" + version)
            emap[row["run_id"]][version] = (i, record)
        self.export_section(evaluations, "row", "EVALUATION")
        self.export_section(evaluations, "body_frame_bias", "BODY_FRAME_BIAS")
        self.export_section(evaluations, "transform", "EVALUATION_TRANSFORM")
        counter_rows = []
        for i, row in enumerate(natives):
            counter_rows.append({"source_path": "<V3_ROOT>/FINAL_RUN_RECORDS.json",
                                 "source_row_key": row["run_id"], "source_json_pointer": "/" + str(i) + "/native_counters",
                                 **{key: row.get(key, MISSING) for key in IDENTITY}, **row.get("native_counters", {})})
        self.write_csv("run_statistics/NATIVE_COUNTERS.csv", counter_rows)
        index = []
        identity_differences = []
        for run_id in sorted(set(rmap) | set(nmap) | set(emap)):
            ni, native = nmap.get(run_id, (None, {}))
            ri, registered = rmap.get(run_id, (None, {}))
            base = native or registered
            row = {key: base.get(key, "unknown") for key in IDENTITY}
            row.update(native_ledger_source="<V3_ROOT>/FINAL_RUN_RECORDS.json",
                       native_ledger_json_pointer="/" + str(ni) if ni is not None else "unknown",
                       registry_source=self.alias(regpath), registry_json_pointer="/" + str(ri) if ri is not None else "unknown",
                       native_ledger_status="READ" if native else "EXPECTED_NOT_FOUND",
                       native_status=native.get("status", "unknown"), native_failure_classification=native.get("failure_classification", "unknown"),
                       protocol_id=native.get("protocol_id", "unknown"), scientific_code_commit=native.get("code_commit", "unknown"),
                       config_hash_recorded=native.get("config_hash", "unknown"), nav_sha256_recorded=native.get("nav_sha256", "unknown"),
                       std_sha256_recorded=native.get("std_sha256", "unknown"),
                       native_archive_root=native.get("archive_output_root", "unknown"),
                       native_archive_receipt=native.get("archive_receipt", "unknown"),
                       historical_native_output_root=native.get("output_root", "unknown"),
                       native_invocation_count=native.get("native_invocation_count", "unknown"),
                       native_output_row_count=native.get("bounded_gate", {}).get("row_count", "unknown"),
                       native_runtime_seconds=native.get("runtime_seconds", "unknown"),
                       logical_aliases="F03;A02" if base.get("method_id") == "F03" else "F04;A01" if base.get("method_id") == "F04" else base.get("method_id", "unknown"),
                       five_configuration_view=base.get("method_id") in ["F01", "F02", "F03", "A04", "F04"],
                       natural_three_sequence_view=base.get("domain") == "SEQUENCE" or (base.get("domain") == "CORE" and base.get("case_id") == "C00_clean_normal"),
                       source_registry_row_pointer="<V3_ROOT>/FINAL_RUN_RECORDS.json#/" + str(ni) + "/source_registry_row",
                       retention_decision=retention.get(run_id, {}).get("retain_error_series", "unknown"),
                       retention_reason=retention.get(run_id, {}).get("reason", "unknown"),
                       metadata_scan_phase=self.phase)
            for key in ["duration_s", "window_start_s", "window_end_s", "outage_start_s", "outage_end_s", "seed_value", "anchor_time_s"]:
                row["case_meta_" + key] = base.get("case_meta", {}).get(key, "unknown")
            for key in IDENTITY:
                if native and registered and native.get(key, MISSING) != registered.get(key, MISSING):
                    identity_differences.append({"run_id": run_id, "field": key, "registry_value": self.cell(registered.get(key, MISSING)), "native_value": self.cell(native.get(key, MISSING))})
            for version in ["v3", "v2"]:
                ei, evaluation = emap.get(run_id, {}).get(version, (None, {}))
                erow = evaluation.get("row", {})
                row[version + "_ledger_json_pointer"] = "/" + str(ei) + "/row" if ei is not None else "unknown"
                row[version + "_ledger_status"] = "READ" if evaluation else "EXPECTED_NOT_FOUND"
                suffix = "_" + base["method_id"] if base.get("domain") == "CORE" else ""
                row[version + "_statistics_file"] = "run_statistics/EVALUATION_" + base.get("domain", "unknown") + "_" + version + suffix + ".csv"
                row[version + "_archive_root"] = evaluation.get("archive_output_root", "unknown")
                row[version + "_archive_receipt"] = evaluation.get("archive_receipt", "unknown")
                for key in ["status", "failure_classification", "evaluation_invoked", "evaluator_contract", "metrics_admitted",
                            "time_start", "time_end", "matched_epoch_count", "output_epoch_count", "reference_epoch_count",
                            "unmatched_epoch_count", "coverage_ratio", "sequence_window_start_s", "sequence_window_end_s",
                            "horizontal_rmse_m", "position_3d_rmse_m", "up_rmse_m", "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg",
                            "yaw_p95_absolute_deg", "uncertainty_status"]:
                    row[version + "_" + key] = erow.get(key, "unknown")
            index.append(row)
        if self.phase == "full":
            total = len(index)
            start = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = {pool.submit(self.inspect_slot, nmap[row["run_id"]][1],
                                       {v: rec[1] for v, rec in emap[row["run_id"]].items()}): row
                           for row in index if row["run_id"] in nmap}
                for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
                    row = futures[future]
                    values, files, conflicts = future.result()
                    row.update(values)
                    self.files.extend(files)
                    self.conflicts.extend(conflicts)
                    if count % 500 == 0 or count == total:
                        print(json.dumps({"metadata_slots_read": count, "native_total": total,
                                          "elapsed_seconds": round(time.monotonic() - start, 1)}), flush=True)
        self.write_csv("V3_RUN_RESULT_INDEX.csv", index)
        self.write_csv("run_statistics/FAILURE_RUNS.csv", [row for row in index if row["native_status"] not in ["COMPLETED", "unknown"]])
        self.write_csv("run_statistics/NATURAL_C00_ALL_CONFIGS.csv", [row for row in index if row["natural_three_sequence_view"]])
        self.write_csv("RUN_RESULT_FILES.csv", self.compact_file_rows(self.files), FILE_FIELDS)
        self.write_csv("run_statistics/REGISTRY_IDENTITY_DIFFERENCES.csv", identity_differences,
                       ["run_id", "field", "registry_value", "native_value"])
        self.write_csv("run_statistics/INDIVIDUAL_LEDGER_DIFFERENCES.csv", self.conflicts,
                       ["run_id", "version", "field", "source_a", "source_b", "value_a", "value_b"])
        expected_eval = {(rid, version) for rid in rmap for version in ["v3", "v2"]}
        actual_eval = {(rid, version) for rid, versions in emap.items() for version in versions}
        summary = {
            "schema": "V3_RESULTS_READONLY_COLLECTION_V1", "phase": self.phase,
            "data_mode": "existing_results_descriptive_collection", "synthetic_data_used": False,
            "semisynthetic_data_used": True, "semisynthetic_data_generated": False, "synthetic_data_generated": False,
            "data_mode_note": "Existing real and semisynthetic result rows are used; no new synthetic data or performance experiment is generated. Original source-row flags are preserved.",
            "native_calls": 0, "provider_generator_calls": 0, "evaluator_calls": 0, "aggregate_controller_calls": 0,
            "raw_reference_payload_opens": 0, "new_performance_statistics": 0,
            "native_records_read": len(natives), "evaluation_records_read": len(evaluations), "registry_records_read": len(registry),
            "native_unique_ids": len(nmap), "evaluation_unique_slots": len(actual_eval),
            "native_by_domain": dict(collections.Counter(x["domain"] for x in natives)),
            "native_by_status": dict(collections.Counter(x["status"] for x in natives)),
            "native_by_data_mode": dict(collections.Counter(x["data_mode"] for x in natives)),
            "evaluation_by_status": dict(collections.Counter(x["row"]["status"] for x in evaluations)),
            "actual_evaluator_invocations_recorded": sum(x["row"].get("evaluation_invoked") is True for x in evaluations),
            "missing_native_ids": sorted(set(rmap) - set(nmap)), "extra_native_ids": sorted(set(nmap) - set(rmap)),
            "missing_evaluation_slots": sorted(expected_eval - actual_eval), "extra_evaluation_slots": sorted(actual_eval - expected_eval),
            "duplicate_native_ids": duplicate_n, "duplicate_registry_ids": duplicate_r, "duplicate_evaluation_slots": duplicate_e,
            "registry_identity_difference_count": len(identity_differences), "individual_ledger_difference_count": len(self.conflicts),
            "file_index_rows": len(self.files),
            "file_read_status_counts": dict(collections.Counter(x["read_status"] for x in self.files)),
            "file_retention_status_counts": dict(collections.Counter(x["retention_status"] for x in self.files)),
            "file_category_read_counts": {category: dict(collections.Counter(row["read_status"] for row in self.files if row["category"] == category)) for category in sorted({row["category"] for row in self.files})},
            "payload_status_counts": {key: dict(collections.Counter(str(row.get(key, "unknown")) for row in index)) for key in sorted({k for row in index for k in row if k.endswith("_status") and any(t in k for t in ["nav", "std", "error_series", "matched_trajectory", "result", "manifest", "runtime_config", "access_log"])})},
            "outputs": self.outputs,
            "hash_policy": "recorded_sha256 is copied from historical evidence; verified_sha256 is calculated only over bytes read in this invocation",
            "large_payload_read_boundary": "NAV/STD are not reconstructed; existing error_series/matched payloads are header-only reads; existing result JSON and tables are fully read",
        }
        (self.output / "RUN_COLLECTION_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes = """# Protocol V3 per-run collection\n\nThe run index has one row per physical native identity, with separate v3 and v2 evaluation columns. It does not count F03/A02 or F04/A01 aliases twice. BY2 C00 remains inside CORE; the natural-sequence view selects those 11 rows plus the 22 SEQUENCE rows.\n\n`run_statistics/EVALUATION_{CORE,SEQUENCE,ADDENDUM}_{v3,v2}.csv` contains every existing evaluation row, including the non-invoked failure slots, with all original scalar metric names and values. `source_path`, `source_row_key`, and the zero-based JSON pointer identify each original cell; a column name appends directly to that pointer. JSON floats use Decimal during reading, so metric decimal tokens are not rounded through binary floating point. Boolean tokens remain true/false, null remains null, and `__FIELD_ABSENT__` means the source never had that field. Blank original strings stay blank. The smaller run index uses unknown for absent descriptive fields.\n\nThe only portable path transformation is an exact local-root alias replacement. `raw_source_hashes` cells retain exact pointers to the original JSON rather than repeating unnecessary device-specific raw filenames. Nested provider hashes retain their original JSON values. `BODY_FRAME_BIAS_*`, `EVALUATION_TRANSFORM_*`, and `NATIVE_COUNTERS.csv` preserve all existing associated numerical fields without calculation.\n\nThe top-level PROTOCOL_V3 identity, config hash, code commit and native status are current-run fields. `source_registry_row` contains inherited preparation identities and historical fields; its old `terminal_status` or `runtime_config_hash` is not the V3 terminal or V3 config hash. Its exact source pointer is retained in the index. `case_meta` preserves registered duration, seed and support windows; unknown values are never filled with zero.\n\n`RUN_RESULT_FILES.csv` records the files actually read and the relevant payload paths named by each retained archive receipt. These archive roots are retained directories, not ZIP files. Gzip headers demonstrate current accessibility of those particular payloads, not a full payload read. Error-series release and full NAV/STD omission use explicit discard/omission receipts. Missing expected retained files remain EXPECTED_NOT_FOUND. Original strace payloads are metadata-only; retained audit JSON is fully read. No raw/reference input is opened.\n\nEvery existing final result JSON, native summary, manifest, runtime config, evaluator summary, capture and access-audit file encountered through the authoritative per-slot receipts is read in full in phase `full`. Failures are retained even when NAV, STD, metrics, or an evaluator child were never generated. Sparse NAV and matched trajectories are separate categories; a matched trajectory is never relabelled as full NAV. `NOT_REGISTERED_FOR_THIS_SLOT` means no such member is in the actual slot receipt, not a claim that an undocumented copy cannot exist elsewhere.\n\n`REGISTRY_IDENTITY_DIFFERENCES.csv` and `INDIVIDUAL_LEDGER_DIFFERENCES.csv` preserve disagreements rather than choosing a source by timestamp or filename. The summary states exact checked counts and any missing slots. Hashes copied from existing evidence and hashes calculated during this collection are separate columns. Raw result payloads remain in place.\n\nCurrent phase: PHASE. Scientific verification, mathematical review, defect diagnosis, repair, replay, evaluator execution, aggregate execution and performance-statistic recomputation were not performed.\n""".replace("PHASE", self.phase)
        (self.output / "RUN_COLLECTION_NOTES.md").write_text(notes, encoding="utf-8")
        print(json.dumps({key: summary[key] for key in ["phase", "native_records_read", "evaluation_records_read", "file_index_rows", "individual_ledger_difference_count"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["ledgers", "full", "metadata"], default="full")
    args = parser.parse_args()
    collector = Collector(load_paths(args.paths), args.output, args.phase)
    if args.phase == "metadata":
        collector.export_retained_metadata()
    else:
        collector.run()
        if args.phase == "full":
            collector.export_retained_metadata()


if __name__ == "__main__":
    main()
