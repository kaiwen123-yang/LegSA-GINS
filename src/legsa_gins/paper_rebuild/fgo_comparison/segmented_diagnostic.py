"""Separately identified OiSAM diagnostics on every source-continuous block.

This is an engineering missing-input policy, never the single-initialization
paper profile. Blocks are determined before execution; numerical failure stops
only that block and does not add another initialization inside it. No reference
is read here. Initial prior-only positions remain explicit secondary output.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile

import numpy as np

from .oisam_inputs import read_sequence
from .raw_inputs import aliases, dump, sha256
from .runner import deny_reference_access, json_safe, write_csv, hardware


def partition_intervals(intervals, nodes, maximum_dt=.1, tolerance=1e-7):
    """Preserve all continuous blocks and assign original, unretimed nodes.

    An epoch inside a missing interval has no block. An epoch after a real gap
    may initialize its new independent block; it is not a propagated solution.
    A gap between two nominal epochs still separates their graph histories.
    """
    values = np.asarray(intervals, float)
    if values.ndim != 2 or values.shape[1] != 2 or not len(values):
        raise ValueError("IMU_INTERVAL_SCHEMA")
    duration = values[:, 1] - values[:, 0]
    if not np.isfinite(values).all() or np.any(duration <= 0) or np.any(duration > maximum_dt):
        raise ValueError("IMU_INTERVAL_INVALID")
    discontinuity = values[1:, 0] - values[:-1, 1]
    if np.any(discontinuity < -tolerance):
        raise ValueError("IMU_INTERVAL_OVERLAP_OR_REORDER")
    starts = np.r_[0, np.flatnonzero(discontinuity > tolerance) + 1]
    ends = np.r_[starts[1:] - 1, len(values) - 1]
    blocks, assignment = [], np.full(len(nodes), -1, int)
    times = np.asarray([item[0] for item in nodes], float)
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("DIAGNOSTIC_NODE_TIME_INVALID")
    for number, (start, end) in enumerate(zip(starts, ends), 1):
        left, right = float(values[start, 0]), float(values[end, 1])
        indices = np.flatnonzero((times >= left) & (times <= right))
        if np.any(assignment[indices] != -1):
            raise ValueError("CONTINUOUS_BLOCK_DUPLICATE_NODE")
        assignment[indices] = number
        blocks.append({"block_id": number, "imu_interval_first_index": int(start),
                       "imu_interval_last_index": int(end), "start_s": left, "end_s": right,
                       "node_indices": indices.tolist(), "scheduled_nodes": len(indices),
                       "first_node_s": float(times[indices[0]]) if len(indices) else None,
                       "last_node_s": float(times[indices[-1]]) if len(indices) else None})
    return blocks, assignment


def execute_blocks(inputs, config, *, executor=None, graph_factory=None):
    """Attempt ALL preregistered blocks, retaining every original node row."""
    if executor is None:
        from .oisam import run_inputs
        executor = run_inputs
    if config.get("gap_policy") != "strict_single_initialization_no_gap_bridge":
        raise ValueError("INNER_BLOCK_MUST_USE_STRICT_POLICY")
    blocks, assignment = partition_intervals(inputs.imu_intervals, inputs.nodes,
                                              config["maximum_imu_interval_s"])
    rows = [[item[0], *([float("nan")] * 9), 0, "NO_CONTINUOUS_IMU_SUPPORT"]
            for item in inputs.nodes]
    events, records = [], []
    for block in blocks:
        indices = block["node_indices"]
        selected = replace(inputs, nodes=[inputs.nodes[i] for i in indices])
        cursor = 0

        def state(values):
            nonlocal cursor
            if cursor >= len(indices) or float(values[0]) != inputs.nodes[indices[cursor]][0]:
                raise ValueError("BLOCK_OUTPUT_IDENTITY_OR_COUNT")
            rows[indices[cursor]] = list(values)
            cursor += 1

        def event(values):
            events.append({**values, "block_id": block["block_id"],
                           "history_identity": "INDEPENDENT_TRUE_GAP_BLOCK"})

        result = executor(selected, config, state, event, graph_factory=graph_factory)
        if cursor != len(indices) or result["actual_rows"] != len(indices):
            raise ValueError("BLOCK_MISSING_SCHEDULED_OUTPUT_ROWS")
        initializations = []
        for item in result["segments"]:
            stamp = item["start_s"]
            candidates = [n for n in selected.nodes if n[0] == stamp]
            if len(candidates) != 1 or candidates[0][1] is None:
                raise ValueError("INITIALIZATION_SENSOR_IDENTITY")
            row = candidates[0][1]
            initializations.append({**item, "block_id": block["block_id"],
                "gnss_provider_time_rel_s": float(row[0]),
                "initialization_expected_second": int(candidates[0][2]),
                "position_llh_deg_m": row[1:4].tolist(), "position_std_ned_m": row[4:7].tolist(),
                "velocity_gnss1_ned_mps": row[7:10].tolist(), "velocity_std_ned_mps": row[10:13].tolist(),
                "yaw_deg": float(row[13]), "yaw_std_deg": float(row[14]),
                "reference_used": False, "prior_only_output_is_dynamic_solution": False})
        if len(initializations) > 1:
            raise ValueError("FORBIDDEN_WITHIN_BLOCK_REINITIALIZATION")
        dynamic = sum(bool(rows[i][10]) and rows[i][11] != "INITIALIZED" for i in indices)
        records.append({**block, "attempted": True, "actual_rows": cursor,
                        "prior_only_count": len(initializations), "dynamic_valid_nodes": dynamic,
                        "singleton_prior_only": len(indices) == 1 and len(initializations) == 1,
                        "initializations": initializations, "execution": result})
    for index in np.flatnonzero(assignment < 0):
        events.append({"time_rel_s": inputs.nodes[index][0], "expected_second": inputs.nodes[index][2],
                       "block_id": None, "mode": "UNAVAILABLE", "reason": "NO_CONTINUOUS_IMU_SUPPORT"})
    if len(events) != len(inputs.nodes):
        raise ValueError("DIAGNOSTIC_EVENT_COUNT")
    events.sort(key=lambda item: item["time_rel_s"])
    return rows, events, records


def graph_diagnostics(target, directory):
    """Observe the requested actual epoch, without changing any solver option."""
    from .oisam import OiSAMGraph, normal_system

    class DiagnosticGraph(OiSAMGraph):
        def capture(self, phase):
            normal, rhs = normal_system(self.factors, self.values, self.indices)
            diagonal = normal.diagonal()
            scale = 1.0 / np.sqrt(np.maximum(diagonal, 1e-24))
            scaled = normal.scaled(scale).dense()
            eigenvalues = np.linalg.eigvalsh((scaled + scaled.T) / 2)
            maximum = float(eigenvalues[-1])
            positive = eigenvalues[eigenvalues > maximum * 1e-12]
            families = {}
            for factor in self.factors:
                jac, residual = factor.linearize(self.values).jacobian()
                family = f"{type(factor).__name__}:dim{len(residual)}:keys{len(factor.keys())}"
                entry = families.setdefault(family, {"factor_count": 0, "residual_squared_sum": 0.0})
                entry["factor_count"] += 1
                entry["residual_squared_sum"] += float(residual @ residual)
            destination = directory / (str(int(target)) + "_" + phase)
            np.savez_compressed(str(destination) + ".npz", scaled_normal=scaled, scaled_rhs=rhs*scale,
                                normal_diagonal=diagonal, eigenvalues=eigenvalues)
            dump(str(destination) + ".json", {"time_rel_s": target, "phase": phase,
                "state_indices": self.indices, "dimension": len(rhs), "factors": families,
                "factor_half_squared_residual_cost": sum(v["residual_squared_sum"] for v in families.values())/2,
                "scaled_normal_rank_relative_1e_12": len(positive), "scaled_normal_eigenvalue_min": float(eigenvalues[0]),
                "scaled_normal_eigenvalue_max": maximum,
                "scaled_normal_condition_positive": maximum/float(positive[0]) if len(positive) else None,
                "condition_note": "Normal-matrix condition; approximately squared Jacobian condition. Diagnostic only, not an admission threshold.",
                "solver_options_unchanged": True, "reference_read_count": 0})

        def _relinearize(self, diagnostics):
            requested = diagnostics.get("time_rel_s") == target
            if requested:
                self.capture("CERES_INITIAL")
            super()._relinearize(diagnostics)
            if requested:
                self.capture("CERES_FINAL")

        def step(self, timestamp, row, pieces):
            result = super().step(timestamp, row, pieces)
            if timestamp == target:
                self.capture("STEP_OUTPUT")
                dump(directory / "TARGET_EVENT.json", {**result,
                     "new_history_not_identical_old_problem": True,
                     "initialization_source": self.config.get("initialization_information"),
                     "requested_time_rel_s": target, "actual_time_rel_s": timestamp})
            return result
    return DiagnosticGraph


def verify_sources(code, protocol):
    files = list((code/"src/legsa_gins").rglob("*.py"))
    files += list((code/"src/legsa_gins/paper_rebuild/fgo_comparison").glob("*.cc"))
    files += list((code/"src/legsa_gins/paper_rebuild/fgo_comparison").glob("*.c"))
    if {str(path.relative_to(code)) for path in files} != set(protocol["execution_source_hashes"]):
        raise ValueError("SEGMENTED_SOURCE_INVENTORY_CHANGED")
    actual = {name: sha256(code/name) for name in protocol["execution_source_hashes"]}
    if actual != protocol["execution_source_hashes"]:
        raise ValueError("SEGMENTED_SOURCE_PIN_MISMATCH")
    configuration = code/protocol["method_config_path"]
    if sha256(configuration) != protocol["method_config_sha256"]:
        raise ValueError("SEGMENTED_METHOD_CONFIG_PIN_MISMATCH")
    if sha256(code/protocol["execution_contract_path"]) != protocol["execution_contract_sha256"]:
        raise ValueError("SEGMENTED_EXECUTION_CONTRACT_PIN_MISMATCH")
    bridge = os.environ.get("LEGSA_OBGINS_BRIDGE")
    if not bridge or sha256(bridge) != protocol["bridge_sha256"] or sha256(Path(bridge).with_suffix(".build.json")) != protocol["bridge_build_receipt_sha256"]:
        raise ValueError("SEGMENTED_BRIDGE_PIN_MISMATCH")
    receipt = json.loads(Path(bridge).with_suffix(".build.json").read_text())
    if any(sha256(name) != digest for name, digest in receipt["source_sha256"].items()):
        raise ValueError("SEGMENTED_UPSTREAM_BUILD_SOURCE_CHANGED")
    return actual, configuration


def run_native(roots_path, protocol_path, sequence):
    roots = aliases(roots_path)
    code, stage = Path(roots["<CODE_ROOT>"]), Path(roots["<FGO_DIAGNOSTIC_ROOT>"])
    protocol = json.loads(Path(protocol_path).read_text())
    if sequence not in protocol["new_native_sequences"] or protocol["status"] != "PREREGISTERED":
        raise ValueError("UNREGISTERED_DIAGNOSTIC_RUN")
    source_hashes, configuration = verify_sources(code, protocol)
    denied = deny_reference_access(roots)
    config = json.loads(configuration.read_text())
    started = time.perf_counter()
    inputs = read_sequence(roots_path, sequence, config)
    blocks, assignment = partition_intervals(inputs.imu_intervals, inputs.nodes, config["maximum_imu_interval_s"])
    if blocks != protocol["block_plan"][sequence]:
        raise ValueError("SEGMENTED_BLOCK_PLAN_MISMATCH")
    if inputs.metadata != protocol["input_metadata"][sequence]:
        raise ValueError("SEGMENTED_INPUT_IDENTITY_MISMATCH")
    output = stage/"runs"/sequence/"OISAM"/"SEGMENTED_DIAGNOSTIC"
    output.mkdir(parents=True, exist_ok=False)
    # G uses 256KiB allocation units: thousands of loose snapshot files would
    # exceed the registered storage budget despite their small logical size.
    with zipfile.ZipFile(output/"SOURCE_SNAPSHOT.zip", "x", compression=zipfile.ZIP_DEFLATED) as snapshot:
        for name in source_hashes:
            snapshot.writestr(name, (code/name).read_bytes())
        for name in (protocol["method_config_path"], protocol["execution_contract_path"]):
            snapshot.writestr(name, (code/name).read_bytes())
    (output/"PREREGISTRATION.json").write_bytes(Path(protocol_path).read_bytes())
    target = protocol["target_epoch_diagnostics"].get(sequence)
    diagnostic = output/"TARGET_DIAGNOSTICS"
    diagnostic.mkdir()
    factory = graph_diagnostics(target, diagnostic) if target is not None else None
    graph_started = time.perf_counter()
    rows, events, records = execute_blocks(inputs, config, graph_factory=factory)
    graph_elapsed = time.perf_counter()-graph_started
    from .oisam import STATE_COLUMNS
    augmented = []
    for index, row in enumerate(rows):
        augmented.append(dict(zip(STATE_COLUMNS + ["block_id", "prior_only", "dynamic_valid"],
            [*row, int(assignment[index]) if assignment[index] > 0 else None,
             int(bool(row[10]) and row[11] == "INITIALIZED"),
             int(bool(row[10]) and row[11] != "INITIALIZED") ])))
    write_csv(output/"STATES.csv", augmented)
    with (output/"SOLVER_EVENTS.jsonl").open("x") as stream:
        for event in events:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
    dump(output/"BLOCKS.json", json_safe(records))
    if verify_sources(code, protocol)[0] != source_hashes:
        raise ValueError("SEGMENTED_SOURCE_CHANGED_DURING_NATIVE")
    run = {"schema": "fgo.segmented.diagnostic.native.v1", "sequence": sequence, "method": "OISAM",
        "attempt": "SEGMENTED_DIAGNOSTIC", "mode": "ALL_SOURCE_CONTINUOUS_BLOCKS_INDEPENDENTLY_INITIALIZED",
        "terminal_status": "ALL_BLOCKS_ATTEMPTED_WITH_FAILURES" if any(r["execution"]["numerical_failure"] for r in records) else "ALL_BLOCKS_ATTEMPTED",
        "planned_blocks": len(blocks), "attempted_blocks": len(records),
        "initialization_count": sum(len(r["initializations"]) for r in records),
        "A1_yaw_initialization_count": sum(len(r["initializations"]) for r in records),
        "expected_nodes": len(inputs.nodes), "actual_rows": len(rows),
        "finite_nodes": sum(bool(r[10]) for r in rows),
        "dynamic_valid_nodes": sum(bool(r[10]) and r[11] != "INITIALIZED" for r in rows),
        "native_process_count": 1, "evaluator_process_count": 0, "reference_payload_reads": 0,
        "reference_paths_denied": denied, "trace_used_online": False, "synthetic_data_used": False,
        "semisynthetic_data_used": False, "per_case_tuning": False, "epoch_deleted_for_metric": False,
        "solver_and_adapter_elapsed_s": time.perf_counter()-started,
        "graph_execution_elapsed_s": graph_elapsed,
        "timing_scope": "adapter elapsed includes raw time decoding, snapshot copy and post-pin verification; graph time separately reported; neither is online worst-case latency",
        "hardware": hardware(),
        "maximum_imu_endpoint_wait_s": max((r["execution"]["maximum_imu_endpoint_wait_s"] for r in records), default=0.0),
        "future_gnss_factors_used": False, "historical_output_revised": False,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=code, text=True).strip(),
        "config_hash": sha256(configuration), "protocol_sha256": sha256(protocol_path),
        "bridge_sha256": protocol["bridge_sha256"], "bridge_build_receipt_sha256": protocol["bridge_build_receipt_sha256"],
        "implementation_source_hashes": source_hashes, "source_identity": "exact preregistered snapshot, including dependency superset",
        "source_snapshot_format": "lossless ZIP, all member SHA256 checked against preregistration at native seal",
        "input_provenance": inputs.metadata, "output_point": "IMU",
        "source_continuity_failure_policy": "no reset within a block; every separately preregistered true-gap block attempted",
        "prior_only_primary_support": False,
        "output_hashes": {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file() and "SOURCE_SNAPSHOT" not in path.parts}}
    dump(output/"RUN.json", json_safe(run))
    return run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--sequence", required=True, choices=["BY2", "BY2H", "BY2O"])
    args = parser.parse_args()
    result = run_native(args.roots, args.protocol, args.sequence)
    print(json.dumps({k: result[k] for k in ("sequence", "terminal_status", "attempted_blocks", "finite_nodes", "dynamic_valid_nodes")}), flush=True)


if __name__ == "__main__":
    main()
