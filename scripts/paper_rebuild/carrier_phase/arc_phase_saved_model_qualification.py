#!/usr/bin/env python3
"""One registered full-denominator audit of saved phase models, not navigation.

Only prepared NPZ/JSON and old singleton valid flags are read. No raw UBX,
reference, integer solver, attitude estimate or output-based block selection.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import csv
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"src"))
import numpy as np

from legsa_gins.paper_rebuild.carrier_phase.arc_relations import SdArcNode, DdArcRelation
from legsa_gins.paper_rebuild.carrier_phase.arc_phase_difference import (
    PhaseEpoch, PhaseArcContinuity, build_phase_contrast_geometry,
    unknown_cross_difference_bound,
)
from legsa_gins.paper_rebuild.carrier_phase.multignss import signal_spec, raw

FAMILY = "GPS_GAL_BDS_DUAL"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_phase_saved_model_qualification.py"
SCHEMA = "arc_phase_saved_model_qualification/v1"
STATUS = "FROZEN_AWAITING_REGISTERED_SINGLE_EXECUTION"
STAGES = dict(prepared="FULL_WINDOW_PREPARE_ATTEMPT02",
              singleton="FULL_WINDOW_FRONTEND_ATTEMPT01",
              out="ARC_PHASE_SAVED_MODEL_ATTEMPT01")
SEQUENCES = (("BY2", [66, 340], 1370, 274),
             ("BY2H", [413, 683], 1350, 270),
             ("BY2O", [3186, 3563], 1885, 377))
BUDGETS = dict(fixed_blocks=921, block_length=5, endpoint_npz_reads=1842,
               saved_plan_reads=3, saved_seal_reads=3, saved_arc_metadata_reads=3,
               singleton_valid_table_reads=3, geometry_contrast_calls=921,
               conditional_bound_calls=921, saved_metadata_bytes=500_000_000,
               endpoint_npz_bytes=100_000_000, wall_s=600)


def imported_local_sources():
    paths = {SCRIPT}
    for module in tuple(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file:
            path = Path(file).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py":
                paths.add(path.relative_to(ROOT).as_posix())
    return paths


def validate_plan_and_locations(args, plan):
    require(plan["schema"] == SCHEMA and plan["status"] == STATUS,
            "unregistered plan schema/status")
    require(plan["family"] == FAMILY and plan["block_length"] == 5
            and plan["endpoint_indices_in_block"] == [0, 4], "fixed contrast family/block")
    require(plan["stage_aliases"] == STAGES and plan["budgets"] == BUDGETS,
            "fixed stage/budget contract changed")
    specs = [(s["sequence"], s["window_s"], s["epochs"], s["blocks"])
             for s in plan["sequences"]]
    require(specs == list(SEQUENCES), "fixed original three windows/denominator")
    # Derive from checkout layout, never accept another stage to erase an attempt.
    scratch = ROOT.parent.parent/"LegSA-GINS-SCRATCH"
    for key, alias in STAGES.items():
        round_dir = "TRUSTED_HEADING_CONTINUATION_20261007" if key == "out" else "TRUSTED_HEADING_20261006"
        require(getattr(args, key).resolve() == (scratch/round_dir/alias).resolve(),
                "registered "+key+" stage identity")
    require(imported_local_sources() <= set(plan["source_pins"]),
            "imported local dependency missing from source pins")


def check_read_budgets(counts):
    for key, maximum in BUDGETS.items():
        if key not in ("fixed_blocks", "block_length", "wall_s"):
            require(counts[key] <= maximum, "registered read/call budget exceeded: "+key)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def emit(path, value):
    path.write_text(json.dumps(value, indent=2, default=json_default)+"\n")


def read_pinned(path, expected_sha):
    data = path.read_bytes()
    require(sha(data) == expected_sha, "saved input identity mismatch: "+str(path.name))
    return data


def read_plan_and_seal(prepared, spec, counts):
    seq = prepared/spec["sequence"]
    seal = json.loads(read_pinned(seq/"MODEL_OUTPUT_SEAL.json", spec["seal_sha256"]))
    counts["saved_seal_reads"] += 1
    require(seal["complete_preparation"] is True, "incomplete original preparation")
    payload = read_pinned(seq/"MODELS/PLAN.json", spec["plan_sha256"])
    counts["saved_plan_reads"] += 1
    counts["saved_metadata_bytes"] += len(payload)
    check_read_budgets(counts)
    saved = json.loads(payload)
    require(saved["sequence"] == spec["sequence"] and saved["window_s"] == spec["window_s"],
            "original window identity")
    require(len(saved["records"]) == spec["epochs"] and len(saved["records"]) % 5 == 0,
            "original full denominator")
    require(saved["cross_epoch_covariance"] == "assumed independent",
            "cross-time declaration changed; explicit new review required")
    return seq/"MODELS", saved, seal


def read_arc_histories(model_dir, seal, counts):
    payload = read_pinned(model_dir/"ARC_EVENTS.json", seal["files"]["ARC_EVENTS.json"]["sha256"])
    counts["saved_arc_metadata_reads"] += 1
    counts["saved_metadata_bytes"] += len(payload)
    check_read_budgets(counts)
    events = json.loads(payload)
    histories = defaultdict(list)
    for e in events:
        key = (int(e["rx"]), e["signal"])
        histories[key].append((
            float(e["time_s"]), e["arc_token"], bool(e["eligible"]),
            bool(e["continued"]), bool(e["metadata_continuous"]),
            bool(e["temporal_link_qualified"]), tuple(e["reasons"])))
    counts["arc_event_records"] += len(events)
    del events, payload
    result = {}
    for key, values in histories.items():
        ts = [e[0] for e in values]
        require(all(b > a for a, b in zip(ts, ts[1:])),
                "nonmonotone/duplicate physical arc event")
        result[key] = (ts, values)
    return result


def continuous_nodes(nodes, block_times, histories, max_gap_s):
    """Inspect every saved per-receiver event, including unpaired intermediate ones."""
    t0, t1 = block_times[0], block_times[-1]
    kept, rejected = [], {}
    for n in sorted(nodes):
        tokens = json.loads(n.arc)
        require(isinstance(tokens, list) and len(tokens) == 2,
                "SD arc must bind exactly two receiver tokens")
        reasons = set()
        for rx, token in zip((1, 2), tokens):
            require(isinstance(token, str) and token.startswith(f"{rx}|{n.signal}|arc="),
                    "SD token receiver/signal mismatch")
            ts, events = histories.get((rx, n.signal), ([], []))
            lo, hi = bisect_left(ts, t0), bisect_right(ts, t1)
            selected = events[lo:hi]
            if not selected or selected[0][0] != t0 or selected[-1][0] != t1:
                reasons.add("MISSING_ENDPOINT_ARC_EVENT")
                continue
            if not set(block_times).issubset({e[0] for e in selected}):
                reasons.add("MISSING_INTERMEDIATE_PAIRED_EVENT")
            if any(b[0]-a[0] > max_gap_s for a, b in zip(selected, selected[1:])):
                reasons.add("ORIGINAL_ARC_MAX_GAP_EXCEEDED")
            for event in selected:
                t, current_token, eligible, continued, metadata_ok, temporal_ok, raw_reasons = event
                if current_token != token:
                    reasons.add("PHYSICAL_TOKEN_CHANGED")
                if not eligible:
                    reasons.add("PHASE_INELIGIBLE")
                # The start sample may be the first observation of this arc.
                # Every subsequent link must be qualified over the whole interval.
                if t > t0 and not (continued and metadata_ok and temporal_ok):
                    reasons.add("INTERVAL_LINK_UNQUALIFIED")
                    reasons.update("SAVED_"+r for r in raw_reasons)
        if reasons:
            rejected[n] = tuple(sorted(reasons))
        else:
            kept.append(n)
    return tuple(kept), rejected


def load_phase_epoch(model_dir, rec, seal, saved, sequence, counts):
    entry = rec["families"].get(FAMILY, {})
    require(entry.get("status") == "BUILT", "endpoint model unavailable")
    name = entry["file"]
    require(Path(name).name == name and name.endswith(".npz"), "unsafe model path")
    payload = read_pinned(model_dir/name, seal["files"][name]["sha256"])
    counts["endpoint_npz_reads"] += 1
    counts["endpoint_npz_bytes"] += len(payload)
    check_read_budgets(counts)
    with np.load(io.BytesIO(payload), allow_pickle=False) as z:
        require(set(z.files) == {"y", "A", "B", "Q"}, "unexpected saved array fields")
        y, a, b, q = (z[k] for k in ("y", "A", "B", "Q"))
    labels = tuple(entry["ambiguity_labels"])
    m = len(labels)
    require(y.shape == (2*m,) and a.shape == (2*m, m)
            and b.shape == (2*m, 3) and q.shape == (2*m, 2*m), "saved row dimensions")
    require(all(np.isfinite(v).all() for v in (y, a, b, q)), "nonfinite saved arrays")
    require(entry["rows"] == 2*m and entry["ambiguities"] == m, "row metadata mismatch")
    meta = entry["metadata"]
    require(meta["receiver_order"] == "GNSS2_MINUS_GNSS1"
            and meta["baseline_frame"] == "ECEF"
            and meta["dd_sign"] == "SATELLITE_MINUS_PIVOT"
            and meta["arc_label_policy"] == "EXPLICIT_SD_ARCS", "phase source convention")
    require(meta["phase_policy"] == "CPMES_AS_REPORTED_NO_SECOND_HALF_CYCLE_SHIFT",
            "phase half-cycle convention")
    require(meta["covariance_policy"] == "INDEPENDENT_RAW_SD_WORKING_MODEL",
            "endpoint Q working policy changed")
    require(meta["timing_policy"] == "EXACT_RECEIVER_TAG_PAIR_NOT_PHYSICAL_SYNC_CALIBRATION",
            "time semantics changed")
    relations = tuple(DdArcRelation.from_label(label) for label in labels)
    wave = np.array([signal_spec(raw.SignalIdentity(
        *(int(x) for x in e.target.signal.split(":")))).wavelength_m for e in relations])
    require(np.array_equal(a[:m], np.zeros((m, m)))
            and np.array_equal(a[m:], np.diag(wave)), "saved integer/phase row contract")
    require(np.array_equal(b[:m], b[m:]), "code/phase geometry-row contract")
    require(rec["navigation"]["causal_cutoff_relative_s"] <= rec["time_s"],
            "future navigation prefix")
    require(rec["anchor_decision"]["available"]
            and rec["anchor_decision"]["source_time_s"] <= rec["time_s"], "future/unavailable anchor")
    # y already has the known-SD geometric correction subtracted in preparation.
    # No second correction, new SPP, changed geometry or resampling is performed.
    key = json.dumps(rec["key"], separators=(",", ":"))
    return PhaseEpoch(
        float(rec["time_s"]), None, sequence+":RAWX:"+key,
        sequence+":"+name+":"+seal["files"][name]["sha256"],
        sequence+":RX1_RIGHT_RX2_LEFT", sequence+":GPS_WEEK_TOW__SAVED_LOCAL_BASE",
        "CPMETRES_CORRECTED_KNOWN_SD__RX2_RX1__TARGET_PIVOT",
        sequence+":SAVED_OWN_TRANSMIT_GEOMETRY:"+name,
        sequence+":RAWX_SD_WORKING_Q:"+name,
        relations, y[m:], b[m:], q[m:, m:])


def matrix_rank_detail(a):
    singular = np.linalg.svd(a, compute_uv=False)
    tol = max(a.shape, default=0)*np.finfo(float).eps*(float(singular[0]) if len(singular) else 0.)
    return int(np.count_nonzero(singular > tol)), singular.tolist(), tol


def self_check():
    n = SdArcNode("0:1:0:0", '["1|0:1:0:0|arc=1","2|0:1:0:0|arc=1"]')
    ts = [0., .2, .4, .6, .8]
    histories = {}
    for rx in (1, 2):
        token = f"{rx}|0:1:0:0|arc=1"
        histories[(rx, n.signal)] = (ts, [
            (t, token, True, t > 0, t > 0, t > 0,
             ("FIRST_OBSERVATION",) if t == 0 else ()) for t in ts])
    good, rejected = continuous_nodes((n,), ts, histories, .5)
    assert good == (n,) and not rejected
    old = histories[(2, n.signal)][1][2]
    histories[(2, n.signal)][1][2] = (old[0], old[1], True, False, False, False, ("HIDDEN_MID_BREAK",))
    good, rejected = continuous_nodes((n,), ts, histories, .5)
    assert not good and "INTERVAL_LINK_UNQUALIFIED" in rejected[n]
    histories[(2, n.signal)][1][2] = old
    histories[(2, n.signal)][1].insert(2, (.3, None, False, False, False, False, ("UNPAIRED_LOSS",)))
    histories[(2, n.signal)] = ([e[0] for e in histories[(2, n.signal)][1]],
                                histories[(2, n.signal)][1])
    good, rejected = continuous_nodes((n,), ts, histories, .5)
    assert not good and "PHYSICAL_TOKEN_CHANGED" in rejected[n]
    print("SELF_CHECK_PASS: start-link, middle-link, unpaired-intermediate loss; 3 cases")
    print("LOCAL_SOURCE_DEPENDENCIES="+json.dumps(sorted(imported_local_sources())))


def run(args):
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text())
    validate_plan_and_locations(args, plan)
    require(args.out.resolve() != args.prepared.resolve(), "output cannot overwrite prepared")
    require(not args.out.exists(), "output directory must be new; no overwrite/retry")
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        require(os.environ.get(key) == "1", "one numerical thread required")
    for rel, pin in plan["source_pins"].items():
        payload = (ROOT/rel).read_bytes()
        require(sha(payload) == pin, "source pin "+rel)
        require(payload == subprocess.check_output(["git", "show", args.registration_commit+":"+rel],
                                                   cwd=ROOT), "unregistered source "+rel)
    require(plan_path.read_bytes() == subprocess.check_output(
        ["git", "show", args.registration_commit+":"+plan_path.relative_to(ROOT).as_posix()],
        cwd=ROOT), "unregistered plan")
    args.out.mkdir(parents=True)
    started = time.monotonic()
    counts = Counter(pytest_processes=0, raw_UBX_reads=0, reference_reads=0,
                     native_calls=0, evaluator_calls=0, integer_search_calls=0)
    rows, sequence_summaries = [], []
    try:
        for spec in plan["sequences"]:
            sequence = spec["sequence"]
            model_dir, saved, seal = read_plan_and_seal(args.prepared, spec, counts)
            records = saved["records"]
            times = [float(r["time_s"]) for r in records]
            require(all(b > a for a, b in zip(times, times[1:])), "nonmonotone source times")
            histories = read_arc_histories(model_dir, seal, counts)
            carrier_bytes = read_pinned(args.singleton/sequence/"CARRIER.csv", spec["singleton_csv_sha256"])
            old = list(csv.DictReader(io.StringIO(carrier_bytes.decode())))
            counts["singleton_valid_table_reads"] += 1
            require(len(old) == len(records), "old singleton full denominator")
            require(all(float(o["measurement_time"]) == t for o, t in zip(old, times)),
                    "old singleton exact time keys")
            local = []
            details_path = args.out/(sequence+"_DETAILS.jsonl.gz")
            with gzip.open(details_path, "wt", encoding="utf-8") as details:
                for start in range(0, len(records), 5):
                    require(time.monotonic()-started <= plan["budgets"]["wall_s"],
                            "registered processing time exceeded")
                    block = records[start:start+5]
                    ts = times[start:start+5]
                    row = dict(sequence=sequence, block_index=start//5,
                        first_epoch_index=start, last_epoch_index=start+4,
                        start_s=ts[0], end_s=ts[-1], interval_s=ts[-1]-ts[0],
                        status="UNASSESSED", endpoint_models_available=False,
                        common_endpoint_nodes=0, interval_continuous_nodes=0,
                        contrast_relations=0, geometry_rank0=None, geometry_rank1=None,
                        free_two_baseline_rank=None, attitude_rank=None,
                        singleton_valid_at_block_end=int(old[start+4]["valid"]),
                        singleton_valid_slots_in_block=sum(int(o["valid"]) for o in old[start:start+5]),
                        legal_contrast_without_singleton_at_end=False,
                        all_five_model_slots_built=all(r["families"].get(FAMILY,{}).get("status")=="BUILT" for r in block),
                        actual_available_time_s=None, actual_latency_s=None,
                        joint_covariance_m2=None, direction_point_ecef=None,
                        cross_time_covariance_known=False, between_block_independence_known=False,
                        covariance_calibrated=False, navigation_admitted=False,
                        endpoint0_Q_trace_m2=None, endpoint1_Q_trace_m2=None,
                        conditional_unknown_cross_bound_trace_m2=None,
                        norm_z_m=None, norm_geometry_change=None,
                        lost_node_reasons="{}")
                    detail = dict(row=row)
                    spacing_ok = all(abs(b-a-.2) <= .01 for a, b in zip(ts, ts[1:]))
                    if not spacing_ok:
                        row["status"] = "SOURCE_TIME_GRID_GAP"
                    elif any(r["families"].get(FAMILY,{}).get("status") != "BUILT" for r in (block[0],block[-1])):
                        row["status"] = "ENDPOINT_MODEL_UNAVAILABLE"
                        detail["endpoint_model_status"] = [
                            r["families"].get(FAMILY, {"status":"NO_ANCHOR_MODEL"})
                            if r["families"].get(FAMILY,{}).get("status") != "BUILT"
                            else {"status":"BUILT"} for r in (block[0],block[-1])]
                    else:
                        e0 = load_phase_epoch(model_dir, block[0], seal, saved, sequence, counts)
                        e1 = load_phase_epoch(model_dir, block[-1], seal, saved, sequence, counts)
                        row["endpoint_models_available"] = True
                        common = set(e0.nodes) & set(e1.nodes)
                        kept, rejected = continuous_nodes(common, ts, histories, saved["max_gap_s"])
                        row["common_endpoint_nodes"] = len(common)
                        row["interval_continuous_nodes"] = len(kept)
                        loss_counts = Counter(reason for reasons in rejected.values() for reason in reasons)
                        row["lost_node_reasons"] = json.dumps(dict(sorted(loss_counts.items())),separators=(",",":"))
                        continuity = PhaseArcContinuity(ts[0], ts[-1], None, e0.receiver_pair_id,
                                                       sequence+":SEALED_FULL_INTERVAL_ARC_EVENTS", kept)
                        g = build_phase_contrast_geometry(e0, e1, continuity)
                        counts["geometry_contrast_calls"] += 1
                        bound = unknown_cross_difference_bound(g,
                            marginal_bound_source_id="CONDITIONAL_ONLY:UNCALIBRATED_RAWX_ENDPOINT_WORKING_Q")
                        counts["conditional_bound_calls"] += 1
                        check_read_budgets(counts)
                        row["contrast_relations"] = len(g.relations)
                        row["status"] = "LEGAL_SAME_ARC_CONTRAST" if g.relations else "NO_CONTINUOUS_RELATIONS"
                        row["geometry_rank0"], s0, tol0 = matrix_rank_detail(g.G0)
                        row["geometry_rank1"], s1, tol1 = matrix_rank_detail(g.G1)
                        row["free_two_baseline_rank"], sx, tolx = matrix_rank_detail(np.hstack([-g.G0,g.G1]))
                        row["endpoint0_Q_trace_m2"] = float(np.trace(g.epoch0_covariance_contribution_m2))
                        row["endpoint1_Q_trace_m2"] = float(np.trace(g.epoch1_covariance_contribution_m2))
                        row["conditional_unknown_cross_bound_trace_m2"] = float(np.trace(bound.matrix_m2))
                        row["norm_z_m"] = float(np.linalg.norm(g.z_m))
                        row["norm_geometry_change"] = float(np.linalg.norm(g.G1-g.G0))
                        row["legal_contrast_without_singleton_at_end"] = bool(g.relations) and row["singleton_valid_at_block_end"] == 0
                        detail.update(
                            epoch0_fingerprint=e0.fingerprint, epoch1_fingerprint=e1.fingerprint,
                            relations=[e.label for e in g.relations],
                            physical_nodes=[dict(signal=n.signal,arc=n.arc) for n in g.physical_nodes],
                            interval_rejected_nodes=[dict(signal=n.signal,arc=n.arc,reasons=why) for n,why in rejected.items()],
                            F0=g.F0,F1=g.F1,physical_coefficients_m=g.physical_coefficients_m,
                            z_m=g.z_m,G0=g.G0,G1=g.G1,
                            endpoint0_Q_contribution_m2=g.epoch0_covariance_contribution_m2,
                            endpoint1_Q_contribution_m2=g.epoch1_covariance_contribution_m2,
                            conditional_unknown_cross_second_moment_bound_m2=bound.matrix_m2,
                            bound_scope=bound.scope,
                            geometry_singular_values=dict(G0=s0,G1=s1,free_two_baselines=sx),
                            algebraic_rank_tolerances=dict(G0=tol0,G1=tol1,free_two_baselines=tolx),
                            scope="OBSERVATION_ALGEBRA_ONLY_NOT_TRUSTED_HEADING_OR_NAVIGATION")
                    local.append(row);rows.append(row)
                    details.write(json.dumps(detail,default=json_default,separators=(",",":"))+"\n")
            legal = [r for r in local if r["status"] == "LEGAL_SAME_ARC_CONTRAST"]
            summary = dict(sequence=sequence,original_epochs=len(records),fixed_blocks=len(local),
                statuses=dict(Counter(r["status"] for r in local)),
                endpoint_models_available=sum(r["endpoint_models_available"] for r in local),
                legal_contrasts=len(legal),
                legal_without_singleton_at_block_end=sum(r["legal_contrast_without_singleton_at_end"] for r in local),
                legal_without_any_singleton_in_block=sum(r["singleton_valid_slots_in_block"]==0 for r in legal),
                endpoint_reuse_count=0,
                relation_count_range=([min(r["contrast_relations"] for r in legal),
                                        max(r["contrast_relations"] for r in legal)] if legal else None),
                current_geometry_rank_counts=dict(Counter(r["geometry_rank1"] for r in legal)),
                actual_availability_known=False,cross_time_covariance_known=False,
                between_block_independence_known=False,covariance_calibrated=False)
            require(len(local) == spec["blocks"], "sequence full block denominator")
            sequence_summaries.append(summary)
            print(json.dumps(summary),flush=True)
            del saved, records, histories, old, local
            gc.collect()
        require(len(rows)==plan["budgets"]["fixed_blocks"], "full denominator not completed")
        check_read_budgets(counts)
        for key in ("saved_plan_reads", "saved_seal_reads", "saved_arc_metadata_reads",
                    "singleton_valid_table_reads"):
            require(counts[key] == BUDGETS[key], "incomplete fixed input traversal")
        require(all(r["actual_available_time_s"] is None and r["actual_latency_s"] is None
                    and r["joint_covariance_m2"] is None and r["direction_point_ecef"] is None
                    and r["attitude_rank"] is None and not r["navigation_admitted"]
                    for r in rows), "NA/diagnostic-only boundary")
        with (args.out/"OPPORTUNITIES.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        result=dict(status="COMPLETE_SAVED_MODEL_GEOMETRY_QUALIFICATION_NOT_NAVIGATION",
            registration_commit=args.registration_commit,
            execution_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
            data_mode="real_saved_models_structural_diagnostic",
            counts=dict(counts),sequences=sequence_summaries,total_fixed_blocks=len(rows),
            elapsed_s=time.monotonic()-started,
            forbidden_inputs_used=False,integer_values_used=False,integer_truth_available=False,
            true_heading_or_navigation_benefit_evaluated=False,
            uncertainty_scope="Two endpoint working Q contributions plus conditional second-moment upper bound; no Q01/real calibration/between-factor independence or actual availability",
            output_sha256={p.name:sha(p.read_bytes()) for p in args.out.iterdir() if p.is_file()})
        emit(args.out/"SUMMARY.json",result)
        emit(args.out/"COMPLETE.json",dict(status=result["status"],completed_blocks=len(rows),
                                         summary_sha256=sha((args.out/"SUMMARY.json").read_bytes())))
        print("COMPLETE",len(rows),"blocks",flush=True)
    except Exception as exc:
        emit(args.out/"FAILED.json",dict(exception=repr(exc),traceback=traceback.format_exc(),
             completed_blocks=len(rows),counts=dict(counts),elapsed_s=time.monotonic()-started))
        if rows:
            with (args.out/"PARTIAL_OPPORTUNITIES.csv").open("w",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-check",action="store_true")
    parser.add_argument("--prepared",type=Path)
    parser.add_argument("--singleton",type=Path)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--plan",type=Path)
    parser.add_argument("--registration-commit")
    args=parser.parse_args()
    if args.self_check:
        self_check();return
    require(all(getattr(args,k) is not None for k in (
        "prepared","singleton","out","plan","registration_commit")), "all run arguments required")
    run(args)


if __name__=="__main__":
    main()
