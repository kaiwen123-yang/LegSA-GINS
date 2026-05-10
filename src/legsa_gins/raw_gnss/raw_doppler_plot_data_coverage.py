"""N5D1 plot-data coverage checks for raw Doppler visual validation.

中文说明：本模块检查“图像背后的数据”是否真的非空，避免只凭 png 文件存在就
通过 visual validation。检查基于传给绘图函数的数据源与 manifest，不解析图片像素。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any


CLEAN_ABLATION_FIGURES = {
    "clean_horizontal_error_baseline_vs_raw",
    "clean_up_error_baseline_vs_raw",
    "clean_yaw_error_baseline_vs_raw",
    "clean_roll_pitch_error_baseline_vs_raw",
}

CLEAN_DIFF_FIGURES = {
    "baseline_minus_raw_horizontal_diff",
    "baseline_minus_raw_yaw_diff",
}


@dataclass
class FigureCoverage:
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


def _stem(plot_name: str) -> str:
    return Path(plot_name).stem


def _series_rows(series: dict[str, Any]) -> tuple[list[float], list[float]]:
    x = _finite(list(series.get("x", [])))
    y = _finite(list(series.get("y", [])))
    count = min(len(x), len(y)) if x else len(y)
    if x:
        return x[:count], y[:count]
    return [], y[:count]


def inspect_plot_source_data(plot_name: str, source_data_dict: dict[str, Any]) -> FigureCoverage:
    """Inspect the source rows used by one figure.

    中文说明：调用方应把将要绘制的 series/bar 数据传进来；这里只做覆盖检查，
    不触碰滤波器输出、不删除 epoch、不做 output-only correction。
    """

    mandatory = bool(source_data_dict.get("mandatory", True))
    figure_path = str(source_data_dict.get("figure_path", plot_name))
    roles = [str(role) for role in source_data_dict.get("source_data_roles", [])]
    series_list = [row for row in source_data_dict.get("series", []) if isinstance(row, dict)]
    row_counts: dict[str, int] = {}
    all_x: list[float] = []
    all_y: list[float] = []
    for index, series in enumerate(series_list):
        label = str(series.get("label") or f"series_{index}")
        x_values, y_values = _series_rows(series)
        count = len(y_values)
        row_counts[label] = count
        all_x.extend(x_values)
        all_y.extend(y_values)

    total_rows = sum(row_counts.values())
    plotted_series_count = sum(1 for count in row_counts.values() if count > 0)
    x_min, x_max, x_range = _range(all_x)
    y_min, y_max, y_range = _range(all_y)
    has_nonempty = plotted_series_count > 0 and total_rows > 0
    min_rows = int(source_data_dict.get("min_rows", 1 if mandatory else 0) or 0)
    min_series = int(source_data_dict.get("min_series", 1 if mandatory else 0) or 0)
    min_x_range = source_data_dict.get("min_x_range")
    if min_x_range is None and (_stem(plot_name) in CLEAN_ABLATION_FIGURES or _stem(plot_name) in CLEAN_DIFF_FIGURES):
        min_x_range = 200.0
    reason_codes: list[str] = []
    if mandatory and not Path(figure_path).exists() and source_data_dict.get("require_file_exists", True):
        reason_codes.append("figure_file_missing")
    if not has_nonempty:
        reason_codes.append("no_plotted_source_rows")
    if plotted_series_count < min_series:
        reason_codes.append("plotted_series_below_requirement")
    if total_rows < min_rows:
        reason_codes.append("plotted_rows_below_requirement")
    if mandatory and (_stem(plot_name) in CLEAN_ABLATION_FIGURES) and plotted_series_count < 2:
        reason_codes.append("clean_baseline_raw_series_missing")
    if mandatory and (_stem(plot_name) in CLEAN_DIFF_FIGURES) and plotted_series_count < 1:
        reason_codes.append("clean_diff_series_missing")
    required_pairs = set(str(item) for item in source_data_dict.get("required_pairs", []))
    present_pairs = set(str(item) for item in source_data_dict.get("present_pairs", []))
    if required_pairs and not required_pairs.issubset(present_pairs):
        reason_codes.append("stress_required_pairs_missing")
    has_reasonable_time_axis = True
    if min_x_range is not None:
        has_reasonable_time_axis = x_range is not None and x_range >= float(min_x_range)
        if not has_reasonable_time_axis:
            reason_codes.append("unreasonable_time_axis_range")
    empty_plot_suspect = mandatory and bool(reason_codes)
    return FigureCoverage(
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
    )


def validate_required_figure_coverage(coverage_list: list[FigureCoverage]) -> dict[str, Any]:
    """Summarize mandatory figure coverage.

    中文说明：只要 mandatory 图为空或时间轴不合理，N5D1 visual candidate 不能通过。
    """

    mandatory = [coverage for coverage in coverage_list if coverage.mandatory]
    failed = [coverage for coverage in mandatory if coverage.empty_plot_suspect]
    physical_files_generated = all(Path(coverage.figure_path).exists() for coverage in mandatory)
    required_nonempty = not failed and all(coverage.has_nonempty_data for coverage in mandatory)
    return {
        "stage": "N5D1_visual_data_coverage_spike_audit",
        "figure_count": len(coverage_list),
        "mandatory_figure_count": len(mandatory),
        "physical_required_files_generated": physical_files_generated,
        "required_figures_generated": physical_files_generated and required_nonempty,
        "required_figures_nonempty": required_nonempty,
        "mandatory_coverage_passed": required_nonempty,
        "empty_plot_suspect_count": len(failed),
        "failed_mandatory_figures": [coverage.figure_name for coverage in failed],
        "failed_reason_codes": {coverage.figure_name: coverage.reason_codes for coverage in failed},
        "visual_stress_candidate_passed": required_nonempty,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_coverage_report(
    path: str | Path,
    coverage_list: list[FigureCoverage],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = validate_required_figure_coverage(coverage_list)
    report["figures"] = [asdict(coverage) for coverage in coverage_list]
    if extra:
        report.update(extra)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
