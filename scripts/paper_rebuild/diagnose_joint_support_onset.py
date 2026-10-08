#!/usr/bin/env python3
"""One source-only onset profile. Authoring this file does not execute it.

Uses only events through one specified actual rebuilt four-foot publication.
No truth, reference, evaluation metadata, error series, noise fit or full-90 run.
The existing finite model still starts with s=0 and stationary random u; this
does not implement continuous-zero-velocity onset or a calibrated change model.
"""
from __future__ import annotations
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def save(path, value):
    path.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False)+"\n")


def source_frontier(root, publication_time):
    """Read an explicitly selected observed publication; not a truth fault time."""
    decisions = json.loads((root/"U3/decisions.json").read_text())
    expansions = [d for d in decisions if d.get("kind") == "NONLINEAR_CONDITIONAL_HISTORY_EXPANDED"]
    csv.field_size_limit(sys.maxsize)
    with (root/"U3/navigation.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            if float(row["time_s"]) < publication_time:
                continue
            if float(row["time_s"]) > publication_time:
                break
            extra = json.loads(row["extra_fields"])
            policy = extra.get("selected_support_policy", {}).get("source_policy", [])
            if not (extra.get("conditional_history_recomputed") is True and len(policy) == 1
                    and policy[0]["mode"] == "finite_common_motion" and len(policy[0]["arc_ids"]) == 4):
                continue
            frontier = float(row["time_s"])
            matches = [d for d in expansions if d["time_s"] <= frontier
                       and d["support_identity"] == extra["selected_support_model"]
                       and d.get("source_policy") == policy]
            if not matches:
                continue
            selected = extra["candidate_local_directions"][int(extra["selected_branch"])]
            return dict(time_s=frontier, checkpoint_time_s=matches[-1]["checkpoint_time_s"],
                first_use_s=matches[-1]["first_use_s"], policy=policy,
                selected_identity=extra["selected_support_model"],
                selected_integer_lineage=selected["integer_lineage"],
                selected_state=selected["conditional_state"],
                selected_score=json.loads(row["candidate_costs"])[int(extra["selected_branch"])],
                expansion=matches[-1])
    raise ValueError("No completed actually published nonlinear four-foot finite history")


def is_ancestor(earlier, later):
    return clean(earlier) == clean(later[:len(earlier)])


def decomposition(records, lineage):
    matching = [r for r in records if is_ancestor(r["integer_lineage"], lineage)
                and r.get("score_accumulations") == 1]
    fields = ("joint_negative_twice_log_density", "external_marginal_negative_twice_log_density",
              "conditional_foot_negative_twice_log_density", "joint_dimension",
              "external_dimension", "conditional_foot_dimension")
    return {name: sum(r.get(name, 0) for r in matching) for name in fields}


def joint_motion_readout(branch, policy, X, V):
    """Native joint marginal, plus its complete world p/v/s/u pushforward."""
    pose = branch.window.values.atPose3(X(branch.index))
    keys = [X(branch.index), V(branch.index)]
    motion = branch.support_motion_states.get(policy[0]["group_id"]) if policy else None
    s, u = np.zeros(3), np.zeros(3)
    kind = "FIXED_EXACT_ZERO_MOTION"
    if motion is not None:
        key = motion["motion_key"]
        if key is None:
            key = motion["initial_velocity_key"]
            u = branch.window.values.atVector(key)
            kind = "BIRTH_EXACT_ZERO_DISPLACEMENT_RANDOM_VELOCITY"
        else:
            state = branch.window.values.atVector(key)
            s, u = state[:3], state[3:]
            kind = "FINITE_DISPLACEMENT_VELOCITY"
        keys.append(key)
    native = branch.joint_covariance(keys)
    mapping = np.zeros((12, native.shape[0]))
    mapping[:3, 3:6] = pose.rotation().matrix()
    mapping[3:6, 6:9] = np.eye(3)
    if kind == "FINITE_DISPLACEMENT_VELOCITY":
        mapping[6:, 9:] = np.eye(6)
    elif motion is not None:
        mapping[9:, 9:] = np.eye(3)
    covariance = mapping @ native @ mapping.T
    vv, uu, vu = covariance[3:6, 3:6], covariance[9:12, 9:12], covariance[3:6, 9:12]
    denominator = np.sqrt(np.outer(np.diag(vv), np.diag(uu)))
    correlation = np.full((3, 3), np.nan)
    np.divide(vu, denominator, out=correlation, where=denominator > 0)
    conditional = vv if motion is None else vv-vu @ np.linalg.solve(uu, vu.T)
    return dict(motion_semantics=kind, motion_birth_time_s=None if motion is None else motion["birth_time_s"],
        motion_state_time_s=None if motion is None else motion["time_s"],
        p_ned_m=pose.translation(), v_ned_mps=branch.window.values.atVector(V(branch.index)),
        s_ned_m=s, u_ned_mps=u,
        native_key_order=[int(k) for k in keys],
        native_coordinate_order="pose tangent [rotation,body translation], world v, then motion [s,u] or birth u",
        native_joint_covariance=native, world_coordinate_order=["p_NED","v_NED","s_NED","u_NED"],
        world_joint_covariance=covariance, covariance_v_u=vu, correlation_v_u=correlation,
        covariance_v_minus_u=vv+uu-vu-vu.T, covariance_v_conditioned_on_u=conditional,
        correlation_null_means="undefined because a fixed motion coordinate has zero variance")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--automatic-root", type=Path, required=True)
    parser.add_argument("--publication-time", type=float, required=True,
                        help="Actual emitted policy-selection time chosen for diagnosis, not a fault onset")
    parser.add_argument("--output-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    status = json.loads((args.automatic_root/"run_status.json").read_text())
    if status.get("status") != "COMPLETED" or "U3" not in status.get("completed_modes", []):
        raise ValueError("This diagnostic requires the completed original automatic result")
    target = source_frontier(args.automatic_root, args.publication_time)
    metadata = json.loads((args.automatic_root/"sensor_metadata.json").read_text())
    if metadata["support_motion_model"] != {"velocity_sigma_mps": .075, "tau_s": 100.}:
        raise ValueError("This one diagnostic retains the declared original sigma=.075, tau=100")
    if metadata["support_prediction"] != "foot_external":
        raise ValueError("This diagnostic compares the same proper foot/external rows")
    args.output_root.mkdir(parents=True, exist_ok=True)
    status_path = args.output_root/"diagnostic_status.json"
    # A single user-authorized execution; do not silently restart or overwrite it.
    with status_path.open("x") as stream:
        json.dump(dict(status="STARTING", scope="ONE_SOURCE_ONSET_PROFILE_NOT_NAVIGATION_VALIDATION"), stream)

    sys.path.insert(0, str(args.repository/"src"))
    import legsa_gins.paper_rebuild.joint_navigation as package
    package.__path__ = [str(args.automatic_root/"SOURCE_SNAPSHOT/src/legsa_gins/paper_rebuild/joint_navigation")]
    from legsa_gins.paper_rebuild.joint_navigation.navigator import JointNavigator
    from legsa_gins.paper_rebuild.joint_navigation.synthetic import generate_scene
    from legsa_gins.paper_rebuild.joint_navigation.support_policy import canonical_policy, policy_readout
    from gtsam.symbol_shorthand import X, V

    started = time.monotonic()
    report = dict(status="RUNNING", source_scope="ORIGINAL_OBSERVATIONS_THROUGH_SPECIFIED_ACTUAL_FOUR_FOOT_PUBLICATION",
        original_automatic_root=str(args.automatic_root), frontier=target,
        unchanged_support_motion_model=metadata["support_motion_model"],
        no_truth_reference_or_error_reads=True, no_navigation_after_frontier=True,
        source_module_scope="ORIGINAL_AUTOMATIC_SOURCE_SNAPSHOT",
        diagnostic_not_calibrated_probability=True, formal_online_score_claim=False,
        onset_prior=None, onset_ranking="UNPENALIZED_SOURCE_PROFILE_NOT_POSTERIOR_OR_ONLINE_ACCEPTANCE",
        onset_birth_semantics="Existing effective_from: s=0 and stationary u prior at first active foot event; velocity jump remains permitted",
        results=[])
    try:
        # The generator constructs observations; its separate truth/evaluation
        # products are never read or passed to any estimator or ranking.
        generated = generate_scene(duration_s=target["time_s"], seed=status["seed"],
            key_dt=metadata["key_dt_s"], imu_dt=metadata["imu_max_dt_s"])
        events = generated["events"]
        del generated
        with (args.automatic_root/"input_timeline.csv").open(newline="") as stream:
            original_times = [float(r["time_s"]) for r in csv.DictReader(stream)
                              if float(r["time_s"]) <= target["time_s"]]
        if original_times != [e["time_s"] for e in events]:
            raise ValueError("Regenerated prefix event times differ from the saved original timeline")
        origin_time = target["checkpoint_time_s"]
        prefix = [e for e in events if e["time_s"] <= origin_time]
        print(f"One fixed U3 prefix: 0 through {origin_time:g} s", flush=True)
        fixed = JointNavigator(metadata, mode="U3", monitor_support=False)
        prefix_result = fixed.run(prefix)
        origin = next(c for c in fixed.checkpoints if c.time_s == origin_time)
        if origin.index != len(prefix)-1:
            raise ValueError("Saved origin is not the exact end of the one fixed prefix")
        tail = [(i, e) for i, e in enumerate(events) if i > origin.index]
        arcs = set(target["policy"][0]["arc_ids"])
        first_use = min(e["time_s"] for e in events
                        if any(f["arc_id"] in arcs for f in e.get("feet", [])))
        candidates = sorted({e["time_s"] for _, e in tail
            if e["time_s"] > first_use and any(f["arc_id"] in arcs for f in e.get("feet", []))})
        base_policy = [{**p, "effective_from": -math.inf if p["effective_from"] is None else p["effective_from"]}
                       for p in target["policy"]]
        hypotheses = [("H0_FIXED", []), ("ORIGINAL_WHOLE_ARC_FINITE", list(canonical_policy(base_policy)))]
        hypotheses += [(f"ONSET_{tc:.10g}", list(canonical_policy(
            [{**p, "effective_from": tc} for p in base_policy]))) for tc in candidates]
        report.update(prefix_event_count=len(prefix), tail_event_count=len(tail), prefix_run_count=1,
            checkpoint_index=origin.index, checkpoint_time_s=origin.time_s,
            first_observed_target_arc_s=first_use, candidate_onsets_s=candidates,
            candidate_rule="All original target-group member observation boundaries after first arc use and no later than the specified publication",
            excluded_birth_duplicate_s=first_use, prefix_output_state=prefix_result["rows"][-1],
            hypothesis_count=len(hypotheses))
        prefix_blocks = [block for row in prefix_result["rows"] for block in row["background_predictive_blocks"]]
        expected_rows = {}
        expected_fingerprint = None
        for number, (name, policy) in enumerate(hypotheses):
            print(f"{number+1}/{len(hypotheses)} {name}: same checkpoint through {target['time_s']:g} s", flush=True)
            nav = JointNavigator(metadata, mode="U3", monitor_support=False, support_models=policy)
            nav._restore(origin)
            nav.events = [(i, e) for i, e in enumerate(prefix)]
            event_scores, tail_blocks = [], []
            for index, event in tail:
                # Never call run(tail): it would restart global event indexes.
                nav.events.append((index, event))
                packet = nav._filter(event)
                rows, _ = nav._advance(packet, index, None if name == "H0_FIXED" else expected_rows[index])
                if name == "H0_FIXED":
                    expected_rows[index] = rows
                blocks = copy.deepcopy(nav.last_prediction_blocks)
                tail_blocks.extend(blocks)
                event_scores.append(dict(index=index, time_s=event["time_s"], row_ids=rows, blocks=blocks))
            if name == "H0_FIXED":
                expected_fingerprint = nav.predictive_rows_fingerprint
            if nav.predictive_rows_fingerprint != expected_fingerprint:
                raise ValueError("A conditional interpretation scored different physical rows")
            branches = []
            for branch in nav.branches:
                total_parts = decomposition(prefix_blocks+tail_blocks, branch.integer_lineage)
                tail_parts = decomposition(tail_blocks, branch.integer_lineage)
                ancestors = [s.state for s in origin.branches if is_ancestor(s.state["integer_lineage"], branch.integer_lineage)]
                if len(ancestors) != 1:
                    raise ValueError("Current integer lineage has no unique common-checkpoint ancestor")
                prefix_score = ancestors[0]["predictive_score"]
                branches.append(dict(integer_lineage=branch.integer_lineage, fixed_integer_by_label=branch.fixed,
                    total_normalized_predictive_score=branch.predictive_score,
                    common_prefix_predictive_score=prefix_score,
                    tail_predictive_score=branch.predictive_score-prefix_score,
                    total_density_decomposition=total_parts, tail_density_decomposition=tail_parts,
                    decomposition_minus_recorded_total=total_parts["joint_negative_twice_log_density"]-branch.predictive_score,
                    predictive_row_count=branch.predictive_row_count, predictive_frontier=branch.predictive_frontier,
                    state=branch.current_output(), joint=joint_motion_readout(branch, policy, X, V)))
            best = min(range(len(branches)), key=lambda j: branches[j]["total_normalized_predictive_score"])
            result = dict(name=name, source_policy=policy_readout(policy), branches=branches,
                best_branch_index=best, best_source_score=branches[best]["total_normalized_predictive_score"],
                predictive_rows_fingerprint=nav.predictive_rows_fingerprint,
                raw_proposal_complete=nav.proposal_complete, raw_support_incomplete=nav.support_incomplete,
                endpoint_onset_has_no_following_motion_observation=bool(policy and policy[0]["effective_from"] == target["time_s"]),
                event_scores=event_scores)
            if name == "ORIGINAL_WHOLE_ARC_FINITE":
                matched = [b for b in branches if clean(b["integer_lineage"]) == target["selected_integer_lineage"]]
                if len(matched) == 1:
                    branch = matched[0]
                    deltas = {key: np.asarray(branch["state"][key])-np.asarray(target["selected_state"][key])
                              for key in ("p", "v", "rpy_rad", "bias")}
                    deltas["rpy_rad"] = (deltas["rpy_rad"]+np.pi)%(2*np.pi)-np.pi
                    score_delta = branch["total_normalized_predictive_score"]-target["selected_score"]
                    same = max(np.max(np.abs(v)) for v in deltas.values()) <= 1e-8 and abs(score_delta) <= 1e-6
                    report["original_automatic_consistency"] = dict(
                        status="NUMERICALLY_MATCHED" if same else "DIFFERENT_CONDITIONAL_RECONSTRUCTION",
                        reconstructed_minus_saved_state=deltas, reconstructed_minus_saved_score=score_delta,
                        tolerance_role="Reproduction readout only, not a scientific acceptance threshold",
                        state_absolute_tolerance=1e-8, score_absolute_tolerance=1e-6,
                        interpretation=("Same saved policy and integer lineage reproduced from the one fixed prefix"
                            if same else "Do not treat this profile as a reproduction of the original accepted branch. Compare its saved origin/prefix, inherited integer history and nonlinear source chart before attributing navigation failure to onset. No discrepancy is repaired by this script."))
                else:
                    report["original_automatic_consistency"] = dict(status="SAVED_INTEGER_LINEAGE_NOT_UNIQUELY_REPRODUCED",
                        interpretation="Different conditional lineage; no equivalence or mechanism attribution claim")
            report["results"].append(result)
            save(args.output_root/"ONSET_SOURCE_PROFILE.json", report)
            save(status_path, dict(status="RUNNING", completed_hypotheses=len(report["results"]),
                hypothesis_count=len(hypotheses), last_completed=name, elapsed_s=time.monotonic()-started))
        ranking = sorted(report["results"], key=lambda r:r["best_source_score"])
        minimum = ranking[0]["best_source_score"]
        report["source_profile_ranking"] = [dict(name=r["name"], source_policy=r["source_policy"],
            source_score=r["best_source_score"], score_above_minimum=r["best_source_score"]-minimum)
            for r in ranking]
        report.update(status="COMPLETED_SOURCE_ONSET_DIAGNOSTIC", elapsed_s=time.monotonic()-started,
            scientific_interpretation="Locates conditional source-fit and v/u-confounding changes only. Unpenalized onset search is not a calibrated probability, causal online acceptance or navigation gain; retained birth u prior does not enforce continuous zero-velocity onset.")
        save(args.output_root/"ONSET_SOURCE_PROFILE.json", report)
        save(status_path, dict(status=report["status"], completed_hypotheses=len(report["results"]),
            elapsed_s=report["elapsed_s"], original_automatic_consistency=report.get("original_automatic_consistency")))
        print(json.dumps(clean(dict(status=report["status"], ranking=report["source_profile_ranking"],
            original_automatic_consistency=report.get("original_automatic_consistency")))), flush=True)
    except BaseException as error:
        save(status_path, dict(status="FAILED", error_type=type(error).__name__, error=str(error),
            completed_hypotheses=len(report["results"]), elapsed_s=time.monotonic()-started))
        raise


if __name__ == "__main__":
    main()

