#!/usr/bin/env python3
"""UA-02: derive the manuscript uncertainty tables from the sealed UA-01 outputs and
check every numeric claim used in the uncertainty documents.

Read-only with respect to every input; writes only UNC_*.csv files into --out.
No solver, evaluator, provider or reference-trajectory access.

Usage:
  python3 scripts/paper_rebuild/unc02_derive_and_check.py \
      --repo-root /home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair \
      --out docs/paper_rebuild/v3/uncertainty
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

UA01_PINS = {
    "UA01_C00_SERIES_STATS.csv": "79382d85fd641d1a708e3a8ac44346000cb9a599acdbee83ebcbc650b4ddee04",
    "UA01_C00_PAIRED_SERIES.csv": "071c4ca886d30d33acebcf274f0ab2162dd6087049bf4f167dc4115818af96b4",
    "UA01_BY2O_SEGMENT_BANDS.csv": "a3f3471438d80109656b63aac7f3b49c8da2551a8b8bd1649d2522723e16e231",
    "UA01_TYPE_SEED_DISPERSION.csv": "1c0584fc9b21a6df41106dac81903794a64b204234786136af39c29c11ceebca",
    "UA01_FAMILY_DISPERSION_SUMMARY.csv": "bd1567e262c1fba57413353986053676799e473568560520e185d68ae5b1b208",
    "UA01_PAIRED_OVERALL.csv": "7ef92f4e9b2d7a05b61a9c6e2d964cb96e668c142145ae5164aa2733845b854f",
    "UA01_EXTERNAL_PAIRED.csv": "5f0bcf02139b0842ae8eff1656ae7acc51222185ca9f630bdc5ed364765a4276",
    "UA01_DISTRIBUTION_QUANTILES.csv": "463f302d8e95f78d2986cb223e1f430d65468e916eeb3589713fecb41829e92b",
    "UA01_ADDENDUM_STATS.csv": "0d7385ef6ba7b7305480a5f3cc6c409f11fb78f1d5009acaf2b08bbbbaa1da13",
    "UA01_ADDENDUM_PAIRED.csv": "86057129bd35a2e6a785b8802d0d425bb9b8e1c704c3c565952fbcc9347544aa",
    "UA01_MOTION_STATS.csv": "815496e6a51918cd3bf0a95920c3c2e358683f7dcd5324f8bb633ced357b291c",
    "UA01_IDENTITY_CHECKS.csv": "69c361fc8bdd24855ded30038b154895f94ff47b2650a0a25552481e6e88b6bd",
}

REF_SPEC_DEG = 0.4 / 0.35          # manufacturer 0.4 deg @ 1 m, 0.35 m nominal separation
REF_FUSED_DEG = {"BY2": 0.886, "BY2H": 0.910, "BY2O": 0.970}   # self-reported sqrt-cov medians, CLEAN5_PARITY_PLAN.md:187-189
MAIN_METHODS = ["F01", "F02", "F03", "A04", "F04", "LC01", "LC01-S"]
YAW_PARITY_DEG = 0.1
H_PARITY_M = 0.005


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def derive_yaw_decomposition(series: pd.DataFrame) -> pd.DataFrame:
    y = series[series.series == "yaw_err_deg"].copy()
    rows = []
    for _, r in y.iterrows():
        b2, s2, f2 = r["mean"] ** 2, r["std_slow"] ** 2, r["std_fast"] ** 2
        tot = r["rmse_recomputed"] ** 2
        own = math.sqrt(b2 + s2)
        ref_f = REF_FUSED_DEG[r["sequence"]]

        def sub(x, rf):
            v = x * x - rf * rf
            return math.sqrt(v) if v > 0 else float("nan")

        rows.append({
            "sequence": r["sequence"], "method": r["method"], "n": int(r["n"]),
            "rmse_deg": r["rmse_recomputed"], "bias_deg": r["mean"], "std_slow_deg": r["std_slow"],
            "std_fast_deg": r["std_fast"], "bias_sq": b2, "slow_sq": s2, "fast_sq": f2,
            "closure_ratio": (b2 + s2 + f2) / tot, "share_bias": b2 / tot, "share_slow": s2 / tot,
            "share_fast": f2 / tot, "estimator_specific_deg": own,
            "estimator_specific_minus_ref_spec_deg": sub(own, REF_SPEC_DEG),
            "estimator_specific_minus_ref_fused_deg": sub(own, ref_f),
            "ref_spec_deg": REF_SPEC_DEG, "ref_fused_deg": ref_f,
        })
    return pd.DataFrame(rows)


def derive_realization(series: pd.DataFrame) -> pd.DataFrame:
    keep = series[series.series.isin(["yaw_err_deg", "horizontal_err_m", "err_u_m"])].copy()
    out = keep[["sequence", "method", "series", "n", "rmse_recomputed", "tau_int_s", "n_eff",
                "se_rmse_acf", "se_rmse_batch_20s", "se_rmse_batch_40s", "rmse_mbb_low", "rmse_mbb_high"]].copy()
    out["mbb_half_width"] = (out["rmse_mbb_high"] - out["rmse_mbb_low"]) / 2.0
    out["mbb_half_width_relative"] = out["mbb_half_width"] / out["rmse_recomputed"]
    return out


def verdict(delta: float, lo: float, hi: float, parity: float):
    """Rule fixed in UNC02_DISTINGUISHABILITY.md §1 (applied to A minus B):
    RESOLVED             interval excludes zero and |delta| >= parity threshold
    RESOLVED_NEGLIGIBLE  interval excludes zero but |delta| < parity threshold
    PARITY               interval includes zero and |delta| < parity threshold
    DIRECTION_ONLY       interval includes zero and |delta| >= parity threshold
    """
    excludes_zero = lo > 0 or hi < 0
    small = abs(delta) < parity
    if excludes_zero and not small:
        return "RESOLVED", ("lower" if delta < 0 else "higher")
    if excludes_zero and small:
        return "RESOLVED_NEGLIGIBLE", "comparable (difference below reporting resolution)"
    if small:
        return "PARITY", "comparable"
    return "DIRECTION_ONLY", ("lower, interval includes zero" if delta < 0 else "higher, interval includes zero")


def derive_distinguishability(paired: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in paired.iterrows():
        metric = "yaw" if r["series"] == "yaw_err_deg" else "horizontal"
        parity = YAW_PARITY_DEG if metric == "yaw" else H_PARITY_M
        v, w = verdict(r["delta_rmse"], r["delta_rmse_mbb_low"], r["delta_rmse_mbb_high"], parity)
        rows.append({
            "sequence": r["sequence"], "segment": r["segment"], "pair_A_minus_B": r["pair"], "metric": metric,
            "n_common": int(r["n_common"]), "match_method": r["match_method"],
            "rmse_A": r["rmse_A"], "rmse_B": r["rmse_B"], "delta_rmse": r["delta_rmse"],
            "se_delta_batch_20s": r["se_delta_rmse_batch_20s"], "se_delta_acf": r["se_delta_rmse_acf"],
            "mbb95_low": r["delta_rmse_mbb_low"], "mbb95_high": r["delta_rmse_mbb_high"],
            "corr_squared_errors": r["corr_squared_errors"], "parity_threshold": parity,
            "verdict": v, "wording_for_A_vs_B": w,
        })
    return pd.DataFrame(rows)


def derive_seed_summary(tsd: pd.DataFrame) -> pd.DataFrame:
    rows = []
    edges = {"yaw_rmse_deg": [0.01, 0.1, 1.0], "horizontal_rmse_m": [0.001, 0.02, 0.1], "up_rmse_m": [0.001, 0.02, 0.1]}
    for (m, metric), g in tsd.groupby(["method", "metric"]):
        if metric not in edges:
            continue
        g = g[g.type.str.match(r"^D\d\d$")]
        sd = g.sd.dropna()
        e = edges[metric]
        big = sorted(g[g.sd >= e[2]].type.tolist())
        rows.append({
            "method": m, "metric": metric, "n_types": int(len(g)), "n_types_finite_sd": int(len(sd)),
            "n_types_all_9_finite": int((g.n_finite == 9).sum()), "median_sd": sd.median(), "p90_sd": sd.quantile(0.9),
            f"n_sd_lt_{e[0]}": int((sd < e[0]).sum()), f"n_sd_lt_{e[1]}": int((sd < e[1]).sum()),
            f"n_sd_lt_{e[2]}": int((sd < e[2]).sum()), f"types_sd_ge_{e[2]}": ";".join(big),
        })
    return pd.DataFrame(rows)


def parse_body_frame_rows(repo_root: Path) -> pd.DataFrame:
    """Calibrated-chain v3 body-frame residuals (CLEAN5_STAGE2_CLOSEOUT.md §10, rows B3:*)."""
    doc = repo_root / "docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md"
    rows = []
    pat = re.compile(r"^\|\s*(BY2O|BY2H|BY2)\s*\|\s*V2s\s*\|\s*(F0[1-4]|A04)\s*\|\s*标定 v3\s*\|" + r"\s*([-0-9.e]+)\s*\|" * 6 + r"\s*(B3:\d+)\s*\|")
    for line in doc.read_text(encoding="utf-8").splitlines():
        m = pat.match(line.strip())
        if m:
            seq, method = m.group(1), m.group(2)
            fm, fs, rm, rs, um, us = (float(m.group(i)) for i in range(3, 9))
            mse = fm * fm + fs * fs + rm * rm + rs * rs
            rows.append({"sequence": seq, "method": method, "forward_mean_m": fm, "forward_std_m": fs,
                         "right_mean_m": rm, "right_std_m": rs, "up_mean_m": um, "up_std_m": us,
                         "h_rmse_m": math.sqrt(mse), "share_forward_bias": fm * fm / mse, "share_forward_random": fs * fs / mse,
                         "share_right_bias": rm * rm / mse, "share_right_random": rs * rs / mse,
                         "up_rmse_m": math.sqrt(um * um + us * us), "share_up_bias": um * um / (um * um + us * us),
                         "source": f"CLEAN5_STAGE2_CLOSEOUT.md §10 {m.group(9)}"})
    return pd.DataFrame(rows)


def build_claims():
    """Numeric claims made in UNC01/UNC02/UNC03/UNCERTAINTY_HANDOFF, asserted against the derived tables."""
    C = []

    def add(cid, table, sel, col, exp, tol, where):
        C.append((cid, table, sel, col, exp, tol, where))
    # --- yaw decomposition (UNC_YAW_DECOMPOSITION.csv) ---
    Y={'BY2':{'F04':(1.886,-1.086,0.816,1.305,0.33,0.19,0.48,1.36),'F02':(2.232,-1.390,1.153,1.307,None,None,None,None),
              'LC01':(2.995,-1.353,2.216,1.272,None,0.55,None,None),'LC01-S':(1.539,-0.357,0.844,1.229,None,None,None,None)},
       'BY2H':{'F04':(1.934,-0.538,1.222,1.405,0.08,0.40,0.53,1.34),'LC01':(2.209,-0.805,1.445,1.391,None,None,None,None)},
       'BY2O':{'F04':(2.434,0.339,2.076,1.078,0.02,0.73,0.20,2.10),'LC01':(2.454,0.300,2.075,1.065,None,None,None,None)}}
    for seq,d in Y.items():
        for m,(r,b,sl,fa,shb,shs,shf,own) in d.items():
            sel=f"sequence={seq};method={m}"
            add(f"yaw_{seq}_{m}_rmse","yawdec",sel,"rmse_deg",r,0.0006,"UNC01 §2,D1")
            add(f"yaw_{seq}_{m}_bias","yawdec",sel,"bias_deg",b,0.0006,"UNC01 §2")
            add(f"yaw_{seq}_{m}_slow","yawdec",sel,"std_slow_deg",sl,0.0006,"UNC01 §2")
            add(f"yaw_{seq}_{m}_fast","yawdec",sel,"std_fast_deg",fa,0.0006,"UNC01 §2")
            if shb is not None: add(f"yaw_{seq}_{m}_share_bias","yawdec",sel,"share_bias",shb,0.006,"UNC01 §2")
            if shs is not None: add(f"yaw_{seq}_{m}_share_slow","yawdec",sel,"share_slow",shs,0.006,"UNC01 §2")
            if shf is not None: add(f"yaw_{seq}_{m}_share_fast","yawdec",sel,"share_fast",shf,0.006,"UNC01 §2")
            if own is not None: add(f"yaw_{seq}_{m}_own","yawdec",sel,"estimator_specific_deg",own,0.006,"UNC01 §2")
    add("yaw_BY2_F04_own_spec","yawdec","sequence=BY2;method=F04","estimator_specific_minus_ref_spec_deg",0.73,0.006,"UNC01 §2")
    add("yaw_BY2_F04_own_fused","yawdec","sequence=BY2;method=F04","estimator_specific_minus_ref_fused_deg",1.03,0.006,"UNC01 §2")
    add("yaw_BY2H_F04_own_spec","yawdec","sequence=BY2H;method=F04","estimator_specific_minus_ref_spec_deg",0.69,0.006,"UNC01 §2")
    add("yaw_BY2H_F04_own_fused","yawdec","sequence=BY2H;method=F04","estimator_specific_minus_ref_fused_deg",0.98,0.006,"UNC01 §2")
    # fast component range
    for seq,(lo,hi,n) in {'BY2':(1.229,1.311,13),'BY2H':(1.391,1.415,12),'BY2O':(1.053,1.079,12)}.items():
        add(f"fast_{seq}_min","fast",f"sequence={seq}","fast_min",lo,0.0006,"UNC01 §2; paragraphs")
        add(f"fast_{seq}_max","fast",f"sequence={seq}","fast_max",hi,0.0006,"UNC01 §2; paragraphs")
        add(f"fast_{seq}_n","fast",f"sequence={seq}","n_estimators",n,0,"UNC01 §2")
    # BY2O segment bands
    add("seg_F04_primary_yaw","bands","method=F04;segment=primary","rmse_yaw",0.2325,0.0006,"UNC01 §2")
    add("seg_F04_primary_fast","bands","method=F04;segment=primary","std_fast",0.059,0.0006,"UNC01 §2; paragraphs")
    add("seg_F04_primary_slow","bands","method=F04;segment=primary","std_slow",0.182,0.0006,"UNC01 §2")
    add("seg_F04_primary_mean","bands","method=F04;segment=primary","mean_yaw",-0.124,0.0006,"UNC01 §2")
    add("seg_F04_primary_n","bands","method=F04;segment=primary","n",7612,0,"UNC01 §2")
    add("seg_F04_primary_h","bands","method=F04;segment=primary","rmse_h",0.0242,0.00006,"UNC01 §2")
    add("seg_F04_primary_up","bands","method=F04;segment=primary","rmse_up",0.0158,0.00006,"UNC01 §2")
    add("seg_F01_primary_fast","bands","method=F01;segment=primary","std_fast",0.058,0.0006,"UNC01 §2")
    add("seg_F04_outside_yaw","bands","method=F04;segment=outside","rmse_yaw",2.589,0.0006,"UNC02 §3")
    add("seg_LC01_primary_yaw","bands","method=LC01;segment=primary","rmse_yaw",4.008,0.0006,"UNC02 §3")
    add("seg_LC01_outside_yaw","bands","method=LC01;segment=outside","rmse_yaw",1.878,0.0006,"UNC02 §3")
    add("seg_LC01_primary_fast","bands","method=LC01;segment=primary","std_fast",0.271,0.0006,"UNC01 §2")
    # realization intervals
    R=[('BY2','F04','yaw_err_deg',0.153,0.206,1.604,2.158),('BY2H','F04','yaw_err_deg',0.164,0.141,1.602,2.037),('BY2O','F04','yaw_err_deg',0.661,0.717,1.364,3.613),
       ('BY2','LC01','yaw_err_deg',0.863,1.094,1.618,4.554),('BY2H','LC01','yaw_err_deg',0.162,0.180,1.744,2.421),('BY2O','LC01','yaw_err_deg',0.329,0.439,1.707,3.139),
       ('BY2','F04','horizontal_err_m',0.0246,0.0404,0.0452,0.1520),('BY2H','F04','horizontal_err_m',0.0068,0.0106,0.0452,0.0853),('BY2O','F04','horizontal_err_m',0.0115,0.0028,0.0376,0.0730),
       ('BY2','F04','err_u_m',0.0036,0.0058,0.0407,0.0570)]
    for seq,m,s,b20,b40,lo,hi in R:
        sel=f"sequence={seq};method={m};series={s}"
        tol=0.0006 if s=='yaw_err_deg' else 0.00006
        add(f"real_{seq}_{m}_{s}_b20","real",sel,"se_rmse_batch_20s",b20,tol,"UNC01 §4")
        add(f"real_{seq}_{m}_{s}_b40","real",sel,"se_rmse_batch_40s",b40,tol,"UNC01 §4")
        add(f"real_{seq}_{m}_{s}_lo","real",sel,"rmse_mbb_low",lo,tol,"UNC01 §4; paragraphs")
        add(f"real_{seq}_{m}_{s}_hi","real",sel,"rmse_mbb_high",hi,tol,"UNC01 §4; paragraphs")
    add("real_BY2_F04_yaw_tau","real","sequence=BY2;method=F04;series=yaw_err_deg","tau_int_s",0.64,0.006,"UNC01 §4")
    add("real_BY2O_F04_yaw_tau","real","sequence=BY2O;method=F04;series=yaw_err_deg","tau_int_s",7.98,0.006,"UNC01 §4")
    add("real_BY2O_F04_yaw_neff","real","sequence=BY2O;method=F04;series=yaw_err_deg","n_eff",38.5,0.06,"UNC01 §4")
    add("real_BY2_F04_h_tau","real","sequence=BY2;method=F04;series=horizontal_err_m","tau_int_s",12.2,0.06,"UNC01 §4")
    add("real_BY2_F04_h_neff","real","sequence=BY2;method=F04;series=horizontal_err_m","n_eff",18.6,0.06,"UNC01 §4")
    # distinguishability
    D=[('BY2','full','LC01-F04','yaw',1.110,-0.215,2.574,'DIRECTION_ONLY'),('BY2H','full','LC01-F04','yaw',0.274,-0.052,0.514,'DIRECTION_ONLY'),
       ('BY2O','full','LC01-F04','yaw',0.018,-1.344,1.401,'PARITY'),('BY2O','primary','LC01-F04','yaw',3.776,2.197,4.438,'RESOLVED'),
       ('BY2','full','LC01-S-F04','yaw',-0.348,-0.590,-0.152,'RESOLVED'),('BY2','full','F04-F02','yaw',-0.346,-0.692,-0.055,'RESOLVED'),
       ('BY2H','full','F04-F02','yaw',-0.350,-0.827,-0.020,'RESOLVED'),('BY2O','full','F04-F02','yaw',0.124,-0.034,0.219,'DIRECTION_ONLY'),
       ('BY2','full','F04-F03','yaw',-0.029,-0.066,0.001,'PARITY'),('BY2H','full','F04-F03','yaw',-0.007,-0.021,0.002,'PARITY'),('BY2O','full','F04-F03','yaw',0.002,-0.003,0.005,'PARITY'),
       ('BY2','full','F04-A04','yaw',0.0003,-0.004,0.005,'PARITY'),('BY2H','full','F04-A04','yaw',-0.0001,-0.001,0.001,'PARITY'),('BY2O','full','F04-A04','yaw',0.005,-0.0002,0.009,'PARITY'),
       ('BY2','full','F03-F02','yaw',-0.316,-0.639,-0.014,'RESOLVED'),('BY2H','full','F03-F02','yaw',-0.342,-0.817,-0.013,'RESOLVED'),
       ('BY2O','primary','F04-F02','yaw',-0.631,-0.713,-0.579,'RESOLVED'),
       ('BY2','full','F04-F02','horizontal',-0.0040,-0.0080,-0.0013,'RESOLVED'),('BY2H','full','F04-F02','horizontal',-0.0031,-0.0061,-0.0014,'RESOLVED'),
       ('BY2','full','F04-A04','horizontal',0.0010,0.0002,0.0023,'RESOLVED_NEGLIGIBLE'),
       ('BY2','full','LC01-F04','horizontal',-0.0003,-0.0039,0.0026,'PARITY'),('BY2H','full','LC01-F04','horizontal',0.0064,-0.0015,0.0107,'DIRECTION_ONLY'),('BY2O','full','LC01-F04','horizontal',-0.0002,-0.0028,0.0037,'PARITY'),
       ('BY2O','primary','LC01-F04','horizontal',0.0154,0.0132,0.0176,'RESOLVED')]
    for seq,seg,pair,metric,dl,lo,hi,v in D:
        sel=f"sequence={seq};segment={seg};pair_A_minus_B={pair};metric={metric}"
        tol=0.0006 if metric=='yaw' else 0.00006
        add(f"dist_{seq}_{seg}_{pair}_{metric}_delta","dist",sel,"delta_rmse",dl,tol,"UNC02 table")
        add(f"dist_{seq}_{seg}_{pair}_{metric}_lo","dist",sel,"mbb95_low",lo,tol,"UNC02 table")
        add(f"dist_{seq}_{seg}_{pair}_{metric}_hi","dist",sel,"mbb95_high",hi,tol,"UNC02 table")
    add("dist_BY2_LC01F04_corr","dist","sequence=BY2;segment=full;pair_A_minus_B=LC01-F04;metric=yaw","corr_squared_errors",0.185,0.0006,"UNC02 table")
    add("dist_BY2O_LC01F04_corr","dist","sequence=BY2O;segment=full;pair_A_minus_B=LC01-F04;metric=yaw","corr_squared_errors",0.005,0.0006,"UNC02 table")
    add("dist_BY2_LC01F04_ncommon","dist","sequence=BY2;segment=full;pair_A_minus_B=LC01-F04;metric=yaw","n_common",56628,0,"UNC02 table")
    add("dist_BY2O_F04F02_ncommon","dist","sequence=BY2O;segment=full;pair_A_minus_B=F04-F02;metric=yaw","n_common",76548,0,"UNC02 table")
    # seeds summary
    add("seed_F04_yaw_median","seeds","method=F04;metric=yaw_rmse_deg","median_sd",0.0023,0.00006,"UNC01 §5")
    add("seed_F04_yaw_p90","seeds","method=F04;metric=yaw_rmse_deg","p90_sd",0.268,0.0006,"UNC01 §5")
    add("seed_F04_yaw_lt01","seeds","method=F04;metric=yaw_rmse_deg","n_sd_lt_0.1",50,0,"UNC01 §5; paragraphs")
    add("seed_F04_yaw_lt001","seeds","method=F04;metric=yaw_rmse_deg","n_sd_lt_0.01",33,0,"UNC01 §5")
    add("seed_F04_h_median","seeds","method=F04;metric=horizontal_rmse_m","median_sd",0.00045,0.000006,"UNC01 §5")
    add("seed_F04_h_p90","seeds","method=F04;metric=horizontal_rmse_m","p90_sd",0.0204,0.00006,"UNC01 §5")
    add("seed_F04_h_lt01","seeds","method=F04;metric=horizontal_rmse_m","n_sd_lt_0.1",55,0,"UNC01 §5")
    # per-type
    for ty,med,sd in [('D32',1.913,0.052),('D33',2.215,0.230),('D35',1.903,0.069)]:
        add(f"tsd_F04_{ty}_yaw_med","tsd",f"method=F04;metric=yaw_rmse_deg;type={ty}","median",med,0.0006,"UNC01 §5")
        add(f"tsd_F04_{ty}_yaw_sd","tsd",f"method=F04;metric=yaw_rmse_deg;type={ty}","sd",sd,0.0006,"UNC01 §5")
    for ty,med,sd in [('D03',0.1003,0.0025),('D04',0.1142,0.0079),('D05',0.1198,0.0148),('D06',10.29,3.98)]:
        tol=0.00006 if med<1 else 0.006
        add(f"tsd_F04_{ty}_h_med","tsd",f"method=F04;metric=horizontal_rmse_m;type={ty}","median",med,tol,"UNC01 §5")
        add(f"tsd_F04_{ty}_h_sd","tsd",f"method=F04;metric=horizontal_rmse_m;type={ty}","sd",sd,tol,"UNC01 §5")
    # external paired per type
    for ty,mn,sd in [('D32',1.142,0.062),('D33',1.657,0.273),('D35',1.348,0.101)]:
        add(f"ext_LC01F04_{ty}_mean","ext",f"pair=LC01-F04;metric=yaw_rmse_deg;type={ty}","mean",mn,0.0006,"UNC01 §5; UNC02")
        add(f"ext_LC01F04_{ty}_sd","ext",f"pair=LC01-F04;metric=yaw_rmse_deg;type={ty}","sd",sd,0.0006,"UNC01 §5; UNC02")
    add("ext_LC01F04_D31_min","ext","pair=LC01-F04;metric=yaw_rmse_deg;type=D31","min",0.923,0.0006,"UNC02")
    # paired overall
    add("povr_F04F02_yaw_med","povr","pair=F04-F02;metric=yaw_rmse_deg","median",-0.346,0.0006,"UNC01 §5")
    add("povr_F04F02_yaw_frac","povr","pair=F04-F02;metric=yaw_rmse_deg","frac_negative",0.988,0.0006,"UNC01 §5")
    add("povr_F04F02_yaw_n","povr","pair=F04-F02;metric=yaw_rmse_deg","n_pairs",497,0,"UNC01 §5")
    add("povr_F04F03_yaw_med","povr","pair=F04-F03;metric=yaw_rmse_deg","median",-0.029,0.0006,"UNC01 §5")
    add("povr_F04F03_yaw_frac","povr","pair=F04-F03;metric=yaw_rmse_deg","frac_negative",0.988,0.0006,"UNC01 §5")
    add("povr_F04A04_yaw_frac","povr","pair=F04-A04;metric=yaw_rmse_deg","frac_negative",0.371,0.0006,"UNC01 §5")
    add("povr_F04F02_h_med","povr","pair=F04-F02;metric=horizontal_rmse_m","median",-0.0040,0.00006,"UNC01 §5")
    add("povr_F04F02_h_frac","povr","pair=F04-F02;metric=horizontal_rmse_m","frac_negative",0.893,0.0006,"UNC01 §5")
    add("povr_F04A04_h_frac","povr","pair=F04-A04;metric=horizontal_rmse_m","frac_negative",0.225,0.0006,"UNC01 §5")
    # quantiles
    add("quant_F04_yaw_p95","quant","method=F04;metric=yaw_rmse_deg","p95",2.447,0.0006,"UNC01 §5")
    add("quant_F04_yaw_p95_clo","quant","method=F04;metric=yaw_rmse_deg","cluster_q95_low",2.00,0.006,"UNC01 §5")
    add("quant_F04_yaw_p95_chi","quant","method=F04;metric=yaw_rmse_deg","cluster_q95_high",4.18,0.006,"UNC01 §5")
    add("quant_F04_yaw_p95_nlo","quant","method=F04;metric=yaw_rmse_deg","naive_q95_low",2.11,0.006,"UNC01 §5")
    add("quant_F04_yaw_p95_nhi","quant","method=F04;metric=yaw_rmse_deg","naive_q95_high",2.70,0.006,"UNC01 §5")
    add("quant_F04_yaw_nfin","quant","method=F04;metric=yaw_rmse_deg","n_finite",519,0,"UNC01 §5")
    add("quant_F04_yaw_nfail","quant","method=F04;metric=yaw_rmse_deg","n_failure",22,0,"UNC01 §5")
    add("quant_F04_h_p95","quant","method=F04;metric=horizontal_rmse_m","p95",3.551,0.0006,"UNC01 §5")
    add("quant_F04_h_p95_clo","quant","method=F04;metric=horizontal_rmse_m","cluster_q95_low",1.52,0.006,"UNC01 §5")
    add("quant_F04_h_p95_chi","quant","method=F04;metric=horizontal_rmse_m","cluster_q95_high",4.92,0.006,"UNC01 §5")
    # addendum
    add("addp_D62_10_F04F03_h_mean","addp","type=D62;duration_s=10;pair=F04-F03;metric=horizontal_rmse_m","mean",-1.61,0.006,"UNC01 §6")
    add("addp_D62_10_F04F03_h_sd","addp","type=D62;duration_s=10;pair=F04-F03;metric=horizontal_rmse_m","sd",0.87,0.006,"UNC01 §6")
    add("addp_D62_10_F04F03_h_p95","addp","type=D62;duration_s=10;pair=F04-F03;metric=horizontal_rmse_m","p95",-0.33,0.006,"UNC01 §6")
    add("addp_D62_20_F04F03_h_mean","addp","type=D62;duration_s=20;pair=F04-F03;metric=horizontal_rmse_m","mean",-10.5,0.06,"UNC01 §6")
    add("addp_D62_20_F04F03_h_sd","addp","type=D62;duration_s=20;pair=F04-F03;metric=horizontal_rmse_m","sd",5.7,0.06,"UNC01 §6")
    add("addp_D62_20_F04F03_h_p95","addp","type=D62;duration_s=20;pair=F04-F03;metric=horizontal_rmse_m","p95",-2.6,0.06,"UNC01 §6")
    add("adds_D62_10_F04_h_median","adds","type=D62;duration_s=10;method=F04;metric=horizontal_rmse_m","median",0.126,0.0006,"UNC01 §6")
    add("adds_D62_10_F04_h_sd","adds","type=D62;duration_s=10;method=F04;metric=horizontal_rmse_m","sd",0.015,0.0006,"UNC01 §6")
    add("adds_D62_20_F04_h_median","adds","type=D62;duration_s=20;method=F04;metric=horizontal_rmse_m","median",0.241,0.0006,"UNC01 §6")
    add("adds_D62_20_F04_h_sd","adds","type=D62;duration_s=20;method=F04;metric=horizontal_rmse_m","sd",0.043,0.0006,"UNC01 §6")
    add("adds_D62_10_F03_h_mean","adds","type=D62;duration_s=10;method=F03;metric=horizontal_rmse_m","mean",1.74,0.006,"UNC01 §6")
    add("adds_D62_20_F03_h_mean","adds","type=D62;duration_s=20;method=F03;metric=horizontal_rmse_m","mean",10.8,0.06,"UNC01 §6")
    add("adds_D62_10_F04_up_mean","adds","type=D62;duration_s=10;method=F04;metric=up_rmse_m","mean",0.328,0.0006,"UNC01 §6")
    add("adds_D62_20_F04_up_mean","adds","type=D62;duration_s=20;method=F04;metric=up_rmse_m","mean",1.025,0.0006,"UNC01 §6")
    add("adds_D61_30_F04_h_mean","adds","type=D61;duration_s=30;method=F04;metric=horizontal_rmse_m","mean",30.8,0.06,"UNC01 §6")
    # motion
    for seq,rms,fr,vm in [('BY2',18.0,0.618,1.187),('BY2H',17.5,0.620,1.196),('BY2O',15.4,0.463,0.892)]:
        add(f"motion_{seq}_yawrate_rms","motion",f"sequence={seq};kind=yaw_rate","rms",rms,0.06,"UNC01 §3")
        add(f"motion_{seq}_yawrate_frac10","motion",f"sequence={seq};kind=yaw_rate","time_fraction_abs_gt_10_deg_s",fr,0.0006,"UNC01 §3")
        add(f"motion_{seq}_speed_mean","motion",f"sequence={seq};kind=horizontal_speed","mean",vm,0.0006,"UNC01 §3")
    add("motion_BY2O_static_frac","motion","sequence=BY2O;kind=horizontal_speed","fraction_speed_lt_0p2_m_s",0.243,0.0006,"UNC01 §3")
    # body frame
    for seq,fm,sb,um,sub_ in [('BY2',0.0444,0.204,-0.0170,0.120),('BY2H',0.0303,0.193,-0.0072,0.025),('BY2O',0.0282,0.250,-0.0188,0.168)]:
        add(f"body_{seq}_F04_fwd","body",f"sequence={seq};method=F04","forward_mean_m",fm,0.00006,"UNC01 §3")
        add(f"body_{seq}_F04_fwdshare","body",f"sequence={seq};method=F04","share_forward_bias",sb,0.0006,"UNC01 §3")
        add(f"body_{seq}_F04_up","body",f"sequence={seq};method=F04","up_mean_m",um,0.00006,"UNC01 §3")
        add(f"body_{seq}_F04_upshare","body",f"sequence={seq};method=F04","share_up_bias",sub_,0.0006,"UNC01 §3")
    add("body_BY2_F04_fwdrand","body","sequence=BY2;method=F04","share_forward_random",0.624,0.0006,"UNC01 §3")
    add("body_BY2_F04_rightrand","body","sequence=BY2;method=F04","share_right_random",0.172,0.0006,"UNC01 §3")
    return C


def run_claim_checks(claims: pd.DataFrame, tables: dict) -> pd.DataFrame:
    results = []
    for _, c in claims.iterrows():
        tbl = tables.get(c["table"])
        status, actual = "FAIL", float("nan")
        if tbl is None:
            status = "FAIL_NO_TABLE"
        else:
            sub = tbl
            for cond in str(c["selector"]).split(";"):
                cond = cond.strip()
                if not cond:
                    continue
                k, v = cond.split("=", 1)
                sub = sub[sub[k.strip()].astype(str) == v.strip()]
            if len(sub) != 1:
                status = f"FAIL_ROWS_{len(sub)}"
            else:
                actual = float(sub.iloc[0][c["column"]])
                tol = float(c["tolerance"])
                status = "PASS" if abs(actual - float(c["expected"])) <= tol else "FAIL"
        results.append({**c.to_dict(), "actual": actual, "status": status})
    return pd.DataFrame(results)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--out", default="docs/paper_rebuild/v3/uncertainty")
    ap.add_argument("--skip-pins", action="store_true")
    args = ap.parse_args()
    root = Path(args.repo_root)
    src = root / "docs/paper_rebuild/v3/uncertainty"
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)

    pin_report = {}
    for name, expect in UA01_PINS.items():
        actual = sha256(src / name)
        pin_report[name] = {"expected": expect, "actual": actual, "pass": actual == expect}
    (out / "UNC_INPUT_PINS.json").write_text(json.dumps(pin_report, indent=1))
    if not args.skip_pins and not all(v["pass"] for v in pin_report.values()):
        print("PIN MISMATCH:", [k for k, v in pin_report.items() if not v["pass"]])
        sys.exit(2)

    series = num(pd.read_csv(src / "UA01_C00_SERIES_STATS.csv"), ["n", "rmse_recomputed", "mean", "std", "std_slow", "std_fast", "tau_int_s", "n_eff", "se_rmse_acf", "se_rmse_batch_20s", "se_rmse_batch_40s", "rmse_mbb_low", "rmse_mbb_high"])
    paired = num(pd.read_csv(src / "UA01_C00_PAIRED_SERIES.csv"), ["n_common", "rmse_A", "rmse_B", "delta_rmse", "delta_mse", "corr_squared_errors", "se_delta_rmse_acf", "se_delta_rmse_batch_20s", "delta_rmse_mbb_low", "delta_rmse_mbb_high"])
    tsd = num(pd.read_csv(src / "UA01_TYPE_SEED_DISPERSION.csv"), ["n_registered", "n_failure", "n_finite", "mean", "sd", "min", "median", "p95", "max", "cv"])
    bands = num(pd.read_csv(src / "UA01_BY2O_SEGMENT_BANDS.csv"), ["n", "rmse_yaw", "mean_yaw", "std_slow", "std_fast", "rmse_h", "rmse_up"])
    motion = num(pd.read_csv(src / "UA01_MOTION_STATS.csv"), ["mean", "rms", "p95"])
    quant = num(pd.read_csv(src / "UA01_DISTRIBUTION_QUANTILES.csv"), ["n_finite", "n_failure", "median", "p95", "cluster_q95_low", "cluster_q95_high", "naive_q95_low", "naive_q95_high"])
    povr = num(pd.read_csv(src / "UA01_PAIRED_OVERALL.csv"), ["n_pairs", "median", "frac_negative"])
    ext = num(pd.read_csv(src / "UA01_EXTERNAL_PAIRED.csv"), ["n_pairs_finite", "mean", "sd", "median", "min", "max"])
    addp = num(pd.read_csv(src / "UA01_ADDENDUM_PAIRED.csv"), ["n_pairs_finite", "mean", "sd", "median", "p95"])
    adds = num(pd.read_csv(src / "UA01_ADDENDUM_STATS.csv"), ["n_finite", "mean", "sd", "median", "p95", "max"])

    yawdec = derive_yaw_decomposition(series)
    real = derive_realization(series)
    dist = derive_distinguishability(paired)
    seeds = derive_seed_summary(tsd)
    body = parse_body_frame_rows(root)
    fast = series[series.series == "yaw_err_deg"].groupby("sequence").agg(fast_min=("std_fast", "min"), fast_max=("std_fast", "max"), n_estimators=("method", "count")).reset_index()

    yawdec.to_csv(out / "UNC_YAW_DECOMPOSITION.csv", index=False)
    real.to_csv(out / "UNC_REALIZATION_INTERVALS.csv", index=False)
    dist.to_csv(out / "UNC_DISTINGUISHABILITY.csv", index=False)
    seeds.to_csv(out / "UNC_SEED_DISPERSION_SUMMARY.csv", index=False)
    body.to_csv(out / "UNC_HORIZONTAL_BODY_DECOMPOSITION.csv", index=False)
    fast.to_csv(out / "UNC_FAST_COMPONENT_RANGE.csv", index=False)

    tables = {"yawdec": yawdec, "real": real, "dist": dist, "seeds": seeds, "body": body, "fast": fast, "tsd": tsd,
              "bands": bands, "motion": motion, "quant": quant, "povr": povr, "ext": ext, "addp": addp, "adds": adds}
    claims = pd.DataFrame(build_claims(), columns=["claim_id", "table", "selector", "column", "expected", "tolerance", "used_in"])
    claims.to_csv(out / "UNC_CLAIM_CHECKS.csv", index=False)
    res = run_claim_checks(claims, tables)
    res.to_csv(out / "UNC_CLAIM_CHECK_RESULTS.csv", index=False)
    n_pass = int((res.status == "PASS").sum())
    print(f"claim checks: {n_pass}/{len(res)} PASS")
    if n_pass != len(res):
        print(res[res.status != "PASS"].to_string())
        sys.exit(3)
    print("derived tables written to", out)


if __name__ == "__main__":
    main()
