#!/usr/bin/env python3
"""Reproduce one read-only raw geometry diagnostic; no navigation or scene edits."""
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repository", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.repository / "src"))

from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene
from legsa_gins.paper_rebuild.joint_navigation.candidate import propose_candidates
from legsa_gins.paper_rebuild.carrier_phase.temporal import EpochBlock, assemble_epochs

# This is the unchanged existing generator. Truth is used only below for a
# conditional geometry diagnostic, never supplied to candidate enumeration.
scene = generate_scene(duration_s=26.0, seed=6100801)
original = [e["carrier"] for e in scene["events"]
            if e["carrier"] is not None and 25.0-1e-9 <= e["time_s"] <= 25.8+1e-9]
evaluation = {r["time_s"]: r for r in scene["truth"]}
body_baseline = scene["metadata"]["baseline_body"]
output = {
    "scope": "One existing dynamic-scene raw geometry diagnostic, not a new constant-speed scene or navigation result",
    "scene": {"duration_s": 26.0, "seed": 6100801, "event_window_s": [25.0, 25.8]},
    "navigation_runs": 0,
    "scene_modified": False,
    "reference_reads": 0,
    "evaluation_truth_used": True,
    "ideal_attitude_scope": "R_eval is used only after raw enumeration to condition on ideal gravity tilt AND ideal relative attitude; never an online source or candidate seed",
    "rotation_family": "R_k(delta)=Rz(delta)*R_eval_k; delta=0 is the original generator trajectory, not absolute yaw zero",
    "absolute_yaw_at_first_epoch_deg": math.degrees(math.atan2(
        evaluation[original[0].time_s]["R"][1, 0], evaluation[original[0].time_s]["R"][0, 0])),
    "physical_limit": "Existing dynamic segment has horizontal acceleration. This result does not establish GNSS/IMU observational equivalence for its alternative yaw, nor the future constant-speed scene.",
    "gnss_lever_scope": "Current synthetic events/metadata specify no antenna lever; branch defaults both levers to zero. A nonzero rotating lever needs p_body=p_A-R*l_p and v_body=v_A-R*((omega-b_g) cross l_v), plus IMU consistency.",
    "angle_solver": {
        "method": "Exact degree-two trigonometric objective; quartic real roots in tan(delta/2), plus circle seam",
        "yaw_grid_used": False,
        "imaginary_root_acceptance_tolerance": 1e-8,
        "numeric_scope": "Double-precision polynomial roots, not rigorous interval arithmetic",
        "endpoint_method": "Roots of cost(delta)-original expanded threshold; midpoint determines each arc membership",
    },
    "cases": [],
}

for phase_count in (2, 1):
    blocks = []
    retained_rows = np.r_[np.arange(5), 5+np.arange(phase_count)]
    retained_columns = np.arange(phase_count)
    for block in original:
        # Removing a measurement uses its marginal covariance principal
        # submatrix, never a conditional Schur complement. All five code rows,
        # including their shared-pivot cross covariance, remain unchanged.
        blocks.append(EpochBlock(
            block.time_s, block.y[retained_rows],
            block.A[np.ix_(retained_rows, retained_columns)],
            block.B[retained_rows], block.Q[np.ix_(retained_rows, retained_rows)],
            block.ambiguity_labels[:phase_count],
            dict(block.metadata, phase_dd_indices=list(range(phase_count)))))
    problem = assemble_epochs(blocks, length_m=np.linalg.norm(body_baseline))
    proposal = propose_candidates(blocks, body_baseline, max_active=1024)
    lower = np.linalg.cholesky(problem.Q)
    vectors = np.array([evaluation[b.time_s]["R"] @ body_baseline for b in blocks])
    cos_vectors = vectors.copy()
    cos_vectors[:, 2] = 0.0
    sin_vectors = np.column_stack((-vectors[:, 1], vectors[:, 0], np.zeros(len(vectors))))
    constant_vectors = np.column_stack((np.zeros(len(vectors)), np.zeros(len(vectors)), vectors[:, 2]))
    x = np.linalg.solve(lower, problem.B @ cos_vectors.ravel())
    y = np.linalg.solve(lower, problem.B @ sin_vectors.ravel())
    threshold = proposal.metadata["expanded_working_threshold"]
    results = []
    for candidate in (*proposal.active, *proposal.dormant):
        integers = np.array([candidate.integer_by_label[k] for k in problem.ambiguity_labels])
        z = np.linalg.solve(lower, problem.y-problem.A @ integers-problem.B @ constant_vectors.ravel())
        a0 = float(z @ z + 0.5*(x @ x + y @ y))
        a1, b1 = float(-2*z @ x), float(-2*z @ y)
        a2, b2 = float(0.5*(x @ x-y @ y)), float(x @ y)

        def cost(delta):
            return float(a0+a1*np.cos(delta)+b1*np.sin(delta)
                         +a2*np.cos(2*delta)+b2*np.sin(2*delta))

        derivative_roots = np.roots([
            -b1+2*b2, -2*a1+8*a2, -12*b2, -2*a1-8*a2, b1+2*b2])
        critical = [-math.pi]+[2*math.atan(float(t.real)) for t in derivative_roots if abs(t.imag) < 1e-8]
        minimum_cost, minimum_yaw = min((cost(t), t) for t in critical)
        c0 = a0-threshold
        boundary_roots = np.roots([
            c0-a1+a2, 2*b1-4*b2, 2*c0-6*a2, 2*b1+4*b2, c0+a1+a2])
        finite_edges = [2*math.atan(float(t.real)) for t in boundary_roots if abs(t.imag) < 1e-8]
        edges = sorted([-math.pi, math.pi]+finite_edges)
        intervals = [[math.degrees(lo), math.degrees(hi)]
                     for lo, hi in zip(edges[:-1], edges[1:]) if cost((lo+hi)/2) <= threshold]
        results.append({
            "integer_by_label": candidate.integer_by_label,
            "raw_sphere_profile_cost": candidate.raw_cost,
            "same_tilt_relative_attitude_minimum_cost": minimum_cost,
            "minimum_yaw_offset_deg": math.degrees(minimum_yaw),
            "accepted_yaw_offset_intervals_deg": intervals,
            "maximum_finite_endpoint_cost_error": max(
                [abs(cost(t)-threshold) for t in finite_edges], default=0.0),
        })
    fields = ("status", "termination_reason", "enumeration_complete", "length_support_complete",
              "active_support_complete", "enumerated_count", "length_qualified_count",
              "active_count", "dormant_count", "expanded_nodes", "integer_leaves", "elapsed_s",
              "node_limit", "candidate_limit", "timeout_s", "raw_cost_threshold",
              "expanded_working_threshold", "raw_working_quantile", "threshold_degrees_of_freedom")
    output["cases"].append({
        "phase_count": phase_count,
        "times_s": [b.time_s for b in blocks],
        "original_row_indices_zero_based": retained_rows.tolist(),
        "original_ambiguity_column_indices_zero_based": retained_columns.tolist(),
        "ambiguity_labels": list(problem.ambiguity_labels),
        "integer_continuity": "assemble_epochs shares one integer column per identical physical arc label across all five epochs",
        "threshold_scope": "Unchanged candidate.py chi2.ppf(RAW_WORKING_QUANTILE=0.999, number of retained raw rows), including its original numeric guard; not calibrated false-fix probability",
        "proposal_metadata": {k: proposal.metadata[k] for k in fields},
        "all_length_feasible_candidates": results,
    })

args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))

