"""Protocol-v2 figures from sealed v3 rows; F04 is the proposed method.

This module is deliberately separate from the byte-frozen v1 renderer.  Native
failures are displayed separately from finite errors, never as zero or infinity.
"""
from __future__ import annotations

import json
import string

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

from . import style
from .protocol_v2_data import (ALL, CAL, CONFIG, LABEL, MAIN, PARITY, Bundle,
                               EvidenceUnavailable, finite_values,
                               near_zero_direction, worst_five_percent, display_v3_nav)


COLORS = {**style.COLORS, "A03": "#009E73", "A05": "#CC79A7", "A06": "#999933",
          "A07": "#332288", "A08": "#88CCEE", "A09": "#882255"}
LINES = {**style.LINESTYLES, "A03": "--", "A05": ":", "A06": "-.", "A07": (0, (3, 1)),
         "A08": (0, (5, 2, 1, 2)), "A09": (0, (1, 2))}
FAMILIES = {"clean": "Clean", "dual_yaw": "Dual yaw", "gnss_outage": "Outage",
            "gnss_sampling": "Sampling", "position_value": "Position value",
            "position_std_status": "Position quality", "velocity_raw_doppler": "Velocity / RD",
            "go2_prior_metadata": "Body prior", "multi_source_mixed": "Mixed"}
METRICS = [("horizontal_rmse_m", "Horizontal RMSE (m)"), ("up_rmse_m", "Up RMSE (m)"),
           ("yaw_rmse_deg", "Yaw RMSE (°)")]


def canvas(rows=1, cols=1, height=3.2):
    fig, axes = style.new_figure(rows, cols, height)
    fig.subplots_adjust(left=.11, right=.98, top=.94, bottom=.13,
                        wspace=.55 if cols > 2 else .4, hspace=.6 if rows > 2 else .45)
    for i, ax in enumerate(axes.flat):
        style.panel_label(ax, string.ascii_lowercase[i], x=-.16)
        ax.grid(axis="y", alpha=.35)
    return fig, axes


def linekw(method):
    return {"color": COLORS[method], "linestyle": LINES[method],
            "linewidth": 1.2 if method == "F04" else .85, "label": LABEL[method]}


def legend(ax, columns=1):
    ax.legend(loc="best", ncol=columns, handlelength=2, columnspacing=.8)


def values(b, frame, method, metric):
    selected = frame[frame.profile == method]
    b.p.use(selected)
    completed = selected[selected.evaluation_status == "COMPLETED"]
    return finite_values(completed, metric), int((selected.evaluation_status != "COMPLETED").sum())


def summary(ax, b, frame, methods, metric, ylabel, tail=False):
    xs = np.arange(len(methods))
    ticklabels = []
    for i, method in enumerate(methods):
        vals, failed = values(b, frame, method, metric)
        if not len(vals):
            raise EvidenceUnavailable("No finite metric rows for " + method + "/" + metric)
        ax.plot(i, np.median(vals), "D", ms=4, color=COLORS[method], label="Median" if i == 0 else None)
        ax.plot(i, np.mean(vals), "o", ms=4, mfc="none", color=COLORS[method], label="Mean" if i == 0 else None)
        if tail:
            mean, count = worst_five_percent(vals)
            ax.plot(i, np.percentile(vals, 95), "v", ms=5, color=COLORS[method], label="Case P95 threshold" if i == 0 else None)
            ax.plot(i, mean, "^", ms=5, mfc="none", color=COLORS[method], label="Worst 5% mean" if i == 0 else None)
        states = frame.loc[frame.profile == method, "evaluation_status"]
        algorithm = int(states.eq("NOT_RUN_ALGORITHM_FAILURE").sum())
        other = failed-algorithm
        ticklabels.append(f"{method}\nn={len(vals)}\n×{algorithm}; ?{other}")
    ax.set_xticks(xs, ticklabels, rotation=0, ha="center")
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    legend(ax)


def ecdf(ax, b, frame, methods, metric, ylabel):
    for method in methods:
        vals, failed = values(b, frame, method, metric)
        vals.sort()
        if not len(vals):
            raise EvidenceUnavailable("No finite distribution: " + method)
        ax.step(vals, np.arange(1, len(vals) + 1) / len(vals), where="post", **linekw(method))
    ax.set_xlabel(ylabel)
    ax.set_ylabel("ECDF among finite cases")
    ax.set_ylim(0, 1.02)
    if min(float(pd.to_numeric(frame[metric], errors="coerce").min()), 1) > 0:
        ax.set_xscale("log")
    legend(ax)


def mfig00(b):
    fig, axs = canvas(2, 2, 5.2)
    nav = b.p.use(b.p.table("C00_NAV_AB1111.csv"))
    geometry = b.p.json("PLOT_GEOMETRY_CONTRACT.json")["evaluation"]
    nav_columns = ["gps_week", "time_s", "latitude_deg", "longitude_deg", "height_m",
                   "vn_mps", "ve_mps", "vd_mps", "roll_deg", "pitch_deg", "yaw_deg"]
    nav.loc[:, nav_columns] = display_v3_nav(nav[nav_columns].to_numpy(float),
                                            float(geometry["v3_baseline_median_m"]))
    b.notes.append("Display-only LLH rigid transform of retained native NAV samples; frozen baseline and lever; no EVAL_NAV artifact or evaluator invocation.")
    trace = b.trace()
    series, status = b.series("C00_clean_normal", "F04")
    if series is None:
        raise EvidenceUnavailable("C00 F04 frozen error series " + status)
    t = nav.time_s.to_numpy(float)
    ref = trace[(trace.t >= t.min() - 1) & (trace.t <= t.max() + 1)]
    b.reference_rows = ref._source_csv_row.astype(int).tolist()
    rt = ref.t.to_numpy(float)
    if rt[0] > t[0] or rt[-1] < t[-1]:
        raise EvidenceUnavailable("Truth does not cover the frozen evaluation epochs")
    trlat = np.interp(t, rt, ref.lat); trlon = np.interp(t, rt, ref.lon)
    trh = np.interp(t, rt, ref.height)
    tryaw = np.rad2deg(np.interp(t, rt, np.unwrap(np.deg2rad(ref.yaw_ned_deg))))
    estlat = nav.latitude_deg.to_numpy(float); estlon = nav.longitude_deg.to_numpy(float)
    esth = nav.height_m.to_numpy(float)
    estyaw = np.rad2deg(np.unwrap(np.deg2rad(nav.yaw_deg)))
    # The frame and time are fixed, and the NAV must be the v3 evaluation-point
    # NAV.  No trajectory reconstruction or fitted shift is allowed.
    from .canonical541_figures import _local_enu
    origin = (trlat[0], trlon[0], trh[0])
    re, rn, ru = _local_enu(trlat, trlon, trh, *origin)
    ee, en, eu = _local_enu(estlat, estlon, esth, *origin)
    common, nav_idx, err_idx = np.intersect1d(t, series.time.to_numpy(float), return_indices=True)
    if not len(common):
        raise EvidenceUnavailable("No exact retained NAV/error-series timestamps for identity consistency check")
    errors = series.iloc[err_idx]
    delta = np.hypot((ee - re)[nav_idx] - errors.err_e_m, (en - rn)[nav_idx] - errors.err_n_m)
    dyaw = (estyaw[nav_idx] - tryaw[nav_idx] - errors.yaw_err_deg + 180) % 360 - 180
    if np.max(delta) > .05 or np.max(np.abs((eu - ru)[nav_idx] - errors.err_u_m)) > .05 or np.max(np.abs(dyaw)) > .5:
        raise ValueError("Frozen v3 EVAL_NAV/Truth/error-series consistency gate failed")
    b.notes.append({"display_consistency_check": "Exact retained timestamp intersection only; independently decimated streams are never interpolated against one another.",
                    "exact_intersection_epochs": len(common), "retained_nav_epochs": len(nav),
                    "retained_error_epochs": len(series), "nav_intersection_fraction": len(common)/len(nav),
                    "error_intersection_fraction": len(common)/len(series),
                    "max_horizontal_check_difference_m": float(np.max(delta)),
                    "max_up_check_difference_m": float(np.max(np.abs((eu-ru)[nav_idx]-errors.err_u_m))),
                    "max_yaw_check_difference_deg": float(np.max(np.abs(dyaw)))})
    axs[0, 0].plot(re, rn, color="black", label="Truth Trajectory")
    axs[0, 0].plot(ee, en, **linekw("F04"))
    axs[0, 0].set(xlabel="East (m)", ylabel="North (m)", aspect="equal")
    axs[0, 1].plot(t, tryaw, color="black", label="Truth")
    axs[0, 1].plot(t, estyaw, **linekw("F04"))
    axs[0, 1].set(xlabel="Time (s)", ylabel="Yaw, unwrapped (°)")
    for method in MAIN:
        s, _ = b.series("C00_clean_normal", method)
        if s is None:
            raise EvidenceUnavailable("C00 required method series unavailable")
        axs[1, 0].plot(s.time, s.yaw_err_deg, **linekw(method))
    axs[1, 0].set(xlabel="Time (s)", ylabel="Yaw error (°)")
    axs[1, 1].plot(t, ru, color="black", label="Truth")
    axs[1, 1].plot(t, eu, **linekw("F04"))
    axs[1, 1].set(xlabel="Time (s)", ylabel="Height relative to Truth start (m)")
    for ax in axs.flat:
        legend(ax)
    return fig, "C00 v3 reference-point comparison. Truth is read exclusively from the supplied hash-locked receiver navigation trace. Retained native NAV samples receive the frozen LLH-only rigid point transform and are displayed at their own timestamps; no evaluation metric is recomputed. Independently decimated error-series retain their own sample times; the numerical consistency gate covers only exact coincident timestamps, with its sample count and fractions in the manifest. Coordinates, clock and yaw convention are fixed; no alignment is fitted."


def mfig01(b):
    fig, axs = canvas(2, 2, 5.6)
    rows = b.core()
    summary(axs[0, 0], b, rows, MAIN, "horizontal_rmse_m", "Horizontal RMSE (m)")
    summary(axs[0, 1], b, rows, MAIN, "yaw_rmse_deg", "Yaw RMSE (°)", True)
    ecdf(axs[1, 0], b, rows, MAIN, "horizontal_rmse_m", "Horizontal RMSE (m)")
    ecdf(axs[1, 1], b, rows, MAIN, "yaw_rmse_deg", "Yaw RMSE (°)")
    return fig, "541-core v3 case distributions. n denotes finite cases; × denotes algorithm failures and ? technical or unavailable records, excluded from finite statistics. P95 is the across-case 95th-percentile threshold. Worst 5% mean is separately the mean of the largest ceil(0.05 n) finite case RMSEs; it is not P95."


def mfig02(b):
    pairs = b.aggregate("PAIRWISE_CASE_LEVEL.csv")
    rows = b.p.use(pairs[(pairs.comparison == "A04_vs_F03") & pairs.metric_name.isin([METRICS[0][0], METRICS[2][0]])])
    fig, axs = canvas(2, 2, 5.4)
    for col, (metric, label) in enumerate([METRICS[0], METRICS[2]]):
        subset = rows[rows.metric_name == metric]
        groups = list(subset[subset.degradation_id != "CLEAN"].groupby("degradation_id", sort=True))
        if len(groups) != 60:
            raise EvidenceUnavailable("Per-type paired coverage does not enumerate 60 types")
        x = np.arange(60)
        med = np.array([g.delta_candidate_minus_reference.median() for _, g in groups])
        lo = np.array([g.delta_candidate_minus_reference.min() for _, g in groups])
        hi = np.array([g.delta_candidate_minus_reference.max() for _, g in groups])
        axs[0, col].errorbar(x, med, yerr=[med-lo, hi-med], fmt=".", color=COLORS["A04"], lw=.6)
        axs[0, col].axhline(0, color="black", lw=.6)
        axs[0, col].set_xticks([0, 9, 19, 29, 39, 49, 59], ["D01", "D10", "D20", "D30", "D40", "D50", "D60"])
        axs[0, col].set_ylabel("Δ " + label)
        families = list(subset.groupby("case_family", sort=True))
        rates = [100 * (g.delta_candidate_minus_reference < 0).mean() for _, g in families]
        axs[1, col].barh(np.arange(len(families)), rates, color=COLORS["A04"])
        axs[1, col].set_yticks(np.arange(len(families)), [FAMILIES.get(f, f) for f, _ in families])
        axs[1, col].set(xlim=(0, 100), xlabel="Finite paired win rate (%)")
    return fig, "A04 minus F03. Per-type markers show the median, whiskers the observed seed range (not a confidence interval); family win rates use finite pairs only. A04 remains the v1 preregistered decision and an ablation row."


def mfig03(b):
    pairs = b.aggregate("PAIRWISE_SUMMARY.csv")
    rows = b.p.use(pairs[(pairs.comparison == "full_vs_no_SA") & (pairs.scope == "family")])
    fig, axs = canvas(2, 2, 5.4)
    for ax, (metric, label) in zip(axs[0], [METRICS[0], METRICS[2]]):
        sub = rows[rows.metric_name == metric].sort_values("family")
        if sub.empty:
            raise EvidenceUnavailable("Missing F04/A04 family paired summary")
        y = sub.median_delta_candidate_minus_reference.to_numpy(float)
        lo = sub.median_ci95_low.to_numpy(float); hi = sub.median_ci95_high.to_numpy(float)
        ax.errorbar(np.arange(len(sub)), y, yerr=[y-lo, hi-y], fmt="o", color=COLORS["F04"], capsize=2)
        ax.axhline(0, color="black", lw=.6)
        ax.set_xticks(np.arange(len(sub)), [FAMILIES.get(v, v) for v in sub.family], rotation=45, ha="right")
        ax.set_ylabel("Median Δ " + label)
    u = b.core(["A04", "F04"])
    for ax, (metric, label) in zip(axs[1], [METRICS[0], METRICS[2]]):
        pivot = u.pivot(index="case_id", columns="profile", values=metric).apply(pd.to_numeric, errors="coerce").dropna()
        ax.scatter(pivot.A04, pivot.F04, s=5, alpha=.45, color=COLORS["F04"])
        lo, hi = min(pivot.min()), max(pivot.max())
        ax.plot([lo, hi], [lo, hi], color="black", ls="--", lw=.6)
        ax.set(xlabel="A04 " + label, ylabel="F04 " + label)
    return fig, "F04 minus A04, v3: family median paired changes with frozen bootstrap 95% intervals and case-level paired scatter. Missing or failed runs are excluded from finite pair marks and remain in the failure inventory."


def mfig04(b):
    fig, axs = canvas(2, 2, 5.8)
    u = b.core(ALL)
    summary(axs[0, 0], b, u, MAIN, "horizontal_rmse_m", "Horizontal RMSE (m)")
    summary(axs[0, 1], b, u, MAIN, "yaw_rmse_deg", "Yaw RMSE (°)", True)
    pairs = b.aggregate("PAIRWISE_SUMMARY.csv")
    wanted = ["full_vs_no_RD", "full_vs_no_SA", "full_vs_no_RP", "full_vs_no_HV", "full_vs_no_Go2"]
    for ax, (metric, label) in zip(axs[1], [METRICS[0], METRICS[2]]):
        sub = b.p.use(pairs[(pairs.scope == "overall") & (pairs.metric_name == metric) & pairs.comparison.isin(wanted)])
        sub = sub.set_index("comparison").reindex(wanted)
        if sub.median_delta_candidate_minus_reference.isna().any():
            raise EvidenceUnavailable("Missing overall module pairs")
        y = sub.median_delta_candidate_minus_reference.to_numpy(float)
        ax.errorbar(np.arange(len(sub)), y,
                    yerr=[y-sub.median_ci95_low, sub.median_ci95_high-y], fmt="o", color=COLORS["F04"], capsize=2)
        ax.axhline(0, color="black", lw=.6)
        ax.set_xticks(np.arange(len(sub)), ["RD", "SA", "RP", "HV", "RP + HV"])
        ax.set_ylabel("F04 − module removed\n" + label)
    return fig, "Ablation ladder F01 → F02 → F03 → A04 → F04 and leave-one-module-out pairs. Interval bars are frozen paired bootstrap 95% intervals, with candidate minus reference signs."


def mfig05(b):
    types = ["D27", "D60", "D04", "D12", "D58"]
    fig, axs = canvas(5, 2, 9.4)
    unavailable = []
    for rowidx, typ in enumerate(types):
        case = sorted(b.unique.loc[b.unique.degradation_id == typ, "case_id"].unique())[0]
        start, end = b.window(case)
        for m in ["F03", "A04", "F04"]:
            series, state = b.series(case, m)
            if series is None:
                unavailable.append(case + "/" + m + ": " + state)
                continue
            for ax, col in zip(axs[rowidx], ["horizontal_err_m", "yaw_err_deg"]):
                ax.plot(series.time, series[col], **linekw(m))
        for ax in axs[rowidx]:
            ax.axvspan(start, end, color="#dddddd", alpha=.5)
            ax.text(.02, .94, typ + " / seed " + case.rsplit("_", 1)[-1], transform=ax.transAxes, va="top", fontsize=7)
            ax.set_xlabel("Time (s)")
        axs[rowidx, 0].set_ylabel("Horizontal error (m)")
        axs[rowidx, 1].set_ylabel("Yaw error (°)")
    fig.legend(*axs[0, 0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.55, 1.0), ncol=3)
    if unavailable:
        b.notes.extend(unavailable)
    return fig, "Preregistered representative types D27/D60 and D04/D12/D58 displayed together, deterministic lowest seed. Grey spans are exact frozen case windows. Any algorithm-failure series is listed explicitly in the figure manifest; no substitute trace is drawn."


def mfig06(b):
    fig, axs = canvas(2, 2, 5.2)
    u = b.core(["F03", "A04", "F04"])
    f = u[u.profile == "F04"]
    groups = list(f.groupby("case_family", sort=True))
    labs = [FAMILIES.get(name, name) for name, _ in groups]
    metrics = [("source_aware_touch_rate", "Source-Aware changed-weight fraction"),
               ("raw_doppler_update_count", "Raw Doppler updates (mean count)"),
               ("scheme_c_reject_count", "Scheme-C rejected yaw (mean count)"),
               ("go2_hv_update_count", "HV updates (mean count)")]
    for ax, (metric, label) in zip(axs.flat, metrics):
        data = [pd.to_numeric(g[metric], errors="coerce").mean() for _, g in groups]
        if not np.isfinite(data).any():
            raise EvidenceUnavailable("Module action column unavailable: " + metric)
        ax.barh(np.arange(len(groups)), data, color=COLORS["F04"])
        ax.set_yticks(np.arange(len(groups)), labs)
        ax.set_xlabel(label)
    return fig, "F04 mechanism counters grouped by frozen family. Counts are descriptive and Source-Aware touch is a changed-weight fraction. Finite native counters include failed estimators when the frozen row retains them."


def mfig07(b):
    fig, axs = canvas(1, 2, 3.4)
    u = b.core()
    ecdf(axs[0, 0], b, u, MAIN, "yaw_rmse_deg", "Case yaw RMSE (°)")
    summary(axs[0, 1], b, u, MAIN, "yaw_rmse_deg", "Case yaw RMSE (°)", True)
    fig.subplots_adjust(bottom=.25)
    return fig, "Yaw RMSE distributions across all 541 core cases. Median, mean, across-case P95 threshold and the mean of the worst ceil(5% n) finite case RMSEs are distinct. × counts algorithm failures; ? counts technical or unavailable records. These records have no numeric RMSE."


def mfig08(b):
    methods = ["A03", "A05", "A06", "A07", "A08", "A09"]
    fig, axs = canvas(2, 3, 5.7)
    u = b.core(["F04", *methods])
    for ax, method in zip(axs.flat, methods):
        ecdf(ax, b, u, [method, "F04"], "yaw_rmse_deg", "Yaw RMSE (°)")
        ax.set_ylim(.8, 1.005)
        ax.axhline(.95, color="#777777", lw=.6, ls=":")
        ax.set_ylabel("Upper ECDF (finite cases)")
    return fig, "Single-module and reduced-module yaw tails against F04. Each panel uses its method's finite-case ECDF; the displayed 0.8–1 probability range is a tail view, not a shared paired-support claim."


def outage_curves(b, typ):
    addendum = typ in ("D61", "D62")
    u = b.addendum() if addendum else b.unique
    cases = u[u.degradation_id == typ][["case_id"]].drop_duplicates()
    groups = {}
    for case in sorted(cases.case_id):
        start, end = b.window(case, addendum)
        groups.setdefault(round(end-start, 6), []).append((case, start, end))
    if not groups:
        raise EvidenceUnavailable("No registered outage cases: " + typ)
    methods = ["F03", "A03", "A06", "A07", "F04"]
    fig, axs = canvas(len(groups), len(methods), 1.8 * len(groups) + .8)
    for ri, (duration, casegroup) in enumerate(sorted(groups.items())):
        for ci, method in enumerate(methods):
            ax = axs[ri, ci]
            failed = 0
            for case, start, end in casegroup:
                series, state = b.series(case, method, addendum)
                if series is None:
                    failed += 1
                    b.notes.append(case + "/" + method + ": " + state)
                    continue
                sub = series[(series.time >= start-2) & (series.time <= end+3)]
                ax.plot(sub.time-start, sub.horizontal_err_m, color=COLORS[method], lw=.5, alpha=.55)
            ax.axvspan(0, duration, color="#dddddd", alpha=.35)
            ax.set_xlim(-2, duration+3)
            ax.set_xlabel("Outage time (s)")
            if ci == 0:
                ax.set_ylabel(f"{duration:g} s\nHorizontal error (m)")
            if ri == 0:
                ax.text(.5, 1.17, LABEL[method], ha="center", transform=ax.transAxes, fontsize=7)
            if failed:
                ax.text(.03, .93, f"× {failed}/{len(casegroup)}", transform=ax.transAxes, fontsize=7, va="top")
        # Comparable quantities share a y range within each duration.
        limits = [ax.get_ylim() for ax in axs[ri]]
        for ax in axs[ri]:
            ax.set_ylim(0, max(v[1] for v in limits))
    return fig, f"{typ}: all nine seeded horizontal-error trajectories for each duration; native retained samples, without interpolation. Configuration columns share scales within a duration; different durations may use different scales. Grey spans are outages; × counts algorithm failures. Addendum A1/A2 remain separate from the 541 core."


def mfig12(b):
    rows = b.p.use(b.addendum())
    fig, axs = canvas(1, 2, 3.5)
    have = ["A04", "F04", "A03", "A05"]
    no = ["F03", "A06", "A07", "A08", "A09"]
    if "duration_s" not in rows:
        rows["duration_s"] = [b.window(case, True)[1] - b.window(case, True)[0] for case in rows.case_id]
    for ax, typ in zip(axs[0], ["D61", "D62"]):
        sub = rows[rows.degradation_id == typ]
        for methods, color, marker, label in [(have, COLORS["F04"], "o", "With HV"), (no, COLORS["F03"], "s", "Without HV")]:
            # Each line is one configuration: no pooling of 4/5 correlated runs
            # into a fictitious independent sample or confidence interval.
            for idx, method in enumerate(methods):
                sel = sub[sub.profile == method]
                grouped = sel.groupby("duration_s")["outage_end_horizontal_error_m"].median()
                ax.plot(grouped.index, grouped.values, color=color, marker=marker, ms=3, lw=.8,
                        ls="-" if idx % 2 else "--", alpha=.7, label=label if idx == 0 else None)
        ax.set(xlabel=f"{typ} outage duration (s)", ylabel="Median outage-end error (m)")
        ax.set_xticks(sorted(sub.duration_s.unique()))
        legend(ax)
    return fig, "Outage-end horizontal error: each line is one configuration's median across nine seeds, colored by presence of HV. Endpoints use the full-rate metric extracted from the last evaluation epoch within the preregistered interval; no metric is recomputed from decimated curves. Lines are descriptive, with no invented uncertainty."


def mfig13(b):
    fig, axs = canvas(1, 2, 4.2)
    for ax, rows, label in [(axs[0, 0], b.core(ALL), "541 core"), (axs[0, 1], b.p.use(b.addendum()), "A1/A2 addendum")]:
        sub = rows[rows.evaluation_status == "NOT_RUN_ALGORITHM_FAILURE"]
        other = rows[~rows.evaluation_status.isin(["COMPLETED", "NOT_RUN_ALGORITHM_FAILURE"])]
        families = sorted(rows.case_family.unique())
        width = .75 / len(ALL)
        for i, method in enumerate(ALL):
            counts = [len(sub[(sub.profile == method) & (sub.case_family == family)]) for family in families]
            ax.bar(np.arange(len(families)) + (i-5)*width, counts, width, color=COLORS[method],
                   label=method, hatch="//" if i > 5 else None)
        ax.set_xticks(np.arange(len(families)), [FAMILIES.get(v, v) for v in families], rotation=50, ha="right")
        ax.set_ylabel(label + " algorithm failures (count)")
        ax.set_ylim(bottom=0)
        if sub.empty:
            ax.set_ylim(0, 1)
            ax.set_yticks([0, 1])
            for i, family in enumerate(families):
                denominator = int((rows.case_family == family).sum())
                ax.text(i, .05, f"0 / {denominator} runs", ha="center", va="bottom", fontsize=7)
        if len(other):
            b.notes.append(f"{label}: {len(other)} technical/missing terminal rows are excluded from algorithm-failure counts and must be shown separately.")
            raise EvidenceUnavailable("Technical/missing records require separate failure panel")
    axs[0, 1].legend(ncol=3, loc="upper right")
    return fig, "Algorithm failures by family and effective configuration, keeping the 541-core and A1/A2 denominators separate. Missing or technical records must be identified in the terminal failure inventory; they are never converted into an algorithm failure or a zero RMSE."


def mfig14(b):
    manifest = b.p.table("supplemental/FAILURE_SERIES/SERIES_MANIFEST.csv")
    failures = manifest[(manifest.method_id == "F04") & (manifest.evaluation_status == "NOT_RUN_ALGORITHM_FAILURE")]
    if failures.empty:
        raise EvidenceUnavailable("No F04 algorithm failure native timeline")
    case = sorted(failures.case_id)[0]
    b.disclose(b.unique[b.unique.case_id == case], True)
    manifest = b.p.use(manifest[(manifest.case_id == case) & manifest.method_id.isin(["F02", "F04"])])
    if len(manifest) != 2 or not manifest.status.eq("OK").all():
        raise EvidenceUnavailable("Typical failure and same-case F02 trace unavailable")
    fig, axs = canvas(2, 1, 4.6)
    for i, (_, row) in enumerate(manifest.iterrows()):
        if row.method_id not in ("F02", "F04"):
            continue
        frame = b.p.use(b.p.table(row["member"]))
        accepted = frame.yaw_mode.isin(["NORMAL", "DOWNWEIGHT"])
        rejected = frame.yaw_mode.eq("REJECT")
        offset = 0 if row.method_id == "F02" else 2
        for delta, mask, marker in [(0, accepted, "o"), (1, rejected, "x")]:
            if mask.any():
                axs[0, 0].scatter(frame.loc[mask, "gnss_time"], np.full(mask.sum(), offset+delta),
                                  marker=marker, s=6, color=COLORS[row.method_id], label=LABEL[row.method_id])
        axs[1, 0].step(frame.gnss_time, accepted.astype(int).cumsum(), where="post", **linekw(row.method_id))
        axs[1, 0].step(frame.gnss_time, rejected.astype(int).cumsum(), where="post",
                       color=COLORS[row.method_id], ls=":", label=row.method_id + " rejected")
        b.notes.append(str(row.method_id) + " yaw_update flag denotes attempted update here; native yaw_mode controls accepted/rejected action counts. No emitted yaw residual is available.")
    axs[0, 0].set_yticks([0, 1, 2, 3], ["F02 accepted", "F02 rejected", "F04 accepted", "F04 rejected"])
    axs[0, 0].set_ylim(-.4, 3.4)
    axs[0, 0].set_xlabel("Time (s)")
    axs[1, 0].set(xlabel="Time (s)", ylabel="Cumulative yaw actions (count)")
    for ax in axs.flat:
        legend(ax)
    return fig, f"{case}: deterministically selected first F04 ALL_YAW_REJECTED case with the same-case F02 control. Exact native yaw_mode events determine accepted (NORMAL/DOWNWEIGHT) versus rejected actions; the yaw_update flag itself does not establish acceptance. Residual fields are empty for both methods and remain unavailable."


def mfig15(b):
    fig, axs = canvas(3, 3, 7.4)
    for ri, dataset in enumerate(["BY2", "BY2H", "BY2O"]):
        for m in MAIN:
            series = b.sequence_series(dataset, m)
            for ax, metric in zip(axs[ri], ["horizontal_err_m", "err_u_m", "yaw_err_deg"]):
                ax.plot(series.time, series[metric], **linekw(m))
        for ax in axs[ri]:
            ax.set_xlabel("Time (s)")
        axs[ri, 0].set_ylabel(dataset + "\nHorizontal error (m)")
        axs[ri, 1].set_ylabel("Up error (m)")
        axs[ri, 2].set_ylabel("Yaw error (°)")
    legend(axs[0, 0])
    return fig, "Three real sequences under the identical BY2-calibrated protocol-v2 sensor model, five configurations, evaluator v3. Curves use only frozen error samples. BY2H/BY2O are transferred-model evidence, not additional canonical degradation cases."


def mfig16(b):
    fig, axs = canvas(3, 2, 7.2)
    for ri, dataset in enumerate(["BY2", "BY2H", "BY2O"]):
        q = b.p.use(b.p.table("supplemental/SEQUENCE_QUALITY/" + dataset + ".csv"))
        for m in MAIN:
            s = b.sequence_series(dataset, m)
            axs[ri, 0].plot(s.time, s.yaw_err_deg, **linekw(m))
        axs[ri, 1].plot(q.time, q.yaw_std_deg, color="#333333", label="Heading-provider σ")
        valid = pd.to_numeric(q.valid, errors="raise").eq(1)
        b.notes.append({"sequence": dataset, "quality_scope": "Declared yaw sigma and heading presence only; no dynamic Source-Aware weights or full quality scores.",
                        "heading_observation_epochs": int(valid.sum()), "heading_absent_epochs": int((~valid).sum()),
                        "declared_sigma_values_deg": sorted(pd.to_numeric(q.yaw_std_deg).unique().tolist())})
        axs[ri, 1].scatter(q.loc[~valid, "time"], q.loc[~valid, "yaw_std_deg"], marker="x", s=7, color="#882255", label="Heading absent")
        axs[ri, 0].set_ylabel(dataset + "\nYaw error (°)")
        axs[ri, 1].set_ylabel("Heading-provider yaw σ (°)")
        if dataset == "BY2H":
            for ax in axs[ri]:
                ax.axvspan(618, 621, color="#bbbbbb", alpha=.3)
                ax.set_xlim(610, 630)
        if dataset == "BY2O":
            window = b.p.json("supplemental/SEQUENCE_QUALITY/OCCLUSION_WINDOW.json")
            for interval in window["all_runs"]:
                for ax in axs[ri]:
                    ax.axvspan(float(interval["t0"]), float(interval["t1"]), color="#bbbbbb", alpha=.3)
        axs[ri, 1].set_xlim(axs[ri, 0].get_xlim())
        for ax in axs[ri]:
            ax.set_xlabel("Time (s)")
    legend(axs[0, 0]); legend(axs[0, 1])
    return fig, "Yaw error and frozen A1 heading-provider quality on aligned time axes. Here A1 identifies the pre-existing heading provider, distinct from addendum outage family A1/D61. Quality fields are the frozen GNSS18 declared yaw standard deviation (column 15, yaw_std_deg) and heading validity (column 18, valid). This display is limited to declared sigma and heading presence; it does not show dynamic Source-Aware weights or full quality scores. These frozen inputs declare constant 1.5° yaw sigma; flag zero marks no heading observation at that provider epoch, not invalidity of every GNSS source. BY2H highlights the 618–621 s discontinuity; these fields are observation metadata, not truth. BY2O grey windows come from the frozen OCCLUSION_WINDOW input-status non-fixed intervals (fix_type != 8), not from output error; the status record does not assert every flagged epoch is a float solution."


def mfig17(b):
    frame = b.p.table(PARITY + "12_PARITY_GENERALIZATION/08_AGGREGATE/PARITY_DECOMPOSITION_BY_VERSION.csv")
    frame = b.p.use(frame[(frame.evaluator_contract == "evaluator_contract_v3") & (frame.decomposition_scope == "same_version")])
    fig, axs = canvas(1, 3, 3.7)
    for ax, dataset in zip(axs[0], ["BY2", "BY2H", "BY2O"]):
        sub = frame[frame.dataset_id == dataset]
        if sub.empty:
            raise EvidenceUnavailable("Missing decomposition dataset " + dataset)
        x = np.arange(len(sub))
        ax.plot(x, sub.horizontal_rmse_m, "o-", color=COLORS["F04"], label="Horizontal")
        ax.plot(x, sub.up_rmse_m, "s--", color=COLORS["A04"], label="Up")
        names = [str(x).replace("rate_IMU_same_point_contract", "Rate + IMU").replace("lever", "Lever") for x in sub.term]
        ax.set_xticks(x, names, rotation=40, ha="right")
        ax.set_ylabel(dataset + "\nPaired RMSE change (m)")
        ax.axhline(0, color="black", lw=.6)
        legend(ax)
    return fig, "Frozen v3 same-evaluator decomposition of the parity chain across three sequences. Values are recorded paired RMSE changes; they are not stacked as independent additive uncertainty sources. The time term retains its receiver-velocity same-epoch pairing qualification."


def mfig18(b):
    frame = b.p.use(b.p.table(CAL + "08_AGGREGATE/v3/BODY_FRAME_BIAS.csv"))
    fig, axs = canvas(1, 3, 3.7)
    for ax, dataset in zip(axs[0], ["BY2", "BY2H", "BY2O"]):
        sub = frame[frame.dataset_id == dataset].set_index("method_id")
        for i, m in enumerate(MAIN):
            row = sub.loc[m]
            ax.errorbar(i-.13, row.forward_signed_mean_m, yerr=row.forward_standard_deviation_m,
                        fmt="o", color=COLORS[m], ms=3, capsize=1, label="Forward" if i == 0 else None)
            ax.errorbar(i+.13, row.right_signed_mean_m, yerr=row.right_standard_deviation_m,
                        fmt="s", mfc="none", color=COLORS[m], ms=3, capsize=1, label="Right" if i == 0 else None)
        ax.axhline(0, color="black", lw=.6)
        ax.set_xticks(np.arange(5), MAIN, rotation=30)
        ax.set_ylabel(dataset + "\nBody-frame error mean ± SD (m)")
    fig.legend(*axs[0, 0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.55, 1.07), ncol=2)
    return fig, "Frozen body-frame horizontal error: circles forward, open squares right; whiskers are epoch standard deviations, not confidence intervals. The rotation uses native NAV yaw with no fitted shift or feedback."


def mfig19(b):
    frame = b.p.use(b.p.table(PARITY + "13_NOISE_MODEL_SENSITIVITY/08_AGGREGATE/v3/SENSITIVITY_GRID.csv"))
    fig, axs = canvas(1, 3, 3.8)
    for ax, (metric, label) in zip(axs[0], METRICS):
        grid = frame.pivot(index="abstd_mGal", columns="vrw_mps_sqrt_hour", values=metric).sort_index().sort_index(axis=1)
        if grid.shape != (3, 3) or grid.isna().any().any():
            raise EvidenceUnavailable("Noise sensitivity is not a complete frozen 3 × 3 grid")
        image = ax.imshow(grid.to_numpy(float), cmap="cividis", aspect="auto")
        ax.set_xticks(range(3), [f"{v:g}" for v in grid.columns], rotation=25)
        ax.set_yticks(range(3), [f"{v:g}" for v in grid.index])
        ax.set(xlabel="vrw (m/s/√h)", ylabel="abstd (mGal)")
        for y in range(3):
            for x in range(3):
                val = float(grid.iloc[y, x])
                normalized = image.norm(val)
                ax.text(x, y, f"{val:.3g}", ha="center", va="center", fontsize=7,
                        color="white" if normalized < .5 else "black")
        fig.colorbar(image, ax=ax, fraction=.06, pad=.28, label=label, orientation="horizontal")
    return fig, "Nine preregistered sensor-noise sensitivity settings, v3, A04. Cell values are frozen evaluation metrics. This sensitivity experiment is diagnostic and is not a post-hoc parameter-selection exercise."


def mfig20(b):
    samples = b.p.use(b.p.table(CAL + "00_CALIBRATION/LAG_VARIANCE_FIT.csv"))
    params = b.p.use(b.p.table(CAL + "00_CALIBRATION/CALIBRATED_PARAMETERS.csv"))
    fig, axs = canvas(1, 3, 3.1)
    for ax, axis in zip(axs[0], ["north", "east", "up"]):
        sub = samples[samples.axis == axis]
        par = params[params.axis == axis]
        if sub.empty or par.empty:
            # The source may use down for the third NED component.
            if axis == "up":
                sub = samples[samples.axis == "down"]; par = params[params.axis == "down"]
        if sub.empty or len(par) != 1:
            raise EvidenceUnavailable("Frozen calibration axis unavailable: " + axis)
        x = pd.to_numeric(sub.lag_s, errors="coerce"); y = pd.to_numeric(sub.variance_m2ps2, errors="coerce")
        ax.plot(x, y, "o", color=COLORS["A04"], ms=3, label="Observed")
        xx = np.array([x.min(), x.max()])
        row = par.iloc[0]
        ax.plot(xx, float(row.q_m2ps3)*xx+float(row.c_m2ps2), color=COLORS["F04"], label="Frozen qτ + c")
        ax.set(xlabel="Lag τ (s)", ylabel=axis.title() + " residual variance (m²/s²)")
        legend(ax)
    return fig, "BY2-only frozen calibration regression qτ + c. Markers are retained lag-variance observations and lines use the already accepted coefficients; no regression or calibration is refitted for this figure."


def mfig21(b):
    # Numeric geometry is sourced from the task-authorized frozen contract in
    # the package; an illustration must not silently invent lever-arm signs.
    geometry = b.p.json("PLOT_GEOMETRY_CONTRACT.json")
    geometry = geometry.get("physical_geometry", geometry)
    baseline = float(geometry["nominal_baseline_m"])
    lever = geometry["imu_to_gnss1_frd_m"]
    if abs(baseline-.350) > 1e-12 or len(lever) != 3:
        raise ValueError("Unexpected physical platform geometry")
    fig, axs = canvas(1, 2, 3.2)
    ax = axs[0, 0]
    ax.add_patch(Rectangle((-.16, -.27), .32, .54, facecolor="#eeeeee", edgecolor="#777777"))
    ax.scatter([baseline/2, -baseline/2], [0, 0], c=[COLORS["F02"], COLORS["A04"]], s=32)
    ax.text(baseline/2+.02, 0, "GNSS1\nright", va="center", fontsize=7)
    ax.text(-baseline/2-.02, 0, "GNSS2\nleft", va="center", ha="right", fontsize=7)
    ax.annotate("", (-baseline/2, .1), (baseline/2, .1), arrowprops={"arrowstyle": "<->", "color": "black"})
    ax.text(0, .12, f"{baseline:.3f} m", ha="center", fontsize=7)
    ax.annotate("+X forward", (0, .42), (0, .2), arrowprops={"arrowstyle": "->"}, ha="center", fontsize=7)
    ax.annotate("+Y right (FRD)", (.4, -.18), (.12, -.18), arrowprops={"arrowstyle": "->"}, fontsize=7)
    ax.set(xlim=(-.45, .6), ylim=(-.35, .48), aspect="equal")
    ax.axis("off")
    ax = axs[0, 1]
    ax.scatter([0, lever[0]], [0, -lever[2]], color=["black", COLORS["F02"]], s=28)
    ax.annotate("", (lever[0], -lever[2]), (0, 0), arrowprops={"arrowstyle": "->", "color": "#777777"})
    ax.text(-.025, .005, "IMU", ha="right", fontsize=7)
    ax.text(lever[0], -lever[2]+.03, "GNSS1", ha="center", fontsize=7)
    ax.text(.5, .1, "IMU → GNSS1 (FRD)\n" + str(tuple(lever)) + " m", transform=ax.transAxes, ha="center", fontsize=7)
    ax.set(xlim=(-.2, .25), ylim=(-.12, .45), xlabel="Forward offset (m)", ylabel="Up offset (m)", aspect="equal")
    return fig, "Platform geometry schematic, not a scale drawing of the robot. The antenna vector is GNSS2 − GNSS1 (physical left); body-yaw conversion and the FRD lever arm follow the immutable contract. Receiver IMU and Go2 body IMU remain distinct."


def mfig22(b):
    table = b.aggregate("V1_V2_PAIRWISE_COMPARISON.csv")
    pairs = ["full_vs_strong", "full_vs_no_SA", "full_vs_no_RD", "full_vs_no_RP", "full_vs_no_HV", "A04_vs_F03"]
    fig, axs = canvas(1, 2, 4.6)
    for ax, metric, factor, unit in [(axs[0, 0], "horizontal_rmse_m", 1000, "mm"),
                                     (axs[0, 1], "yaw_rmse_deg", 1, "°")]:
        sub = b.p.use(table[(table.metric_name == metric) & table.comparison.isin(pairs)])
        sub = sub.set_index("comparison").reindex(pairs)
        if sub.median_direction_status.isna().any():
            raise EvidenceUnavailable("Frozen median_direction_status missing")
        for i, (_, row) in enumerate(sub.iterrows()):
            x = np.array([row.v1_median_delta, row.v2_median_delta], float)*factor
            ax.plot(x, [i, i], color="#bbbbbb", lw=1)
            ax.plot(x[0], i, "o", color=COLORS["A04"], label="Protocol v1" if i == 0 else None)
            ax.plot(x[1], i, "s", color=COLORS["F04"], label="Protocol v2" if i == 0 else None)
        labels = []
        for key, row in sub.iterrows():
            status, near, tol = near_zero_direction(row)
            labels.append(key.replace("full_vs_", "F04 − ").replace("A04_vs_", "A04 − ") +
                          "\n" + status + ("; near zero" if near else ""))
        ax.set_yticks(np.arange(len(sub)), labels)
        ax.axvline(0, color="black", lw=.6)
        ax.set_xlabel("Median paired delta (" + unit + ")")
        ax.invert_yaxis()
    fig.legend(*axs[0, 0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.56, 1.035), ncol=2)
    return fig, "v1 (circles) and v2 (squares) frozen median paired deltas. Labels use median_direction_status rather than the completeness classification. A pair is marked near zero only when both protocol magnitudes are at most 2 mm or 0.02°; a small sign flip is not promoted to a material effect."


def sfig01(b):
    u = b.core()
    metrics = [*METRICS, ("roll_rmse_deg", "Roll RMSE (°)"), ("pitch_rmse_deg", "Pitch RMSE (°)"),
               ("position_3d_rmse_m", "3D RMSE (m)")]
    fig, axs = canvas(2, 3, 8.1)
    for ax, (metric, label) in zip(axs.flat, metrics):
        frame = u[u.degradation_id != "CLEAN"].pivot_table(index="degradation_id", columns="profile", values=metric, aggfunc="mean").reindex(columns=MAIN)
        data = frame.to_numpy(float)
        mask = np.ma.masked_invalid(data)
        image = ax.imshow(mask, aspect="auto", cmap="cividis", norm=LogNorm(vmin=float(mask.min()), vmax=float(mask.max())))
        ax.set_xticks(range(5), MAIN, rotation=40)
        ax.set_yticks([0, 9, 19, 29, 39, 49, 59], ["D01", "D10", "D20", "D30", "D40", "D50", "D60"])
        fig.colorbar(image, ax=ax, label=label, fraction=.046, pad=.03)
    return fig, "60 degradation types × five configurations, finite-case mean frozen RMSE, log color scales. Missing means are masked rather than set to zero. Failure rates are reported separately."


def sfig02(b):
    external = b.p.use(b.p.table(CAL + "08_AGGREGATE/v3/EXTERNAL_BY2_V3_REFERENCE.csv"))
    registry = b.p.table("supplemental/HORIZONTAL/FINAL_METHOD_REGISTRY_V2.csv")
    registry = b.p.use(registry[registry.comparison_layer != "INTERNAL_LEGSA_METHOD"])
    compatibility = b.p.table("supplemental/HORIZONTAL/OUTPUT_AND_METRIC_COMPATIBILITY.csv")
    b.p.use(compatibility[compatibility.method_id.isin(registry.method_id)])
    internal = b.core(["A04", "F04"], case_id="C00_clean_normal")
    fig, axs = canvas(1, 3, 4.5)
    external_ids = list(registry.method_id.astype(str))
    external_ids += [m for m in external.method_id.astype(str) if m not in external_ids]
    methods = external_ids + ["A04", "F04"]
    for ax, (metric, label) in zip(axs[0], METRICS):
        for i, method in enumerate(external_ids):
            found = external[external.method_id == method]
            if found.empty:
                ax.text(.02, i, "Not comparable", transform=ax.get_yaxis_transform(), fontsize=7, va="center")
                continue
            if len(found) != 1:
                raise EvidenceUnavailable("Duplicate external v3 identity: " + method)
            row = found.iloc[0]
            state = str(row.get("evaluation_status", ""))
            value = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
            if state == "COMPLETED" and np.isfinite(value):
                ax.plot(value, i, "o", color="#777777", ms=4)
            else:
                ax.text(.02, i, "Not comparable", transform=ax.get_yaxis_transform(), fontsize=7, va="center")
        for j, method in enumerate(["A04", "F04"]):
            row = internal[internal.profile == method].iloc[0]
            ax.plot(float(row[metric]), len(external_ids)+j, "s", color=COLORS[method], ms=5)
        ax.set_yticks(np.arange(len(methods)), [LABEL.get(m, m) for m in methods] if ax is axs[0, 0] else [""]*len(methods))
        ax.set_xlabel(label)
        maximum = max(float(pd.to_numeric(external[metric], errors="coerce").max()),
                      float(pd.to_numeric(internal[metric], errors="coerce").max()))
        ax.set_xlim(0, maximum*1.15)
        ax.set_ylim(-.6, len(methods)-.4)
        ax.invert_yaxis()
    return fig, "Horizontal method comparison at the v3 evaluation point. Internal LegSA rows are protocol-v2 C00 F04 and A04. External methods lacking compatible IMU-point NAV remain listed as Not comparable; no incompatible native metric is substituted. Source roles and finite coverage remain those of the frozen external reference table."


def horizontal01(b):
    registry = b.p.use(b.p.table("supplemental/HORIZONTAL/FINAL_METHOD_REGISTRY_V2.csv"))
    b.p.use(b.p.table("supplemental/HORIZONTAL/OUTPUT_AND_METRIC_COMPATIBILITY.csv"))
    required = {"RAW01", "RAW02", "RAW03", "LC01", "LC02", "LSE01", "A04", "F04"}
    if not required <= set(registry.method_id):
        raise EvidenceUnavailable("Incomplete horizontal information hierarchy")
    fig, axs = canvas(1, 1, 4.5)
    ax = axs[0, 0]; ax.axis("off")
    rows = [
        ("Carrier / Doppler observations", "EXT01 / EXT02 / EXT03", "Baseline and heading states"),
        ("Receiver navigation solutions", "LC01 / GINav", "Solution-level navigation"),
        ("IMU and leg kinematics", "Hartley InEKF", "Relative state and observability"),
        ("Dual GNSS + receiver IMU\nDoppler + weak body priors", "F04 (proposed)\nA04 (ablation)", "Full navigation estimate"),
    ]
    for i, (left, middle, right) in enumerate(rows):
        y = .85-i*.22
        for x, text, color in [(.02, left, "#eef1f3"), (.38, middle, "#edf4f8"), (.72, right, "#f7f3ed")]:
            ax.add_patch(Rectangle((x, y-.07), .26, .15, transform=ax.transAxes,
                                  facecolor=color, edgecolor="#777777", lw=.6))
            ax.text(x+.13, y, text, transform=ax.transAxes, ha="center", va="center", fontsize=7)
        for a, c in [(.285, .375), (.645, .715)]:
            ax.annotate("", xy=(c, y), xytext=(a, y), xycoords="axes fraction",
                        arrowprops={"arrowstyle": "->", "color": "#555555", "lw": .8})
    return fig, "Information hierarchy of the frozen horizontal-method registry. Arrows denote input-to-method-to-output flow, not a ranking. Raw baseline methods, solution-level navigation and proprioceptive structural evidence retain distinct observation and output roles. F04 is the proposed manuscript method."


def horizontal02(b):
    external = b.p.use(b.p.table(CAL + "08_AGGREGATE/v3/EXTERNAL_BY2_V3_REFERENCE.csv"))
    registry = b.p.table("supplemental/HORIZONTAL/FINAL_METHOD_REGISTRY_V2.csv")
    b.p.use(registry[registry.method_id.isin(["LC01", "LC02", "A04", "F04"])])
    internal = b.core(["A04", "F04"], case_id="C00_clean_normal")
    methods = ["LC01", "LC02", "A04", "F04"]
    fig, axs = canvas(2, 3, 5.3)
    metrics = [*METRICS, ("roll_rmse_deg", "Roll RMSE (°)"), ("pitch_rmse_deg", "Pitch RMSE (°)"),
               ("coverage_ratio", "Matched output fraction")]
    for ax, (metric, label) in zip(axs.flat, metrics):
        for i, method in enumerate(methods):
            rows = internal[internal.profile == method] if method in ("A04", "F04") else external[external.method_id == method]
            value = pd.to_numeric(rows[metric], errors="coerce") if len(rows) else pd.Series(dtype=float)
            if len(value) == 1 and np.isfinite(value.iloc[0]):
                ax.bar(i, value.iloc[0], width=.6, color=COLORS.get(method, "#777777"),
                       hatch="//" if method == "A04" else None)
            else:
                ax.text(i, .03, "Not\ncomparable", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(4), ["LC01", "GINav", "A04", "F04"], rotation=25)
        ax.set_ylabel(label)
        ax.set_ylim(bottom=0)
    return fig, "Formal C00 solution-level comparison using compatible frozen v3 metrics: LC01 and protocol-v2 A04/F04. GINav is retained explicitly as Not comparable because no compatible completed v3 C00 evaluation is available. Coverage is the matched-output fraction on each native support, not a common-support or epoch-count equality claim."


def horizontal03(b):
    root = "supplemental/HORIZONTAL/"
    primary = b.p.use(b.p.table(root + "RAW_PRIMARY_METHOD_C00_SUMMARY.csv"))
    available = b.p.table(root + "RAW_AVAILABILITY_AND_STATE_SUMMARY.csv")
    heading = b.p.table(root + "RAW_BASELINE_AND_HEADING_SUMMARY.csv")
    failures = b.p.table(root + "RAW_RUNTIME_AND_FAILURE_SUMMARY.csv")
    fig, axs = canvas(2, 2, 5.6)
    methods = ["RAW01", "RAW02", "RAW03"]
    labels = ["EXT01\nCertified integer", "EXT02\nWrapped accepted", "EXT03\nValid baseline"]
    selected_a, selected_h, selected_f = [], [], []
    for method in methods:
        p = primary[primary.method_id == method]
        if len(p) != 1:
            raise EvidenceUnavailable("Missing raw primary mode: " + method)
        mode = p.iloc[0].primary_mode_key
        for source, dest in [(available, selected_a), (heading, selected_h), (failures, selected_f)]:
            selected = b.p.use(source[(source.method_id == method) & (source.mode_key == mode)])
            if len(selected) != 1:
                raise EvidenceUnavailable("Raw mode is not uniquely matched to frozen primary identity")
            dest.append(selected.iloc[0])
    a, h, f = pd.DataFrame(selected_a), pd.DataFrame(selected_h), pd.DataFrame(selected_f)
    x = np.arange(3)
    axs[0, 0].bar(x, pd.to_numeric(a.valid_count), color="#0072B2", label="Native output")
    axs[0, 0].bar(x, pd.to_numeric(a.invalid_count), bottom=pd.to_numeric(a.valid_count), color="#cccccc", label="Invalid / no output")
    axs[0, 0].set_ylabel("Input epochs (count)")
    for i, row in enumerate(selected_a):
        axs[0, 0].text(i, float(row.input_epochs)+15, f"{int(row.valid_count)}/{int(row.input_epochs)}", ha="center", fontsize=7)
    legend(axs[0, 0])
    axs[0, 1].plot(x-.08, pd.to_numeric(h.baseline_heading_resultant_length), "o", color="#0072B2", label="Baseline heading")
    axs[0, 1].plot(x+.08, pd.to_numeric(h.body_yaw_resultant_length), "s", mfc="none", color="#D55E00", label="Converted body yaw")
    axs[0, 1].set(ylabel="Native angular resultant length", ylim=(0, 1.05))
    legend(axs[0, 1])
    axs[1, 0].plot(x-.08, pd.to_numeric(h.baseline_length_median_m), "o", color="#0072B2", label="Median")
    axs[1, 0].plot(x+.08, pd.to_numeric(h.baseline_length_p95_m), "s", mfc="none", color="#D55E00", label="P95")
    axs[1, 0].axhline(.350, color="#777777", ls=":", lw=.8, label="Hard-constraint nominal")
    axs[1, 0].set_ylabel("Baseline length (m)")
    legend(axs[1, 0])
    counts = [json.loads(str(row.failure_code_counts)) for row in selected_f]
    categories = sorted(set().union(*(set(row) for row in counts)))
    # Per-method stacked composition is native terminal accounting, with each
    # category kept explicit in the source manifest and the caption.
    bottom = np.zeros(3)
    palette = ["#999999", "#0072B2", "#D55E00", "#CC79A7", "#E69F00", "#009E73"]
    short = {"INSUFFICIENT_CP_VALID": "Carrier validity", "INSUFFICIENT_DD_DIMENSION": "DD dimension",
             "INSUFFICIENT_HALF_CYCLE_VALID": "Half-cycle validity", "INSUFFICIENT_SATELLITE_STATES": "Satellite states",
             "NUMERICAL_FAILURE": "Numerical", "GNSS1_PNTPOS_REJECTED": "GNSS1 PVT rejected",
             "GNSS2_PNTPOS_REJECTED": "GNSS2 PVT rejected",
             "INSUFFICIENT_GPS_DUAL_FREQUENCY_COMMON_SATELLITES": "Dual-frequency satellites"}
    for ci, category in enumerate(categories):
        values = np.array([row.get(category, 0) for row in counts], float)
        axs[1, 1].bar(x, values, bottom=bottom, color=palette[ci % len(palette)],
                       hatch="//" if ci >= len(palette) else None, label=short.get(category, category.replace("_", " ").title()))
        bottom += values
    axs[1, 1].set_ylabel("Native failure events (count)")
    fig.legend(*axs[1, 1].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.55, -.025), ncol=3,
               title="Native failure events in panel (d)", title_fontsize=7, fontsize=7)
    for ax in axs.flat:
        ax.set_xticks(x, labels)
    return fig, "Raw dual-antenna applicability on the frozen primary BY2 modes. Native output states are not a shared fix-success measure: certified integers, accepted wrapped solutions and EXT03 valid baselines retain distinct meanings and unknown ambiguity correctness. Angular resultant lengths describe native concentration, not absolute yaw accuracy. A hard-constrained 0.350 m baseline is not independent accuracy evidence; none of these outputs supplies comparable v3 IMU-point navigation metrics."


def horizontal04(b):
    root = "supplemental/HORIZONTAL/"
    gauge = b.p.use(b.p.table(root + "HARTLEY_GAUGE_EQUIVALENCE_SUMMARY.csv"))
    obs = b.p.use(b.p.table(root + "HARTLEY_OBSERVABILITY_SUMMARY.csv"))
    spectrum = b.p.table(root + "OBSERVABILITY_SINGULAR_VALUES_R1.csv")
    spectrum = b.p.use(spectrum[spectrum.normalization == "RAW_STRUCTURAL"])
    fig, axs = canvas(2, 2, 5.7)
    x = pd.to_numeric(gauge.initial_yaw_deg)
    for metric, marker, color, label in [
        ("orientation_geodesic_difference_rad", "o", "#0072B2", "Orientation"),
        ("position_difference_m", "s", "#D55E00", "Position"),
        ("velocity_difference_m_per_s", "^", "#009E73", "Velocity")]:
        normalized = pd.to_numeric(gauge[metric+"_max"])/pd.to_numeric(gauge[metric+"_tolerance"])
        axs[0, 0].plot(x, normalized, marker=marker, color=color, ms=3, label=label)
    axs[0, 0].axhline(1, color="#777777", lw=.7, ls=":")
    axs[0, 0].set(xlabel="Initial yaw gauge offset (°)", ylabel="Maximum difference / tolerance")
    legend(axs[0, 0])
    yaw = pd.to_numeric(gauge.native_yaw_offset_residual_rad_max)/pd.to_numeric(gauge.native_yaw_offset_residual_rad_tolerance)
    inc = pd.to_numeric(gauge.relative_yaw_increment_difference_rad_max)/pd.to_numeric(gauge.relative_yaw_increment_difference_rad_tolerance)
    axs[0, 1].plot(x, yaw, "o-", color="#0072B2", ms=3, label="Yaw-offset residual")
    axs[0, 1].plot(x, inc, "s--", color="#D55E00", ms=3, label="Relative yaw increment")
    axs[0, 1].axhline(1, color="#777777", lw=.7, ls=":")
    axs[0, 1].set(xlabel="Initial yaw gauge offset (°)", ylabel="Maximum difference / tolerance")
    legend(axs[0, 1])
    for i, model in enumerate(["IDEAL_BIAS_FREE", "BIAS_AUGMENTED"]):
        sub = obs[obs.model == model].sort_values("window_id")
        offset = -.16 if i == 0 else .16
        xx = np.arange(len(sub))+offset
        axs[1, 0].bar(xx, sub.rank_at_base_threshold, width=.3, color=["#0072B2", "#D55E00"][i],
                       label=["Bias-free rank", "Bias-augmented rank"][i])
        axs[1, 0].bar(xx, sub.nullity_at_base_threshold, bottom=sub.rank_at_base_threshold, width=.3,
                       color="#dddddd", hatch="//", label="Nullity" if i == 0 else None)
    axs[1, 0].set_xticks(range(5), ["4 feet\nW0", "4 feet\nW1", "2 feet\nW2", "2 feet\nW3", "2 feet\nW4"])
    axs[1, 0].set_ylabel("State rank + nullity (count)")
    legend(axs[1, 0])
    for (model, window), sub in spectrum.groupby(["model", "window_id"]):
        sub = sub.sort_values("singular_index_descending")
        vals = sub.singular_value.to_numpy(float)
        if not len(vals) or vals[0] <= 0:
            raise EvidenceUnavailable("Invalid frozen observability singular spectrum")
        color = "#0072B2" if model == "IDEAL_BIAS_FREE" else "#D55E00"
        axs[1, 1].plot(sub.singular_index_descending+1, vals/vals[0], color=color, alpha=.6,
                       ls="-" if model == "IDEAL_BIAS_FREE" else "--", lw=.7,
                       label=("Bias-free" if model == "IDEAL_BIAS_FREE" else "Bias-augmented") if window == "WIN000" else None)
    axs[1, 1].set_yscale("symlog", linthresh=1e-12)
    axs[1, 1].set(xlabel="Descending singular-value index", ylabel="Singular value / largest")
    legend(axs[1, 1])
    return fig, "Hartley yaw unobservability from the frozen gauge ensemble and structural analysis, without an absolute navigation-error ranking. Panels (a,b) show exact normalized gauge-equivalence residuals against frozen tolerances; (c) the registered 4- and 2-contact rank/nullity, with four known gauge dimensions; (d) all frozen raw-structural singular spectra normalized by their own largest singular value. The symmetric-log floor retains exact zeros. No reference trace is used."


FIGURES = {
    "MFIG00": ("C00 reference trajectory and attitude", mfig00, "Reissued", "Results: nominal sequence", "Experimental results: nominal sequence"),
    "MFIG01": ("Canonical-541 matrix overview", mfig01, "Reissued", "Results: degradation library", "Robustness evaluation"),
    "MFIG02": ("A04 versus F03 seed consistency", mfig02, "Reissued", "Ablation study", "Ablation study"),
    "MFIG03": ("Source-Aware paired tradeoffs", mfig03, "Reissued", "Robustness: quality weighting", "Protective weighting analysis"),
    "MFIG04": ("Five-configuration ablation ladder", mfig04, "Reissued", "Method ablation", "Component verification"),
    "MFIG05": ("Favorable and adverse representative cases", mfig05, "Reissued", "Degradation case study", "Failure and recovery cases"),
    "MFIG06": ("Mechanism action counters", mfig06, "Reissued", "Mechanism evidence", "Measurement update diagnostics"),
    "MFIG07": ("Yaw RMSE distributions and worst-five-percent means", mfig07, "New", "Tail robustness", "Tail error assessment"),
    "MFIG08": ("Individual-module yaw tails", mfig08, "New", "Ablation: tail behavior", "Component tail sensitivity"),
    "MFIG09": ("D05 velocity-aid outage trajectories", lambda b: outage_curves(b, "D05"), "New", "Velocity redundancy", "Degradation and redundancy"),
    "MFIG10": ("A1 all-GNSS outage trajectories", lambda b: outage_curves(b, "D61"), "New", "Addendum A1", "Complete-GNSS outage study"),
    "MFIG11": ("A2 heading-retained outage trajectories", lambda b: outage_curves(b, "D62"), "New", "Addendum A2", "Heading-retained outage study"),
    "MFIG12": ("Outage-end horizontal error versus duration", mfig12, "New", "Velocity redundancy addendum", "Duration-dependent degradation"),
    "MFIG13": ("Algorithm failures by family", mfig13, "New", "Failure-aware results", "Failure accounting"),
    "MFIG14": ("All-yaw-rejected timeline and F02 control", mfig14, "New", "Adverse mechanism example", "Gating failure diagnostics"),
    "MFIG15": ("Three-sequence five-configuration error histories", mfig15, "New", "Real-sequence transfer", "Cross-sequence verification"),
    "MFIG16": ("Yaw errors and heading-provider quality", mfig16, "New", "Observation quality", "Input-quality diagnostics"),
    "MFIG17": ("Error-budget parity steps", mfig17, "New", "Error budget", "Uncertainty and systematic effects"),
    "MFIG18": ("Three-sequence body-frame bias", mfig18, "New", "Body-frame error analysis", "Systematic-error diagnostics"),
    "MFIG19": ("Frozen nine-setting noise sensitivity", mfig19, "New", "Noise-model sensitivity", "Sensor model sensitivity"),
    "MFIG20": ("Frozen calibration regression", mfig20, "New", "Sensor-noise calibration", "Calibration methodology"),
    "MFIG21": ("Platform and antenna geometry", mfig21, "New", "System setup", "Measurement geometry"),
    "MFIG22": ("Protocol v1–v2 comparison and effect scale", mfig22, "New", "Protocol comparison", "Protocol sensitivity"),
    "SFIG01": ("Type-by-configuration error heatmaps", sfig01, "Supplementary", "Supplement: degradation tables", "Supplement: complete robustness grid"),
    "SFIG02": ("External-method v3 point comparability", sfig02, "Supplementary", "Literature comparison", "Benchmark comparability"),
    "FIG01": ("Horizontal comparison information hierarchy", horizontal01, "New horizontal", "Comparison information hierarchy", "Measurement information hierarchy"),
    "FIG02": ("Formal C00 solution-level navigation comparison", horizontal02, "New horizontal", "Solution-level comparison", "Navigation benchmark"),
    "FIG03": ("Raw dual-antenna BY2 applicability", horizontal03, "New horizontal", "Raw-observation method applicability", "Raw GNSS method applicability"),
    "FIG04": ("Hartley yaw unobservability", horizontal04, "New horizontal", "Proprioceptive observability", "Gauge and observability analysis"),
}
