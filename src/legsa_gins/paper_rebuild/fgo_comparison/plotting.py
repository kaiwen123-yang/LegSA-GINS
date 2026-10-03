"""Three compact publication composites from completed FGO evaluations.

No solver/evaluator imports, raw reference reads, new errors, method
interpolation, or trajectory reconstruction from errors. Figures show full
own-valid support, not a common-support selection. Common-support numbers
belong in the separate comparison table.

Panels: GNSS1-antenna and POI-midpoint trajectories, horizontal/vertical/heading
errors, and actual GNC weights with native output epochs. H/U use one fixed
symlog rule: linear inside +/-1 m, every finite extreme retained. Dense marks
may be rasterized at 600 dpi inside PDF/SVG; axes and labels remain vector.
Actual rendering and raster visual QA are separate actions of the caller.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import struct

import numpy as np
import pandas as pd


STYLES = {
    "GNC": {"label": "FGO-GNC", "color": "#0072B2", "ls": (0, (4, 1.5))},
    "WEN_TC": {"label": "Wen TC", "color": "#D55E00", "ls": (0, (1, 1.2))},
    "OISAM": {"label": "OiSAM-FGO", "color": "#758B28", "ls": "-"},
    "V3_F04": {"label": "V3 F04", "color": "#A1477D", "ls": (0, (6, 1.5, 1, 1.5))},
    "LC01": {"label": "LC01", "color": "#B88A00", "ls": (0, (7, 2.2))},
}
NEW_METHODS = ("GNC", "WEN_TC", "OISAM")
XYZ = ["x_ecef_m", "y_ecef_m", "z_ecef_m"]


class PlotInputError(ValueError):
    """A completed evaluation or unambiguous source descriptor is missing."""


def _resolve(value, roots):
    text = str(value)
    for alias, root in sorted(roots.items(), key=lambda item: -len(item[0])):
        text = text.replace(alias, str(root))
    if "<" in text or ">" in text:
        raise PlotInputError("Unresolved plotting source alias: " + text)
    return Path(text)


def _portable(path, roots):
    value = str(path)
    for alias, root in sorted(roots.items(), key=lambda item: -len(str(item[1]))):
        if value == str(root) or value.startswith(str(root).rstrip("/") + "/"):
            return alias + value[len(str(root)):]
    return value


def _read_table(path, roots, *, usecols=None):
    path = Path(path)
    # Derived Truth CSVs are products of a separate completed evaluation.
    raw = Path(roots["<RAW_ROOT>"]).absolute()
    absolute = path.absolute()
    if absolute == raw or raw in absolute.parents or path.name.lower().startswith("trace"):
        raise PlotInputError("Raw/reference payload is outside plotting input scope")
    if not path.is_file():
        raise PlotInputError("Required evaluated table is missing: " + _portable(path, roots))
    return pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)


def _valid_values(values):
    a = pd.Series(values)
    if pd.api.types.is_numeric_dtype(a) or pd.api.types.is_bool_dtype(a):
        return pd.to_numeric(a, errors="coerce").to_numpy(float) > 0
    return a.astype(str).str.lower().isin(("true", "1", "1.0")).to_numpy()


def _window(frame, window, *, time_column="time", valid_column="valid"):
    result = frame.copy()
    if time_column not in result:
        raise PlotInputError("Time column missing from evaluated table: " + time_column)
    result["time"] = pd.to_numeric(result[time_column], errors="coerce")
    result = result.loc[result.time.notna() & (result.time >= window[0]) & (result.time <= window[1])].copy()
    result = result.sort_values("time", kind="stable").reset_index(drop=True)
    result["plot_valid"] = (_valid_values(result[valid_column])
                            if valid_column and valid_column in result else np.ones(len(result), dtype=bool))
    return result


def _descriptor_frame(descriptor, roots, window):
    if not descriptor or not descriptor.get("exists", Path(descriptor.get("path", "")).is_file()):
        return None
    if descriptor.get("time_basis") != "sequence_relative_seconds":
        raise PlotInputError("Retained time basis is not declared sequence-relative seconds")
    columns = descriptor.get("columns", {})
    required = {descriptor["time_column"], *columns.values(), *descriptor.get("filters", {})}
    if descriptor.get("valid_column"):
        required.add(descriptor["valid_column"])
    frame = _read_table(_resolve(descriptor["path"], roots), roots, usecols=sorted(required))
    for key, value in descriptor.get("filters", {}).items():
        frame = frame.loc[frame[key].astype(str) == str(value)]
    frame["time"] = pd.to_numeric(frame[descriptor["time_column"]], errors="coerce")
    frame["plot_valid"] = (_valid_values(frame[descriptor["valid_column"]])
                            if descriptor.get("valid_column") else np.ones(len(frame), bool))
    for unified, original in columns.items():
        frame[unified] = pd.to_numeric(frame[original], errors="coerce")
    return _window(frame, window, valid_column="plot_valid")


def _segments(time, x, y, valid, cadence_s=None):
    """Insert breaks; never interpolate or remove either endpoint of a gap."""
    time, x, y = (np.asarray(v, float) for v in (time, x, y))
    valid = np.asarray(valid, bool) & np.isfinite(time) & np.isfinite(x) & np.isfinite(y)
    delta = np.diff(time)
    positive = delta[delta > 0]
    cadence = float(cadence_s) if cadence_s is not None else (float(np.median(positive)) if len(positive) else None)
    split = np.flatnonzero((delta > 1.5 * cadence) | (delta <= 0)) + 1 if cadence else np.empty(0, int)
    xx, yy = x.copy(), y.copy()
    xx[~valid], yy[~valid] = np.nan, np.nan
    if len(split):
        xx, yy = np.insert(xx, split, np.nan), np.insert(yy, split, np.nan)
    return xx, yy, {"finite_count": int(valid.sum()), "cadence_s": cadence,
                    "time_gap_breaks": len(split), "invalid_row_count": int((~valid).sum()),
                    "x_min": float(x[valid].min()) if valid.any() else None,
                    "x_max": float(x[valid].max()) if valid.any() else None,
                    "y_min": float(y[valid].min()) if valid.any() else None,
                    "y_max": float(y[valid].max()) if valid.any() else None}


def _ecef_from_llh(latitude, longitude, height):
    latitude, longitude = np.deg2rad(latitude), np.deg2rad(longitude)
    radius = 6378137. / np.sqrt(1. - 6.6943799901413165e-3 * np.sin(latitude) ** 2)
    return np.column_stack(((radius + height) * np.cos(latitude) * np.cos(longitude),
        (radius + height) * np.cos(latitude) * np.sin(longitude),
        (radius * (1. - 6.6943799901413165e-3) + height) * np.sin(latitude)))


def _enu_rotation(origin):
    """WGS84 display frame only: no fitted alignment or output correction."""
    x, y, z = np.asarray(origin, float)
    horizontal = np.hypot(x, y)
    if horizontal < 1 or np.linalg.norm(origin) < 1e6:
        raise PlotInputError("Invalid Earth-fixed origin for local trajectory axes")
    lon = np.arctan2(y, x)
    lat = np.arctan2(z, horizontal * (1 - 6.6943799901413165e-3))
    for _ in range(10):
        radius = 6378137. / np.sqrt(1 - 6.6943799901413165e-3 * np.sin(lat)**2)
        lat = np.arctan2(z + 6.6943799901413165e-3 * radius * np.sin(lat), horizontal)
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    return np.array([[-so, co, 0.], [-sl*co, -sl*so, cl], [cl*co, cl*so, sl]])


def _series_line(axis, frame, column, style, summary):
    if frame is None or column not in frame:
        return 0
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(float)
    time = frame.time.to_numpy(float)
    x, y, counts = _segments(time, time, values, frame.plot_valid)
    dense = counts["finite_count"] > 5000
    if counts["finite_count"]:
        axis.plot(x, y, color=style["color"], linestyle=style["ls"], linewidth=.85,
                  marker="." if counts["finite_count"] < 3 else None, markersize=3,
                  rasterized=dense, label=style["label"])
    summary.append({"series": style["label"], "panel": axis.get_gid(), "field": column, **counts,
                    "rasterized_in_vector_export": dense})
    return counts["finite_count"]


def _trajectory_line(axis, frame, style, origin, rotation, summary):
    if frame is None or not set(XYZ).issubset(frame):
        return 0
    ecef = frame[XYZ].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    enu = (ecef - origin) @ rotation.T
    x, y, counts = _segments(frame.time, enu[:, 0], enu[:, 1], frame.plot_valid, style.get('cadence_s'))
    dense = counts["finite_count"] > 5000
    if counts["finite_count"]:
        axis.plot(x, y, color=style["color"], linestyle=style["ls"], linewidth=.85,
                  marker="." if counts["finite_count"] < 3 else None, markersize=3,
                  rasterized=dense, label=style["label"])
    summary.append({"series": style["label"], "panel": axis.get_gid(), "field": "actual_trajectory", **counts,
                    "rasterized_in_vector_export": dense})
    return counts["finite_count"]


def _time_axis(axis, window):
    axis.set_xlim(*window)
    axis.set_xticks(np.unique(np.r_[window[0], np.rint(np.linspace(*window, 5)[1:-1]), window[1]]))
    axis.set_xlabel("Sequence time (s)")
    axis.ticklabel_format(axis="x", style="plain", useOffset=False)


def render_sequence(roots_path, sequence):
    """Render one registered sequence, returning sources, support and QA state.

    Inputs: completed EVALUATION.json, three method *_ERRORS.csv and
    *_TRAJECTORY.csv, and two TRUTH_*.csv products. A failed method's empty
    table is valid input and is visibly labelled. Missing tables or ambiguous
    physical points raise PlotInputError. V3/LC01 are read exclusively through
    retained_results source descriptors.

    Each render retains an external revision. The docs figures directory gets
    only current per-sequence PNG/PDF/SVG composites. Raster review is returned
    as PENDING: successful saving does not certify visual QA.
    """
    if sequence not in ("BY2", "BY2H", "BY2O"):
        raise PlotInputError("Sequence is outside the registered comparison")
    roots = json.loads(Path(roots_path).read_text(encoding="utf-8"))["aliases"]
    root = Path(roots["<FGO_ROOT>"])
    evaluated = Path(roots.get("<FGO_EVALUATION_ROOT>", root / "evaluation")) / sequence
    evaluation = json.loads((evaluated / "EVALUATION.json").read_text(encoding="utf-8"))
    own = {r["method_id"]: r for r in evaluation["rows"] if r["support"] == "OWN_VALID"}
    if set(NEW_METHODS) - own.keys():
        raise PlotInputError("Evaluation must register all three methods, including failed ones")
    windows = {(float(own[m]["window_start_s"]), float(own[m]["window_end_s"])) for m in NEW_METHODS}
    if len(windows) != 1 or evaluation["sequence"] != sequence:
        raise PlotInputError("Method window/sequence identity mismatch")
    window = windows.pop()
    summary = {"sequence": sequence, "window_s": list(window), "support": "FULL_OWN_VALID",
        "common_support_filter_used": False, "output_interpolation": False,
        "trajectory_from_errors_reconstruction": False, "trace_payload_reads": 0,
        "sources": [], "warnings": [], "series": [], "native_output_support": {},
        "trajectory_unavailable": [], "retained_boundaries": [],
        "visual_qa": "PENDING_ACTUAL_RASTER_REVIEW"}
    sources, errors, trajectories, native, styles = summary["sources"], {}, {}, {}, {}
    for method in NEW_METHODS:
        expected_point = "POI_MIDPOINT" if method == "OISAM" else "GNSS1_ANTENNA"
        if own[method]["physical_point"] != expected_point:
            raise PlotInputError("Unexpected evaluated physical point for " + method)
        ep, tp = evaluated / (method + "_ERRORS.csv"), evaluated / (method + "_TRAJECTORY.csv")
        errors[method] = _window(_read_table(ep, roots), window)
        trajectories[method] = _window(_read_table(tp, roots), window)
        styles[method] = STYLES[method].copy()
        sources.extend([_portable(ep, roots), _portable(tp, roots)])
        native[method] = _resolve(own[method]["source_path"], roots).parent
    truth = {}
    for point in ("POI_MIDPOINT", "GNSS1_ANTENNA"):
        path = evaluated / ("TRUTH_" + point + ".csv")
        truth[point] = _window(_read_table(path, roots), window, valid_column=None)
        if not len(truth[point]) or not np.isfinite(truth[point][XYZ].to_numpy(float)).all():
            raise PlotInputError("Finite derived Truth trajectory is unavailable at " + point)
        sources.append(_portable(path, roots))

    from .retained_results import read_retained
    retained = [row for row in read_retained(roots, sequence)
                if row["method_id"] in ("V3_F04", "LC01") and row["support"] == "RETAINED_OWN_VALID"]
    seen = set()
    retained_trajectories = {}
    for row in retained:
        method, start = row["method_id"], row.get("start_policy", "")
        summary["retained_boundaries"].append({key: row.get(key) for key in
            ("method_id", "start_policy", "comparison_boundary", "geometric_audit_status", "physical_point")})
        key = method + ("_" + start if start else "")
        if key in seen:
            raise PlotInputError("Ambiguous retained own-support identity: " + key)
        seen.add(key)
        style = STYLES[method].copy()
        if method == "LC01" and sum(r["method_id"] == method for r in retained) > 1:
            short = {"FILE_START": "FS", "CONTRACT_START": "CS"}.get(start, start)
            style["label"] += " (" + short + ")"
            if start == "CONTRACT_START":
                style["ls"] = (0, (2, 1, 1, 1))
        styles[key] = style
        descriptor = row.get("error_series")
        errors[key] = _descriptor_frame(descriptor, roots, window)
        if errors[key] is None:
            summary["warnings"].append(style["label"] + ": retained error series unavailable")
        else:
            sources.append(descriptor.get("source_path", _portable(descriptor["path"], roots)))
        descriptor = row.get("trajectory")
        if descriptor and descriptor.get("physical_point") == "POI_MIDPOINT":
            frame = _descriptor_frame(descriptor, roots, window)
            if frame is not None and {"latitude_deg", "longitude_deg", "height_m"}.issubset(frame):
                frame[XYZ] = _ecef_from_llh(frame.latitude_deg.to_numpy(float), frame.longitude_deg.to_numpy(float), frame.height_m.to_numpy(float))
            if frame is not None and set(XYZ).issubset(frame):
                retained_trajectories[key] = frame
                sources.append(descriptor.get("source_path", _portable(descriptor["path"], roots)))
        if key not in retained_trajectories:
            summary["trajectory_unavailable"].append(style["label"])
    for method in ("V3_F04", "LC01"):
        if not any(row["method_id"] == method for row in retained):
            summary["warnings"].append(method + ": no retained navigation registration")

    # Import rendering only after source registration, never solver/evaluator.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    origin = truth["POI_MIDPOINT"][XYZ].iloc[0].to_numpy(float)
    rotation = _enu_rotation(origin)
    summary["display_frame"] = "WGS84 ENU at first derived POI Truth epoch; one shared origin for both physical-point panels"
    summary["display_origin_ecef_m"] = origin.tolist()
    rc = {"font.family": "DejaVu Sans", "font.size": 8., "axes.labelsize": 8.,
          "xtick.labelsize": 7., "ytick.labelsize": 7., "legend.fontsize": 7.4,
          "axes.spines.top": False, "axes.spines.right": False,
          "axes.edgecolor": "#555555", "axes.labelcolor": "#222222", "text.color": "#222222",
          "grid.color": "#DADADA", "grid.linewidth": .45, "grid.alpha": .75,
          "pdf.fonttype": 42, "svg.fonttype": "none", "path.simplify": False,
          "agg.path.chunksize": 10000, "savefig.facecolor": "white"}
    with plt.rc_context(rc):
        fig = plt.figure(figsize=(7.2, 8.2), facecolor="white")
        grid = fig.add_gridspec(3, 2, left=.09, right=.985, bottom=.055, top=.922, hspace=.46, wspace=.36)
        a, b, c, d, e = [fig.add_subplot(grid[r, col]) for r, col in ((0, 0), (0, 1), (1, 0), (1, 1), (2, 0))]
        sub = grid[2, 1].subgridspec(2, 1, height_ratios=(2., 1.), hspace=.14)
        f = fig.add_subplot(sub[0]); gaps = fig.add_subplot(sub[1], sharex=f)
        axes = [a, b, c, d, e, f]
        for label, axis in zip("abcdef", axes):
            axis.set_gid(label)
            axis.set_title("(" + label + ")", loc="left", fontsize=9., pad=5)
            axis.grid(True)
            axis.set_axisbelow(True)
        # The frozen reference has paired messages within each 10 Hz packet.
        # Median adjacent dt is a within-packet separation, not its cadence;
        # using it would make the actual Truth trajectory almost invisible.
        # Keep every reference row and break at genuine >0.15s packet gaps.
        truth_style = {"label": "Truth", "color": "#202020", "ls": "-", "cadence_s": .1}
        for axis, point, methods in ((a, "GNSS1_ANTENNA", ("GNC", "WEN_TC")), (b, "POI_MIDPOINT", ("OISAM",))):
            _trajectory_line(axis, truth[point], truth_style, origin, rotation, summary["series"])
            missing = []
            for method in methods:
                if not _trajectory_line(axis, trajectories[method], styles[method], origin, rotation, summary["series"]):
                    missing.append(styles[method]["label"])
            if point == "POI_MIDPOINT":
                for key, frame in retained_trajectories.items():
                    _trajectory_line(axis, frame, styles[key], origin, rotation, summary["series"])
                if summary["trajectory_unavailable"]:
                    note = "No retained trajectory:\n" + ", ".join(summary["trajectory_unavailable"])
                    axis.text(.02, .02, note, transform=axis.transAxes, fontsize=6.1, va="bottom", wrap=True)
            if missing:
                axis.text(.02, .10, "No position output: " + ", ".join(missing), transform=axis.transAxes, fontsize=6.6, wrap=True)
                summary["warnings"].append("No position output: " + ", ".join(missing))
            axis.set_xlabel("East at " + ("GNSS1 antenna" if point == "GNSS1_ANTENNA" else "POI midpoint") + " (m)")
            axis.set_ylabel("North (m)")
            axis.set_aspect("equal", adjustable="datalim")
            axis.margins(.08)
        for axis, field, label in ((c, "horizontal_err_m", "Horizontal error (m)"),
                                   (d, "err_u_m", "Vertical error (m)"),
                                   (e, "yaw_err_deg", "Heading error (deg)")):
            present = 0
            for key, frame in errors.items():
                if field == "yaw_err_deg" and key in ("GNC", "WEN_TC"):
                    continue
                present += _series_line(axis, frame, field, styles[key], summary["series"])
            axis.axhline(0, color="#666666", linewidth=.5, zorder=0)
            if field != "yaw_err_deg":
                axis.set_yscale("symlog", linthresh=1., linscale=1.)
                axis.text(.02, .97, "Symlog; linear within ±1 m", transform=axis.transAxes,
                          va="top", fontsize=6.4, color="#555555")
                if field == "horizontal_err_m":
                    axis.set_ylim(bottom=0.)
            if not present:
                axis.text(.5, .5, "No evaluated output", transform=axis.transAxes, ha="center", fontsize=8.)
                summary["warnings"].append(label + ": no finite own-support samples")
            axis.set_ylabel(label)
            _time_axis(axis, window)
            axis.margins(y=.10)

        weight_path = native["GNC"] / "WEIGHTS.npz"
        gnc_state_path = native["GNC"] / "STATES.csv"
        weight_count = 0
        if weight_path.is_file() and gnc_state_path.is_file():
            state_times = _read_table(gnc_state_path, roots, usecols=["time_rel_s"])["time_rel_s"].to_numpy(float)
            with np.load(weight_path, allow_pickle=False) as saved:
                index, weights = np.asarray(saved["epoch_index"], int), np.asarray(saved["weights"], float)
            if index.shape != weights.shape or np.any((index < 0) | (index >= len(state_times))):
                raise PlotInputError("GNC weight/epoch identity mismatch")
            times = state_times[index]
            mask = np.isfinite(weights) & (times >= window[0]) & (times <= window[1])
            if np.any((weights[mask] < 0) | (weights[mask] > 1 + 1e-12)):
                raise PlotInputError("Saved GNC weights are outside [0,1]")
            weight_count = int(mask.sum())
            if weight_count:
                f.scatter(times[mask], weights[mask], s=2., marker=".", color="#777777", alpha=.3,
                          linewidths=0, rasterized=True)
                medians = np.full(len(state_times), np.nan)
                for i in np.unique(index[mask]):
                    medians[i] = np.median(weights[mask & (index == i)])
                xx, yy, _ = _segments(state_times, state_times, medians, np.isfinite(medians))
                f.plot(xx, yy, color=STYLES["GNC"]["color"], linewidth=.8)
                f.text(.02, .04, "Observations (grey); epoch median (blue)", transform=f.transAxes, fontsize=6.2)
            sources.extend([_portable(weight_path, roots), _portable(gnc_state_path, roots)])
        if not weight_count:
            f.text(.5, .5, "GNC weights unavailable", transform=f.transAxes, ha="center", fontsize=7.5)
            summary["warnings"].append("No saved finite GNC weights in the complete evaluation window")
        summary["gnc_weight_observation_count"] = weight_count
        f.set_ylabel("GNC weight")
        f.set_ylim(-.035, 1.055)
        f.set_yticks([0., .5, 1.])
        f.tick_params(axis="x", labelbottom=False)
        gaps.set_yticks(range(3), [STYLES[m]["label"] for m in NEW_METHODS], fontsize=6.5)
        gaps.set_ylim(2.6, -.6)
        gaps.set_ylabel("Output\nepochs", fontsize=7.)
        for y, method in enumerate(NEW_METHODS):
            gaps.hlines(y, *window, color="#DADADA", linewidth=5., zorder=0)
            path = native[method] / "STATES.csv"
            count = 0
            if path.is_file():
                frame = _window(_read_table(path, roots, usecols=["time_rel_s", "valid"]), window, time_column="time_rel_s")
                valid_times = frame.time.to_numpy(float)[frame.plot_valid.to_numpy(bool)]
                count = len(valid_times)
                gaps.plot(valid_times, np.full(count, y), linestyle="none", marker="|", markersize=5.,
                          markeredgewidth=.85, color=STYLES[method]["color"])
                sources.append(_portable(path, roots))
            else:
                summary["warnings"].append(STYLES[method]["label"] + ": native STATES.csv unavailable")
            summary["native_output_support"][method] = {"valid_epochs_in_window": count,
                "expected_window_epochs": int(own[method]["expected_epoch_count"]),
                "evaluated_matched_epochs": int(own[method]["matched_epoch_count"])}
        _time_axis(gaps, window)
        handles = [Line2D([], [], color=truth_style["color"], linewidth=.85, label="Truth")]
        handles += [Line2D([], [], color=style["color"], linestyle=style["ls"], linewidth=.85,
                           label=style["label"]) for style in styles.values()]
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.54, .994), ncol=4,
                   frameon=False, columnspacing=1.4, handlelength=2.8, handletextpad=.45)
        render_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        external = root / "figures" / sequence / render_id
        external.mkdir(parents=True, exist_ok=False)
        docs = Path(roots.get("<FGO_DOCS>", str(Path(roots["<CODE_ROOT>"]) / "docs/paper_rebuild/hext/FGO_COMPARISON"))) / "figures"
        docs.mkdir(parents=True, exist_ok=True)
        files = {}
        fig.canvas.draw()
        by_panel = dict(zip("abcdef", axes))
        for series in summary["series"]:
            if not series["finite_count"]:
                continue
            axis = by_panel[series["panel"]]
            for prefix, limits in (("x", axis.get_xlim()), ("y", axis.get_ylim())):
                tolerance = 1e-9 * max(1., abs(limits[0]), abs(limits[1]))
                if series[prefix + "_min"] < limits[0] - tolerance or series[prefix + "_max"] > limits[1] + tolerance:
                    raise PlotInputError("Axis clips a finite observed extreme: " + series["series"] + "/" + series["field"])
        summary["all_finite_extrema_inside_axes"] = True
        for extension in ("png", "pdf", "svg"):
            name = "FGO_" + sequence + "." + extension
            path = external / name
            fig.savefig(path, dpi=600, facecolor="white")
            shutil.copyfile(path, docs / name)
            files[extension] = {"external": _portable(path, roots), "publication": _portable(docs / name, roots),
                                "bytes": path.stat().st_size}
        summary["files"] = files
        with (external / ("FGO_" + sequence + ".png")).open("rb") as stream:
            header = stream.read(24)
        summary["png_dimensions_px"] = list(struct.unpack(">II", header[16:24]))
        if summary["png_dimensions_px"][0] < 4096:
            raise PlotInputError("PNG width is below the 4096 px publication minimum")
        summary["axis_limits"] = {label: {"x": list(axis.get_xlim()), "y": list(axis.get_ylim()), "yscale": axis.get_yscale()}
                                  for label, axis in zip("abcdef", axes)}
        plt.close(fig)
    summary["sources"] = list(dict.fromkeys(sources))
    summary["caption"] = (
        f"{sequence}, {window[0]:g}–{window[1]:g} s. (a) GNSS1-antenna trajectories; "
        "(b) POI-midpoint trajectories; (c) horizontal error; (d) signed vertical error; "
        "(e) signed heading error of methods that actually estimate attitude; "
        "(f) actual GNC observation weights and valid native output epochs (grey denotes absent output). "
        "All curves use their own complete available support; method gaps are not interpolated. "
        "The H/U axes use symlog with a fixed +/-1 m linear interval and retain every finite extreme. "
        "GNC/Wen positions are evaluated at GNSS1; OiSAM/V3/LC01 at POI, with different sensor inputs. "
        "These are application comparisons, not common-input rankings. FS/CS, when present, mean "
        "file-start/contract-start LC01. Missing retained NAV is not reconstructed from errors. "
        "GNC and Wen TC use offline full-batch optimization with future observations. "
        "Dense curves/weight marks are rasterized at 600 dpi in otherwise vector PDF/SVG exports."
    )
    return summary
