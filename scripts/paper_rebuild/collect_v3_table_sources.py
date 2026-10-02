#!/usr/bin/env python3
"""Read retained V3 tables and source maps; never import the scientific project.

Reads only explicit result roots and references in existing manifests. Writes
portable string-preserving views to the supplied collection directory. No solver,
provider, evaluator, plotting, aggregate controller, raw/trace payload, or archive
execution is possible here. All numeric CSV tokens remain strings.
"""
import argparse
import collections
import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


FIELDS = [
    "category", "source_path", "source_row_key", "read_status", "retention_status",
    "archive_path", "archive_member", "recorded_sha256", "verified_sha256",
    "row_count", "columns", "sequence_scope", "method_scope", "case_scope",
    "version_scope", "source_commit", "source_bytes", "shared_view", "notes",
]
REL_FIELDS = [
    "presentation_set", "artifact_id", "artifact_path", "artifact_status",
    "source_path", "source_row_key", "source_columns", "source_value",
    "display_value", "comparison_status", "protocol_scope", "evaluator_version",
    "source_recorded_sha256", "manifest_path", "derivation_or_qualifier",
]
IDENTITY = [
    "run_id", "method_id", "profile_id", "configuration_id", "case_id",
    "case_family", "degradation_type_id", "seed_index", "effective_profile",
    "sequence_id", "dataset_id", "domain", "evaluator_version", "evaluator_contract",
    "evaluation_status", "solver_terminal_status", "status", "failure_classification",
    "metric", "metric_name", "comparison", "family", "scope", "segment_id",
    "start_convention", "variant", "config", "duration_s", "outage_duration_s",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local-config", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--refine-links-only", action="store_true", help="Refine already-read source links using existing collection and small source manifests only")
    args = ap.parse_args()
    # Only simple existing key/value paths are needed. No project YAML loader.
    config = {}
    for line in args.local_config.read_text().splitlines():
        match = re.match(r"^  ([A-Za-z0-9_]+):\s*(.*?)\s*$", line)
        if match:
            config[match.group(1)] = match.group(2).strip("\"'")
    code = Path(config["code_root"])
    original = Path(config["audit_source_worktree"])
    root = Path(config["clean_root"]) / "stages/CLEAN8_PROTOCOL_V3"
    output = args.output.resolve()
    expected = code / "docs/paper_rebuild/audit_xbpg_20261001/v3_results"
    if output != expected.resolve():
        raise SystemExit("Output must be the authorized v3_results collection directory")
    output.mkdir(parents=True, exist_ok=True)
    aliases = {"<" + k.upper() + ">": v for k, v in config.items() if v.startswith("/")}
    aliases["<V3_ROOT>"] = str(root)
    aliases["<V3>"] = str(root)
    aliases["<HEXT_SCRATCH>"] = config["hext_scratch"]
    # These dollar aliases are defined by the already-existing, read-only
    # hx05_common.py:paths mapping, not guessed from an unrelated directory.
    external_stage = Path(config["clean_root"]) / "stages/CLEAN9_EXTERNAL_COMPARISON"
    dollar_aliases = {"$W": str(original), "$V3": str(root), "$RAW_ROOT": config["raw_root"],
                      "$CLEAN_ROOT": config["clean_root"]}
    for key, relative in {"HX02": "HX02_FIVE_CATEGORY", "HX02D": "HX02D_HARTLEY_DIAGNOSTIC",
                          "HX02E": "HX02E_HARTLEY_OFFICIAL", "HX03R2": "HX03R2_AUDIT_REEVAL",
                          "HX05": "HX05_CLOSEOUT"}.items():
        dollar_aliases["$" + key] = str(external_stage / relative)
    preferred = {v: k for k, v in aliases.items()}
    preferred[str(code)] = "<CODE_ROOT>"
    preferred[str(original)] = "<AUDIT_SOURCE_WORKTREE>"
    preferred[str(root)] = "<V3_ROOT>"
    pairs = sorted(preferred.items(), key=lambda x: -len(x[0]))

    def portable(value):
        if not isinstance(value, str):
            value = str(value)
        for source, alias in pairs:
            value = value.replace(source, alias)
        return value

    def resolve(value, base=None):
        value = str(value)
        for alias, path in aliases.items():
            value = value.replace(alias, path)
        for alias, path in sorted(dollar_aliases.items(), key=lambda x: -len(x[0])):
            if value == alias or value.startswith(alias + "/"):
                value = path + value[len(alias):]
        p = Path(value)
        return p if p.is_absolute() else (base or code) / p

    records, parsed, relations, pins = {}, {}, [], collections.defaultdict(set)
    copied, projections, source_reads = [], [], collections.Counter()

    def category_for(path):
        s = portable(str(path))
        if "/07E_UNIFIED_FAILURE/" in s:
            return "B_FOLLOWUP_FAILURE_AUDIT_HISTORY"
        if "/10_UNCERTAINTY/" in s or "/v3/uncertainty/" in s:
            return "B_UNCERTAINTY_POSTPROCESSING"
        if s.startswith("<V3_ROOT>/07"):
            if any(x in path.name for x in ["V21", "T5BCR", "MAIN_TABLE", "BY2O_SEGMENT"]):
                return "AB_MIXED_PRESENTATION_OR_COMPARISON"
            return "A_PROTOCOL_V3_RESULT_TABLE"
        if "paper_package/gpss_v0" in s:
            return "B_PAPER_GPSS_V0"
        return "B_REFERENCED_SOURCE"

    def scope_for(path):
        s = portable(str(path))
        if "CLEAN6_SENSOR_MODEL_V21" in s:
            return "experiment_protocol=v2.1; evaluator=" + ("v2" if "/v2/" in s else "v3")
        if "CLEAN7_T5BC" in s or "T5BCR" in path.name:
            return "T5bc-R candidate sensitivity; separate physical runs; outside A"
        if "CLEAN7_HEXT" in s or "/hext/" in s:
            return "external/legacy-protocol comparison; original start/information structure retained; outside A"
        if "/uncertainty/" in s or "/10_UNCERTAINTY/" in s:
            return "UA-01/UA-02 existing postprocessing of sealed results; no new runs"
        if "paper_package" in s:
            return "MS-01 GPSS v0 presentation; rounded values are display only"
        if s.startswith("<V3_ROOT>"):
            version = "v2" if path.name.endswith("_V2.csv") else "v3" if path.name.endswith("_V3.csv") else "both/original manifest"
            protocol = "Protocol V3 versus v2.1" if "V21_COMPARISON" in path.name else "Protocol V3"
            return protocol + "; evaluator=" + version
        return "original source version retained; see manifest and source_commit"

    def rowkey(row, number):
        items = {k: row[k] for k in IDENTITY if row.get(k, "") != ""}
        return json.dumps({"data_row_1based": number, **items}, ensure_ascii=False, separators=(",", ":"))

    def write_csv(path, rows, fields):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def view_name(path):
        if path.parent in [root / "07_AGGREGATE", root / "07C_FAILURE_FAMILY_CONFIG", root / "07D_CLASSIFICATION_PROVENANCE"]:
            # Same-named 07C corrected comparisons must retain a distinct name.
            if path.parent.name == "07C_FAILURE_FAMILY_CONFIG" and "COMPARISON" in path.name:
                return "07C_CORRECTED__" + path.name
            return path.name
        label = portable(str(path))
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")

    def table_view(path, fields, rows):
        if path.name in ["error_series.csv", "MATCHED_TRAJECTORY.csv"] or path.name.startswith("HEADING_ERROR_SERIES"):
            return "PAYLOAD_RETAINED_IN_PLACE; fully parsed here, not copied to Git"
        # A's full per-run statistics are collected independently from every
        # evaluation JSON. Avoid duplicating the very wide aggregate copies.
        if path.parent == root / "07_AGGREGATE" and re.match(r"(?:CORE_541|ADDENDUM|SEQUENCE|SUBSET61)_TABLE_V[23]\.csv$", path.name):
            return "run_statistics/ (independent complete evaluation-statistic collection); original aggregate retained in place"
        if str(path).startswith(str(code)):
            return portable(str(path))
        if str(path).startswith(str(original)):
            counterpart = code / path.relative_to(original)
            # A current-worktree counterpart is an explicit separate source,
            # not a silent replacement. Its byte identity is checked below.
            if counterpart.exists() and counterpart.read_bytes() == path.read_bytes():
                return portable(str(counterpart)) + " [byte-identical counterpart verified this collection]"
        # Long metadata fields from huge B tables stay available at source.
        # All retained columns retain every row and every original string token.
        selected = list(fields)
        excluded = []
        if path.stat().st_size > 10_000_000 or len(fields) > 300:
            # B's old protocol and sensitivity tables carry hundreds of optional
            # diagnostics and large JSON provenance strings. Publish every row
            # with identity, states, support, RMSE and P95 tokens; the original
            # full source remains indexed and has actually been read in full.
            keep = set(IDENTITY + ["data_mode", "synthetic_data_used", "semisynthetic_data_used",
                                  "code_commit", "config_hash", "source_nav_sha256", "native_nav_sha256",
                                  "std_sha256", "evaluator_sha256", "trace_used_online", "evaluation_invoked",
                                  "sequence_window_start_s", "sequence_window_end_s", "matched_epoch_count",
                                  "output_epoch_count", "coverage_ratio", "registered_count", "finite_count",
                                  "algorithm_failure_count", "unavailable_count", "not_applicable_count"])
            keep.update(k for k in fields if any(t in k for t in ["rmse", "p95", "failure", "terminal_status", "evaluation_status"]))
            excluded = [k for k in fields if k not in keep or max((len(r.get(k, "")) for r in rows), default=0) > 350]
            selected = [k for k in fields if k not in excluded]
        final_rows = [
            {"_source_path": portable(str(path)), "_source_row_key": "data_row_1based:" + str(i),
             **{k: portable(r.get(k, "")) for k in selected}}
            for i, r in enumerate(rows, 1)
        ]
        outfields = ["_source_path", "_source_row_key"] + selected
        name = view_name(path)
        size_estimate = sum(sum(len(str(v)) for v in r.values()) for r in final_rows)
        if size_estimate > 5_000_000:
            groups = collections.defaultdict(list)
            for r in final_rows:
                groups[r.get("method_id") or r.get("profile_id") or "all"].append(r)
            if len(groups) == 1:
                group = next(iter(groups.values()))
                groups = {"part_%02d" % (i // 2000 + 1): group[i:i + 2000] for i in range(0, len(group), 2000)}
            viewpaths = []
            for method, group in sorted(groups.items()):
                target = output / "table_views" / (name[:-4] + "__" + re.sub(r"[^A-Za-z0-9_.-]", "_", method) + ".csv")
                write_csv(target, group, outfields)
                viewpaths.append(str(target.relative_to(output)))
        else:
            target = output / ("table_views" if excluded else "source_tables") / name
            write_csv(target, final_rows, outfields)
            viewpaths = [str(target.relative_to(output))]
        if excluded:
            projections.append({"source_path": portable(str(path)), "excluded_metadata_columns": excluded,
                                "retained_columns": selected, "rows": len(rows), "views": viewpaths})
        copied.extend(viewpaths)
        return ";".join(viewpaths)

    def read(path, category=None, sha="", note="", copy=True, force_text=False):
        path = Path(path)
        key = portable(str(path))
        if sha:
            pins[key].add(sha)
        if key in records:
            if note and note not in records[key]["notes"]:
                records[key]["notes"] += "; " + note
            return parsed.get(key)
        rec = dict.fromkeys(FIELDS, "")
        rec.update(category=category or category_for(path), source_path=key,
                   source_row_key="all records", read_status="INDEXED_NOT_FOUND",
                   retention_status="EXPECTED_SOURCE_NOT_FOUND", row_count="unknown",
                   version_scope=scope_for(path), source_commit="unknown", notes=note)
        records[key] = rec
        if "<" in str(path):
            rec["notes"] += "; unresolved source alias"
            return None

        if not path.exists():
            return None
        if path.is_dir():
            rec.update(read_status="DIRECTORY_EXISTS_ONLY", retention_status="EXISTS", row_count="not_applicable")
            return None
        rec["source_bytes"] = str(path.stat().st_size)
        rec["retention_status"] = "PRESENT_IN_PLACE"
        if str(path).startswith(config["raw_root"] + "/"):
            rec.update(read_status="REFERENCED_RAW_NOT_OPENED", row_count="not_read",
                       notes=rec["notes"] + "; raw/trace source outside result-only collection scope")
            return None
        if path.suffix.lower() in [".png", ".pdf", ".svg", ".gz", ".zip", ".imu", ".gnss", ".nav", ".std"] or path.name.endswith(".local.yaml"):
            rec.update(read_status="EXISTS_NOT_PARSED_PAYLOAD", row_count="not_read")
            return None
        if path.suffix.lower() in [".py", ".cpp", ".hpp", ".h", ".sh"]:
            rec.update(read_status="EXISTS_SOURCE_CODE_NOT_EXECUTED_OR_READ", row_count="not_read")
            return None
        try:
            data = path.read_bytes()
            text = data.decode("utf-8-sig")
            # Hash only bytes already fully read. No second traversal or payload hashing.
            rec["verified_sha256"] = hashlib.sha256(data).hexdigest()
            if path.suffix.lower() == ".csv":
                reader = csv.DictReader(text.splitlines(keepends=True))
                rows = list(reader)
                fields = list(reader.fieldnames or [])
                rec.update(read_status="READ_FULL_PARSED", row_count=str(len(rows)), columns=json.dumps(fields, ensure_ascii=False))
                for dest, names in [("sequence_scope", ["sequence_id", "dataset_id", "sequence"]),
                                    ("method_scope", ["method_id", "profile_id", "method"]),
                                    ("case_scope", ["case_family", "domain", "scope", "segment_id"])]:
                    rec[dest] = json.dumps(sorted({row.get(k, "") for row in rows for k in names if row.get(k, "")}), ensure_ascii=False)
                commits = sorted({r.get("code_commit", "") for r in rows if r.get("code_commit", "")})
                if commits:
                    rec["source_commit"] = ";".join(commits)
                if copy:
                    rec["shared_view"] = table_view(path, fields, rows)
                parsed[key] = rows
                source_reads["csv_files"] += 1
                source_reads["csv_records"] += len(rows)
                return rows
            if path.suffix.lower() == ".json":
                obj = json.loads(text, parse_float=str)
                rec.update(read_status="READ_FULL_PARSED", row_count=str(len(obj)) if isinstance(obj, list) else "1 JSON object",
                           columns=json.dumps(list(obj) if isinstance(obj, dict) else sorted({k for x in obj if isinstance(x, dict) for k in x}), ensure_ascii=False))
                if isinstance(obj, dict):
                    rec["source_commit"] = str(obj.get("code_commit", obj.get("code_freeze", obj.get("science_freeze", "unknown"))))
                parsed[key] = obj
                source_reads["json_files"] += 1
                return obj
            rec.update(read_status="READ_FULL_TEXT", row_count=str(len(text.splitlines())), columns="not_tabular")
            parsed[key] = text
            source_reads["text_files"] += 1
            return text
        except (OSError, UnicodeError, ValueError, csv.Error) as exc:
            rec.update(read_status="READ_OR_PARSE_ERROR", notes=rec["notes"] + "; " + str(exc))
            return None

    def refine_links():
        """Add literal row joins and recorded dependencies, without any metrics."""
        def small_csv(path):
            key = portable(str(path))
            if key in parsed:
                return parsed[key]
            with path.open(encoding="utf-8-sig", newline="") as f:
                return list(csv.DictReader(f))
        def edge(artifact, source, selector, columns, qualifier, scope=None):
            relations.append({"presentation_set": "RESULT_SOURCE_JOIN", "artifact_id": artifact.name,
                              "artifact_path": portable(str(artifact)), "artifact_status": "EXISTING_SOURCE_RELATION",
                              "source_path": portable(str(source)), "source_row_key": selector,
                              "source_columns": columns, "protocol_scope": scope or scope_for(artifact),
                              "manifest_path": "<V3_ROOT>/07_AGGREGATE/AGGREGATE_MANIFEST.json",
                              "derivation_or_qualifier": qualifier})
        for rec in records.values():
            rec["version_scope"] = scope_for(resolve(rec["source_path"]))
        for rel in relations:
            if rel.get("presentation_set") == "STAGE_RESULT_TABLES":
                rel["source_columns"] = "file pin only; not an arithmetic or row-level dependency"
                rel["protocol_scope"] = scope_for(resolve(rel["artifact_path"]))
        aggregate = root / "07_AGGREGATE"
        report_path = code / "configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json"
        report_obj = parsed.get(portable(str(report_path))) or json.loads(report_path.read_text())
        for version in ["v3", "v2"]:
            suffix = version.upper()
            for domain, stem in [("CORE", "CORE_541"), ("ADDENDUM", "ADDENDUM"), ("SEQUENCE", "SEQUENCE")]:
                edge(aggregate / (stem + "_TABLE_" + suffix + ".csv"), root / "FINAL_EVALUATION_RECORDS.json",
                     "JOIN table.run_id to row.run_id; row.evaluator_contract=evaluator_contract_" + version + "; row.domain=" + domain + ("; plus BY2 C00 rows reused from CORE" if domain == "SEQUENCE" else ""),
                     "original evaluation fields; child EVALUATION_RESULT.json paths and statuses in run index",
                     "Read navigation join, not recomputation. Aggregate manifest source_sha256 pins concrete per-run evaluation JSON; V3_RUN_RESULT_INDEX resolves every child path.")
                for ending in ["SUMMARY", "FAMILY_SUMMARY", "TYPE_SUMMARY", "DISTRIBUTION"]:
                    artifact = aggregate / (stem + "_" + ending + "_" + suffix + ".csv")
                    if portable(str(artifact)) in records:
                        edge(artifact, aggregate / (stem + "_TABLE_" + suffix + ".csv"),
                             "method_id; metric names original source column; " + ("case_id for distribution" if ending == "DISTRIBUTION" else "case_family/degradation_type_id where present"),
                             "metric column; status/failure classification; finite and registered support",
                             "Existing summary/distribution field definitions preserved; means, percentiles and failures are not recalculated.")
            for ending in ["TABLE", "SUMMARY"]:
                artifact = aggregate / ("SUBSET61_" + ending + "_" + suffix + ".csv")
                edge(artifact, aggregate / ("CORE_541_TABLE_" + suffix + ".csv"),
                     "case_id and method_id; exact registered subset membership retained in SUBSET61_TABLE", "original fields; subset identities",
                     "Subset view of the same physical V3 runs; never added to 6468 denominator.")
            for target, source in [("PAIRWISE_CASE_LEVEL", "CORE_541_TABLE"), ("PAIRWISE_SUMMARY", "PAIRWISE_CASE_LEVEL")]:
                edge(aggregate / (target + "_" + suffix + ".csv"), aggregate / (source + "_" + suffix + ".csv"),
                     "comparison, case_id, metric_name; summary additionally scope/family", "candidate_value, reference_value, original delta fields",
                     "Existing paired results only; negative means candidate minus reference is lower; bootstrap outputs retained, not rerun.")
            for stem, frozen in [("CORE_541", "frozen_core"), ("SUBSET61", "frozen_core"), ("ADDENDUM", "frozen_addendum"), ("SEQUENCE", "frozen_sequences")]:
                artifact = aggregate / (stem + "_V21_COMPARISON_" + suffix + ".csv")
                for source, role in [(aggregate / (stem + "_TABLE_" + suffix + ".csv"), "v3_*"), (resolve(report_obj[frozen][version]["path"]), "v21_*")]:
                    edge(artifact, source, "JOIN dataset_id, case_id, method_id; source profile aliases retained", role + "; original status and metric columns",
                         "Experiment protocol and evaluator are distinct; both sides use evaluator=" + version,
                         "Protocol V3 versus v2.1; evaluator=" + version)
                corrected = root / "07C_FAILURE_FAMILY_CONFIG" / artifact.name
                if portable(str(corrected)) in records:
                    edge(corrected, artifact, "dataset_id, case_id, method_id", "all columns; correction limited to v21_failure",
                         "07C manifest: numeric_tokens_changed=0; corrected_field_only=v21_failure. Original table retained; corrected report table is separately identified.")
            main = aggregate / ("MAIN_TABLE_" + suffix + ".csv")
            source_internal = aggregate / ("SEQUENCE_TABLE_" + suffix + ".csv")
            internal = small_csv(source_internal)
            source_external = resolve(report_obj["horizontal_tables"][version]["path"])
            external = small_csv(source_external)
            for number, row in enumerate(small_csv(main), 1):
                own = row.get("config") == "PROTOCOL_V3"
                source = source_internal if own else source_external
                candidates = internal if own else external
                where = {k: row[k] for k in ["sequence_id", "method_id"]}
                if not own:
                    where.update({k: row[k] for k in ["config", "start_convention"]})
                matches = [i for i, x in enumerate(candidates, 1) if all(x.get(k) == v for k, v in where.items())]
                edge(main, source,
                     json.dumps({"output_data_row_1based": number, "where": where, "source_data_rows_1based": matches}, ensure_ascii=False),
                     "h_rmse_m <- horizontal_rmse_m for internal rows; other original metric/status/support columns",
                     "Internal V3 row" if own else "Preserved external row; see HORIZONTAL_REPLACEMENT_AUDIT.csv csv_tokens_equal; outside A")
            edge(aggregate / ("ABLATION_TABLE_" + suffix + ".csv"), main,
                 "config=PROTOCOL_V3 and method_id in F01,F02,F03,A04,F04; all three sequences", "all existing columns",
                 "Five-configuration display view; does not replace eleven-configuration full ablation.")
            edge(root / "07C_FAILURE_FAMILY_CONFIG" / ("FULL_ABLATION_TABLE_" + suffix + ".csv"), source_internal,
                 "JOIN run_id; all 33 rows and eleven configurations per sequence", "all original evaluation columns",
                 "Full three-sequence view; BY2 C00 is already in CORE.")
            for kind, key in [("THREE_SEQUENCES", "sensitivity_pilot"), ("SUBSET61", "sensitivity_subset")]:
                edge(aggregate / ("T5BCR_REFERENCE_" + kind + "_" + suffix + ".csv"), resolve(report_obj[key][version]["path"]),
                     "original run_id, case_id, method_id, variant/effective_configuration_id; selected candidate rows retained", "all copied candidate fields",
                     "T5bc-R sensitivity with its original physical run identities; outside A.", "T5bc-R sensitivity; evaluator=" + version)
        edge(root / "07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv", root / "FINAL_RUN_RECORDS.json",
             "Protocol V3 side: run_id grouped by case_family, method_id, failure_classification; evaluator version is a reporting axis", "native terminal status; original failure categories",
             "Counts are read, not recomputed here. v2.1 side uses the pinned frozen comparison sources in 07C MANIFEST.")
        edge(root / "07D_CLASSIFICATION_PROVENANCE/F01_IDENTICAL_NAV_CLASSIFICATION.csv", root / "FINAL_RUN_RECORDS.json",
             "dataset_id, case_id, method_id=F01; 20 retained entries", "native NAV identity and original classification fields",
             "07D provenance table is preserved alongside the later 07E hard stop; this collection does not adjudicate the conflict.")
        render_file = root / "08_FIGURES/RENDER_MANIFEST.json"
        manifest = parsed.get(portable(str(render_file))) or json.loads(render_file.read_text(), parse_float=str)
        by_figure = {x["figure_id"]: x for x in manifest["figures"]}
        selectors = {
            "MFIG00": "case_id=C00_clean_normal; exact run-specific matched/error-series sources separately listed",
            "MFIG01": "Canonical-541 finite case distributions; case_id/method_id; exact display selection beyond caption not encoded",
            "MFIG02": "comparison=A04_vs_F03; D01-D60; case_family and metric_name",
            "MFIG03": "comparison=full_vs_no_SA (F04 minus A04); family and metric_name; finite pairs",
            "MFIG04": "ladder F01,F02,F03,A04,F04; leave-one-module-out comparisons; exact comparison names not enumerated by manifest",
            "MFIG05": "D27,D60,D04,D12,D58; deterministic lowest seed; exact run-specific series sources separately listed",
            "MFIG06": "method_id=F04; grouped by frozen case_family; retained native counters include failed runs",
            "SFIG01": "D01-D60 x five display configurations; finite-case means; no new computation",
        }
        for rel in relations:
            if rel.get("presentation_set") != "STAGE_V3_FIGURES":
                continue
            fid = rel["artifact_id"]
            if fid in selectors:
                rel["source_row_key"] = selectors[fid]
            detail = by_figure[fid].get("details", {})
            if detail.get("source_rows"):
                rel["source_row_key"] = json.dumps([{k: r[k] for k in ["sequence_id", "method_id", "config", "start_convention", "segment_id", "evaluator_contract"] if k in r} for r in detail["source_rows"]], ensure_ascii=False)
        for rec in records.values():
            for field, value in rec.items():
                rec[field] = portable(value)
        for rel in relations:
            for field, value in rel.items():
                rel[field] = portable(value)

    if args.refine_links_only:
        with (output / "TABLE_RESULT_FILES.csv").open(newline="") as f:
            records.update((r["source_path"], r) for r in csv.DictReader(f))
        with (output / "V3_TABLE_FIGURE_SOURCES.csv").open(newline="") as f:
            relations.extend(r for r in csv.DictReader(f) if r["presentation_set"] != "RESULT_SOURCE_JOIN")
        refine_links()
        write_csv(output / "TABLE_RESULT_FILES.csv", sorted(records.values(), key=lambda r: r["source_path"]), FIELDS)
        write_csv(output / "V3_TABLE_FIGURE_SOURCES.csv", relations, REL_FIELDS)
        summary_path = output / "TABLE_COLLECTION_SUMMARY.json"
        summary = json.loads(summary_path.read_text())
        summary["source_relations"] = len(relations)
        summary["source_link_refinement"] = "Small existing maps/tables only; no scientific calculations or large-source reread"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"source_relations": len(relations), "mode": "refine_existing_links_only"}))
        return

    # Explicit known result roots; no full disk traversal. Historical continuations
    # are read only below their recorded 07E result directory and remain B/history.
    for name in ["07_AGGREGATE", "07C_FAILURE_FAMILY_CONFIG", "07D_CLASSIFICATION_PROVENANCE", "07E_UNIFIED_FAILURE", "10_UNCERTAINTY"]:
        directory = root / name
        if directory.exists():
            for p in sorted(directory.rglob("*")):
                if p.is_file() and p.suffix.lower() in [".csv", ".json", ".md"]:
                    read(p, copy=name not in ["07E_UNIFIED_FAILURE", "10_UNCERTAINTY"])
    unc = code / "docs/paper_rebuild/v3/uncertainty"
    for p in sorted(unc.iterdir()):
        if p.is_file() and p.suffix.lower() in [".csv", ".json", ".md", ".txt"]:
            read(p)

    # Record table pins and exact source relationships from final manifests.
    for p in [root / "07_AGGREGATE/AGGREGATE_MANIFEST.json", root / "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json", root / "07D_CLASSIFICATION_PROVENANCE/MANIFEST.json"]:
        obj = read(p) or {}
        for name, sha in obj.get("files_sha256", {}).items():
            target = p.parent / name
            read(target, sha=sha)
            relations.append({"presentation_set": "STAGE_RESULT_TABLES", "artifact_id": name,
                              "artifact_path": portable(str(target)), "artifact_status": "EXISTING_FINAL_MANIFEST",
                              "source_path": portable(str(p)), "source_row_key": "files_sha256." + name,
                              "source_columns": "all original columns; run_id joins to FINAL_EVALUATION_RECORDS",
                              "protocol_scope": scope_for(target), "source_recorded_sha256": sha,
                              "manifest_path": portable(str(p)), "derivation_or_qualifier": "Existing aggregate/repair manifest; no aggregation performed this collection"})
        for name, sha in obj.get("source_sha256", {}).items():
            # Per-run sources are fully collected by the independent run-index
            # collector. This pass reads result tables, not all input payloads.
            if name.endswith(".csv") and "/04_EVALUATION/" not in name:
                read(resolve(name), sha=sha)

    report_index = code / "configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json"
    report = read(report_index) or {}
    def report_entries(obj, prefix=""):
        if not isinstance(obj, dict):
            return
        if "path" in obj:
            p = resolve(obj["path"])
            read(p, sha=obj.get("sha256", ""), note="V3_REPORT_SOURCE_INDEX entry " + prefix)
            relations.append({"presentation_set": "REPORT_REFERENCES_B", "artifact_id": prefix,
                              "artifact_path": portable(str(report_index)), "artifact_status": "REGISTERED_REFERENCE",
                              "source_path": portable(str(p)), "source_row_key": "all original records",
                              "source_columns": "all original columns", "protocol_scope": scope_for(p),
                              "source_recorded_sha256": obj.get("sha256", ""), "manifest_path": portable(str(report_index)),
                              "derivation_or_qualifier": "Retain original protocol; not an additional Protocol V3 native run"})
            return
        for k, v in obj.items():
            report_entries(v, prefix + "." + k if prefix else k)
    report_entries(report)

    render_path = root / "08_FIGURES/RENDER_MANIFEST.json"
    render = read(render_path) or {}
    for fig in render.get("figures", []):
        fid = fig["figure_id"]
        for ext, sha in fig.get("output_sha256", {}).items():
            read(root / "08_FIGURES" / fid / (fid + "." + ext), "STAGE_FIGURE_EXPORT", sha=sha,
                 note="Existence only; no new visual QA. Three formats are one figure group.")
        for kind in ["table_sources", "runtime_sources"]:
            for name, sha in fig.get(kind, {}).items():
                src = root / "07_AGGREGATE" / name if kind == "table_sources" else resolve(name)
                read(src, sha=sha, note="Stage figure " + fid + " " + kind)
                relations.append({"presentation_set": "STAGE_V3_FIGURES", "artifact_id": fid,
                                  "artifact_path": "<V3_ROOT>/08_FIGURES/" + fid + "/" + fid + ".{png,pdf,svg}",
                                  "artifact_status": fig.get("status", "unknown"), "source_path": portable(str(src)),
                                  "source_row_key": "see caption/details; manifest gives file-level source, not an exhaustive row selector",
                                  "source_columns": "original manifest source; no inferred column selection",
                                  "protocol_scope": fig.get("protocol", "unknown"), "evaluator_version": fig.get("evaluator_version", "unknown"),
                                  "source_recorded_sha256": sha, "manifest_path": portable(str(render_path)),
                                  "derivation_or_qualifier": fig.get("caption", "") + " | details=" + portable(json.dumps(fig.get("details", {}), ensure_ascii=False))})

    paper = code / "paper_package/gpss_v0"
    for name in ["TABLE_MAP.csv", "FIGURE_MAP.csv", "NUMBER_LEDGER.csv", "NUMBER_LEDGER_CHECK.csv", "READ_FILES.json", "MS01_REPORT.md", "MANUSCRIPT_GPSS_v0.md", "SUPPLEMENT_GPSS_v0.md", "NOTES_ZH.md"]:
        read(paper / name)
    for p in sorted((paper / "tables").glob("*.csv")):
        read(p)
    for p in sorted((paper / "figures").glob("*")):
        if p.is_file():
            read(p, note="Current paper package output; not equated to stage figure by name")
    for row in parsed.get(portable(str(paper / "TABLE_MAP.csv")), []):
        artifact = paper / row["output_csv"]
        for name in row["source_files"].split(";"):
            src = resolve(name, original)
            read(src, note="Paper table " + row["manuscript_table"])
            relations.append({"presentation_set": "PAPER_GPSS_V0_TABLES", "artifact_id": row["manuscript_table"],
                              "artifact_path": portable(str(artifact)), "artifact_status": "EXISTING_DISPLAY_TABLE",
                              "source_path": portable(str(src)), "source_row_key": row["derivation"],
                              "source_columns": "display headers: " + records.get(portable(str(artifact)), {}).get("columns", "unknown"),
                              "protocol_scope": scope_for(src), "manifest_path": "<CODE_ROOT>/paper_package/gpss_v0/TABLE_MAP.csv",
                              "derivation_or_qualifier": row["derivation"]})
    for row in parsed.get(portable(str(paper / "FIGURE_MAP.csv")), []):
        sources = row["data_sources"].split(";")
        shas = row["data_sha256"].split(";")
        for i, name in enumerate(sources):
            src = resolve(name, paper)
            sha = shas[i] if i < len(shas) else ""
            read(src, sha=sha, note="Paper figure " + row["manuscript_figure"])
            relations.append({"presentation_set": "PAPER_GPSS_V0_FIGURES", "artifact_id": row["manuscript_figure"] + "/" + row["panel"],
                              "artifact_path": "<CODE_ROOT>/paper_package/gpss_v0/figures/" + row["manuscript_figure"] + ".{png,pdf,svg}",
                              "artifact_status": row["status"], "source_path": portable(str(src)),
                              "source_row_key": "panel=" + row["panel"] + "; recorded source file; no exact row selector supplied by map",
                              "source_columns": "unknown unless defined by cited table/series", "protocol_scope": scope_for(src),
                              "source_recorded_sha256": sha, "manifest_path": "<CODE_ROOT>/paper_package/gpss_v0/FIGURE_MAP.csv",
                              "derivation_or_qualifier": portable(row["source_or_script"]) + " | " + row["qa_notes"]})
        for name in row["source_or_script"].split(";"):
            read(resolve(name, paper), note="Paper figure source/script; code not executed")

    # HX-05 is a displayed synthesis, not the primary raw numeric source. Its
    # existing cell citations supply the original full-precision external tables,
    # exact CSV lines/JSON fields, and method-specific denominator meanings.
    hx05 = original / "docs/paper_rebuild/hext/HX05"
    for name in ["SOURCE_CITATIONS.json", "D43_SOURCE_CITATIONS.json", "MANUSCRIPT_DATA.json",
                 "FIGURE_MANIFEST.json", "ALL_SOURCE_SHA256.json", "SOURCE_SHA256.json", "SOURCE_PINS.json"]:
        obj = read(hx05 / name, note="Original HX-05 source provenance used by GPSS v0")
        if name in ["ALL_SOURCE_SHA256.json", "SOURCE_SHA256.json", "SOURCE_PINS.json"] and isinstance(obj, dict):
            for name_or_path, sha in obj.items():
                if isinstance(sha, str) and re.fullmatch("[0-9a-f]{64}", sha):
                    target = resolve(name_or_path, hx05)
                    if target.suffix.lower() in [".csv", ".json", ".md", ".yaml", ".png", ".pdf", ".svg"]:
                        read(target, sha=sha, note="HX05 recorded source pin; original external role retained")
        if name not in ["SOURCE_CITATIONS.json", "D43_SOURCE_CITATIONS.json"] or not isinstance(obj, dict):
            continue
        for cell_id, cell in obj.items():
            if not isinstance(cell, dict):
                continue
            for source in cell.get("sources", []):
                target = resolve(source["file"])
                data = read(target, sha=source.get("sha256", ""), note="HX05 exact cell source " + cell_id)
                relations.append({"presentation_set": "HX05_SOURCE_CELLS_USED_BY_GPSS_V0", "artifact_id": cell_id,
                                  "artifact_path": portable(str(hx05 / name)), "artifact_status": "EXISTING_FULL_PRECISION_CELL",
                                  "source_path": portable(str(target)),
                                  "source_row_key": json.dumps({k: source[k] for k in ["lines", "row_keys", "where", "json_path"] if k in source}, ensure_ascii=False),
                                  "source_columns": json.dumps(source.get("fields", []), ensure_ascii=False),
                                  "source_value": portable(json.dumps(cell.get("metrics", cell.get("exact", {})), ensure_ascii=False)),
                                  "display_value": cell.get("display", ""), "protocol_scope": scope_for(target),
                                  "source_recorded_sha256": source.get("sha256", ""), "manifest_path": portable(str(hx05 / name)),
                                  "derivation_or_qualifier": "; ".join(v for v in (source.get("operation", ""), cell.get("notes", "")) if v)})

    # Read every existing provenance pin list. Follow result/document pointers;
    # raw, provider and long series entries get availability only, no new metrics.
    pin_sources = [paper / "READ_FILES.json", unc / "UA01_INPUT_SHA256.json", unc / "UNC_INPUT_PINS.json", root / "10_UNCERTAINTY/UA01_ERROR_SERIES_PATHS.json"]
    for p in pin_sources:
        obj = read(p)
        entries = obj if isinstance(obj, list) else (obj or {}).get("inputs", [])
        for ent in entries:
            if not isinstance(ent, dict) or "path" not in ent:
                continue
            target = resolve(ent["path"], original)
            sha = ent.get("sha256", "")
            # Local config and raw/source-code contents are not copied or opened.
            if target.suffix in [".csv", ".json", ".md", ".yaml", ".gz", ".png", ".pdf", ".svg", ".py", ".cpp", ".hpp", ".imu", ".gnss"]:
                if target.name == "error_series.csv":
                    # Source series stays in place; separate large-payload reader
                    # can use the exact recorded location without recomputation.
                    key = portable(str(target))
                    if key not in records:
                        rec = dict.fromkeys(FIELDS, "")
                        rec.update(category="B_REFERENCED_ERROR_SERIES", source_path=key,
                                   read_status="EXISTS_NOT_PARSED_PAYLOAD" if target.is_file() else "INDEXED_NOT_FOUND",
                                   retention_status="PRESENT_IN_PLACE" if target.is_file() else "EXPECTED_SOURCE_NOT_FOUND",
                                   row_count="not_read", version_scope=scope_for(target), source_commit="unknown",
                                   notes="Specific existing series location from " + portable(str(p)))
                        records[key] = rec
                    pins[key].add(sha)
                else:
                    read(target, sha=sha, note="Recorded by " + portable(str(p)))
        if p.name == "UNC_INPUT_PINS.json" and isinstance(obj, dict):
            for name, ent in obj.items():
                read(unc / name, sha=ent.get("expected", ""), note="UA-02 recorded pin; actual field is historical, current verified_sha256 separate")

    # Each manuscript-number relation retains full source token(s), row selector,
    # display string, and exact existing column name. Only direct display rounding
    # is compared; derived claims are not recalculated.
    number_counts = collections.Counter()
    for row in parsed.get(portable(str(paper / "NUMBER_LEDGER.csv")), []):
        src = resolve(row["source_path"], original)
        obj = read(src, note="Manuscript number ledger source")
        locator = json.loads(row["source_locator"])
        value = ""
        state = "SOURCE_READ_NO_NEW_DERIVATION"
        keys = row["source_locator"]
        if row["check_mode"] == "CSV" and isinstance(obj, list):
            matches = [(i, r) for i, r in enumerate(obj, 1) if all(r.get(k) == str(v) for k, v in locator.get("where", {}).items())]
            vals = [r.get(locator.get("column", ""), "COLUMN_NOT_FOUND") for i, r in matches]
            value = json.dumps(vals, ensure_ascii=False)
            keys = json.dumps([{"data_row_1based": i, **locator} for i, r in matches], ensure_ascii=False)
            if len(vals) == 1:
                try:
                    digits = locator.get("display_digits")
                    token = vals[0]
                    if locator.get("regex"):
                        found = re.search(locator["regex"], token)
                        token = found.group(1) if found else "REGEX_NOT_FOUND"
                    rounded = format(Decimal(token), "." + str(digits) + "f") if digits is not None else token
                    state = "DISPLAY_ROUNDING_MATCH" if Decimal(rounded) == Decimal(row["value"]) else "DISPLAY_SOURCE_DIFFERENCE_RETAINED"
                except (InvalidOperation, ValueError):
                    state = "NONNUMERIC_SOURCE_VALUE_RETAINED"
            else:
                state = "NONUNIQUE_OR_MISSING_SOURCE_ROW"
        elif isinstance(obj, str) and "line_start" in locator:
            lines = obj.splitlines()
            value = "\n".join(lines[locator["line_start"] - 1:locator.get("line_end", locator["line_start"])])
        number_counts[state] += 1
        relations.append({"presentation_set": "PAPER_GPSS_V0_NUMBER_LEDGER", "artifact_id": row["claim_id"],
                          "artifact_path": "<CODE_ROOT>/paper_package/gpss_v0/NUMBER_LEDGER.csv",
                          "artifact_status": row["check_mode"], "source_path": portable(str(src)), "source_row_key": keys,
                          "source_columns": locator.get("column", "literal/document locator"), "source_value": portable(value),
                          "display_value": row["value"], "comparison_status": state, "protocol_scope": scope_for(src),
                          "manifest_path": "<CODE_ROOT>/paper_package/gpss_v0/NUMBER_LEDGER.csv",
                          "derivation_or_qualifier": row["derivation"] + "; " + row["unit"] + "; " + row["section"]})

    for key, rec in records.items():
        rec["recorded_sha256"] = ";".join(sorted(s for s in pins.get(key, []) if s))
        if rec["verified_sha256"] and pins.get(key):
            bad = sorted(s for s in pins[key] if s and s != rec["verified_sha256"])
            if bad:
                rec["notes"] += "; RECORDED_HASH_DIFFERS_CURRENT_BYTES: " + ";".join(bad) + "; originals and recorded pins preserved"
        for field, value in rec.items():
            rec[field] = portable(value)
    for rel in relations:
        for field, value in rel.items():
            rel[field] = portable(value)
    refine_links()
    write_csv(output / "TABLE_RESULT_FILES.csv", sorted(records.values(), key=lambda r: r["source_path"]), FIELDS)
    write_csv(output / "V3_TABLE_FIGURE_SOURCES.csv", relations, REL_FIELDS)
    summary = {
        "operation": "read_existing_result_records_and_string_preserving_views_only",
        "data_mode": "existing_mixed_real_and_registered_semisynthetic_records",
        "synthetic_data_used": False, "semisynthetic_data_used": True,
        "solver_calls": 0, "provider_calls": 0, "evaluator_calls": 0,
        "bootstrap_calls": 0, "raw_trace_payload_reads": 0,
        "read_counts": dict(source_reads), "registry_files": len(records),
        "registry_read_status": dict(collections.Counter(r["read_status"] for r in records.values())),
        "registry_categories": dict(collections.Counter(r["category"] for r in records.values())),
        "table_rows": {k: r["row_count"] for k, r in records.items() if k.endswith(".csv") and r["read_status"] == "READ_FULL_PARSED"},
        "stage_figure_groups": len(render.get("figures", [])),
        "paper_table_map_rows": len(parsed.get(portable(str(paper / "TABLE_MAP.csv")), [])),
        "paper_figure_map_rows": len(parsed.get(portable(str(paper / "FIGURE_MAP.csv")), [])),
        "paper_distinct_figure_ids": len({r["manuscript_figure"] for r in parsed.get(portable(str(paper / "FIGURE_MAP.csv")), [])}),
        "source_relations": len(relations), "number_ledger_comparisons": dict(number_counts),
        "shared_views": copied, "large_table_projections": projections,
        "missing_sources": [k for k, r in records.items() if r["read_status"] in ["INDEXED_NOT_FOUND", "READ_OR_PARSE_ERROR"]],
        "recorded_pin_conflicts": [k for k, r in records.items() if "RECORDED_HASH_DIFFERS_CURRENT_BYTES" in r["notes"]],
        "units": "retain source column units; m, deg, s, epochs, finite/registered cases are distinct",
        "row_key_definition": "data_row_1based excludes CSV header; original identity fields included when present",
        "field_mapping": "Original headers unchanged. _source_path and _source_row_key are added. Only configured machine path prefixes become aliases; numeric/status strings unchanged.",
        "large_source_rule": "Full source files parsed. B browse projections preserve every row, identities, states, support, RMSE/P95 values. Excluded columns are explicit; complete originals remain accessible. All A run statistics collected independently. No per-epoch error-series payload is copied to Git.",
    }
    (output / "TABLE_COLLECTION_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["read_counts", "registry_files", "registry_read_status", "source_relations", "number_ledger_comparisons", "missing_sources", "recorded_pin_conflicts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
