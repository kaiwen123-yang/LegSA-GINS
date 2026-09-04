"""Targeted publication refinements for the approved CLEAN4 plot families."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Iterable

from .common import _atomic_savefig, _caption, _new_figure, artifact_path
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .style import METHOD_COLORS, add_scope_badge, color_for

Draw = Callable[[Any], None]

LABELS = {
    "horizontal_rmse_m": "Horizontal RMSE",
    "position_3d_rmse_m": "3D position RMSE",
    "north_rmse_m": "North RMSE",
    "east_rmse_m": "East RMSE",
    "up_rmse_m": "Up RMSE",
    "roll_rmse_deg": "Roll RMSE",
    "pitch_rmse_deg": "Pitch RMSE",
    "yaw_rmse_deg": "Yaw RMSE",
    "horizontal_p95_m": "Horizontal P95",
    "horizontal_p99_m": "Horizontal P99",
    "horizontal_max_m": "Horizontal maximum",
    "yaw_p95_deg": "Yaw P95",
    "yaw_p99_deg": "Yaw P99",
    "yaw_max_deg": "Yaw maximum",
    "yaw_p95_absolute_deg": "Yaw P95",
    "yaw_p99_absolute_deg": "Yaw P99",
    "yaw_max_absolute_deg": "Yaw maximum",
    "row_coverage_fraction": "Row coverage",
    "temporal_span_coverage_fraction": "Time-span coverage",
    "coverage_ratio": "Matched-epoch coverage",
    "orientation_geodesic_difference_rad_max": "Orientation max",
    "native_yaw_offset_residual_rad_max": "Yaw-offset max",
    "position_difference_m_max": "Position max",
}


def _method(value: object) -> str:
    text = str(value)
    return "GINav" if text in {"LC02", "GINAV"} else text


def _num(row: dict[str, Any], field: str) -> float:
    value = row.get(field)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else float("nan")


def _bar(ax: Any, rows: Iterable[dict[str, Any]], fields: tuple[str, ...], ylabel: str, title: str, *, log: bool = False) -> None:
    import numpy as np

    rows = list(rows)
    labels = [_method(row.get("method_id", row.get("family", "overall"))) for row in rows]
    x = np.arange(len(labels), dtype=float)
    width = 0.78 / max(1, len(fields))
    for index, field in enumerate(fields):
        values = [_num(row, field) for row in rows]
        offset = (index - (len(fields) - 1) / 2) * width
        ax.bar(x + offset, values, width=width, label=LABELS.get(field, field.replace("_", " ").title()),
               color=color_for(field, index), alpha=0.88, edgecolor="#333333", linewidth=0.8)
    ax.set_xticks(x, labels)
    if len(labels) > 6:
        ax.tick_params(axis="x", labelrotation=38)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="semibold")
    if log:
        ax.set_yscale("log")
    if len(fields) > 1:
        ax.legend(frameon=False, loc="best", ncol=2 if len(fields) > 3 else 1)


def _ecdf(ax: Any, rows: Iterable[dict[str, Any]], metrics: tuple[str, ...], *, unit: str, title: str) -> None:
    import numpy as np

    rows = list(rows)
    for index, metric in enumerate(metrics):
        values = np.asarray([_num(row, "delta_candidate_minus_reference") for row in rows if row.get("metric_name") == metric], dtype=float)
        values = np.sort(values[np.isfinite(values)])
        if values.size:
            ax.plot(values, np.arange(1, values.size + 1) / values.size, label=LABELS.get(metric, metric), color=color_for(metric, index), lw=3)
    ax.axvline(0, color="#333333", lw=1.6, linestyle="--")
    ax.set_xlabel(f"F04 − A04 ({unit}); negative favors F04")
    ax.set_ylabel("Empirical CDF")
    ax.set_title(title, fontweight="semibold")
    ax.legend(frameon=False, loc="best")


def _finish(ax: Any) -> None:
    ax.grid(True, alpha=0.55)


def _render(
    family: PlotFamily,
    output_dir: Path,
    draw_functions: tuple[Draw, ...],
    *,
    formats: tuple[str, ...],
    dpi: int,
    composite_pixels: tuple[int, int],
    panel_pixels: tuple[int, int],
    force_rewrite: bool,
) -> list[str]:
    import matplotlib.pyplot as plt

    if len(draw_functions) != family.panel_count:
        raise ValueError(f"{family.plot_id}: refined panel contract mismatch")
    written: list[str] = []
    fig, axes = _new_figure(plt, *composite_pixels, dpi, family.panel_count)
    try:
        if family.plot_id in {"HAR07_GAUGE_TOLERANCE_NORMALIZED", "HAR08_OBSERVABILITY_RANK_NULLITY"}:
            fig.subplots_adjust(bottom=0.29)
        for ax, draw in zip(axes, draw_functions):
            draw(ax)
            _finish(ax)
        if family.plot_id == "HAR07_GAUGE_TOLERANCE_NORMALIZED" and len(axes) > 1:
            # The composite shares the residual/tolerance unit; retaining the
            # right-panel ylabel duplicates it into the inter-panel gutter.
            axes[1].set_ylabel("")
        add_scope_badge(fig, family.scope_label)
        fig.suptitle(family.title, fontsize=35, fontweight="bold")
        fig.text(0.01, 0.01, _caption(family), ha="left", va="bottom", fontsize=14, color="#333333")
        for fmt in formats:
            target = artifact_path(output_dir, family.plot_id, "COMPOSITE", fmt)
            _atomic_savefig(fig, target, fmt=fmt, dpi=dpi, force_rewrite=force_rewrite)
            written.append(str(target))
    finally:
        plt.close(fig)
    for index, draw in enumerate(draw_functions):
        fig, axes = _new_figure(plt, *panel_pixels, dpi, 1)
        try:
            if family.plot_id in {"HAR07_GAUGE_TOLERANCE_NORMALIZED", "HAR08_OBSERVABILITY_RANK_NULLITY"}:
                fig.subplots_adjust(bottom=0.31)
            draw(axes[0])
            _finish(axes[0])
            add_scope_badge(fig, family.scope_label)
            panel_titles = {
                "HAR07_GAUGE_TOLERANCE_NORMALIZED": "Hartley gauge tolerance check",
                "HAR08_OBSERVABILITY_RANK_NULLITY": "Hartley observability structure",
            }
            fig.suptitle(
                panel_titles.get(family.plot_id, family.title),
                x=0.46 if family.plot_id in panel_titles else 0.5,
                fontsize=28 if family.plot_id in panel_titles else 32,
                fontweight="bold",
            )
            fig.text(0.01, 0.01, _caption(family), ha="left", va="bottom", fontsize=12, color="#333333")
            for fmt in formats:
                target = artifact_path(output_dir, family.plot_id, f"PANEL_{chr(65 + index)}", fmt)
                _atomic_savefig(fig, target, fmt=fmt, dpi=dpi, force_rewrite=force_rewrite)
                written.append(str(target))
        finally:
            plt.close(fig)
    return written


def _lc_draws(family: PlotFamily, table: FrozenTable) -> tuple[Draw, Draw]:
    rows = list(table.rows)
    if family.plot_id == "LC01_FORMAL_C00_COVERAGE":
        def a(ax: Any) -> None:
            _bar(ax, rows, ("row_coverage_fraction", "temporal_span_coverage_fraction"), "Coverage fraction", "Formal support coverage")
            ax.set_ylim(0, 1.08)
        def b(ax: Any) -> None:
            _bar(ax, rows, ("matched_rows",), "Matched rows", "Matched formal rows")
        return a, b
    if family.plot_id == "LC02_FORMAL_POSITION_METRICS":
        return (
            lambda ax: _bar(ax, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), "RMSE (m)", "Horizontal and 3D position", log=True),
            lambda ax: _bar(ax, rows, ("north_rmse_m", "east_rmse_m", "up_rmse_m"), "RMSE (m)", "Position components", log=True),
        )
    if family.plot_id == "LC03_FORMAL_ATTITUDE_METRICS":
        return (
            lambda ax: _bar(ax, rows, ("roll_rmse_deg", "pitch_rmse_deg"), "RMSE (deg)", "Roll and pitch"),
            lambda ax: _bar(ax, rows, ("yaw_rmse_deg",), "RMSE (deg)", "Yaw"),
        )
    if family.plot_id == "LC04_FORMAL_TAIL_METRICS":
        return (
            lambda ax: _bar(ax, rows, ("horizontal_p95_m", "horizontal_p99_m", "horizontal_max_m"), "Horizontal error (m)", "Position tails", log=True),
            lambda ax: _bar(ax, rows, ("yaw_p95_deg", "yaw_p99_deg", "yaw_max_deg"), "Absolute yaw error (deg)", "Yaw tails", log=True),
        )
    if family.plot_id == "LC07_GINAV_STATUS_TIMELINE":
        times = [_num(row, "relative_time_s") for row in rows]
        def a(ax: Any) -> None:
            status = [1 if str(row.get("status_name")) == "SPP" else 0 for row in rows]
            ax.step(times, status, where="mid", color=METHOD_COLORS["GINAV"], lw=3, label="Native status")
            ax.scatter([t for t, row in zip(times, rows) if row.get("lc_update") is True], [1] * sum(row.get("lc_update") is True for row in rows), marker="o", s=65, color="#2CA02C", label="LC update / SPP")
            ax.set_yticks([0, 1], ["INS-only", "SPP / LC"])
            ax.set_xlabel("Time (s)")
            ax.set_title("Native status and update events", fontweight="semibold")
            ax.legend(frameon=False, loc="best")
        def b(ax: Any) -> None:
            sats = [_num(row, "satellite_count") for row in rows]
            ax.plot(times, sats, color=METHOD_COLORS["GINAV"], lw=2.8, label="Satellites")
            update_times = [t for t, row in zip(times, rows) if row.get("lc_update") is True]
            ins_times = [t for t, row in zip(times, rows) if row.get("ins_only") is True]
            ax.scatter(update_times, [-1] * len(update_times), marker="|", s=180, color="#2CA02C", label="LC update")
            ax.scatter(ins_times, [-2] * len(ins_times), marker="|", s=100, color="#7A7A7A", label="INS-only")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Satellite count")
            ax.set_title("Satellite support and propagation mode", fontweight="semibold")
            ax.text(0.02, 0.96, f"{len(update_times)} LC-update/SPP | {len(ins_times)} INS-only", transform=ax.transAxes, va="top", fontweight="bold")
            ax.legend(frameon=False, loc="upper right")
        return a, b
    if family.plot_id == "LC10_COMMON_SUPPORT_77_DIAGNOSTIC":
        return (
            lambda ax: _bar(ax, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), "RMSE (m)", "Position on 77 common epochs", log=True),
            lambda ax: _bar(ax, rows, ("roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"), "RMSE (deg)", "Attitude on 77 common epochs", log=True),
        )
    raise KeyError(family.plot_id)


def render_lc(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    return _render(family, output_dir, _lc_draws(family, table), **kwargs)


def _series_draw(table: FrozenTable, fields: tuple[str, ...], ylabel: str, title: str, *, ecdf: bool = False) -> Draw:
    rows = list(table.rows)
    def draw(ax: Any) -> None:
        import numpy as np
        for index, field in enumerate(fields):
            values = np.asarray([_num(row, field) for row in rows], dtype=float)
            valid = np.isfinite(values)
            if ecdf:
                data = np.sort(np.abs(values[valid]))
                ax.plot(data, np.arange(1, len(data) + 1) / len(data), label=LABELS.get(field, field), color=color_for(field, index))
            else:
                times = np.asarray([_num(row, "time") for row in rows], dtype=float)
                keep = np.flatnonzero(valid & np.isfinite(times))[::max(1, len(rows) // 5000)]
                ax.plot(times[keep], values[keep], label=LABELS.get(field, field), color=color_for(field, index), alpha=0.9)
        ax.set_xlabel(f"Absolute error ({ylabel})" if ecdf else "Time (s)")
        ax.set_ylabel("Empirical CDF" if ecdf else ylabel)
        ax.set_title(title, fontweight="semibold")
        ax.legend(frameon=False, loc="best")
    return draw


def render_internal(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = list(table.rows)
    if family.plot_id == "INT01_FORMAL_C00_RMSE":
        draws = (
            lambda ax: _bar(ax, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), "RMSE (m)", "Formal C00 position RMSE"),
            lambda ax: _bar(ax, rows, ("roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"), "RMSE (deg)", "Formal C00 attitude RMSE"),
        )
    elif family.plot_id == "INT02_FORMAL_C00_TAIL_METRICS":
        draws = (
            lambda ax: _bar(ax, rows, ("horizontal_p95_m", "horizontal_p99_m", "horizontal_max_m"), "Horizontal error (m)", "Formal C00 position tails"),
            lambda ax: _bar(ax, rows, ("yaw_p95_absolute_deg", "yaw_p99_absolute_deg", "yaw_max_absolute_deg"), "Absolute yaw error (deg)", "Formal C00 yaw tails"),
        )
    elif family.plot_id == "INT03_FORMAL_C00_COVERAGE_AND_TIME":
        def coverage(ax: Any) -> None:
            _bar(ax, rows, ("coverage_ratio",), "Coverage fraction", "Matched-epoch coverage")
            ax.set_ylim(0, 1.08)
            for i, row in enumerate(rows):
                ax.text(i, _num(row, "coverage_ratio") + 0.02, f"n={int(_num(row, 'matched_epoch_count')):,}", ha="center")
        def support(ax: Any) -> None:
            derived = [dict(row, time_span_s=_num(row, "time_end_s") - _num(row, "time_start_s")) for row in rows]
            _bar(ax, derived, ("time_span_s", "max_gap_s"), "Time (s)", "Evaluated span and maximum gap")
        draws = (coverage, support)
    elif family.plot_id == "INT04_C00_HORIZONTAL_AND_3D_ERROR_TIME":
        draws = (
            _series_draw(table, ("horizontal_err_m",), "Error (m)", "A04 horizontal error"),
            _series_draw(table, ("position_3d_err_m",), "Error (m)", "A04 3D position error"),
        )
    elif family.plot_id == "INT05_C00_ATTITUDE_ERROR_TIME":
        draws = (
            _series_draw(table, ("roll_err_deg", "pitch_err_deg"), "Error (deg)", "A04 roll and pitch errors"),
            _series_draw(table, ("yaw_err_deg",), "Error (deg)", "A04 yaw error"),
        )
    elif family.plot_id == "INT06_C00_ERROR_ECDF":
        draws = (
            _series_draw(table, ("horizontal_err_m", "position_3d_err_m"), "m", "A04 position-error ECDF", ecdf=True),
            _series_draw(table, ("roll_err_deg", "pitch_err_deg", "yaw_err_deg"), "deg", "A04 attitude-error ECDF", ecdf=True),
        )
    else:
        raise KeyError(family.plot_id)
    return _render(family, output_dir, draws, **kwargs)


def _pair_rows(table: FrozenTable) -> list[dict[str, Any]]:
    rows = [row for row in table.rows if row.get("comparison") == "full_vs_no_SA"]
    if "candidate_method_id" in table.columns:
        rows = [row for row in rows if row.get("candidate_method_id") == "F04" and row.get("reference_method_id") == "A04"]
    if not rows:
        raise IdentityMismatch("F04/A04 full_vs_no_SA pair is absent")
    return rows


def render_canonical(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = _pair_rows(table)
    if family.plot_id == "C541_06_A04_F04_PAIRED_DELTA_DISTRIBUTION":
        draws = (
            lambda ax: _ecdf(ax, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), unit="m", title="Position delta distribution"),
            lambda ax: _ecdf(ax, rows, ("roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"), unit="deg", title="Attitude delta distribution"),
        )
    elif family.plot_id == "C541_07_A04_F04_PAIRED_SCATTER":
        def scatter(metric: str, unit: str, title: str) -> Draw:
            def draw(ax: Any) -> None:
                selected = [row for row in rows if row.get("metric_name") == metric]
                x = [_num(row, "reference_value") for row in selected]
                y = [_num(row, "candidate_value") for row in selected]
                ax.scatter(x, y, s=28, alpha=0.55, color=METHOD_COLORS["F04"], edgecolors="none")
                finite = [v for v in x + y if math.isfinite(v)]
                lo, hi = (min(finite), max(finite)) if finite else (0, 1)
                ax.plot([lo, hi], [lo, hi], "--", color="#333333", lw=2, label="Identity")
                ax.set_xlabel(f"A04 ({unit})")
                ax.set_ylabel(f"F04 ({unit})")
                ax.set_title(title, fontweight="semibold")
                ax.legend(frameon=False, loc="lower right")
            return draw
        draws = (scatter("horizontal_rmse_m", "m", "Horizontal RMSE paired cases"), scatter("yaw_rmse_deg", "deg", "Yaw RMSE paired cases"))
    elif family.plot_id == "C541_08_WIN_TIE_LOSS_BY_FAMILY":
        def wtl(metric: str, title: str) -> Draw:
            def draw(ax: Any) -> None:
                import numpy as np
                selected = [row for row in rows if row.get("metric_name") == metric and row.get("scope") in {"overall", "family"}]
                selected.sort(key=lambda row: (row.get("scope") != "overall", str(row.get("family"))))
                family_labels = {
                    "clean": "Clean",
                    "dual_yaw": "Dual yaw",
                    "gnss_outage": "GNSS outage",
                    "gnss_sampling": "GNSS sampling",
                    "go2_prior_metadata": "Go2 metadata",
                    "multi_source_mixed": "Mixed source",
                    "position_std_status": "Position status",
                    "position_value": "Position value",
                    "velocity_raw_doppler": "Raw Doppler",
                }
                labels = ["Overall" if row.get("scope") == "overall" else family_labels.get(str(row.get("family")), str(row.get("family"))) for row in selected]
                y = np.arange(len(labels))
                left = np.zeros(len(labels))
                for field, label, color in (("win_count", "Win", "#2CA02C"), ("tie_count", "Tie", "#B0B0B0"), ("loss_count", "Loss", "#D62728")):
                    vals = np.asarray([_num(row, field) for row in selected])
                    ax.barh(y, vals, left=left, label=label, color=color, alpha=0.88)
                    left += vals
                ax.set_yticks(y, labels, fontsize=15)
                ax.invert_yaxis()
                ax.set_xlabel("Case count")
                ax.set_title(title, fontweight="semibold")
                ax.text(0.98, 0.02, "F04 − A04; negative favors F04", transform=ax.transAxes, ha="right")
                ax.legend(frameon=False, loc="lower right")
                ax.figure.subplots_adjust(left=0.13, right=0.97)
            return draw
        draws = (wtl("horizontal_rmse_m", "Horizontal RMSE wins / ties / losses"), wtl("yaw_rmse_deg", "Yaw RMSE wins / ties / losses"))
    else:
        raise KeyError(family.plot_id)
    return _render(family, output_dir, draws, **kwargs)


def render_cross(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = list(table.rows)
    def coverage(ax: Any) -> None:
        _bar(ax, rows, ("row_coverage_fraction", "temporal_span_coverage_fraction"), "Coverage fraction", "Formal support coverage")
        ax.set_ylim(0, 1.08)
    def accuracy(ax: Any) -> None:
        # Two visually separate axes preserve units while retaining the historic Panel B filename.
        ax.set_axis_off()
        pos = ax.inset_axes([0.00, 0.0, 0.47, 1.0])
        att = ax.inset_axes([0.56, 0.0, 0.44, 1.0])
        _bar(pos, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), "RMSE (m)", "Position", log=True)
        _bar(att, rows, ("yaw_rmse_deg",), "RMSE (deg)", "Yaw", log=True)
    return _render(family, output_dir, (coverage, accuracy), **kwargs)


def _aggregate(rows: Iterable[dict[str, Any]], key: str, fields: tuple[str, ...], *, mode: str = "sum") -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key)), []).append(row)
    result = []
    for label, members in grouped.items():
        item: dict[str, Any] = {"method_id": label, key: label}
        for field in fields:
            values = [_num(row, field) for row in members]
            values = [value for value in values if math.isfinite(value)]
            item[field] = (sum(values) / len(values) if mode == "mean" else sum(values)) if values else float("nan")
        result.append(item)
    return result


def _policy(value: object) -> str:
    text = str(value)
    labels = {
        "FAR_ALL_AMBIGUITIES": "FAR",
        "EXT04_PAR_DECLARED_POLICY_V1": "PAR",
        "EXT04_PAR_DECLARED_POLICY_V1_RATIO_2P0": "R2",
        "EXT04_PAR_DECLARED_POLICY_V1_RATIO_5P0": "R5",
        "EXT04_PAR_DECLARED_POLICY_V1_BASELINE_0P020M": "B20",
        "EXT04_PAR_DECLARED_POLICY_V1_BASELINE_0P100M": "B100",
        "EXT04_PAR_DECLARED_POLICY_V1_POSTERIOR_ALPHA_0P001": "A001",
        "EXT04_PAR_DECLARED_POLICY_V1_ADOP_0P10": "ADOP10",
        "EXT04_PAR_DECLARED_POLICY_V1_ADOP_0P15": "ADOP15",
    }
    return labels.get(text, text)


def render_ext04(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = list(table.rows)
    count_fields = tuple(field for field in family.required_fields if field.endswith("_count") or field == "row_count")
    if family.plot_id == "EXT04_01_FAR_PAR_INVALID_FLOW":
        agg = _aggregate(rows, "policy_identity", ("FAR_REJECTED_count", "PAR_EXHAUSTED_count", "INVALID_count", "accepted_count"))
        for row in agg:
            row["method_id"] = _policy(row["policy_identity"])
        draws = (
            lambda ax: _bar(ax, agg, ("FAR_REJECTED_count", "PAR_EXHAUSTED_count", "INVALID_count"), "Rows", "Rejected and invalid states", log=True),
            lambda ax: _accepted_zero(ax, agg),
        )
    elif family.plot_id == "EXT04_02_POLICY_MODE_STATE_HEATMAP":
        def heat(field: str, title: str) -> Draw:
            def draw(ax: Any) -> None:
                import numpy as np
                policies = list(dict.fromkeys(str(row.get("policy_identity")) for row in rows))
                modes = list(dict.fromkeys(str(row.get("system_mode")) for row in rows))
                matrix = np.asarray([[_num(next(row for row in rows if str(row.get("policy_identity")) == p and str(row.get("system_mode")) == m), field) for m in modes] for p in policies])
                image = ax.imshow(matrix, aspect="auto", cmap="cividis")
                ax.set_yticks(range(len(policies)), [_policy(p) for p in policies])
                ax.set_xticks(range(len(modes)), [m.replace("GPS_BDS_DUAL_FREQUENCY", "GPS+BDS").replace("_DUAL_FREQUENCY", "") for m in modes])
                ax.set_title(title, fontweight="semibold")
                ax.figure.colorbar(image, ax=ax, fraction=0.045, pad=0.02, label="Rows")
            return draw
        draws = (heat("INVALID_count", "Invalid rows by policy and mode"), heat("FAR_REJECTED_count", "FAR-rejected rows by policy and mode"))
    elif family.plot_id == "EXT04_03_AMBIGUITY_QC_BASELINE_FUNNEL":
        fields = ("row_count", "ADOP_pass_count", "baseline_validation_pass_count", "posterior_residual_pass_count", "accepted_count")
        agg = _aggregate(rows, "policy_identity", fields)
        for row in agg:
            row["method_id"] = _policy(row["policy_identity"])
        draws = (
            lambda ax: _bar(ax, agg, fields[:-1], "Rows", "Quality-control funnel", log=True),
            lambda ax: _accepted_zero(ax, agg),
        )
    elif family.plot_id == "EXT04_04_POLICY_MODE_RUNTIME":
        fields = ("allocated_runtime_seconds_total", "shared_chain_mode_runtime_seconds_total")
        agg = _aggregate(rows, "policy_identity", fields, mode="sum")
        for row in agg:
            row["method_id"] = _policy(row["policy_identity"])
        draws = (
            lambda ax: _bar(ax, agg, ("allocated_runtime_seconds_total",), "Runtime (s)", "Allocated runtime by policy"),
            lambda ax: _bar(ax, agg, ("shared_chain_mode_runtime_seconds_total",), "Runtime (s)", "Shared-chain runtime by policy"),
        )
    else:
        raise KeyError(family.plot_id)
    return _render(family, output_dir, draws, **kwargs)


def _accepted_zero(ax: Any, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    labels = [_method(row.get("method_id")) for row in rows]
    values = [_num(row, "accepted_count") for row in rows]
    ax.bar(labels, values, color="#8C8C8C", edgecolor="#333333")
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_ylabel("Accepted rows")
    ax.set_title("No accepted solutions", fontweight="semibold")
    ax.text(0.5, 0.55, "accepted = 0", transform=ax.transAxes, ha="center", fontsize=30, fontweight="bold", color="#555555")


def render_lc_extra(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = list(table.rows)
    if family.plot_id == "LC05_TIME_SUPPORT_GAPS_SEGMENTS":
        def gap(ax: Any) -> None:
            _bar(ax, rows, ("max_gap_s",), "Gap (s)", "Maximum output gap")
            for index, row in enumerate(rows):
                segments = _num(row, "segment_count")
                if math.isfinite(segments):
                    ax.text(index, _num(row, "max_gap_s") + 0.2, f"{int(segments)} segments", ha="center")
        draws = (
            lambda ax: _bar(ax, rows, ("first_valid_output_s", "last_valid_output_s"), "Time (s)", "First and last valid output"),
            gap,
        )
    elif family.plot_id == "LC06_INITIALIZATION_AND_UPDATE_FUNNEL":
        normalized = []
        for row in rows:
            copy = dict(row)
            update = row.get("update_count")
            if not isinstance(update, (int, float)) and isinstance(update, str) and "LC=" in update:
                try:
                    copy["update_count"] = float(update.split("LC=", 1)[1].split(";", 1)[0])
                except ValueError:
                    copy["update_count"] = float("nan")
            group = str(row.get("support_or_group"))
            short_group = {
                "FORMAL_FULL_C00": "LC01\nFormal C00",
                "OVERALL": "GINav\nOverall",
                "LC_UPDATE_DIAGNOSTIC": "GINav\nLC update",
                "INS_ONLY_DIAGNOSTIC": "GINav\nINS-only",
            }.get(group, group.replace("_", " "))
            copy["method_id"] = short_group
            normalized.append(copy)
        draws = (
            lambda ax: _bar(ax, normalized, ("configured_epochs", "official_eligible_epochs", "spp_valid", "spp_invalid"), "Epoch count", "Configured and GNSS eligibility"),
            lambda ax: _bar(ax, normalized, ("native_rows", "matched_rows", "update_count"), "Row / update count", "Native output and updates", log=True),
        )
    elif family.plot_id == "LC08_GINAV_LC_UPDATE_VS_INS_ONLY":
        for row in rows:
            row["method_id"] = str(row.get("diagnostic_group") or row.get("evaluation_scope")).replace("_DIAGNOSTIC", "").replace("_", " ")
        draws = (
            lambda ax: _bar(ax, rows, ("horizontal_rmse_m", "position_3d_rmse_m"), "RMSE (m)", "Position by native-support group", log=True),
            lambda ax: _bar(ax, rows, ("roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"), "RMSE (deg)", "Attitude by native-support group", log=True),
        )
    else:
        raise KeyError(family.plot_id)
    return _render(family, output_dir, draws, **kwargs)


def _short_group(row: dict[str, Any]) -> str:
    if row.get("model") is not None:
        model = "Ideal" if row.get("model") == "IDEAL_BIAS_FREE" else "Bias"
        window = str(row["window_id"]).replace("WIN00", "W")
        return f"{model} {window} C={row.get('contact_count')}"
    value = row.get("group_id") or row.get("window_id") or row.get("run_id")
    if not value:
        model = str(row.get("model", "Model")).replace("IDEAL_BIAS_FREE", "Ideal").replace("FULL_WITH_BIASES", "Bias")
        contact = row.get("contact_count")
        value = f"{model} C={contact}"
    value = str(value)
    topology = {
        "INITIAL_STATIC_FOUR_CONTACT": "Static 4-contact",
        "DYNAMIC_FOUR_CONTACT": "Dynamic 4-contact",
        "INITIALIZATION_NO_CHI_SQUARE": "Init (no chi-square)",
        "PROPAGATION_ONLY_FLIGHT": "Flight propagation",
        "AUGMENTATION_ONLY_NO_SURVIVOR_UPDATE": "Augment only",
    }
    if value in topology:
        return topology[value]
    if value.startswith("H6R_YAW_"):
        offset = value.removeprefix("H6R_YAW_").replace("M", "-").replace("P", "+")
        return offset
    return value.replace("CONTACT_COUNT_", "C=").replace("CONTACT_TOPOLOGY_", "Topo ")


def _barh(ax: Any, rows: list[dict[str, Any]], fields: tuple[str, ...], title: str) -> None:
    import numpy as np
    labels = [row["method_id"] for row in rows]
    y = np.arange(len(labels), dtype=float)
    height = 0.76 / max(1, len(fields))
    for index, field in enumerate(fields):
        ax.barh(y + (index - (len(fields) - 1) / 2) * height, [_num(row, field) for row in rows], height=height, label=LABELS.get(field, field.replace("_", " ").title()), color=color_for(field, index), alpha=0.88)
    ax.set_yticks(y, labels, fontsize=14)
    ax.invert_yaxis()
    ax.set_xlabel("Dimension")
    ax.set_title(title, fontweight="semibold")
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=len(fields),
    )


def render_hartley(family: PlotFamily, table: FrozenTable, output_dir: Path, **kwargs: Any) -> list[str]:
    rows = [dict(row, method_id=_short_group(row)) for row in table.rows]
    if family.plot_id == "HAR06_GAUGE_EQUIVALENCE_QUANTILES":
        def gauge(fields: tuple[str, ...], ylabel: str, title: str) -> Draw:
            def draw(ax: Any) -> None:
                _bar(ax, rows, fields, ylabel, title, log=True)
                ax.set_xlabel("Initial yaw offset (deg)")
            return draw
        draws = (gauge(("orientation_geodesic_difference_rad_p95", "relative_yaw_increment_difference_rad_p95"), "Difference (rad)", "Gauge-equivalent orientation"), gauge(("position_difference_m_p95",), "Difference (m)", "Gauge-equivalent position"))
    elif family.plot_id == "HAR07_GAUGE_TOLERANCE_NORMALIZED":
        def ratio(fields: tuple[tuple[str, str], ...], title: str) -> Draw:
            derived = []
            for row in rows:
                item = {"method_id": row["method_id"]}
                for value, tolerance in fields:
                    item[value] = _num(row, value) / _num(row, tolerance)
                derived.append(item)
            return lambda ax: _ratio_bar(ax, derived, tuple(value for value, _ in fields), title)
        draws = (
            ratio((("orientation_geodesic_difference_rad_max", "orientation_geodesic_difference_rad_tolerance"), ("native_yaw_offset_residual_rad_max", "native_yaw_offset_residual_rad_tolerance")), "Orientation residual / tolerance"),
            ratio((("position_difference_m_max", "position_difference_m_tolerance"),), "Position residual / tolerance"),
        )
        original = draws
        draws = tuple((lambda draw: (lambda ax: (draw(ax), ax.set_xlabel("Initial yaw offset (deg)"))))(draw) for draw in original)
    elif family.plot_id == "HAR08_OBSERVABILITY_RANK_NULLITY":
        draws = (
            lambda ax: _barh(ax, rows, ("rank_at_base_threshold", "expected_rank"), "Observed and expected rank"),
            lambda ax: _barh(ax, rows, ("nullity_at_base_threshold", "expected_nullity"), "Observed and expected nullity"),
        )
    elif family.plot_id == "HAR09_NONGAUGE_SINGULAR_AND_WEAK_DIRECTIONS":
        def singular(ax: Any) -> None:
            _bar(ax, rows, ("smallest_non_gauge_singular_value",), "Singular value", "Smallest non-gauge singular value", log=True)
            for index, row in enumerate(rows):
                weak = _num(row, "bias_dominated_weak_direction_count")
                if math.isfinite(weak):
                    ax.text(index, _num(row, "smallest_non_gauge_singular_value") * 1.15, f"weak={int(weak)}", ha="center")
        draws = (
            lambda ax: _bar(ax, rows, ("condition_number_after_gauge_projection",), "Condition number", "Gauge-projected conditioning", log=True),
            singular,
        )
    elif family.plot_id == "HAR10_TOPOLOGY_NIS_CHI_SQUARE":
        count_rows = [row for row in rows if row.get("group_type") == "CONTACT_COUNT"]
        topology_rows = [row for row in rows if row.get("group_type") != "CONTACT_COUNT"]
        def nis(ax: Any) -> None:
            _bar(ax, count_rows, ("nis_over_dof_mean",), "NIS / DoF", "NIS by contact count")
            ax.axhline(1, color="#333333", linestyle="--", lw=2, label="Ideal mean")
            ax.legend(frameon=False)
        def coverage(ax: Any) -> None:
            import numpy as np
            labels = [row["method_id"] for row in topology_rows]
            y = np.arange(len(labels), dtype=float)
            height = 0.24
            for index, (field, label, color) in enumerate((("chi_square_central_95_coverage", "Central 95%", "#4C78A8"), ("lower_tail_rate", "Lower tail", "#F28E2B"), ("upper_tail_rate", "Upper tail", "#36A165"))):
                ax.barh(y + (index - 1) * height, [_num(row, field) for row in topology_rows], height=height, label=label, color=color, alpha=0.88)
            ax.set_yticks(y, labels, fontsize=13)
            ax.invert_yaxis()
            ax.set_xlabel("Fraction")
            ax.set_title("Chi-square coverage by topology", fontweight="semibold")
            ax.legend(frameon=False, loc="lower right")
        draws = (nis, coverage)
    else:
        raise KeyError(family.plot_id)
    return _render(family, output_dir, draws, **kwargs)


def _ratio_bar(ax: Any, rows: list[dict[str, Any]], fields: tuple[str, ...], title: str) -> None:
    _bar(ax, rows, fields, "Residual / tolerance", title, log=True)
    ax.axhline(1, color="#333333", linestyle="--", lw=2, label="Tolerance")
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        # Two columns keep HAR07's three-item orientation legend inside its
        # own axes while leaving every entry below, rather than over, the bars.
        ncol=2,
    )
