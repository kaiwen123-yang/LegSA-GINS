"""Tests for legsa_gins.paper_rebuild.publication.derived_tables (AGENTS section 12b)."""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from legsa_gins.paper_rebuild.publication import derived_tables as dt

CONFIGS = list(dt.CONFIG_OF.values())


def _synthetic_unique() -> pd.DataFrame:
    """Three degraded types x 3 seeds + clean, five configurations, deterministic values."""
    rows = []
    run = 0
    cases = [("C00_clean_normal", "CLEAN", "clean", "none")]
    for dtype, fam in [("D01", "gnss_outage"), ("D02", "gnss_outage"), ("D30", "dual_yaw")]:
        for seed in range(3):
            cases.append((f"{dtype}_seed_0{seed}", dtype, fam, f"seed_0{seed}"))
    for idx, (case_id, deg, fam, seed) in enumerate(cases):
        for cfg in CONFIGS:
            run += 1
            base = 1.0 + 0.05 * (idx % 7)
            # AB1011 is better than AB0000 by 0.01 on every case except D30 seeds where it ties
            adj = {"single_antenna_EKF": 0.5, "basic_dual_yaw_EKF": 0.2, "AB0000": 0.0, "AB1011": -0.01, "AB1111": 0.02}[cfg]
            if deg == "D30" and cfg == "AB1011":
                adj = 0.0
            val = base + adj
            row = {
                "run_id": f"RUN_{run:05d}", "case_id": case_id, "degradation_id": deg, "case_family": fam,
                "seed_id": seed, "effective_configuration_id": cfg, "evaluation_status": "COMPLETED",
                "output_root": "/nonexistent",
            }
            for m in dt.METRICS:
                row[m] = f"{val:.6f}"
            for axis, unit in dt.AXES:
                row[f"{axis}_signed_mean_{unit}"] = "0.3"
                row[f"{axis}_standard_deviation_{unit}"] = "0.4"
                row[f"{axis}_rmse_{unit}"] = "0.5"
            rows.append(row)
    return pd.DataFrame(rows)


def test_pairwise_sign_convention_and_rates():
    u = _synthetic_unique()
    cl = dt.pairwise_case_level(u, "A04", "F03", "horizontal_rmse_m")
    assert set(cl["comparison"]) == {"A04_vs_F03"}
    assert len(cl) == 10
    d = cl["delta_candidate_minus_reference"]
    # D30 seeds tie, everything else improves by 0.01 (negative = better)
    assert (d[cl["degradation_id"] == "D30"].abs() <= dt.TIE_EPS).all()
    assert np.allclose(d[cl["degradation_id"] != "D30"], -0.01)
    s = dt.summarize_pairwise(cl, n_boot=200, seed=1)
    assert s["win_count"] == 7 and s["tie_count"] == 3 and s["loss_count"] == 0
    assert s["majority_seed_improved_types"] == 0  # only 3 seeds per type in the fixture (<5)
    assert s["degraded_type_count"] == 3
    assert s["ci95_low"] <= s["mean_delta"] <= s["ci95_high"]


def test_bootstrap_is_deterministic_for_a_seed():
    d = np.array([-0.3, -0.2, 0.1, -0.05, 0.0, -0.4, 0.2, -0.1])
    assert dt.bootstrap_mean_ci(d, 500, 7) == dt.bootstrap_mean_ci(d, 500, 7)
    assert dt.bootstrap_mean_ci(d, 500, 7) != dt.bootstrap_mean_ci(d, 500, 8)


def test_wilcoxon_matches_scipy_normal_approximation():
    scipy_stats = pytest.importorskip("scipy.stats")
    rng = np.random.default_rng(3)
    d = rng.normal(-0.05, 0.3, size=120)
    mine = dt.wilcoxon_signed_rank_p(d)
    ref = scipy_stats.wilcoxon(d, zero_method="wilcox", correction=True, method="approx").pvalue
    assert math.isclose(mine, ref, rel_tol=1e-6)


def test_wilcoxon_returns_nan_for_tiny_or_all_tied_samples():
    assert math.isnan(dt.wilcoxon_signed_rank_p(np.zeros(50)))
    assert math.isnan(dt.wilcoxon_signed_rank_p(np.array([-1.0, 1.0, -2.0])))


def test_bias_decomposition_share():
    per_run, by_family = dt.bias_decomposition(_synthetic_unique())
    assert np.allclose(per_run["up_bias_share"], 0.36)  # 0.3^2 / 0.5^2
    assert set(by_family.columns) >= {"case_family", "effective_configuration_id", "up_bias_share", "up_signed_mean_m"}


def test_body_frame_bias_recovers_a_constant_body_offset():
    # constant body-frame offset (forward -0.2, right +0.15) seen through a yaw sweep
    t = np.arange(0.0, 300.0, 0.5)
    yaw = np.deg2rad(np.linspace(0, 720, t.size))
    fwd, right = -0.2, 0.15
    en = np.cos(yaw) * fwd - np.sin(yaw) * right
    ee = np.sin(yaw) * fwd + np.cos(yaw) * right
    series = pd.DataFrame({"time": t, "err_n_m": en, "err_e_m": ee})
    nav = pd.DataFrame(np.column_stack([np.zeros(t.size), t] + [np.zeros(t.size)] * 8 + [np.rad2deg(yaw) % 360]))
    stats = dt.body_frame_bias(series, nav)
    assert math.isclose(stats["body_mean_forward_m"], fwd, abs_tol=1e-6)
    assert math.isclose(stats["body_mean_right_m"], right, abs_tol=1e-6)
    assert abs(stats["ned_mean_north_m"]) < 1e-3 and abs(stats["ned_mean_east_m"]) < 1e-3
    assert math.isclose(stats["body_offset_share_of_horizontal_mse"], 1.0, abs_tol=1e-6)


def test_identity_gate_fails_closed_on_synthetic_data():
    gate = dt.identity_gate(_synthetic_unique())
    assert gate["pass"] is False
    names = {c["check"] for c in gate["checks"]}
    assert {"unique_rows", "cases", "configurations", "c00_yaw_AB1011"} <= names


def test_tail_tables_thresholds():
    t = dt.tail_tables(_synthetic_unique())
    assert set(t["threshold"]) == {10.0, 30.0, 2.0}
    assert (t["case_count"] == 0).all()  # synthetic values are ~1


@pytest.mark.skipif(not os.environ.get("LEGSA_C541_ATTEMPT_ROOT"), reason="LEGSA_C541_ATTEMPT_ROOT not set")
def test_real_attempt_reproduces_agents_7a2():
    root = Path(os.environ["LEGSA_C541_ATTEMPT_ROOT"])
    unique = dt.load_unique(root)
    gate = dt.identity_gate(unique)
    assert gate["pass"], [c for c in gate["checks"] if not c["pass"]]
    cl = dt.pairwise_case_level(unique, "A04", "F03", "horizontal_rmse_m")
    s = dt.summarize_pairwise(cl, n_boot=100, seed=1)
    assert math.isclose(s["mean_delta"], -0.004568, abs_tol=5e-7)
    assert math.isclose(s["win_rate"], 0.876, abs_tol=5e-4)
    assert s["majority_seed_improved_types"] == 54
