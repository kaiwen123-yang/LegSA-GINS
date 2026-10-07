#!/usr/bin/env python3
"""One registered information readout of the dependency-qualified working priors.

All matrix calculations, joins and numeric failure rules reuse the frozen adapter.
No provider, decision CSV, navigation, raw or reference payload is read here.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import traceback
import arc_phase_real_information as base

ROOT = base.ROOT
D = base.D
PLAN = D / "ARC_PHASE_DEPENDENCY_INFORMATION_PLAN.json"
SCRIPT = "scripts/paper_rebuild/carrier_phase/arc_phase_dependency_information.py"
STAGE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/ARC_PHASE_DEPENDENCY_INFORMATION_ATTEMPT01"
NATIVE_REL = "TRUSTED_HEADING_CONTINUATION_20261007/HV_DEPENDENCY_POLICY_REAL_ATTEMPT01/REPAIR01"
BUDGET = dict(base.BUDGET)
SIDS = base.SIDS
OBJECTIVES = ["joint", "current", "relative_ecef", "common_ecef"]
POLICY = "causal_recorded_dependencies_unique_latest"
STATUS = "COMPLETE_LINEARIZED_WORKING_INFORMATION_READOUT_NOT_PHYSICAL_OR_NAVIGATION_GAIN"
require = base.require
emit = base.emit
io_helpers = base.io_helpers


class Inputs(base.Inputs):
    """Keep the tested cache/decode/stat interface; bound each sole content read."""
    def read(self, key):
        require(key in self.pins, "input outside registered closure")
        if key not in self.seen:
            pin = self.pins[key]
            path = io_helpers.expand(pin["path"], self.reg["aliases"])
            before = path.stat()
            require(type(pin["size_bytes"]) is int and pin["size_bytes"] >= 0 and
                    before.st_size == pin["size_bytes"], "input size drift: " + key)
            with path.open("rb") as stream:
                payload = stream.read(pin["size_bytes"] + 1)
            after = path.stat()
            signature = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            require(signature(before) == signature(after), "input changed during read: " + key)
            digest = hashlib.sha256(payload).hexdigest()
            require(len(payload) == pin["size_bytes"] and digest == pin["sha256"], "input SHA mismatch: " + key)
            self.seen[key] = payload
            self.stat_snapshots[key] = signature(after)
            self.receipts.append(dict(key=key, path=pin["path"], sha256=digest,
                size_bytes=len(payload), content_passes=1, verified_before_decode=True,
                maximum_read_bytes=pin["size_bytes"] + 1))
        return self.seen[key]


def registration(commit):
    payload = PLAN.read_bytes(); reg = base.decode_json(payload)
    require(reg["schema"] == "arc_phase_dependency_information.registration/v1" and
            reg["status"] == "REGISTERED_READY_SINGLE_EXECUTION", "draft not executable")
    require(reg["budgets"] == BUDGET and reg["stage"] == "<SCRATCH_ROOT>/" + STAGE_REL, "fixed stage/budget")
    require(reg["baseline_body_m"] == base.BASELINE and reg["epsilon_grid"] == base.EPSILONS and
            list(base.core.EPSILON_GRID) == base.EPSILONS and reg["objectives"] == OBJECTIVES,
            "same four objectives, baseline and five epsilons")
    require(reg["covariance_kind"] == "SECOND_MOMENT_UPPER_BOUND" and
            reg["error_model"] == "SECOND_MOMENT_ABOUT_NOMINAL" and
            reg["cross_mode"] == "UNKNOWN_CROSS_BOUND" and reg["phase_state_cross"] == "UNKNOWN" and
            reg["scope"] == "LINEARIZED_WORKING_SURROGATE_ONLY" and
            reg["nonlinear_remainder_qualified"] is False, "unchanged working model scope")
    require(payload == subprocess.check_output(["git", "show", commit + ":" + PLAN.relative_to(ROOT).as_posix()], cwd=ROOT), "registered plan bytes")
    require(SCRIPT in reg["source_pins"] and base.SCRIPT in reg["source_pins"], "new wrapper and frozen adapter pinned")
    io_helpers.source_check(reg, commit)
    require(io_helpers.expand("<CODE_ROOT>", reg["aliases"]) == ROOT and
            io_helpers.expand("<SCRATCH_ROOT>", reg["aliases"]) == (ROOT.parent.parent / "LegSA-GINS-SCRATCH").resolve(), "fixed aliases")
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        require(os.environ.get(key) == "1", "one numerical thread")
    require(not base.COUNTS, "fresh bounded mathematical counters")
    required_metadata = {"native_complete", "native_seal", "native_results", "prepared_plan",
                         "phase_summary", "phase_complete", "local_adapter_result"}
    required_metadata.update(s + "_native_manifest" for s in SIDS)
    require(set(reg["metadata_pins"]) == required_metadata, "exact ten metadata inputs")
    require(set(reg["input_pins"]) == {s + "_" + k for s in SIDS for k in ("priors", "lifecycle", "ledger", "details", "events")}, "exact fifteen scientific inputs")
    require(sum(p["size_bytes"] for p in reg["input_pins"].values()) == 30766496 and
            reg["source_byte_reads"]["input_bytes"] == 30766496 and
            reg["source_byte_reads"]["input_files"] == 15 and
            reg["source_byte_reads"]["metadata_files"] == 10 and
            reg["source_byte_reads"]["metadata_bytes"] == sum(p["size_bytes"] for p in reg["metadata_pins"].values()) and
            reg["source_byte_reads"]["content_passes_per_file"] == 1, "fixed once-read byte closure")
    stage = io_helpers.expand(reg["stage"], reg["aliases"])
    require(not stage.exists(), "unique stage, no automatic retry")
    return reg, stage, payload


def metadata_gate(reg, metadata):
    local = metadata["local_adapter_result"]
    require(local["status"] == "PASS_THREE_SYNTHETIC_ADAPTER_TESTS" and local["passed"] == 3 and
            local["failed"] == local["native_calls"] == local["real_input_reads"] == 0,
            "unchanged adapter already qualified by three synthetic tests")
    tested_pins = local["source_pins"]
    require(isinstance(tested_pins, dict) and len(tested_pins) == 8 and
            all(reg["source_pins"].get(path) == sha for path, sha in tested_pins.items()),
            "all eight tested source identities unchanged in this registration")
    complete, seal, results = (metadata[k] for k in ("native_complete", "native_seal", "native_results"))
    native_stage = io_helpers.expand("<SCRATCH_ROOT>/" + NATIVE_REL, reg["aliases"])
    require(io_helpers.expand(reg["metadata_pins"]["native_complete"]["path"], reg["aliases"]) == native_stage / "COMPLETE.json" and
            io_helpers.expand(reg["metadata_pins"]["native_seal"]["path"], reg["aliases"]) == native_stage / "ALL_NATIVE_SEALED.json", "fixed dependency native attempt")
    require(complete["status"] == "COMPLETE_RECORDED_DEPENDENCY_POLICY_FIRST_METADATA_FAILURE_RETAINED" and
            complete["new_native_calls"] == 5 and complete["reused_native_calls"] == 1 and
            complete["total_native_calls_across_attempts"] == 6 and
            complete["repeated_native_calls"] == complete["evaluator_calls"] == complete["phase_information_calls"] == complete["automatic_retries"] == 0 and
            complete["first_failure_retained"] is True and
            complete["seal_sha256"] == reg["metadata_pins"]["native_seal"]["sha256"], "completed native repair, no repeated call")
    require(seal["status"] == "ALL_SIX_SEALED_THREE_CAUSAL_CONTROLS_IDENTICAL_FIRST_FAILURE_RETAINED" and
            seal["total_native_calls_across_attempts"] == 6 and seal["reused_native_calls"] == 1 and
            seal["control_identities"] == complete["control_identities"], "native control identity seal")
    expected_controls = [dict(sequence_id=s, files=15, status=("PASS_REUSED_BY2_OLD_CAUSAL_ALL_FILE_BYTE_IDENTITY" if s == "BY2" else "PASS_OLD_CAUSAL_ALL_FILE_BYTE_IDENTITY")) for s in SIDS]
    require(seal["control_identities"] == expected_controls, "all 45 old causal files identical")
    require(results["status"] == complete["status"] and
            results["source_result_sha256"] == reg["metadata_pins"]["native_complete"]["sha256"] and
            results["native_seal_sha256"] == reg["metadata_pins"]["native_seal"]["sha256"] and
            io_helpers.expand(results["source_result"], reg["aliases"]) == native_stage / "COMPLETE.json" and
            results["independent_review"]["status"] == "PASS", "limited output review tied to these native results")
    require(metadata["phase_summary"]["status"] == "COMPLETE_SAVED_MODEL_GEOMETRY_QUALIFICATION_NOT_NAVIGATION" and
            metadata["phase_summary"]["total_fixed_blocks"] == 921 and
            metadata["phase_complete"]["summary_sha256"] == reg["metadata_pins"]["phase_summary"]["sha256"], "unchanged sealed phase model")
    for items in (reg["sequences"], complete["dependency_sequences"], metadata["prepared_plan"]["runs"], results["rows"]):
        require(tuple(x["sequence_id"] for x in items) == SIDS, "three complete ordered sequence records")
    require(len(seal["outputs"]) == 6 and tuple((x["arm"], x["sequence_id"]) for x in seal["outputs"]) ==
            tuple((a, s) for a in ("CAUSAL", "DEPENDENCY") for s in SIDS), "six sealed output identities")
    return complete, seal, results


def bind_sequence(reg, metadata, spec, native, old, reviewed):
    sid = spec["sequence_id"]; manifest = metadata[sid + "_native_manifest"]
    require(spec["blocks"] == native["source_blocks"] == old["block_count"] == reviewed["source_blocks"] and
            spec["priors"] == native["prior_rows"] == reviewed["covered_priors"] and
            spec["legal_models"] == native["legal_model_blocks"] and
            spec["legal_intersection"] == native["legal_model_covered"] == reviewed["legal_models_covered"], "all denominators retained")
    require(spec["run_id"] == old["run_id"] and spec["event_sha256"] == old["events"]["sha256"] and
            spec["manifest_sha256"] == old["manifest"]["sha256"], "unchanged source schedule identity")
    out = next(x for x in metadata["native_seal"]["outputs"] if x["sequence_id"] == sid and x["arm"] == "DEPENDENCY")
    for role, name in (("priors", "ARC_JOINT_PRIORS.jsonl"), ("lifecycle", "ARC_LIFECYCLE.csv"), ("ledger", "ARC_CONDITIONING_EVENTS.jsonl"), ("native_manifest", "RUN_MANIFEST.json")):
        pin = reg["metadata_pins" if role == "native_manifest" else "input_pins"][sid + "_" + role]
        sealed = out["seal"]["files"][name]
        require(pin["sha256"] == sealed["sha256"] and pin["size_bytes"] == sealed["size_bytes"] and
                io_helpers.expand(pin["path"], reg["aliases"]) == Path(out["path"]) / name, "input bound to new native seal: " + role)
    require(manifest["run_id"] == spec["run_id"] and manifest["arc_source_events_sha256"] == spec["event_sha256"] and
            manifest["arc_schedule_manifest_sha256"] == spec["manifest_sha256"] and
            manifest["go2_velocity_prior_time_policy"] == POLICY and manifest["arc_native_telemetry_enabled"] is True and
            manifest["arc_phase_updates"] == manifest["arc_foot_pair_updates"] == 0 and
            manifest["arc_uncovered_initial"] == 0, "new passive policy manifest")
    # Each ordinary update, full reset, START and covered END contributes one row.
    # A covered END retirement has no separate ledger row; only terminal retirement
    # adds one. With zero initial-uncovered blocks, that count is retires minus ends.
    expected_ledger = (manifest["arc_ordinary_updates"] + manifest["arc_full_resets"] + manifest["arc_starts"] +
                       manifest["arc_ends"] + manifest["arc_retires"] - manifest["arc_ends"])
    require(spec["ledger_rows"] == expected_ledger == {"BY2": 8311, "BY2H": 8062, "BY2O": 11172}[sid], "bounded actual ledger row count")
    require(manifest["go2_velocity_prior_update_count"] == reviewed["new_accepted"] ==
            native["recorded_dependency_decisions"]["accepted"] == native["causal_source_decisions"]["accepted"], "inherit reviewed dependency decisions, do not reopen decision CSV")
    require(spec["priors_sha256"] == reg["input_pins"][sid + "_priors"]["sha256"] and
            spec["details_sha256"] == metadata["phase_summary"]["output_sha256"][sid + "_DETAILS.jsonl.gz"] ==
            reg["input_pins"][sid + "_details"]["sha256"], "new prior and original phase model pins")
    require(reg["input_pins"][sid + "_events"]["sha256"] == old["events"]["sha256"] and
            io_helpers.expand(reg["input_pins"][sid + "_events"]["path"], reg["aliases"]) ==
            io_helpers.expand(old["events"]["path"], reg["aliases"]), "original exact event CSV")


def scalar_summary(rows, objectives):
    """Summarize values already returned by the frozen kernel; no new matrix math."""
    qualified = [r for r in rows if r["status"] == "QUALIFIED_LINEARIZED_WORKING_DIAGNOSTIC"]
    values = [r["working_information_eigenvalue_max"] for r in qualified]
    threshold_counts = Counter()
    for rho in values:
        require(math.isfinite(rho), "finite existing working spectrum")
        twice = 2 * rho; margin = 1 - twice
        tolerance = 128 * sys.float_info.epsilon * max(1., abs(twice))
        threshold_counts["SUFFICIENT_WITH_NUMERICAL_MARGIN" if margin > tolerance else
                         "NUMERICAL_BOUNDARY_UNRESOLVED" if abs(margin) <= tolerance else "NOT_SUFFICIENT"] += 1
    return dict(qualified_geometry_rows=len(qualified), unavailable_or_unresolved_geometry_rows=len(rows)-len(qualified),
        minimum_working_information_eigenvalue=min((r["working_information_eigenvalue_min"] for r in qualified), default=None),
        maximum_working_information_eigenvalue=max(values, default=None),
        maximum_J_over_T={t:max((r["J_over_T"] for r in objectives if r["target"] == t and r["J_over_T"] is not None), default=None) for t in OBJECTIVES},
        two_rho_lt_one=dict(counts=dict(threshold_counts), assessed_rows=len(values), all_block_denominator=len(rows),
            rho_definition="maximum eigenvalue of Rbar-whitened H P6 H^T; Rbar=2S",
            comparison_margin="128*machine_epsilon*max(1,abs(2*rho)); boundary remains unresolved",
            scope="Numerical sufficient condition for S-H P6 H^T positive definite in the qualified linearized working arrays; not a physical error bound or navigation claim"))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--registration-commit", required=True)
    args = parser.parse_args(); reg, stage, plan_bytes = registration(args.registration_commit)
    stage.mkdir(parents=True)
    emit(stage / "RESERVATION.json", dict(registration_commit=args.registration_commit,
        plan_sha256=hashlib.sha256(plan_bytes).hexdigest(), budget=BUDGET))
    with (stage / "REGISTERED_PLAN.json").open("xb") as stream: stream.write(plan_bytes)
    def timeout(*unused): raise TimeoutError("registered 600 s wall budget exceeded")
    signal.signal(signal.SIGALRM, timeout); signal.alarm(600)
    inputs = Inputs(reg)
    try:
        metadata = {k:inputs.json(k) for k in reg["metadata_pins"]}
        complete, seal, results = metadata_gate(reg, metadata)
        rows = []; objectives = []; numerical = []
        for spec, native, old, reviewed in zip(reg["sequences"], complete["dependency_sequences"],
                metadata["prepared_plan"]["runs"], results["rows"]):
            sid = spec["sequence_id"]
            bind_sequence(reg, metadata, spec, native, old, reviewed)
            events = inputs.csv(sid + "_events"); life = inputs.csv(sid + "_lifecycle")
            priors = inputs.jsonl(sid + "_priors", spec["priors"])
            details = inputs.jsonl(sid + "_details", spec["blocks"], compressed=True)
            ledger = inputs.jsonl(sid + "_ledger", spec["ledger_rows"])
            base.COUNTS.update(source_csv_reads=1, source_event_rows=len(events), lifecycle_file_reads=1,
                lifecycle_rows=len(life), prior_file_reads=1, prior_rows=len(priors), phase_detail_file_reads=1,
                phase_detail_rows=len(details), conditioning_ledger_reads=1)
            joined = base.join_sequence(spec, events, life, priors, details, ledger, native)
            a, b, c = base.block_readout(spec, joined, ledger, native)
            rows.extend(a); objectives.extend(b); numerical.extend(c)
        inputs.final_stat()
        require(len(rows) == 921 and len(objectives) <= 3428 and
                base.COUNTS["prior_rows"] == 918 and base.COUNTS["phase_detail_rows"] == 921 and
                base.COUNTS["source_event_rows"] == 1842, "complete unfiltered denominator")
        base.write_csv(stage / "BLOCKS.csv", rows)
        base.write_csv(stage / "OBJECTIVES.csv", objectives)
        emit(stage / "NUMERICAL_DETAILS.json", numerical)
        emit(stage / "INPUT_READ_RECEIPT.json", dict(files=inputs.receipts, post_stat_identity=True,
            content_passes_per_input=1, post_hash_pass=False,
            limits="Each finite cached byte snapshot SHA-verified before decode; final stat detects ordinary drift, not a second content authentication."))
        summary = dict(status=STATUS, registration_commit=args.registration_commit,
            prior_policy=POLICY, total_blocks=921, covered_priors=918, legal_models=860, legal_intersection=857,
            block_statuses=dict(Counter(r["status"] for r in rows)),
            prior_qualification_statuses=dict(Counter(r["prior_qualification"] for r in rows)),
            per_sequence=[dict(sequence_id=s, blocks=sum(r["sequence_id"] == s for r in rows),
                statuses=dict(Counter(r["status"] for r in rows if r["sequence_id"] == s)),
                existing_scalar_diagnostics=scalar_summary([r for r in rows if r["sequence_id"] == s],
                                                          [r for r in objectives if r["sequence_id"] == s])) for s in SIDS],
            objectives={t:dict(rows=sum(r["target"] == t for r in objectives),
                conditions=dict(Counter(r["continuous_condition"] for r in objectives if r["target"] == t)),
                grid_selected_count=sum(r["target"] == t and r["grid_selected_epsilon"] != 0 for r in objectives)) for t in OBJECTIVES},
            existing_scalar_diagnostics=scalar_summary(rows, objectives), calls=dict(base.COUNTS),
            fixed_zero_calls={k:0 for k in ("native_calls", "evaluator_calls", "residual_calls", "provider_payload_reads",
                "raw_reads", "reference_reads", "npz_reads", "integer_search_calls")},
            qualification_note=base.QUALIFICATION, scope="LINEARIZED_WORKING_SURROGATE_ONLY",
            nonlinear_remainder_qualified=False, actual_available_time_s=None, phase_state_cross="UNKNOWN",
            navigation_admitted=False, physical_covariance_bound_qualified=False,
            source_time_flags_are_report_only=True, all_source_online_causality_qualified=False,
            inherited_dependency_qualification=dict(native_result_sha256=reg["metadata_pins"]["native_complete"]["sha256"],
                limited_output_review=results["independent_review"], accepted_rows=results["totals"]["new_accepted"],
                decision_csv_reopened=False, scope="Historical calibrated GNSS18 generating-row times only; actual arrival and full upstream dependence remain unqualified"),
            native_failure_history=dict(first_metadata_failure_retained=True, total_native_calls=6,
                new_calls_in_registered_repair=5, reused_calls=1, repeated_calls=0))
        emit(stage / "SUMMARY.json", summary)
        files = {p.name:io_helpers.pin(p) for p in sorted(stage.iterdir()) if p.is_file()}
        emit(stage / "COMPLETE.json", dict(status=STATUS, registration_commit=args.registration_commit,
            output_pins=files, counts=dict(base.COUNTS), automatic_retries=0))
        print(json.dumps(dict(status=STATUS, blocks=len(rows), objective_rows=len(objectives), counts=dict(base.COUNTS))))
    except BaseException as exc:
        emit(stage / "FAILED.json", dict(error_type=type(exc).__name__, error=str(exc),
            counts=dict(base.COUNTS), input_reads=inputs.receipts, automatic_retries=0, valid_summary=False))
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    try: main()
    except BaseException: traceback.print_exc(); raise
