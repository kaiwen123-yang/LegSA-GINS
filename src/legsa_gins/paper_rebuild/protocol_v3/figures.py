"""The ten requested v3 composites from new sealed errors and report tables.

Reuse the established publication style/drawings. The only Truth input admitted
is a sealed export made in an evaluator child; this renderer never opens trace.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

from ..publication import qa, style
from ..publication import protocol_v2_figures as drawing
from ..publication.protocol_v21_figures import mfig02
from ..publication.protocol_v21_render import figure_checks
from ..publication.canonical541_figures import _local_enu
from ..hext.readonly_figures import make_fig02s, make_fig02sb
from .reporting import (MAIN, METRICS, RuntimeResults, Sources, safe, sha256,
    write_json, number, state)

FIGURE_IDS = (*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b")
TRUTH_COLUMNS = ("time", "truth_latitude_deg", "truth_longitude_deg", "truth_height_m", "truth_yaw_deg",
    "estimate_latitude_deg", "estimate_longitude_deg", "estimate_height_m", "estimate_yaw_deg")


class Tables:
    def __init__(self, root, manifest):
        self.root, self.manifest = root, manifest
        self.used = set()

    def table(self, name):
        path = self.root / name
        if sha256(path) != self.manifest["files_sha256"][name]:
            raise ValueError("V3 figure table hash differs: " + name)
        self.used.add(name)
        rows = pd.read_csv(path, low_memory=False)
        for field in (*METRICS, "delta_candidate_minus_reference", "source_aware_touch_rate",
            "raw_doppler_update_count", "scheme_c_reject_count", "go2_hv_update_count"):
            if field in rows:
                rows[field] = pd.to_numeric(rows[field], errors="coerce")
        return rows

    def use(self, rows):
        return rows


def frozen_plot_intervals(bundle, evaluation_window):
    """Use realized component intervals, with full-sequence exposure explicit."""
    if (bundle.get("case_meta") or {}).get("duration_s") == "full_sequence":
        pairs = [tuple(map(float, evaluation_window))]
    else:
        pairs = []
        for component in bundle.get("components", []):
            if component.get("component") == "clean_recovery_interval":
                continue
            details = component.get("details", {})
            values = [details["interval"]] if "interval" in details else details.get("intervals", [])
            for value in values:
                pair = tuple(map(float, (value["start_s"], value["end_s"]) if isinstance(value, dict) else value))
                if pair not in pairs:
                    pairs.append(pair)
    if not pairs or any(len(pair) != 2 or not np.isfinite(pair).all() or pair[1] <= pair[0] for pair in pairs):
        raise ValueError("Frozen provider has no valid realized fault interval")
    return sorted(pairs)


def type_heatmap(rows, metric):
    """Retain all registered type positions, including wholly unavailable types."""
    completed = rows[(rows.evaluation_status == "COMPLETED") & (rows.degradation_id != "CLEAN")]
    frame = completed.pivot_table(index="degradation_id", columns="profile", values=metric, aggfunc="mean")
    return frame.reindex(index=[f"D{i:02}" for i in range(1, 61)], columns=MAIN)


class Bundle:
    def __init__(self, root, manifest, runtime, source_index):
        self.p = Tables(root, manifest)
        self.runtime = runtime
        self.source_index = source_index
        self.case_sources = json.loads(runtime.sources.read(source_index["frozen_case_bundles"]))["case_bundles"]
        import yaml
        self.evaluation_windows = yaml.safe_load(runtime.sources.read(source_index["evaluation_window_contract"]))["sequences"]
        self.metadata_sources = {str(runtime.sources.resolve(source_index[key]["path"])): source_index[key]["sha256"]
            for key in ("frozen_case_bundles", "evaluation_window_contract")}
        self.unique = self.p.table("CORE_541_TABLE_V3.csv")
        self.notes = []

    def core(self, methods=MAIN, **filters):
        self.p.used.add("CORE_541_TABLE_V3.csv")
        rows = self.unique[self.unique.method_id.isin(methods)]
        for field, values in filters.items():
            rows = rows[rows[field].isin(values if isinstance(values, (tuple, list, set)) else [values])]
        return rows

    def aggregate(self, name):
        return self.p.table(name.removesuffix(".csv") + "_V3.csv")

    def series(self, case, profile):
        rows = self.unique[(self.unique.case_id == case) & (self.unique.method_id == profile)]
        if len(rows) != 1:
            raise ValueError("V3 figure series has no unique registered case/profile")
        row = rows.iloc[0].to_dict()
        if state(row) != "COMPLETED":
            return None, row["failure_classification"]
        return self.runtime.series(row)[0], "COMPLETED"

    def window(self, case):
        rows = self.unique[self.unique.case_id == case]
        bundle = json.loads(self.runtime.sources.read(self.case_sources[case]))
        if bundle.get("case_id") != case:
            raise ValueError("Frozen component-window case identity differs")
        intervals = frozen_plot_intervals(bundle, self.evaluation_windows[rows.iloc[0].dataset_id]["window_seconds"])
        if len(intervals) != 1:
            raise ValueError("Representative figure requires one exact realized interval")
        return intervals[0]


def mfig00(bundle):
    """Display independent evaluator-exported Truth, never estimate-minus-error."""
    row = bundle.unique[(bundle.unique.case_id == "C00_clean_normal") & (bundle.unique.method_id == "F04")].iloc[0].to_dict()
    trajectory = bundle.runtime.truth(row)
    if not set(TRUTH_COLUMNS) <= set(trajectory):
        raise ValueError("Evaluator Truth export is missing registered display columns")
    if not np.isfinite(trajectory[list(TRUTH_COLUMNS)].to_numpy(float)).all():
        raise ValueError("Evaluator Truth export contains nonfinite samples")
    if trajectory.time.duplicated().any() or not trajectory.time.is_monotonic_increasing:
        raise ValueError("Truth export timestamps must increase without duplicates")
    t = trajectory.time.to_numpy(float)
    origin = tuple(trajectory.iloc[0][["truth_latitude_deg", "truth_longitude_deg", "truth_height_m"]])
    tr = _local_enu(*(trajectory[field].to_numpy(float) for field in
        ("truth_latitude_deg", "truth_longitude_deg", "truth_height_m")), *origin)
    est = _local_enu(*(trajectory[field].to_numpy(float) for field in
        ("estimate_latitude_deg", "estimate_longitude_deg", "estimate_height_m")), *origin)
    fig, axes = drawing.canvas(2, 2, 5.2)
    axes[0, 0].plot(tr[0], tr[1], color="black", label="Truth Trajectory")
    axes[0, 0].plot(est[0], est[1], **drawing.linekw("F04"))
    axes[0, 0].set(xlabel="East (m)", ylabel="North (m)", aspect="equal")
    axes[0, 1].plot(t, np.rad2deg(np.unwrap(np.deg2rad(trajectory.truth_yaw_deg))), color="black", label="Truth")
    axes[0, 1].plot(t, np.rad2deg(np.unwrap(np.deg2rad(trajectory.estimate_yaw_deg))), **drawing.linekw("F04"))
    axes[0, 1].set(xlabel="Time (s)", ylabel="Yaw, unwrapped (°)")
    for method in MAIN:
        errors, status = bundle.series("C00_clean_normal", method)
        if errors is None:
            bundle.notes.append(dict(case_id="C00_clean_normal", method_id=method, unavailable=status))
            continue
        axes[1, 0].plot(errors.time, errors.yaw_err_deg, **drawing.linekw(method))
    axes[1, 0].set(xlabel="Time (s)", ylabel="Yaw error (°)")
    axes[1, 1].plot(t, tr[2], color="black", label="Truth")
    axes[1, 1].plot(t, est[2], **drawing.linekw("F04"))
    axes[1, 1].set(xlabel="Time (s)", ylabel="Height relative to Truth start (m)")
    for ax in axes.flat:
        drawing.legend(ax)
    return fig, ("Protocol-v3 C00 comparison at the frozen v3 evaluation point. Truth and estimate samples "
        "were exported inside the authorized evaluator child at its own matched epochs. The renderer opens "
        "no raw trace, fits no alignment, and never reconstructs Truth from estimation errors. "
        "Yaw-error curves use the corresponding new full-rate sealed evaluations.")


def _paired_range(ax, pairs, groups, metric, *, field, color, xlabel):
    values, low, high, counts = [], [], [], []
    for group in groups:
        selected = pairs.loc[(pairs[field] == group) & (pairs.metric_name == metric)]
        if len(selected) > 1:
            raise ValueError("Duplicate paired inference summary")
        row = selected.iloc[0] if len(selected) else {}
        values.append(float(row.get("median_delta_candidate_minus_reference", np.nan)))
        low.append(float(row.get("median_ci95_low", np.nan)))
        high.append(float(row.get("median_ci95_high", np.nan)))
        counts.append(int(row.get("paired_sample_count", 0)))
    values, low, high = map(np.asarray, (values, low, high))
    ax.errorbar(np.arange(len(groups)), values, yerr=(values - low, high - values), fmt="o", color=color, capsize=2)
    ax.axhline(0, color="black", lw=.6)
    ax.set_xticks(np.arange(len(groups)), xlabel, rotation=40, ha="right")
    missing = np.flatnonzero(np.asarray(counts) == 0)
    if len(missing):
        ax.plot(missing, np.full(len(missing), .04), "x", transform=ax.get_xaxis_transform(), color="#666666")
    return counts


def mfig03(bundle):
    fig, axes = drawing.canvas(2, 2, 5.4)
    pairs = bundle.aggregate("PAIRWISE_SUMMARY.csv")
    pairs = pairs[(pairs.comparison == "full_vs_no_SA") & (pairs.scope == "family")]
    core = bundle.core(["A04", "F04"])
    families = sorted(core.case_family.unique())
    for col, (metric, label) in enumerate((("horizontal_rmse_m", "Horizontal RMSE (m)"), ("yaw_rmse_deg", "Yaw RMSE (°)"))):
        counts = _paired_range(axes[0, col], pairs, families, metric, field="family", color=style.COLORS["F04"],
            xlabel=[drawing.FAMILIES.get(key, key) for key in families])
        axes[0, col].set_ylabel("F04 − A04\n" + label)
        values = core[core.evaluation_status == "COMPLETED"].pivot(index="case_id", columns="profile", values=metric).dropna()
        if len(values):
            axes[1, col].scatter(values.A04, values.F04, s=5, alpha=.45, color=style.COLORS["F04"])
            low, high = float(values.min().min()), float(values.max().max())
            axes[1, col].plot([low, high], [low, high], color="black", ls="--", lw=.6)
        axes[1, col].set(xlabel="A04 " + label, ylabel="F04 " + label)
        bundle.notes.append(dict(metric=metric, finite_pairs_by_family=dict(zip(families, counts))))
    return fig, ("F04 minus A04 under protocol v3. Family markers are finite-pair medians; whiskers show "
        "paired percentile 95% bootstrap intervals (10,000 samples; frozen seed 20260904). Scatter includes only pairs whose new evaluations both completed. "
        "Unavailable families remain marked without assigning a metric value; all failures remain in the tables.")


def mfig04(bundle):
    fig, axes = drawing.canvas(2, 2, 5.8)
    core = bundle.core(list(drawing.ALL))
    pairs = bundle.aggregate("PAIRWISE_SUMMARY.csv")
    pairs = pairs[pairs.scope == "overall"]
    wanted = ["full_vs_no_RD", "full_vs_no_SA", "full_vs_no_RP", "full_vs_no_HV", "full_vs_no_Go2"]
    for col, (metric, label) in enumerate((("horizontal_rmse_m", "Horizontal RMSE (m)"), ("yaw_rmse_deg", "Yaw RMSE (°)"))):
        drawing.summary(axes[0, col], bundle, core, MAIN, metric, label, tail=col == 1)
        counts = _paired_range(axes[1, col], pairs, wanted, metric, field="comparison", color=style.COLORS["F04"],
            xlabel=["RD", "SA", "RP", "HV", "RP + HV"])
        axes[1, col].set_ylabel("F04 − module removed\n" + label)
        bundle.notes.append(dict(metric=metric, module_finite_pairs=dict(zip(wanted, counts))))
    return fig, ("Protocol-v3 ablation ladder F01 → F02 → F03 → A04 → F04 and same-case leave-one-module-out "
        "comparisons. Module markers show median changes and paired percentile 95% bootstrap intervals "
        "(10,000 samples; frozen seed 20260904). Failure counts and finite denominators are retained separately.")


def sfig01(bundle):
    fig, axes = drawing.canvas(2, 3, 8.1)
    rows = bundle.core()
    metrics = [*drawing.METRICS, ("roll_rmse_deg", "Roll RMSE (°)"),
        ("pitch_rmse_deg", "Pitch RMSE (°)"), ("position_3d_rmse_m", "3D RMSE (m)")]
    for ax, (metric, label) in zip(axes.flat, metrics):
        frame = type_heatmap(rows, metric)
        data = np.ma.masked_invalid(frame.to_numpy(float))
        if not data.count() or data.min() <= 0:
            raise ValueError("Log-RMSE heatmap requires positive available values")
        image = ax.imshow(data, aspect="auto", cmap="cividis", norm=LogNorm(vmin=float(data.min()), vmax=float(data.max())))
        ax.set_xticks(range(5), MAIN, rotation=40)
        ax.set_yticks([0, 9, 19, 29, 39, 49, 59], ["D01", "D10", "D20", "D30", "D40", "D50", "D60"])
        fig.colorbar(image, ax=ax, label=label, fraction=.046, pad=.03)
        bundle.notes.append(dict(metric=metric, missing_cells=int(np.ma.getmaskarray(data).sum()),
            type_order=list(frame.index), method_order=list(frame.columns)))
    return fig, ("All 60 registered degradation types × five configurations, protocol-v3 finite-case mean RMSE. "
        "Log color scales preserve the v2.1 style. Every type retains its fixed row even when all five methods "
        "failed; unavailable cells are masked and never assigned zero. Failure counts are reported separately.")


DRAWERS = {"MFIG00": mfig00, "MFIG01": drawing.mfig01, "MFIG02": mfig02,
    "MFIG03": mfig03, "MFIG04": mfig04, "MFIG05": drawing.mfig05,
    "MFIG06": drawing.mfig06, "SFIG01": sfig01}


def render(root, *, roots, code_freeze):
    root = safe(root)
    aggregate_root, output = root / "07_AGGREGATE", root / "08_FIGURES"
    if output.exists():
        raise FileExistsError("Existing v3 exports must be preserved")
    manifest = json.loads((aggregate_root / "AGGREGATE_MANIFEST.json").read_text())
    if manifest.get("status") != "COMPLETE_V3_AGGREGATES" or manifest.get("code_freeze") != code_freeze:
        raise ValueError("Figures require complete reports from the registered freeze")
    source_index = json.loads((aggregate_root / "REPORT_SOURCE_INDEX.json").read_text())
    sources = Sources(roots)
    runtime = RuntimeResults(root, sources, code_freeze)
    bundle = Bundle(aggregate_root, manifest, runtime, source_index)
    selection = json.loads(sources.read(source_index["selection"]))["selection"]
    output.mkdir(parents=True, exist_ok=False)
    entries, captions = [], []
    for figure_id in FIGURE_IDS:
        directory = output / figure_id
        directory.mkdir()
        bundle.notes, bundle.p.used = [], {"CORE_541_TABLE_V3.csv"} if figure_id.startswith(("MFIG", "SFIG")) else set()
        sources.used = dict(bundle.metadata_sources)
        figure = None
        try:
            if figure_id == "FIG02S":
                rows = bundle.p.table("MAIN_TABLE_V3.csv").fillna("UNAVAILABLE").to_dict("records")
                figure, details = make_fig02s(rows, selection)
                caption = ("Protocol-v3 three-sequence comparison. LegSA rows use new 5 Hz heading runs. "
                    "LC01 literature bars and LC01-S hollow markers retain the exact H-EXT-04L results and starts. "
                    "BY2H geometric-audit limitations remain visible in the companion table.")
            elif figure_id == "FIG02S-b":
                rows = bundle.p.table("BY2O_SEGMENT_TABLE.csv").fillna("UNAVAILABLE").to_dict("records")
                figure, details = make_fig02sb(rows)
                caption = ("Protocol-v3 BY2O closed primary (3369.94–3411.95 s) and secondary (3495.94–3508.94 s) "
                    "occlusion intervals. New LegSA metrics use sealed full-rate errors and the unchanged H-EXT-04L "
                    "region evaluator. LC01 and LC01-S values are copied unchanged. Outside blocks remain in the table.")
            else:
                figure, caption = DRAWERS[figure_id](bundle)
                details = {}
            caption = caption.replace("v2.1 figure edition", "v3 figure edition")
            if "protocol-v3" not in caption.lower():
                caption += " Protocol-v3 edition; all LegSA evidence comes from the new registered matrix."
            checks = figure_checks(figure, figure_id)
            if not all(check["pass"] for check in checks):
                raise ValueError("Figure semantic checks failed: " + str(checks))
            saved = style.save_figure(figure, directory, figure_id)
            checks += qa.check_png(Path(saved["png"]), figure_id)
            if not all(check["pass"] for check in checks):
                raise ValueError("Figure raster checks failed")
            entry = dict(figure_id=figure_id, status="RENDERED", protocol="v3", code_freeze=code_freeze,
                data_mode="real_sequence_visualization" if figure_id in ("MFIG00", "FIG02S", "FIG02S-b") else "registered_semisynthetic_case_visualization",
                synthetic_data_used=False, semisynthetic_data_used=figure_id not in ("MFIG00", "FIG02S", "FIG02S-b"),
                evaluator_version="v3", trace_open_count=0, native_calls=0, evaluator_calls=0,
                caption=caption, details=details, notes=bundle.notes, qa=checks,
                output_sha256={ext: saved[ext + "_sha256"] for ext in ("png", "pdf", "svg")},
                png_width_px=saved["png_width_px"], png_height_px=saved["png_height_px"],
                table_sources={name: manifest["files_sha256"][name] for name in sorted(bundle.p.used)},
                runtime_sources=sources.used)
        except Exception as exc:
            entry = dict(figure_id=figure_id, status="UNAVAILABLE_REQUIRED_FIGURE", reason=str(exc),
                protocol="v3", code_freeze=code_freeze, data_mode="unavailable", synthetic_data_used=False,
                semisynthetic_data_used=False, trace_open_count=0)
        finally:
            style.plt.close(figure) if figure is not None else style.plt.close("all")
        write_json(directory / "FIGURE_MANIFEST.json", entry)
        entries.append(entry)
        captions.append("**" + figure_id + ".** " + entry.get("caption", entry.get("reason", "")))
        print(json.dumps(dict(figure_id=figure_id, status=entry["status"])), flush=True)
    result = dict(status="COMPLETE" if all(e["status"] == "RENDERED" for e in entries) else "INCOMPLETE",
        protocol="v3", code_freeze=code_freeze, data_mode="mixed_real_and_registered_semisynthetic_visualization",
        synthetic_data_used=False, semisynthetic_data_used=True, trace_open_count=0, figures=entries,
        requested_count=10, rendered_count=sum(e["status"] == "RENDERED" for e in entries),
        visual_review_status="PENDING_ACTUAL_RASTER_REVIEW")
    write_json(output / "RENDER_MANIFEST.json", result)
    (output / "CAPTIONS.md").write_text("\n\n".join(captions) + "\n", encoding="utf-8")
    (output / "FIGURE_INDEX.md").write_text("# Protocol v3 figures\n\n" + "\n".join(
        "- [" + e["figure_id"] + "](" + e["figure_id"] + "/" + e["figure_id"] + ".png): " + e["status"] for e in entries) + "\n", encoding="utf-8")
    return result
