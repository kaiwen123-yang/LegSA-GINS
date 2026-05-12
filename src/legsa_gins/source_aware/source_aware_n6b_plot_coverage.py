"""Plot-data coverage checks for N6B1 source-aware visual validation.

中文说明：本模块只检查“图背后的数据”是否真实存在、时间轴是否足够长、源
ID 是否齐全；它不读取 trace 作为 solver 输入，不删 epoch，不做输出修正。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any


@dataclass
class N6B1FigureCoverage:
    figure_name: str
    figure_path: str
    mandatory: bool
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
    source_ids: list[str]
    figure_category: str


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
    x_values = _finite(list(series.get("x", [])))
    y_values = _finite(list(series.get("y", [])))
    count = min(len(x_values), len(y_values)) if x_values else len(y_values)
    if x_values:
        return x_values[:count], y_values[:count]
    return [], y_values[:count]


def inspect_n6b1_plot_source_data(plot_name: str, source_data: dict[str, Any]) -> N6B1FigureCoverage:
    """Inspect one planned figure using the data handed to matplotlib.

    中文说明：调用方必须把实际绘图使用的 series/bar 数据传入这里。这样可以
    防止“文件存在但曲线为空”的假通过。
    """

    mandatory = bool(source_data.get("mandatory", True))
    figure_path = str(source_data.get("figure_path", plot_name))
    figure_category = str(source_data.get("figure_category", "generic"))
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
    source_ids = sorted({str(item) for item in source_data.get("source_ids", []) if str(item)})
    reason_codes: list[str] = []
    if mandatory and source_data.get("require_file_exists", True) and not Path(figure_path).exists():
        reason_codes.append("figure_file_missing")
    if not has_nonempty:
        reason_codes.append("no_plotted_source_rows")
    if plotted_series_count < min_series:
        reason_codes.append("plotted_series_below_requirement")
    if total_rows < min_rows:
        reason_codes.append("plotted_rows_below_requirement")
    if min_x_range is not None:
        if x_range is None or x_range < float(min_x_range):
            reason_codes.append("unreasonable_time_axis_range")
    if figure_category == "clean" and (total_rows < 1000 or x_range is None or x_range < 200.0):
        if "clean_time_series_coverage_failed" not in reason_codes:
            reason_codes.append("clean_time_series_coverage_failed")
    if figure_category == "stress":
        labels = {str(row.get("label", "")) for row in series_list}
        if not any("no_sourceaware" in label for label in labels) or not any("n6b" in label for label in labels):
            reason_codes.append("stress_required_series_missing")
    if figure_category == "weight_trace" and len(source_ids) < 4:
        reason_codes.append("weight_trace_source_ids_below_requirement")
    if figure_category == "spike_zoom":
        labels = {str(row.get("label", "")) for row in series_list}
        has_scale = any("scale" in label.lower() for label in labels)
        has_residual = any("residual" in label.lower() or "innovation" in label.lower() for label in labels)
        if not (has_scale and has_residual):
            reason_codes.append("spike_zoom_scale_or_residual_missing")
    has_reasonable_time_axis = "unreasonable_time_axis_range" not in reason_codes
    empty_plot_suspect = mandatory and bool(reason_codes)
    return N6B1FigureCoverage(
        figure_name=plot_name,
        figure_path=figure_path,
        mandatory=mandatory,
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
        source_ids=source_ids,
        figure_category=figure_category,
    )


def summarize_n6b1_plot_coverage(coverage_list: list[N6B1FigureCoverage]) -> dict[str, Any]:
    mandatory = [row for row in coverage_list if row.mandatory]
    failed = [row for row in mandatory if row.empty_plot_suspect]
    required_files_generated = all(Path(row.figure_path).exists() for row in mandatory)
    required_nonempty = not failed and all(row.has_nonempty_data for row in mandatory)
    weight_source_ids = sorted({source for row in coverage_list for source in row.source_ids if row.figure_category == "weight_trace"})
    clean_rows = [
        {
            "figure_name": row.figure_name,
            "total_plotted_row_count": row.total_plotted_row_count,
            "x_range": row.x_range,
        }
        for row in coverage_list
        if row.figure_category == "clean"
    ]
    spike_rows = [
        {
            "figure_name": row.figure_name,
            "total_plotted_row_count": row.total_plotted_row_count,
            "x_range": row.x_range,
        }
        for row in coverage_list
        if row.figure_category == "spike_zoom"
    ]
    return {
        "stage": "N6B1_source_aware_visual_validation",
        "figure_count": len(coverage_list),
        "mandatory_figure_count": len(mandatory),
        "required_figures_generated": required_files_generated and required_nonempty,
        "required_figures_nonempty": required_nonempty,
        "visual_validation_passed": required_nonempty,
        "empty_plot_suspect_count": len(failed),
        "failed_mandatory_figures": [row.figure_name for row in failed],
        "failed_reason_codes": {row.figure_name: row.reason_codes for row in failed},
        "clean_figure_coverage": clean_rows,
        "weight_trace_source_ids": weight_source_ids,
        "spike_zoom_coverage": spike_rows,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_n6b1_plot_coverage_report(
    path: str | Path,
    coverage_list: list[N6B1FigureCoverage],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = summarize_n6b1_plot_coverage(coverage_list)
    report["figures"] = [asdict(row) for row in coverage_list]
    if extra:
        report.update(extra)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
