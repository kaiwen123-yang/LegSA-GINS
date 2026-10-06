#!/usr/bin/env python3
"""Registered three-window RAWX observation-layer semi-synthetic fault trial.

This is a wrapper over the existing decoder/ArcTracker/model builder and complete
set frontend. No run is dispatched at import, and DRAFT plans cannot execute.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
PLAN_REL = "docs/paper_rebuild/TRUSTED_HEADING_20261006/RAWX_FAULT_PLAN.json"
SCRIPT_REL = "scripts/paper_rebuild/carrier_phase/rawx_fault_trial.py"
FAMILY = "GPS_GAL_BDS_DUAL"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text())


def emit(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n"); f.flush(); os.fsync(f.fileno())


def check(path, digest):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "missing/symlink file: " + str(path))
    require(sha(path) == digest, "SHA mismatch: " + str(path))
    return path


def registration(commit):
    plan = read(ROOT / PLAN_REL)
    require(plan["status"] == "REGISTERED_READY", "fault plan remains a draft")
    require(os.uname().sysname == "Linux", "Ubuntu WSL required")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        require(os.environ.get(key) == "1", "one thread required: " + key)
    for rel in (PLAN_REL, SCRIPT_REL, *plan["source_pins"]):
        payload = (ROOT / rel).read_bytes()
        saved = subprocess.check_output(["git", "show", commit + ":" + rel], cwd=ROOT)
        require(payload == saved, "registration bytes mismatch: " + rel)
        if rel in plan["source_pins"]:
            require(hashlib.sha256(payload).hexdigest() == plan["source_pins"][rel], "source pin: " + rel)
    return plan


class SealedCodeAnchorReuse:
    """Bound cache, never a navigation P/V measurement or a future interpolator."""
    def __init__(self, saved, *, seal_sha256, plan_sha256):
        self.saved = saved
        self.records = {tuple(r["key"]): r for r in saved["records"]}
        require(len(self.records) == len(saved["records"]), "duplicate cached anchor epoch")
        self.identity = dict(source_model_seal_sha256=seal_sha256, source_plan_sha256=plan_sha256,
            policy="exact same epoch/code/clock/causal broadcast; unchanged SPP result including unavailable",
            new_spp_calls=0, position_measurement=False)
        self.calls = 0; self.bound = False

    def bind(self, *, sequence, window_s, base_time, inputs, epochs, navigation_audit):
        from legsa_gins.paper_rebuild.carrier_phase.rawx_fault_overlay import code_doppler_fingerprint, local_time
        old = self.saved
        require(sequence == old["sequence"] and window_s == old["window_s"] and base_time == old["base_time"],
                "anchor sequence/window/base identity")
        require(inputs["registry_sha256"] == old["inputs"]["registry_sha256"], "anchor registry identity")
        for rx in ("1", "2"):
            require(inputs["raw_sources"][rx]["sha256"] == old["inputs"]["raw_sources"][rx]["sha256"],
                    "anchor UBX source identity")
        require(navigation_audit["sha256"] == old["inputs"]["navigation_override"]["sha256"],
                "anchor causal NAV schedule identity")
        for rx in (1, 2):
            keys = [(e.gps_week, e.gps_tow_seconds) for e in epochs[rx]]
            require(len(set(keys)) == len(keys) and set(keys) == set(self.records), "anchor complete paired time keys")
            require(all(local_time(e, base_time) == self.records[k]["time_s"] for e, k in zip(epochs[rx], keys)),
                    "anchor exact relative time identity")
        self.identity["unchanged_code_doppler_sha256"] = code_doppler_fingerprint(epochs)
        self.bound = True

    def verify_overlay(self, before, after):
        from legsa_gins.paper_rebuild.carrier_phase.rawx_fault_overlay import code_doppler_fingerprint
        require(self.bound and code_doppler_fingerprint(before) == code_doppler_fingerprint(after)
                == self.identity["unchanged_code_doppler_sha256"], "overlay changed cached code/clock input")

    def for_epoch(self, key, time_s, navigation):
        import copy
        import math
        require(self.bound, "anchor cache not source-bound")
        old = self.records[tuple(key)]
        require(old["time_s"] == time_s and old["navigation"] == navigation, "anchor per-epoch causal identity")
        decision = old["anchor_decision"]
        require(decision["time_s"] == time_s, "anchor decision time mismatch")
        if decision["available"]:
            position = decision["position_ecef_m"]
            require(len(position) == 3 and all(math.isfinite(x) for x in position)
                    and decision["source_time_s"] <= time_s, "invalid/future cached anchor")
            require(old["anchor_ecef_m"] == position, "cached anchor center identity")
        self.calls += 1
        result = {k: copy.deepcopy(old[k]) for k in ("spp", "spp_failure", "anchor_decision") if k in old}
        result["anchor_computation"] = "SEALED_UNCHANGED_CODE_REUSE_NOT_NEW_SPP"
        return result


def prepare(a):
    import real_trial
    from full_window_prepare import seal_models
    from legsa_gins.paper_rebuild.carrier_phase.rawx_fault_overlay import apply_rawx_fault_overlay
    plan = registration(a.registration_commit)
    roots = real_trial.aliases(a.roots)
    for dependency in plan["native_dependencies"]:
        check(real_trial.expand(dependency["path"], roots), dependency["sha256"])
    source = Path(a.clean_prepared).resolve()
    check(source / "COMPLETE.json", plan["clean_prepared_complete_sha256"])
    check(source / "SUMMARY.json", plan["clean_prepared_summary_sha256"])
    require(read(source / "COMPLETE.json")["status"] == "COMPLETE", "clean model preparation incomplete")
    stage = Path(a.stage).resolve(); stage.mkdir(parents=True, exist_ok=False)
    emit(stage / "REGISTERED_PLAN.json", plan)
    emit(stage / "PREPARE_STARTED.json", dict(registration_commit=a.registration_commit, retry=0,
        source=str(source), rawx_payload_read_budget=6, prepare_call_budget=3,
        pid=os.getpid(), parent_pid=os.getppid(), argv=sys.argv, started_unix_s=time.time()))
    out = stage / "PREPARED"; out.mkdir()
    summaries = []; calls = 0; started = time.monotonic()
    try:
        for spec in plan["sequences"]:
            sid = spec["sequence"]; seqsource = source / sid
            seal = read(check(seqsource / "MODEL_OUTPUT_SEAL.json", spec["clean_seal_sha256"]))
            require(seal["complete_preparation"] is True, "incomplete clean model seal")
            saved = read(check(seqsource / "MODELS/PLAN.json", seal["files"]["PLAN.json"]["sha256"]))
            require(saved["sequence"] == sid and saved["window_s"] == spec["window_s"]
                    and len(saved["records"]) == spec["paired_epochs"], "original V3 full-window model identity")
            require(saved["max_gap_s"] == .21 and saved["tdcp_limit_cycles"] == .5
                    and saved["pivot_policy"] == "reselect_when_missing", "unchanged arc/pivot policy")
            nav = saved["inputs"]["navigation_override"]
            schedule = check(nav["schedule"], nav["sha256"])
            reuse = SealedCodeAnchorReuse(saved, seal_sha256=spec["clean_seal_sha256"],
                                         plan_sha256=seal["files"]["PLAN.json"]["sha256"])
            pivots = {r["time_s"]: [g["pivot"] for g in r.get("families", {}).get(FAMILY, {}).get("groups", ())]
                      for r in saved["records"]}
            def overlay(epochs, base):
                return apply_rawx_fault_overlay(epochs, base_time=base, window_s=tuple(spec["window_s"]),
                    supported_groups=real_trial.FAMILIES[FAMILY], pivot_history=pivots)
            seqout = out / sid; seqout.mkdir()
            args = SimpleNamespace(roots=a.roots, code=ROOT, output=seqout / "MODELS", sequence=sid,
                start=spec["window_s"][0], stop=spec["window_s"][1], length=.35, max_gap=.21, tdcp_limit=.5,
                max_anchor_hold_s=20., pivot_policy="reselect_when_missing", navigation_manifest=None,
                navigation_schedule=schedule, allow_empty_navigation=True)
            calls += 1
            emit(seqout / "PREPARE_INVOCATION.json", dict(ordinal=calls, budget=3, retry=0,
                source_seal_sha256=spec["clean_seal_sha256"], source_plan_sha256=seal["files"]["PLAN.json"]["sha256"],
                family=FAMILY, code_anchor_reuse=True, rawx_overlay=True, navigation_schedule_sha256=nav["sha256"]))
            real_trial.prepare(args, epoch_overlay=overlay, anchor_reuse=reuse, prepare_families=(FAMILY,))
            prepared = read(args.output / "PLAN.json")
            require(len(prepared["records"]) == spec["paired_epochs"] and reuse.calls == spec["paired_epochs"],
                    "fault preparation denominator changed")
            require(prepared["pairing"] == saved["pairing"], "overlay changed receiver pairing")
            require(prepared["spp_calls"] == 0 and set(prepared["families"]) == {FAMILY}, "unexpected prepare work")
            output_sha = seal_models(args.output, seqout / "MODEL_OUTPUT_SEAL.json", dict(
                registration_commit=a.registration_commit, registered_plan_sha256=sha(ROOT / PLAN_REL),
                source_clean_seal_sha256=spec["clean_seal_sha256"], data_mode="RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC"), complete=True)
            summaries.append(dict(sequence=sid, window_s=spec["window_s"], paired_epochs=spec["paired_epochs"],
                seal_sha256=output_sha, reused_anchor_slots=reuse.calls,
                overlay_sha256=sha(args.output / "RAWX_OBSERVATION_OVERLAY.json"),
                built_models=sum(r.get("families", {}).get(FAMILY, {}).get("status") == "BUILT" for r in prepared["records"])))
            print("FAULT_PREPARED", sid, spec["paired_epochs"], flush=True)
        registration(a.registration_commit)
        emit(out / "SUMMARY.json", dict(status="COMPLETE", data_mode="RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC",
            sequences=summaries, prepare_calls=calls, rawx_source_payload_reads=2*calls,
            spp_calls=0, converter_calls=0, search_calls=0, navigation_calls=0, evaluator_calls=0,
            reference_reads=0, wall_s=time.monotonic()-started))
        emit(out / "COMPLETE.json", dict(status="COMPLETE", registration_commit=a.registration_commit,
            registered_plan_sha256=sha(ROOT / PLAN_REL), summary_sha256=sha(out / "SUMMARY.json"),
            sequence_seals={s["sequence"]: s["seal_sha256"] for s in summaries}))
        emit(stage / "PREPARE_COMPLETE.json", dict(status="COMPLETE", prepared_complete_sha256=sha(out / "COMPLETE.json")))
    except BaseException as exc:
        emit(stage / "PREPARE_FAILED.json", dict(error=repr(exc), traceback=traceback.format_exc(),
            prepare_calls=calls, retries=0, no_search_dispatched=True))
        raise


def frontend(a):
    import full_window_frontend as original
    plan = registration(a.registration_commit); stage = Path(a.stage).resolve()
    require(read(stage / "REGISTERED_PLAN.json") == plan, "prepared registration mismatch")
    prepared = stage / "PREPARED"
    terminal = read(check(prepared / "COMPLETE.json", read(stage / "PREPARE_COMPLETE.json")["prepared_complete_sha256"]))
    require(terminal["status"] == "COMPLETE" and terminal["registration_commit"] == a.registration_commit
            and terminal["registered_plan_sha256"] == sha(ROOT / PLAN_REL), "fault prepare chain")
    summary = read(check(prepared / "SUMMARY.json", terminal["summary_sha256"]))
    require(len(summary["sequences"]) == 3 and set(terminal["sequence_seals"]) == {s["sequence"] for s in plan["sequences"]},
            "fault preparation sequence coverage")
    derived = dict(plan["frontend_template"])
    derived.update(prepared_complete_sha256=sha(prepared / "COMPLETE.json"),
                   prepared_summary_sha256=terminal["summary_sha256"], source_pins=plan["source_pins"],
                   data_mode="RAWX_OBSERVATION_LEVEL_SEMISYNTHETIC",
                   sequences=[dict(sequence=s["sequence"],window_s=s["window_s"],paired_epochs=s["paired_epochs"],
                       seal_sha256=terminal["sequence_seals"][s["sequence"]]) for s in plan["sequences"]])
    # Derived hashes are not unknown discretionary settings: they are solely the
    # completed prepare outputs under this byte-bound registration.
    def validate(commit, effective):
        current = registration(commit)
        require(current == plan and effective == derived, "effective fault frontend contract changed")
        require(read(stage / "REGISTERED_PLAN.json") == current, "fault source registration changed")
        check(prepared / "COMPLETE.json", derived["prepared_complete_sha256"])
        check(prepared / "SUMMARY.json", derived["prepared_summary_sha256"])
    emit(stage / "FRONTEND_DERIVED_PLAN.json", derived)
    emit(stage / "FRONTEND_STARTED.json", dict(registration_commit=a.registration_commit, retry=0,
        derived_plan_sha256=sha(stage / "FRONTEND_DERIVED_PLAN.json"), enumeration_budget=921,
        pid=os.getpid(), parent_pid=os.getppid(), argv=sys.argv, started_unix_s=time.time()))
    original.run(SimpleNamespace(registration_commit=a.registration_commit, prepared=prepared,
                                output=stage / "FRONTEND"), supplied_plan=derived, registration_check=validate)
    emit(stage / "FRONTEND_COMPLETE.json", dict(status="COMPLETE",
        frontend_complete_sha256=sha(stage / "FRONTEND/COMPLETE.json")))


def main():
    p = argparse.ArgumentParser(); p.add_argument("command", choices=("prepare", "frontend"))
    p.add_argument("--stage", type=Path, required=True); p.add_argument("--registration-commit", required=True)
    p.add_argument("--clean-prepared", type=Path); p.add_argument("--roots", type=Path)
    a = p.parse_args()
    if a.command == "prepare":
        require(a.clean_prepared is not None and a.roots is not None, "prepare requires source directory and roots")
    try:
        globals()[a.command](a)
    except BaseException as exc:
        if a.stage.exists() and not (a.stage / (a.command.upper()+"_FAILED.json")).exists():
            emit(a.stage / (a.command.upper()+"_FAILED.json"), dict(error=repr(exc), traceback=traceback.format_exc(), retries=0))
        raise


if __name__ == "__main__":
    main()
