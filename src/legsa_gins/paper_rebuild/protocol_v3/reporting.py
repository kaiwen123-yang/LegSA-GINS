"""Protocol-v3 reporting from sealed terminals; no solver, evaluator or trace I/O.

The horizontal registry retains every external CSV token. Failures remain rows,
finite statistics have explicit denominators, and sensitivity rows are copied
from the completed T5bc-R package without being promoted to v3 experiments.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..hext.aggregate import AVAILABLE, METRIC_FIELDS, TABLE_FIELDS, normalize_row
from ..hext.t5a_reporting import ERROR_COLUMNS, derive_segments, unavailable_segments
from ..publication.protocol_v2_data import CONFIG, MAIN

UNAVAILABLE = "UNAVAILABLE"
SEQUENCES = ("BY2", "BY2H", "BY2O")
VERSIONS = ("v3", "v2")
DOMAINS = {"CORE": (5951, 541), "ADDENDUM": (495, 45), "SEQUENCE": (33, 3)}
METRICS = ("horizontal_rmse_m", *METRIC_FIELDS[1:])
SUBSET61 = ("C00_clean_normal", *(f"D{i:02}_seed_00" for i in range(1, 61)))
SENSITIVITY_VARIANTS = {"R5SIGMA", "R5W", "B3"}
PAIR_DEFINITIONS = (("A04_vs_F03", "A04", "F03"),
    ("full_vs_strong", "F04", "F03"), ("full_vs_no_RD", "F04", "A03"),
    ("full_vs_no_SA", "F04", "A04"), ("full_vs_no_RP", "F04", "A05"),
    ("full_vs_no_HV", "F04", "A06"), ("full_vs_no_Go2", "F04", "A07"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe(path):
    path = Path(path).absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Reporting paths cannot traverse symlinks or parent components")
    return path


def write_json(path, value):
    def scalar(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)
    with safe(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False, default=scalar)
        stream.write("\n")


def write_csv(path, rows, fields=None):
    fields = list(fields or dict.fromkeys(key for row in rows for key in row)) or ["status"]
    with safe(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def delta(current, frozen):
    try:
        a, b = Decimal(str(current)), Decimal(str(frozen))
        return str(a - b) if a.is_finite() and b.is_finite() else UNAVAILABLE
    except (InvalidOperation, TypeError, ValueError):
        return UNAVAILABLE


def state(row):
    status = str(row.get("evaluation_status", row.get("status", UNAVAILABLE)))
    failure = str(row.get("failure_classification", row.get("terminal_status", status)))
    if status in AVAILABLE:
        return "COMPLETED"
    if "NOT_APPLICABLE" in status or "NOT_APPLICABLE" in failure:
        return "NOT_APPLICABLE"
    if "ALGORITHM_FAILURE" in status or "ALGORITHM_FAILURE" in failure:
        return "ALGORITHM_FAILURE"
    return "UNAVAILABLE"


class Sources:
    """Only pinned result/metadata files; no raw input is admitted here."""
    def __init__(self, roots):
        self.roots = {key: safe(value) for key, value in roots.items()}
        self.used = {}

    def resolve(self, name):
        for key, root in self.roots.items():
            name = str(name).replace("<" + key.upper() + ">", str(root))
        if "<" in str(name):
            raise ValueError("Unresolved reporting input alias")
        return safe(name)

    def read(self, ref):
        path = self.resolve(ref["path"])
        raw = self.roots.get("raw_root")
        if (raw is not None and (path == raw or raw in path.parents)) or path.name.lower().startswith("trace_"):
            raise PermissionError("Reporting cannot open raw data or reference trace")
        if path.suffix.lower() in {".nav", ".imu", ".gnss", ".bag", ".fpl"}:
            raise PermissionError("Reporting cannot read native/provider inputs")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != ref["sha256"]:
            raise RuntimeError("HARD_STOP_V3_REPORT_INPUT_HASH: " + path.name)
        self.used[str(path)] = digest
        return payload

    def rows(self, ref):
        payload = self.read(ref)
        if str(ref["path"]).endswith(".gz"):
            payload = gzip.decompress(payload)
        return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))

    def frame(self, ref):
        payload = self.read(ref)
        if str(ref["path"]).endswith(".gz"):
            payload = gzip.decompress(payload)
        return pd.read_csv(io.BytesIO(payload))


def validate_domain(rows, domain):
    expected_rows, expected_cases = DOMAINS[domain]
    keys = [(r["dataset_id"], r["case_id"], r["method_id"]) for r in rows]
    if len(keys) != expected_rows or len(set(keys)) != expected_rows:
        raise ValueError("Missing or duplicate v3 " + domain + " result slots")
    if len({r["case_id"] for r in rows}) != expected_cases or {r["method_id"] for r in rows} != set(CONFIG):
        raise ValueError("Registered v3 method/case coverage changed")
    groups = defaultdict(list)
    for row in rows:
        groups[row["dataset_id"], row["case_id"]].append(row["method_id"])
    if any(Counter(methods) != Counter(CONFIG.keys()) for methods in groups.values()):
        raise ValueError("Every registered case must retain each of the eleven configurations exactly once")
    if domain == "SEQUENCE" and ({r["dataset_id"] for r in rows} != set(SEQUENCES)
        or set(Counter(r["dataset_id"] for r in rows).values()) != {11}):
        raise ValueError("Sequence coverage must be three by eleven")
    for row in rows:
        if row.get("synthetic_data_used") not in (False, "False", "false"):
            raise ValueError("Synthetic row cannot enter the v3 result tables")
        controlled = domain == "ADDENDUM" or (domain == "CORE" and row["case_id"] != "C00_clean_normal")
        semi = row.get("semisynthetic_data_used")
        if str(semi).lower() != str(controlled).lower():
            raise ValueError("Outer controlled-input data role differs from registered domain")
        if state(row) == "COMPLETED" and any(number(row.get(metric)) is None for metric in METRICS):
            raise ValueError("Completed terminal has missing/nonfinite principal metrics")


def main_table(frozen_rows, sequence_rows, version):
    """Replace exactly fifteen LegSA rows, preserving all 37 external row tokens."""
    if len(frozen_rows) != 52:
        raise ValueError("Horizontal registry must retain its 52-row format")
    index = {(r["dataset_id"], r["method_id"]): r for r in sequence_rows}
    result, replaced, audit = [], set(), []
    for line, original in enumerate(frozen_rows, 2):
        if original["method_id"] not in MAIN:
            result.append(deepcopy(original))
            audit.append(dict(source_line=line, disposition="EXTERNAL_TOKENS_UNCHANGED", method_id=original["method_id"],
                sequence_id=original["sequence_id"], csv_tokens_equal=True))
            continue
        key = original["sequence_id"], original["method_id"]
        if key in replaced or key not in index:
            raise ValueError("Missing/duplicate LegSA horizontal row")
        replaced.add(key)
        source = index[key]
        row = normalize_row(source, sequence_id=key[0], method_id=key[1], config="PROTOCOL_V3",
            start="FROZEN_V21_RUNTIME_CONFIG", geometric_status="NOT_APPLICABLE",
            body_bias=source.get("body_frame_bias", {}), notes="Protocol v3: raw HPPOSECEF scalar 5 Hz heading; other inputs and parameters frozen.")
        row.update(main_row=original["main_row"], manuscript_row=original["manuscript_row"],
            evaluator_contract="evaluator_contract_" + version)
        result.append(row)
        audit.append(dict(source_line=line, disposition="LEGSA_REPLACED_WITH_V3", method_id=key[1],
            sequence_id=key[0], csv_tokens_equal="NOT_APPLICABLE", run_id=source.get("run_id")))
    if replaced != {(sequence, method) for sequence in SEQUENCES for method in MAIN}:
        raise ValueError("All fifteen LegSA replacements are required")
    return result, audit


def comparison_rows(current, frozen):
    key = lambda row: (row.get("dataset_id", row.get("sequence_id")), row["case_id"], row["method_id"])
    old = {key(row): row for row in frozen}
    new = {key(row): row for row in current}
    if len(old) != len(frozen) or len(new) != len(current) or set(old) != set(new):
        raise ValueError("v3/v2.1 comparison requires identical unique case/method keys")
    result = []
    for identity, row in new.items():
        ref = old[identity]
        available = state(row) == state(ref) == "COMPLETED"
        entry = {name: row.get(name, UNAVAILABLE) for name in ("dataset_id", "case_id", "method_id", "case_family", "degradation_id", "seed_id")}
        entry.update(v3_status=row["evaluation_status"], v21_status=ref["evaluation_status"],
            v3_failure=row.get("failure_classification", "NONE"), v21_failure=ref.get("failure_classification", "NONE"),
            paired_finite=available, completed_to_failure=state(ref) == "COMPLETED" and state(row) == "ALGORITHM_FAILURE",
            failure_to_completed=state(ref) == "ALGORITHM_FAILURE" and state(row) == "COMPLETED")
        for metric in METRICS:
            entry.update({"v3_" + metric: row.get(metric, UNAVAILABLE), "v21_" + metric: ref.get(metric, UNAVAILABLE),
                "delta_" + metric: delta(row.get(metric), ref.get(metric)) if available else UNAVAILABLE})
        result.append(entry)
    return result


def absolute_summary(rows, *, grouping=("method_id",)):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(str(row.get(field) or UNAVAILABLE) for field in grouping)].append(row)
    result = []
    for key, group in sorted(groups.items()):
        counts = Counter(state(row) for row in group)
        for metric in METRICS:
            values = np.asarray([number(row.get(metric)) for row in group if state(row) == "COMPLETED"], float)
            if len(values) and not np.isfinite(values).all():
                raise ValueError("Finite statistics cannot silently remove completed nonfinite metrics")
            tail_n = math.ceil(.05 * len(values))
            entry = dict(zip(grouping, key))
            entry.update(metric=metric, registered_count=len(group), finite_count=len(values),
                algorithm_failure_count=counts["ALGORITHM_FAILURE"], unavailable_count=counts["UNAVAILABLE"],
                not_applicable_count=counts["NOT_APPLICABLE"], failure_rate=counts["ALGORITHM_FAILURE"] / len(group),
                mean=float(np.mean(values)) if len(values) else UNAVAILABLE,
                median=float(np.median(values)) if len(values) else UNAVAILABLE,
                p95=float(np.percentile(values, 95)) if len(values) else UNAVAILABLE,
                maximum=float(np.max(values)) if len(values) else UNAVAILABLE,
                worst_5pct_mean=float(np.mean(np.sort(values)[-tail_n:])) if tail_n else UNAVAILABLE,
                worst_5pct_count=tail_n)
            result.append(entry)
    return result


def failure_comparison(current, frozen, domain, version):
    rows = []
    for method in CONFIG:
        new = [r for r in current if r["method_id"] == method]
        old = [r for r in frozen if r["method_id"] == method]
        if len(new) != len(old):
            raise ValueError("Failure comparison denominator differs")
        for edition, group in (("v3", new), ("v2.1", old)):
            for classification, count in sorted(Counter((state(r), str(r.get("failure_classification", "NONE"))) for r in group).items()):
                rows.append(dict(domain=domain, evaluator_version=version, protocol=edition, method_id=method,
                    outcome_class=classification[0], failure_classification=classification[1], count=count, registered_count=len(group)))
    return rows


def paired_rows(rows):
    index = {(row["case_id"], row["method_id"]): row for row in rows}
    result = []
    for comparison, candidate, reference in PAIR_DEFINITIONS:
        for case in sorted({r["case_id"] for r in rows}):
            a, b = index[case, candidate], index[case, reference]
            if state(a) != "COMPLETED" or state(b) != "COMPLETED":
                continue
            for metric in METRICS:
                result.append(dict(comparison=comparison, case_id=case,
                    degradation_id=a["degradation_id"], case_family=a["case_family"], metric_name=metric,
                    candidate_value=a[metric], reference_value=b[metric],
                    delta_candidate_minus_reference=delta(a[metric], b[metric])))
    return result


def paired_summary(pairs):
    """Keep the v2.1 display inference defaults unchanged (10000, seed 20260904)."""
    from ..clean6_canonical_v2.aggregate import finite_stats
    groups = defaultdict(list)
    for row in pairs:
        groups[row["comparison"], row["metric_name"], "overall", "ALL"].append(row)
        groups[row["comparison"], row["metric_name"], "family", row["case_family"]].append(row)
    result = []
    for (comparison, metric, scope, family), group in sorted(groups.items()):
        result.append(dict(comparison=comparison, metric_name=metric, scope=scope, family=family,
            **finite_stats([float(row["delta_candidate_minus_reference"]) for row in group])))
    return result


def distribution_rows(rows):
    result = []
    for method in CONFIG:
        group = [row for row in rows if row["method_id"] == method]
        for metric in METRICS:
            finite = [row for row in group if state(row) == "COMPLETED"]
            if any(number(row.get(metric)) is None for row in finite):
                raise ValueError("ECDF cannot delete completed nonfinite metric rows")
            ordered = sorted(finite, key=lambda row: (float(row[metric]), row["case_id"]))
            for rank, row in enumerate(ordered, 1):
                result.append(dict(method_id=method, metric=metric, case_id=row["case_id"], value=row[metric],
                    ordered_rank=rank, finite_denominator=len(finite), registered_denominator=len(group),
                    ecdf=rank / len(finite)))
    return result


def copy_sensitivity(rows, *, subset):
    result = [deepcopy(row) for row in rows if row.get("variant") in SENSITIVITY_VARIANTS]
    expected = 183 if subset else 15
    if len(result) != expected:
        raise ValueError("T5bc-R sensitivity row coverage differs")
    if subset:
        for variant in SENSITIVITY_VARIANTS:
            if {r["case_id"] for r in result if r["variant"] == variant} != set(SUBSET61):
                raise ValueError("Sensitivity subset must retain all 61 registered cases")
    return result


def by2o_segments(sequence_rows, error_reader, frozen_rows, version, window):
    """Reuse H-EXT-04L arithmetic and closed intervals, including the outside block."""
    result = [deepcopy(r) for r in frozen_rows if r["method_id"] not in MAIN
        and r["evaluator_contract"] == "evaluator_contract_" + version]
    for row in sequence_rows:
        if row["dataset_id"] != "BY2O":
            continue
        profile = row["method_id"]
        if state(row) == "COMPLETED":
            errors, source = error_reader(row)
            if any(field not in errors for field in ERROR_COLUMNS) or not np.isfinite(errors[list(ERROR_COLUMNS)].to_numpy(float)).all():
                raise ValueError("Sealed full-rate errors have missing/nonfinite values")
            values = derive_segments(errors, profile=profile, variant="PROTOCOL_V3", version=version,
                window=window, source=source)
        else:
            values = unavailable_segments(profile, "PROTOCOL_V3", version, row.get("failure_classification", UNAVAILABLE))
        for item in values:
            item["role"] = "PROTOCOL_V3_FULL_REPORT"
        result.extend(values)
    return result


def manuscript_text(main_rows, failures, *, validity_rule):
    rows = [r for r in main_rows if r["method_id"] in MAIN]
    text = ["# Protocol v3 replacement text", "",
        "Protocol v3 changes only the dual-antenna scalar heading input: the raw HPPOSECEF1/2 stream supplies 5 Hz headings using the fixed physical antenna order and transform. "
        f"Validity is {validity_rule}. The heading standard-deviation marker remains 2.933193 degrees. "
        "The binary, evaluator, other providers, parameters, seeds and configuration set remain those of protocol v2.1.", "",
        "HV priors retain the exact frozen v2.1 files, including every injected condition. Their rotation uses the status heading; they are not regenerated from 5 Hz heading. "
        "Thus the sole heading-input replacement does not establish a synchronized raw-heading/HV model. D57 has zero valid raw-heading epochs and retains the registered failure category. "
        "Injected standard-deviation faults remain on their original 1 Hz rows. Stochastic heading perturbations are held over the original frozen 1 s cells; they are not independent draws at 5 Hz. "
        "Time offsets, three-dimensional baseline observations and alternative weights are excluded. Existing T5bc-R R5sigma/R5W/B3 results are supplementary sensitivity evidence and were not rerun.", "",
        "Every registered result is reported without a numerical performance admission threshold. "
        "Finite-only summaries and paired differences retain explicit denominators; failed or unavailable cases remain in the failure inventory. "
        "External LC01/EXT05C records and the literature-configuration amendment are copied from H-EXT-03/04L without numerical changes.", "",
        "| Sequence | Method | Horizontal RMSE (m) | Yaw RMSE (deg) | Status |", "|---|---|---:|---:|---|"]
    for row in rows:
        text.append("| " + " | ".join(str(row.get(key, UNAVAILABLE)) for key in ("sequence_id", "method_id", "h_rmse_m", "yaw_rmse_deg", "evaluation_status")) + " |")
    text += ["", "Failure counts by method, category and evaluator are provided in FAILURE_COMPARISON.csv; "
        "the complete 52-row external registry, 541-case distributions, 61-case comparison, A1/A2 and BY2O region tables accompany this replacement."]
    return "\n".join(text) + "\n"


class RuntimeResults:
    """Bound new result rows and plot series to their own terminal output seals."""
    def __init__(self, root, sources, code_freeze):
        self.root, self.sources, self.freeze = safe(root), sources, code_freeze
        self.native = json.loads((self.root / "FINAL_RUN_RECORDS.json").read_text())
        self.evaluations = json.loads((self.root / "FINAL_EVALUATION_RECORDS.json").read_text())
        if len(self.native) != 6468 or len(self.evaluations) != 12936:
            raise ValueError("Incomplete v3 terminal matrix cannot enter final reporting")
        self.native_index = {r["run_id"]: r for r in self.native}
        if len(self.native_index) != 6468 or any(r.get("code_commit") != code_freeze or r.get("status") == "HARD_STOP" for r in self.native):
            raise ValueError("Mixed freeze, duplicate run or hard-stop v3 terminal")
        self.payloads = {}
        self.seals = {}
        self.folders, self.archives = {}, {}
        self.counter_cache = {}
        for payload in self.evaluations:
            row = payload["row"]
            version = row["evaluator_contract"].removeprefix("evaluator_contract_")
            key = row["run_id"], version
            if key in self.payloads or key[0] not in self.native_index or version not in VERSIONS:
                raise ValueError("Duplicate/unregistered evaluator terminal")
            folder = safe(payload.get("archive_output_root", self.root / "04_EVALUATION" / key[0] / version))
            seal = json.loads((folder / "OUTPUT_SEAL.json").read_text())
            if seal.get("status") != "SEALED":
                raise ValueError("Unsealed v3 evaluator result")
            sealed = json.loads(sources.read(dict(path=str(folder / "EVALUATION_RESULT.json"),
                sha256=seal["files"]["EVALUATION_RESULT.json"])))
            original_payload = {name: value for name, value in payload.items()
                if name not in ("archive_output_root", "archive_receipt", "resolved_error_series_source")}
            if sealed != original_payload:
                raise ValueError("Final evaluator row differs from its sealed terminal")
            self.payloads[key], self.seals[key] = payload, seal
            self.folders[key] = folder
            receipt = payload.get("archive_receipt")
            self.archives[key] = json.loads(safe(receipt).read_text()) if receipt else None
        if set(self.payloads) != {(run_id, version) for run_id in self.native_index for version in VERSIONS}:
            raise ValueError("Evaluator terminal coverage differs from native slots")

    def rows(self, version):
        from ..canonical541.offline_eval_aggregate import MODULE_SCALARS, MODULE_JSON
        result = []
        for run_id, native in self.native_index.items():
            payload = self.payloads[run_id, version]
            row = deepcopy(payload["row"])
            if payload.get("resolved_error_series_source"):
                row.update(sealed_original_error_series_source=row.get("error_series_source", UNAVAILABLE),
                    error_series_source=payload["resolved_error_series_source"])
            row.update(evaluator_version=version, profile=row["method_id"],
                effective_configuration_id=CONFIG[row["method_id"]],
                degradation_id=row.get("degradation_type_id") or (native.get("source_registry_row") or {}).get("degradation_id") or "CLEAN",
                seed_id=row.get("seed_index", UNAVAILABLE), body_frame_bias=payload.get("body_frame_bias", {}))
            row["horizontal_rmse_m"] = row.get("horizontal_rmse_m", row.get("h_rmse_m", UNAVAILABLE))
            if state(row) != "COMPLETED":
                row.update({metric: UNAVAILABLE for metric in METRICS})
            if row.get("metrics_admitted") is False and state(row) == "COMPLETED":
                raise ValueError("Unadmitted metrics cannot enter v3 tables")
            native_folder = safe(native.get("archive_output_root", native["output_root"]))
            native_manifest = native_folder / "RUN_MANIFEST.json"
            counters = native.get("native_counters", {})
            if run_id in self.counter_cache:
                counters = self.counter_cache[run_id]
            elif native_manifest.is_file():
                digest = native.get("native_manifest_sha256", native.get("file_hashes", {}).get("RUN_MANIFEST.json"))
                if not digest:
                    raise ValueError("Native mechanism manifest lacks terminal hash")
                counters = json.loads(self.sources.read(dict(path=str(native_manifest), sha256=digest)))
                self.counter_cache[run_id] = counters
            for output_name, source_name in {**MODULE_SCALARS, **MODULE_JSON}.items():
                row[output_name] = row.get(output_name, counters.get(source_name, UNAVAILABLE))
            count = number(row.get("source_aware_evaluation_count"))
            changed = number(row.get("source_aware_changed_weight_count"))
            row["source_aware_touch_rate"] = changed / count if count and changed is not None else UNAVAILABLE
            result.append(row)
        return result

    def member(self, key, name):
        folder, seal, archive = self.folders[key], self.seals[key]["files"], self.archives[key]
        digest, stored = seal[name], name
        if archive:
            if archive.get("status") != "ARCHIVE_VERIFIED":
                raise ValueError("Unverified runtime archive")
            item = archive["files"][name]
            if item["source_sha256"] != digest:
                raise ValueError("Archive source digest differs from evaluation seal")
            stored, digest = item["storage_relative_path"], item["sha256"]
        content = self.sources.read(dict(path=str(folder / stored), sha256=digest))
        if archive and archive["files"][name]["compression"] in ("gzip", "gz"):
            content = gzip.decompress(content)
        if hashlib.sha256(content).hexdigest() != seal[name]:
            raise ValueError("Lossless archived evaluation member differs from seal")
        return content, str(folder / stored)

    def series(self, row):
        key = row["run_id"], row["evaluator_version"]
        seal = self.seals[key]["files"]
        candidates = [name for name in seal if Path(name).name in ("error_series.csv", "error_series.csv.gz")]
        if not candidates:
            raise ValueError("Completed v3 evaluation has no sealed error series")
        # Plain and compressed exports, when both retained, must encode identical bytes.
        decoded = []
        for name in candidates:
            content, source = self.member(key, name)
            decoded.append(gzip.decompress(content) if name.endswith(".gz") else content)
        if any(content != decoded[0] for content in decoded[1:]):
            raise ValueError("Sealed error exports disagree")
        frame = pd.read_csv(io.BytesIO(decoded[0]))
        if frame.time.duplicated().any() or not frame.time.is_monotonic_increasing:
            raise ValueError("Sealed error times are not unique and increasing")
        return frame, source

    def truth(self, row):
        key = row["run_id"], row["evaluator_version"]
        seal = self.seals[key]["files"]
        names = [name for name in seal if Path(name).name in ("MATCHED_TRAJECTORY.csv", "MATCHED_TRAJECTORY.csv.gz")]
        if len(names) != 1:
            raise ValueError("MFIG00 requires sealed evaluator-child Truth/estimate export")
        name = names[0]
        content, _ = self.member(key, name)
        return pd.read_csv(io.BytesIO(gzip.decompress(content) if name.endswith(".gz") else content))


def aggregate(root, source_index, *, roots, code_freeze):
    """Write all step-4 numeric deliverables, without overwriting any prior file."""
    root = safe(root)
    output = root / "07_AGGREGATE"
    if output.exists():
        raise FileExistsError("Existing v3 reports must be preserved")
    sources = Sources(roots)
    runtime = RuntimeResults(root, sources, code_freeze)
    tables, audits, all_failures, all_segments, series_index = {}, [], [], [], []
    for version in VERSIONS:
        rows = runtime.rows(version)
        core = [r for r in rows if r["domain"] == "CORE"]
        addendum = [r for r in rows if r["domain"] == "ADDENDUM"]
        sequences = [r for r in rows if r["domain"] == "SEQUENCE"]
        for row in core:
            if row["case_id"] == "C00_clean_normal":
                alias = deepcopy(row)
                alias.update(domain="SEQUENCE", sequence_c00_alias=True)
                sequences.append(alias)
        for domain, current, key in (("CORE", core, "frozen_core"), ("ADDENDUM", addendum, "frozen_addendum"), ("SEQUENCE", sequences, "frozen_sequences")):
            validate_domain(current, domain)
            frozen = sources.rows(source_index[key][version])
            comparisons = comparison_rows(current, frozen)
            stem = "CORE_541" if domain == "CORE" else domain
            tables[f"{stem}_TABLE_{version.upper()}.csv"] = current
            tables[f"{stem}_V21_COMPARISON_{version.upper()}.csv"] = comparisons
            tables[f"{stem}_SUMMARY_{version.upper()}.csv"] = absolute_summary(current)
            tables[f"{stem}_FAMILY_SUMMARY_{version.upper()}.csv"] = absolute_summary(current, grouping=("method_id", "case_family"))
            all_failures.extend(failure_comparison(current, frozen, domain, version))
            if domain == "CORE":
                subset = [r for r in current if r["case_id"] in SUBSET61]
                if len(subset) != 671:
                    raise ValueError("The seed-zero 61-case subset must contain all eleven profiles")
                tables[f"SUBSET61_TABLE_{version.upper()}.csv"] = subset
                tables[f"SUBSET61_V21_COMPARISON_{version.upper()}.csv"] = [r for r in comparisons if r["case_id"] in SUBSET61]
                tables[f"SUBSET61_SUMMARY_{version.upper()}.csv"] = absolute_summary(subset)
                tables[f"CORE_541_TYPE_SUMMARY_{version.upper()}.csv"] = absolute_summary(current, grouping=("method_id", "degradation_id"))
                pairs = paired_rows(current)
                tables[f"PAIRWISE_CASE_LEVEL_{version.upper()}.csv"] = pairs
                tables[f"PAIRWISE_SUMMARY_{version.upper()}.csv"] = paired_summary(pairs)
                tables[f"CORE_541_DISTRIBUTION_{version.upper()}.csv"] = distribution_rows(current)
        horizontal = sources.rows(source_index["horizontal_tables"][version])
        main, replacements = main_table(horizontal, sequences, version)
        tables[f"MAIN_TABLE_{version.upper()}.csv"] = main
        tables[f"ABLATION_TABLE_{version.upper()}.csv"] = [next(r for r in main if r["sequence_id"] == seq and r["method_id"] == method) for seq in SEQUENCES for method in MAIN]
        audits.extend(dict(evaluator_version=version, **row) for row in replacements)
        external_segments = sources.rows(source_index["frozen_by2o_segments"])
        window = source_index["by2o_window"]
        all_segments.extend(by2o_segments(sequences, runtime.series, external_segments, version, window))
        for key, subset in (("sensitivity_pilot", False), ("sensitivity_subset", True)):
            copied = copy_sensitivity(sources.rows(source_index[key][version]), subset=subset)
            tables[f"T5BCR_REFERENCE_{'SUBSET61' if subset else 'THREE_SEQUENCES'}_{version.upper()}.csv"] = copied
        # Exact source records point plots to new full-rate errors, never old series.
        for row in rows:
            series_index.append({key: row.get(key, UNAVAILABLE) for key in ("run_id", "dataset_id", "case_id", "method_id", "domain", "evaluator_version", "evaluation_status", "failure_classification")})
    if "sensitivity_summary" in source_index:
        tables["T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv"] = [r for r in sources.rows(source_index["sensitivity_summary"]) if r.get("variant") in SENSITIVITY_VARIANTS]
    tables.update({"FAILURE_COMPARISON.csv": all_failures, "HORIZONTAL_REPLACEMENT_AUDIT.csv": audits,
        "BY2O_SEGMENT_TABLE.csv": all_segments, "ERROR_SERIES_INDEX.csv": series_index})
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in tables.items():
        write_csv(output / name, rows, fields=TABLE_FIELDS if name.startswith(("MAIN_TABLE_", "ABLATION_TABLE_")) else None)
    (output / "MANUSCRIPT_REPLACEMENT_TEXT.md").write_text(manuscript_text(tables["MAIN_TABLE_V3.csv"], all_failures,
        validity_rule=source_index["validity_rule"]), encoding="utf-8")
    write_json(output / "REPORT_SOURCE_INDEX.json", source_index)
    manifest = dict(status="COMPLETE_V3_AGGREGATES", protocol="v3", code_freeze=code_freeze,
        data_mode="mixed_real_clean_and_semisynthetic_registered_cases", synthetic_data_used=False, semisynthetic_data_used=True,
        native_calls=0, evaluator_calls=0, trace_open_count=0, unique_native_terminals=6468,
        evaluator_terminal_slots=12936, sequence_c00_alias_count=11,
        main_table_rows_per_evaluator=52, core_rows_per_evaluator=5951, addendum_rows_per_evaluator=495,
        sequence_rows_per_evaluator=33, subset61_rows_per_evaluator=671,
        sensitivity_policy="Exact T5bc-R CSV tokens; no reruns; outside the protocol-v3 matrix",
        external_row_policy="All 37 external rows per evaluator retained with byte-identical CSV field tokens",
        files_sha256={p.name: sha256(p) for p in output.iterdir() if p.is_file()}, source_sha256=sources.used)
    write_json(output / "AGGREGATE_MANIFEST.json", manifest)
    return manifest
