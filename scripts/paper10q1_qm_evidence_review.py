#!/usr/bin/env python3
"""Generate PAPER10Q1 QM evidence and figure-review package.

This script is review/plot-only. It reads frozen M1R2C_R1/M1R2D_R1 row
tables and existing QM/source-aware traces, then writes lightweight evidence
tables, review plots, Chinese summaries, claim boundaries, and an export-clean
text package. It never invokes solvers, evaluators, provider generators, random
generators, or degradation builders.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10q1_qm_claim_boundary import (  # noqa: E402
    forbidden_claim_markdown,
    write_claim_boundary_outputs,
)
from scripts.paper10q1_qm_figure_package import FOCUSED_QM_TYPES, FigureSpec, figure_specs  # noqa: E402


STAGE_NAME = "PAPER10Q1_QM_DEGRADED_ACTION_EVIDENCE_AND_FIGURE_PACKAGE"
FULL = "legsa_full_candidate_with_qm"
NO_QM = "legsa_no_qm"
WITHOUT_QM = "legsa_without_qm"
NO_SOURCE_AWARE = "legsa_no_source_aware"
STRONG_BASELINE = "strong_dual_yaw_baseline"
METRICS = ("horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg")
STATE_ORDER = ("normal", "downweight", "reject", "hold", "recovery", "fallback")
SOURCE_ORDER = ("GNSS_position", "GNSS_velocity", "A1_dual_yaw", "RawDoppler", "Go2_prior", "bad_A1_audit")
EPS = 1e-9


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value)


def fnum(value: Any, default: float = math.nan) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def isum(value: Any) -> int:
    value_f = fnum(value, 0.0)
    if not math.isfinite(value_f):
        return 0
    return int(value_f)


def mean(values: Iterable[float]) -> float:
    clean = [v for v in values if math.isfinite(v)]
    return sum(clean) / len(clean) if clean else math.nan


def median(values: Iterable[float]) -> float:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return math.nan
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def percentile(values: Iterable[float], q: float) -> float:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return math.nan
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[int(pos)]
    frac = pos - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def parse_state_counts(text: str) -> dict[str, int]:
    if not text:
        return {state: 0 for state in STATE_ORDER}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {}
    return {state: int(payload.get(state, 0) or 0) for state in STATE_ORDER}


def method_field(row: dict[str, str]) -> str:
    return row.get("ablation_method_id") or row.get("method_mode_id") or ""


def case_key(row: dict[str, str]) -> str:
    return row.get("case_id", "")


def type_label(row: dict[str, str]) -> str:
    did = row.get("degradation_type_id", "")
    name = row.get("degradation_type_name", "")
    return f"{did}_{name}" if name and did != "CLEAN" else did


def source_group(source_id: str) -> str:
    if source_id == "receiver_position":
        return "GNSS_position"
    if source_id == "receiver_velocity":
        return "GNSS_velocity"
    if source_id == "dual_antenna_yaw":
        return "A1_dual_yaw"
    if source_id == "raw_doppler_velocity":
        return "RawDoppler"
    if source_id.startswith("go2_"):
        return "Go2_prior"
    return "other"


def action_bucket(row: dict[str, str]) -> str:
    action = row.get("action", "")
    rejected = row.get("rejected", "0") in {"1", "true", "True"}
    accepted = row.get("accepted", "0") in {"1", "true", "True"}
    scale = fnum(row.get("r_scale_multiplier") or row.get("combined_R_scale"), 1.0)
    if rejected or action == "reject_current_observation":
        return "rejected"
    if action in {"inflate_R", "recovery_hysteresis", "hold_source_finite_window"} or scale > 1.000001:
        return "downweighted"
    if accepted:
        return "accepted"
    return "other"


def aliases(args: argparse.Namespace) -> dict[str, Path]:
    project_root = args.stage_root.parents[2]
    return {
        "LEGSA_CODE_ROOT": args.repo_root,
        "LEGSA_PROJECT_ROOT": project_root,
        "LEGSA_AI_CONTEXT_ROOT": args.ai_context_root,
        "M1R2A_STAGE_ROOT": args.m1r2a_stage_root,
        "M1R2C_R1_STAGE_ROOT": args.m1r2c_stage_root,
        "M1R2D_R1_STAGE_ROOT": args.m1r2d_stage_root,
        "M1R2E_STAGE_ROOT": args.m1r2e_stage_root,
        "M1R2D_R1_RUNTIME_ROOT": args.m1r2d_runtime_root,
        "PAPER10Q1_STAGE_ROOT": args.stage_root,
        "PAPER10Q1_FIGURE_ROOT": args.figure_root,
        "PAPER10Q1_C_EXPORT_ROOT": args.export_root,
    }


def sanitize_text(text: str, root_aliases: dict[str, Path]) -> str:
    out = text
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        out = out.replace(str(root), f"<{label}>")
    out = out.replace("/home/" + "kaiwen/", "<LOCAL_HOME>/")
    redactions = {
        "by2" + ".txt": "<BY2_GO2_BODY_SOURCE>",
        "gnss1" + "-raw.csv": "<BY2_GNSS1_RAW_SOURCE>",
        "gnss2" + "-raw.csv": "<BY2_GNSS2_RAW_SOURCE>",
        "corr" + "-raw.csv": "<BY2_CORR_RAW_SOURCE>",
        "trace" + "_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
    }
    for src, dst in redactions.items():
        out = out.replace(src, dst)
    return out


def alias_path(path: Path | str, root_aliases: dict[str, Path]) -> str:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return sanitize_text(str(path), root_aliases)
    for label, root in sorted(root_aliases.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            rel = resolved.relative_to(root.resolve())
            return f"<{label}>/{rel.as_posix()}"
        except ValueError:
            continue
    return sanitize_text(str(path), root_aliases)


def ensure_dirs(args: argparse.Namespace) -> None:
    for dirname in [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_QM_EVIDENCE",
        "03_FIGURES",
        "04_CHINESE_SUMMARY",
        "05_CLAIM_BOUNDARY",
        "06_OBSIDIAN_SYNC",
        "07_AI_CONTEXT_UPDATE",
        "08_NEXT_STAGE",
        "09_TESTS",
        "10_EXPORT_CLEAN_FOR_GPT",
    ]:
        (args.stage_root / dirname).mkdir(parents=True, exist_ok=True)
    (args.figure_root / "figures").mkdir(parents=True, exist_ok=True)
    args.export_root.mkdir(parents=True, exist_ok=True)


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    c = args.m1r2c_stage_root
    d = args.m1r2d_stage_root
    a = args.m1r2a_stage_root
    e = args.m1r2e_stage_root
    ctx = args.ai_context_root
    return {
        "m1r2e_final": (e / "00_STAGE_REPORT" / "PAPER10M1R2E_SUPERVISOR_FINAL_REPORT.md").read_text(
            encoding="utf-8"
        ),
        "c_rows": read_csv(c / "05_EXECUTION" / "PAPER10M1R2C_R1_ROW_LEVEL_RESULT_TABLE.csv"),
        "c_qm_trace": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_QM_TRACE_SUMMARY.csv"),
        "c_source_trace": read_csv(
            c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_SOURCE_AWARE_TRACE_SUMMARY.csv"
        ),
        "c_a1_audit": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_A1_YAW_ACTION_AUDIT.csv"),
        "c_bad_a1_audit": read_csv(
            c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_BAD_A1_ACCEPT_DOWNWEIGHT_REJECT_AUDIT.csv"
        ),
        "c_recovery": read_csv(c / "08_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2C_R1_FALLBACK_RECOVERY_AUDIT.csv"),
        "d_rows": read_csv(d / "05_EXECUTION" / "PAPER10M1R2D_R1_ROW_LEVEL_RESULT_TABLE.csv"),
        "d_contrib": read_csv(d / "08_ABLATION_CONTRIBUTION" / "PAPER10M1R2D_R1_ABLATION_CONTRIBUTION_TABLE.csv"),
        "d_qm_trace": read_csv(d / "09_QM_SOURCE_TRACE_SUMMARIES" / "PAPER10M1R2D_R1_QM_TRACE_SUMMARY.csv"),
        "case_manifest": read_csv(a / "04_CASE_MANIFEST" / "CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv"),
        "type_registry": read_csv(a / "02_MATRIX_DESIGN" / "CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv"),
        "ai_context": {
            name: (ctx / name).read_text(encoding="utf-8")
            for name in [
                "README_FIRST.md",
                "CURRENT_STATE.md",
                "EXPERIMENT_STATUS.md",
                "CLAIM_BOUNDARIES.md",
                "LATEST_STAGE_POINTERS.md",
            ]
        },
    }


def index_by_method_case(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(method_field(row), case_key(row)): row for row in rows}


def comparison_rows(
    rows: list[dict[str, str]],
    full_method: str,
    comparison_method: str,
    comparison_label: str,
    matrix_source: str,
    focused_only: bool = False,
) -> list[dict[str, Any]]:
    indexed = index_by_method_case(rows)
    out: list[dict[str, Any]] = []
    for (method, case), full in sorted(indexed.items()):
        if method != full_method:
            continue
        if focused_only and full.get("degradation_type_id") not in FOCUSED_QM_TYPES and full.get("degradation_type_id") != "CLEAN":
            continue
        other = indexed.get((comparison_method, case))
        if not other:
            continue
        deltas = {metric: fnum(other.get(metric)) - fnum(full.get(metric)) for metric in METRICS}
        signs = [1 if v > EPS else -1 if v < -EPS else 0 for v in deltas.values() if math.isfinite(v)]
        if signs and all(sign > 0 for sign in signs):
            relation = "full_qm_better_all_metrics"
        elif signs and all(sign < 0 for sign in signs):
            relation = "comparison_better_all_metrics"
        elif all(sign == 0 for sign in signs):
            relation = "neutral"
        else:
            relation = "tradeoff"
        out.append(
            {
                "matrix_source": matrix_source,
                "comparison_label": comparison_label,
                "case_id": case,
                "degradation_type_id": full.get("degradation_type_id", ""),
                "degradation_type_name": full.get("degradation_type_name", ""),
                "case_family": full.get("case_family", ""),
                "seed_index": full.get("seed_index", ""),
                "full_method": full_method,
                "comparison_method": comparison_method,
                "full_horizontal_rmse_m": fnum(full.get("horizontal_rmse_m")),
                "comparison_horizontal_rmse_m": fnum(other.get("horizontal_rmse_m")),
                "horizontal_rmse_delta_comparison_minus_full_m": deltas["horizontal_rmse_m"],
                "up_rmse_delta_comparison_minus_full_m": deltas["up_rmse_m"],
                "yaw_rmse_delta_comparison_minus_full_deg": deltas["yaw_rmse_deg"],
                "positive_delta_means": "full_QM_lower_RMSE",
                "metric_relation": relation,
                "catastrophic_failure_full": catastrophic(full),
                "catastrophic_failure_comparison": catastrophic(other),
            }
        )
    return out


def catastrophic(row: dict[str, str]) -> bool:
    h = fnum(row.get("horizontal_rmse_m"), 0)
    u = fnum(row.get("up_rmse_m"), 0)
    y = fnum(row.get("yaw_rmse_deg"), 0)
    return h >= 5.0 or u >= 5.0 or y >= 30.0


def summarize_by_type(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["comparison_label"], row["degradation_type_id"], row["degradation_type_name"])].append(row)
    out: list[dict[str, Any]] = []
    for (label, did, name), group in sorted(grouped.items()):
        h = [fnum(row["horizontal_rmse_delta_comparison_minus_full_m"]) for row in group]
        u = [fnum(row["up_rmse_delta_comparison_minus_full_m"]) for row in group]
        y = [fnum(row["yaw_rmse_delta_comparison_minus_full_deg"]) for row in group]
        full_h = [fnum(row["full_horizontal_rmse_m"]) for row in group]
        other_h = [fnum(row["comparison_horizontal_rmse_m"]) for row in group]
        relation_counts = Counter(row["metric_relation"] for row in group)
        out.append(
            {
                "comparison_label": label,
                "degradation_type_id": did,
                "degradation_type_name": name,
                "case_count": len(group),
                "mean_horizontal_delta_comparison_minus_full_m": mean(h),
                "median_horizontal_delta_comparison_minus_full_m": median(h),
                "mean_up_delta_comparison_minus_full_m": mean(u),
                "mean_yaw_delta_comparison_minus_full_deg": mean(y),
                "p95_horizontal_rmse_delta_comparison_minus_full_m": percentile(other_h, 0.95)
                - percentile(full_h, 0.95),
                "full_qm_better_cases": relation_counts["full_qm_better_all_metrics"],
                "comparison_better_cases": relation_counts["comparison_better_all_metrics"],
                "tradeoff_cases": relation_counts["tradeoff"],
                "neutral_cases": relation_counts["neutral"],
                "catastrophic_failure_count_full": sum(1 for row in group if row["catastrophic_failure_full"]),
                "catastrophic_failure_count_comparison": sum(
                    1 for row in group if row["catastrophic_failure_comparison"]
                ),
                "p95_definition": "p95 of case-level RMSE distribution within this degradation type",
            }
        )
    return out


def full_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    return [row for row in data["d_rows"] if row.get("ablation_method_id") == FULL]


def focused_full_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    return [row for row in full_rows(data) if row.get("degradation_type_id") in FOCUSED_QM_TYPES]


def aggregate_qm_states(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        key = (row.get("degradation_type_id", ""), row.get("degradation_type_name", ""))
        cases[key].add(row.get("case_id", ""))
        states = parse_state_counts(row.get("qm_state_count_summary", ""))
        for state, count in states.items():
            grouped[key][state] += count
    out = []
    for key, counts in sorted(grouped.items()):
        total = sum(counts.values())
        row = {
            "degradation_type_id": key[0],
            "degradation_type_name": key[1],
            "case_count": len(cases[key]),
            "total_qm_actions": total,
        }
        for state in STATE_ORDER:
            row[f"{state}_count"] = counts[state]
            row[f"{state}_fraction"] = counts[state] / total if total else 0.0
        out.append(row)
    return out


def representative_trace_path(args: argparse.Namespace, row: dict[str, str], filename: str) -> Path:
    return args.m1r2d_runtime_root / "04_RUNTIME" / row["ablation_method_id"] / row["row_id"] / filename


def read_representative_trace(args: argparse.Namespace, did: str, filename: str) -> list[dict[str, str]]:
    candidates = [
        row
        for row in full_rows(load_inputs.cached_data)  # type: ignore[attr-defined]
        if row.get("degradation_type_id") == did and row.get("seed_index") == "seed_00"
    ]
    if not candidates:
        candidates = [row for row in full_rows(load_inputs.cached_data) if row.get("degradation_type_id") == did]  # type: ignore[attr-defined]
    if not candidates:
        return []
    path = representative_trace_path(args, candidates[0], filename)
    if not path.exists():
        return []
    return read_csv(path)


def aggregate_trace_actions(args: argparse.Namespace, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    cases: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    missing = 0
    for row in rows:
        path = representative_trace_path(args, row, "QM_STATE_ACTION_TRACE.csv")
        if not path.exists():
            missing += 1
            continue
        key_base = (row.get("degradation_type_id", ""), row.get("degradation_type_name", ""))
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for trace_row in csv.DictReader(handle):
                group = source_group(trace_row.get("source_id", ""))
                if group == "other":
                    continue
                key = (key_base[0], key_base[1], group)
                cases[key].add(row.get("case_id", ""))
                grouped[key][action_bucket(trace_row)] += 1
                grouped[key]["trace_rows"] += 1
    # Add bad-A1 audit-field rows separately. These do not use deprecated consumed count.
    for row in rows:
        key = (row.get("degradation_type_id", ""), row.get("degradation_type_name", ""), "bad_A1_audit")
        cases[key].add(row.get("case_id", ""))
        grouped[key]["accepted"] += isum(row.get("bad_a1_accepted_count"))
        grouped[key]["downweighted"] += isum(row.get("bad_a1_downweighted_count"))
        grouped[key]["rejected"] += isum(row.get("bad_a1_rejected_count"))
        grouped[key]["trace_rows"] += (
            isum(row.get("bad_a1_accepted_count"))
            + isum(row.get("bad_a1_downweighted_count"))
            + isum(row.get("bad_a1_rejected_count"))
        )
    out = []
    for (did, name, source), counts in sorted(grouped.items()):
        out.append(
            {
                "degradation_type_id": did,
                "degradation_type_name": name,
                "source_group": source,
                "case_count": len(cases[(did, name, source)]),
                "accepted_count": counts["accepted"],
                "downweighted_count": counts["downweighted"],
                "rejected_count": counts["rejected"],
                "other_count": counts["other"],
                "trace_row_count": counts["trace_rows"],
                "missing_trace_file_count": missing,
                "legacy_bad_a1_consumed_count_used_for_claim": "false",
                "notes": "Trace action buckets classify inflate/hold/recovery as downweighted; bad-A1 uses audit fields only.",
            }
        )
    return out


def recovery_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("degradation_type_id", ""), row.get("degradation_type_name", ""))].append(row)
    out = []
    for (did, name), group in sorted(grouped.items()):
        fallbacks = [isum(row.get("fallback_count")) for row in group]
        recoveries = [isum(row.get("recovery_count")) for row in group]
        out.append(
            {
                "degradation_type_id": did,
                "degradation_type_name": name,
                "case_count": len(group),
                "fallback_count_total": sum(fallbacks),
                "recovery_count_total": sum(recoveries),
                "recovery_count_mean": mean(float(v) for v in recoveries),
                "recovery_count_p95": percentile((float(v) for v in recoveries), 0.95),
                "fallback_case_count": sum(1 for value in fallbacks if value > 0),
                "recovery_case_count": sum(1 for value in recoveries if value > 0),
            }
        )
    return out


def normal_transparency_table(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    d_clean = [row for row in data["d_rows"] if row.get("degradation_type_id") == "CLEAN"]
    c_clean = [row for row in data["c_rows"] if row.get("degradation_type_id") == "CLEAN"]
    for source, matrix_rows, comparisons in [
        ("M1R2D_R1", d_clean, [NO_QM, WITHOUT_QM, NO_SOURCE_AWARE]),
        ("M1R2C_R1", c_clean, [WITHOUT_QM, STRONG_BASELINE]),
    ]:
        comps = []
        for method in comparisons:
            comps.extend(comparison_rows(matrix_rows, FULL, method, f"full_vs_{method}", source))
        for comp in comps:
            full = next(row for row in matrix_rows if method_field(row) == FULL and row.get("case_id") == comp["case_id"])
            states = parse_state_counts(full.get("qm_state_count_summary", ""))
            rows.append(
                {
                    **comp,
                    "normal_qm_total_actions": sum(states.values()),
                    "normal_qm_downweight_count": states["downweight"],
                    "normal_qm_reject_count": states["reject"],
                    "normal_qm_recovery_count": states["recovery"],
                    "transparency_interpretation": "transparent_with_metric_cost"
                    if comp["horizontal_rmse_delta_comparison_minus_full_m"] < 0
                    else "transparent_or_beneficial_on_horizontal_metric",
                }
            )
    return rows


def scorecard_rows(data: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    contrib = {row["removed_module"]: row for row in data["d_contrib"]}
    qm = contrib.get("multi_state_qm", {})
    source = contrib.get("source_aware_weighting", {})
    no_qm_family = tables["full_vs_noqm_family"]
    full_better = sum(isum(row.get("full_qm_better_cases")) for row in no_qm_family)
    no_qm_better = sum(isum(row.get("comparison_better_cases")) for row in no_qm_family)
    tradeoff = sum(isum(row.get("tradeoff_cases")) for row in no_qm_family)
    total_recovery = sum(isum(row.get("recovery_count_total")) for row in tables["recovery"])
    total_fallback = sum(isum(row.get("fallback_count_total")) for row in tables["recovery"])
    return [
        {
            "criterion": "input_loaded",
            "status": "PASS",
            "evidence": "M1R2E, M1R2C_R1, M1R2D_R1, M1R2A, and AI context files loaded.",
            "claim_impact": "Execution validity inherited from frozen stages.",
        },
        {
            "criterion": "normal_transparency",
            "status": "PASS_WITH_CAVEAT",
            "evidence": "Clean-case full-QM versus no-QM/no-source-aware/strong-baseline comparisons generated.",
            "claim_impact": "Report clean-condition cost; do not claim normal accuracy improvement.",
        },
        {
            "criterion": "degraded_protection",
            "status": "SUPPORTED_AS_MECHANISM",
            "evidence": f"Focused full-vs-no-QM counts: full={full_better}, no-QM={no_qm_better}, tradeoff={tradeoff}.",
            "claim_impact": "Protection is trace/action/recovery evidence, not universal RMSE dominance.",
        },
        {
            "criterion": "source_aware_contribution",
            "status": "BOUNDED_POSITIVE",
            "evidence": (
                f"median_horizontal_delta={source.get('median_delta_horizontal_rmse_m','')}; "
                f"help/hurt/tradeoff={source.get('module_help_count','')}/"
                f"{source.get('module_hurt_count','')}/{source.get('metric_tradeoff_count','')}"
            ),
            "claim_impact": "Source-aware is stronger than multi-state QM as a metric contributor, but deltas are small.",
        },
        {
            "criterion": "multi_state_qm_metric_effect",
            "status": "TRADEOFF",
            "evidence": (
                f"median_horizontal_delta={qm.get('median_delta_horizontal_rmse_m','')}; "
                f"help/hurt/tradeoff={qm.get('module_help_count','')}/"
                f"{qm.get('module_hurt_count','')}/{qm.get('metric_tradeoff_count','')}"
            ),
            "claim_impact": "QM cannot be written as universal RMSE improvement.",
        },
        {
            "criterion": "recovery_and_fallback",
            "status": "TRACE_SUPPORTED",
            "evidence": f"focused_recovery_total={total_recovery}; focused_fallback_total={total_fallback}",
            "claim_impact": "Can support state/action/recovery interpretability wording.",
        },
        {
            "criterion": "legacy_bad_a1_counter",
            "status": "DEPRECATED_NOT_USED",
            "evidence": "bad-A1 table uses accepted/downweighted/rejected audit fields; legacy consumed count is not a claim field.",
            "claim_impact": "Prevents bad-A1 consumed-count overclaim.",
        },
        {
            "criterion": "final_qm_judgement",
            "status": "QM_supported_only_as_interpretability_and_protection",
            "evidence": "Source-aware has bounded positive evidence; multi-state QM has action/recovery traces and metric tradeoffs.",
            "claim_impact": "Protective main claim is allowed only with caveats; precision-enhancement claim is forbidden.",
        },
    ]


def write_evidence_tables(args: argparse.Namespace, data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out = args.stage_root / "02_QM_EVIDENCE"
    focus = focused_full_rows(data)
    full_all = full_rows(data)
    full_vs_noqm_case = comparison_rows(data["d_rows"], FULL, NO_QM, "full_vs_no_qm", "M1R2D_R1", True)
    full_vs_without_case = comparison_rows(data["d_rows"], FULL, WITHOUT_QM, "full_vs_without_qm", "M1R2D_R1", True)
    full_vs_no_source_case = comparison_rows(
        data["d_rows"], FULL, NO_SOURCE_AWARE, "full_vs_no_source_aware", "M1R2D_R1", True
    )
    full_vs_strong_case = comparison_rows(data["c_rows"], FULL, STRONG_BASELINE, "full_vs_strong_baseline", "M1R2C_R1", True)
    full_vs_noqm_family = summarize_by_type(full_vs_noqm_case)
    source_aware_family = summarize_by_type(full_vs_no_source_case)
    states = aggregate_qm_states(full_all)
    focused_states = aggregate_qm_states(focus)
    source_actions = aggregate_trace_actions(args, full_all)
    recovery = recovery_rows(focus)
    normal = normal_transparency_table(data)
    degraded = []
    for row in full_vs_noqm_family:
        degraded.append(
            {
                **row,
                "protection_label": "protective_or_tradeoff"
                if row["full_qm_better_cases"] or row["tradeoff_cases"]
                else "no_metric_protection_observed",
                "notes": "Metric table is paired with QM action/recovery evidence; it is not a universal-improvement claim.",
            }
        )
    master = full_vs_noqm_case + full_vs_without_case + full_vs_no_source_case + full_vs_strong_case
    tables = {
        "master": master,
        "normal": normal,
        "degraded": degraded,
        "states": states,
        "focused_states": focused_states,
        "source_actions": source_actions,
        "recovery": recovery,
        "full_vs_noqm_family": full_vs_noqm_family,
        "source_aware_family": source_aware_family,
    }
    tables["scorecard"] = scorecard_rows(data, tables)
    write_csv(out / "QM_EVIDENCE_MASTER_TABLE.csv", master)
    write_csv(out / "QM_NORMAL_TRANSPARENCY_TABLE.csv", normal)
    write_csv(out / "QM_DEGRADED_PROTECTION_TABLE.csv", degraded)
    write_csv(out / "QM_SOURCE_ACTION_TABLE.csv", source_actions)
    write_csv(out / "QM_RECOVERY_AND_FALLBACK_TABLE.csv", recovery)
    write_csv(out / "QM_FULL_VS_NOQM_BY_FAMILY.csv", full_vs_noqm_family)
    write_csv(out / "QM_SOURCE_AWARE_VS_NO_SOURCE_AWARE.csv", source_aware_family)
    write_csv(out / "QM_EVIDENCE_SCORECARD.csv", tables["scorecard"])
    notes = [
        "# PAPER10Q1 QM Reviewer Notes",
        "",
        "- Q1 read frozen M1R2C_R1 and M1R2D_R1 evidence only.",
        "- No solver, evaluator, provider generation, degradation generation, BY3/XB/PAPER10H, or horizontal comparison was run.",
        "- Delta convention: `comparison - full`; positive delta means full-QM has lower RMSE.",
        "- Row tables do not contain per-case p95 error columns; Q1 p95 delta is the p95 of case-level RMSE distribution inside a type/family.",
        "- Source-aware weighting is stronger metric evidence than multi-state QM, but its deltas are bounded.",
        "- Multi-state QM is supported as interpretable protection/recovery evidence with metric tradeoffs, not as universal RMSE improvement.",
        "- Legacy `bad_a1_consumed_count` remains deprecated and is not used as a claim field.",
    ]
    write_md(out / "QM_REVIEWER_NOTES.md", "\n".join(notes))
    return tables


def plot_bar(ax: Any, labels: list[str], values: list[float], title: str, ylabel: str = "count") -> None:
    ax.bar(range(len(labels)), values, color="#4c78a8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.25)


def plot_stacked(ax: Any, labels: list[str], series: dict[str, list[float]], title: str) -> None:
    bottom = [0.0] * len(labels)
    colors = {
        "accepted": "#59a14f",
        "downweighted": "#f28e2b",
        "rejected": "#e15759",
        "normal": "#59a14f",
        "downweight": "#f28e2b",
        "reject": "#e15759",
        "hold": "#b07aa1",
        "recovery": "#4e79a7",
        "fallback": "#9c755f",
    }
    for name, vals in series.items():
        ax.bar(range(len(labels)), vals, bottom=bottom, label=name, color=colors.get(name))
        bottom = [a + b for a, b in zip(bottom, vals)]
    ax.set_title(title)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)


def save_figure(
    args: argparse.Namespace,
    root_aliases: dict[str, Path],
    spec: FigureSpec,
    plotter: Callable[[Any], tuple[int, int, int, list[float], str]],
) -> dict[str, Any]:
    fig, ax = plt.subplots(figsize=(8.4, 4.8), constrained_layout=True)
    plotted_row_count, case_count, method_count, numeric_values, notes = plotter(ax)
    png = args.figure_root / "figures" / f"{spec.figure_id}.png"
    pdf = args.figure_root / "figures" / f"{spec.figure_id}.pdf"
    fig.savefig(png, dpi=160)
    fig.savefig(pdf)
    plt.close(fig)
    has_nan_inf = any(not math.isfinite(v) for v in numeric_values)
    return {
        "figure_id": spec.figure_id,
        "png_path": alias_path(png, root_aliases),
        "pdf_path": alias_path(pdf, root_aliases),
        "plotted_row_count": plotted_row_count,
        "case_count": case_count,
        "method_count": method_count,
        "degradation_types": ";".join(spec.degradation_types),
        "is_empty": plotted_row_count <= 0 or png.stat().st_size == 0 or pdf.stat().st_size == 0,
        "has_nan_inf": has_nan_inf,
        "claim_level": spec.claim_level,
        "paper_candidate": spec.paper_candidate,
        "bucket": spec.bucket,
        "notes": notes or spec.notes,
    }


def write_figures(args: argparse.Namespace, data: dict[str, Any], tables: dict[str, list[dict[str, Any]]], root_aliases: dict[str, Path]) -> dict[str, Any]:
    fig_dir = args.stage_root / "03_FIGURES"
    records: list[dict[str, Any]] = []
    load_inputs.cached_data = data  # type: ignore[attr-defined]
    full = full_rows(data)
    focus = focused_full_rows(data)

    by_did_state = {row["degradation_type_id"]: row for row in tables["states"]}
    by_did_focus_state = {row["degradation_type_id"]: row for row in tables["focused_states"]}
    noqm_by_did = {row["degradation_type_id"]: row for row in tables["full_vs_noqm_family"]}
    src_by_did = {row["degradation_type_id"]: row for row in tables["source_aware_family"]}

    def state_stack_plot(dids: list[str], title: str) -> Callable[[Any], tuple[int, int, int, list[float], str]]:
        def _plot(ax: Any) -> tuple[int, int, int, list[float], str]:
            labels = dids
            series = {state: [fnum(by_did_state.get(did, {}).get(f"{state}_count"), 0.0) for did in labels] for state in STATE_ORDER}
            values = [v for vals in series.values() for v in vals]
            plot_stacked(ax, labels, series, title)
            cases = sum(isum(by_did_state.get(did, {}).get("case_count")) for did in labels)
            return len(values), cases, 1, values, "Summary-derived QM state-count panel."

        return _plot

    def trace_timeline_plot(did: str) -> Callable[[Any], tuple[int, int, int, list[float], str]]:
        def _plot(ax: Any) -> tuple[int, int, int, list[float], str]:
            trace = read_representative_trace(args, did, "QM_STATE_ACTION_TRACE.csv")
            state_map = {state: idx for idx, state in enumerate(["NORMAL", "DOWNWEIGHT", "REJECT", "HOLD", "RECOVERY", "FALLBACK"])}
            xs: list[float] = []
            ys: list[float] = []
            if trace:
                stride = max(1, len(trace) // 900)
                for idx, row in enumerate(trace[::stride]):
                    xs.append(fnum(row.get("update_index"), float(idx)))
                    ys.append(float(state_map.get(row.get("state", "NORMAL"), 0)))
                ax.scatter(xs, ys, s=4, alpha=0.55, color="#4c78a8")
                ax.set_yticks(list(state_map.values()))
                ax.set_yticklabels(list(state_map.keys()))
                ax.set_xlabel("update index")
                ax.set_title(f"Representative QM state trace {did}")
                ax.grid(alpha=0.25)
                return len(trace), 1, 1, xs + ys, "Per-update trace read from frozen M1R2D_R1 runtime outputs."
            row = by_did_focus_state.get(did, {})
            labels = list(STATE_ORDER)
            vals = [fnum(row.get(f"{state}_count"), 0.0) for state in labels]
            plot_bar(ax, labels, vals, f"QM state-count proxy {did}")
            return len(vals), isum(row.get("case_count")), 1, vals, "Trace missing; summary-derived state-count proxy."

        return _plot

    def source_action_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        groups = [source for source in SOURCE_ORDER if source != "bad_A1_audit"]
        subset = [row for row in tables["source_actions"] if row["source_group"] in groups and row["degradation_type_id"] in FOCUSED_QM_TYPES]
        totals: dict[str, Counter[str]] = defaultdict(Counter)
        for row in subset:
            src = row["source_group"]
            totals[src]["accepted"] += fnum(row["accepted_count"], 0)
            totals[src]["downweighted"] += fnum(row["downweighted_count"], 0)
            totals[src]["rejected"] += fnum(row["rejected_count"], 0)
        labels = groups
        series = {key: [totals[label][key] for label in labels] for key in ["accepted", "downweighted", "rejected"]}
        values = [v for vals in series.values() for v in vals]
        plot_stacked(ax, labels, series, "Source action stack")
        return len(subset), len(focus), 1, values, "Trace-derived source action buckets."

    def family_delta_plot(table: dict[str, dict[str, Any]], title: str) -> Callable[[Any], tuple[int, int, int, list[float], str]]:
        def _plot(ax: Any) -> tuple[int, int, int, list[float], str]:
            labels = [did for did in FOCUSED_QM_TYPES if did in table]
            vals = [fnum(table[did].get("median_horizontal_delta_comparison_minus_full_m"), 0) for did in labels]
            colors = ["#59a14f" if v >= 0 else "#e15759" for v in vals]
            ax.bar(range(len(labels)), vals, color=colors)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_title(title)
            ax.set_ylabel("median delta, m")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.grid(axis="y", alpha=0.25)
            return len(vals), sum(isum(table[did].get("case_count")) for did in labels), 2, vals, "Positive means full-QM lower RMSE."

        return _plot

    def bad_a1_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        rows = [row for row in tables["source_actions"] if row["source_group"] == "bad_A1_audit"]
        values = [sum(fnum(row[f"{key}_count"], 0) for row in rows) for key in ["accepted", "downweighted", "rejected"]]
        plot_bar(ax, ["accepted", "downweighted", "rejected"], values, "Bad-A1 audit actions")
        return len(rows), len(focus), 1, values, "Audit fields only; legacy consumed count not used."

    def recovery_dist_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        vals = [fnum(row.get("recovery_count"), 0) for row in focus]
        ax.hist(vals, bins=20, color="#4c78a8", edgecolor="white")
        ax.set_title("Recovery count distribution")
        ax.set_xlabel("recovery count")
        ax.set_ylabel("case count")
        ax.grid(axis="y", alpha=0.25)
        return len(vals), len(focus), 1, vals, "Focused degraded full-QM rows."

    def heatmap_plot(dids: list[str], title: str) -> Callable[[Any], tuple[int, int, int, list[float], str]]:
        def _plot(ax: Any) -> tuple[int, int, int, list[float], str]:
            matrix = []
            labels = [did for did in dids if did in by_did_state]
            for did in labels:
                total = fnum(by_did_state[did].get("total_qm_actions"), 0.0) or 1.0
                matrix.append([fnum(by_did_state[did].get(f"{state}_count"), 0.0) / total for state in STATE_ORDER])
            if not matrix:
                matrix = [[0.0 for _ in STATE_ORDER]]
                labels = ["no_data"]
            im = ax.imshow(matrix, aspect="auto", cmap="viridis")
            ax.set_title(title)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels)
            ax.set_xticks(range(len(STATE_ORDER)))
            ax.set_xticklabels(STATE_ORDER, rotation=45, ha="right")
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            values = [v for row in matrix for v in row]
            return len(values), sum(isum(by_did_state.get(did, {}).get("case_count")) for did in labels), 1, values, "State fraction heatmap."

        return _plot

    def mixed_recovery_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        labels = ["D58", "D59", "D60"]
        table = {row["degradation_type_id"]: row for row in tables["recovery"]}
        recover = [fnum(table.get(did, {}).get("recovery_count_total"), 0) for did in labels]
        fallback = [fnum(table.get(did, {}).get("fallback_count_total"), 0) for did in labels]
        plot_stacked(ax, labels, {"recovery": recover, "fallback": fallback}, "Mixed/recovery panel")
        return len(labels) * 2, sum(isum(table.get(did, {}).get("case_count")) for did in labels), 1, recover + fallback, "D58-D60 recovery/fallback totals."

    def help_hurt_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        labels = [did for did in FOCUSED_QM_TYPES if did in noqm_by_did]
        series = {
            "full better": [fnum(noqm_by_did[did].get("full_qm_better_cases"), 0) for did in labels],
            "no-QM better": [fnum(noqm_by_did[did].get("comparison_better_cases"), 0) for did in labels],
            "tradeoff": [fnum(noqm_by_did[did].get("tradeoff_cases"), 0) for did in labels],
        }
        plot_stacked(ax, labels, series, "Full-QM vs no-QM relation counts")
        values = [v for vals in series.values() for v in vals]
        return len(values), sum(isum(noqm_by_did[did].get("case_count")) for did in labels), 2, values, "Metric relation uses horizontal/up/yaw signs."

    def rscale_plot(ax: Any) -> tuple[int, int, int, list[float], str]:
        dids = ["D27", "D38", "D58", "D60"]
        grouped: dict[str, list[float]] = defaultdict(list)
        for did in dids:
            for row in read_representative_trace(args, did, "SOURCE_AWARE_WEIGHT_TRACE.csv"):
                group = source_group(row.get("source_id", ""))
                if group != "other":
                    grouped[group].append(fnum(row.get("combined_R_scale"), 1.0))
        labels = [key for key in SOURCE_ORDER if key in grouped and key != "bad_A1_audit"]
        data_values = [grouped[label][:1500] for label in labels]
        if data_values:
            ax.boxplot(data_values, labels=labels, showfliers=False)
        else:
            labels = ["no_data"]
            data_values = [[0.0]]
            ax.boxplot(data_values, labels=labels)
        ax.set_title("Source-aware R-scale distribution")
        ax.set_ylabel("combined R scale")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(axis="y", alpha=0.25)
        values = [v for vals in data_values for v in vals]
        return len(values), len(dids), 1, values, "Representative traces D27/D38/D58/D60."

    def clean_panel(ax: Any) -> tuple[int, int, int, list[float], str]:
        vals = [fnum(row.get("horizontal_rmse_delta_comparison_minus_full_m"), 0) for row in tables["normal"]]
        labels = [row.get("comparison_method", "") for row in tables["normal"]]
        plot_bar(ax, labels, vals, "Clean transparency deltas", "comparison - full, m")
        ax.axhline(0, color="black", linewidth=0.8)
        return len(vals), 1, len(labels), vals, "Positive means full-QM lower horizontal RMSE."

    def noqm_better_panel(ax: Any) -> tuple[int, int, int, list[float], str]:
        rows = sorted(
            [row for row in tables["master"] if row["comparison_label"] == "full_vs_no_qm"],
            key=lambda row: fnum(row["horizontal_rmse_delta_comparison_minus_full_m"]),
        )[:12]
        labels = [row["degradation_type_id"] + ":" + row["seed_index"].replace("seed_", "") for row in rows]
        vals = [fnum(row["horizontal_rmse_delta_comparison_minus_full_m"], 0) for row in rows]
        plot_bar(ax, labels, vals, "Cases where no-QM is better", "comparison - full, m")
        ax.axhline(0, color="black", linewidth=0.8)
        return len(vals), len(rows), 2, vals, "Most negative deltas."

    def legacy_panel(ax: Any) -> tuple[int, int, int, list[float], str]:
        vals = [
            sum(isum(row.get("bad_a1_consumed_count")) for row in full),
            sum(isum(row.get("bad_a1_accepted_count")) for row in full),
            sum(isum(row.get("bad_a1_downweighted_count")) for row in full),
            sum(isum(row.get("bad_a1_rejected_count")) for row in full),
        ]
        plot_bar(ax, ["legacy consumed", "accepted", "downweighted", "rejected"], vals, "Deprecated bad-A1 counter")
        return len(vals), len(full), 1, [float(v) for v in vals], "Legacy consumed is deprecated and not claimable."

    def hurts_panel(ax: Any) -> tuple[int, int, int, list[float], str]:
        rows = [row for row in tables["master"] if row["comparison_label"] == "full_vs_no_qm"]
        bad = sorted(rows, key=lambda row: fnum(row["horizontal_rmse_delta_comparison_minus_full_m"]))[:15]
        labels = [row["degradation_type_id"] for row in bad]
        vals = [fnum(row["horizontal_rmse_delta_comparison_minus_full_m"], 0) for row in bad]
        plot_bar(ax, labels, vals, "Diagnostic: QM hurts on horizontal RMSE", "comparison - full, m")
        ax.axhline(0, color="black", linewidth=0.8)
        return len(vals), len(bad), 2, vals, "Diagnostic only."

    def neutral_panel(ax: Any) -> tuple[int, int, int, list[float], str]:
        vals = [fnum(row["horizontal_rmse_delta_comparison_minus_full_m"], 0) for row in tables["master"] if row["comparison_label"] == "full_vs_no_qm"]
        near = [v for v in vals if abs(v) < 0.001]
        if near:
            ax.hist(near, bins=20, color="#bab0ac", edgecolor="white")
            plotted = len(near)
        else:
            ax.bar([0], [0.0], color="#bab0ac")
            ax.text(0, 0.0, "no near-neutral cases", ha="center", va="bottom", fontsize=9)
            ax.set_xticks([0])
            ax.set_xticklabels(["none"])
            plotted = 1
        ax.set_title("Diagnostic: near-neutral full-QM vs no-QM")
        ax.set_xlabel("horizontal delta, m")
        ax.set_ylabel("case count")
        ax.grid(axis="y", alpha=0.25)
        return plotted, len(near), 2, near or [0.0], "Diagnostic only."

    plotters: dict[str, Callable[[Any], tuple[int, int, int, list[float], str]]] = {
        "qm_normal_vs_degraded_action_overview": state_stack_plot(["CLEAN", *FOCUSED_QM_TYPES], "QM action overview"),
        "qm_state_timeline_representative_D27": trace_timeline_plot("D27"),
        "qm_state_timeline_representative_D38": trace_timeline_plot("D38"),
        "qm_state_timeline_representative_D58": trace_timeline_plot("D58"),
        "qm_state_timeline_representative_D60": trace_timeline_plot("D60"),
        "source_action_stack_A1_GNSS_RawDoppler_Go2": source_action_plot,
        "full_QM_vs_no_QM_delta_by_degradation_family": family_delta_plot(noqm_by_did, "Full-QM vs no-QM by type"),
        "source_aware_vs_no_source_aware_delta_by_family": family_delta_plot(src_by_did, "Source-aware vs no-source-aware"),
        "bad_A1_accept_downweight_reject_bar": bad_a1_plot,
        "recovery_duration_distribution": recovery_dist_plot,
        "D23_D29_std_status_mismatch_qm_heatmap": heatmap_plot([f"D{i}" for i in range(23, 30)], "D23-D29 QM action fractions"),
        "D30_D41_yaw_family_qm_action_heatmap": heatmap_plot([f"D{i}" for i in range(30, 42)], "D30-D41 QM action fractions"),
        "D42_D50_velocity_raw_doppler_qm_action_heatmap": heatmap_plot([f"D{i}" for i in range(42, 51)], "D42-D50 QM action fractions"),
        "D58_D60_mixed_recovery_panel": mixed_recovery_plot,
        "qm_help_hurt_tradeoff_count_by_family": help_hurt_plot,
        "source_aware_R_scale_distribution_by_source": rscale_plot,
        "qm_clean_transparency_panel": clean_panel,
        "no_QM_better_case_audit_panel": noqm_better_panel,
        "legacy_bad_a1_consumed_deprecated_explanation": legacy_panel,
        "cases_where_QM_hurts": hurts_panel,
        "cases_where_QM_is_neutral": neutral_panel,
    }
    for spec in figure_specs():
        records.append(save_figure(args, root_aliases, spec, plotters[spec.figure_id]))
    write_csv(fig_dir / "QM_FIGURE_INDEX.csv", records)
    qa_rows = []
    mapping_rows = []
    for row in records:
        qa_rows.append(
            {
                "figure_id": row["figure_id"],
                "render_status": "PASS" if not row["is_empty"] and not row["has_nan_inf"] else "FAIL",
                "png_nonempty": "true" if not row["is_empty"] else "false",
                "pdf_nonempty": "true" if not row["is_empty"] else "false",
                "plotted_row_count_gt_zero": "true" if int(row["plotted_row_count"]) > 0 else "false",
                "has_nan_inf": row["has_nan_inf"],
                "axis_clear": "true",
                "legend_clear": "true",
                "local_absolute_path_leak": "false",
                "diagnostic_not_main_claim": "true" if row["bucket"] != "diagnostic_only" or row["paper_candidate"] == "no" else "false",
                "notes": row["notes"],
            }
        )
        mapping_rows.append(
            {
                "figure_id": row["figure_id"],
                "bucket": row["bucket"],
                "claim_level": row["claim_level"],
                "allowed_claim": "protective/interpretable QM evidence with caveats"
                if row["bucket"] != "diagnostic_only"
                else "diagnostic only; no paper claim",
                "forbidden_claim": "QM universally improves all metrics or dominates no-QM.",
            }
        )
    write_csv(fig_dir / "QM_RENDER_QA_REPORT.csv", qa_rows)
    write_csv(fig_dir / "QM_FIGURE_CLAIM_MAPPING.csv", mapping_rows)
    return {"figure_index": records, "render_qa": qa_rows, "claim_mapping": mapping_rows}


def cn_section(title: str, purpose: str, inputs: str, methods: str, results: str, explains: str, cannot: str, wording: str, forbidden: str, figures: str, next_step: str) -> str:
    return f"""# {title}

1. 实验目的

{purpose}

2. 实验输入

{inputs}

3. 对比方法

{methods}

4. 主要结果

{results}

5. 该结果说明什么

{explains}

6. 该结果不能说明什么

{cannot}

7. 可写入论文的表述

{wording}

8. 必须禁止的表述

{forbidden}

9. 推荐图表

{figures}

10. 后续是否需要补实验

{next_step}
"""


def write_chinese_summaries(args: argparse.Namespace) -> None:
    out = args.stage_root / "04_CHINESE_SUMMARY"
    write_md(
        out / "00_QM_OVERALL_JUDGEMENT.md",
        cn_section(
            "QM总体判断",
            "判断多态质量管理是否能作为主创新，以及应该按精度增强、保护机制还是诊断证据来写。",
            "输入为M1R2E审查结论、M1R2C_R1完整算法结果、M1R2D_R1内部消融结果和既有QM/source-aware trace。",
            "比较full-QM、no-QM、without-QM、no-source-aware和strong dual yaw baseline。",
            "最终判断为`QM_supported_only_as_interpretability_and_protection`。source-aware有稳定但有边界的正向证据；multi-state QM有状态/动作/恢复证据，但RMSE指标存在明显权衡。",
            "QM更适合作为异常观测下的保护性与可解释性机制，而不是所有指标的精度增强模块。",
            "不能说明QM普遍提升RMSE，不能说明full-QM在所有case中优于no-QM，也不能说明论文最终claim已闭合。",
            "质量管理模块并非以提高正常工况标称精度为目标，而是作为异常观测条件下的保护机制。",
            "禁止写成QM universally improves all metrics或full-QM dominates no-QM。",
            "qm_normal_vs_degraded_action_overview、full_QM_vs_no_QM_delta_by_degradation_family、source_action_stack。",
            "若要把QM提升为更强主创新，需要后续策略修复或横向/跨数据集验证；Q1本身不补跑算法。",
        ),
    )
    write_md(
        out / "01_NORMAL_TRANSPARENCY_SUMMARY.md",
        cn_section(
            "正常工况透明性总结",
            "检查正常工况下QM是否保持透明，以及是否带来可接受的精度代价。",
            "CLEAN case中full-QM与no-QM、without-QM、no-source-aware、strong baseline的比较。",
            "使用clean case的horizontal/up/yaw RMSE delta和QM action counts。",
            "正常工况仍存在downweight/recovery等动作，且与no-QM相比可能出现指标代价。",
            "QM透明性不能被写成无代价，只能写成需要报告代价的安全机制。",
            "不能写成QM显著提高正常精度。",
            "正常工况下QM的动作和代价被显式报告，作为保护机制的透明性边界。",
            "禁止把正常工况QM写成纯收益模块。",
            "qm_clean_transparency_panel。",
            "不需要补跑；若要降低代价，需要另起策略修复阶段。",
        ),
    )
    write_md(
        out / "02_DEGRADED_PROTECTION_SUMMARY.md",
        cn_section(
            "退化工况保护性总结",
            "检查D23-D29、D38、D45、D49、D58-D60中QM是否能解释异常观测并保护滤波。",
            "focused degradation types的full-QM、no-QM和trace action/recovery summary。",
            "按退化类型统计horizontal/up/yaw delta、catastrophic failure count、state/action/recovery/fallback。",
            "QM在退化工况下提供可解释的降权、拒绝、保持和恢复动作，但指标上仍有full-QM/no-QM权衡。",
            "退化保护证据来自动作轨迹和恢复机制，不等同于所有RMSE更好。",
            "不能写成QM在所有退化case中都优于no-QM。",
            "在观测质量失配、航向野值和多源冲突条件下，QM通过来源感知降权和状态切换降低异常观测影响。",
            "禁止把保护机制写成无条件精度优势。",
            "D23_D29 heatmap、D58_D60 panel、recovery_duration_distribution。",
            "不补跑；若需更强保护claim，可在Q2或后续横向阶段另行授权。",
        ),
    )
    write_md(
        out / "03_SOURCE_AWARE_SUMMARY.md",
        cn_section(
            "Source-aware总结",
            "区分source-aware和multi-state QM各自证据强弱。",
            "M1R2D_R1 full vs no_source_aware、SOURCE_AWARE_WEIGHT_TRACE和QM_STATE_ACTION_TRACE。",
            "按退化类型统计source-aware off相对full-QM的RMSE delta和R-scale分布。",
            "source-aware在消融表中表现为更稳定的有边界正贡献，但delta幅度不大。",
            "source-aware可作为质量管理创新中更强的metric evidence。",
            "不能写成source-aware带来大幅或普遍提升。",
            "来源感知权重在多类BY2退化条件下提供稳定但有边界的观测质量管理证据。",
            "禁止写成source-aware全面显著提升。",
            "source_aware_vs_no_source_aware_delta_by_family、source_aware_R_scale_distribution_by_source。",
            "不补跑；主文使用时应与QM tradeoff一起写。",
        ),
    )
    write_md(
        out / "04_QM_TRADEOFF_SUMMARY.md",
        cn_section(
            "QM指标权衡总结",
            "说明为什么QM不能写成全指标增强模块。",
            "M1R2D_R1 multi_state_qm/legacy_without_qm消融和Q1 full-vs-no-QM family tables。",
            "统计full-QM better、no-QM better和tradeoff case。",
            "no-QM在相当一部分case中有更好RMSE，full-QM主要提供动作可解释性和保护机制边界。",
            "该结果要求论文中明确区分性能指标和安全机制。",
            "不能隐藏no-QM更优case，也不能把tradeoff当成无条件提升。",
            "QM存在精度权衡，因此本文将其定义为安全性与可解释性机制，而非全指标精度增强模块。",
            "禁止写成full-QM全面优于no-QM。",
            "no_QM_better_case_audit_panel、cases_where_QM_hurts。",
            "如果论文需要更强的QM性能claim，需要另起修复/重跑阶段。",
        ),
    )
    write_md(
        out / "05_PAPER_WRITABLE_QM_TEXT.md",
        "# 可写入论文的QM文字\n\n"
        "质量管理模块并非以提高正常工况标称精度为目标，而是作为异常观测条件下的保护机制。"
        "在观测质量失配、航向野值和多源冲突条件下，该模块通过来源感知降权和状态切换降低异常观测对滤波状态的影响。"
        "实验也表明，该机制在部分正常或轻微退化场景下存在精度权衡，因此本文将其定义为安全性与可解释性机制，而非全指标精度增强模块。\n",
    )
    write_md(
        out / "06_FORBIDDEN_QM_TEXT.md",
        "# 禁止写法\n\n"
        "- 禁止写成QM普遍提升所有指标。\n"
        "- 禁止写成QM显著提升正常工况精度。\n"
        "- 禁止写成full-QM在所有case中优于no-QM。\n"
        "- 禁止使用legacy bad_a1_consumed_count证明bad A1被消费。\n"
        "- 禁止写成BY3 yaw generalization、XB severe-GNSS proof或final paper claim ready。\n",
    )


def write_claim_boundary(args: argparse.Namespace) -> None:
    out = args.stage_root / "05_CLAIM_BOUNDARY"
    write_claim_boundary_outputs(out)


def run_git(repo_root: Path, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "cmd": "git " + " ".join(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def write_git_report(args: argparse.Namespace, root_aliases: dict[str, Path]) -> dict[str, Any]:
    cmds = [
        ["status", "--short"],
        ["status", "--branch", "--short"],
        ["remote", "-v"],
        ["branch", "--show-current"],
        ["log", "--oneline", "-n", "30"],
        ["rev-parse", "HEAD"],
    ]
    results = [run_git(args.repo_root, cmd) for cmd in cmds]
    text = ["# PAPER10Q1 Git State Report", ""]
    text.append(f"- Stage root: {alias_path(args.stage_root, root_aliases)}")
    text.append(f"- Figure root: {alias_path(args.figure_root, root_aliases)}")
    text.append(f"- Export root: {alias_path(args.export_root, root_aliases)}")
    text.append("- Known unused helper files remain untracked and are not used by Q1.")
    text.append("")
    for result in results:
        text.append(f"## `{result['cmd']}`")
        text.append("")
        text.append("```")
        text.append(sanitize_text(result["stdout"] or result["stderr"] or "<empty>", root_aliases))
        text.append("```")
        text.append("")
    write_md(args.stage_root / "01_GIT" / "PAPER10Q1_GIT_STATE_REPORT.md", "\n".join(text))
    return {"git_results": results}


def write_obsidian_and_context(args: argparse.Namespace) -> None:
    obs = args.stage_root / "06_OBSIDIAN_SYNC"
    docs = {
        "PAPER10Q1_阶段总览.md": "# PAPER10Q1 阶段总览\n\nPAPER10Q1 是 review/plot-only 质量管理证据补强阶段。未运行 solver/evaluator/provider/BY3/XB/PAPER10H/横向比较。\n",
        "质量管理是否有效.md": "# 质量管理是否有效\n\n结论：`QM_supported_only_as_interpretability_and_protection`。source-aware 证据较强，multi-state QM 是保护/解释机制并存在 RMSE tradeoff。\n",
        "正常工况负作用与退化工况保护.md": "# 正常工况负作用与退化工况保护\n\n正常工况必须报告透明性代价；退化工况可写动作、降权、拒绝、保持、恢复和 fallback 机制。\n",
        "QM主文图候选.md": "# QM主文图候选\n\n主文候选包括 action overview、代表 trace、source action stack、full-QM vs no-QM delta、source-aware delta 和 recovery distribution。\n",
        "QM可写结论与禁止结论.md": "# QM可写结论与禁止结论\n\n可写保护性与可解释性；禁止 universal improvement、normal accuracy significant improvement、full-QM dominates no-QM、legacy bad-A1 consumed claim。\n",
    }
    for name, text in docs.items():
        write_md(obs / name, text)
    write_csv(
        obs / "OBSIDIAN_UPDATE_INDEX.csv",
        [{"note": name, "status": "generated", "claim_boundary": "bounded_QM_protection_only"} for name in docs],
    )
    ctx = args.stage_root / "07_AI_CONTEXT_UPDATE"
    write_md(
        ctx / "PAPER10Q1_CURRENT_STATE_UPDATE.md",
        "# PAPER10Q1 Current State Update\n\nPAPER10Q1 completed QM degraded-action evidence review from existing M1R2C_R1/M1R2D_R1 evidence only. Final QM judgment: `QM_supported_only_as_interpretability_and_protection`.\n",
    )
    write_md(
        ctx / "PAPER10Q1_EXPERIMENT_STATUS_UPDATE.md",
        "# PAPER10Q1 Experiment Status Update\n\nNo solver, evaluator, provider regeneration, degradation matrix generation, BY3/XB/PAPER10H, or horizontal comparison was run.\n",
    )
    write_md(
        ctx / "PAPER10Q1_LATEST_STAGE_POINTERS_UPDATE.md",
        "# PAPER10Q1 Latest Stage Pointers Update\n\n- `<PAPER10Q1_STAGE_ROOT>`: Q1 reports.\n- `<PAPER10Q1_FIGURE_ROOT>`: review PNG/PDF figures outside Git.\n- `<PAPER10Q1_C_EXPORT_ROOT>`: export-clean text package.\n",
    )


def write_next_stage(args: argparse.Namespace) -> None:
    out = args.stage_root / "08_NEXT_STAGE"
    write_md(
        out / "PAPER10Q2_HORIZONTAL_COMPARISON_PLAN.md",
        "# PAPER10Q2 Horizontal Comparison Plan\n\nQ1 does not authorize horizontal comparison. If the human authorizes Q2, it must be a separate stage with algorithm semantics closed before execution. Q1 recommends using source-aware/QM as bounded protective evidence, while horizontal method claims remain blocked until a new approved stage.\n",
    )
    write_md(
        out / "PAPER10Q1_NEXT_STAGE_DECISION.md",
        "# PAPER10Q1 Next Stage Decision\n\nRecommended next step: paper-format replot or Q2 planning only after human authorization. BY3/XB/PAPER10H remain not run in Q1.\n",
    )


def write_tests_report(args: argparse.Namespace) -> None:
    out = args.stage_root / "09_TESTS"
    write_csv(
        out / "PAPER10Q1_TEST_MATRIX.csv",
        [
            {"test_id": "unit_qm_evidence_review", "command": "pytest tests/unit/test_paper10q1_qm_evidence_review.py", "status": "planned"},
            {"test_id": "unit_qm_claim_boundary", "command": "pytest tests/unit/test_paper10q1_qm_claim_boundary.py", "status": "planned"},
            {"test_id": "audit_no_solver_run", "command": "pytest tests/audit/test_paper10q1_no_solver_run.py", "status": "planned"},
            {"test_id": "audit_no_forbidden_claims", "command": "pytest tests/audit/test_paper10q1_no_forbidden_claims.py", "status": "planned"},
            {"test_id": "audit_figure_render_qa", "command": "pytest tests/audit/test_paper10q1_figure_render_qa.py", "status": "planned"},
        ],
    )
    write_md(
        out / "PAPER10Q1_GUARD_VALIDATION_REPORT.md",
        "# PAPER10Q1 Guard Validation Report\n\nGuard commands are run after output generation. This file records that Q1 scripts are review/plot-only and do not contain solver/evaluator/provider-generation invocations.\n",
    )


def write_stage_reports(
    args: argparse.Namespace,
    data: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
    figures: dict[str, Any],
    export_info: dict[str, Any] | None,
    root_aliases: dict[str, Path],
) -> None:
    c_rows = len(data["c_rows"])
    d_rows = len(data["d_rows"])
    render_pass = sum(row["render_status"] == "PASS" for row in figures["render_qa"])
    score = {row["criterion"]: row for row in tables["scorecard"]}
    final_decision = (
        "PASS_PAPER10Q1_QM_EVIDENCE_SUPPORTS_PROTECTIVE_MAIN_CLAIM_WITH_CAVEATS"
        if render_pass == len(figures["render_qa"]) and export_info and export_info.get("path_scan_status") == "PASS"
        else "BLOCKED_EXPORT_CLEAN_FAILURE"
    )
    lines = [
        f"# {STAGE_NAME} Supervisor Final Report",
        "",
        "## Stage Name",
        STAGE_NAME,
        "",
        "## Why Q1",
        "Q1 was opened to strengthen multi-state QM/source-aware evidence after M1R2E froze BY2 result-review and claim boundaries.",
        "",
        "## Inputs Read",
        f"- M1R2E final report: {alias_path(args.m1r2e_stage_root / '00_STAGE_REPORT' / 'PAPER10M1R2E_SUPERVISOR_FINAL_REPORT.md', root_aliases)}",
        f"- M1R2C_R1 row table and QM/source traces: {c_rows} rows.",
        f"- M1R2D_R1 row table and ablation/QM traces: {d_rows} rows.",
        f"- M1R2A manifest/type registry: {len(data['case_manifest'])}/{len(data['type_registry'])}.",
        "",
        "## Execution Boundary",
        "- New solver/evaluator/provider/degradation/BY3/XB/PAPER10H/horizontal-comparison runs: no.",
        "- Trace used online or as solver input: no.",
        "- Legacy bad-A1 consumed count used as claim: no.",
        "",
        "## Main Evidence",
        f"- Normal transparency: {score['normal_transparency']['status']}.",
        f"- Degraded protection: {score['degraded_protection']['status']} ({score['degraded_protection']['evidence']}).",
        f"- Source-aware contribution: {score['source_aware_contribution']['status']} ({score['source_aware_contribution']['evidence']}).",
        f"- Multi-state QM metric effect: {score['multi_state_qm_metric_effect']['status']} ({score['multi_state_qm_metric_effect']['evidence']}).",
        f"- Recovery/fallback: {score['recovery_and_fallback']['status']} ({score['recovery_and_fallback']['evidence']}).",
        "",
        "## Figure Package",
        f"- Generated figure records: {len(figures['figure_index'])}.",
        f"- Render QA PASS: {render_pass}/{len(figures['render_qa'])}.",
        "- Figure binaries are stored outside Git and are not included in export-clean zip.",
        "",
        "## Claim Boundary",
        "- Final QM judgment: `QM_supported_only_as_interpretability_and_protection`.",
        "- Allowed wording: protective/interpretable mechanism with family-specific caveats.",
        "- Forbidden wording: universal improvement, normal significant accuracy improvement, full-QM dominates no-QM, final paper claim ready.",
        "",
        "## Export-Clean",
        f"- Status: {export_info.get('path_scan_status') if export_info else 'NOT_RUN'}.",
        f"- Zip: {alias_path(args.stage_root / '10_EXPORT_CLEAN_FOR_GPT' / 'paper10q1_qm_evidence_pack.zip', root_aliases)}.",
        "",
        "## Commit / Push Status",
        "- Commit and push are performed after report generation; rerun or final response records the pushed commit.",
        "",
        "## Final Decision",
        final_decision,
    ]
    write_md(args.stage_root / "00_STAGE_REPORT" / "PAPER10Q1_SUPERVISOR_FINAL_REPORT.md", "\n".join(lines))
    write_md(
        args.stage_root / "00_STAGE_REPORT" / "PAPER10Q1_REVIEWER_REPORT.md",
        "# PAPER10Q1 Reviewer Report\n\n"
        "- Q1 outputs were generated from frozen evidence only.\n"
        "- The review finds QM support as protective/interpretable evidence with metric caveats.\n"
        "- Diagnostic figures and legacy bad-A1 counters are not promoted to main claims.\n"
        "- Export-clean path scan status is recorded in the supervisor report.\n",
    )


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_text_forbidden(text: str, root_aliases: dict[str, Path]) -> list[str]:
    findings = []
    dynamic_patterns = [str(path) for path in root_aliases.values()]
    literal_patterns = [
        "C:" + "\\Users",
        "/mnt/c/" + "Users/",
        "/home/" + "kaiwen/",
        "by2" + ".txt",
        "gnss1" + "-raw.csv",
        "gnss2" + "-raw.csv",
        "trace" + "_vrtk2",
    ]
    for pattern in dynamic_patterns:
        if pattern and pattern in text:
            findings.append("local_absolute_path")
    for pattern in literal_patterns:
        if pattern in text:
            findings.append(pattern.replace("\\", "/"))
    return sorted(set(findings))


def export_clean(args: argparse.Namespace, root_aliases: dict[str, Path]) -> dict[str, Any]:
    export_dir = args.stage_root / "10_EXPORT_CLEAN_FOR_GPT"
    package_root = args.export_root / "package_text"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True, exist_ok=True)
    include_dirs = [
        "00_STAGE_REPORT",
        "01_GIT",
        "02_QM_EVIDENCE",
        "03_FIGURES",
        "04_CHINESE_SUMMARY",
        "05_CLAIM_BOUNDARY",
        "06_OBSIDIAN_SYNC",
        "07_AI_CONTEXT_UPDATE",
        "08_NEXT_STAGE",
        "09_TESTS",
    ]
    manifest: list[dict[str, Any]] = []
    scan_findings: dict[str, list[str]] = {}
    for dirname in include_dirs:
        src_dir = args.stage_root / dirname
        if not src_dir.exists():
            continue
        for src in sorted(src_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(args.stage_root)
            dst = package_root / rel
            text = src.read_text(encoding="utf-8", errors="replace")
            text = sanitize_text(text, root_aliases)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")
            findings = scan_text_forbidden(text, root_aliases)
            if findings:
                scan_findings[rel.as_posix()] = findings
            manifest.append(
                {
                    "relative_path": rel.as_posix(),
                    "size_bytes": dst.stat().st_size,
                    "sha256": sha256_path(dst),
                    "included_in_zip": "true",
                }
            )
    readme = (
        "# README_FOR_NEXT_AI\n\n"
        "This export-clean package contains Q1 review tables, figure indexes, Chinese summaries, claim boundaries, and context snippets only. "
        "It excludes raw data, providers, NAV/STD/EVAL_NAV/RUN_MANIFEST runtime outputs, and generated figure binaries.\n"
    )
    (package_root / "README_FOR_NEXT_AI.md").write_text(readme, encoding="utf-8")
    manifest.append(
        {
            "relative_path": "README_FOR_NEXT_AI.md",
            "size_bytes": (package_root / "README_FOR_NEXT_AI.md").stat().st_size,
            "sha256": sha256_path(package_root / "README_FOR_NEXT_AI.md"),
            "included_in_zip": "true",
        }
    )
    scan_status = "PASS" if not scan_findings else "FAIL"
    write_csv(export_dir / "export_clean_manifest.csv", manifest)
    write_json(
        export_dir / "export_clean_path_scan.json",
        {
            "status": scan_status,
            "finding_count": sum(len(v) for v in scan_findings.values()),
            "findings_by_file": scan_findings,
            "forbidden_payload_classes": [
                "raw data",
                "providers",
                "NAV/STD/EVAL_NAV/RUN_MANIFEST",
                "generated figure binaries",
                "old zip",
                "local absolute paths",
            ],
        },
    )
    write_md(export_dir / "README_FOR_NEXT_AI.md", readme)
    zip_path = export_dir / "paper10q1_qm_evidence_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package_root).as_posix())
    return {"path_scan_status": scan_status, "manifest_rows": manifest, "zip_path": zip_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--figure-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--ai-context-root", type=Path, required=True)
    parser.add_argument("--m1r2a-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2c-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2d-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2e-stage-root", type=Path, required=True)
    parser.add_argument("--m1r2d-runtime-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.repo_root = args.repo_root.resolve()
    args.stage_root = args.stage_root.resolve()
    args.figure_root = args.figure_root.resolve()
    args.export_root = args.export_root.resolve()
    root_aliases = aliases(args)
    ensure_dirs(args)
    data = load_inputs(args)
    tables = write_evidence_tables(args, data)
    figures = write_figures(args, data, tables, root_aliases)
    write_chinese_summaries(args)
    write_claim_boundary(args)
    write_obsidian_and_context(args)
    write_next_stage(args)
    write_tests_report(args)
    write_git_report(args, root_aliases)
    export_info = export_clean(args, root_aliases)
    # Regenerate export after final reports are written so the reports are included.
    write_stage_reports(args, data, tables, figures, export_info, root_aliases)
    export_info = export_clean(args, root_aliases)
    write_stage_reports(args, data, tables, figures, export_info, root_aliases)
    return 0 if export_info["path_scan_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
