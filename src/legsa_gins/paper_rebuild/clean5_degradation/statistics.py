"""Preregistered case-paired four-column comparisons; no solver/evaluator calls."""
from __future__ import annotations

from collections import defaultdict
import math
import warnings

import numpy as np
from scipy.stats import wilcoxon

from .common import FLAGS, pinned, read_csv, write_csv, write_json


def paired_statistics(values, spec):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("Paired differences must be finite; no silent case deletion")
    if not len(x):
        return {"status": "UNAVAILABLE", "n": 0}
    rng = np.random.Generator(np.random.PCG64(spec["bootstrap"]["seed"]))
    # Bound peak memory while preserving the registered random stream.
    sampled = []
    remaining = spec["bootstrap"]["resamples"]
    while remaining:
        count = min(remaining, 256)
        sampled.extend(np.median(x[rng.integers(0, len(x), size=(count, len(x)))], axis=1))
        remaining -= count
    ci = np.quantile(sampled, [.025, .975], method="linear")
    if len(x) < 2:
        p, status = None, "UNAVAILABLE_N_LESS_THAN_2"
    elif np.all(x == 0):
        p, status = 1., "ALL_ZERO_CONVENTION"
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            p = float(wilcoxon(x, zero_method="wilcox", correction=False,
                               alternative="two-sided", method="auto").pvalue)
        status = "AVAILABLE"
    return {"status": "AVAILABLE", "n": len(x), "median_delta": float(np.median(x)),
            "win_rate": float(np.mean(x < -1e-12)), "win_count": int(np.sum(x < -1e-12)),
            "tie_count": int(np.sum(np.abs(x) <= 1e-12)), "ci95_low": float(ci[0]),
            "ci95_high": float(ci[1]), "wilcoxon_p": p, "wilcoxon_status": status}


def strict_same_direction(reference, candidate):
    if reference.get("status") != "AVAILABLE" or candidate.get("status") != "AVAILABLE":
        return False
    return (reference["median_delta"] * candidate["median_delta"] > 0
            and (reference["win_rate"] - .5) * (candidate["win_rate"] - .5) > 0)


def build_comparison(contract, reg, stage, results, code_commit):
    spec = contract["statistics"]
    frozen = read_csv(pinned(contract["sources"]["pairwise_case_level"], reg))
    summary = read_csv(pinned(contract["sources"]["pairwise_summary"], reg))
    selected = set(contract["selection"]["selected_case_ids"])
    metrics = spec["primary_metrics"] + spec["secondary_metrics"]
    index = {(r["chain"], r["evaluator_version"], r["case_id"], r["method_id"]): r for r in results}
    if len(index) != len(results):
        raise ValueError("Duplicate new evaluation identities")
    frozen_groups = defaultdict(list)
    for r in frozen:
        frozen_groups[(r["comparison"], r["metric_name"])].append(r)
    summaries = {(r["comparison"], r["metric_name"]): r for r in summary
                 if r["scope"] == "overall" and r["family"] == "ALL"}
    comparison, pairs, flips, missing = [], [], [], []
    for definition in spec["pair_definitions"]:
        name = definition["comparison"]
        for metric in metrics:
            old_rows = frozen_groups[(name, metric)]
            if len(old_rows) != 541 or len({r["case_id"] for r in old_rows}) != 541:
                raise ValueError("Frozen full pair coverage changed")
            old_values = [float(r["delta_candidate_minus_reference"]) for r in old_rows]
            full = paired_statistics(old_values, spec)
            old_summary = summaries[(name, metric)]
            frozen_median = float(old_summary["median_delta_candidate_minus_reference"])
            frozen_win = float(old_summary["win_rate"])
            if not math.isclose(full["median_delta"], frozen_median, abs_tol=1e-13, rel_tol=1e-12):
                raise ValueError("Frozen summary/case delta median disagreement")
            if not math.isclose(full["win_rate"], frozen_win, abs_tol=1e-13):
                raise ValueError("Frozen summary/case win-rate disagreement")
            # Preserve the original frozen summary tokens as provenance columns.
            full.update(median_delta=frozen_median, win_rate=frozen_win,
                        original_median_token=old_summary["median_delta_candidate_minus_reference"],
                        original_win_rate_token=old_summary["win_rate"], evaluator_version="v2")
            subset_rows = [r for r in old_rows if r["case_id"] in selected]
            if len(subset_rows) != 61:
                raise ValueError("Frozen selected case coverage mismatch")
            subset = paired_statistics([float(r["delta_candidate_minus_reference"]) for r in subset_rows], spec)
            subset["evaluator_version"] = "v2"
            for version in contract["evaluation"]["versions"]:
                columns = {"Canonical_full_frozen": full, "subset_frozen": subset}
                for chain in ("CAL", "V2S"):
                    differences = []
                    absent = []
                    for case in contract["selection"]["selected_case_ids"]:
                        left = index.get((chain, version, case, definition["candidate_method_id"]))
                        right = index.get((chain, version, case, definition["reference_method_id"]))
                        available = (left is not None and right is not None
                                     and left["evaluation_status"] == right["evaluation_status"] == "COMPLETED"
                                     and left.get(metric) is not None and right.get(metric) is not None)
                        delta = float(left[metric]) - float(right[metric]) if available else None
                        if available and not math.isfinite(delta):
                            raise ValueError("Nonfinite new paired metric")
                        pairs.append({"comparison": name, "metric_name": metric, "evaluator_version": version,
                                      "chain": chain, "case_id": case, "delta_candidate_minus_reference": delta,
                                      "status": "AVAILABLE" if available else "UNAVAILABLE",
                                      "candidate_source_row": left.get("source_row") if left else None,
                                      "reference_source_row": right.get("source_row") if right else None})
                        (differences if available else absent).append(delta if available else case)
                    stat = paired_statistics(differences, spec)
                    stat.update(evaluator_version=version, missing_case_ids=absent)
                    columns["subset_" + chain] = stat
                maintained = strict_same_direction(full, columns["subset_CAL"])
                complete = columns['subset_CAL']['n'] == len(selected)
                classification = ('UNAVAILABLE_INCOMPLETE_PAIRS' if not complete else
                                  'MAINTAINED' if maintained else 'FLIPPED')
                row = {"comparison": name, "metric_name": metric, "new_evaluator_version": version,
                       "frozen_evaluator_version": "v2", "primary_metric": metric in spec["primary_metrics"],
                       "classification": classification}
                for name_column, stat in columns.items():
                    row.update({name_column + "__" + k: v for k, v in stat.items()})
                comparison.append(row)
                if row["primary_metric"] and classification == 'FLIPPED':
                    flips.append({"comparison": name, "metric_name": metric, "evaluator_version": version,
                                  "canonical_median_delta": full["median_delta"], "canonical_win_rate": full["win_rate"],
                                  "CAL_median_delta": columns["subset_CAL"].get("median_delta"),
                                  "CAL_win_rate": columns["subset_CAL"].get("win_rate"),
                                  "median_delta_change": (columns["subset_CAL"]["median_delta"] - full["median_delta"])
                                      if columns["subset_CAL"].get("median_delta") is not None else None})
                if row["primary_metric"]:
                    for chain in ("CAL", "V2S"):
                        absent = columns["subset_" + chain]["missing_case_ids"]
                        if absent:
                            missing.append({"comparison": name, "metric_name": metric, "chain": chain,
                                            "evaluator_version": version, "case_ids": absent})
    destination = stage / "08_AGGREGATE"
    write_csv(destination / "PAIRWISE_FOUR_COLUMN_COMPARISON.csv", comparison)
    write_csv(destination / "PAIRWISE_CASE_LEVEL.csv", pairs)
    write_csv(destination / "PRIMARY_FLIPS.csv", flips)
    decision = {**FLAGS, "data_mode": "real_base_controlled_degradation", "code_commit": code_commit,
                "decision": "HUMAN_DECISION_REQUIRED" if flips or missing else "FULL_MATRIX_RERUN_NOT_REQUIRED",
                "selected_case_count": 61, "excluded_case_count": 480, "NOT_TRANSFERABLE": [],
                "primary_pair_version_count": 60,
                "maintained_primary_pair_version_count": sum(r['primary_metric'] and r['classification'] == 'MAINTAINED' for r in comparison),
                "unavailable_primary_pair_version_count": sum(r['primary_metric'] and r['classification'] == 'UNAVAILABLE_INCOMPLETE_PAIRS' for r in comparison),
                "flip_count": len(flips), "flips": flips, "missing_evidence": missing,
                "full_matrix_rerun_executed": False, "full_matrix_rerun_authorized_automatically": False,
                "frozen_metric_recomputation_performed": False,
                "frozen_solver_rerun_count": 0, "frozen_case_delta_aggregation_only": True,
                "confidence_intervals": "case-paired median bootstrap 10000 resamples, seed260910007, percentile95%",
                "decision_versions": spec["decision_versions"], "rule": spec["decision"]}
    write_json(destination / "DEGRADATION_SUBSET_DECISION.json", decision)
    return comparison, decision
