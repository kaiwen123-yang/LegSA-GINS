#!/usr/bin/env python3
"""Build/run new synthetic fixtures once; retain every process and negative control."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = Path(__file__).resolve().parent
    repo = Path(__file__).resolve().parents[6]
    aliases = json.loads((repo / "configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json").read_text())["aliases"]
    build_root = Path(aliases["<VALIDATION_BUILD_ROOT>"])
    fixture_root = build_root / "fixtures_N16_ONLY"
    fixture_root.mkdir(exist_ok=False)
    candidate = build_root / "source_N16_ONLY"
    observed = Path(aliases["<OBSERVED_SOURCE>"])
    common_targets = [candidate / "cpp/legsa_v23_port_core" / p for p in [
        "include/legsa_v23_port_core/kf_gins/covariance_diagnostics.hpp",
        "src/kf_gins/gi_engine.cpp", "src/kf_gins/gi_observer.cpp"]]
    for path in common_targets:
        assert path.resolve().is_relative_to(candidate.resolve())
        assert not any(parent.is_symlink() for parent in [path, *path.parents])

    def portable(value):
        value = str(value)
        for key, root in sorted(aliases.items(), key=lambda item: -len(item[1])):
            value = value.replace(root, key)
        return value

    def dump(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    sources = {
        "baseline": (observed, Path(aliases["<MECHANISM_BUILD_ROOT>"]) / "build_observed/liblegsa_v23_port_core.a"),
        "candidate": (candidate, build_root / "build_N16_ONLY/liblegsa_v23_port_core.a"),
    }
    receipt = {"candidate": "N16_ONLY", "data_mode": "synthetic_fixture_only",
               "synthetic_data_used": True, "semisynthetic_data_used": False,
               "real_native_calls": 0, "evaluator_calls": 0, "provider_calls": 0,
               "real_payload_reads": 0, "compiles": [], "fixture_processes": [],
               "common_target_containment": "3/3 regular targets and parents; no symlink; inside candidate source",
               "compiler": subprocess.run(["g++", "-dumpfullversion"], check=True, capture_output=True, text=True).stdout.strip(),
               "fixture_source_sha256": digest(out / "native_fixture.cpp"),
               "retry_count": 0, "status": "BUILDING_FIXTURES"}
    assert receipt["compiler"] == "11.4.0"
    for label, (source, library) in sources.items():
        binary = fixture_root / ("fixture_" + label)
        command = ["g++", "-std=c++17", "-O3", "-DNDEBUG", "-I" + str(source / "cpp/legsa_v23_port_core/include")]
        if label == "candidate":
            command.append("-DN16_ACTIVE_AXES=1")
        command += [str(out / "native_fixture.cpp"), str(library), "-o", str(binary)]
        log = fixture_root / ("compile_" + label + ".log")
        start = time.monotonic()
        with log.open("x") as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        row = {"label": label, "command": [portable(x) for x in command], "exit_code": process.returncode,
               "elapsed_seconds": time.monotonic() - start, "log": portable(log),
               "linked_library": portable(library), "linked_library_sha256": digest(library)}
        if binary.exists():
            row["binary_sha256"] = digest(binary)
        receipt["compiles"].append(row)
        dump("FIXTURE_RECEIPT.json", receipt)
        if process.returncode:
            receipt["status"] = "FIXTURE_COMPILE_FAILED"
            dump("FIXTURE_RECEIPT.json", receipt)
            raise SystemExit(process.returncode)

    for label, binary_label, observation in [("baseline", "baseline", "observer_on"),
                                             ("candidate_off", "candidate", "observer_off"),
                                             ("candidate_on", "candidate", "observer_on")]:
        target = fixture_root / label
        command = [str(fixture_root / ("fixture_" + binary_label)), str(target), observation]
        row = {"label": label, "command": [portable(x) for x in command], "native_fixture_exec_count": 1,
               "real_native_exec_count": 0, "status": "STARTED", "output": portable(target)}
        receipt["fixture_processes"].append(row)
        receipt["status"] = "RUNNING_SYNTHETIC_FIXTURES"
        dump("FIXTURE_RECEIPT.json", receipt)
        start = time.monotonic()
        with (fixture_root / (label + ".stdout")).open("x") as stdout, (fixture_root / (label + ".stderr")).open("x") as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr)
        row.update(exit_code=process.returncode, elapsed_seconds=time.monotonic() - start,
                   status="COMPLETED" if process.returncode == 0 else "FAILED_RETAINED")
        dump("FIXTURE_RECEIPT.json", receipt)
        if process.returncode:
            receipt["status"] = "NATIVE_FIXTURE_FAILED_RETAINED"
            dump("FIXTURE_RECEIPT.json", receipt)
            raise SystemExit(process.returncode)

    checks = []
    def check(name, passed, detail):
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    policy = {}
    for label in ["baseline", "candidate_off", "candidate_on"]:
        path = fixture_root / label / "POLICY_RESULTS.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines()]
        policy[label] = {r["case"]: r for r in records}
        check(label + " unique policy cases", len(policy[label]) == len(records), str(len(records)))
        check(label + " metadata std bytes preserved", all(r["std_bytes_preserved"] for r in records), "all 3 stored std values unchanged")
    old, new = policy["baseline"], policy["candidate_on"]
    check("policy scenario identities equal", old.keys() == new.keys(), "same newly generated synthetic cases")
    check("policy candidate observer toggle parity", (fixture_root / "candidate_off/POLICY_RESULTS.jsonl").read_bytes() == (fixture_root / "candidate_on/POLICY_RESULTS.jsonl").read_bytes(), "byte-identical direct policy result JSONL")
    for name, row in new.items():
        check(name + " active mask preserved", row["actual_mask"] == row["requested_mask"], "new interface records requested quality domain")
        if row["three_dimensional_control"]:
            check(name + " old 3D scientific result", row["scientific"] == old[name]["scientific"], "all weights/scores/reasons/acceptance/statistic fields exact; metadata-summary extension separate")
    failures = []
    for name in [x for x in new if x.startswith("inactive_D_")]:
        r = new[name]["scientific"]
        ok = r["lsim_R_scale"] == r["combined_R_scale"] == 1.0 and r["accepted"] and not r["rejected"]
        check(name + " inactive D has no effect", ok and "lsim_std_nonfinite_or_missing" not in r["reason_codes"] and "lsim_go2_horizontal_velocity_std_high" not in r["reason_codes"], "nominal N/E; original D retained")
        original = old[name]["scientific"]
        old_conforms = original["lsim_R_scale"] == 1.0 and "lsim_std_nonfinite_or_missing" not in original["reason_codes"]
        if not old_conforms:
            failures.append({"case": name, "status": "EXPECTED_OLD_CONTRACT_FAILURE_RETAINED", "baseline_lsim": original["lsim_R_scale"], "candidate_lsim": r["lsim_R_scale"], "baseline_reasons": original["reason_codes"]})
    check("six old inactive-domain counterexamples retained", len(failures) == 6, "999/NaN/Inf/-Inf/zero/negative inactive D")
    for name in [x for x in new if x.startswith("active_N_") or x.startswith("active_E_")]:
        r = new[name]["scientific"]
        check(name + " invalid active value remains protected", r["lsim_R_scale"] >= 1.5 and "lsim_std_nonfinite_or_missing" in r["reason_codes"], "original std-invalid protection; not forced nominal or forced reject")
    for name in ["empty_active_domain", "other_quality_remains_1p5", "time_quality_remains_1p5", "covariance_missing_remains_1p5"]:
        check(name + " preserves protection", new[name]["scientific"]["lsim_R_scale"] == 1.5, "no collapse of unrelated quality factors to 1")
    check("empty domain not valid", "lsim_std_nonfinite_or_missing" in new["empty_active_domain"]["scientific"]["reason_codes"], "finiteStd empty=false; original n6b protection path")
    check("at least one active axis valid", new["single_E_active"]["scientific"]["lsim_R_scale"] == 1.0, "inactive N NaN and D Inf ignored")
    check("active threshold remains strict", new["active_std_at_10"]["scientific"]["lsim_R_scale"] == 1.0 and new["active_std_above_10"]["scientific"]["lsim_R_scale"] == 2.0, "10 and nextafter(10,+Inf)")
    for name in ["provider_unavailable_rejected", "invalid_source_rejected"]:
        check(name, new[name]["scientific"]["rejected"] and not new[name]["scientific"]["accepted"], "other source-validity decisions remain")
    for name in ["oim_masks_lsim_change", "cap_masks_lsim_change"]:
        check(name, new[name]["scientific"]["lsim_R_scale"] == 1.5 and old[name]["scientific"]["lsim_R_scale"] == 2.0 and new[name]["scientific"]["combined_R_scale"] == old[name]["scientific"]["combined_R_scale"], "LSIM changes but final R multiplier does not")
    for name in ["sa_off", "source_off", "lsim_off", "mode_off"]:
        check(name, new[name]["scientific"] == old[name]["scientific"] and new[name]["scientific"]["combined_R_scale"] == 1.0, "disabled path unchanged")

    integration_names = sorted(p.name for p in (fixture_root / "candidate_on").iterdir() if p.is_dir())
    snapshots = {}
    for label in ["baseline", "candidate_on"]:
        for name in integration_names:
            path = fixture_root / label / name / "observer/events.jsonl"
            events = [json.loads(line) for line in path.read_text().splitlines()]
            check(label + "/" + name + " stream complete", [x["event_seq"] for x in events] == list(range(1, len(events) + 1)) and events[0]["event"] == "OBSERVER_BEGIN" and events[-1]["event"] == "OBSERVER_END" and events[-1]["data"]["prior_event_count"] == len(events) - 1, "new fixture log read once; no real events read")
            selected = [x for x in events if x["event"] == "SA_EVALUATION" and x["data"]["context"]["source"] == "go2_horizontal_velocity"]
            check(label + "/" + name + " one HV policy event", len(selected) == 1, "actual GIEngine helper and policy, not duplicated test formula")
            if selected:
                snapshots[label, name] = selected[0]["data"]["snapshot"]
            if label == "candidate_on":
                check(name + " full P observation coverage", sum(x["event"] == "COVARIANCE_HEALTH" for x in events) == 3, "three synthetic newImuProcess ends; common diagnostic exercised")
                check(name + " candidate identity", sum(x["event"] == "CANDIDATE_DEFINITION" for x in events) == 1, "common layer installed once")
                check(name + " other-source default mask", all(x["data"]["snapshot"]["metadata"]["std_active_axes"] == [True, True, True] for x in events if x["event"] == "SA_EVALUATION" and x["data"]["context"]["source"] != "go2_horizontal_velocity"), "other source stays three-dimensional")
    for name in integration_names:
        off = fixture_root / "candidate_off" / name / "SCIENTIFIC_STATE.csv"
        on = fixture_root / "candidate_on" / name / "SCIENTIFIC_STATE.csv"
        check(name + " observation no interference", off.read_bytes() == on.read_bytes(), "full state/quaternion/Cbn/bias/scale/P and scientific counters exact")
        if ("candidate_on", name) not in snapshots:
            continue
        snap = snapshots["candidate_on", name]
        two = name.startswith("hv2d")
        check(name + " actual matrix dimension sets mask", snap["metadata"]["std_active_axes"] == ([True, True, False] if two else [True, True, True]) and snap["H"]["rows"] == (2 if two else 3) and snap["base_R"]["rows"] == (2 if two else 3), "actual H/R, not the vertical-disabled flag alone")
        if name in ["hv2d_sentinel999", "hv3d_sentinel_D"]:
            check(name + " sentinel still 999", snap["metadata"]["std_xyz"][2] == 999.0, "not rewritten to zero")
    for name in ["hv2d_ordinary_D", "hv2d_nan_D", "hv2d_inf_D"]:
        check(name + " actual 2D state invariant", (fixture_root / "candidate_on" / name / "SCIENTIFIC_STATE.csv").read_bytes() == (fixture_root / "candidate_on/hv2d_sentinel999/SCIENTIFIC_STATE.csv").read_bytes(), "only inactive provider D differs; old positiveStd preprocessing retained")
    for name in ["hv3d_ordinary_D", "hv3d_sentinel_D", "hv2d_sa_off", "hv2d_source_off", "hv2d_ordinary_D", "hv2d_cap_masked"]:
        check(name + " baseline negative control", (fixture_root / "baseline" / name / "SCIENTIFIC_STATE.csv").read_bytes() == (fixture_root / "candidate_on" / name / "SCIENTIFIC_STATE.csv").read_bytes(), "expected unchanged scientific state and counters")
    for name in ["hv2d_sentinel999", "hv2d_quality_1p5", "hv2d_inf_D"]:
        check(name + " active-domain change reaches update", (fixture_root / "baseline" / name / "SCIENTIFIC_STATE.csv").read_bytes() != (fixture_root / "candidate_on" / name / "SCIENTIFIC_STATE.csv").read_bytes(), "synthetic positive control only; no real performance inference")
    cap_new = snapshots.get(("candidate_on", "hv2d_cap_masked"), {})
    cap_old = snapshots.get(("baseline", "hv2d_cap_masked"), {})
    check("actual helper cap masking", bool(cap_new) and cap_new["result"]["lsim_R_scale"] == 1.5 and cap_old["result"]["lsim_R_scale"] == 2.0 and cap_new["result"]["combined_R_scale"] == cap_old["result"]["combined_R_scale"] == 10.0, "same actual effective R despite changed metadata LSIM")
    with (out / "CHECKS.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "status", "detail"], lineterminator="\n")
        writer.writeheader(); writer.writerows(checks)
    dump("OLD_CONTRACT_COUNTEREXAMPLES.json", failures)
    failed = sum(row["status"] == "FAIL" for row in checks)
    receipt.update(status="PASS" if not failed else "VALIDATION_FAILED_RETAINED", checks=len(checks), failed_checks=failed,
                   policy_scenarios_per_process=len(new), integration_scenarios_per_process=len(integration_names),
                   native_fixture_process_count=len(receipt["fixture_processes"]),
                   scenario_executions=sum(len(policy[x]) + len(integration_names) for x in policy),
                   old_target_contract_failures_retained=len(failures),
                   three_dimensional_control_cases=sum(x["three_dimensional_control"] for x in new.values()),
                   fixture_logs_read="new pure-synthetic logs only; once each",
                   covariance_common_suite="separate root-owned receipt; not counted as this candidate's tests")
    dump("FIXTURE_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in ["status", "checks", "failed_checks", "native_fixture_process_count", "policy_scenarios_per_process", "integration_scenarios_per_process", "scenario_executions", "old_target_contract_failures_retained"]}))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
