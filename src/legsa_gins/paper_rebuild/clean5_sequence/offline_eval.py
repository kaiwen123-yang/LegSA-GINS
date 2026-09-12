"""C-05 identity gates, sequential offline evaluation and table-only decision inputs."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import resource

import yaml

from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from .evaluation_process import EVALUATOR_SHA256, evaluate, write_json
from .registry import load_registry
from .solver_seal import validate_output_seal

SEALS = {
    "BY2H": "e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5",
    "BY2O": "ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285",
}
SEAL_GATES = {
    "BY2H": "4be3cc8e2c40ad614ceb57ceb2be5206a6820b40362796a87d5e552858440fcc",
    "BY2O": "b5efd957b6d6565fe7287cc9d4ba7db417354ff54055ce5ab0d5e00e233add28",
}
RULE_SHA256 = "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce"


def read_json(path):
    def reject(value):
        raise ValueError("Nonfinite JSON: " + value)
    return json.loads(Path(path).read_text(), parse_constant=reject)


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def identity_root(registry):
    return registry.clean_root / "stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY"


def preflight(registry, dataset):
    stage = registry.clean_root / "stages" / registry.sequences[dataset].stage_id
    seal_dir = stage / "05_OUTPUT_SEAL_V2"
    seal_path, gate_path = seal_dir / "OUTPUT_SEAL.json", seal_dir / "SEAL_GATE.json"
    if sha256_file(seal_path) != SEALS[dataset] or sha256_file(gate_path) != SEAL_GATES[dataset]:
        raise RuntimeError("V2 seal/gate SHA256 mismatch: " + dataset)
    gate = read_json(gate_path)
    if gate["status"] != "PASS" or gate["completed_run_count"] != 5:
        raise RuntimeError("V2 seal gate not PASS")
    validation = validate_output_seal(seal_path)
    seal = read_json(seal_path)
    expected = {Path(row["relative_path"]).name: row["sha256"] for row in seal["registries"]}
    expected.update({"OUTPUT_SEAL.json": SEALS[dataset], "SEAL_GATE.json": SEAL_GATES[dataset]})
    if {p.name for p in seal_dir.iterdir()} != set(expected):
        raise RuntimeError("Unexpected V2 seal directory file set")
    for name, digest in expected.items():
        path = seal_dir / name
        if path.is_symlink() or sha256_file(path) != digest:
            raise RuntimeError("V2 seal directory hash mismatch: " + name)
    contract_path = registry.code_root / f"configs/paper_rebuild/clean5/CLEAN5_{dataset}_SEQUENCE_CONTRACT.yaml"
    contract = yaml.safe_load(contract_path.read_text())
    if contract != gate["contract"] or contract["contract_version"] != 2:
        raise RuntimeError("Contract differs from the V2 solver seal")
    rule = registry.code_root / "docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md"
    if sha256_file(rule) != RULE_SHA256:
        raise RuntimeError("Decision rule changed")
    provider = stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"
    yaw = stage / "02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json"
    if sha256_file(provider) != gate["provider_manifest_sha256"] or read_json(yaw) != read_json(provider)["physical_yaw_gate"]:
        raise RuntimeError("Frozen yaw gate/provider manifest changed")
    decision_hashes = {"yaw_gate": sha256_file(yaw)}
    if dataset == "BY2O":
        occlusion = stage / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json"
        if sha256_file(occlusion) != seal["occlusion_window_reference"]["sha256"]:
            raise RuntimeError("Preregistered occlusion file changed")
        decision_hashes["occlusion_window"] = sha256_file(occlusion)
    unique = csv_rows(seal_dir / "UNIQUE_RUN_TERMINAL_REGISTRY.csv")
    logical = csv_rows(seal_dir / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv")
    if len(unique) != 5 or len(logical) != 7 or any(row["terminal_status"] != "COMPLETED" for row in unique):
        raise RuntimeError("Sealed registry identities incomplete")
    return {"dataset_id": dataset, "stage": str(stage), "contract": contract,
            "contract_sha256": sha256_file(contract_path), "seal_directory_hashes": expected,
            "seal_validation": validation, "unique": unique, "logical": logical,
            "decision_source_hashes": decision_hashes}


def trace_lock(registry, dataset):
    path = registry.clean_root / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK_CLEAN5.csv"
    if sha256_file(path) != "faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67":
        raise RuntimeError("CLEAN5 raw lock SHA256 mismatch")
    relative = registry.sequences[dataset].trace_path.relative_to(registry.raw_root).as_posix()
    rows = [row for row in csv_rows(path) if row["relative_path"] == relative and row["dataset"] == dataset]
    if len(rows) != 1:
        raise RuntimeError("Trace missing or duplicated in raw lock")
    if registry.sequences[dataset].trace_path.stat().st_size != int(rows[0]["size_bytes"]):
        raise RuntimeError("Trace size differs from raw lock")
    return rows[0]


def run_header_gate(registry, local_config, root, script):
    from .header_evidence import audit_headers
    output = root / "HEADER_ONLY"
    output.mkdir(exist_ok=False)
    log = output / "HEADER_ONLY.strace"
    result = run_process_group(["env", "PYTHONDONTWRITEBYTECODE=1", "GIT_OPTIONAL_LOCKS=0",
        "strace", "-f", "-yy", "-s", "65535", "-e", "trace=openat,read,close", "-o", str(log),
        sys.executable, "-B", str(script), "--phase", "header", "--local-config", str(local_config)],
        cwd=registry.code_root, timeout_seconds=1800, timeout_message="Header audit timeout", launch_failure_message="Header audit launch failure")
    (output / "stdout.log").write_text(result.stdout)
    (output / "stderr.log").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError("Header child failed: " + result.stderr[-2000:])
    rows = read_json(output / "HEADER_ONLY_READS.json")
    audit = audit_headers(log, rows, cwd=registry.code_root, raw_root=registry.raw_root,
                          clean_root=registry.clean_root, output_root=output)
    required = {"lat": "lat", "lon": "lon", "height": "height", "yaw": "yaw"}
    selected_ok = all(all(row["selected_columns_by_archived_source"].get(key) == value for key, value in required.items()) for row in rows)
    identical = len({row["header_bytes_hex"] for row in rows}) == 1
    payload = {"passed": audit["passed"] and selected_ok, "header_bytes_identical": identical,
               "column_lists_identical": all(row["columns"] == rows[0]["columns"] for row in rows),
               "equivalence_basis": "identical headers plus C00 reproduction" if identical else "source resolution on each actual header plus synthetic selected/unselected-column contrast",
               "rows": rows, "strace": audit, "selected_columns_are_plain": selected_ok}
    write_json(output / "HEADER_GATE.json", payload)
    return payload


def run_identity(registry, local_config, attempt, evaluator, script):
    from .evaluator_identity import run_known_and_synthetic
    root = identity_root(registry)
    root.mkdir(parents=True, exist_ok=False)
    gate = {"status": "FAIL", "code_commit": git_head(registry.code_root),
            "evaluator_sha256": sha256_file(evaluator), "created_at": datetime.now(timezone.utc).isoformat(),
            "BY2H_BY2O_evaluator_execution_count_during_A2": 0}
    try:
        gate["sealed_inputs"] = {seq: preflight(registry, seq) for seq in ("BY2H", "BY2O")}
        if gate["evaluator_sha256"] != EVALUATOR_SHA256:
            raise RuntimeError("Archived evaluator SHA256 mismatch")
        # Lock metadata/stat only. No H/O trace content is read here.
        gate["trace_locks"] = {seq: trace_lock(registry, seq) for seq in ("BY2H", "BY2O")}
        gates = run_known_and_synthetic(registry, attempt, evaluator, root)
        gate.update(gates)
        if not gates["passed_known_and_synthetic"]:
            raise RuntimeError("A2-1/A2-2 failed")
        gate["A2_3"] = run_header_gate(registry, local_config, root, script)
        if not gate["A2_3"]["passed"]:
            raise RuntimeError("A2-3 header equivalence failed")
        gate["status"] = "PASS"
        gate["full_identity_gate"] = "PASS"
        gate["evidence_files"] = {name: sha256_file(root / name) for name in
            ("A2_1_C00_REPRODUCTION_GATE.json", "A2_2_SYNTHETIC_GATE.json", "HEADER_ONLY/HEADER_GATE.json")}
    except Exception as exc:
        gate["failure"] = str(exc)
        for name in ("A2_1_C00_REPRODUCTION_GATE.json", "A2_2_SYNTHETIC_GATE.json"):
            if (root / name).exists():
                gate[name] = read_json(root / name)
        write_json(root / "EVALUATOR_IDENTITY_GATE.json", gate)
        raise
    write_json(root / "EVALUATOR_IDENTITY_GATE.json", gate)
    return gate


def git_head(root):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def summary_checks(summary, row):
    checks = []
    required = {"position": {"north_rmse_m", "east_rmse_m", "up_rmse_m", "horizontal_rmse_m",
                             "position_3d_rmse_m", "horizontal_p95_m", "vertical_p95_m"},
                "attitude": {"roll_rmse_deg", "pitch_rmse_deg", "yaw_rmse_deg",
                             "roll_p95_deg", "pitch_p95_deg", "yaw_p95_deg"}}
    if any(not required[group].issubset(summary.get(group, {})) for group in required):
        raise RuntimeError("Missing required archived evaluator RMSE/P95 fields")
    for group in ("position", "attitude"):
        for name, value in summary[group].items():
            if "rmse" not in name and "p95" not in name:
                continue
            key = {"vertical_p95_m": "up_p95_absolute_m", "yaw_p95_deg": "yaw_p95_absolute_deg",
                   "roll_p95_deg": "roll_p95_absolute_deg", "pitch_p95_deg": "pitch_p95_absolute_deg"}.get(name, name)
            target = row.get(key)
            if target is None or not math.isfinite(float(target)) or not math.isfinite(float(value)):
                raise RuntimeError("Missing/nonfinite summary parity field " + key)
            delta = abs(float(value) - float(target))
            relative = delta / abs(float(target)) if target else (0.0 if delta == 0 else None)
            checks.append({"summary_field": group + "/" + name, "result_field": key,
                           "summary_value": value, "result_value": target, "relative_difference": relative,
                           "passed": relative is not None and relative <= 1e-10})
    if not checks or not all(item["passed"] for item in checks):
        raise RuntimeError("Evaluator summary versus Canonical statistics gate failed")
    return checks


def validate_identity_gate(path, *, code_commit):
    gate = read_json(path)
    if (gate.get("status") != "PASS" or gate.get("full_identity_gate") != "PASS"
            or gate.get("evaluator_sha256") != EVALUATOR_SHA256 or gate.get("code_commit") != code_commit):
        raise RuntimeError("A2 identity gate not PASS for this frozen code/evaluator")
    mapping = {"A2_1": "A2_1_C00_REPRODUCTION_GATE.json", "A2_2": "A2_2_SYNTHETIC_GATE.json",
               "A2_3": "HEADER_ONLY/HEADER_GATE.json"}
    for key, name in mapping.items():
        if gate.get(key, {}).get("passed") is not True:
            raise RuntimeError("A2 component gate not PASS: " + key)
        source = Path(path).parent / name
        if (not source.is_file() or sha256_file(source) != gate.get("evidence_files", {}).get(name)
                or read_json(source) != gate[key]):
            raise RuntimeError("A2 component evidence changed: " + key)
    headers = gate["A2_3"].get("strace", {})
    if (headers.get("passed") is not True or headers.get("trace_open_count") != 3
            or any(headers.get(key) != 0 for key in ("bag_open_count", "fpl_open_count", "data_line_bytes_read"))):
        raise RuntimeError("A2 header-only read audit invalid")
    if len(gate["A2_1"].get("runs", [])) != 2 or len(gate["A2_2"].get("runs", [])) != 4:
        raise RuntimeError("A2 evaluator evidence count invalid")
    return gate


def canonical_headers(attempt):
    from .evaluation_tables import CANONICAL_CSV_NAMES
    result = {}
    for name in CANONICAL_CSV_NAMES:
        root = "12_OFFLINE_EVALUATION" if name in ("UNIQUE_EVALUATION_RESULTS.csv", "LOGICAL_EVALUATION_RESULTS.csv") else "13_AGGREGATE"
        with (attempt / root / name).open(encoding="utf-8-sig", newline="") as handle:
            result[name] = next(csv.reader(handle))
    return result


def run_sequence(registry, dataset, evaluator, attempt):
    from ..canonical541 import offline_eval_aggregate as canonical
    from .evaluation_tables import compute_sequence_result, segment_rows, build_tables, write_tables
    gate_path = identity_root(registry) / "EVALUATOR_IDENTITY_GATE.json"
    gate = validate_identity_gate(gate_path, code_commit=git_head(registry.code_root))
    frozen = preflight(registry, dataset)
    lock = trace_lock(registry, dataset)
    stage = Path(frozen["stage"])
    root, aggregate = stage / "07_OFFLINE_EVALUATION", stage / "08_AGGREGATE"
    if root.exists() or aggregate.exists():
        raise RuntimeError("Existing evaluation/aggregate attempt; retry forbidden")
    root.mkdir()
    write_json(root / "PRE_EVALUATION.json", frozen)
    contract = frozen["contract"]
    window = {key: contract["window_contract"][key] for key in ("t_start", "t_end")}
    selected_header = next(row for row in gate["A2_3"]["rows"] if row["dataset_id"] == dataset)
    results, segments, run_gates = [], [], []
    started = time.monotonic()
    try:
        for source in frozen["unique"]:
            run_id = source["run_id"]
            output = stage / "04_SOLVER_RUNS_V2" / run_id
            if Path(source["output_root"]) != output:
                raise RuntimeError("Sealed run path identity mismatch")
            wrapper = read_json(output / "CLEAN5_FORMAL_RUN_MANIFEST.json")
            case = next(row for row in frozen["logical"] if row["run_id"] == run_id and row["method_id"] == source["method_id"])
            staging = root / ".work" / run_id
            evaluation = evaluate(evaluator=evaluator, trace=registry.sequences[dataset].trace_path,
                nav=output / "KF_GINS_Navresult.nav", std=output / "KF_GINS_STD.txt", outdir=staging,
                base_time=contract["time_contract"]["base_time"], window=list(window.values()), trace_sha256=lock["sha256"],
                code_root=registry.code_root, raw_root=registry.raw_root, clean_root=registry.clean_root)
            target = root / "PER_RUN" / run_id
            target.parent.mkdir(exist_ok=True)
            if target.exists():
                raise RuntimeError("Existing per-run evaluation target")
            staging.rename(target)
            evaluation["staging_outdir"] = str(staging)
            evaluation["outdir"] = str(target)
            capture = evaluation["capture"]
            if capture["trace_header"] != selected_header["columns"] or capture["selected_columns"] != selected_header["selected_columns_by_archived_source"]:
                raise RuntimeError("Runtime selected columns differ from the A2 header proof")
            row = compute_sequence_result(source, case, output, evaluation["outdir"], window=window,
                reference_epoch_count=capture["reference_epoch_count"], evaluation_runtime=evaluation["runtime_seconds"],
                evaluation_invoked=True, wrapper_runtime_seconds=wrapper["runtime_seconds"], wrapper_exit_code=wrapper["exit_code"])
            row.update(data_mode=registry.sequences[dataset].data_mode, synthetic_data_used=False,
                       semisynthetic_data_used=False, trace_used_online=False)
            if row["coverage_ratio"] is None or row["coverage_ratio"] < .99 or row["finite_ratio"] != 1:
                raise RuntimeError("Coverage/finite ratio gate failed")
            parity = summary_checks(evaluation["summary"], row)
            item = {"run_id": run_id, "status": "PASS" if capture["consistency"]["passed"] else "FAIL",
                    "coverage_ratio": row["coverage_ratio"], "finite_ratio": row["finite_ratio"],
                    "selected_columns": capture["selected_columns"], "summary_parity": parity,
                    "consistency": capture["consistency"], "strace": evaluation["audit"]}
            write_json(Path(evaluation["outdir"]) / "EVALUATION_GATE.json", item)
            run_gates.append(item)
            if item["status"] != "PASS":
                raise RuntimeError("MFIG00 consistency gate failed: " + run_id)
            results.append(row)
            segments.extend(segment_rows(canonical._read_error_series(Path(evaluation["outdir"])),
                registry=source, dataset_id=dataset, window=window, case_meta=case))
            print(f"{dataset}: {len(results)}/5 evaluated, gates PASS", flush=True)
        post = preflight(registry, dataset)
        write_json(root / "POST_EVALUATION.json", post)
        metadata = {"dataset_id": dataset, "data_mode": registry.sequences[dataset].data_mode,
                    "code_commit": git_head(registry.code_root), "window": window,
                    "evaluator_sha256": EVALUATOR_SHA256, "trace_sha256": lock["sha256"],
                    "identity_gate_sha256": sha256_file(gate_path), "output_seal_sha256": SEALS[dataset],
                    "run_gates": run_gates, "synthetic_data_used": False, "semisynthetic_data_used": False,
                    "total_wall_time_seconds": time.monotonic() - started,
                    "total_cpu_time_seconds": sum(resource.getrusage(resource.RUSAGE_CHILDREN)[:2])}
        tables = build_tables(results, frozen["logical"], segments, metadata=metadata)
        files = write_tables(aggregate, tables, canonical_headers=canonical_headers(attempt))
        write_json(root / "EVALUATION_SEQUENCE_GATE.json", {"status": "PASS", **metadata,
            "completed_evaluations": 5, "logical_result_count": 7, "retry_count": 0,
            "aggregate_files": files["files"], "decision_source_hashes": frozen["decision_source_hashes"],
            "post_seal_hashes_unchanged": post["seal_directory_hashes"] == frozen["seal_directory_hashes"]})
    except Exception as exc:
        write_json(root / "EVALUATION_SEQUENCE_GATE.json", {"status": "FAIL", "failure": str(exc),
            "completed_evaluations": len(results), "run_gates": run_gates, "retry_count": 0})
        raise


def run_decision(registry):
    from .decision_inputs import extract_decision_inputs
    stages = {seq: registry.clean_root / "stages" / registry.sequences[seq].stage_id for seq in ("BY2H", "BY2O")}
    gates = {}
    for seq, stage in stages.items():
        gates[seq] = read_json(stage / "07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json")
        if gates[seq]["status"] != "PASS":
            raise RuntimeError("Decision inputs require two completed evaluations")
        for name, entry in gates[seq]["aggregate_files"].items():
            if sha256_file(stage / "08_AGGREGATE" / name) != entry["sha256"]:
                raise RuntimeError("Frozen aggregate changed before decision extraction")
    paths = {"by2h_table": stages["BY2H"] / "08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
             "by2o_table": stages["BY2O"] / "08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
             "yaw_gate": stages["BY2H"] / "02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json",
             "occlusion_window": stages["BY2O"] / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json"}
    result = extract_decision_inputs(by2h_table=paths["by2h_table"], by2o_table=paths["by2o_table"],
        yaw_gate_path=paths["yaw_gate"], occlusion_window_path=paths["occlusion_window"],
        rule_path=registry.code_root / "docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
        expected_source_hashes={
            "by2h_table": gates["BY2H"]["aggregate_files"]["WINDOW_SEGMENT_SUMMARY.csv"]["sha256"],
            "by2o_table": gates["BY2O"]["aggregate_files"]["WINDOW_SEGMENT_SUMMARY.csv"]["sha256"],
            "yaw_gate": gates["BY2H"]["decision_source_hashes"]["yaw_gate"],
            "occlusion_window": gates["BY2O"]["decision_source_hashes"]["occlusion_window"]}, source_root=registry.clean_root)
    write_json(registry.clean_root / "stages/CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json", result)


def main(argv=None, *, execution_script=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("identity", "header", "evaluate", "decision"), default="evaluate")
    parser.add_argument("--sequence", choices=("BY2H", "BY2O"))
    parser.add_argument("--exact-evaluator", type=Path)
    parser.add_argument("--local-config", type=Path, default=Path("configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml"))
    args = parser.parse_args(argv)
    code = Path(__file__).resolve().parents[4]
    local = args.local_config.resolve(strict=True)
    registry = load_registry(code / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml", local)
    attempt = Path(yaml.safe_load(local.read_text())["paths"]["runtime_root"])
    try:
        if args.phase == "header":
            from .header_evidence import header_child
            header_child(registry, identity_root(registry) / "HEADER_ONLY")
        elif args.phase == "identity":
            run_identity(registry, local, attempt, args.exact_evaluator.resolve(strict=True), execution_script)
        elif args.phase == "decision":
            run_decision(registry)
        else:
            if not args.sequence or not args.exact_evaluator:
                parser.error("evaluation requires --sequence and --exact-evaluator")
            run_sequence(registry, args.sequence, args.exact_evaluator.resolve(strict=True), attempt)
        return 0
    except Exception as exc:
        print("CLEAN5_C05_FAIL_CLOSED: " + str(exc), file=sys.stderr, flush=True)
        return 1
