"""CLEAN2R2A clean 2^4 的预冻结描述性效应计算。"""

from __future__ import annotations

import math
import csv
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping

from .clean2r2a_ablation import BIT_ORDER, VARIANT_IDS, canonical_ablation_profiles
from .paths import load_yaml_mapping
from .manifest import write_json_atomic


class Clean2R2AAnalysisError(ValueError):
    """输入不是 16 行有限 clean factorial 结果。"""


def _validated_values(values: Mapping[str, float]) -> dict[str, float]:
    if set(values) != set(VARIANT_IDS):
        raise Clean2R2AAnalysisError("factorial result set must be exactly AB0000..AB1111")
    normalized: dict[str, float] = {}
    for configuration_id in VARIANT_IDS:
        value = values[configuration_id]
        if isinstance(value, bool):
            raise Clean2R2AAnalysisError("boolean is not a metric value")
        number = float(value)
        if not math.isfinite(number):
            raise Clean2R2AAnalysisError("factorial metric contains NaN or Inf")
        normalized[configuration_id] = number
    return normalized


def factorial_effect(values: Mapping[str, float], factors: tuple[str, ...]) -> float:
    """实现冻结公式 effect = 2 * sum(x*y) / 16。"""

    normalized = _validated_values(values)
    if not factors or len(set(factors)) != len(factors) or any(factor not in BIT_ORDER for factor in factors):
        raise Clean2R2AAnalysisError("invalid factorial term")
    total = 0.0
    for profile in canonical_ablation_profiles():
        # 主效应与交互都使用同一组 {-1,+1} 正交编码。
        code = 1
        for factor in factors:
            code *= profile.effect_code(factor)
        total += code * normalized[profile.configuration_id]
    return 2.0 * total / 16.0


def factorial_main_effects(values: Mapping[str, float]) -> dict[str, float]:
    return {factor: factorial_effect(values, (factor,)) for factor in BIT_ORDER}


def factorial_pairwise_interactions(values: Mapping[str, float]) -> dict[str, float]:
    return {
        f"{left}:{right}": factorial_effect(values, (left, right))
        for left, right in combinations(BIT_ORDER, 2)
    }


def full_vs_strong_delta(values: Mapping[str, float]) -> float:
    normalized = _validated_values(values)
    return normalized["AB1111"] - normalized["AB0000"]


def analyze_clean_factorial(values: Mapping[str, float]) -> dict[str, object]:
    normalized = _validated_values(values)
    return {
        "variant_count": 16,
        "bit_order": list(BIT_ORDER),
        "main_effects": factorial_main_effects(normalized),
        "pairwise_interactions": factorial_pairwise_interactions(normalized),
        "full_vs_strong_delta": full_vs_strong_delta(normalized),
        "descriptive_only": True,
        "parameter_search_performed": False,
    }


def validate_statistical_contract(path: str | Path) -> dict[str, object]:
    """校验统计公式在读取任何正式指标前已经冻结。"""

    payload = load_yaml_mapping(path)
    if payload.get("schema_version") != "paper_rebuild.clean2r2a_statistics.v1":
        raise Clean2R2AAnalysisError("statistical contract schema mismatch")
    if payload.get("stage_id") != "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD":
        raise Clean2R2AAnalysisError("statistical contract stage mismatch")
    factorial = payload.get("factorial")
    reporting = payload.get("reporting")
    if not isinstance(factorial, Mapping) or not isinstance(reporting, Mapping):
        raise Clean2R2AAnalysisError("statistical contract sections are missing")
    expected_pairs = [list(pair) for pair in combinations(BIT_ORDER, 2)]
    expected = {
        "variant_count": 16,
        "bit_order": list(BIT_ORDER),
        "coding": {"disabled": -1, "enabled": 1},
        "coefficient_formula": "beta=sum(x*y)/16",
        "effect_formula": "effect=2*sum(x*y)/16",
        "main_effects": list(BIT_ORDER),
        "pairwise_interactions": expected_pairs,
        "significance_testing": False,
    }
    if dict(factorial) != expected:
        raise Clean2R2AAnalysisError("frozen factorial formula mismatch")
    if reporting.get("no_parameter_search") is not True:
        raise Clean2R2AAnalysisError("parameter search boundary is not frozen")
    if reporting.get("no_metric_driven_rerun") is not True:
        raise Clean2R2AAnalysisError("metric rerun boundary is not frozen")
    return dict(payload)


METRIC_COLUMNS = {
    "horizontal": "horizontal_rmse_m",
    "Up": "up_rmse_m",
    "3D": "position_3d_rmse_m",
    "roll": "roll_rmse_deg",
    "pitch": "pitch_rmse_deg",
    "yaw": "yaw_rmse_deg",
}


def materialize_factorial_analysis(
    *, evaluation_csv: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """从 18 行 current evaluation 生成 clean-only descriptive factorial evidence。"""

    source = Path(evaluation_csv).resolve(strict=True)
    destination = Path(output_root)
    destination.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["configuration_id"]: row for row in rows}
    if set(VARIANT_IDS) - set(by_id) or len(rows) != 18:
        raise Clean2R2AAnalysisError("evaluation registry is not the 18-row clean closure")
    main_rows: list[dict[str, Any]] = []
    interaction_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    metric_reports: dict[str, Any] = {}
    for metric, column in METRIC_COLUMNS.items():
        values = {configuration_id: float(by_id[configuration_id][column]) for configuration_id in VARIANT_IDS}
        report = analyze_clean_factorial(values)
        metric_reports[metric] = report
        for factor, effect in report["main_effects"].items():
            main_rows.append({"metric": metric, "factor": factor, "effect": effect,
                              "lower_is_better": True, "positive_effect_is_harmful": True})
        for term, effect in report["pairwise_interactions"].items():
            interaction_rows.append({"metric": metric, "interaction": term, "effect": effect,
                                     "lower_is_better": True})
        for comparison, left, right in (
            ("full_vs_strong", "AB1111", "AB0000"),
            ("full_vs_no_source_aware", "AB1111", "AB1011"),
            ("full_vs_no_go2_priors", "AB1111", "AB1100"),
        ):
            delta_rows.append({"metric": metric, "comparison": comparison,
                               "left": left, "right": right,
                               "delta_left_minus_right": values[left] - values[right],
                               "lower_is_better": True})
    with (destination / "CLEAN2R2A_FACTORIAL_RESULTS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (destination / "CLEAN2R2A_MODULE_MAIN_EFFECTS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(main_rows[0])); writer.writeheader(); writer.writerows(main_rows)
    with (destination / "CLEAN2R2A_PAIRWISE_INTERACTIONS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(interaction_rows[0])); writer.writeheader(); writer.writerows(interaction_rows)
    with (destination / "CLEAN2R2A_METHOD_DELTAS.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(delta_rows[0])); writer.writeheader(); writer.writerows(delta_rows)
    runtime_root = destination.parent / "06_FORMAL_RUNS"
    action_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    from .clean2r2a_runner import METHOD_ORDER, run_directory
    for configuration_id in METHOD_ORDER:
        wrapper = json.loads(
            (runtime_root / run_directory(configuration_id) / "CLEAN2R2A_FORMAL_RUN_MANIFEST.json")
            .read_text(encoding="utf-8")
        )
        counters = wrapper["module_counters"]
        mechanisms = wrapper["mechanism_evidence"]
        scheme = mechanisms["scheme_c"]
        source_aware = mechanisms["source_aware"]
        action_rows.append({
            "configuration_id": configuration_id,
            **counters,
            "scheme_c_enabled": scheme["enabled"],
            "source_aware_reject_count": source_aware["rejects"],
        })
        for source_id, stats in source_aware["R_scale_p50_p95_max_by_source"].items():
            source_rows.append({
                "configuration_id": configuration_id,
                "source_id": source_id,
                "source_aware_enabled": source_aware["enabled"],
                "evaluation_count": source_aware["updates_by_source"][source_id],
                "reject_count": source_aware["rejects_by_source"][source_id],
                "R_scale_p50": stats["p50"],
                "R_scale_p95": stats["p95"],
                "R_scale_max": stats["max"],
            })
    with (destination / "CLEAN2R2A_MODULE_ACTION_SUMMARY.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(action_rows[0])); writer.writeheader(); writer.writerows(action_rows)
    with (destination / "CLEAN2R2A_SOURCE_AWARE_R_SCALE_SUMMARY.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0])); writer.writeheader(); writer.writerows(source_rows)
    payload = {
        "schema_version": "paper_rebuild.clean2r2a_factorial_report.v1",
        "stage_id": "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD",
        "variant_count": 16, "structural_method_count": 2,
        "bit_order": list(BIT_ORDER), "metrics": metric_reports,
        "descriptive_only": True, "p_value_generated": False,
        "parameter_search_performed": False, "degradation_case_count": 0,
    }
    write_json_atomic(destination / "CLEAN2R2A_FACTORIAL_REPORT.json", payload)
    lines = [
        "# CLEAN2R2A BY2 clean module ablation report",
        "",
        "This is a descriptive clean-only 2^4 factorial analysis. Positive effects are harmful for lower-is-better metrics.",
        "",
        "| Metric | RD | SA | RP | HV | Full - strong |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for metric in METRIC_COLUMNS:
        report = metric_reports[metric]
        effects = report["main_effects"]
        lines.append(
            f"| {metric} | {effects['RD']:.9g} | {effects['SA']:.9g} | {effects['RP']:.9g} | "
            f"{effects['HV']:.9g} | {report['full_vs_strong_delta']:.9g} |"
        )
    lines.extend(["", "No p-value, parameter search, or non-clean execution is part of this report.", ""])
    (destination / "CLEAN2R2A_FACTORIAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return payload
