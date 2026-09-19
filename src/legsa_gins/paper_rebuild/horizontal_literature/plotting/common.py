"""Generic, source-driven plotting primitives and output QA."""

from __future__ import annotations

import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .loaders import FrozenTable, categorical_values, finite_values
from .registry import PlotFamily
from .style import BASELINE_NOTE, METHOD_COLORS, add_scope_badge, color_for

FORMATS = ("png", "pdf", "svg")


def artifact_path(output_dir: Path, plot_id: str, component: str, fmt: str) -> Path:
    return output_dir / f"{plot_id}_{component}.{fmt}"


def expected_artifacts(
    output_dir: Path, family: PlotFamily, formats: Iterable[str]
) -> list[Path]:
    components = ["COMPOSITE"] + [f"PANEL_{chr(65 + i)}" for i in range(family.panel_count)]
    return [artifact_path(output_dir, family.plot_id, component, fmt) for component in components for fmt in formats]


def validate_artifact(path: Path, *, min_long_edge: int = 3840) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size == 0:
        return False, "missing_or_empty"
    suffix = path.suffix.lower()
    if suffix == ".png":
        try:
            from PIL import Image, ImageStat

            with Image.open(path) as image:
                image.load()
                if max(image.size) < min_long_edge:
                    return False, f"under_4k:{image.size[0]}x{image.size[1]}"
                thumb = image.convert("RGB")
                thumb.thumbnail((256, 256))
                extrema = ImageStat.Stat(thumb).extrema
                if all(low == high for low, high in extrema):
                    return False, "blank_canvas"
        except Exception as exc:  # Pillow reports exact decode reason.
            return False, f"decode_error:{exc}"
    elif suffix == ".pdf":
        with path.open("rb") as stream:
            header = stream.read(5)
        if path.stat().st_size < 100 or not header.startswith(b"%PDF-"):
            return False, "invalid_pdf"
    elif suffix == ".svg":
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            head = stream.read(4096).lower()
        if "<svg" not in head:
            return False, "invalid_svg"
    else:
        return False, "unknown_format"
    return True, "ok"


def _atomic_savefig(
    fig: Any, target: Path, *, fmt: str, dpi: int, force_rewrite: bool = False
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force_rewrite:
        valid, _ = validate_artifact(target)
        if valid:
            return
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        fig.savefig(temp, format=fmt, dpi=dpi, facecolor="white")
        with temp.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temp, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            try:
                os.fsync(directory_fd)
            except OSError:
                # DrvFS can reject directory fsync even after the file fsync succeeds.
                pass
        finally:
            os.close(directory_fd)
    finally:
        temp.unlink(missing_ok=True)


def _labels(table: FrozenTable, family: PlotFamily) -> list[str]:
    field = family.category_field or family.x_field
    if field and field in table.columns:
        return [str(row.get(field, "NA")) for row in table.rows]
    return [str(index) for index in range(len(table.rows))]


def _sample_indices(length: int, maximum: int = 2500) -> range | list[int]:
    if length <= maximum:
        return range(length)
    step = length / maximum
    return [min(length - 1, int(i * step)) for i in range(maximum)]


def _short_label(value: object, maximum: int = 30) -> str:
    label = str(value).replace("_", " ")
    return label if len(label) <= maximum else f"{label[: maximum - 1]}…"


def _numeric_or_counts(table: FrozenTable, family: PlotFamily) -> tuple[list[str], list[list[float]], list[str]]:
    labels = _labels(table, family)
    series: list[list[float]] = []
    names: list[str] = []
    for field in family.y_fields:
        values: list[float] = []
        usable = True
        for row in table.rows:
            value = row.get(field)
            if isinstance(value, bool):
                values.append(float(value))
            elif isinstance(value, (int, float)) and math.isfinite(float(value)):
                values.append(float(value))
            else:
                values.append(float("nan"))
        if any(math.isfinite(value) for value in values):
            series.append(values)
            names.append(field)
        else:
            usable = False
        if not usable:
            continue
    if series:
        return labels, series, names
    category = family.category_field or family.x_field
    if category:
        counts = Counter(categorical_values(table, category))
        return list(counts), [list(map(float, counts.values()))], ["row_count"]
    raise ValueError(f"{family.plot_id}: no finite numeric or categorical values")


def _semantic_color(label: str, family: PlotFamily, index: int) -> str:
    upper_label = label.upper()
    for method, color in METHOD_COLORS.items():
        if method.upper() in upper_label:
            return color
    layer_matches = [
        color
        for method, color in METHOD_COLORS.items()
        if method.upper() in family.method_layer.upper()
    ]
    if len(set(layer_matches)) == 1:
        return layer_matches[0]
    return color_for(label, index)


def _line_style(label: str, series_index: int) -> str:
    upper = label.upper()
    if "REFERENCE" in upper or "EXT04" in upper:
        return "--"
    return ("-", "-.", ":")[series_index % 3]


def _category_groups(table: FrozenTable, field: str) -> dict[str, list[int]]:
    if not field or field not in table.columns:
        return {}
    groups: dict[str, list[int]] = {}
    for index, row in enumerate(table.rows):
        value = row.get(field)
        if value is not None:
            groups.setdefault(str(value), []).append(index)
    return groups if 1 < len(groups) <= 12 else {}


def _draw_primary(ax: Any, table: FrozenTable, family: PlotFamily) -> None:
    import numpy as np

    labels, series, names = _numeric_or_counts(table, family)
    kind = family.plot_kind
    if kind == "ecdf":
        groups = _category_groups(table, family.category_field)
        for series_index, (values, name) in enumerate(zip(series, names)):
            group_items = groups.items() if groups else [(name, list(range(len(values))))]
            for group_index, (group, indices) in enumerate(group_items):
                finite = np.asarray(
                    [values[index] for index in indices if index < len(values) and math.isfinite(values[index])],
                    dtype=float,
                )
                finite.sort()
                if finite.size:
                    label = f"{group} · {name}" if groups else name
                    ax.plot(
                        finite,
                        np.arange(1, finite.size + 1) / finite.size,
                        lw=3.0,
                        color=_semantic_color(group, family, group_index),
                        linestyle=_line_style(group, series_index + group_index),
                        label=label,
                    )
        ax.set_ylabel("Empirical CDF")
        ax.set_xlabel("Value")
    elif kind in {"line", "timeline", "scatter"}:
        x_values: list[float] = []
        for row_index, row in enumerate(table.rows):
            value = row.get(family.x_field) if family.x_field else row_index
            x_values.append(float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else float(row_index))
        groups = _category_groups(table, family.category_field)
        for series_index, (values, name) in enumerate(zip(series, names)):
            group_items = groups.items() if groups else [(name, list(range(len(table.rows))))]
            for group_index, (group, indices) in enumerate(group_items):
                sampled = list(_sample_indices(len(indices)))
                selected = [indices[index] for index in sampled]
                points = [(x_values[i], values[i]) for i in selected if i < len(values) and math.isfinite(values[i])]
                if not points:
                    continue
                xs, ys = zip(*points)
                label = f"{group} · {name}" if groups else name
                color = _semantic_color(group, family, group_index)
                if kind == "scatter":
                    ax.scatter(xs, ys, s=24, alpha=0.58, color=color, label=label)
                else:
                    ax.plot(xs, ys, lw=2.6, color=color, linestyle=_line_style(group, series_index + group_index), label=label)
        ax.set_xlabel(family.x_field or "Row index")
        ax.set_ylabel(" / ".join(names))
    elif kind == "heatmap":
        if family.plot_id == "RAW12_YANG_MODE_STATE_GRID":
            layout_engine = ax.figure.get_layout_engine()
            if layout_engine is not None:
                layout_engine.set(w_pad=0.9, wspace=0.08)
            row_labels = []
            matrix_rows = []
            system_labels = {
                "GPS_DUAL_FREQUENCY": "GPS",
                "BDS_DUAL_FREQUENCY": "BDS",
                "GPS_BDS_DUAL_FREQUENCY": "G+B",
            }
            for row in table.rows:
                sigma = row.get("baseline_sigma_m")
                constraint = str(row.get("constraint_mode"))
                constraint_label = "UC" if constraint == "UNCONSTRAINED" else "C"
                sigma_label = "" if sigma is None else f" {float(sigma):g}"
                row_labels.append(
                    f"{system_labels.get(str(row.get('system_mode')), row.get('system_mode'))} "
                    f"{constraint_label}{sigma_label}"
                )
                matrix_rows.append(
                    [
                        float(row[field])
                        if isinstance(row.get(field), (int, float, bool))
                        else float("nan")
                        for field in family.y_fields
                    ]
                )
            matrix = np.asarray(matrix_rows, dtype=float)
            image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
            ax.set_yticks(
                range(len(row_labels)),
                [_short_label(label, 62) for label in row_labels],
                fontsize=13,
            )
            ax.set_xticks(
                range(len(family.y_fields)),
                [_short_label(field, 28) for field in family.y_fields],
                rotation=25,
                ha="right",
                fontsize=13,
            )
            ax.set_xlabel(
                "10 EXT03 modes; G+B=GPS+BDS; UC=unconstrained\n"
                "C=constrained (trailing value is sigma [m]); no error-based selection"
            )
            ax.figure.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
            ax.set_title(family.title, fontsize=29, pad=18, fontweight="semibold")
            return
        row_field = family.x_field
        col_field = family.category_field
        value_field = family.y_fields[0]
        rows = list(table.rows)
        selected_metric = ""
        if "metric_name" in table.columns:
            metrics = sorted({str(row.get("metric_name")) for row in rows if row.get("metric_name") is not None})
            priorities = ("horizontal_rmse_m", "yaw_rmse_deg", "coverage_ratio")
            selected_metric = next((metric for metric in priorities if metric in metrics), metrics[0] if metrics else "")
            if selected_metric:
                rows = [row for row in rows if str(row.get("metric_name")) == selected_metric]
        row_labels = sorted({str(row.get(row_field)) for row in rows if row.get(row_field) is not None})[:80]
        col_labels = sorted({str(row.get(col_field)) for row in rows if row.get(col_field) is not None})[:80]
        if row_labels and col_labels:
            matrix = np.full((len(row_labels), len(col_labels)), np.nan)
            for row in rows:
                row_label = str(row.get(row_field))
                col_label = str(row.get(col_field))
                value = row.get(value_field)
                if row_label in row_labels and col_label in col_labels and isinstance(value, (int, float, bool)):
                    cell = (row_labels.index(row_label), col_labels.index(col_label))
                    if not math.isfinite(matrix[cell]):
                        matrix[cell] = float(value)
            image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
            ax.set_yticks(range(len(row_labels)), [_short_label(label) for label in row_labels], fontsize=13)
            ax.set_xticks(range(len(col_labels)), [_short_label(label) for label in col_labels], rotation=60, ha="right", fontsize=12)
            if selected_metric:
                ax.set_xlabel(f"Frozen metric: {selected_metric}")
        else:
            matrix = np.asarray(series, dtype=float)
            if matrix.shape[1] > 120:
                matrix = matrix[:, list(_sample_indices(matrix.shape[1], 120))]
            image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="viridis")
            ax.set_yticks(range(len(names)), names)
            ax.set_xlabel("Source rows (deterministically sampled)")
        ax.figure.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    elif kind == "matrix":
        row_field = family.x_field
        col_field = family.category_field
        value_field = family.y_fields[0] if family.y_fields else ""
        row_labels = sorted(set(categorical_values(table, row_field)))
        col_labels = sorted(set(categorical_values(table, col_field)))
        if not row_labels or not col_labels:
            raise ValueError(f"{family.plot_id}: matrix axes unavailable")
        numeric_map: dict[str, float] = {}
        matrix = np.full((len(row_labels), len(col_labels)), np.nan)
        for row in table.rows:
            if row.get(row_field) is None or row.get(col_field) is None:
                continue
            value = row.get(value_field)
            if not isinstance(value, (int, float, bool)):
                key = str(value)
                if key not in numeric_map:
                    numeric_map[key] = float(len(numeric_map))
                value = numeric_map[key]
            matrix[row_labels.index(str(row[row_field])), col_labels.index(str(row[col_field]))] = float(value)
        image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="cividis")
        ax.set_yticks(range(len(row_labels)), [_short_label(label) for label in row_labels], fontsize=13)
        ax.set_xticks(range(len(col_labels)), [_short_label(label) for label in col_labels], rotation=60, ha="right", fontsize=12)
        ax.figure.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    else:
        x = np.arange(len(labels), dtype=float)
        width = min(0.8 / max(1, len(series)), 0.28)
        hatches = ("", "//", "xx", "..", "\\\\", "++")
        for index, (values, name) in enumerate(zip(series, names)):
            offset = (index - (len(series) - 1) / 2.0) * width
            colors = [_semantic_color(label, family, label_index) for label_index, label in enumerate(labels)]
            hatch = "///" if "EXT04" in family.method_layer.upper() else hatches[index % len(hatches)]
            ax.bar(
                x + offset,
                values,
                width=width,
                color=colors,
                label=name,
                alpha=0.88,
                edgecolor="#333333",
                linewidth=0.7,
                hatch=hatch,
            )
        if len(labels) <= 40:
            ax.set_xticks(x, [_short_label(label) for label in labels], rotation=55 if len(labels) > 8 else 0, ha="right" if len(labels) > 8 else "center")
        else:
            ax.set_xticks([])
            ax.set_xlabel(f"{len(labels)} source rows")
        ax.set_ylabel("Frozen source value")
    if len(names) > 1:
        ax.legend(frameon=False, loc="best", fontsize=18)
    ax.set_title(family.title, fontsize=29, pad=18, fontweight="semibold")


def _draw_profile(ax: Any, table: FrozenTable, family: PlotFamily) -> None:
    import numpy as np

    fields = list(family.y_fields) or list(family.required_fields)
    names: list[str] = []
    coverage: list[float] = []
    for field in fields[:12]:
        present = sum(row.get(field) is not None for row in table.rows)
        names.append(_short_label(field, 34))
        coverage.append(present / len(table.rows))
    if not names:
        names = ["source rows"]
        coverage = [1.0]
    positions = np.arange(len(names))
    ax.barh(positions, coverage, color=[color_for(name, i) for i, name in enumerate(names)], alpha=0.85)
    ax.set_yticks(positions, names, fontsize=15)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Finite / populated row fraction")
    ax.set_title("Frozen-source field coverage", fontsize=27, pad=18, fontweight="semibold")
    for pos, value in zip(positions, coverage):
        ax.text(min(1.02, value + 0.015), pos, f"{100*value:.1f}%", va="center", fontsize=15)
    ax.text(
        0.0,
        -0.16,
        f"Source: {'/'.join(table.source.parts[-4:])}\nRows: {len(table.rows):,} | Columns: {len(table.columns):,}",
        transform=ax.transAxes,
        fontsize=13,
        va="top",
        color="#444444",
        wrap=True,
    )


def _caption(family: PlotFamily) -> str:
    lines = [family.caption]
    if "BASELINE_LENGTH" in family.plot_id:
        lines.append(BASELINE_NOTE)
    return "\n".join(line for line in lines if line)


def _new_figure(plt: Any, width_px: int, height_px: int, dpi: int, panels: int) -> tuple[Any, list[Any]]:
    fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    axes = fig.subplots(1, panels, squeeze=False)[0].tolist()
    fig.subplots_adjust(
        left=0.105 if panels == 1 else 0.075,
        right=0.97,
        bottom=0.20,
        top=0.82,
        wspace=0.34,
    )
    return fig, axes


def render_dataset_family(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    *,
    formats: tuple[str, ...],
    dpi: int,
    composite_pixels: tuple[int, int],
    panel_pixels: tuple[int, int],
    force_rewrite: bool = False,
) -> list[str]:
    import matplotlib.pyplot as plt

    written: list[str] = []
    fig, axes = _new_figure(plt, *composite_pixels, dpi, family.panel_count)
    try:
        _draw_primary(axes[0], table, family)
        if family.panel_count == 2:
            _draw_profile(axes[1], table, family)
        add_scope_badge(fig, family.scope_label)
        fig.suptitle(family.plot_id, fontsize=35, fontweight="bold")
        fig.text(0.01, 0.01, _caption(family), ha="left", va="bottom", fontsize=14, color="#333333")
        for fmt in formats:
            target = artifact_path(output_dir, family.plot_id, "COMPOSITE", fmt)
            _atomic_savefig(
                fig, target, fmt=fmt, dpi=dpi, force_rewrite=force_rewrite
            )
            written.append(str(target))
    finally:
        plt.close(fig)
    draw_functions = [_draw_primary, _draw_profile]
    for panel_index in range(family.panel_count):
        fig, axes = _new_figure(plt, *panel_pixels, dpi, 1)
        try:
            draw_functions[panel_index](axes[0], table, family)
            add_scope_badge(fig, family.scope_label)
            fig.suptitle(f"{family.plot_id} — Panel {chr(65 + panel_index)}", fontsize=32, fontweight="bold")
            fig.text(0.01, 0.01, _caption(family), ha="left", va="bottom", fontsize=12, color="#333333")
            for fmt in formats:
                target = artifact_path(output_dir, family.plot_id, f"PANEL_{chr(65 + panel_index)}", fmt)
                _atomic_savefig(
                    fig, target, fmt=fmt, dpi=dpi, force_rewrite=force_rewrite
                )
                written.append(str(target))
        finally:
            plt.close(fig)
    return written
