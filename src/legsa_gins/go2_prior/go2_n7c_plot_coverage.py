"""Plot-data coverage checks for N7C1 visual validation.

中文说明：N7C1 不只检查图像文件是否存在，还记录每张图实际绘制的数据行数、
时间轴范围和边界证据；这些检查不回灌 solver、不调参、不删除 epoch。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any


@dataclass
class N7C1FigureCoverage:
    figure_name: str
    figure_path: str
    mandatory: bool
    figure_category: str
    source_data_roles: list[str]
    plotted_series_count: int
    plotted_row_count_by_series: dict[str, int]
    total_plotted_row_count: int
    x_min: float | None
    x_max: float | None
    x_range: float | None
    y_min: float | None
    y_max: float | None
    y_range: float | None
    has_nonempty_data: bool
    has_reasonable_time_axis: bool
    empty_plot_suspect: bool
    reason_codes: list[str]
    documented_aggregation: bool
    vertical_disabled_evidence: bool


def _finite(values: list[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            out.append(number)
    return out


def _range(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    low = min(values)
    high = max(values)
    return low, high, high - low


def _series_rows(series: dict[str, Any]) -> tuple[list[float], list[float]]:
    xs = _finite(list(series.get("x", [])))
    ys = _finite(list(series.get("y", [])))
    count = min(len(xs), len(ys)) if xs else len(ys)
    if xs:
        return xs[:count], ys[:count]
    return [], ys[:count]


def inspect_n7c1_plot_source_data(plot_name: str, source_data: dict[str, Any]) -> N7C1FigureCoverage:
    """Inspect one figure using the exact series handed to matplotlib.

    中文说明：调用方传入真实绘图 series；coverage 因此能发现“空图但文件存在”的
    情况，也能检查 clean/stress/vertical boundary 图是否包含必需曲线。
    """

    mandatory = bool(source_data.get("mandatory", True))
    figure_path = str(source_data.get("figure_path", plot_name))
    category = str(source_data.get("figure_category", "generic"))
    roles = [str(role) for role in source_data.get("source_data_roles", [])]
    series_list = [row for row in source_data.get("series", []) if isinstance(row, dict)]
    row_counts: dict[str, int] = {}
    all_x: list[float] = []
    all_y: list[float] = []
    for index, series in enumerate(series_list):
        label = str(series.get("label") or f"series_{index}")
        xs, ys = _series_rows(series)
        row_counts[label] = len(ys)
        all_x.extend(xs)
        all_y.extend(ys)
    total_rows = sum(row_counts.values())
    plotted_series_count = sum(1 for count in row_counts.values() if count > 0)
    x_min, x_max, x_range = _range(all_x)
    y_min, y_max, y_range = _range(all_y)
    has_nonempty = plotted_series_count > 0 and total_rows > 0
    min_rows = int(source_data.get("min_rows", 1 if mandatory else 0) or 0)
    min_series = int(source_data.get("min_series", 1 if mandatory else 0) or 0)
    min_x_range = source_data.get("min_x_range")
    update_count = int(source_data.get("update_count", 0) or 0)
    documented_aggregation = bool(source_data.get("documented_aggregation", False))
    vertical_disabled_evidence = bool(source_data.get("vertical_disabled_evidence", False))
    labels = {str(row.get("label", "")) for row in series_list}
    reason_codes: list[str] = []
    if mandatory and source_data.get("require_file_exists", True) and not Path(figure_path).exists():
        reason_codes.append("figure_file_missing")
    if not has_nonempty:
        reason_codes.append("no_plotted_source_rows")
    if plotted_series_count < min_series:
        reason_codes.append("plotted_series_below_requirement")
    if total_rows < min_rows:
        reason_codes.append("plotted_rows_below_requirement")
    if min_x_range is not None and (x_range is None or x_range < float(min_x_range)):
        reason_codes.append("unreasonable_time_axis_range")
    if category == "clean":
        if total_rows < 1000 or x_range is None or x_range < 200.0:
            reason_codes.append("clean_time_series_coverage_failed")
        if not any("no_go2" in label for label in labels) or not any("go2_horizontal" in label for label in labels):
            reason_codes.append("clean_required_series_missing")
    if category == "prior_signal" and not any("go2" in label.lower() and ("vn" in label.lower() or "ve" in label.lower()) for label in labels):
        reason_codes.append("go2_horizontal_velocity_series_missing")
    if category == "update_residual" and update_count > 0 and total_rows < update_count and not documented_aggregation:
        reason_codes.append("update_residual_rows_below_update_count")
    if category == "stress" and (not any("no_go2" in label for label in labels) or not any("plus_go2" in label for label in labels)):
        reason_codes.append("stress_required_series_missing")
    if category == "vertical_disabled" and not vertical_disabled_evidence:
        reason_codes.append("vertical_disabled_evidence_missing")
    has_reasonable_time_axis = "unreasonable_time_axis_range" not in reason_codes
    empty_plot_suspect = mandatory and bool(reason_codes)
    return N7C1FigureCoverage(
        figure_name=plot_name,
        figure_path=figure_path,
        mandatory=mandatory,
        figure_category=category,
        source_data_roles=roles,
        plotted_series_count=plotted_series_count,
        plotted_row_count_by_series=row_counts,
        total_plotted_row_count=total_rows,
        x_min=x_min,
        x_max=x_max,
        x_range=x_range,
        y_min=y_min,
        y_max=y_max,
        y_range=y_range,
        has_nonempty_data=has_nonempty,
        has_reasonable_time_axis=has_reasonable_time_axis,
        empty_plot_suspect=empty_plot_suspect,
        reason_codes=reason_codes,
        documented_aggregation=documented_aggregation,
        vertical_disabled_evidence=vertical_disabled_evidence,
    )


def summarize_n7c1_plot_coverage(coverage_list: list[N7C1FigureCoverage]) -> dict[str, Any]:
    mandatory = [row for row in coverage_list if row.mandatory]
    failed = [row for row in mandatory if row.empty_plot_suspect]
    required_files_generated = all(Path(row.figure_path).exists() for row in mandatory)
    required_nonempty = not failed and all(row.has_nonempty_data for row in mandatory)
    by_category: dict[str, list[dict[str, Any]]] = {}
    for row in coverage_list:
        by_category.setdefault(row.figure_category, []).append(
            {
                "figure_name": row.figure_name,
                "total_plotted_row_count": row.total_plotted_row_count,
                "x_range": row.x_range,
                "reason_codes": row.reason_codes,
            }
        )
    return {
        "stage": "N7C1_go2_horizontal_velocity_visual_validation",
        "figure_count": len(coverage_list),
        "mandatory_figure_count": len(mandatory),
        "required_figures_generated": required_files_generated and required_nonempty,
        "required_figures_nonempty": required_nonempty,
        "visual_validation_passed": required_nonempty,
        "empty_plot_suspect_count": len(failed),
        "failed_mandatory_figures": [row.figure_name for row in failed],
        "failed_reason_codes": {row.figure_name: row.reason_codes for row in failed},
        "coverage_by_category": by_category,
        "clean_figure_coverage": by_category.get("clean", []),
        "prior_signal_coverage": by_category.get("prior_signal", []),
        "update_residual_coverage": by_category.get("update_residual", []),
        "stress_coverage": by_category.get("stress", []),
        "vertical_disabled_coverage": by_category.get("vertical_disabled", []),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_n7c1_plot_coverage_report(path: str | Path, coverage_list: list[N7C1FigureCoverage]) -> dict[str, Any]:
    report = summarize_n7c1_plot_coverage(coverage_list)
    report["figures"] = [asdict(row) for row in coverage_list]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
