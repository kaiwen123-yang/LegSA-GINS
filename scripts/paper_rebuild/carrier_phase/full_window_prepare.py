#!/usr/bin/env python3
"""Registered three-window causal NAV/RAWX preparation; never searches integers."""
from __future__ import annotations
import argparse
import csv
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from prepare_navigation import scan, nav_records

PLAN_REL = "docs/paper_rebuild/TRUSTED_HEADING_20261006/FULL_WINDOW_PREPARE_PLAN.json"
SCRIPT_REL = "scripts/paper_rebuild/carrier_phase/full_window_prepare.py"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def emit(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def expand(value, roots):
    for key in sorted(roots, key=len, reverse=True):
        if value == key or value.startswith(key + "/"):
            return Path(roots[key] + value[len(key):])
    raise ValueError("unregistered path alias: " + value)


def check_pin(path, expected):
    require(sha(path) == expected, "SHA256 mismatch: " + str(path))


def registration(commit, plan):
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "full registration commit required")
    for rel in (PLAN_REL, SCRIPT_REL):
        require(subprocess.check_output(["git", "show", commit + ":" + rel], cwd=ROOT)
                == (ROOT / rel).read_bytes(), "registration bytes differ: " + rel)
    for rel, expected in plan["source_pins"].items():
        p = (ROOT / rel).resolve()
        require(p.is_relative_to(ROOT), "source pin outside repository")
        check_pin(p, expected)
        require(hashlib.sha256(subprocess.check_output(["git", "show", commit + ":" + rel], cwd=ROOT)).hexdigest()
                == expected, "registration source mismatch: " + rel)
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        require(os.environ.get(key) == "1", "single-thread environment required: " + key)


def seal_models(models, destination, identity, complete):
    """Pin only this attempt's new outputs, including failed partial preparations."""
    files = {}
    for path in sorted(models.rglob("*")):
        require(not path.is_symlink(), "model output symlink not allowed")
        if path.is_file():
            files[path.relative_to(models).as_posix()] = {
                "sha256": sha(path), "bytes": path.stat().st_size}
    refs = []
    if complete:
        saved = read(models / "PLAN.json")
        refs = [row["file"] for rec in saved["records"]
                for row in rec.get("families", {}).values() if row["status"] == "BUILT"]
        require(len(refs) == len(set(refs)), "model NPZ reference duplicated")
        require(set(refs) == {name for name in files if name.endswith(".npz")},
                "built-model references differ from saved NPZ inventory")
        require(all(Path(name).name == name for name in refs), "NPZ reference leaves model folder")
    emit(destination, dict(schema="full_window_models.seal.v1", complete_preparation=complete,
        model_directory=str(models), identity=identity, files=files,
        model_npz_count=sum(name.endswith(".npz") for name in files),
        exact_built_model_references_checked=complete,
        original_raw_rehashed_for_seal=False))
    return sha(destination)


def invoke(argv, folder, kind, state, limits):
    """One process group per actual invocation; preserve failure, never retry."""
    counter = kind + "_calls"
    require(state[counter] < limits[counter], "invocation budget exhausted: " + kind)
    state[counter] += 1
    started = time.monotonic()
    receipt = dict(kind=kind, index=state[counter], argv=list(map(str, argv)), status="STARTING")
    emit(folder / "INVOCATION.json", receipt)
    with (folder / "stdout.log").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
        proc = subprocess.Popen(list(map(str, argv)), cwd=folder, stdout=stdout, stderr=stderr,
                                start_new_session=True)
        receipt.update(pid=proc.pid, status="RUNNING")
        emit(folder / "INVOCATION.json", receipt)
        try:
            code = proc.wait(timeout=limits[kind + "_timeout_s"])
        except BaseException as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            receipt.update(status="INTERRUPTED_OR_TIMEOUT", exception=repr(exc),
                           returncode=proc.returncode, elapsed_s=time.monotonic()-started)
            emit(folder / "INVOCATION.json", receipt)
            raise
    receipt.update(status="COMPLETED" if code == 0 else "FAILED",
                   returncode=code, elapsed_s=time.monotonic()-started)
    emit(folder / "INVOCATION.json", receipt)
    require(code == 0, kind + " failed; no retry")
    return receipt


def main(args):
    require(os.uname().sysname == "Linux", "Ubuntu WSL required")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(status="PREFLIGHT", converter_calls=0, prepare_calls=0,
                 integer_search_calls=0, navigation_solver_calls=0, evaluator_calls=0,
                 reference_reads=0, old_full_history_NAV_reads=0, converter_build_calls=0,
                 prefixes_created=0, prefixes_reused=0, sequences_completed=[])
    started = time.monotonic()
    emit(out / "STATE.json", state)
    try:
        plan = read(ROOT / PLAN_REL)
        registration(args.registration_commit, plan)
        emit(out / "REGISTERED_PLAN.json", plan)
        roots = read(args.roots)["aliases"]
        roots = {**roots, "<OLD_CARRIER_ROOT>": str(args.carrier_root.resolve())}
        # The child real_trial script resolves package imports without changing
        # its source; it must use this checked-out source, not another install.
        os.environ["PYTHONPATH"] = str(ROOT / "src")
        for item in plan["native_dependencies"]:
            check_pin(expand(item["path"], roots), item["sha256"])
        for item in plan["count_evidence"]:
            check_pin(ROOT / item["path"], item["sha256"])
        overview = list(csv.DictReader((ROOT / plan["count_evidence"][0]["path"]).open()))
        paired = list(csv.DictReader((ROOT / plan["count_evidence"][1]["path"]).open()))
        for spec in plan["sequences"]:
            name = spec["sequence"]
            rows = [r for r in overview if r["sequence"] == name]
            require({r["receiver"] for r in rows} == {"1", "2"} and len(rows) == 2
                    and all(int(r["raw_epochs"]) == spec["expected_paired_epochs"] for r in rows),
                    "registered DG01 receiver count evidence differs")
            rows = [r for r in paired if r["sequence"] == name and r["scope"] == "paired_epochs"
                    and r["metric"] == "rcvTow_R2_minus_R1_s"]
            require(len(rows) == 1 and int(rows[0]["n"]) == spec["expected_paired_epochs"]
                    and int(rows[0]["unpaired_R1"]) == int(rows[0]["unpaired_R2"]) == 0,
                    "registered DG01 exact-pair evidence differs")
        lock_path = ROOT / plan["v3_lock"]["path"]
        check_pin(lock_path, plan["v3_lock"]["sha256"])
        lock = read(lock_path)
        lock_sequences = {s["sequence_id"]: s for s in lock["sequences"]}
        old_schedule_path = expand(plan["reuse"]["schedule"], roots)
        check_pin(old_schedule_path, plan["reuse"]["schedule_sha256"])
        old_schedule = read(old_schedule_path)
        require([e["cutoff_relative_s"] for e in old_schedule["entries"]]
                == plan["reuse"]["cutoffs_s"], "old BY2 prefix schedule differs")
        old_entries = {float(e["cutoff_relative_s"]): e for e in old_schedule["entries"]}
        initial_path = Path(old_entries[100.0]["manifest"])
        check_pin(initial_path, old_entries[100.0]["manifest_sha256"])
        initial = read(initial_path)
        initial_pins = read(initial_path.parent / "INPUT_PINS.json")
        check_pin(initial_path.parent / "INPUT_PINS.json", plan["reuse"]["initial_input_pins_sha256"])
        converter = Path(initial["commands"][0]["argv"][0])
        require(initial["converter"]["executable_sha256"] == plan["converter_sha256"],
                "converter metadata differs")
        check_pin(converter, plan["converter_sha256"])
        inputs = {}
        for spec in plan["sequences"]:
            name = spec["sequence"]
            recorded = lock_sequences[name]
            require(recorded["full_window_s"] == spec["window_s"], "V3 full window mismatch")
            registry_path = expand(spec["registry"], roots)
            check_pin(registry_path, spec["registry_sha256"])
            info = read(registry_path)
            require(info["sequence"] == name and info["base_time"] == recorded["base_time_unix_s"]
                    and info["window_seconds"] == spec["window_s"], "registry/V3 sequence or time mismatch")
            sources = {}
            for rx in (1, 2):
                key = "gnss" + str(rx)
                raw_lock = recorded["raw_files"][key]
                lineage = info["raw_hash_locks"][key]
                require(raw_lock["path"] == "<RAW_ROOT>/" + lineage["relative_path"]
                        and raw_lock["registered_sha256"] == lineage["sha256"]
                        and raw_lock["current_size_bytes"] == lineage["size_bytes"],
                        "registry is not the original V3 raw source: " + name + key)
                row = info["source_files"][key + ".ubx"]
                source = expand(row["source"], roots)
                require(source.stat().st_size == row["bytes"], "registered UBX size differs")
                # Once for prefix production. Unmodified real_trial additionally
                # verifies each UBX once during its own registered preparation.
                check_pin(source, row["sha256"])
                sources[rx] = source
            inputs[name] = (registry_path, info, sources)
        require(initial_pins["registry_sha256"] == plan["sequences"][0]["registry_sha256"],
                "initial BY2 prefix belongs to another registry")
        emit(out / "INPUT_IDENTITY.json", dict(registration_commit=args.registration_commit,
             roots_file=str(args.roots.resolve()), v3_lock_sha256=plan["v3_lock"]["sha256"],
             registry_pins={s["sequence"]: s["registry_sha256"] for s in plan["sequences"]},
             converter=dict(path=str(converter), sha256=plan["converter_sha256"]),
             original_csv_payloads_read=False, original_nonheading_providers_read=False,
             source_prefix_history_policy="same registered full UBX; prefix payload closed by original RAWX"))
        summaries = []
        for spec in plan["sequences"]:
            name = spec["sequence"]
            registry_path, info, sources = inputs[name]
            seqout = out / name
            seqout.mkdir()
            entries = []
            for cutoff in spec["cutoffs_s"]:
                prefix = seqout / ("PREFIX_" + f"{cutoff:08.3f}")
                prefix.mkdir()
                lineage = dict(registry_sha256=spec["registry_sha256"], base_time=info["base_time"],
                    source_ubx_sha256={str(rx): info["source_files"][f"gnss{rx}.ubx"]["sha256"] for rx in (1, 2)})
                if name == "BY2" and cutoff in old_entries:
                    entry = old_entries[cutoff]
                    old_path = Path(entry["manifest"])
                    check_pin(old_path, entry["manifest_sha256"])
                    manifest = read(old_path)
                    require(manifest["causal_cutoff_relative_s"] == cutoff
                            and manifest["old_full_history_navigation_loaded"] is False, "invalid reusable prefix")
                    if cutoff == 100:
                        for rx in (1, 2):
                            require(initial_pins["ubx"][str(rx)]["sha256"] == lineage["source_ubx_sha256"][str(rx)],
                                    "old initial prefix raw identity mismatch")
                    else:
                        require(all(manifest.get(k) == v for k, v in lineage.items()),
                                "old later prefix lineage mismatch")
                    for nav in manifest["navigation"]:
                        check_pin(Path(nav["path"]), nav["sha256"])
                    # New metadata wrapper only; original NAV and manifests untouched.
                    manifest = {**manifest, **lineage, "reused_navigation_payload": True,
                        "original_manifest": dict(path=str(old_path), sha256=entry["manifest_sha256"]),
                        "wrapper_script_sha256": sha(ROOT / SCRIPT_REL)}
                    state["prefixes_reused"] += 1
                else:
                    navigation, commands, audits = [], [], {}
                    for rx in (1, 2):
                        payload, audit = scan(sources[rx], info["base_time"], cutoff)
                        derived = prefix / f"gnss{rx}_rawx_e1b.ubx"
                        derived.write_bytes(payload)
                        audit["derived_stream_sha256"] = sha(derived)
                        audits[str(rx)] = audit
                        emit(prefix / "PAGE_QUALIFICATION.json", audits)
                        nav = prefix / f"broadcast_prefix_rx{rx}.nav"
                        logdir = prefix / f"CONVERT_RX{rx}"
                        logdir.mkdir()
                        argv = [converter, "-r", "ubx", "-v", "3.04", "-o", prefix / f"unused_rx{rx}.obs",
                                "-n", nav, "-trace", "0", derived]
                        commands.append(invoke(argv, logdir, "converter", state, plan["budgets"]))
                        require(nav.is_file(), "converter produced no NAV")
                        navigation.append(dict(path=str(nav), sha256=sha(nav), receiver=rx,
                            role="NEW_ALL_GNSS_CAUSAL_PREFIX_GAL_E1B_ONLY", records=dict(nav_records(nav))))
                        emit(out / "STATE.json", state)
                    manifest = dict(navigation=navigation, converter=initial["converter"], commands=commands,
                        source="SAME_DATASET_PINNED_UBX_ALL_GNSS_PREFIX_GAL_E1B_ONLY",
                        cutoff_relative_s=cutoff, causal_cutoff_relative_s=cutoff,
                        old_full_history_navigation_loaded=False, old_nav_modified=False,
                        causal_availability="surrounding original RAWX; untagged SFRBX waits for following tag",
                        reference_reads=0, downloaded_ephemeris=False, converter_reused_not_rebuilt=True,
                        reused_navigation_payload=False, script_sha256=sha(ROOT / SCRIPT_REL), **lineage)
                    state["prefixes_created"] += 1
                target = prefix / "NAVIGATION_MANIFEST.json"
                emit(target, manifest)
                entries.append(dict(cutoff_relative_s=cutoff, manifest=str(target),
                                    manifest_sha256=sha(target), reuse_initial_prefix=False))
                emit(out / "STATE.json", state)
                print(json.dumps(dict(event="PREFIX_COMPLETE", sequence=name, cutoff_s=cutoff,
                    reused=manifest["reused_navigation_payload"],
                    converter_calls=state["converter_calls"])), flush=True)
            schedule = seqout / "NAVIGATION_SCHEDULE.json"
            emit(schedule, dict(schema="causal_navigation_schedule.v1", entries=entries,
                registry_sha256=spec["registry_sha256"], reference_reads=0,
                availability_policy="load latest cutoff not later than current RAWX epoch",
                old_full_history_navigation_loaded=False))
            models = seqout / "MODELS"
            logdir = seqout / "PREPARE"
            logdir.mkdir()
            argv = [sys.executable, ROOT / "scripts/paper_rebuild/carrier_phase/real_trial.py", "prepare",
                    "--code", ROOT, "--roots", args.roots.resolve(), "--output", models,
                    "--sequence", name, "--start", spec["window_s"][0], "--stop", spec["window_s"][1],
                    "--length", .35, "--max-gap", .21, "--tdcp-limit", .5,
                    "--max-anchor-hold-s", 20., "--pivot-policy", "reselect_when_missing",
                    "--navigation-schedule", schedule]
            invoke(argv, logdir, "prepare", state, plan["budgets"])
            seal_path = seqout / "MODEL_OUTPUT_SEAL.json"
            output_seal_sha = seal_models(models, seal_path, dict(
                registration_commit=args.registration_commit,
                registered_plan_sha256=sha(ROOT / PLAN_REL),
                registry_sha256=spec["registry_sha256"],
                navigation_schedule_sha256=sha(schedule)), complete=True)
            saved = read(models / "PLAN.json")
            records = saved["records"]
            require(saved["sequence"] == name and saved["window_s"] == spec["window_s"],
                    "prepared sequence mismatch")
            require(len(records) == spec["expected_paired_epochs"], "unexpected full-window pair count; preserve, stop")
            require(saved["pairing"] == dict(unique_pairs=spec["expected_paired_epochs"],
                    unpaired_rx1=0, unpaired_rx2=0, duplicate_rx1=0, duplicate_rx2=0),
                    "unexpected pairing; preserve all records and stop")
            item = dict(sequence=name, window_s=spec["window_s"], prepared_plan=str(models / "PLAN.json"),
                prepared_plan_sha256=sha(models / "PLAN.json"), paired_epochs=len(records),
                model_output_seal=str(seal_path), model_output_seal_sha256=output_seal_sha,
                model_npz_count=sum(r.get("status") == "BUILT" for x in records
                                    for r in x.get("families", {}).values()),
                actual_first_s=records[0]["time_s"], actual_last_s=records[-1]["time_s"],
                spp_attempts=len(records), spp_failures=sum("spp_failure" in x for x in records),
                anchor_status=dict(Counter(x["anchor_decision"]["status"] for x in records)),
                family_status={family: dict(Counter(x.get("families", {}).get(family, {}).get("status",
                    "NOT_ATTEMPTED_NO_ANCHOR") for x in records)) for family in saved["families"]},
                causal_navigation_schedule_sha256=sha(schedule), arc_events_sha256=sha(models / "ARC_EVENTS.json"),
                accepted_integer_measurement=False, model_failures_preserved=True)
            emit(seqout / "MODEL_COUNTS.json", item)
            summaries.append(item)
            state["sequences_completed"].append(name)
            state["status"] = "PREPARING"
            emit(out / "STATE.json", state)
            print(json.dumps(dict(event="SEQUENCE_COMPLETE", **item)), flush=True)
        registration(args.registration_commit, plan)
        for item in plan["native_dependencies"]:
            check_pin(expand(item["path"], roots), item["sha256"])
        require(state["converter_calls"] == 74 and state["prepare_calls"] == 3
                and state["prefixes_created"] == 37 and state["prefixes_reused"] == 12,
                "registered terminal invocation/prefix counts differ")
        state.update(status="COMPLETE", total_wall_s=time.monotonic()-started)
        emit(out / "SUMMARY.json", dict(**state, sequences=summaries,
            caveat="input models only; no integer selection, FIX, navigation or independent truth qualification"))
        emit(out / "STATE.json", state)
        emit(out / "COMPLETE.json", dict(status="COMPLETE", registration_commit=args.registration_commit,
            summary_sha256=sha(out / "SUMMARY.json"), converter_calls=74, prepare_calls=3))
    except BaseException as exc:
        state.update(status="FAILED_NO_RETRY", error=repr(exc), total_wall_s=time.monotonic()-started,
                     failure_scope="INPUT_MODEL_PREPARATION_NOT_NAVIGATION_ACCURACY")
        for models in out.glob("*/MODELS"):
            seal_path = models.parent / "MODEL_OUTPUT_SEAL_FAILED_PARTIAL.json"
            try:
                seal_models(models, seal_path, dict(registration_commit=args.registration_commit),
                            complete=False)
            except BaseException as seal_exc:
                state.setdefault("partial_seal_errors", []).append(repr(seal_exc))
        emit(out / "STATE.json", state)
        emit(out / "FAILED.json", dict(**state, traceback=traceback.format_exc()))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("roots", "carrier-root", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--registration-commit", required=True)
    main(parser.parse_args())
