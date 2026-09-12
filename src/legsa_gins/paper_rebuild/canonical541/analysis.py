"""Descriptive canonical541 aggregation, paired deltas and recovery metrics."""

from __future__ import annotations

import hashlib
import csv
import gzip
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


METRICS = (
    "horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m",
    "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg",
)
FULL_PAIRS = (("F04", "F03"), ("F03", "F02"), ("F02", "F01"))
ABLATION_PAIRS = (("A01", "A03"), ("A01", "A04"), ("A01", "A05"),
                  ("A01", "A06"), ("A01", "A07"), ("A08", "A02"), ("A09", "A02"))
BOOTSTRAP_SEED = 2026071801
BOOTSTRAP_REPLICATES = 10000


class AnalysisError(ValueError):
    pass


def strict_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}: return True
    if normalized in {"0", "false", "no", ""}: return False
    raise AnalysisError(f"invalid boolean token: {value!r}")


def _analysis_samples(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Use every independent seed once and one value per deterministic execution."""

    independent = [row for row in rows if strict_bool(row.get("independent_realization", False))]
    deterministic: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if strict_bool(row.get("independent_realization", False)):
            continue
        deterministic.setdefault(str(row.get("run_id", row.get("case_id"))), row)
    return [*independent, *deterministic.values()]


def _finite_values(rows: Iterable[Mapping[str, Any]], field: str) -> np.ndarray:
    values = []
    for row in rows:
        if row.get("evaluable") is not True: continue
        value = float(row[field])
        if not math.isfinite(value): raise AnalysisError(f"non-finite evaluable metric: {field}")
        values.append(value)
    return np.asarray(values, dtype=float)


def descriptive(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return {"n": 0, "mean": None, "median": None, "std": None, "p05": None, "p95": None, "worst": None}
    return {"n": int(array.size), "mean": float(np.mean(array)), "median": float(np.median(array)),
            "std": float(np.std(array)), "p05": float(np.quantile(array, 0.05)),
            "p95": float(np.quantile(array, 0.95)), "worst": float(np.max(array))}


def aggregate_rows(rows: Iterable[Mapping[str, Any]], group_fields: Sequence[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows: groups[tuple(str(row[field]) for field in group_fields)].append(row)
    output: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        samples = _analysis_samples(group)
        independent_count = sum(strict_bool(row.get("independent_realization", False)) for row in group)
        deterministic_rows = [row for row in group if not strict_bool(row.get("independent_realization", False))]
        deterministic_unique = len({str(row.get("run_id", row.get("case_id"))) for row in deterministic_rows})
        base = dict(zip(group_fields, key)); base.update(
            logical_row_count=len(group), evaluable_count=sum(row.get("evaluable") is True for row in group),
            failure_count=sum(row.get("evaluable") is not True for row in group),
            evaluable_rate=sum(row.get("evaluable") is True for row in group) / len(group),
            unique_execution_count=len({str(row.get("run_id")) for row in group}),
            independent_realization_count=independent_count,
            deterministic_logical_count=len(deterministic_rows),
            deterministic_unique_execution_count=deterministic_unique,
            deterministic_alias_count=len(deterministic_rows) - deterministic_unique,
            descriptive_sample_count=len(samples),
        )
        for metric in METRICS:
            for stat, value in descriptive(_finite_values(samples, metric)).items(): base[f"{metric}_{stat}"] = value
        output.append(base)
    return output


def paired_deltas(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items = tuple(rows); by_key = {(str(row["method_id"]), str(row["case_id"])): row for row in items}
    output: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for left, right in (*FULL_PAIRS, *ABLATION_PAIRS):
        pair_rows = []
        for (method, case_id), left_row in by_key.items():
            if method != left or (right, case_id) not in by_key: continue
            right_row = by_key[(right, case_id)]
            if left_row.get("evaluable") is not True or right_row.get("evaluable") is not True: continue
            for metric in METRICS:
                pair_rows.append({
                    "comparison": f"{left}_vs_{right}", "left": left, "right": right,
                    "case_id": case_id, "degradation_type_id": left_row.get("degradation_type_id"),
                    "case_family": left_row.get("case_family"), "seed_index": left_row.get("seed_index"),
                    "independent_realization": strict_bool(left_row.get("independent_realization", False)),
                    "left_run_id": left_row.get("run_id"), "right_run_id": right_row.get("run_id"),
                    "metric": metric, "paired_delta_left_minus_right": float(left_row[metric]) - float(right_row[metric]),
                })
        output.extend(pair_rows)
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in pair_rows:
            grouped[(str(row["degradation_type_id"]), str(row["case_family"]), str(row["metric"]))].append(row)
        for (type_id, family, metric), group in sorted(grouped.items()):
            independent = [row for row in group if strict_bool(row["independent_realization"])]
            deterministic: dict[tuple[str, str], dict[str, Any]] = {}
            for row in group:
                if not strict_bool(row["independent_realization"]):
                    deterministic.setdefault((str(row["left_run_id"]), str(row["right_run_id"])), row)
            samples = independent or list(deterministic.values())
            values = [float(row["paired_delta_left_minus_right"]) for row in samples]
            stats = descriptive(values); stats.update(
                comparison=f"{left}_vs_{right}", degradation_type_id=type_id,
                case_family=family, metric=metric, logical_pair_count=len(group),
                independent_realization_count=len(independent),
                deterministic_unique_count=len(deterministic),
                deterministic_logical_count=sum(not strict_bool(row["independent_realization"]) for row in group),
                deterministic_alias_count=(
                    sum(not strict_bool(row["independent_realization"]) for row in group) - len(deterministic)
                ),
                deterministic_unique_value=(values[0] if not independent and len(values) == 1 else None),
                helpful_count=sum(value < 0 for value in values), harmful_count=sum(value > 0 for value in values),
                neutral_count=sum(value == 0 for value in values),
                sign_consistency=(
                    max(sum(value < 0 for value in values), sum(value > 0 for value in values)) / len(values)
                    if independent and values else None
                ),
            ); summary.append(stats)
    return output, summary


def bootstrap_intervals(delta_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in delta_rows:
        if strict_bool(row.get("independent_realization", False)):
            groups[(str(row["comparison"]), str(row["degradation_type_id"]), str(row["metric"]))].append(float(row["paired_delta_left_minus_right"]))
    output = []
    for key, values in sorted(groups.items()):
        if len(values) < 5: continue
        # Each group gets a stable child seed independent of dictionary order.
        digest = hashlib.sha256("|".join(key).encode()).digest(); offset = int.from_bytes(digest[:8], "big")
        rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED + offset))
        array = np.asarray(values); samples = rng.choice(array, size=(BOOTSTRAP_REPLICATES, len(array)), replace=True).mean(axis=1)
        output.append({"comparison": key[0], "degradation_type_id": key[1], "metric": key[2],
                       "independent_seed_count": len(values), "replicates": BOOTSTRAP_REPLICATES,
                       "bootstrap_seed": BOOTSTRAP_SEED, "mean_delta": float(np.mean(array)),
                       "ci95_low": float(np.quantile(samples, 0.025)), "ci95_high": float(np.quantile(samples, 0.975)),
                       "interpretation": "controlled-seed descriptive uncertainty"})
    return output


def recovery_band(clean_absolute_errors: Sequence[float]) -> float:
    values = np.asarray(clean_absolute_errors, dtype=float)
    if values.size == 0 or not np.all(np.isfinite(values)): raise AnalysisError("clean recovery values invalid")
    median = float(np.median(values)); mad = float(np.median(np.abs(values - median)))
    return median + 3.0 * mad


def recovery_metrics(*, times: Sequence[float], errors: Sequence[float], degradation_interval: tuple[float, float],
                     recovery_interval: tuple[float, float], clean_absolute_errors: Sequence[float]) -> dict[str, Any]:
    t = np.asarray(times); e = np.asarray(errors); start, end = degradation_interval; rstart, rend = recovery_interval
    if t.shape != e.shape or not np.all(np.isfinite(t)) or not np.all(np.isfinite(e)): raise AnalysisError("recovery series invalid")
    pre = e[t < start]; during = e[(t >= start) & (t < end)]; post = e[(t >= rstart) & (t < rend)]
    band = recovery_band(clean_absolute_errors); within = np.flatnonzero((t >= rstart) & (t < rend) & (np.abs(e) <= band))
    return {"pre_median": float(np.median(pre)) if pre.size else None,
            "during_median": float(np.median(during)) if during.size else None,
            "post_median": float(np.median(post)) if post.size else None,
            "peak_error": float(np.max(np.abs(during))) if during.size else None,
            "time_to_return_s": float(t[within[0]] - rstart) if within.size else None,
            "recovery_jump": float(post[0] - during[-1]) if post.size and during.size else None,
            "recovery_band": band, "finite_throughout": True}


def method_clean_penalties(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items = tuple(rows)
    clean = {
        (str(row["matrix"]), str(row["method_id"])): row
        for row in items if row["case_id"] == "C00_clean_normal" and row.get("evaluable") is True
    }
    output = []
    for row in items:
        key = (str(row["matrix"]), str(row["method_id"])); anchor = clean.get(key)
        if row["case_id"] == "C00_clean_normal" or row.get("evaluable") is not True or anchor is None:
            continue
        for metric in METRICS:
            output.append({
                "matrix": key[0], "method_id": key[1], "case_id": row["case_id"],
                "degradation_type_id": row.get("degradation_type_id"),
                "case_family": row.get("case_family"), "seed_index": row.get("seed_index"),
                "independent_realization": strict_bool(row.get("independent_realization", False)),
                "metric": metric, "degraded_value": float(row[metric]),
                "clean_value": float(anchor[metric]),
                "penalty_degraded_minus_clean": float(row[metric]) - float(anchor[metric]),
            })
    return output


def worst_cases(rows: Iterable[Mapping[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("evaluable") is True:
            for metric in METRICS:
                groups[(str(row["matrix"]), str(row["method_id"]), metric)].append(row)
    output = []
    for (matrix, method, metric), group in sorted(groups.items()):
        for rank, row in enumerate(sorted(group, key=lambda item: float(item[metric]), reverse=True)[:limit], 1):
            output.append({
                "matrix": matrix, "method_id": method, "metric": metric, "rank": rank,
                "case_id": row["case_id"], "degradation_type_id": row.get("degradation_type_id"),
                "case_family": row.get("case_family"), "seed_index": row.get("seed_index"),
                "value": float(row[metric]), "run_id": row["run_id"],
            })
    return output


def _runtime_hashes(row: Mapping[str, Any]) -> tuple[str, str]:
    root = Path(str(row["output_root"]))
    nav = root / "KF_GINS_Navresult.nav"; std = root / "KF_GINS_STD.txt"
    if not nav.is_file() or not std.is_file():
        return "", ""
    from .provider_generator import sha256_file
    return sha256_file(nav), sha256_file(std)


def source_isolation_audit(logical_rows: Iterable[Mapping[str, Any]],
                           unique_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    from .ablation_registry import ABLATION_METHODS
    from .full_method_registry import FULL_METHODS
    profiles = {row.method_id: row for row in (*FULL_METHODS, *ABLATION_METHODS)}
    logical = tuple(logical_rows); unique = {str(row["run_id"]): row for row in unique_rows}
    clean = {(str(row["matrix"]), str(row["method_id"])): row
             for row in logical if row["case_id"] == "C00_clean_normal"}
    output = []
    for row in logical:
        type_id = str(row.get("degradation_type_id", ""))
        if not type_id.startswith("D"): continue
        number = int(type_id[1:]); method = str(row["method_id"])
        flags = profiles[method].flags
        invariant = False; rule = ""
        if number == 29:
            invariant, rule = True, "status_metadata_no_active_loader_invariant"
        elif number == 40:
            invariant, rule = True, "baseline_metadata_no_active_solver_path_invariant"
        elif 30 <= number <= 41 and not flags["dual_yaw"]:
            invariant, rule = True, "dual_yaw_nonconsumer_invariant"
        elif 42 <= number <= 45 and not flags["receiver_velocity"]:
            invariant, rule = True, "receiver_velocity_nonconsumer_invariant"
        elif 46 <= number <= 50 and not flags["raw_doppler"]:
            invariant, rule = True, "raw_doppler_nonconsumer_invariant"
        elif 51 <= number <= 52 and not flags["go2_rp"]:
            invariant, rule = True, "go2_rp_nonconsumer_invariant"
        elif 53 <= number <= 54 and not flags["go2_hv"]:
            invariant, rule = True, "go2_hv_nonconsumer_invariant"
        elif 55 <= number <= 56:
            invariant, rule = True, "metadata_no_active_loader_invariant"
        if not invariant: continue
        anchor = clean[(str(row["matrix"]), method)]
        current_unique = unique[str(row["run_id"])]; anchor_unique = unique[str(anchor["run_id"])]
        current_nav, current_std = _runtime_hashes(current_unique)
        clean_nav, clean_std = _runtime_hashes(anchor_unique)
        passed = bool(current_nav and current_std and current_nav == clean_nav and current_std == clean_std)
        output.append({
            "rule_id": rule, "case_id": row["case_id"], "degradation_type_id": type_id,
            "matrix": row["matrix"], "method_id": method, "run_id": row["run_id"],
            "clean_run_id": anchor["run_id"], "execution_alias_exact": row["run_id"] == anchor["run_id"],
            "nav_bit_identical": current_nav == clean_nav and bool(current_nav),
            "std_bit_identical": current_std == clean_std and bool(current_std),
            "passed": passed,
        })
    if not output or not all(row["passed"] for row in output):
        raise AnalysisError("FAIL_CANONICAL541_SOURCE_ISOLATION")
    return output


def mechanism_tables(logical_rows: Iterable[Mapping[str, Any]],
                     unique_rows: Iterable[Mapping[str, Any]],
                     provider_root: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    logical = tuple(logical_rows); unique = {str(row["run_id"]): row for row in unique_rows}
    providers = Path(provider_root).resolve(strict=True) / "FINALIZED"
    perturbations: dict[str, dict[str, list[float]]] = {}
    audit_only_perturbations: dict[str, dict[str, list[float]]] = {}
    for case_id in {str(row["case_id"]) for row in logical}:
        ledger = providers / case_id / "02_PROVIDERS/CASE_PERTURBATION_LEDGER.csv.gz"
        times: dict[str, dict[str, float]] = defaultdict(dict)
        audit_times: dict[str, dict[str, float]] = defaultdict(dict)
        if ledger.is_file():
            with gzip.open(ledger, "rt", encoding="utf-8-sig", newline="") as handle:
                for item in csv.DictReader(handle):
                    source = str(item["source"]); key = str(item["row_index"])
                    changed_fields = {value for value in str(item.get("changed_fields", "")).split(";") if value}
                    if case_id.startswith("D40_") and source == "dual_yaw":
                        if changed_fields != {"baseline_length_m"}:
                            raise AnalysisError(
                                f"D40 contains unexpected solver-visible changed fields: {sorted(changed_fields)}"
                            )
                        audit_times[source][key] = float(item["generated_time"])
                    else:
                        times[source][key] = float(item["generated_time"])
        perturbations[case_id] = {source: sorted(values.values()) for source, values in times.items()}
        audit_only_perturbations[case_id] = {
            source: sorted(values.values()) for source, values in audit_times.items()
        }
    proof_cache: dict[str, Mapping[str, Any]] = {}; trace_cache: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {}
    source_rows: list[dict[str, Any]] = []; scheme_rows: list[dict[str, Any]] = []
    provider_to_action = {
        "gnss_position": "receiver_position", "receiver_velocity": "receiver_velocity",
        "dual_yaw": "dual_antenna_yaw", "raw_doppler": "raw_doppler_velocity",
        "go2_rp": "go2_attitude_roll_pitch", "go2_hv": "go2_horizontal_velocity",
    }
    action_to_provider = {value: key for key, value in provider_to_action.items()}

    def is_perturbed(time_value: float, candidates: Sequence[float], tolerance: float = 1.0e-6) -> bool:
        if not candidates: return False
        values = np.asarray(candidates, dtype=float); index = int(np.searchsorted(values, time_value))
        return any(abs(time_value - float(values[position])) <= tolerance
                   for position in (max(0, index - 1), min(len(values) - 1, index)))

    def scale_stats(values: Sequence[float]) -> tuple[Any, Any, Any]:
        if not values: return None, None, None
        array = np.asarray(values, dtype=float)
        return float(np.median(array)), float(np.quantile(array, .95)), float(np.max(array))

    for row in logical:
        run_id = str(row["run_id"]); proof = proof_cache.get(run_id)
        if proof is None:
            runtime = Path(str(unique[run_id]["output_root"]))
            proof = json.loads((runtime / "CANONICAL541_EXECUTION_PROOF.json").read_text(encoding="utf-8"))
            proof_cache[run_id] = proof
            source_trace = runtime / "SOURCE_AWARE_WEIGHT_TRACE.csv"
            scheme_trace = runtime / "PORT_GNSS_UPDATE_TRACE.csv"
            terminal_status = str(proof.get("terminal_status", unique[run_id].get("terminal_status", "")))
            if terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
                # 严重退化下的 failure proof 是合法终态；缺失动作 trace 不是零动作，
                # 因此输出明确 not-evaluable 行，绝不把未知计数伪造成 0。
                source_trace_rows, scheme_trace_rows = [], []
            elif terminal_status == "COMPLETED_EVALUABLE":
                if not scheme_trace.is_file():
                    raise AnalysisError(f"Scheme-C action trace missing for evaluable run: {run_id}")
                with scheme_trace.open("r", encoding="utf-8-sig", newline="") as handle:
                    scheme_trace_rows = list(csv.DictReader(handle))
                if source_trace.is_file():
                    with source_trace.open("r", encoding="utf-8-sig", newline="") as handle:
                        source_trace_rows = list(csv.DictReader(handle))
                else: source_trace_rows = []
            else:
                raise AnalysisError(f"unresolved terminal status in mechanism analysis: {run_id}/{terminal_status}")
            trace_cache[run_id] = (source_trace_rows, scheme_trace_rows)
        if any(int(value) for value in proof.get("forbidden_counts", {}).values()):
            raise AnalysisError("out-of-scope mechanism count is nonzero")
        terminal_status = str(proof.get("terminal_status", unique[run_id].get("terminal_status", "")))
        if terminal_status == "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF":
            failure_type = str(proof.get("failure_type", unique[run_id].get("failure_type", "")))
            scheme_rows.append({
                "logical_id": row["logical_id"], "case_id": row["case_id"],
                "method_id": row["method_id"], "run_id": run_id,
                "attempt": None, "normal": None, "downweight": None,
                "reject": None, "accept": None,
                "perturbed_yaw_epoch_count": len(perturbations[str(row["case_id"])].get("dual_yaw", [])),
                "audit_only_yaw_epoch_count": len(audit_only_perturbations[str(row["case_id"])].get("dual_yaw", [])),
                "perturbed_action_count": None, "perturbed_normal": None,
                "perturbed_downweight": None, "perturbed_reject": None,
                "unperturbed_action_count": None, "join_tolerance_s": 1.0e-6,
                "action_partition_complete": False, "enabled": None,
                "mechanism_evaluable": False,
                "mechanism_status": "not_evaluable_algorithm_failure",
                "terminal_status": terminal_status, "failure_type": failure_type,
                "perturbation_path_status": (
                    "audit_only_no_active_path" if audit_only_perturbations[str(row["case_id"])].get("dual_yaw")
                    else "solver_visible_or_none"
                ),
            })
            for provider_source, action_source in sorted(provider_to_action.items()):
                source_rows.append({
                    "logical_id": row["logical_id"], "case_id": row["case_id"],
                    "method_id": row["method_id"], "run_id": run_id,
                    "source": provider_source, "runtime_source_id": action_source,
                    "perturbed_epoch_count": len(perturbations[str(row["case_id"])].get(provider_source, [])),
                    "audit_only_perturbed_epoch_count": len(audit_only_perturbations[str(row["case_id"])].get(provider_source, [])),
                    "evaluated_count": None, "perturbed_evaluated_count": None,
                    "unperturbed_evaluated_count": None,
                    "perturbed_R_scale_changed_count": None,
                    "unperturbed_R_scale_changed_count": None,
                    "perturbed_reject_count": None, "unperturbed_reject_count": None,
                    "perturbed_R_scale_p50": None, "perturbed_R_scale_p95": None,
                    "perturbed_R_scale_max": None, "unperturbed_R_scale_p50": None,
                    "unperturbed_R_scale_p95": None, "unperturbed_R_scale_max": None,
                    "join_tolerance_s": 1.0e-6, "perturbed_evaluation_coverage": None,
                    "epoch_partition_status": "not_evaluable_algorithm_failure",
                    "perturbation_path_status": (
                        "audit_only_no_active_path" if audit_only_perturbations[str(row["case_id"])].get(provider_source)
                        else "solver_visible_or_none"
                    ),
                    "source_aware_enabled": None, "mechanism_evaluable": False,
                    "mechanism_status": "not_evaluable_algorithm_failure",
                    "terminal_status": terminal_status, "failure_type": failure_type,
                })
            continue
        mechanisms = proof.get("mechanism_evidence") or {}; scheme = mechanisms.get("scheme_c") or {}
        source_trace_rows, scheme_trace_rows = trace_cache[run_id]
        yaw_actions = [item for item in scheme_trace_rows if item.get("yaw_mode") in {"NORMAL", "DOWNWEIGHT", "REJECT"}]
        mode_counts = {mode: sum(item.get("yaw_mode") == mode for item in yaw_actions)
                       for mode in ("NORMAL", "DOWNWEIGHT", "REJECT")}
        if scheme and (
            len(yaw_actions) != int(scheme.get("attempt", 0))
            or mode_counts["NORMAL"] != int(scheme.get("normal", 0))
            or mode_counts["DOWNWEIGHT"] != int(scheme.get("downweight", 0))
            or mode_counts["REJECT"] != int(scheme.get("reject", 0))
        ):
            raise AnalysisError(f"Scheme-C trace/manifest action mismatch: {run_id}")
        perturbed_yaw_times = perturbations[str(row["case_id"])].get("dual_yaw", [])
        audit_only_yaw_times = audit_only_perturbations[str(row["case_id"])].get("dual_yaw", [])
        perturbed_actions = [item for item in yaw_actions if is_perturbed(float(item["gnss_time"]), perturbed_yaw_times)]
        scheme_rows.append({
            "logical_id": row["logical_id"], "case_id": row["case_id"], "method_id": row["method_id"],
            "run_id": run_id, "attempt": len(yaw_actions),
            "normal": mode_counts["NORMAL"], "downweight": mode_counts["DOWNWEIGHT"],
            "reject": mode_counts["REJECT"], "accept": mode_counts["NORMAL"] + mode_counts["DOWNWEIGHT"],
            "perturbed_yaw_epoch_count": len(perturbed_yaw_times),
            "audit_only_yaw_epoch_count": len(audit_only_yaw_times),
            "perturbed_action_count": len(perturbed_actions),
            "perturbed_normal": sum(item["yaw_mode"] == "NORMAL" for item in perturbed_actions),
            "perturbed_downweight": sum(item["yaw_mode"] == "DOWNWEIGHT" for item in perturbed_actions),
            "perturbed_reject": sum(item["yaw_mode"] == "REJECT" for item in perturbed_actions),
            "unperturbed_action_count": len(yaw_actions) - len(perturbed_actions),
            "join_tolerance_s": 1.0e-6, "action_partition_complete": True,
            "enabled": bool(scheme.get("enabled", False)),
            "mechanism_evaluable": True, "mechanism_status": "complete",
            "terminal_status": terminal_status, "failure_type": "",
            "perturbation_path_status": (
                "audit_only_no_active_path" if audit_only_yaw_times and not perturbed_yaw_times
                else "solver_visible_or_none"
            ),
        })
        source = mechanisms.get("source_aware") or {}; enabled = bool(source.get("enabled", False))
        if enabled and len(source_trace_rows) != int(source.get("evaluations", -1)):
            raise AnalysisError(f"source-aware trace/evaluation count mismatch: {run_id}")
        trace_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
        for item in source_trace_rows: trace_by_source[str(item["source_id"])].append(item)
        unknown_source_ids = sorted(set(trace_by_source) - set(action_to_provider))
        if unknown_source_ids:
            raise AnalysisError(
                f"unknown source-aware runtime source_id for {run_id}: {unknown_source_ids}"
            )
        for action_source in sorted(set(trace_by_source) | {
            provider_to_action[name] for name in perturbations[str(row["case_id"])] if name in provider_to_action
        } | {
            provider_to_action[name] for name in audit_only_perturbations[str(row["case_id"])] if name in provider_to_action
        }):
            provider_source = action_to_provider[action_source]
            action_rows = trace_by_source.get(action_source, [])
            perturbed_times = perturbations[str(row["case_id"])].get(provider_source, [])
            audit_only_times = audit_only_perturbations[str(row["case_id"])].get(provider_source, [])
            partition = [is_perturbed(float(item["time"]), perturbed_times) for item in action_rows]
            perturbed_rows = [item for item, selected in zip(action_rows, partition) if selected]
            unperturbed_rows = [item for item, selected in zip(action_rows, partition) if not selected]
            perturbed_scales = [float(item["combined_R_scale"]) for item in perturbed_rows]
            unperturbed_scales = [float(item["combined_R_scale"]) for item in unperturbed_rows]
            pp50, pp95, pmax = scale_stats(perturbed_scales); up50, up95, umax = scale_stats(unperturbed_scales)
            source_rows.append({
                "logical_id": row["logical_id"], "case_id": row["case_id"], "method_id": row["method_id"],
                "run_id": run_id, "source": provider_source, "runtime_source_id": action_source,
                "perturbed_epoch_count": len(perturbed_times),
                "audit_only_perturbed_epoch_count": len(audit_only_times),
                "evaluated_count": len(action_rows), "perturbed_evaluated_count": len(perturbed_rows),
                "unperturbed_evaluated_count": len(unperturbed_rows),
                "perturbed_R_scale_changed_count": sum(abs(value - 1.0) > 1e-12 for value in perturbed_scales),
                "unperturbed_R_scale_changed_count": sum(abs(value - 1.0) > 1e-12 for value in unperturbed_scales),
                "perturbed_reject_count": sum(str(item.get("rejected", "0")) == "1" for item in perturbed_rows),
                "unperturbed_reject_count": sum(str(item.get("rejected", "0")) == "1" for item in unperturbed_rows),
                "perturbed_R_scale_p50": pp50, "perturbed_R_scale_p95": pp95, "perturbed_R_scale_max": pmax,
                "unperturbed_R_scale_p50": up50, "unperturbed_R_scale_p95": up95, "unperturbed_R_scale_max": umax,
                "join_tolerance_s": 1.0e-6,
                "perturbed_evaluation_coverage": len(perturbed_rows) / len(perturbed_times) if perturbed_times else None,
                "epoch_partition_status": "offline_trace_provider_time_join_complete",
                "perturbation_path_status": (
                    "audit_only_no_active_path" if audit_only_times and not perturbed_times
                    else "solver_visible_or_none"
                ),
                "source_aware_enabled": enabled,
                "mechanism_evaluable": True, "mechanism_status": "complete",
                "terminal_status": terminal_status, "failure_type": "",
            })
    return source_rows, scheme_rows


def _read_error_series(path: Path, column: str) -> tuple[np.ndarray, np.ndarray]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return (np.asarray([float(row["time"]) for row in rows]),
            np.abs(np.asarray([float(row[column]) for row in rows])))


def build_recovery_table(rows: Iterable[Mapping[str, Any]], evaluation_root: str | Path) -> list[dict[str, Any]]:
    from .seed_anchor import place_interval
    items = tuple(rows); evaluation = Path(evaluation_root).resolve(strict=True)
    clean = {(str(row["matrix"]), str(row["method_id"])): row for row in items
             if row["case_id"] == "C00_clean_normal" and row.get("evaluable") is True}
    columns = {"horizontal": "horizontal_err_m", "up": "err_u_m", "position_3d": "position_3d_err_m", "yaw": "yaw_err_deg"}
    output = []
    for row in items:
        type_id = str(row.get("degradation_type_id"));
        if type_id not in {"D58", "D60"}: continue
        if row.get("evaluable") is not True:
            duration = 10.0 if type_id == "D58" else 20.0
            interval = place_interval(float(row["anchor_time_s"]), duration)
            recovery = (interval[1], min(340.0, interval[1] + 20.0))
            for metric in columns:
                output.append({
                    "logical_id": row["logical_id"], "case_id": row["case_id"],
                    "method_id": row["method_id"], "run_id": row["run_id"],
                    "degradation_type_id": type_id, "metric": metric,
                    "evaluable": False, "finite_throughout": False,
                    "failure_type": row.get("failure_type"),
                    "degradation_start_s": interval[0], "degradation_end_s": interval[1],
                    "recovery_start_s": recovery[0], "recovery_end_s": recovery[1],
                    "pre_median": None, "during_median": None, "post_median": None,
                    "peak_error": None, "time_to_return_s": None,
                    "recovery_jump": None, "recovery_band": None,
                })
            continue
        anchor = clean.get((str(row["matrix"]), str(row["method_id"])))
        if anchor is None: continue
        duration = 10.0 if type_id == "D58" else 20.0
        interval = place_interval(float(row["anchor_time_s"]), duration)
        recovery = (interval[1], min(340.0, interval[1] + 20.0))
        for metric, column in columns.items():
            times, errors = _read_error_series(evaluation / str(row["run_id"]) / "error_series.csv.gz", column)
            _, clean_errors = _read_error_series(evaluation / str(anchor["run_id"]) / "error_series.csv.gz", column)
            result = recovery_metrics(times=times, errors=errors, degradation_interval=interval,
                                      recovery_interval=recovery, clean_absolute_errors=clean_errors)
            output.append({
                "logical_id": row["logical_id"], "case_id": row["case_id"], "method_id": row["method_id"],
                "run_id": row["run_id"], "degradation_type_id": type_id, "metric": metric,
                "degradation_start_s": interval[0], "degradation_end_s": interval[1],
                "recovery_start_s": recovery[0], "recovery_end_s": recovery[1], **result,
                "evaluable": True, "failure_type": "",
            })
    return output


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], *, gzip_output: bool = False,
               fallback_fields: Sequence[str] = ("status",)) -> str:
    items = [dict(row) for row in rows]
    fields = list(items[0]) if items else list(fallback_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    # gzip.open has no mtime keyword; use GzipFile for deterministic bytes.
    if gzip_output:
        import io
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(items)
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
                compressed.write(buffer.getvalue().encode("utf-8"))
    else:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
            writer.writeheader(); writer.writerows(items)
    os.replace(temporary, path)
    from .provider_generator import sha256_file
    return sha256_file(path)


def build_analysis(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = tuple(rows)
    if len(items) != 7033: raise AnalysisError("analysis requires all 7033 logical rows")
    full = [row for row in items if row["matrix"] == "full_algorithm"]
    ablation = [row for row in items if row["matrix"] == "internal_ablation"]
    if len(full) != 2164 or len(ablation) != 4869: raise AnalysisError("matrix split count mismatch")
    deltas, sign = paired_deltas(items)
    return {
        "full_method_summary": aggregate_rows(full, ("method_id",)),
        "full_family_summary": aggregate_rows(full, ("method_id", "case_family")),
        "full_type_summary": aggregate_rows(full, ("method_id", "degradation_type_id")),
        "ablation_method_summary": aggregate_rows(ablation, ("method_id",)),
        "ablation_family_summary": aggregate_rows(ablation, ("method_id", "case_family")),
        "ablation_type_summary": aggregate_rows(ablation, ("method_id", "degradation_type_id")),
        "paired_method_deltas": deltas, "seed_sign_consistency": sign,
        "bootstrap_intervals": bootstrap_intervals(deltas),
        "finite_and_failure_summary": aggregate_rows(items, ("matrix", "method_id")),
        "descriptive_only": True, "p_value_primary_gate": False,
    }


def materialize_analysis(
    *, logical_rows: Iterable[Mapping[str, Any]], unique_rows: Iterable[Mapping[str, Any]],
    evaluation_root: str | Path, provider_root: str | Path,
    analysis_root: str | Path, mechanism_root: str | Path,
    trusted_direct: bool = False,
) -> dict[str, Any]:
    """Materialize every required result/mechanism table from sealed logical rows."""

    rows = tuple(dict(row) for row in logical_rows); unique = tuple(dict(row) for row in unique_rows)
    analysis = build_analysis(rows)
    result_root = Path(analysis_root); mechanism = Path(mechanism_root)
    result_root.mkdir(parents=True, exist_ok=True); mechanism.mkdir(parents=True, exist_ok=True)
    full = [row for row in rows if row["matrix"] == "full_algorithm"]
    ablation = [row for row in rows if row["matrix"] == "internal_ablation"]
    penalties = method_clean_penalties(rows); worst = worst_cases(rows)
    recovery = build_recovery_table(rows, evaluation_root)
    isolation = [] if trusted_direct else source_isolation_audit(rows, unique)
    source_actions, scheme_actions = mechanism_tables(rows, unique, provider_root)
    files: dict[str, str] = {}
    files["full_rows"] = _write_csv(result_root / "FULL_ALGORITHM_ROW_RESULTS.csv.gz", full, gzip_output=True)
    files["ablation_rows"] = _write_csv(result_root / "INTERNAL_ABLATION_ROW_RESULTS.csv.gz", ablation, gzip_output=True)
    files["full_method"] = _write_csv(result_root / "FULL_ALGORITHM_METHOD_SUMMARY.csv", analysis["full_method_summary"])
    files["full_family"] = _write_csv(result_root / "FULL_ALGORITHM_FAMILY_SUMMARY.csv", analysis["full_family_summary"])
    files["full_type"] = _write_csv(result_root / "FULL_ALGORITHM_DEGRADATION_TYPE_SUMMARY.csv", analysis["full_type_summary"])
    files["ablation_method"] = _write_csv(result_root / "INTERNAL_ABLATION_METHOD_SUMMARY.csv", analysis["ablation_method_summary"])
    files["ablation_family"] = _write_csv(result_root / "INTERNAL_ABLATION_FAMILY_SUMMARY.csv", analysis["ablation_family_summary"])
    files["ablation_type"] = _write_csv(result_root / "INTERNAL_ABLATION_DEGRADATION_TYPE_SUMMARY.csv", analysis["ablation_type_summary"])
    files["paired"] = _write_csv(result_root / "PAIRED_METHOD_DELTAS.csv.gz", analysis["paired_method_deltas"], gzip_output=True)
    files["sign"] = _write_csv(result_root / "SEED_SIGN_CONSISTENCY.csv", analysis["seed_sign_consistency"])
    files["bootstrap"] = _write_csv(result_root / "BOOTSTRAP_INTERVALS.csv", analysis["bootstrap_intervals"])
    files["worst"] = _write_csv(result_root / "WORST_CASES.csv", worst)
    files["recovery"] = _write_csv(result_root / "RECOVERY_METRICS.csv", recovery)
    files["penalties"] = _write_csv(result_root / "METHOD_CLEAN_PENALTIES.csv", penalties)
    files["finite"] = _write_csv(result_root / "FINITE_AND_FAILURE_SUMMARY.csv", analysis["finite_and_failure_summary"])
    files["source_actions"] = _write_csv(mechanism / "SOURCE_AWARE_ACTIONS.csv.gz", source_actions, gzip_output=True)
    files["scheme_actions"] = _write_csv(mechanism / "SCHEMEC_ACTIONS.csv", scheme_actions)
    if not trusted_direct:
        files["source_isolation"] = _write_csv(mechanism / "SOURCE_ISOLATION_AUDIT.csv", isolation)
    # Lightweight representative series are copied, not recomputed or corrected.
    evaluable = [row for row in rows if row.get("evaluable") is True]
    if not evaluable:
        raise AnalysisError("no evaluable result available for representative evidence")
    worst_row = max(evaluable, key=lambda row: float(row["horizontal_rmse_m"]))
    recovery_candidates = [row for row in evaluable if row.get("degradation_type_id") in {"D58", "D60"}]
    recovery_row = max(recovery_candidates, key=lambda row: float(row["horizontal_rmse_m"])) if recovery_candidates else worst_row
    for name, row in (("REPRESENTATIVE_WORST_ERROR_SERIES.csv.gz", worst_row),
                      ("REPRESENTATIVE_RECOVERY_ERROR_SERIES.csv.gz", recovery_row)):
        source = Path(evaluation_root) / str(row["run_id"]) / "error_series.csv.gz"
        destination = result_root / name
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise AnalysisError(f"representative series drift: {name}")
        if not destination.exists(): destination.write_bytes(source.read_bytes())
        from .provider_generator import sha256_file
        files[name] = sha256_file(destination)
    terminal_status_resolved = all(row.get("terminal_status") in {
        "COMPLETED_EVALUABLE", "COMPLETED_ALGORITHM_FAILURE_WITH_PROOF",
    } for row in rows)
    evaluable_metrics_finite = all(
        all(math.isfinite(float(row[metric])) for metric in METRICS)
        for row in rows if row.get("evaluable") is True
    )
    mechanism_closure = (
        len(scheme_actions) == 7033
        and all(row.get("mechanism_status") in {
            "complete", "not_evaluable_algorithm_failure",
        } for row in scheme_actions)
        and bool(source_actions)
        and all(row.get("mechanism_status") in {
            "complete", "not_evaluable_algorithm_failure",
        } for row in source_actions)
    )
    crosscheck = {
        "schema_version": "paper_rebuild.canonical541_aggregate_crosscheck.v1",
        "logical_row_count_recomputed": len(rows),
        "full_algorithm_row_count_recomputed": len(full),
        "internal_ablation_row_count_recomputed": len(ablation),
        "unique_execution_count_recomputed": len({str(row["run_id"]) for row in rows}),
        "logical_id_unique": len({str(row["logical_id"]) for row in rows}) == 7033,
        "terminal_status_resolved": terminal_status_resolved,
        "evaluable_metrics_finite": evaluable_metrics_finite,
        "source_isolation_row_count": len(isolation),
        "source_isolation_recomputed_pass": (
            all(row["passed"] for row in isolation) if not trusted_direct else None
        ),
        "source_isolation_audit_performed": not trusted_direct,
        "scheme_mechanism_row_count": len(scheme_actions),
        "source_mechanism_row_count": len(source_actions),
        "mechanism_trace_ledger_closure": mechanism_closure,
        "bootstrap_groups_independent_only": True,
        "deterministic_aliases_not_independent": True,
        "file_sha256": files,
        "passed": (
            len(rows) == 7033 and len(full) == 2164 and len(ablation) == 4869
            and len({str(row["logical_id"]) for row in rows}) == 7033
            and (trusted_direct or all(row["passed"] for row in isolation))
            and terminal_status_resolved and evaluable_metrics_finite
            and mechanism_closure
        ),
    }
    crosscheck_path = result_root / "AGGREGATE_CROSSCHECK.json"
    crosscheck_path.write_text(json.dumps(crosscheck, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return crosscheck
