"""Data-driven CLEAN2 diagnostic payload builder and PNG/PDF renderer."""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import sha256_file, write_json_atomic


FIGURE_NAMES = (
    "01_clean_factorial_yaw_main_effects",
    "02_clean_factorial_position_main_effects",
    "03_clean_pairwise_interactions",
    "04_classic18_yaw_penalty_heatmap",
    "05_classic18_horizontal_penalty_heatmap",
    "06_classic18_up_penalty_heatmap",
    "07_seeded_family_yaw_penalties",
    "08_seeded_family_worst_case",
    "09_C01_outage_yaw_error_and_actions",
    "10_C07_baseline_spike_yaw_error_and_actions",
    "11_C11_yaw_spike_yaw_error_and_actions",
    "12_C15_mixed_yaw_error_and_actions",
    "13_LegSA_source_aware_scale_perturbed_epochs",
    "14_schemeC_accept_downweight_reject_by_case",
    "15_sentinel_leave_one_out_yaw",
    "16_sentinel_leave_one_out_position",
    "17_method_degradation_ratio_panel",
    "18_clean_vs_controlled_claim_boundary_panel",
)
METHODS = (
    "single_antenna_EKF",
    "basic_dual_yaw_EKF",
    "strong_dual_yaw_EKF",
    "LegSA_Paper_V1",
)
MODULES = ("RD", "SA", "RP", "HV")
FAMILIES = (
    "baseline_vector_noise",
    "baseline_vector_spike",
    "yaw_spike",
    "mixed",
)
SENTINELS = ("C01", "C04", "C07", "C10", "C11", "C15")
PALETTE = ("#2F6B9A", "#D58A27", "#6F7D45", "#A85D75", "#555B66", "#7A5AA6")
LINESTYLES = ("-", "--", "-.", ":")
MARKERS = ("o", "s", "^", "D", "x", "v")


class Clean2PlotError(RuntimeError):
    """Diagnostic source data, payload semantics, or rendered output failed QA."""


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).resolve(strict=True).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise Clean2PlotError(f"Diagnostic source table is empty: {Path(path).name}")
    return rows


def _finite(values: Sequence[Any]) -> list[float]:
    try:
        result = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise Clean2PlotError("Figure data contain a non-numeric value") from exc
    if not result or not all(math.isfinite(value) for value in result):
        raise Clean2PlotError("Figure data are empty or non-finite")
    return result


def _code(case_id: str) -> str:
    return case_id.split("_", 1)[0]


def _ordered_case_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    result = sorted({str(row["case_id"]) for row in rows}, key=lambda value: int(_code(value)[1:]))
    if len(result) != 18 or [_code(value) for value in result] != [f"C{i:02d}" for i in range(18)]:
        raise Clean2PlotError("Diagnostic table does not contain C00..C17 exactly")
    return result


def _categorical(
    *, title: str, unit: str, x_labels: Sequence[str], series: Sequence[Mapping[str, Any]],
    delta_values: Sequence[float], delta_labels: Sequence[str], delta_unit: str,
    source: str, source_row_count: int, kind: str = "bar", subtitle: str = "frozen CLEAN2 descriptive evidence",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "unit": unit,
        "x_labels": list(x_labels),
        "series": [dict(row) for row in series],
        "delta_values": list(delta_values),
        "delta_labels": list(delta_labels),
        "delta_unit": delta_unit,
        "semantic_role": "descriptive_diagnostic_only",
        "source": source,
        "source_row_count": source_row_count,
    }


def _heatmap(
    *, title: str, unit: str, case_ids: Sequence[str], methods: Sequence[str],
    matrix: Sequence[Sequence[float]], delta_values: Sequence[float], source_row_count: int,
) -> dict[str, Any]:
    return {
        "kind": "heatmap",
        "title": title,
        "subtitle": "controlled A1 dual-yaw perturbations; not real scenarios",
        "unit": unit,
        "x_labels": [_code(value) for value in case_ids],
        "y_labels": list(methods),
        "matrix": [list(row) for row in matrix],
        "delta_values": list(delta_values),
        "delta_labels": [_code(value) for value in case_ids],
        "delta_unit": "LegSA minus strong penalty",
        "semantic_role": "controlled_degradation_diagnostic_only",
        "source": "CLEAN2_CASE_METHOD_DELTAS.csv",
        "source_row_count": source_row_count,
    }


def _table_paths(raw: Mapping[str, str | Path]) -> dict[str, Path]:
    required = {
        "main_effects", "interactions", "canonical", "deltas", "family",
        "marginal", "actions", "source_aware",
    }
    if not required.issubset(raw):
        raise Clean2PlotError(f"Analysis table index is incomplete: {sorted(required.difference(raw))}")
    return {key: Path(value).resolve(strict=True) for key, value in raw.items()}


def _evaluation_results(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path).resolve(strict=True)
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = payload.get("results")
    if (
        payload.get("run_count") != 110
        or payload.get("passed") is not True
        or payload.get("all_110_outputs_validated_before_trace") is not True
        or not isinstance(rows, list)
        or len(rows) != 110
    ):
        raise Clean2PlotError("Offline evaluation index is incomplete")
    result = {str(row["run_id"]): dict(row) for row in rows if isinstance(row, Mapping)}
    if len(result) != 110:
        raise Clean2PlotError("Offline evaluation run ids are duplicated")
    for run_id, row in result.items():
        expected = source.parent / run_id / "error_series.csv.gz"
        actual = Path(str(row.get("error_series") or "")).resolve(strict=True)
        if actual != expected.resolve(strict=True) or expected.is_symlink() or expected.parent.is_symlink():
            raise Clean2PlotError("Offline diagnostic error-series path escaped its run")
    return result


def _error_rows(path: str | Path) -> list[dict[str, str]]:
    with gzip.open(Path(path).resolve(strict=True), "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    time_fields = {"time", "time_s", "solver_time", "tow"}
    if not rows or "yaw_err_deg" not in rows[0] or len(time_fields.intersection(rows[0])) != 1:
        raise Clean2PlotError("Representative exact error rows are incomplete")
    return rows


def _error_time_field(row: Mapping[str, Any]) -> str:
    matches = [field for field in ("time", "time_s", "solver_time", "tow") if field in row]
    if len(matches) != 1:
        raise Clean2PlotError("Exact error rows have an ambiguous time column")
    return matches[0]


def _sample_pairs(x: Sequence[float], y: Sequence[float], maximum: int = 450) -> tuple[list[float], list[float]]:
    if len(x) != len(y) or not x:
        raise Clean2PlotError("Time-series x/y cardinality differs")
    if len(x) <= maximum:
        return list(x), list(y)
    indices = sorted({round(index * (len(x) - 1) / (maximum - 1)) for index in range(maximum)})
    return [x[index] for index in indices], [y[index] for index in indices]


def _representative_payload(
    *, code: str, canonical: Sequence[Mapping[str, Any]], evaluations: Mapping[str, Mapping[str, Any]],
    solver_artifacts: Mapping[str, Mapping[str, Path | None]], title: str,
) -> dict[str, Any]:
    rows = [row for row in canonical if _code(str(row["case_id"])) == code]
    by_method = {str(row["method"]): row for row in rows}
    if not {"strong_dual_yaw_EKF", "LegSA_Paper_V1"}.issubset(by_method):
        raise Clean2PlotError(f"Representative case lacks strong/full rows: {code}")
    series = []
    raw_by_method: dict[str, dict[float, float]] = {}
    for method in ("strong_dual_yaw_EKF", "LegSA_Paper_V1"):
        result = evaluations[str(by_method[method]["run_id"])]
        errors = _error_rows(result["error_series"])
        time_field = _error_time_field(errors[0])
        times = _finite([row[time_field] for row in errors])
        values = _finite([row["yaw_err_deg"] for row in errors])
        raw_by_method[method] = {round(time, 9): value for time, value in zip(times, values)}
        sampled_x, sampled_y = _sample_pairs(times, values)
        series.append({"label": method, "x_values": sampled_x, "values": sampled_y})
    common = sorted(set(raw_by_method["strong_dual_yaw_EKF"]).intersection(raw_by_method["LegSA_Paper_V1"]))
    if not common:
        raise Clean2PlotError("Representative strong/full error rows do not overlap")
    delta = [
        abs(raw_by_method["LegSA_Paper_V1"][time])
        - abs(raw_by_method["strong_dual_yaw_EKF"][time])
        for time in common
    ]
    delta_x, delta_y = _sample_pairs(common, delta)
    full_run_id = str(by_method["LegSA_Paper_V1"]["run_id"])
    action_artifact = solver_artifacts.get(full_run_id, {}).get("port_gnss_update_trace")
    if action_artifact is None:
        raise Clean2PlotError("Representative case lacks its sealed action trace")
    action_path = Path(action_artifact).resolve(strict=True)
    actions = _read_csv(action_path)
    action_code = {"NORMAL": 1.0, "DOWNWEIGHT": 2.0, "REJECT": 3.0}
    action_x, action_y = [], []
    for row in actions:
        mode = str(row.get("yaw_mode") or "NONE").upper()
        if mode in action_code:
            action_x.append(float(row["gnss_time"]))
            action_y.append(action_code[mode])
    if not action_x:
        raise Clean2PlotError("Representative case has no yaw action markers")
    return {
        "kind": "time_series",
        "title": title,
        "subtitle": "exact evaluator rows plus sealed neutral action labels",
        "unit": "signed yaw error (deg)",
        "series": series,
        "action_series": [{
            "label": "LegSA action: 1 normal / 2 downweight / 3 reject",
            "x_values": action_x,
            "values": action_y,
        }],
        "delta_x_values": delta_x,
        "delta_values": delta_y,
        "delta_labels": [],
        "delta_unit": "abs(LegSA error)-abs(strong error) deg",
        "semantic_role": "controlled_degradation_row_diagnostic_only",
        "source": "exact error_series.csv.gz + sealed PORT_GNSS_UPDATE_TRACE.csv",
        "source_row_count": sum(len(item) for item in raw_by_method.values()) + len(actions),
    }


def build_diagnostic_plot_payload(
    *, analysis_tables: Mapping[str, str | Path], evaluation_index_path: str | Path,
    solver_artifacts: Mapping[str, Mapping[str, Path | None]],
    output_path: str | Path,
) -> dict[str, Any]:
    """Build all 18 named figures from final analysis tables and sealed row artifacts."""

    paths = _table_paths(analysis_tables)
    main = _read_csv(paths["main_effects"])
    interactions = _read_csv(paths["interactions"])
    canonical = _read_csv(paths["canonical"])
    deltas = _read_csv(paths["deltas"])
    family = _read_csv(paths["family"])
    marginal = _read_csv(paths["marginal"])
    actions = _read_csv(paths["actions"])
    source = _read_csv(paths["source_aware"])
    evaluations = _evaluation_results(evaluation_index_path)
    if set(solver_artifacts) != set(evaluations):
        raise Clean2PlotError("Diagnostic solver artifacts/evaluation runs differ")
    case_ids = _ordered_case_ids(canonical)

    def main_values(metric: str) -> list[float]:
        index = {(row["metric"], row["module"]): float(row["reported_effect_2beta"]) for row in main}
        return [index[(metric, module)] for module in MODULES]

    payload: dict[str, Any] = {}
    payload[FIGURE_NAMES[0]] = _categorical(
        title="C00 factorial yaw main effects", unit="effect on error (deg)", x_labels=MODULES,
        series=[{"label": stat, "values": main_values(f"yaw_{stat}")} for stat in ("rmse", "mae", "p95", "max")],
        delta_values=main_values("yaw_rmse"), delta_labels=MODULES, delta_unit="2*beta yaw RMSE",
        source=paths["main_effects"].name, source_row_count=len(main),
    )
    position_metrics = ("horizontal_rmse", "up_rmse", "position_3d_rmse")
    payload[FIGURE_NAMES[1]] = _categorical(
        title="C00 factorial position main effects", unit="effect on error (m)", x_labels=MODULES,
        series=[{"label": metric, "values": main_values(metric)} for metric in position_metrics],
        delta_values=main_values("horizontal_rmse"), delta_labels=MODULES, delta_unit="2*beta horizontal RMSE",
        source=paths["main_effects"].name, source_row_count=len(main),
    )
    interaction_names = sorted({row["interaction"] for row in interactions})
    interaction_index = {(row["metric"], row["interaction"]): float(row["reported_effect_2beta"]) for row in interactions}
    payload[FIGURE_NAMES[2]] = _categorical(
        title="C00 pairwise module interactions", unit="interaction effect", x_labels=interaction_names,
        series=[{"label": metric, "values": [interaction_index[(metric, term)] for term in interaction_names]} for metric in ("yaw_rmse", "horizontal_rmse", "up_rmse")],
        delta_values=[interaction_index[("yaw_rmse", term)] for term in interaction_names], delta_labels=interaction_names,
        delta_unit="2*beta yaw RMSE", source=paths["interactions"].name, source_row_count=len(interactions),
    )
    delta_index = {(row["case_id"], row["method"]): row for row in deltas}
    for figure, metric, title, unit in (
        (FIGURE_NAMES[3], "delta_yaw_rmse", "Classic-18 yaw degradation penalty", "delta yaw RMSE (deg)"),
        (FIGURE_NAMES[4], "delta_horizontal_rmse", "Classic-18 horizontal degradation penalty", "delta horizontal RMSE (m)"),
        (FIGURE_NAMES[5], "delta_up_rmse", "Classic-18 Up degradation penalty", "delta Up RMSE (m)"),
    ):
        matrix = [[float(delta_index[(case_id, method)][metric]) for case_id in case_ids] for method in METHODS]
        strong, full = matrix[2], matrix[3]
        payload[figure] = _heatmap(
            title=title, unit=unit, case_ids=case_ids, methods=METHODS, matrix=matrix,
            delta_values=[right - left for left, right in zip(strong, full)], source_row_count=len(deltas),
        )
    family_index = {(row["family"], row["method"], row["metric"]): row for row in family}
    for figure, statistic, title in (
        (FIGURE_NAMES[6], "mean", "Seeded-family mean yaw penalties"),
        (FIGURE_NAMES[7], "worst", "Seeded-family worst yaw penalties"),
    ):
        series = [{"label": method, "values": [float(family_index[(name, method, "delta_yaw_rmse")][statistic]) for name in FAMILIES]} for method in METHODS]
        payload[figure] = _categorical(
            title=title, unit="delta yaw RMSE (deg)", x_labels=FAMILIES, series=series,
            delta_values=[full - strong for strong, full in zip(series[2]["values"], series[3]["values"])],
            delta_labels=FAMILIES, delta_unit="LegSA minus strong penalty", source=paths["family"].name,
            source_row_count=len(family), subtitle="three frozen seeds; descriptive only",
        )
    representative = (
        (FIGURE_NAMES[8], "C01", "C01 outage yaw error and actions"),
        (FIGURE_NAMES[9], "C07", "C07 baseline-vector spike yaw error and actions"),
        (FIGURE_NAMES[10], "C11", "C11 signed yaw spike error and actions"),
        (FIGURE_NAMES[11], "C15", "C15 mixed perturbation yaw error and actions"),
    )
    for figure, code, title in representative:
        payload[figure] = _representative_payload(
            code=code, canonical=canonical, evaluations=evaluations,
            solver_artifacts=solver_artifacts, title=title
        )
    source_rows = [row for row in source if row["perturbed_epoch_R_scale_p50"] != ""]
    source_cases = sorted(source_rows, key=lambda row: int(_code(row["case_id"])[1:]))
    payload[FIGURE_NAMES[12]] = _categorical(
        title="LegSA source-aware dual-yaw R scale on perturbed epochs", unit="R scale",
        x_labels=[_code(row["case_id"]) for row in source_cases],
        series=[{"label": stat, "values": [float(row[f"perturbed_epoch_R_scale_{stat}"]) for row in source_cases]} for stat in ("p50", "p95", "max")],
        delta_values=[float(row["perturbed_epoch_source_aware_changed_ratio"]) for row in source_cases],
        delta_labels=[_code(row["case_id"]) for row in source_cases], delta_unit="changed ratio",
        source=paths["source_aware"].name, source_row_count=len(source), kind="line",
    )
    action_index = {(row["case_id"], row["alias_roles"]): row for row in actions}
    strong_actions = [next(row for row in actions if row["case_id"] == case and "canonical_strong" in row["alias_roles"]) for case in case_ids]
    full_actions = [next(row for row in actions if row["case_id"] == case and "canonical_LegSA" in row["alias_roles"]) for case in case_ids]
    action_series = []
    for label, rows in (("strong", strong_actions), ("LegSA", full_actions)):
        for action in ("accepted", "downweighted", "rejected"):
            action_series.append({"label": f"{label} {action}", "values": [float(row[f"perturbed_epoch_{action}_count"]) for row in rows]})
    payload[FIGURE_NAMES[13]] = _categorical(
        title="Scheme-C accept/downweight/reject by case", unit="perturbed epoch count",
        x_labels=[_code(case) for case in case_ids], series=action_series,
        delta_values=[float(full["perturbed_epoch_rejected_count"]) - float(strong["perturbed_epoch_rejected_count"]) for strong, full in zip(strong_actions, full_actions)],
        delta_labels=[_code(case) for case in case_ids], delta_unit="LegSA minus strong rejected count",
        source=paths["actions"].name, source_row_count=len(actions), kind="line",
    )
    marginal_index = {(row["case_id"], row["module"]): row for row in marginal}
    sentinel_ids = [next(case for case in case_ids if _code(case) == code) for code in SENTINELS]
    for figure, metric, title, unit in (
        (FIGURE_NAMES[14], "yaw_rmse", "Sentinel leave-one-module-out yaw marginal loss", "no-module minus full yaw RMSE (deg)"),
        (FIGURE_NAMES[15], "horizontal_rmse", "Sentinel leave-one-module-out position marginal loss", "no-module minus full horizontal RMSE (m)"),
    ):
        series = [{"label": module, "values": [float(marginal_index[(case, module)][metric]) for case in sentinel_ids]} for module in MODULES]
        by_case = list(zip(*(row["values"] for row in series)))
        payload[figure] = _categorical(
            title=title, unit=unit, x_labels=SENTINELS, series=series,
            delta_values=[max(values) - min(values) for values in by_case], delta_labels=SENTINELS,
            delta_unit="module spread", source=paths["marginal"].name, source_row_count=len(marginal),
        )
    canonical_index = {(row["case_id"], row["method"]): row for row in canonical}
    controlled = case_ids[1:]
    ratio_series = []
    for method in METHODS:
        base = float(canonical_index[(case_ids[0], method)]["yaw_rmse"])
        if base <= 0.0:
            raise Clean2PlotError("C00 yaw RMSE cannot form a degradation ratio")
        ratio_series.append({"label": method, "values": [float(canonical_index[(case, method)]["yaw_rmse"]) / base for case in controlled]})
    payload[FIGURE_NAMES[16]] = _categorical(
        title="Method yaw degradation ratios", unit="controlled yaw RMSE / C00 yaw RMSE",
        x_labels=[_code(case) for case in controlled], series=ratio_series,
        delta_values=[full - strong for strong, full in zip(ratio_series[2]["values"], ratio_series[3]["values"])],
        delta_labels=[_code(case) for case in controlled], delta_unit="LegSA ratio minus strong ratio",
        source=paths["canonical"].name, source_row_count=len(canonical), kind="line",
    )
    boundary_series = []
    boundary_delta = []
    for method in METHODS:
        clean = float(canonical_index[(case_ids[0], method)]["yaw_rmse"])
        controlled_values = [float(canonical_index[(case, method)]["yaw_rmse"]) for case in controlled]
        mean = sum(controlled_values) / len(controlled_values)
        worst = max(controlled_values)
        boundary_series.append({"label": method, "values": [clean, mean, worst]})
        boundary_delta.append(mean - clean)
    payload[FIGURE_NAMES[17]] = _categorical(
        title="Clean-real versus controlled-pilot claim boundary", unit="yaw RMSE (deg)",
        x_labels=("C00 clean real", "controlled mean", "controlled worst"), series=boundary_series,
        delta_values=boundary_delta, delta_labels=METHODS, delta_unit="controlled mean minus C00",
        source=paths["canonical"].name, source_row_count=len(canonical),
        subtitle="Classic-18 is controlled degradation, not 18 real scenarios",
    )
    payload[FIGURE_NAMES[17]]["claim_boundary"] = (
        "controlled dual-yaw degradation pilot; no universal superiority"
    )
    if set(payload) != set(FIGURE_NAMES):
        raise Clean2PlotError("Diagnostic payload set is incomplete")
    write_json_atomic(output_path, payload)
    return payload


def _render_categorical(ax: Any, payload: Mapping[str, Any]) -> tuple[int, list[float], list[float], int]:
    x_labels = [str(value) for value in payload.get("x_labels") or []]
    series = payload.get("series")
    if not x_labels or not isinstance(series, list) or not series:
        raise Clean2PlotError("Categorical payload lacks x labels or series")
    x = list(range(len(x_labels)))
    values_all: list[float] = []
    kind = str(payload.get("kind") or "line")
    for index, raw in enumerate(series):
        values = _finite(raw.get("values") or [])
        if len(values) != len(x):
            raise Clean2PlotError("Figure series length differs from x labels")
        values_all.extend(values)
        label = str(raw.get("label") or f"series_{index+1}")
        if kind == "bar":
            width = 0.8 / len(series)
            offset = (index - (len(series) - 1) / 2.0) * width
            ax.bar([value + offset for value in x], values, width=width, label=label,
                   color=PALETTE[index % len(PALETTE)], alpha=0.78, edgecolor="#30343B",
                   linewidth=0.7, hatch=("", "//", "\\", "..", "xx", "oo")[index % 6], zorder=2 + index)
        else:
            ax.plot(x, values, label=label, color=PALETTE[index % len(PALETTE)],
                    linestyle=LINESTYLES[index % len(LINESTYLES)], marker=MARKERS[index % len(MARKERS)],
                    alpha=0.82, zorder=2 + index)
    ax.set_xticks(x, x_labels, rotation=35, ha="right")
    return len(values_all), values_all, [float(value) for value in x], 0


def _render_heatmap(ax: Any, payload: Mapping[str, Any]) -> tuple[int, list[float], list[float], int]:
    import numpy as np

    matrix = np.asarray(payload.get("matrix"), dtype=float)
    x_labels = [str(value) for value in payload.get("x_labels") or []]
    y_labels = [str(value) for value in payload.get("y_labels") or []]
    if matrix.ndim != 2 or matrix.size == 0 or not np.isfinite(matrix).all() or matrix.shape != (len(y_labels), len(x_labels)):
        raise Clean2PlotError("Heatmap matrix/labels are empty, non-finite, or inconsistent")
    maximum = float(np.max(np.abs(matrix))) or 1.0
    image = ax.imshow(matrix, aspect="auto", cmap="coolwarm", vmin=-maximum, vmax=maximum)
    ax.figure.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label=str(payload.get("unit") or "delta"))
    ax.set_xticks(range(len(x_labels)), x_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(y_labels)), y_labels)
    return int(matrix.size), matrix.ravel().tolist(), list(range(len(x_labels))), 0


def _render_time_series(ax: Any, payload: Mapping[str, Any]) -> tuple[int, list[float], list[float], int]:
    series = payload.get("series")
    if not isinstance(series, list) or not series:
        raise Clean2PlotError("Time-series payload has no series")
    all_x: list[float] = []
    all_y: list[float] = []
    for index, raw in enumerate(series):
        x = _finite(raw.get("x_values") or [])
        y = _finite(raw.get("values") or [])
        if len(x) != len(y) or any(right <= left for left, right in zip(x, x[1:])):
            raise Clean2PlotError("Time-series coordinates are inconsistent")
        all_x.extend(x); all_y.extend(y)
        ax.plot(x, y, label=str(raw.get("label")), color=PALETTE[index % len(PALETTE)],
                linestyle=LINESTYLES[index % len(LINESTYLES)], alpha=0.83, zorder=3 + index)
    action_count = 0
    actions = payload.get("action_series") or []
    if actions:
        action_ax = ax.twinx()
        for index, raw in enumerate(actions):
            x = _finite(raw.get("x_values") or [])
            y = _finite(raw.get("values") or [])
            if len(x) != len(y) or any(right <= left for left, right in zip(x, x[1:])):
                raise Clean2PlotError("Action-marker coordinates differ")
            action_count += len(x); all_x.extend(x)
            action_ax.scatter(x, y, label=str(raw.get("label")), marker="x", s=24,
                              color="#A85D75", alpha=0.58, zorder=7)
        action_ax.set_ylabel("neutral action code")
        action_ax.set_yticks([1, 2, 3], ["normal", "downweight", "reject"])
        action_ax.legend(frameon=False, loc="upper right", fontsize=8)
    return len(all_y), all_y, all_x, action_count


def _reasonable_x_range(kind: str, values: Sequence[float]) -> bool:
    """Validate the frozen categorical domain or BY2 evaluator time window."""

    finite = [float(value) for value in values]
    if len(finite) < 2 or not all(math.isfinite(value) for value in finite):
        return False
    if kind == "time_series":
        return min(finite) >= 66.0 - 1.0e-6 and max(finite) <= 340.0 + 1.0e-6 and max(finite) > min(finite)
    unique = sorted(set(finite))
    return unique == [float(index) for index in range(len(unique))]


def render_diagnostic_figures(
    *, plot_payload_path: str | Path, output_dir: str | Path
) -> dict[str, Any]:
    """Render 18 diagnostics and fail closed on data, range, delta, or semantic QA."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    payload = json.loads(Path(plot_payload_path).resolve(strict=True).read_text(encoding="utf-8"))
    if set(payload) != set(FIGURE_NAMES):
        raise Clean2PlotError("Figure payload set does not match the frozen 18 names")
    destination = Path(output_dir).resolve(strict=False)
    if destination.exists():
        raise Clean2PlotError("Fresh CLEAN2 diagnostic figure directory already exists")
    destination.mkdir(parents=True, exist_ok=False)
    manifest_rows: list[dict[str, Any]] = []
    semantic_checks: dict[str, bool] = {}
    x_range_checks: dict[str, bool] = {}
    for name in FIGURE_NAMES:
        spec = payload[name]
        if not isinstance(spec, Mapping) or int(spec.get("source_row_count", 0)) <= 0:
            raise Clean2PlotError(f"Figure payload lacks source lineage: {name}")
        fig, (main_ax, delta_ax) = plt.subplots(
            2, 1, figsize=(12.0, 7.8), gridspec_kw={"height_ratios": [3.2, 1.0]}, constrained_layout=True
        )
        kind = str(spec.get("kind") or "line")
        if kind == "heatmap":
            sample_count, values, x_values, action_count = _render_heatmap(main_ax, spec)
        elif kind in {"line", "bar"}:
            sample_count, values, x_values, action_count = _render_categorical(main_ax, spec)
        elif kind == "time_series":
            sample_count, values, x_values, action_count = _render_time_series(main_ax, spec)
        else:
            raise Clean2PlotError(f"Unsupported diagnostic plot kind: {kind}")
        delta_values = _finite(spec.get("delta_values") or [])
        delta_x_raw = spec.get("delta_x_values")
        if delta_x_raw:
            delta_x = _finite(delta_x_raw)
            if len(delta_x) != len(delta_values):
                raise Clean2PlotError("Time delta panel x/y differ")
            delta_ax.plot(delta_x, delta_values, color="#2F6B9A", linewidth=1.0, alpha=0.82)
        else:
            delta_labels = [str(value) for value in spec.get("delta_labels") or []]
            if len(delta_labels) != len(delta_values):
                raise Clean2PlotError("Delta panel labels/values differ")
            delta_ax.bar(range(len(delta_values)), delta_values, color="#2F6B9A", alpha=0.78,
                         edgecolor="#30343B", hatch="//")
            delta_ax.set_xticks(range(len(delta_labels)), delta_labels, rotation=30, ha="right")
        delta_ax.axhline(0.0, color="#30343B", linewidth=0.9)
        delta_ax.set_ylabel(str(spec.get("delta_unit") or "delta"))
        main_ax.set_title(f"DIAGNOSTIC ONLY — {spec.get('title') or name}", loc="left")
        main_ax.set_ylabel(str(spec.get("unit") or "value"))
        main_ax.grid(axis="y", color="#D9DCE1", linewidth=0.7, alpha=0.8, zorder=0)
        if kind not in {"heatmap"} and len(spec.get("series") or []) > 1:
            main_ax.legend(frameon=False, ncol=2, fontsize=8, loc="best")
        fig.suptitle(
            f"{spec.get('subtitle') or 'frozen CLEAN2 descriptive evidence'} | plotted samples n={sample_count}",
            fontsize=9, color="#555B66",
        )
        png, pdf = destination / f"{name}.png", destination / f"{name}.pdf"
        fig.savefig(png, dpi=180, facecolor="white"); fig.savefig(pdf, facecolor="white"); plt.close(fig)
        if png.stat().st_size <= 1000 or pdf.stat().st_size <= 1000:
            raise Clean2PlotError(f"Rendered figure is empty or implausibly small: {name}")
        x_finite = _finite(x_values)
        x_range_ok = _reasonable_x_range(kind, x_finite)
        semantic_ok = (
            sample_count > 0 and len(values) > 0 and len(delta_values) > 0
            and x_range_ok
            and str(spec.get("semantic_role") or "").endswith("diagnostic_only")
            and (name not in FIGURE_NAMES[8:12] or action_count > 0)
            and (name != FIGURE_NAMES[17] or "controlled dual-yaw degradation pilot" in str(spec.get("claim_boundary")))
        )
        semantic_checks[name] = semantic_ok
        x_range_checks[name] = x_range_ok
        manifest_rows.append({
            "figure_id": name, "kind": kind, "plotted_sample_count": sample_count,
            "finite_value_count": len(values), "x_min": min(x_finite), "x_max": max(x_finite),
            "value_min": min(values), "value_max": max(values), "delta_sample_count": len(delta_values),
            "action_sample_count": action_count, "source_row_count": spec["source_row_count"],
            "png_sha256": sha256_file(png), "pdf_sha256": sha256_file(pdf),
            "diagnostic_only_title": True, "non_color_distinction": True,
            "x_range_reasonable": x_range_ok, "semantic_qa": semantic_ok,
        })
    manifest_path = destination / "CLEAN2_FIGURE_MANIFEST.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0])); writer.writeheader(); writer.writerows(manifest_rows)
    qa = {
        "schema_version": "paper_rebuild.clean2_figure_render_qa.v2",
        "expected_figure_count": 18,
        "rendered_png_count": len(list(destination.glob("*.png"))),
        "rendered_pdf_count": len(list(destination.glob("*.pdf"))),
        "all_nonempty": len(manifest_rows) == 18 and all(row["plotted_sample_count"] > 0 for row in manifest_rows),
        "all_finite": len(manifest_rows) == 18 and all(
            math.isfinite(float(row["value_min"])) and math.isfinite(float(row["value_max"]))
            for row in manifest_rows
        ),
        "all_x_ranges_valid": len(x_range_checks) == 18 and all(x_range_checks.values()),
        "all_have_delta_panel": True, "all_titles_diagnostic_only": True,
        "non_color_distinction_used": True, "visual_parameter_selection_from_metrics": False,
        "x_range_checks": x_range_checks,
        "semantic_checks": semantic_checks,
        "passed": len(manifest_rows) == 18 and all(semantic_checks.values())
        and all(x_range_checks.values()),
    }
    if not qa["passed"]:
        raise Clean2PlotError("CLEAN2 figure semantic/render QA failed")
    write_json_atomic(destination / "CLEAN2_FIGURE_RENDER_QA.json", qa)
    return qa
