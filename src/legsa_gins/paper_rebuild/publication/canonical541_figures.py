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
    tick_idx = [i for i, d in enumerate(dtb["degradation_id"]) if int(d[1:]) % 5 == 0 or i == 0]
    ax.set_xticks([x[i] for i in tick_idx]); ax.set_xticklabels([dtb["degradation_id"].iloc[i] for i in tick_idx], rotation=90, fontsize=6)
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
        ax.text(start + n / 2 - 0.5, 1.02 + 0.09 * (i % 2), FAMILY_SHORT[fam], transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=5.8)
        start += n
    ax.legend(loc="lower left", ncol=2, columnspacing=0.8, handletextpad=0.3)
    return dtb


def mfig02_core_vs_backbone_consistency(b: Bundle):
    fig, axes = style.new_figure(2, 2, 5.8, hspace=0.7, wspace=0.32, width_ratios=[1.35, 1])
    (a1, a2), (a3, a4) = axes
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
        a2.text(xi, c + 1, str(c), ha="center", va="bottom", fontsize=6.5)
    a2.set_ylim(0, 68)
    a2.set_xticks(x); a2.set_xticklabels([b.names["metrics"][m]["label"].replace(" RMSE", "") for m in metrics], rotation=25, ha="right")
    a2.set_ylabel("Types with ≥5 of 9 seeds improved (count)")
    # (d) win rate by family, horizontal and yaw
    fam = b.derived_family[b.derived_family["comparison"] == "A04_vs_F03"]
    order = [f for f in _family_order(b)]
    xs = np.arange(len(order))
    w = 0.38
    for k, (metric, col, lab) in enumerate([("horizontal_rmse_m", style.COLORS["A04"], "Horizontal RMSE"), ("yaw_rmse_deg", style.COLORS["F03"], "Yaw RMSE")]):
        vals = [float(fam[(fam["metric_name"] == metric) & (fam["case_family"] == f)]["win_rate"].iloc[0]) for f in order]
        a4.bar(xs + (k - 0.5) * w, vals, width=w, color=col, label=lab)
    a4.axhline(0.5, color="black", lw=0.5, ls=(0, (3, 2)))
    a4.set_ylim(0, 1.05)
    a4.set_xticks(xs); a4.set_xticklabels([FAMILY_SHORT[f] for f in order], rotation=30, ha="right")
    a4.set_ylabel("Case win rate, Core vs Backbone (fraction)")
    a4.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, columnspacing=1.0)
    for ax, letter in zip((a1, a2, a3, a4), "abcd"):
        style.panel_label(ax, letter, x=-0.12)
    h = s.loc["horizontal_rmse_m"]; y = s.loc["yaw_rmse_deg"]
    caption = (
        "Core versus Backbone across the 541 cases (delta = Core − Backbone, negative is better). Per-type panels show the mean "
        "of nine seeds with the seed range. Horizontal RMSE: mean delta "
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
            ax.bar(xs + (k - 0.5) * w, vals, width=w, color=col, edgecolor="black", lw=0.3, label=lab)
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
    mean_pct = [100 * ds.loc[m, "mean_delta"] / b.method_stat(core_cfg, m, "mean") for m in metrics]
    med_pct = [100 * ds.loc[m, "median_delta"] / b.method_stat(core_cfg, m, "median") for m in metrics]
    win_pct = [100 * ds.loc[m, "win_rate"] for m in metrics]
    x = np.arange(len(metrics))
    a3.bar(x - 0.2, mean_pct, width=0.4, color=style.COLORS["F04"], label="Δ mean / Core mean")
    a3.bar(x + 0.2, med_pct, width=0.4, color=style.COLORS["light"], edgecolor="black", lw=0.3, label="Δ median / Core median")
    a3.plot(x, win_pct, "o", color="black", ms=3.4, mfc="white", label="Case win rate")
    a3.axhline(0, color="black", lw=0.5); a3.axhline(50, color="black", lw=0.5, ls=(0, (3, 2)))
    a3.set_xticks(x); a3.set_xticklabels([b.names["metrics"][m]["label"].replace(" RMSE", "") for m in metrics], rotation=25, ha="right")
    a3.set_ylabel("Change and win rate, Full vs Core (%)")
    a3.set_ylim(-30, 105)
    a3.legend(loc="lower left", bbox_to_anchor=(0.1, 1.0), ncol=3, columnspacing=0.8, fontsize=6)
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
    cols = [style.COLORS["F02"], style.COLORS["F03"], "#8CB6D9", style.COLORS["A04"], style.COLORS["F04"]]
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
            ax.text(xi, v + (0.06 * ymax if v >= 0 else -0.06 * ymax), f"win {100*wr:.0f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=5.8)
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
    fig, axes = style.new_figure(len(cases), 2, 8.0, hspace=0.6, wspace=0.28)
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
            ax.text(0.0, 1.03, f"{case['label']} ({case['verdict']})", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.4)
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
        "Representative cases (seed 00) with favourable (D27, D60) and unfavourable (D04, D12, D58) outcomes for Source-Aware shown together. "
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
    a2.set_ylabel("Scheme-C action share (fraction)"); a2.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=6)
    # (c) raw Doppler updates and rejects (Core)
    upd = [_module_mean(b, "A04", f, "raw_doppler_update_count") for f in order]
    rej = [_module_mean(b, "A04", f, "raw_doppler_reject_count") for f in order]
    a3.bar(xs - 0.19, upd, width=0.38, color=style.COLORS["A04"], label="Updates")
    a3.bar(xs + 0.19, rej, width=0.38, color=style.COLORS["light"], edgecolor="black", lw=0.3, label="Rejects")
    a3.set_xticks(xs); a3.set_xticklabels(short, rotation=30, ha="right")
    a3.set_ylabel("Raw-Doppler epochs per case (count)"); a3.set_ylim(0, 300); a3.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    # (d) yaw tail counts
    t = b.tail[b.tail["metric_name"] == "yaw_rmse_deg"]
    methods = ["F02", "F03", "A04", "F04"]
    xm = np.arange(len(methods))
    for k, thr in enumerate((10.0, 30.0)):
        vals = [int(t[(t["method_id"] == m) & (t["threshold"] == thr)]["case_count"].iloc[0]) for m in methods]
        a4.bar(xm + (k - 0.5) * 0.38, vals, width=0.38, color=[style.COLORS[m] for m in methods], alpha=1.0 if k else 0.45, label=f"Yaw RMSE > {thr:.0f}°")
        for xi, v in zip(xm + (k - 0.5) * 0.38, vals):
            a4.text(xi, v + 0.6, str(v), ha="center", va="bottom", fontsize=6)
    a4.set_xticks(xm); a4.set_xticklabels(_labels(b, methods), rotation=20, ha="right")
    a4.set_ylabel("Cases beyond threshold (count)"); a4.set_ylim(0, 52); a4.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=6)
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
        ax.set_yticks(range(len(piv.index))); ax.set_yticklabels(piv.index, fontsize=4.2)
        if k % 3 == 0:
            ax.set_ylabel("Degradation type")
        ax.text(0.0, 1.01, b.names["metrics"][metric]["label"] + ", mean of 9 seeds", transform=ax.transAxes, ha="left", va="bottom", fontsize=7)
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cb.set_label(f"RMSE ({b.names['metrics'][metric]['unit']})")
        style.panel_label(ax, letter, x=-0.42 if k % 3 == 0 else -0.3, y=1.01)
    caption = "Mean RMSE over nine seeds for every degradation type and method (log colour scale); supplementary replacement for the exploratory atlases."
    return fig, caption


FIGURES = {
    "MFIG01_matrix_overview": mfig01_matrix_overview,
    "MFIG02_core_vs_backbone_consistency": mfig02_core_vs_backbone_consistency,
    "MFIG03_full_tradeoff_tails": mfig03_full_tradeoff_tails,
    "MFIG04_module_ablation": mfig04_module_ablation,
    "MFIG05_representative_cases": mfig05_representative_cases,
    "MFIG06_mechanism": mfig06_mechanism,
    "SFIG01_type_method_heatmaps": sfig01_type_method_heatmaps,
}
