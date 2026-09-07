"""Canonical-541 publication figures (AGENTS section 12b).

Every renderer takes a :class:`~.loaders.Bundle`, reads frozen or derived tables
only, and returns ``(fig, caption)``.  Delta convention: candidate - reference,
negative is better.  Favourable and unfavourable representative cases are always
drawn together (AGENTS section 7A.10).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

from . import style
from .loaders import Bundle

FAMILY_SHORT = {
    "dual_yaw": "Yaw", "gnss_outage": "Outage", "gnss_sampling": "Sampling", "position_value": "Pos. value",
    "position_std_status": "Pos. std", "velocity_raw_doppler": "Vel./Dopp.", "go2_prior_metadata": "Go2 prior",
    "multi_source_mixed": "Mixed", "clean": "Clean",
}
MAIN_METHODS = ["F01", "F02", "F03", "A04", "F04"]


def _ecdf(ax, values, **kw):
    v = np.sort(np.asarray(values, dtype=float))
    ax.step(v, np.arange(1, v.size + 1) / v.size, where="post", **kw)


def _method_style(m):
    return dict(color=style.COLORS[m], ls=style.LINESTYLES[m], lw=style.LINEWIDTHS[m])


def _labels(b: Bundle, methods):
    return [b.label_of(m) for m in methods]


def _family_order(b: Bundle):
    return list(b.names["family_order"])


# ------------------------------------------------------------------ MFIG00
def _local_enu(lat_deg, lon_deg, h, lat0_deg, lon0_deg, h0):
    lat0, lon0 = np.deg2rad(lat0_deg), np.deg2rad(lon0_deg)
    east = (np.deg2rad(lon_deg) - lon0) * np.cos(lat0) * 6378137.0
    north = (np.deg2rad(lat_deg) - lat0) * 6378137.0
    return east, north, np.asarray(h, float) - h0


TRACE_CONSISTENCY_TOL_M = 0.05
TRACE_CONSISTENCY_TOL_DEG = 0.5


def mfig00_reference_comparison(b: Bundle):
    """Clean-case Core estimate against the reference.

    With a trace path the reference is read from the hash-locked trace using the evaluator's frozen time
    origin and yaw formula (no re-alignment), and a consistency gate checks that "estimate minus frozen
    error" reproduces the trace at the matched epochs.  Without a trace path the reference is reconstructed
    from the frozen error series alone."""
    from . import derived_tables as dt

    fig, axes = style.new_figure(2, 2, 5.4, hspace=0.55, wspace=0.32)
    (a1, a2), (a3, a4) = axes
    ref_label = b.names["reference_label"]
    core_cfg = b.config_of("A04")
    s = b.series_for(dt.CLEAN_CASE_ID, core_cfg)
    row = b.unique[(b.unique["case_id"] == dt.CLEAN_CASE_ID) & (b.unique["effective_configuration_id"] == core_cfg)].iloc[0]
    _, nav_path = b.series_resolver(row)
    if s is None or nav_path is None:
        raise FileNotFoundError("C00 Core error series or NAV file not resolvable")
    nav = dt.read_nav(nav_path)
    t = s["time"].to_numpy(float)
    tow = nav.iloc[:, 1].to_numpy(float)
    est_lat = np.interp(t, tow, nav.iloc[:, 2].to_numpy(float)); est_lon = np.interp(t, tow, nav.iloc[:, 3].to_numpy(float))
    est_h = np.interp(t, tow, nav.iloc[:, 4].to_numpy(float))
    est_yaw = np.rad2deg(np.interp(t, tow, np.unwrap(np.deg2rad(nav.iloc[:, 10].to_numpy(float)))))
    trace = b.reference_trace()
    if trace is not None:
        tr = trace[(trace["t"] >= t[0] - 1.0) & (trace["t"] <= t[-1] + 1.0)]
        tt = tr["t"].to_numpy(float)
        ref_lat = np.interp(t, tt, tr["lat"].to_numpy(float)); ref_lon = np.interp(t, tt, tr["lon"].to_numpy(float))
        ref_h = np.interp(t, tt, tr["height"].to_numpy(float))
        ref_yaw = np.rad2deg(np.interp(t, tt, np.unwrap(np.deg2rad(tr["yaw_ned_deg"].to_numpy(float)))))
        origin = (ref_lat[0], ref_lon[0], ref_h[0])
        e_est, n_est, h_est = _local_enu(est_lat, est_lon, est_h, *origin)
        e_ref, n_ref, h_ref = _local_enu(ref_lat, ref_lon, ref_h, *origin)
        # consistency gate: estimate minus frozen error must reproduce the trace at the matched epochs
        d_e = (e_est - s["err_e_m"].to_numpy(float)) - e_ref
        d_n = (n_est - s["err_n_m"].to_numpy(float)) - n_ref
        d_u = (h_est - s["err_u_m"].to_numpy(float)) - h_ref
        d_yaw = (est_yaw - s["yaw_err_deg"].to_numpy(float)) - ref_yaw
        d_yaw = (d_yaw + 180.0) % 360.0 - 180.0
        worst_m = float(np.nanmax(np.hypot(d_e, d_n))); worst_u = float(np.nanmax(np.abs(d_u))); worst_yaw = float(np.nanmax(np.abs(d_yaw)))
        if worst_m > TRACE_CONSISTENCY_TOL_M or worst_u > TRACE_CONSISTENCY_TOL_M or worst_yaw > TRACE_CONSISTENCY_TOL_DEG:
            raise RuntimeError(f"trace/evaluator inconsistency: horizontal {worst_m:.3f} m, up {worst_u:.3f} m, yaw {worst_yaw:.3f} deg")
        source_note = (f"Reference curves are read from the hash-locked trace with the evaluator's frozen time origin and yaw convention; "
                       f"they agree with estimate-minus-frozen-error to {100*worst_m:.1f} cm horizontally, {100*worst_u:.1f} cm vertically and {worst_yaw:.2f}° in yaw.")
    else:
        origin = (est_lat[0], est_lon[0], est_h[0])
        e_est, n_est, h_est = _local_enu(est_lat, est_lon, est_h, *origin)
        e_ref, n_ref, h_ref = e_est - s["err_e_m"].to_numpy(float), n_est - s["err_n_m"].to_numpy(float), h_est - s["err_u_m"].to_numpy(float)
        ref_yaw = est_yaw - s["yaw_err_deg"].to_numpy(float)
        source_note = "Reference curves are reconstructed at the evaluator's matched epochs as estimate minus frozen error (no trace file given)."
    # (a) trajectory
    a1.plot(e_ref, n_ref, color="black", lw=1.4, label=ref_label)
    a1.plot(e_est, n_est, color=style.COLORS["A04"], lw=0.8, label=b.label_of("A04"))
    a1.plot(e_ref[0], n_ref[0], "o", color="black", ms=3); a1.text(e_ref[0], n_ref[0], "  start", fontsize=style.MIN_TEXT_PT, va="center")
    a1.set_xlabel("East (m)"); a1.set_ylabel("North (m)"); a1.set_aspect("equal", adjustable="datalim"); a1.legend(loc="best")
    # (b) yaw versus time
    a2.plot(t, ref_yaw, color="black", lw=1.2, label=ref_label)
    a2.plot(t, est_yaw, color=style.COLORS["A04"], lw=0.8, label=b.label_of("A04"))
    a2.set_xlabel("Time (s)"); a2.set_ylabel("Yaw, unwrapped (°)"); a2.legend(loc="upper right", ncol=2)
    # (c) yaw error for the baselines and Core
    for m in ("F01", "F02", "A04"):
        sm = b.series_for(dt.CLEAN_CASE_ID, b.config_of(m))
        if sm is not None:
            a3.plot(sm["time"], sm["yaw_err_deg"], label=b.label_of(m), **_method_style(m))
    a3.set_xlabel("Time (s)"); a3.set_ylabel("Yaw error (°)"); a3.legend(loc="upper right", ncol=3, columnspacing=0.8)
    # (d) height versus time, common origin so that the constant offset stays visible
    a4.plot(t, h_ref, color="black", lw=1.2, label=ref_label)
    a4.plot(t, h_est, color=style.COLORS["A04"], lw=0.8, label=b.label_of("A04"))
    a4.set_xlabel("Time (s)"); a4.set_ylabel("Height relative to reference start (m)"); a4.legend(loc="upper right", ncol=2)
    for ax in (a2, a3, a4):
        ax.set_xlim(60, 345)
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter, x=-0.18)
    yaw_rmse = {m: b.method_stat(b.config_of(m), "yaw_rmse_deg", "mean") for m in ("F01", "F02", "A04")}
    caption = (
        f"Clean case (C00): Core estimate against the reference ({ref_label}). (a) Horizontal trajectory in a local east-north frame; "
        f"(b) yaw; (c) yaw error of Single ({yaw_rmse['F01']:.2f}° RMSE), Dual-basic ({yaw_rmse['F02']:.2f}°) and Core ({yaw_rmse['A04']:.2f}°); "
        f"(d) height. {source_note}"
    )
    return fig, caption


# ------------------------------------------------------------------ MFIG01
def mfig01_matrix_overview(b: Bundle):
    fig, axes = style.new_figure(2, 2, 5.2, hspace=0.5, wspace=0.32)
    (a1, a2), (a3, a4) = axes
    x = np.arange(len(MAIN_METHODS))
    cfgs = [b.config_of(m) for m in MAIN_METHODS]
    cols = [style.COLORS[m] for m in MAIN_METHODS]
    labels = _labels(b, MAIN_METHODS)
    # (a) horizontal
    means = [b.method_stat(c, "horizontal_rmse_m", "mean") for c in cfgs]
    medians = [b.method_stat(c, "horizontal_rmse_m", "median") for c in cfgs]
    a1.bar(x, means, color=cols, width=0.62, label="Mean over 541 cases")
    a1.plot(x, medians, "D", color="black", ms=3.2, label="Median")
    a1.set_xticks(x); a1.set_xticklabels(labels, rotation=20, ha="right")
    a1.set_ylabel("Horizontal RMSE (m)")
    a1.set_ylim(0, 1.5)
    a1.legend(loc="upper right")
    # (b) yaw
    ym = [b.method_stat(c, "yaw_rmse_deg", "mean") for c in cfgs]
    ymed = [b.method_stat(c, "yaw_rmse_deg", "median") for c in cfgs]
    yp95 = [b.method_stat(c, "yaw_rmse_deg", "p95") for c in cfgs]
    a2.bar(x, ym, color=cols, width=0.62, label="Mean")
    a2.plot(x, ymed, "D", color="black", ms=3.2, label="Median")
    a2.plot(x, yp95, "v", color="black", ms=3.6, mfc="white", label="P95")
    a2.set_yscale("log"); a2.set_ylim(1, 400)
    a2.set_xticks(x); a2.set_xticklabels(labels, rotation=20, ha="right")
    a2.set_ylabel("Yaw RMSE (°)")
    a2.legend(loc="upper right", ncol=3, columnspacing=0.8)
    # (c)(d) ECDFs
    for m, c, lab in zip(MAIN_METHODS, cfgs, labels):
        _ecdf(a3, b.metric_values("horizontal_rmse_m", c), label=lab, **_method_style(m))
        _ecdf(a4, b.metric_values("yaw_rmse_deg", c), label=lab, **_method_style(m))
    a3.set_xscale("log"); a3.set_xlabel("Horizontal RMSE (m)"); a3.set_ylabel("ECDF over 541 cases (fraction)")
    a4.set_xscale("log"); a4.set_xlabel("Yaw RMSE (°)"); a4.set_ylabel("ECDF over 541 cases (fraction)")
    a3.set_ylim(0, 1.02); a4.set_ylim(0, 1.02)
    a3.legend(loc="lower right"); a4.legend(loc="lower right")
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter)
    caption = (
        "541-case matrix overview relative to the same-source reference. Bars are means, diamonds medians, "
        f"triangles P95. Horizontal RMSE mean: Dual-basic {means[1]:.3f} m, Backbone {means[2]:.3f} m, Core {means[3]:.3f} m, "
        f"Full {means[4]:.3f} m; yaw RMSE median Core {ymed[3]:.2f}°, yaw P95 Backbone {yp95[2]:.1f}° versus Full {yp95[4]:.1f}°."
    )
    return fig, caption


# ------------------------------------------------------------------ MFIG02
def _type_panel(ax, b: Bundle, comparison: str, metric: str, unit: str, linthresh: float, color: str):
    dtb = b.derived_type[(b.derived_type["comparison"] == comparison) & (b.derived_type["metric_name"] == metric)]
    dtb = dtb[dtb["degradation_id"] != "C00"].copy()
    order = _family_order(b)
    dtb["fam_rank"] = dtb["case_family"].map({f: i for i, f in enumerate(order)})
    dtb = dtb.sort_values(["fam_rank", "degradation_id"]).reset_index(drop=True)
    x = np.arange(len(dtb))
    ax.axhline(0, color="black", lw=0.5)
    ax.vlines(x, dtb["min_delta"], dtb["max_delta"], color=style.COLORS["light"], lw=1.0)
    ax.plot(x, dtb["mean_delta"], "o", color=color, ms=2.4, label="Mean of 9 seeds")
    ax.plot(x, dtb["median_delta"], "_", color="black", ms=4, mew=0.8, label="Median")
    ax.set_yscale("symlog", linthresh=linthresh, linscale=0.6)
    ax.set_xlim(-0.8, len(dtb) - 0.2)
    ax.set_xticks(x); ax.set_xticklabels(dtb["degradation_id"], rotation=90, fontsize=style.MIN_TEXT_PT)
    ax.set_ylabel(f"Δ {b.names['metrics'][metric]['label']}, Core − Backbone ({unit})")
    # family bands
    top = ax.get_ylim()[1]
    start = 0
    for i, fam in enumerate(order):
        n = int((dtb["case_family"] == fam).sum())
        if n == 0:
            continue
        if i % 2 == 1:
            ax.axvspan(start - 0.5, start + n - 0.5, color="#F2F2F2", zorder=0)
        ax.text(start + n / 2 - 0.5, 1.02 + 0.09 * (i % 2), FAMILY_SHORT[fam], transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=style.MIN_TEXT_PT)
        start += n
    ax.legend(loc="lower left", ncol=2, columnspacing=0.8, handletextpad=0.3)
    return dtb


def mfig02_core_vs_backbone_consistency(b: Bundle):
    fig, gs = style.new_gridspec_figure(7.0, 3, 2, hspace=0.75, wspace=0.3, height_ratios=[1.15, 1.15, 1])
    a1 = fig.add_subplot(gs[0, :]); a2 = fig.add_subplot(gs[2, 0])
    a3 = fig.add_subplot(gs[1, :]); a4 = fig.add_subplot(gs[2, 1])
    _type_panel(a1, b, "A04_vs_F03", "horizontal_rmse_m", "m", 0.01, style.COLORS["A04"])
    _type_panel(a3, b, "A04_vs_F03", "yaw_rmse_deg", "°", 0.1, style.COLORS["A04"])
    a3.set_xlabel("Degradation type")
    # (b) majority-seed counts per metric
    s = b.derived_summary[b.derived_summary["comparison"] == "A04_vs_F03"].set_index("metric_name")
    metrics = ["horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m", "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"]
    counts = [int(s.loc[m, "majority_seed_improved_types"]) for m in metrics]
    x = np.arange(len(metrics))
    a2.bar(x, counts, color=style.COLORS["A04"], width=0.6)
    a2.axhline(60, color="black", lw=0.6, ls=(0, (3, 2)))
    for xi, c in zip(x, counts):
        a2.text(xi, c + 1, str(c), ha="center", va="bottom", fontsize=style.MIN_TEXT_PT)
    a2.set_ylim(0, 68)
    a2.set_xticks(x); a2.set_xticklabels([b.names["metrics"][m]["label"].replace(" RMSE", "") for m in metrics], rotation=25, ha="right")
    a2.set_ylabel("Types improved in ≥5 of 9 seeds (count)")
    # (d) win rate by family, horizontal and yaw
    fam = b.derived_family[b.derived_family["comparison"] == "A04_vs_F03"]
    order = [f for f in _family_order(b)]
    xs = np.arange(len(order))
    w = 0.38
    for k, (metric, col, lab) in enumerate([("horizontal_rmse_m", style.COLORS["A04"], "Horizontal RMSE"), ("yaw_rmse_deg", style.COLORS["F03"], "Yaw RMSE")]):
        vals = [float(fam[(fam["metric_name"] == metric) & (fam["case_family"] == f)]["win_rate"].iloc[0]) for f in order]
        a4.bar(xs + (k - 0.5) * w, vals, width=w, color=col, label=lab, hatch=style.HATCH_SECONDARY if k else None, edgecolor="black", lw=0.3)
    a4.axhline(0.5, color="black", lw=0.5, ls=(0, (3, 2)))
    a4.set_ylim(0, 1.05)
    a4.set_xticks(xs); a4.set_xticklabels([FAMILY_SHORT[f] for f in order], rotation=30, ha="right")
    a4.set_ylabel("Win rate vs Backbone (fraction)")
    a4.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, columnspacing=1.0)
    for ax, letter, xo in ((a1, "a", -0.06), (a3, "b", -0.06), (a2, "c", -0.24), (a4, "d", -0.24)):
        style.panel_label(ax, letter, x=xo)
    h = s.loc["horizontal_rmse_m"]; y = s.loc["yaw_rmse_deg"]
    caption = (
        "Core versus Backbone across the 541 cases (delta = Core − Backbone, negative is better). Per-type panels show the mean "
        "of nine seeds with the seed range; type identifiers are defined in Table S1. Horizontal RMSE: mean delta "
        f"{h['mean_delta']:+.4f} m (95% CI {h['ci95_low']:+.4f} to {h['ci95_high']:+.4f}), win rate {100*h['win_rate']:.1f}%, "
        f"{int(h['majority_seed_improved_types'])}/60 types improved in a majority of seeds. Yaw RMSE: median delta {y['median_delta']:+.3f}°, "
        f"win rate {100*y['win_rate']:.1f}%; the yaw mean delta CI ({y['ci95_low']:+.3f} to {y['ci95_high']:+.3f}°) includes zero."
    )
    return fig, caption


# ------------------------------------------------------------------ MFIG03
def mfig03_full_tradeoff_tails(b: Bundle):
    fig, axes = style.new_figure(2, 2, 5.6, hspace=0.75, wspace=0.34)
    (a1, a2), (a3, a4) = axes
    fam = b.derived_family[b.derived_family["comparison"] == "F04_vs_A04"]
    order = _family_order(b)
    xs = np.arange(len(order))
    w = 0.38
    for ax, pairs, unit in ((a1, [("horizontal_rmse_m", style.COLORS["F04"], "Horizontal"), ("up_rmse_m", style.COLORS["light"], "Up")], "m"),
                            (a2, [("yaw_rmse_deg", style.COLORS["F04"], "Yaw"), ("roll_rmse_deg", style.COLORS["light"], "Roll")], "°")):
        for k, (metric, col, lab) in enumerate(pairs):
            vals = [float(fam[(fam["metric_name"] == metric) & (fam["case_family"] == f)]["mean_delta"].iloc[0]) for f in order]
            ax.bar(xs + (k - 0.5) * w, vals, width=w, color=col, edgecolor="black", lw=0.3, label=lab, hatch=style.HATCH_SECONDARY if k else None)
        ax.axhline(0, color="black", lw=0.5)
        ax.set_xticks(xs); ax.set_xticklabels([FAMILY_SHORT[f] for f in order], rotation=30, ha="right")
        ax.set_ylabel(f"Δ RMSE, Full − Core ({unit})")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, columnspacing=1.0)
    a2.set_yscale("symlog", linthresh=0.5, linscale=0.7)
    a2.set_yticks([0.1, 0, -0.1, -1, -10]); a2.set_yticklabels(["0.1", "0", "−0.1", "−1", "−10"])
    # (c) ratio-of-means, ratio-of-medians and win rate per metric (derived summary + frozen method summary)
    ds = b.derived_summary[b.derived_summary["comparison"] == "F04_vs_A04"].set_index("metric_name")
    metrics = ["horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m", "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"]
    core_cfg = b.config_of("A04")
    core_means = [b.method_stat(core_cfg, m, "mean") for m in metrics]
    mean_pct = [100 * ds.loc[m, "mean_delta"] / cm for m, cm in zip(metrics, core_means)]
    ci_lo = [mp - 100 * ds.loc[m, "ci95_low"] / cm for m, cm, mp in zip(metrics, core_means, mean_pct)]
    ci_hi = [100 * ds.loc[m, "ci95_high"] / cm - mp for m, cm, mp in zip(metrics, core_means, mean_pct)]
    med_pct = [100 * ds.loc[m, "median_delta"] / b.method_stat(core_cfg, m, "median") for m in metrics]
    win_pct = [100 * ds.loc[m, "win_rate"] for m in metrics]
    x = np.arange(len(metrics))
    a3.bar(x - 0.2, mean_pct, width=0.4, color=style.COLORS["F04"], yerr=[ci_lo, ci_hi], capsize=2, error_kw={"lw": 0.6}, label="Δ mean / Core mean (95% CI)")
    a3.bar(x + 0.2, med_pct, width=0.4, color=style.COLORS["light"], edgecolor="black", lw=0.3, hatch=style.HATCH_SECONDARY, label="Δ median / Core median")
    a3.plot(x, win_pct, "o", color="black", ms=3.4, mfc="white", label="Case win rate")
    a3.axhline(0, color="black", lw=0.5); a3.axhline(50, color="black", lw=0.5, ls=(0, (3, 2)))
    a3.set_xticks(x); a3.set_xticklabels([b.names["metrics"][m]["label"].replace(" RMSE", "") for m in metrics], rotation=25, ha="right")
    a3.set_ylabel("Change and win rate, Full vs Core (%)")
    a3.set_ylim(-45, 105)
    a3.legend(loc="lower left", bbox_to_anchor=(0.02, 1.0), ncol=2, columnspacing=0.8, fontsize=style.MIN_TEXT_PT)
    # (d) paired scatter
    core = b.metric_values("horizontal_rmse_m", b.config_of("A04"))
    full = b.metric_values("horizontal_rmse_m", b.config_of("F04"))
    meta = b.unique.drop_duplicates("case_id").set_index("case_id")["case_family"]
    df = pd.DataFrame({"core": core, "full": full}).join(meta)
    outage = df["case_family"] == "gnss_outage"
    a4.plot([0.05, 40], [0.05, 40], color="black", lw=0.5)
    a4.plot(df.loc[~outage, "core"], df.loc[~outage, "full"], "o", ms=2.2, color=style.COLORS["neutral"], alpha=0.55, label="Other families")
    a4.plot(df.loc[outage, "core"], df.loc[outage, "full"], "^", ms=3.0, color=style.COLORS["F04"], label="GNSS outage family")
    a4.set_xscale("log"); a4.set_yscale("log")
    a4.set_xlabel("Core horizontal RMSE (m)"); a4.set_ylabel("Full horizontal RMSE (m)")
    a4.legend(loc="upper left")
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter, x=-0.14)
    s = b.derived_summary[b.derived_summary["comparison"] == "F04_vs_A04"].set_index("metric_name")
    yaw = s.loc["yaw_rmse_deg"]; up = s.loc["up_rmse_m"]
    caption = (
        "Source-Aware trade-off: Full minus Core across families and metrics (negative is better). Yaw RMSE mean delta "
        f"{yaw['mean_delta']:+.2f}° (95% CI {yaw['ci95_low']:+.2f} to {yaw['ci95_high']:+.2f}°) with a case win rate of only "
        f"{100*yaw['win_rate']:.1f}%, i.e. tail protection rather than a universal gain; Up RMSE delta {up['mean_delta']:+.3f} m with win rate "
        f"{100*up['win_rate']:.1f}%. The paired scatter marks the GNSS-outage family, where Full loses on position."
    )
    return fig, caption


# ------------------------------------------------------------------ MFIG04
def mfig04_module_ablation(b: Bundle):
    fig, axes = style.new_figure(2, 2, 5.2, hspace=0.62, wspace=0.34)
    (a1, a2), (a3, a4) = axes
    chain = b.names["ablation_chain"]
    cfgs = [c["configuration"] for c in chain]
    labels = [c["label"] for c in chain]
    x = np.arange(len(chain))
    cols = [style.COLORS["F02"], style.COLORS["F03"], "#9ECAE1", style.COLORS["A04"], style.COLORS["F04"]]
    hm = [b.method_stat(c, "horizontal_rmse_m", "mean") for c in cfgs]
    hmed = [b.method_stat(c, "horizontal_rmse_m", "median") for c in cfgs]
    a1.bar(x, hm, color=cols, width=0.62, label="Mean")
    a1.plot(x, hmed, "D", color="black", ms=3.2, label="Median")
    a1.set_xticks(x); a1.set_xticklabels(labels, rotation=25, ha="right")
    a1.set_ylabel("Horizontal RMSE (m)"); a1.set_ylim(0, 1.5); a1.legend(loc="upper right")
    ym = [b.method_stat(c, "yaw_rmse_deg", "mean") for c in cfgs]
    ymed = [b.method_stat(c, "yaw_rmse_deg", "median") for c in cfgs]
    yp = [b.method_stat(c, "yaw_rmse_deg", "p95") for c in cfgs]
    a2.bar(x, ym, color=cols, width=0.62, label="Mean")
    a2.plot(x, ymed, "D", color="black", ms=3.2, label="Median")
    a2.plot(x, yp, "v", color="black", ms=3.6, mfc="white", label="P95")
    a2.set_yscale("log"); a2.set_ylim(1, 400)
    a2.set_xticks(x); a2.set_xticklabels(labels, rotation=25, ha="right")
    a2.set_ylabel("Yaw RMSE (°)"); a2.legend(loc="upper right", ncol=3, columnspacing=0.8)
    # (c)(d) leave-one-out from the frozen aggregate
    loo = b.names["leave_one_out"]
    fr = b.pairwise_frozen[b.pairwise_frozen["scope"] == "overall"]
    xs = np.arange(len(loo))
    for ax, metric, unit in ((a3, "horizontal_rmse_m", "m"), (a4, "yaw_rmse_deg", "°")):
        vals, wins = [], []
        for comp in loo:
            row = fr[(fr["comparison"] == comp) & (fr["metric_name"] == metric)].iloc[0]
            vals.append(float(row["mean_delta_candidate_minus_reference"])); wins.append(float(row["win_rate"]))
        ax.bar(xs, vals, color=style.COLORS["F04"], width=0.6)
        ax.axhline(0, color="black", lw=0.5)
        ymax = max(abs(v) for v in vals)
        for xi, v, wr in zip(xs, vals, wins):
            ax.text(xi, v + (0.06 * ymax if v >= 0 else -0.06 * ymax), f"win {100*wr:.0f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=style.MIN_TEXT_PT)
        ax.set_ylim(-1.35 * ymax, 1.35 * ymax)
        ax.set_xticks(xs); ax.set_xticklabels(list(loo.values()), rotation=25, ha="right")
        ax.set_ylabel(f"Δ {b.names['metrics'][metric]['label']}, Full − Full w/o module ({unit})")
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter, x=-0.14)
    caption = (
        "Module ablation on the 541-case matrix. (a)(b) Configuration chain Dual-basic → Backbone → +RD → +RD+RP+HV (Core) → +SA (Full); "
        f"horizontal RMSE mean {hm[0]:.3f} → {hm[1]:.3f} → {hm[2]:.3f} → {hm[3]:.3f} → {hm[4]:.3f} m. (c)(d) Leave-one-out deltas from the frozen "
        "aggregate (Full minus Full without the module; negative means the module helps) with case win rates."
    )
    return fig, caption


# ------------------------------------------------------------------ MFIG05
def mfig05_representative_cases(b: Bundle):
    cases = b.names["representative_cases"]
    fig, axes = style.new_figure(len(cases), 2, 7.2, hspace=0.62, wspace=0.28)
    methods = ["F03", "A04", "F04"]
    letters = iter("abcdefghijklmnop")
    missing = []
    for r, case in enumerate(cases):
        cid = case["case_id"]
        win = b.window_for(cid)
        for k, (col, unit) in enumerate((("horizontal_err_m", "m"), ("yaw_err_deg", "°"))):
            ax = axes[r][k]
            if win:
                ax.axvspan(win["t0"], win["t1"], color=style.COLORS["window"], zorder=0)
                if "t_rec" in win:
                    ax.axvspan(win["t1"], win["t_rec"], color=style.COLORS["recovery"], zorder=0)
            for m in methods:
                s = b.series_for(cid, b.config_of(m))
                if s is None:
                    missing.append(f"{cid}:{m}")
                    continue
                ax.plot(s["time"], s[col], label=b.label_of(m), **_method_style(m))
            ax.text(0.0, 1.03, f"{case['label']} [{cid[:3]}, {case['verdict']}]", transform=ax.transAxes, ha="left", va="bottom", fontsize=style.MIN_TEXT_PT)
            ax.set_ylabel("Horizontal error (m)" if k == 0 else "Yaw error (°)")
            ax.set_xlim(60, 345)
            if r == len(cases) - 1:
                ax.set_xlabel("Time (s)")
            style.panel_label(ax, next(letters), x=-0.2)
    from matplotlib.patches import Patch

    handles, labels = axes[0][0].get_legend_handles_labels()
    handles += [Patch(color=style.COLORS["window"]), Patch(color=style.COLORS["recovery"])]
    labels += ["Injection window", "Recovery interval"]
    fig.legend(handles, labels, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 1.0), frameon=False)
    fig.subplots_adjust(top=0.95)
    caption = (
        "Representative cases (seed 00) with favourable (D27, D60) and unfavourable (D04, D12, D58) outcomes for Source-Aware shown together; "
        "type identifiers are defined in Table S1. "
        "Grey bands are the injection window and, where defined, the recovery interval from the case manifest; curves are Backbone, Core and Full "
        "errors relative to the same-source reference."
    )
    if missing:
        caption += f" [missing series: {', '.join(missing)}]"
    return fig, caption


# ------------------------------------------------------------------ MFIG06
def _module_mean(b: Bundle, method_id: str, family: str, metric: str) -> float:
    ma = b.module_action
    row = ma[(ma["method_id"] == method_id) & (ma["case_family"] == family) & (ma["metric_name"] == metric)]
    return float(row["mean"].iloc[0]) if len(row) else float("nan")


def mfig06_mechanism(b: Bundle):
    fig, axes = style.new_figure(2, 2, 5.6, hspace=0.75, wspace=0.38)
    (a1, a2), (a3, a4) = axes
    order = ["clean"] + _family_order(b)
    xs = np.arange(len(order))
    short = [FAMILY_SHORT[f] for f in order]
    # (a) Source-Aware changed-weight fraction (Full)
    frac = [_module_mean(b, "F04", f, "source_aware_changed_weight_count") / _module_mean(b, "F04", f, "source_aware_evaluation_count") for f in order]
    a1.bar(xs, frac, color=style.COLORS["F04"], width=0.62)
    a1.set_ylim(0, 1.05); a1.set_xticks(xs); a1.set_xticklabels(short, rotation=30, ha="right")
    a1.set_ylabel("SA changed-weight share (fraction)")
    # (b) Scheme-C mix (Core)
    parts = [("scheme_c_normal_count", "Normal", style.COLORS["A04"]), ("scheme_c_downweight_count", "Down-weight", "#9ECAE1"), ("scheme_c_reject_count", "Reject", style.COLORS["F04"])]
    counts = np.array([[_module_mean(b, "A04", f, m) for f in order] for m, _, _ in parts])
    share = counts / np.maximum(counts.sum(axis=0), 1e-9)
    bottom = np.zeros(len(order))
    for (m, lab, col), row in zip(parts, share):
        a2.bar(xs, row, bottom=bottom, color=col, width=0.62, label=lab, edgecolor="black", lw=0.3)
        bottom += row
    a2.set_ylim(0, 1.05); a2.set_xticks(xs); a2.set_xticklabels(short, rotation=30, ha="right")
    a2.set_ylabel("Scheme-C action share (fraction)"); a2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=style.MIN_TEXT_PT)
    # (c) raw Doppler updates and rejects (Core)
    upd = [_module_mean(b, "A04", f, "raw_doppler_update_count") for f in order]
    rej = [_module_mean(b, "A04", f, "raw_doppler_reject_count") for f in order]
    a3.bar(xs - 0.19, upd, width=0.38, color=style.COLORS["A04"], label="Updates")
    a3.bar(xs + 0.19, rej, width=0.38, color=style.COLORS["light"], edgecolor="black", lw=0.3, hatch=style.HATCH_SECONDARY, label="Rejects")
    a3.set_xticks(xs); a3.set_xticklabels(short, rotation=30, ha="right")
    a3.set_ylabel("Raw-Doppler epochs per case (count)"); a3.set_ylim(0, 300); a3.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    # (d) yaw tail counts
    t = b.tail[b.tail["metric_name"] == "yaw_rmse_deg"]
    methods = ["F02", "F03", "A04", "F04"]
    xm = np.arange(len(methods))
    for k, thr in enumerate((10.0, 30.0)):
        vals = [int(t[(t["method_id"] == m) & (t["threshold"] == thr)]["case_count"].iloc[0]) for m in methods]
        a4.bar(xm + (k - 0.5) * 0.38, vals, width=0.38, color=[style.COLORS[m] for m in methods], hatch=None if k else style.HATCH_SECONDARY, edgecolor="black", lw=0.3, label=f"Yaw RMSE > {thr:.0f}°")
        for xi, v in zip(xm + (k - 0.5) * 0.38, vals):
            a4.text(xi, v + 0.6, str(v), ha="center", va="bottom", fontsize=style.MIN_TEXT_PT)
    a4.set_xticks(xm); a4.set_xticklabels(_labels(b, methods), rotation=20, ha="right")
    a4.set_ylabel("Cases beyond threshold (count)"); a4.set_ylim(0, 52); a4.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=style.MIN_TEXT_PT)
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter, x=-0.2)
    caption = (
        f"Mechanism counts from the frozen module-action summary. Source-Aware changes a weight on {100*frac[0]:.1f}% of its evaluations "
        "already in the clean case (always-on); Scheme-C action shares and raw-Doppler updates are per-family means for Core; "
        "(d) counts of cases whose yaw RMSE exceeds 10° and 30°, concentrated in gross-position-fault types."
    )
    return fig, caption


# ------------------------------------------------------------------ SFIG01
def sfig01_type_method_heatmaps(b: Bundle):
    metrics = ["horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m", "roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg"]
    fig, axes = style.new_figure(2, 3, 8.4, hspace=0.22, wspace=0.75)
    ts = b.type_summary[b.type_summary["degradation_id"] != "CLEAN"]
    for k, (ax, metric, letter) in enumerate(zip(axes.ravel(), metrics, "abcdef")):
        piv = ts[ts["metric_name"] == metric].pivot(index="degradation_id", columns="method_id", values="mean")
        piv = piv.reindex(columns=MAIN_METHODS).sort_index()
        vals = piv.to_numpy(dtype=float)
        im = ax.imshow(vals, aspect="auto", cmap="viridis", norm=LogNorm(vmin=np.nanmin(vals), vmax=np.nanmax(vals)))
        ax.set_xticks(range(len(MAIN_METHODS))); ax.set_xticklabels(_labels(b, MAIN_METHODS), rotation=40, ha="right")
        ticks = [i for i, d in enumerate(piv.index) if int(d[1:]) % 5 == 0 or i == 0]
        ax.set_yticks(ticks); ax.set_yticklabels([piv.index[i] for i in ticks], fontsize=style.MIN_TEXT_PT)
        if k % 3 == 0:
            ax.set_ylabel("Degradation type")
        ax.text(0.0, 1.01, b.names["metrics"][metric]["label"] + ", mean of 9 seeds", transform=ax.transAxes, ha="left", va="bottom", fontsize=style.MIN_TEXT_PT)
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cb.set_label(f"RMSE ({b.names['metrics'][metric]['unit']})")
        style.panel_label(ax, letter, x=-0.42 if k % 3 == 0 else -0.3, y=1.01)
    caption = "Mean RMSE over nine seeds for every degradation type and method (log colour scale); supplementary replacement for the exploratory atlases."
    return fig, caption


FIGURES = {
    "MFIG00_reference_comparison": mfig00_reference_comparison,
    "MFIG01_matrix_overview": mfig01_matrix_overview,
    "MFIG02_core_vs_backbone_consistency": mfig02_core_vs_backbone_consistency,
    "MFIG03_full_tradeoff_tails": mfig03_full_tradeoff_tails,
    "MFIG04_module_ablation": mfig04_module_ablation,
    "MFIG05_representative_cases": mfig05_representative_cases,
    "MFIG06_mechanism": mfig06_mechanism,
    "SFIG01_type_method_heatmaps": sfig01_type_method_heatmaps,
}
