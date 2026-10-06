"""Protocol v2 Canonical tables, explicit failures and frozen v1 comparisons.

Only sealed evaluation rows are consumed; this module opens no raw reference.
Original table headers precede appended protocol and inference fields.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path

import numpy as np

from ..canonical541 import offline_eval_aggregate as canonical
from ..canonical541.ablation_registry import ABLATION_METHODS, FULL_ALIAS
from ..publication.derived_tables import BOOT_N, BOOT_SEED, TIE_EPS, wilcoxon_signed_rank_p
from ..manifest import sha256_file
from .evaluation import ALGORITHM_FAILURE, _resolve, _write_json

PAIRS = canonical.PAIRWISE_DEFINITIONS + (
    ("A04_vs_F03", "A04", "F03"), ("A04_vs_F02", "A04", "F02"),
    ("F04_vs_F02", "F04", "F02"), ("F04_vs_F01", "F04", "F01"),
    ("A04_vs_F01", "A04", "F01"),
)
PRIMARY_METRICS = ("horizontal_rmse_m", "yaw_rmse_deg", "yaw_p95_absolute_deg")
SECONDARY_METRICS = ("up_rmse_m", "position_3d_rmse_m")
AGGREGATE_FILES = (
    "UNIQUE_METHOD_SUMMARY.csv", "LOGICAL_METHOD_SUMMARY.csv", "CASE_SUMMARY.csv",
    "DEGRADATION_TYPE_SUMMARY.csv", "FAMILY_SUMMARY.csv", "PAIRWISE_CASE_LEVEL.csv",
    "PAIRWISE_SUMMARY.csv", "SEED_SUMMARY.csv", "RECOVERY_SUMMARY.csv",
    "UNCERTAINTY_CALIBRATION_SUMMARY.csv", "MODULE_ACTION_SUMMARY.csv",
    "RUNTIME_SUMMARY.csv", "METRIC_COVERAGE_REPORT.csv",
    "FINAL_EVALUATION_SUMMARY.json", "EVALUATION_AND_AGGREGATE_STATUS.json",
)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_csv(path, rows, headers=()):
    rows = [_json_safe(dict(row)) for row in rows]
    fields = list(headers)
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True, ensure_ascii=False) if isinstance(v, (list, dict))
                             else v for k, v in row.items()})


def finite_stats(delta, *, n_boot=BOOT_N, seed=BOOT_SEED):
    """Canonical paired bootstrap, with explicit mean and median CI targets."""
    values = np.asarray(delta, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Finite paired statistics reject nonfinite supplied deltas")
    if not len(values):
        return {"paired_sample_count": 0, "mean_delta_candidate_minus_reference": None,
                "median_delta_candidate_minus_reference": None, "mean_ci95_low": None,
                "mean_ci95_high": None, "median_ci95_low": None, "median_ci95_high": None,
                "wilcoxon_p": None, "win_count": 0, "tie_count": 0, "loss_count": 0,
                "win_rate": None, "bootstrap_n": n_boot, "bootstrap_seed": seed}
    if n_boot <= 0:
        raise ValueError("Positive preregistered bootstrap sample count required")
    rng = np.random.default_rng(seed)
    mean_samples, median_samples = [], []
    for start in range(0, n_boot, 256):
        samples = values[rng.integers(0, len(values), size=(min(256, n_boot-start), len(values)))]
        mean_samples.extend(samples.mean(axis=1))
        median_samples.extend(np.median(samples, axis=1))
    ml, mh = np.percentile(mean_samples, [2.5, 97.5])
    dl, dh = np.percentile(median_samples, [2.5, 97.5])
    return _json_safe({"paired_sample_count": len(values),
        "mean_delta_candidate_minus_reference": float(values.mean()),
        "median_delta_candidate_minus_reference": float(np.median(values)),
        "std_delta": float(values.std(ddof=0)), "p10_delta": float(np.percentile(values, 10)),
        "p90_delta": float(np.percentile(values, 90)), "mean_ci95_low": float(ml),
        "mean_ci95_high": float(mh), "median_ci95_low": float(dl), "median_ci95_high": float(dh),
        "wilcoxon_p": wilcoxon_signed_rank_p(values), "wilcoxon_zero_policy": "wilcox; abs(delta)>1e-12",
        "wilcoxon_approximation": "two-sided normal; tie and continuity correction; unavailable nonzero n<10",
        "win_count": int(np.sum(values < -TIE_EPS)), "tie_count": int(np.sum(np.abs(values) <= TIE_EPS)),
        "loss_count": int(np.sum(values > TIE_EPS)), "win_rate": float(np.mean(values < -TIE_EPS)),
        "bootstrap_n": n_boot, "bootstrap_seed": seed,
        "bootstrap_policy": "paired cases; percentile 95%; default_rng PCG64; mean and median explicitly separated",
        "delta_definition": "candidate_minus_reference; negative_is_better"})


def _state(row):
    if row is None:
        return "TECHNICAL_MISSING"
    if row.get("solver_terminal_status", row.get("terminal_status")) == ALGORITHM_FAILURE:
        return "ALGORITHM_FAILURE"
    if row.get("evaluation_status") == "COMPLETED":
        return "SUCCESS"
    if row.get("evaluation_status") == "EVALUATION_SUSPECT":
        return "EVALUATION_SUSPECT"
    return "TECHNICAL_MISSING"


def pairwise_tables(logical, *, pairs=PAIRS, metrics=canonical.PAIRWISE_METRICS,
                    n_boot=BOOT_N, seed=BOOT_SEED):
    index = {(str(row["case_id"]), str(row["method_id"])): row for row in logical}
    if len(index) != len(logical):
        raise ValueError("Duplicate case/method in pairwise input")
    case_ids = sorted({key[0] for key in index})
    case_rows, failure_cases = [], []
    for comparison, candidate_id, reference_id in pairs:
        for case_id in case_ids:
            candidate, reference = index.get((case_id, candidate_id)), index.get((case_id, reference_id))
            meta = candidate or reference or {}
            cs, rs = _state(candidate), _state(reference)
            for metric in metrics:
                cv = canonical._float((candidate or {}).get(metric))
                rv = canonical._float((reference or {}).get(metric))
                identity = {"comparison": comparison, "candidate_method_id": candidate_id,
                    "reference_method_id": reference_id, "metric_name": metric, "case_id": case_id,
                    "degradation_id": meta.get("degradation_id"), "case_family": meta.get("case_family"),
                    "seed_id": meta.get("seed_id")}
                result, delta = "TECHNICAL_MISSING", None
                if "EVALUATION_SUSPECT" in (cs, rs):
                    result = "EVALUATION_SUSPECT"
                elif "TECHNICAL_MISSING" in (cs, rs):
                    pass
                elif cs == rs == "ALGORITHM_FAILURE":
                    result = "BOTH_FAILURE_TIE"
                elif cs == "ALGORITHM_FAILURE":
                    result = "CANDIDATE_LOSS_ALGORITHM_FAILURE"
                elif rs == "ALGORITHM_FAILURE":
                    result = "CANDIDATE_WIN_REFERENCE_FAILURE"
                elif cv is None or rv is None:
                    result = "FINITE_METRIC_UNAVAILABLE"
                else:
                    delta = cv-rv
                    result = "FINITE_WIN" if delta < -TIE_EPS else "FINITE_LOSS" if delta > TIE_EPS else "FINITE_TIE"
                    case_rows.append({**identity, "candidate_value": cv, "reference_value": rv,
                        "delta_candidate_minus_reference": delta,
                        "relative_change_percent": delta/abs(rv)*100 if rv else None,
                        "candidate_better": delta < -TIE_EPS, "tie": abs(delta) <= TIE_EPS})
                failure_cases.append({**identity, "candidate_state": cs, "reference_state": rs,
                    "candidate_value": cv if cs == "SUCCESS" else None,
                    "reference_value": rv if rs == "SUCCESS" else None,
                    "delta_candidate_minus_reference": delta, "pair_status": result,
                    "candidate_algorithm_failure": cs == "ALGORITHM_FAILURE",
                    "reference_algorithm_failure": rs == "ALGORITHM_FAILURE"})
    grouped = defaultdict(list)
    for row in failure_cases:
        grouped[(row["comparison"], row["metric_name"], "overall", "ALL")].append(row)
        grouped[(row["comparison"], row["metric_name"], "family", str(row["case_family"]))].append(row)
    summary, failure_summary = [], []
    for key in sorted(grouped):
        comparison, metric, scope, family = key
        group = grouped[key]
        finite = [r for r in group if r["pair_status"].startswith("FINITE_") and r["pair_status"] != "FINITE_METRIC_UNAVAILABLE"]
        deltas = [r["delta_candidate_minus_reference"] for r in finite]
        stats = finite_stats(deltas, n_boot=n_boot, seed=seed)
        identity = {"comparison": comparison, "metric_name": metric, "scope": scope, "family": family}
        by_type = defaultdict(list)
        for row in finite:
            by_type[row["degradation_id"]].append(row["delta_candidate_minus_reference"])
        consistencies = [max(sum(d < -TIE_EPS for d in ds), sum(d > TIE_EPS for d in ds),
                            sum(abs(d) <= TIE_EPS for d in ds))/len(ds) for ds in by_type.values()]
        relative = [r["delta_candidate_minus_reference"]/abs(r["reference_value"])*100
                    for r in finite if r["reference_value"]]
        worst = finite[int(np.argmax(deltas))] if deltas else None
        best = finite[int(np.argmin(deltas))] if deltas else None
        summary.append({**identity, **stats,
            "mean_relative_change_percent": float(np.mean(relative)) if relative else None,
            "median_relative_change_percent": float(np.median(relative)) if relative else None,
            "seed_direction_consistency": float(np.mean(consistencies)) if consistencies else None,
            "worst_negative_case": worst["case_id"] if worst else None,
            "best_positive_case": best["case_id"] if best else None,
            "total_case_count": len(group), "finite_metric_statistics_only": True})
        counts = Counter(r["pair_status"] for r in group)
        wins = counts["FINITE_WIN"] + counts["CANDIDATE_WIN_REFERENCE_FAILURE"]
        losses = counts["FINITE_LOSS"] + counts["CANDIDATE_LOSS_ALGORITHM_FAILURE"]
        ties = counts["FINITE_TIE"] + counts["BOTH_FAILURE_TIE"]
        comparable = wins+losses+ties
        failure_summary.append({**identity, "total_case_count": len(group),
            "failure_aware_comparable_count": comparable, "failure_aware_win_count": wins,
            "failure_aware_loss_count": losses, "failure_aware_tie_count": ties,
            "failure_aware_win_rate": wins/comparable if comparable else None,
            "failure_aware_win_rate_denominator": comparable,
            "all_registered_case_win_rate_sensitivity": wins/len(group),
            "all_registered_case_denominator": len(group),
            "both_algorithm_failure_count": counts["BOTH_FAILURE_TIE"],
            "candidate_algorithm_failure_count": sum(r["candidate_algorithm_failure"] for r in group),
            "reference_algorithm_failure_count": sum(r["reference_algorithm_failure"] for r in group),
            "technical_missing_count": counts["TECHNICAL_MISSING"],
            "evaluation_suspect_count": counts["EVALUATION_SUSPECT"],
            "finite_metric_unavailable_count": counts["FINITE_METRIC_UNAVAILABLE"],
            "finite_paired_count": len(finite), "finite_win_rate": stats["win_rate"],
            "denominator_policy": "comparable terminals include algorithm failures and double-failure ties; technical/missing excluded and counted; all-registered sensitivity separate"})
    seed_groups = defaultdict(list)
    for row in case_rows:
        seed_groups[(str(row["degradation_id"]), row["comparison"], row["metric_name"])].append(row)
    seed_rows = []
    for (degradation, comparison, metric), group in sorted(seed_groups.items()):
        delta = np.asarray([r["delta_candidate_minus_reference"] for r in group], float)
        positive, negative = int(np.sum(delta > TIE_EPS)), int(np.sum(delta < -TIE_EPS))
        ties = len(delta)-positive-negative
        seed_rows.append({"degradation_id": degradation, "comparison": comparison, "metric_name": metric,
            "valid_seed_count": len(delta), "positive_delta_count": positive,
            "negative_delta_count": negative, "tie_count": ties,
            "direction_consistency_ratio": max(positive, negative, ties)/len(delta),
            "mean_paired_delta": float(delta.mean()), "median_paired_delta": float(np.median(delta)),
            "std_paired_delta": float(delta.std()), "min_paired_delta": float(delta.min()),
            "max_paired_delta": float(delta.max()), "delta_definition": "candidate_minus_reference; negative_is_better"})
    return case_rows, summary, seed_rows, failure_cases, failure_summary


def logical_rows(unique):
    """Canonical four full methods plus nine internal-ablation rows."""
    rows = []
    by_case = defaultdict(dict)
    for row in unique:
        if row["method_id"] in by_case[row["case_id"]]:
            raise ValueError("Duplicate unique method in case")
        by_case[row["case_id"]][row["method_id"]] = row
    profiles = [(f"F{i:02d}", None) for i in range(1, 5)] + [(m.method_id, m.effective_profile) for m in ABLATION_METHODS]
    for method, profile in profiles:
        source_method = FULL_ALIAS.get(method, method)
        for case_id in sorted(by_case):
            source = by_case[case_id].get(source_method)
            if source is None:
                raise ValueError("Missing method for logical registry: " + source_method)
            row = dict(source)
            row.update(method_id=method, logical_id=("FULL_" if method.startswith("F") else "ABLATION_")+method+"_"+case_id,
                       logical_order=len(rows), execution_alias=method in FULL_ALIAS,
                       alias_of="FULL_"+source_method+"_"+case_id if method in FULL_ALIAS else "",
                       matrix="full_algorithm" if method.startswith("F") else "internal_ablation",
                       role="logical_alias" if method in FULL_ALIAS else "logical_result")
            if profile is not None:
                row["effective_configuration_id"] = profile
            rows.append(row)
    return rows


def v1_v2_comparison(v1_rows, v2_rows, *, n_boot=BOOT_N, seed=BOOT_SEED, v1_summary=None, v2_summary=None):
    """Full 541-case v1 and v2 finite pairs, preserving incomplete comparisons."""
    output = []
    old = v1_summary if v1_summary is not None else pairwise_tables(v1_rows, n_boot=n_boot, seed=seed)[1]
    old_index = {(r["comparison"], r["metric_name"], r["scope"], r["family"]): r for r in old}
    new = v2_summary if v2_summary is not None else pairwise_tables(v2_rows, n_boot=n_boot, seed=seed)[1]
    for row in new:
        if row["scope"] != "overall" or row["metric_name"] not in PRIMARY_METRICS + SECONDARY_METRICS:
            continue
        key = (row["comparison"], row["metric_name"], row["scope"], row["family"])
        previous = old_index.get(key, {})
        a, b = previous.get("median_delta_candidate_minus_reference"), row.get("median_delta_candidate_minus_reference")
        status = "INCOMPLETE"
        if a is not None and b is not None:
            sign_a = -1 if a < -TIE_EPS else 1 if a > TIE_EPS else 0
            sign_b = -1 if b < -TIE_EPS else 1 if b > TIE_EPS else 0
            status = "MAINTAINED" if sign_a == sign_b and sign_a != 0 else "FLIPPED"
        win_status = "INCOMPLETE"
        wa, wb = previous.get("win_rate"), row.get("win_rate")
        if wa is not None and wb is not None:
            win_status = "MAINTAINED" if (wa-.5)*(wb-.5) > 0 else "FLIPPED"
        complete = previous.get("paired_sample_count") == row["paired_sample_count"] == 541
        output.append({"comparison": row["comparison"], "metric_name": row["metric_name"],
            "metric_role": "primary" if row["metric_name"] in PRIMARY_METRICS else "secondary",
            "v1_protocol": "Canonical_541_v1", "v2_protocol": "Canonical_541_protocol_v2_CAL",
            "v1_finite_paired_count": previous.get("paired_sample_count", 0),
            "v2_finite_paired_count": row["paired_sample_count"],
            "v1_median_delta": a, "v2_median_delta": b,
            "v1_win_rate": previous.get("win_rate"), "v2_win_rate": row.get("win_rate"),
            "median_direction_status": status,
            "win_direction_status": win_status,
            "classification": "INCOMPLETE" if not complete else "MAINTAINED" if status == win_status == "MAINTAINED" else "FLIPPED",
            "v1_mean_ci95_low": previous.get("mean_ci95_low"), "v1_mean_ci95_high": previous.get("mean_ci95_high"),
            "v2_mean_ci95_low": row.get("mean_ci95_low"), "v2_mean_ci95_high": row.get("mean_ci95_high"),
            "v1_median_ci95_low": previous.get("median_ci95_low"), "v1_median_ci95_high": previous.get("median_ci95_high"),
            "v2_median_ci95_low": row.get("median_ci95_low"), "v2_median_ci95_high": row.get("median_ci95_high"),
            "full_case_comparison_complete": complete})
    return output


def _headers(v1_root, relative):
    path = Path(v1_root) / relative
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _numeric_fields(rows):
    # Count/runtime are excluded from Canonical IDENTITY_FIELDS. Retain them
    # explicitly for the runtime table; avoid dictionaries in numeric probing.
    provenance = {"synthetic_data_used", "semisynthetic_data_used", "trace_used_online", "controlled_degradation_applied",
                  "protocol_id", "dataset_id", "data_mode", "v3_baseline_median_m", "sequence_window_start_s",
                  "sequence_window_end_s", "code_commit", "config_hash", "evaluator_version", "evaluator_contract"}
    normalized = [{k: canonical._json_or_none(v) if isinstance(v, (dict, list)) else v for k, v in r.items() if k not in provenance} for r in rows]
    return canonical._numeric_fields(normalized)


def aggregate_all(evaluations, records, contract, reg, stage, code_commit, *, logical_registry=None, timing=None):
    """Write both evaluator versions, canonical headers and terminal summaries."""
    stage = Path(stage)
    case_pin = contract["sources"]["case_registry"]
    case_path = _resolve(case_pin["path"], reg)
    v1_root = case_path.parent.parent
    # Source identities belong to the preregistration, not guessed nearby rows.
    if sha256_file(case_path) != case_pin["sha256"]:
        raise ValueError("Frozen Canonical case registry changed")
    expected_cases = {r["case_id"] for r in _read_csv(case_path)}
    v1_path = v1_root / "12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv"
    v1_rows = _read_csv(v1_path)
    if len(v1_rows) != 7033 or len({r["case_id"] for r in v1_rows}) != 541:
        raise ValueError("Full v1 logical evidence is unavailable")
    v1_pin = contract["sources"]["logical_evaluation_results"]
    if _resolve(v1_pin["path"], reg) != v1_path or sha256_file(v1_path) != v1_pin["sha256"]:
        raise ValueError("Frozen v1 full evaluation source changed")
    v1_summary = pairwise_tables(v1_rows)[1]
    if len(records) != 5973:
        raise ValueError("All 5951 matrix plus 22 extra sequence terminals required")
    all_statuses = []
    for version in ("v3", "v2"):
        current = [dict(r) for r in evaluations if r["evaluator_version"] == version]
        unique = sorted([r for r in current if r.get("dataset_id", "BY2") == "BY2"], key=lambda r: str(r["run_id"]))
        if len(unique) != 5951 or {r["case_id"] for r in unique} != expected_cases:
            raise ValueError("Full v2 BY2 matrix terminal coverage differs from preregistration")
        if len({(r["case_id"], r["effective_configuration_id"]) for r in unique}) != 5951:
            raise ValueError("Duplicate v2 case/configuration identity")
        logical = canonical._logical_rows(logical_registry, unique) if logical_registry is not None else logical_rows(unique)
        if len(logical) != 7033:
            raise ValueError("Canonical logical alias coverage differs")
        evaluation_root = stage / "12_OFFLINE_EVALUATION" / version
        aggregate_root = stage / "13_AGGREGATE" / version
        evaluation_root.mkdir(parents=True, exist_ok=True)
        aggregate_root.mkdir(parents=True, exist_ok=False)
        for name, rows in (("UNIQUE_EVALUATION_RESULTS.csv", unique), ("LOGICAL_EVALUATION_RESULTS.csv", logical)):
            write_csv(evaluation_root / name, rows, _headers(v1_root, "12_OFFLINE_EVALUATION/"+name))
        failures = [r for r in unique if r["evaluation_status"] != "COMPLETED"]
        write_csv(evaluation_root / "EVALUATION_FAILURES.csv", failures)
        numeric_unique, numeric_logical = _numeric_fields(unique), _numeric_fields(logical)
        tables = {}
        for filename, rows, groups, metrics in (
            ("UNIQUE_METHOD_SUMMARY.csv", unique, ("method_id", "effective_configuration_id"), numeric_unique),
            ("LOGICAL_METHOD_SUMMARY.csv", logical, ("method_id", "effective_configuration_id"), numeric_logical),
            ("CASE_SUMMARY.csv", logical, ("case_id",), numeric_logical),
            ("DEGRADATION_TYPE_SUMMARY.csv", logical, ("degradation_id", "method_id"), numeric_logical),
            ("FAMILY_SUMMARY.csv", logical, ("case_family", "method_id"), numeric_logical)):
            tables[filename] = canonical._summary_rows(rows, groups, metrics)
        pc, ps, ss, fc, fs = pairwise_tables(logical)
        tables.update({"PAIRWISE_CASE_LEVEL.csv": pc, "PAIRWISE_SUMMARY.csv": ps, "SEED_SUMMARY.csv": ss,
                       "FAILURE_AWARE_PAIRWISE_CASE_LEVEL.csv": fc, "FAILURE_AWARE_PAIRWISE_SUMMARY.csv": fs})
        recovery = [key for key in numeric_logical if key.startswith(("pre_", "during_", "post_", "fault_window_")) or key == "recovery_time_sec"]
        tables["RECOVERY_SUMMARY.csv"] = canonical._summary_rows([r for r in logical if r.get("degradation_id") in ("D58", "D60")], ("degradation_id", "method_id"), recovery)
        uncertainty = [k for k in numeric_logical if any(s in k for s in ("coverage_1sigma", "coverage_2sigma", "coverage_3sigma", "z_rmse", "calibration_ratio", "abs_error_sigma_pearson", "abs_error_sigma_spearman", "diagonal_normalized_squared_error"))]
        tables["UNCERTAINTY_CALIBRATION_SUMMARY.csv"] = []
        for dimension in ("method_id", "case_family", "degradation_id", "seed_id"):
            for row in canonical._summary_rows(logical, (dimension,), uncertainty):
                row.update(group_dimension=dimension, group_value=row.pop(dimension))
                tables["UNCERTAINTY_CALIBRATION_SUMMARY.csv"].append(row)
        modules = [k for k in numeric_logical if k in canonical.MODULE_SCALARS or k == "source_aware_touch_rate"]
        tables["MODULE_ACTION_SUMMARY.csv"] = canonical._summary_rows(logical, ("method_id", "case_family"), modules)
        tables["RUNTIME_SUMMARY.csv"] = []
        for groups in (("method_id",), ("case_family",), ("method_id", "case_family")):
            tables["RUNTIME_SUMMARY.csv"].extend(canonical._summary_rows(unique, groups, ("solver_runtime_seconds", "evaluation_runtime_seconds")))
        tables["RUNTIME_SUMMARY.csv"].append({"method_id": "ALL", "case_family": "ALL", "metric_name": "total_wall_time_seconds", "count": len(records), "mean": (timing or {}).get("total_wall_time_seconds"), **(timing or {})})
        tables["METRIC_COVERAGE_REPORT.csv"] = canonical._coverage_report(unique)
        counts = Counter((r.get("case_family"), r.get("degradation_type_id", r.get("degradation_id")), r["method_id"], r["terminal_status"]) for r in records if r.get("dataset_id") == "BY2")
        tables["FAILURE_COUNTS_BY_FAMILY_CONFIG.csv"] = [{"case_family": f, "degradation_id": d, "method_id": m, "terminal_status": s, "run_count": n} for (f, d, m, s), n in sorted(counts.items(), key=str)]
        yaw_counts = Counter((r.get("case_family"), r.get("degradation_type_id", r.get("degradation_id"))) for r in records if r["terminal_status"] == ALGORITHM_FAILURE)
        family_keys = {(r.get("case_family"), r.get("degradation_type_id", r.get("degradation_id"))) for r in records if r.get("dataset_id") == "BY2"}
        tables["ALL_YAW_REJECTED_BY_FAMILY.csv"] = [{"case_family": f, "degradation_id": d, "run_count": yaw_counts[(f, d)]} for f, d in sorted(family_keys, key=str)]
        tables["SEQUENCE_CONSISTENCY_EVALUATION.csv"] = [r for r in current if r.get("dataset_id") != "BY2" or r["case_id"] == "C00_clean_normal"]
        tables["C00_FULL_ABLATION_ANCHORS.csv"] = [r for r in unique if r["case_id"] == "C00_clean_normal"]
        tables["V1_V2_PAIRWISE_COMPARISON.csv"] = v1_v2_comparison(v1_rows, logical, v1_summary=v1_summary, v2_summary=ps)
        tables["KEY_PAIRWISE_SUMMARY.csv"] = [r for r in ps if r["scope"] == "overall"]
        for filename, rows in tables.items():
            old_path = v1_root / "13_AGGREGATE" / filename
            headers = _headers(v1_root, "13_AGGREGATE/"+filename) if old_path.is_file() else []
            write_csv(aggregate_root / filename, rows, headers)
        status = {"terminal_status": "PASS_CANONICAL541_V2_AGGREGATED_WITH_EXPLICIT_TERMINALS",
            "protocol_id": contract.get("protocol_id"), "evaluator_version": version,
            "code_commit": code_commit, "unique_evaluated": len(unique), "logical_evaluated": len(logical),
            "unique_completed_evaluations": sum(r["evaluation_status"] == "COMPLETED" for r in unique),
            "evaluation_failures": sum(bool(r.get("technical_failure")) for r in unique),
            "algorithm_failure_count": sum(bool(r.get("algorithm_failure")) for r in unique),
            "evaluation_status_counts": dict(Counter(r["evaluation_status"] for r in unique)),
            "aggregate_completed": True, "plotting_executed": False,
            "v1_logical_table_sha256": sha256_file(v1_path), "reference_is_independent_ground_truth": False,
            "synthetic_data_used": False, "semisynthetic_data_used": False, "trace_used_online": False,
            "full_covariance_consistency": "UNAVAILABLE", "timing": timing or {}}
        for name in ("FINAL_EVALUATION_SUMMARY.json", "EVALUATION_AND_AGGREGATE_STATUS.json"):
            _write_json(aggregate_root / name, status)
        _write_json(evaluation_root / "EVALUATION_STATUS.json", status)
        (evaluation_root / "FIELD_DEFINITIONS.md").write_text(
            "# Canonical-541 protocol v2 fields\n\n"
            "Original Canonical field names, units and column order are retained. Protocol, evaluator version and terminal class are appended. "
            "v3 is primary; v2 is parallel. Delta is candidate minus reference; negative is better. "
            "Finite statistics include only successful finite metric pairs. Algorithm failures are method failures and are counted in failure-aware results. "
            "Both failures tie; one failure loses. Primary failure-aware denominator includes comparable terminal pairs, including algorithm failures; technical, suspect and unsupported pairs are excluded and counted explicitly. All-registered-case sensitivity is separate. "
            "Mean and median percentile 95% bootstrap intervals use 10000 paired resamples, PCG64 seed 20260904. "
            "Wilcoxon uses the frozen Canonical derived-table two-sided normal approximation with tie and continuity correction, drops absolute deltas <=1e-12 and is unavailable below 10 nonzero samples. "
            "Velocity truth is unsupported. STD statistics are diagonal diagnostics, never full-covariance NEES; v3 position STD is untransported. "
            "Recovery times remain unavailable without a frozen recovery rule. No synthetic observations or fabricated failed-run RMSEs are inserted.\n",
            encoding="utf-8")
        all_statuses.append(status)
    return all_statuses
