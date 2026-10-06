"""Read-only V3 identity checks. Never import/run a solver or read raw/reference payloads."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import yaml

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--local-paths", type=Path, required=True)
    args = parser.parse_args()
    raw_text = args.lock.read_text()
    lock = json.loads(raw_text)
    aliases = json.loads(args.local_paths.read_text())["aliases"]
    passed = 0
    def require(condition, label):
        nonlocal passed
        if not condition: raise ValueError(label)
        passed += 1
    def resolve(value):
        for token, base in sorted(aliases.items(), key=lambda x: -len(x[0])):
            if value == token or value.startswith(token + "/"):
                return Path(base) / value[len(token):].lstrip("/")
        raise ValueError("Unknown alias: " + value)
    def sha256(path):
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()
    require(lock["schema_version"] == "legsa.v3_baseline_lock.v1", "schema")
    require("/home/" not in raw_text and "/mnt/" not in raw_text and "G:\\" not in raw_text, "portable tracked paths")
    require(lock["verification"]["check_count"] == len(lock["verification"]["checks"])
            == lock["verification"]["passed_count"], "producer check count")
    require(all(x["passed"] for x in lock["verification"]["checks"]), "producer checks")
    require(lock["repository"]["main_not_modified"], "main protected")
    require(lock["scientific_freeze"] != lock["repository"]["authoritative_main_commit"], "science/main identities separated")
    seen = set()
    for pin in lock["file_pins"]:
        require(pin["path"] not in seen, "duplicate pin")
        seen.add(pin["path"])
        path = resolve(pin["path"])
        require(not path.is_relative_to(Path(aliases["<RAW_ROOT>"])), "raw hashing forbidden")
        require(path.is_file() and path.stat().st_size == pin["size_bytes"], "pin size: " + pin["role"])
        require(sha256(path) == pin["sha256"], "pin hash: " + pin["role"])
    registry = {x["run_id"]: x for x in json.loads(resolve(lock["registry"]["path"]).read_text())}
    require(len(registry) == lock["registry_native_count"] == 6468, "registry cardinality")
    expected_windows = {"BY2": [66.0, 340.0], "BY2H": [413.0, 683.0], "BY2O": [3186.0, 3563.0]}
    require(set(x["sequence_id"] for x in lock["sequences"]) == set(expected_windows), "sequence set")
    raw_stat_checks = 0
    for seq in lock["sequences"]:
        name = seq["sequence_id"]; reg = registry[seq["run_id"]]
        cfg = yaml.safe_load(resolve(seq["configuration"]["path"]).read_text())
        require(seq["full_window_s"] == expected_windows[name] == reg["evaluation"]["window"]
                == [cfg["starttime"], cfg["endtime"]], name + " full window")
        require(seq["base_time_unix_s"] == reg["evaluation"]["base_time"], name + " time base")
        require(seq["initialization"] == {k: v for k, v in cfg.items() if k.startswith("init")}, name + " initialization")
        require(seq["runtime_antenna_lever_frd_m"] == cfg["antlever"], name + " runtime physical point")
        for role, raw in seq["raw_files"].items():
            path = resolve(raw["path"])
            require(path.is_file() and path.stat().st_size == raw["current_size_bytes"], name + " raw stat only " + role)
            require(raw["registered_sha256"] == reg["raw_source_hashes"][role], name + " inherited raw hash " + role)
            raw_stat_checks += 1
        ev = seq["evaluation"]
        result = json.loads(resolve(ev["result"]["path"]).read_text())
        receipt = json.loads(resolve(ev["archive_receipt"]["path"]).read_text())
        capture = json.loads(resolve(ev["capture"]["path"]).read_text())
        require(result["row"]["evaluator_contract"] == ev["contract"] == "evaluator_contract_v3", name + " evaluation contract")
        require(result["row"]["source_nav_sha256"] == seq["native_output"]["nav_sha256_from_ledger"], name + " native identity")
        require(result["row"]["evaluator_sha256"] == lock["evaluator"]["sha256"], name + " evaluator identity")
        require(result["transform"] == ev["position_transform"], name + " full physical transform")
        require(result["transform"]["lever_frd_m"] == [.03, .03-ev["baseline_median_m"]/2, -.30], name + " lever formula")
        require(not result["transform"]["fit_used"] and not result["transform"]["std_transformed"], name + " no fit/untransported STD")
        require(capture["window"] == seq["full_window_s"] and capture["trace_sha256"] == ev["reference"]["sha256"]
                == reg["evaluation"]["trace"]["sha256"], name + " reference metadata only")
        require(receipt["files"]["EVALUATION_RESULT.json"]["sha256"] == ev["result"]["sha256"], name + " result receipt binding")
        require(receipt["files"]["FROZEN_EVALUATOR/error_series.csv"]["sha256"] == ev["retained_error_series"]["sha256"],
                name + " compressed series receipt binding")
        require(ev["matched_time_start_s"] == result["row"]["time_start"]
                and ev["matched_time_end_s"] == result["row"]["time_end"], name + " matched support")
    require(not lock["degradation_contract"]["raw_carrier_observations_mutated_by_v3_faults"], "fault-layer distinction")
    require(lock["verification"]["raw_files_rehashed"] == lock["verification"]["reference_payload_reads"]
            == lock["verification"]["solver_calls"] == lock["verification"]["evaluator_calls"] == 0, "no science execution")
    print(json.dumps({"status": "PASS", "validation_checks_passed": passed,
                      "hashed_nonraw_files": len(seen), "raw_stat_only_files": raw_stat_checks,
                      "raw_files_rehashed": 0, "reference_payload_reads": 0,
                      "solver_calls": 0, "evaluator_calls": 0}, indent=2))

if __name__ == "__main__":
    main()
