#!/usr/bin/env python3
"""Decompose an already saved no-foot source chart's original residuals.

Read only the saved Gaussian graph, its linearization Values and source-chart
record. At delta=0 each original factor's whitened residual is -b. No graph is
rebuilt, optimized, reweighted or evaluated against a navigation reference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import gtsam
import numpy as np


def _family(keys, dimension):
    symbols = Counter(chr(gtsam.Symbol(key).chr()) for key in keys)
    if dimension == 9 and symbols == {"x": 2, "v": 2, "b": 1}:
        return "IMU_PREINTEGRATION"
    if dimension == 6 and symbols == {"b": 2}:
        return "BIAS_RANDOM_WALK"
    if dimension == 6 and symbols == {"b": 1}:
        return "INITIAL_BIAS_PRIOR"
    if dimension == 6 and symbols in ({"x": 1, "v": 1}, {"x": 1, "v": 1, "b": 1}):
        return "GNSS_POSITION_VELOCITY"
    if dimension == 3 and symbols == {"x": 1}:
        return "GNSS_POSITION"
    if dimension == 3 and symbols in ({"v": 1}, {"x": 1, "v": 1}, {"x": 1, "v": 1, "b": 1}):
        return "GNSS_VELOCITY"
    return "UNCLASSIFIED_ORIGINAL_FACTOR"


def summarize(graph, values):
    """Classify the sparse original factors; do not form a global dense matrix."""
    rows, grouped = [], defaultdict(list)
    zeros = values.zeroVectors()
    for index in range(graph.size()):
        factor = gtsam.JacobianFactor(graph.at(index))
        _, vector = factor.jacobian()
        residual = -np.asarray(vector, float).reshape(-1)
        dimension, keys = len(residual), tuple(factor.keys())
        family = _family(keys, dimension)
        rss = float(residual@residual)
        # This equality also establishes the saved Jacobian API's whitening
        # convention, rather than assuming b contains unweighted physical units.
        if not np.isclose(rss, 2*factor.error(zeros), rtol=1e-11, atol=1e-10):
            raise ValueError(f"factor {index} cannot be read as an original whitened residual")
        indices = [int(gtsam.Symbol(key).index()) for key in keys]
        row = dict(factor_index=index, family=family, scalar_rows=dimension,
                   first_state_index=min(indices), last_state_index=max(indices),
                   whitened_residual_sum_squares=rss,
                   rss_per_scalar_row=rss/dimension,
                   maximum_absolute_whitened_coordinate=float(np.max(np.abs(residual))),
                   keys="|".join(f"{chr(gtsam.Symbol(key).chr())}{gtsam.Symbol(key).index()}" for key in keys))
        rows.append(row)
        grouped[family].append(row)

    scalar_rows = sum(row["scalar_rows"] for row in rows)
    state_dimension = int(values.dim())
    rss = sum(row["whitened_residual_sum_squares"] for row in rows)
    nominal_dof = scalar_rows-state_dimension
    families = {}
    for family, members in sorted(grouped.items()):
        count = sum(row["scalar_rows"] for row in members)
        subtotal = sum(row["whitened_residual_sum_squares"] for row in members)
        normalized = np.array([row["rss_per_scalar_row"] for row in members])
        families[family] = dict(
            factor_count=len(members), scalar_rows=count, whitened_residual_sum_squares=subtotal,
            share_of_total_rss=subtotal/rss if rss else 0., rss_per_scalar_row=subtotal/count,
            factor_rss_per_row_quantiles=dict(zip(("p50", "p90", "p95", "p99", "maximum"),
                                                 map(float, np.quantile(normalized, [.5, .9, .95, .99, 1.])))),
            largest_factors=sorted(members, key=lambda row: row["whitened_residual_sum_squares"],
                                   reverse=True)[:10])
    return rows, dict(
        factor_count=len(rows), scalar_residual_rows=scalar_rows, fitted_state_dimension=state_dimension,
        state_key_counts_by_symbol=dict(sorted(Counter(chr(gtsam.Symbol(key).chr()) for key in values.keys()).items())),
        whitened_residual_sum_squares=rss, gtsam_half_squared_error=rss/2,
        nominal_residual_dof_if_full_column_rank=nominal_dof,
        rss_per_nominal_dof=rss/nominal_dof if nominal_dof > 0 else None,
        rss_per_scalar_row=rss/scalar_rows, families=families,
        rank_computed=False,
        classification_scope="SAVED_ORIGINAL_FACTOR_KEY_STRUCTURE_AND_RESIDUAL_DIMENSION",
        interpretation=dict(
            normalized_cost="GTSAM error is half the whitened residual sum of squares; use 2*error for RSS.",
            dof="m-n assumes full local column rank; no new global rank factorization is performed.",
            subgroup_dof="Per-family RSS/row is descriptive, not a family chi-square statistic after shared-state fitting.",
            source_attribution="A large family contribution locates tension in the fitted source graph; it does not identify which physical sensor caused it.",
            coordinates="Whitened coordinates can mix correlated physical residual components; no metre or acceleration error is inferred from b.",
            indices="State indices identify source events, not seconds; exact physical times require joining the original event mapping.",
            calibration="Stationarity and fitted process parameters do not establish source-model calibration or physical sliding identification."))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.calibration_root.resolve()
    chart = json.loads((source/"NOFOOT_SOURCE_CHART.json").read_text())
    if not chart.get("original_factors_only", False):
        raise ValueError("this decomposition requires original factors, not a marginalized source chart")
    graph, values = gtsam.GaussianFactorGraph(), gtsam.Values()
    graph.deserialize((source/"NOFOOT_GAUSSIAN_GRAPH.txt").read_text())
    values.deserialize((source/"NOFOOT_LINEARIZATION_VALUES.txt").read_text())
    rows, report = summarize(graph, values)
    selected = [seed for seed in chart["seeds"] if seed["seed_yaw_deg"] == chart["chosen_seed_yaw_deg"]]
    original_cost = float(selected[0]["nonlinear_cost"])
    if not np.isclose(report["gtsam_half_squared_error"], original_cost, rtol=1e-9, atol=1e-8):
        raise ValueError("saved linearization residuals do not match the selected original source cost")
    report.update(calibration_root=str(source), selected_seed_yaw_deg=chart["chosen_seed_yaw_deg"],
                  selected_original_nonlinear_cost=original_cost,
                  source_chart_scope=chart["chart_scope"],
                  original_cost_identity_verified=True, nonlinear_optimization_calls=0,
                  new_navigation_runs=0, noise_parameters_changed=False, reference_reads=0)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root/"SOURCE_CHART_RESIDUALS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    with (args.output_root/"SOURCE_CHART_FACTOR_RESIDUALS.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: report[key] for key in
                      ("factor_count", "scalar_residual_rows", "fitted_state_dimension",
                       "whitened_residual_sum_squares", "nominal_residual_dof_if_full_column_rank",
                       "rss_per_nominal_dof")}, indent=2))


if __name__ == "__main__":
    main()
