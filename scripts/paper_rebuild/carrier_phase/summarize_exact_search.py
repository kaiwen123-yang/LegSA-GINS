#!/usr/bin/env python3
"""Summarize registered paired benchmarks without treating timeouts as runtimes."""
from pathlib import Path
import argparse
import csv
import json
import math
import statistics


def close(a, b):
    return abs(a-b) <= 2e-6 + 2e-8*max(abs(a), abs(b))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((args.benchmark/"PLAN.json").read_text())
    terminal = json.loads((args.benchmark/"COMPLETE.json").read_text())
    if terminal["actual_search_calls"] != 2*len(plan["cases"]):
        raise ValueError("benchmark is incomplete")
    rows = []
    certified_pairs = []
    for i, case in enumerate(plan["cases"]):
        base_name = f"{i:02d}_cap{case['cap']}_{case['start']:03d}"
        a, b = [json.loads((args.benchmark/(base_name+"_"+v+".json")).read_text())
                for v in ("baseline", "optimized")]
        for field in ("selection", "all_labels", "limits", "model_plan_sha256"):
            if a[field] != b[field]:
                raise ValueError(f"{base_name}: input/selection mismatch: {field}")
        ac, bc = a["certificate"], b["certificate"]
        both = ac["global_optimum_certified"] and bc["global_optimum_certified"]
        equality = "NOT_COMPARABLE_UNCERTIFIED"
        max_cost_diff = None
        if both:
            differences = []
            # This strict checker does not quietly excuse integer differences as
            # ties. Such a case requires a separate explicit mathematical review.
            for key in ("best", "second"):
                if a[key]["ambiguity"] != b[key]["ambiguity"]:
                    raise ValueError(f"{base_name}: certified {key} integer disagreement")
                for cost in ("reduced_cost", "full_residual_cost"):
                    if not close(a[key][cost], b[key][cost]):
                        raise ValueError(f"{base_name}: certified {key} cost disagreement")
                    differences.append(abs(a[key][cost]-b[key][cost]))
                for av, bv in zip(a[key]["baselines"], b[key]["baselines"]):
                    if max(abs(x-y) for x, y in zip(av, bv)) > 1e-8:
                        raise ValueError(f"{base_name}: certified baseline disagreement")
            equality = "PASS_SAME_TWO_FULL_INTEGER_VECTORS_AND_OBJECTIVE"
            max_cost_diff = max(differences)
            certified_pairs.append(a["whole_solve_elapsed_s"]/b["whole_solve_elapsed_s"])
        rows.append({
            "cap": case["cap"], "window_start_s": case["start"],
            "baseline_certified": ac["global_optimum_certified"],
            "optimized_certified": bc["global_optimum_certified"],
            "baseline_termination": ac["termination_reason"],
            "optimized_termination": bc["termination_reason"],
            "baseline_whole_solve_s": a["whole_solve_elapsed_s"],
            "optimized_whole_solve_s": b["whole_solve_elapsed_s"],
            "paired_speedup_if_both_certified": certified_pairs[-1] if both else None,
            "certified_result_comparison": equality, "max_objective_difference": max_cost_diff,
            "baseline_expanded_nodes": ac["expanded_nodes"],
            "optimized_expanded_nodes": bc["expanded_nodes"],
            "optimized_bound_evaluations": bc["bound_evaluations"],
            "optimized_cheap_prunes": bc["cheap_bound_prunes"],
            "optimized_bound_sphere_evaluations": bc["bound_sphere_evaluations"],
            "optimized_candidate_sphere_evaluations": bc["candidate_sphere_evaluations"],
            "optimized_sphere_metric_factorizations": bc["sphere_metric_factorizations"]})
    summary = {
        "status": "PASS_PAIRED_BENCHMARK_NO_CERTIFIED_RESULT_DISAGREEMENT",
        "cases": len(rows), "search_calls": terminal["actual_search_calls"],
        "both_certified_pairs": len(certified_pairs),
        "median_speedup_on_both_certified_sample": statistics.median(certified_pairs) if certified_pairs else None,
        "baseline_certified": sum(row["baseline_certified"] for row in rows),
        "optimized_certified": sum(row["optimized_certified"] for row in rows),
        "reference_reads": 0, "native_navigation_runs": 0,
        "representative_population_benchmark": False,
        "real_time_qualified": False,
        "runtime_interpretation": "one paired observation per selected development problem; timeouts censored",
        "execution": json.loads((args.benchmark/"EXECUTION.json").read_text())}
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/"EXACT_SEARCH_CACHE_RESULTS.csv").open("x", newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    (args.output/"EXACT_SEARCH_CACHE_SUMMARY.json").write_text(json.dumps(summary,indent=2)+"\n")
    lines=["# Exact-search factor caching: paired real-input benchmark", "",
        f"All {len(rows)} registered problems and {terminal['actual_search_calls']} searches completed. "
        f"Both versions certify {len(certified_pairs)} paired problems; all such pairs preserve the same "
        "two full integer vectors, constrained baselines and objective within the registered tolerance.",
        "", "| Cap | Start s | Baseline s | Cached s | Certificates old/new | Speedup when both certified |",
        "|---|---:|---:|---:|---|---:|"]
    for row in rows:
        speed=row["paired_speedup_if_both_certified"]
        speed_text="NA (censored)" if speed is None else f"{speed:.3f}"
        lines.append(f"| {row['cap']} | {row['window_start_s']} | {row['baseline_whole_solve_s']:.6f} | "
            f"{row['optimized_whole_solve_s']:.6f} | {row['baseline_certified']}/{row['optimized_certified']} | {speed_text} |")
    lines += ["",
        f"Median paired speedup among the {len(certified_pairs)} jointly certified selected problems: "
        f"{summary['median_speedup_on_both_certified_sample']:.3f}. "
        "This is a small diagnostic sample with one execution per version and case, not a general throughput estimate.",
        "", "Same 100000-node/30-second limits, sequential single-thread numerical libraries, alternating order. "
        "Timeouts remain censored and have no measured completion-speed ratio. Solver setup and factor construction "
        "are included in whole-solve time. No admission, tracking, navigation or reference evaluation ran here.",
        "", "The optimization changes factor reuse and preprunes nodes already rejected by a term of the original bound. "
        "It does not alter the integer objective, selected subset, noise, validation gates or certificate requirement. "
        "Speed alone does not establish online acquisition availability; preparation, scheduling and delayed-candidate handling remain separate.", ""]
    (args.output/"EXACT_SEARCH_CACHE_READOUT.md").write_text("\n".join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k!="execution"}))


if __name__ == "__main__":
    main()
