"""Canonical-541 derived tables for the publication-figure task (AGENTS section 12b).

Plotting-side derivation only.  This module reads the frozen evaluation tables and
aggregate tables of the authoritative Canonical-541 attempt, never re-runs a solver,
provider, or evaluator, and fails closed when the frozen identity cannot be
reproduced.

Outputs (written by :func:`build_all`):

    IDENTITY_GATE.json                fail-closed checks against AGENTS section 7
    PAIRWISE_DERIVED_CASE_LEVEL.csv   candidate - reference per case and metric
    PAIRWISE_DERIVED_SUMMARY.csv      mean / bootstrap CI / median / win rate / Wilcoxon
    PAIRWISE_DERIVED_FAMILY.csv       the same by case family
    PAIRWISE_DERIVED_TYPE.csv         the same by degradation type (seed direction)
    TAIL_CASES.csv                    counts of cases beyond fixed thresholds by type
    BIAS_DECOMPOSITION.csv            signed mean / std / rmse / bias share per run
    BIAS_DECOMPOSITION_FAMILY.csv     mean bias share by family and configuration
    BODY_FRAME_BIAS_C00.csv           body-frame mean of the C00 horizontal error
    DERIVED_TABLES_MANIFEST.json      inputs, parameters, output hashes

Delta convention everywhere: candidate - reference, negative is better.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

CONFIG_OF = {
    "F01": "single_antenna_EKF",
    "F02": "basic_dual_yaw_EKF",
    "F03": "AB0000",
    "A04": "AB1011",
    "F04": "AB1111",
}
DISPLAY_OF = {"F01": "Single", "F02": "Dual-basic", "F03": "Backbone", "A04": "Core", "F04": "Full"}
EXPECTED_CONFIGS = {
    "AB0000", "AB0100", "AB0111", "AB1000", "AB1011", "AB1100", "AB1101", "AB1110", "AB1111",
    "basic_dual_yaw_EKF", "single_antenna_EKF",
}
EXPECTED_UNIQUE_ROWS = 5951
EXPECTED_LOGICAL_ROWS = 7033
EXPECTED_CASES = 541
EXPECTED_DEGRADATION_IDS = 61  # D01..D60 + CLEAN
CLEAN_CASE_ID = "C00_clean_normal"
CLEAN_DEGRADATION_IDS = {"CLEAN", "C00"}

# AGENTS.md section 7 (C00 formal yaw RMSE, deg) and section 7A.2 (A04 versus Strong)
AGENTS_C00_YAW_DEG = {
    "single_antenna_EKF": 6.927288,
    "basic_dual_yaw_EKF": 2.338427,
    "AB0000": 1.962413,
    "AB1011": 1.934076,
    "AB1111": 1.954959,
}
AGENTS_7A2_A04_VS_STRONG = {  # metric: (mean delta, win rate)
    "horizontal_rmse_m": (-0.004568, 0.876),
    "up_rmse_m": (-0.000807, 0.976),
    "position_3d_rmse_m": (-0.003589, 0.948),
    "roll_rmse_deg": (-0.012096, 0.982),
    "pitch_rmse_deg": (-0.009315, 0.969),
    "yaw_rmse_deg": (+0.061358, 0.900),
}

COMPARISONS = [
    ("A04", "F03"), ("A04", "F02"), ("F04", "F02"), ("A04", "F01"),
    ("F04", "F01"), ("F04", "A04"), ("F04", "F03"), ("F03", "F02"),
]
FROZEN_EQUIVALENT = {("F04", "F03"): "full_vs_strong", ("F04", "A04"): "full_vs_no_SA", ("F03", "F02"): "strong_vs_basic"}
METRICS = [
    "horizontal_rmse_m", "up_rmse_m", "position_3d_rmse_m", "roll_rmse_deg", "pitch_rmse_deg",
    "yaw_rmse_deg", "horizontal_p95_m", "yaw_p95_absolute_deg",
]
AXES = [("north", "m"), ("east", "m"), ("up", "m"), ("roll", "deg"), ("pitch", "deg"), ("yaw", "deg")]
TAIL_YAW_THRESHOLDS_DEG = (10.0, 30.0)
TAIL_HORIZONTAL_THRESHOLD_M = 2.0
BOOT_N = 10000
BOOT_SEED = 20260904
MAJORITY_MIN_SEEDS = 5
TIE_EPS = 1e-12
IDENTITY_TOL = 1e-5


# --------------------------------------------------------------------------- io
def read_table(root: Path, relative: str) -> pd.DataFrame:
    """Read ``root/relative`` accepting either ``.csv`` or ``.csv.gz``."""
    for candidate in (root / relative, root / (relative + ".gz")):
        if candidate.is_file():
            return pd.read_csv(candidate, dtype=str, low_memory=False)
    raise FileNotFoundError(f"{relative}(.gz) not found under {root}")


def load_unique(attempt_root: Path) -> pd.DataFrame:
    return read_table(attempt_root, "12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv")


def load_logical(attempt_root: Path) -> pd.DataFrame:
    return read_table(attempt_root, "12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv")


def load_frozen_pairwise_summary(attempt_root: Path) -> pd.DataFrame:
    return read_table(attempt_root, "13_AGGREGATE/PAIRWISE_SUMMARY.csv")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: Path | None = None) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    except Exception:  # noqa: BLE001 - best effort provenance
        return "unknown"


# ------------------------------------------------------------------ identity gate
def is_clean(case_id: str, degradation_id: str) -> bool:
    return case_id == CLEAN_CASE_ID or str(degradation_id) in CLEAN_DEGRADATION_IDS


def identity_gate(unique: pd.DataFrame, logical: pd.DataFrame | None = None) -> dict:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    check("unique_rows", len(unique) == EXPECTED_UNIQUE_ROWS, f"{len(unique)} (expected {EXPECTED_UNIQUE_ROWS})")
    if logical is not None:
        check("logical_rows", len(logical) == EXPECTED_LOGICAL_ROWS, f"{len(logical)} (expected {EXPECTED_LOGICAL_ROWS})")
    cases = unique["case_id"].nunique()
    check("cases", cases == EXPECTED_CASES, f"{cases} (expected {EXPECTED_CASES})")
    cfgs = set(unique["effective_configuration_id"].dropna().unique())
    check("configurations", cfgs == EXPECTED_CONFIGS, f"{sorted(cfgs)}")
    per_cfg = unique.groupby("effective_configuration_id")["case_id"].nunique()
    check("cases_per_configuration", bool((per_cfg == EXPECTED_CASES).all()), per_cfg.to_dict().__repr__())
    dups = int(unique.duplicated(["case_id", "effective_configuration_id"]).sum())
    check("no_duplicate_case_configuration", dups == 0, f"{dups} duplicates")
    n_deg = unique["degradation_id"].nunique()
    check("degradation_ids", n_deg == EXPECTED_DEGRADATION_IDS, f"{n_deg} (expected {EXPECTED_DEGRADATION_IDS})")
    status = unique["evaluation_status"].value_counts().to_dict()
    check("all_completed", set(status) == {"COMPLETED"}, repr(status))
    clean_rows = unique[unique["case_id"] == CLEAN_CASE_ID].set_index("effective_configuration_id")
    check("clean_case_present", len(clean_rows) == len(EXPECTED_CONFIGS), f"{len(clean_rows)} clean rows")
    for cfg, expected in AGENTS_C00_YAW_DEG.items():
        got = float(clean_rows.loc[cfg, "yaw_rmse_deg"]) if cfg in clean_rows.index else float("nan")
        check(f"c00_yaw_{cfg}", abs(got - expected) <= IDENTITY_TOL, f"got {got:.6f}, AGENTS {expected:.6f}")
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


# ------------------------------------------------------------- pairwise derivation
def case_meta(unique: pd.DataFrame) -> pd.DataFrame:
    meta = unique.drop_duplicates("case_id").set_index("case_id")[["case_family", "degradation_id", "seed_id"]].copy()
    meta["degradation_id"] = meta["degradation_id"].where(~meta["degradation_id"].isin(CLEAN_DEGRADATION_IDS), "C00")
    return meta


def metric_pivot(unique: pd.DataFrame, metric: str) -> pd.DataFrame:
    return unique.pivot(index="case_id", columns="effective_configuration_id", values=metric).astype(float)


def pairwise_case_level(unique: pd.DataFrame, cand: str, ref: str, metric: str) -> pd.DataFrame:
    piv = metric_pivot(unique, metric)
    cand_cfg, ref_cfg = CONFIG_OF[cand], CONFIG_OF[ref]
    df = pd.DataFrame({"candidate_value": piv[cand_cfg], "reference_value": piv[ref_cfg]})
    df["delta_candidate_minus_reference"] = df["candidate_value"] - df["reference_value"]
    df = df.dropna(subset=["delta_candidate_minus_reference"]).join(case_meta(unique))
    df.insert(0, "comparison", f"{cand}_vs_{ref}")
    df.insert(1, "candidate", cand)
    df.insert(2, "reference", ref)
    df.insert(3, "metric_name", metric)
    return df.reset_index().rename(columns={"index": "case_id"})


def wilcoxon_signed_rank_p(delta: np.ndarray) -> float:
    """Two-sided Wilcoxon signed-rank test, normal approximation with tie and
    continuity correction (Pratt-free: zero deltas are discarded, as SciPy 'wilcox')."""
    d = np.asarray(delta, dtype=float)
    d = d[np.abs(d) > TIE_EPS]
    n = d.size
    if n < 10:
        return float("nan")
    ranks = pd.Series(np.abs(d)).rank(method="average").to_numpy()
    w_plus = float(ranks[d > 0].sum())
    mean = n * (n + 1) / 4.0
    _, counts = np.unique(ranks, return_counts=True)
    tie_term = float(((counts ** 3 - counts) / 2.0).sum())
    var = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term / 24.0
    if var <= 0:
        return float("nan")
    z = (w_plus - mean - 0.5 * np.sign(w_plus - mean)) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def bootstrap_mean_ci(delta: np.ndarray, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    d = np.asarray(delta, dtype=float)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def _rates(d: np.ndarray) -> dict:
    return {
        "win_count": int((d < -TIE_EPS).sum()),
        "tie_count": int((np.abs(d) <= TIE_EPS).sum()),
        "loss_count": int((d > TIE_EPS).sum()),
        "win_rate": float((d < -TIE_EPS).mean()),
    }


def summarize_pairwise(case_level: pd.DataFrame, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    d = case_level["delta_candidate_minus_reference"].to_numpy(dtype=float)
    lo, hi = bootstrap_mean_ci(d, n_boot, seed)
    degraded = case_level[case_level["degradation_id"] != "C00"]
    per_type = degraded.groupby("degradation_id")["delta_candidate_minus_reference"]
    negative = per_type.apply(lambda s: int((s < -TIE_EPS).sum()))
    row = {
        "comparison": case_level["comparison"].iloc[0],
        "metric_name": case_level["metric_name"].iloc[0],
        "paired_sample_count": int(d.size),
        "mean_delta": float(d.mean()),
        "ci95_low": lo,
        "ci95_high": hi,
        "median_delta": float(np.median(d)),
        "p10_delta": float(np.percentile(d, 10)),
        "p90_delta": float(np.percentile(d, 90)),
        "wilcoxon_p": wilcoxon_signed_rank_p(d),
        "majority_seed_improved_types": int((negative >= MAJORITY_MIN_SEEDS).sum()),
        "degraded_type_count": int(per_type.ngroups),
        "delta_definition": "candidate_minus_reference_negative_is_better",
    }
    row.update(_rates(d))
    return row


def summarize_by(case_level: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for key, grp in case_level.groupby(by):
        d = grp["delta_candidate_minus_reference"].to_numpy(dtype=float)
        row = {
            "comparison": grp["comparison"].iloc[0],
            "metric_name": grp["metric_name"].iloc[0],
            by: key,
            "paired_sample_count": int(d.size),
            "mean_delta": float(d.mean()),
            "median_delta": float(np.median(d)),
            "std_delta": float(d.std(ddof=1)) if d.size > 1 else float("nan"),
            "min_delta": float(d.min()),
            "max_delta": float(d.max()),
            "wilcoxon_p": wilcoxon_signed_rank_p(d),
        }
        row.update(_rates(d))
        if by == "degradation_id":
            row["case_family"] = grp["case_family"].iloc[0]
            row["direction_consistency_ratio"] = float(max(row["win_count"], row["loss_count"]) / max(d.size, 1))
        rows.append(row)
    return pd.DataFrame(rows)


def derive_pairwise(unique: pd.DataFrame, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict[str, pd.DataFrame]:
    case_frames, summary_rows, family_frames, type_frames = [], [], [], []
    for cand, ref in COMPARISONS:
        for metric in METRICS:
            if metric not in unique.columns:
                continue
            cl = pairwise_case_level(unique, cand, ref, metric)
            case_frames.append(cl)
            summary_rows.append(summarize_pairwise(cl, n_boot, seed))
            family_frames.append(summarize_by(cl, "case_family"))
            type_frames.append(summarize_by(cl, "degradation_id"))
    return {
        "case_level": pd.concat(case_frames, ignore_index=True),
        "summary": pd.DataFrame(summary_rows),
        "family": pd.concat(family_frames, ignore_index=True),
        "type": pd.concat(type_frames, ignore_index=True),
    }


def validate_against_frozen(summary: pd.DataFrame, frozen: pd.DataFrame, tol: float = 1e-6) -> dict:
    """Fail-closed: derived joins must reproduce the frozen aggregate and AGENTS 7A.2."""
    checks = []
    frozen = frozen[frozen["scope"] == "overall"]
    for (cand, ref), name in FROZEN_EQUIVALENT.items():
        for metric in ("horizontal_rmse_m", "yaw_rmse_deg"):
            fr = frozen[(frozen["comparison"] == name) & (frozen["metric_name"] == metric)]
            mine = summary[(summary["comparison"] == f"{cand}_vs_{ref}") & (summary["metric_name"] == metric)]
            if fr.empty or mine.empty:
                checks.append({"check": f"{name}:{metric}", "pass": False, "detail": "row missing"})
                continue
            dm = abs(float(fr["mean_delta_candidate_minus_reference"].iloc[0]) - float(mine["mean_delta"].iloc[0]))
            dw = abs(float(fr["win_rate"].iloc[0]) - float(mine["win_rate"].iloc[0]))
            checks.append({"check": f"{name}:{metric}", "pass": dm <= tol and dw <= tol, "detail": f"mean diff {dm:.2e}, win diff {dw:.2e}"})
    for metric, (mean_delta, win_rate) in AGENTS_7A2_A04_VS_STRONG.items():
        mine = summary[(summary["comparison"] == "A04_vs_F03") & (summary["metric_name"] == metric)]
        if mine.empty:
            checks.append({"check": f"agents_7A2:{metric}", "pass": False, "detail": "row missing"})
            continue
        dm = abs(float(mine["mean_delta"].iloc[0]) - mean_delta)
        dw = abs(float(mine["win_rate"].iloc[0]) - win_rate)
        checks.append({"check": f"agents_7A2:{metric}", "pass": dm <= 5e-7 and dw <= 5e-4, "detail": f"mean diff {dm:.2e}, win diff {dw:.2e}"})
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


# ------------------------------------------------------------------------ tails
def tail_tables(unique: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sub = unique[unique["effective_configuration_id"].isin(CONFIG_OF.values())].copy()
    sub["yaw"] = sub["yaw_rmse_deg"].astype(float)
    sub["h"] = sub["horizontal_rmse_m"].astype(float)
    label_of = {v: k for k, v in CONFIG_OF.items()}
    for cfg, grp in sub.groupby("effective_configuration_id"):
        specs = [("yaw_rmse_deg", thr, grp["yaw"] > thr) for thr in TAIL_YAW_THRESHOLDS_DEG]
        specs.append(("horizontal_rmse_m", TAIL_HORIZONTAL_THRESHOLD_M, grp["h"] > TAIL_HORIZONTAL_THRESHOLD_M))
        for metric, thr, mask in specs:
            by_type = grp[mask].groupby("degradation_id").size().to_dict()
            rows.append({
                "method_id": label_of[cfg], "display_name": DISPLAY_OF[label_of[cfg]],
                "effective_configuration_id": cfg, "metric_name": metric, "threshold": thr,
                "case_count": int(mask.sum()), "case_total": int(len(grp)),
                "types_json": json.dumps(by_type, sort_keys=True),
            })
    return pd.DataFrame(rows)


# ------------------------------------------------------------ bias decomposition
def bias_decomposition(unique: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for r in unique.itertuples(index=False):
        row = {
            "run_id": r.run_id, "case_id": r.case_id, "degradation_id": r.degradation_id,
            "case_family": r.case_family, "effective_configuration_id": r.effective_configuration_id,
        }
        for axis, unit in AXES:
            mean = float(getattr(r, f"{axis}_signed_mean_{unit}"))
            std = float(getattr(r, f"{axis}_standard_deviation_{unit}"))
            rmse = float(getattr(r, f"{axis}_rmse_{unit}"))
            row[f"{axis}_signed_mean_{unit}"] = mean
            row[f"{axis}_standard_deviation_{unit}"] = std
            row[f"{axis}_rmse_{unit}"] = rmse
            row[f"{axis}_bias_share"] = (mean * mean) / (rmse * rmse) if rmse > 0 else float("nan")
        rows.append(row)
    per_run = pd.DataFrame(rows)
    share_cols = [f"{axis}_bias_share" for axis, _ in AXES]
    mean_cols = [f"{axis}_signed_mean_{unit}" for axis, unit in AXES]
    by_family = per_run.groupby(["case_family", "effective_configuration_id"])[share_cols + mean_cols].mean().reset_index()
    return per_run, by_family


def body_frame_bias(series: pd.DataFrame, nav: pd.DataFrame) -> dict:
    """Rotate the NED horizontal error into the body frame with the solver yaw.

    ``series`` needs ``time, err_n_m, err_e_m``; ``nav`` is the KF-GINS Navresult
    table (columns: week, tow, lat, lon, h, vn, ve, vd, roll, pitch, yaw_deg)."""
    yaw = np.interp(series["time"].to_numpy(float), nav.iloc[:, 1].to_numpy(float),
                    np.unwrap(np.deg2rad(nav.iloc[:, 10].to_numpy(float))))
    en, ee = series["err_n_m"].to_numpy(float), series["err_e_m"].to_numpy(float)
    fwd = np.cos(yaw) * en + np.sin(yaw) * ee
    right = -np.sin(yaw) * en + np.cos(yaw) * ee
    h_mse = float(np.mean(en * en + ee * ee))
    mag2 = float(fwd.mean() ** 2 + right.mean() ** 2)
    return {
        "sample_count": int(len(series)),
        "ned_mean_north_m": float(en.mean()), "ned_mean_east_m": float(ee.mean()),
        "body_mean_forward_m": float(fwd.mean()), "body_mean_right_m": float(right.mean()),
        "body_offset_magnitude_m": math.sqrt(mag2),
        "body_offset_share_of_horizontal_mse": mag2 / h_mse if h_mse > 0 else float("nan"),
    }


def read_nav(path: Path) -> pd.DataFrame:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as fh:
        return pd.read_csv(fh, sep=r"\s+", header=None)


def read_series(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, usecols=lambda c: c in {"time", "err_n_m", "err_e_m", "err_u_m"})


def attempt_series_resolver(attempt_root: Path) -> Callable[[pd.Series], tuple[Path | None, Path | None]]:
    eval_root = attempt_root / "12_OFFLINE_EVALUATION"

    def resolve(row: pd.Series) -> tuple[Path | None, Path | None]:
        series = None
        for d in (eval_root / row["run_id"], *eval_root.glob(f"*/{row['run_id']}")):
            for name in ("error_series.csv.gz", "error_series.csv"):
                if (d / name).is_file():
                    series = d / name
                    break
            if series:
                break
        nav = Path(str(row["output_root"])) / "KF_GINS_Navresult.nav"
        return series, (nav if nav.is_file() else None)

    return resolve


def handoff_subset_resolver(subset_root: Path) -> Callable[[pd.Series], tuple[Path | None, Path | None]]:
    def resolve(row: pd.Series) -> tuple[Path | None, Path | None]:
        series = subset_root / "error_series_subset" / f"{row['run_id']}.csv.gz"
        nav = subset_root / f"C00_NAV_{row['effective_configuration_id']}.nav.gz"
        return (series if series.is_file() else None), (nav if nav.is_file() else None)

    return resolve


def body_frame_bias_c00(unique: pd.DataFrame, resolver) -> pd.DataFrame:
    rows = []
    clean = unique[(unique["case_id"] == CLEAN_CASE_ID) & unique["effective_configuration_id"].isin(CONFIG_OF.values())]
    for _, row in clean.iterrows():
        series_path, nav_path = resolver(row)
        base = {"run_id": row["run_id"], "effective_configuration_id": row["effective_configuration_id"]}
        if series_path is None or nav_path is None:
            rows.append({**base, "status": "INPUT_NOT_FOUND", "series_path": str(series_path), "nav_path": str(nav_path)})
            continue
        stats = body_frame_bias(read_series(series_path), read_nav(nav_path))
        rows.append({**base, "status": "OK", "series_path": str(series_path), "nav_path": str(nav_path), **stats})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- driver
def build_all(attempt_root: Path, out_dir: Path, resolver=None, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    attempt_root, out_dir = Path(attempt_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    unique, logical = load_unique(attempt_root), load_logical(attempt_root)
    gate = identity_gate(unique, logical)
    (out_dir / "IDENTITY_GATE.json").write_text(json.dumps(gate, indent=2))
    if not gate["pass"]:
        raise RuntimeError("identity gate FAILED; see IDENTITY_GATE.json")
    derived = derive_pairwise(unique, n_boot, seed)
    validation = validate_against_frozen(derived["summary"], load_frozen_pairwise_summary(attempt_root))
    (out_dir / "FROZEN_VALIDATION.json").write_text(json.dumps(validation, indent=2))
    if not validation["pass"]:
        raise RuntimeError("derived pairwise tables do not reproduce the frozen aggregate; see FROZEN_VALIDATION.json")
    derived["case_level"].to_csv(out_dir / "PAIRWISE_DERIVED_CASE_LEVEL.csv", index=False)
    derived["summary"].to_csv(out_dir / "PAIRWISE_DERIVED_SUMMARY.csv", index=False)
    derived["family"].to_csv(out_dir / "PAIRWISE_DERIVED_FAMILY.csv", index=False)
    derived["type"].to_csv(out_dir / "PAIRWISE_DERIVED_TYPE.csv", index=False)
    tail_tables(unique).to_csv(out_dir / "TAIL_CASES.csv", index=False)
    per_run, by_family = bias_decomposition(unique)
    per_run.to_csv(out_dir / "BIAS_DECOMPOSITION.csv", index=False)
    by_family.to_csv(out_dir / "BIAS_DECOMPOSITION_FAMILY.csv", index=False)
    body = body_frame_bias_c00(unique, resolver or attempt_series_resolver(attempt_root))
    body.to_csv(out_dir / "BODY_FRAME_BIAS_C00.csv", index=False)
    inputs = {}
    for rel in ("12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv", "12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv", "13_AGGREGATE/PAIRWISE_SUMMARY.csv"):
        for candidate in (attempt_root / rel, attempt_root / (rel + ".gz")):
            if candidate.is_file():
                inputs[str(candidate)] = sha256_of(candidate)
    outputs = {p.name: sha256_of(p) for p in sorted(out_dir.glob("*.csv"))}
    manifest = {
        "task": "AGENTS section 12b derived tables (plotting-side, no rerun)",
        "attempt_root": str(attempt_root), "git_head": git_head(),
        "parameters": {"bootstrap_samples": n_boot, "bootstrap_seed": seed, "majority_min_seeds": MAJORITY_MIN_SEEDS,
                       "tail_yaw_thresholds_deg": TAIL_YAW_THRESHOLDS_DEG, "tail_horizontal_threshold_m": TAIL_HORIZONTAL_THRESHOLD_M,
                       "comparisons": [f"{c}_vs_{r}" for c, r in COMPARISONS], "metrics": METRICS},
        "identity_gate": gate["pass"], "frozen_validation": validation["pass"],
        "body_frame_status": body["status"].value_counts().to_dict() if len(body) else {},
        "inputs_sha256": inputs, "outputs_sha256": outputs,
    }
    (out_dir / "DERIVED_TABLES_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return manifest
