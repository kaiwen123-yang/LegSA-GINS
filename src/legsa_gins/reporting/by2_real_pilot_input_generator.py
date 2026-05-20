"""N9B1A real pilot input generator and WSL bridge precheck."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    discover_cleaned_matrix_root,
    load_csv_rows,
    load_matrix_bundle,
)

STAGE = "N9B1A_REAL_PILOT_INPUT_GENERATOR_AND_WSL_BRIDGE_PRECHECK"
AUDIT_ROOT_NAME = "by2\u6570\u636e\u96c6\u7ed8\u56fe\u5ba1\u8ba1"
GPS_TIME_OFFSET = 1772784000.0
PILOT_CASE_IDS = [
    "M_normal_baseline_repeat",
    "A_outage_5s",
    "C_position_noise_medium",
    "D_position_spike_medium",
    "B_gnss_downsample_2Hz",
    "H_dual_yaw_noise_medium",
    "G_raw_doppler_disabled",
    "L_feedback_disabled",
    "I_source_aware_disabled",
    "J_go2_horizontal_velocity_missing",
]
RANDOM_CASE_IDS = {
    "C_position_noise_medium",
    "D_position_spike_medium",
    "H_dual_yaw_noise_medium",
}
REQUIRED_SUBDIRS = [
    "00_supervisor",
    "01_plan",
    "degraded_inputs",
    "randomness",
    "solver_command_plan",
    "wsl_bridge_precheck",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1A_INPUT_GENERATION_REPORT.json",
    "N9B1A_RANDOMNESS_REPORT.json",
    "N9B1A_WSL_BRIDGE_PRECHECK_REPORT.json",
    "N9B1A_SOLVER_COMMAND_PLAN_REPORT.json",
    "N9B1A_PILOT_READY_REPORT.json",
    "N9B1A_SAFETY_GATE_REPORT.json",
    "N9B1A_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1A_DEGRADED_INPUT_INDEX",
    "N9B1A_RANDOM_VALUE_INDEX",
    "N9B1A_WSL_COMMAND_PLAN",
    "N9B1A_SOLVER_COMMAND_PLAN_INDEX",
    "N9B1A_PILOT_READY_MATRIX",
    "N9B1A_BLOCKED_ITEMS",
]


@dataclass(frozen=True)
class SourcePaths:
    gnss1_status: Path | None
    dual_yaw_gnss: Path | None
    imu: Path | None
    source: str


def default_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def discover_runtime_sources(workspace_root: Path) -> SourcePaths:
    local = workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    candidates = _extract_windows_paths(local) if local.exists() else []
    gnss1_status = _first_existing(candidates, "gnss1-status.csv")
    imu = _first_existing(candidates, "test1.imu")
    dual_yaw = _first_existing(candidates, "test1_statusyaw.gnss") or _first_existing(candidates, "test1.gnss")
    if dual_yaw is None:
        high_level = _first_existing(candidates, "by2.txt")
        if high_level is not None:
            root = high_level.parent
            dual_yaw = _first_existing([root / "test1_statusyaw.gnss", root / "test1.gnss"])
            imu = imu or _first_existing([root / "test1.imu"])
    return SourcePaths(gnss1_status, dual_yaw, imu, "DATA_PATHS.local.md" if local.exists() else "workspace_search")


def run_real_pilot_input_precheck(
    workspace_root: Path,
    runtime_root: Path | None = None,
    matrix_root: Path | None = None,
    write_outputs: bool = True,
    source_paths: SourcePaths | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_runtime_root(workspace_root)
    matrix_root = matrix_root or discover_cleaned_matrix_root(workspace_root)
    bundle = load_matrix_bundle(matrix_root)
    sources = source_paths or discover_runtime_sources(workspace_root)
    routing_rows = _load_aux_matrix(workspace_root, "N9B0B_DEGRADATION_RUNNER_IMPLEMENTATION_AND_DRYRUN_PRECHECK", "N9B0B_ALGORITHM_ROUTING_MATRIX")
    n9b1_rows = _load_aux_matrix(workspace_root, "N9B1_PILOT_DEGRADATION_EXECUTION_AND_REVIEW", "N9B1_EXECUTION_MATRIX")
    seed_rows = _seed_rows(bundle.seed_plan)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    clean7 = _load_clean_single_gnss(sources.gnss1_status) if sources.gnss1_status else []
    clean15 = _load_space_matrix(sources.dual_yaw_gnss, 15) if sources.dual_yaw_gnss else []
    blocked: list[dict[str, Any]] = []
    degraded_index: list[dict[str, Any]] = []
    random_index: list[dict[str, Any]] = []
    case_ready: dict[str, bool] = {}

    for case_id in PILOT_CASE_IDS:
        outputs = _generate_case(
            case_id=case_id,
            runtime_root=runtime_root,
            clean7=clean7,
            clean15=clean15,
            sources=sources,
            seed_rows=seed_rows.get(case_id, []),
            write_outputs=write_outputs,
        )
        degraded_index.extend(outputs["degraded_index"])
        random_index.extend(outputs["random_index"])
        blocked.extend(outputs["blocked"])
        case_ready[case_id] = not outputs["blocked"]

    solver_index, wsl_rows = _build_solver_plans(
        runtime_root=runtime_root,
        routing_rows=routing_rows,
        n9b1_rows=n9b1_rows,
        case_ready=case_ready,
        degraded_index=degraded_index,
        write_outputs=write_outputs,
    )
    blocked = _dedupe_blockers(blocked)
    pilot_ready = _build_pilot_ready(case_ready, solver_index, blocked)
    ready_for_n9b1b = all(row["ready_for_N9B1B_solver_execution"] for row in pilot_ready)
    ready_for_n9b1b = ready_for_n9b1b and not blocked
    validation = validate_n9b1a_result(runtime_root, degraded_index, random_index, solver_index, write_outputs)
    decision_status, recommended_next_stage = _decision_and_next_stage(ready_for_n9b1b, blocked, validation)

    reports = {
        "input_generation_report": {
            "stage": STAGE,
            "case_count": len(PILOT_CASE_IDS),
            "clean_single_rows": len(clean7),
            "clean_dual_yaw_rows": len(clean15),
            "degraded_input_rows": len(degraded_index),
            "blocked_count": len(blocked),
            "source_discovery": _source_report(sources),
        },
        "randomness_report": {
            "stage": STAGE,
            "random_case_ids": sorted(RANDOM_CASE_IDS),
            "random_value_rows": len(random_index),
            "hashes_recorded": all(row.get("sha256") for row in random_index),
            "N9B2_full": False,
        },
        "wsl_bridge_precheck_report": {
            "stage": STAGE,
            "dry_run_only": True,
            "command_plan_rows": len(wsl_rows),
            "script": "scripts/run_wsl_legsa.ps1",
            "executed": False,
        },
        "solver_command_plan_report": {
            "stage": STAGE,
            "plan_rows": len(solver_index),
            "solver_run": False,
            "official_evaluator_run": False,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
        },
        "pilot_ready_report": {
            "stage": STAGE,
            "ready_for_N9B1B_solver_execution": ready_for_n9b1b,
            "ready_for_solver_execution": False,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "blocked_count": len(blocked),
        },
        "safety_gate_report": {
            "stage": STAGE,
            "status": "pass" if validation["status"] == "pass" and not blocked else "blocked",
            "no_solver_run": True,
            "no_official_evaluator_run": True,
            "no_figures": True,
            "no_algorithm_math_changes": True,
            "ready_for_solver_execution": False,
            "issues": validation["issues"] + [row["blocked_reason"] for row in blocked],
        },
        "decision_report": {
            "stage": STAGE,
            "status": decision_status,
            "ready_for_N9B1B_solver_execution": ready_for_n9b1b,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "ready_for_solver_execution": False,
            "recommended_next_stage": recommended_next_stage,
            "blockers": blocked,
        },
    }
    result = {
        **reports,
        "degraded_input_index": degraded_index,
        "random_value_index": random_index,
        "wsl_command_plan": wsl_rows,
        "solver_command_plan_index": solver_index,
        "pilot_ready_matrix": pilot_ready,
        "blocked_items": blocked,
        "validation": validation,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_n9b1a_result(
    runtime_root: Path,
    degraded_index: list[dict[str, Any]] | None = None,
    random_index: list[dict[str, Any]] | None = None,
    solver_index: list[dict[str, Any]] | None = None,
    runtime_written: bool = True,
) -> dict[str, Any]:
    issues: list[str] = []
    forbidden_suffixes = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".npy", ".npz"}
    if runtime_written and runtime_root.exists():
        for path in runtime_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in forbidden_suffixes:
                issues.append(f"forbidden artifact generated: {_rel(runtime_root, path)}")
            if any(path.name.startswith(name) for name in FORBIDDEN_EXECUTION_OUTPUT_NAMES):
                issues.append(f"forbidden execution output generated: {_rel(runtime_root, path)}")
        for subdir in REQUIRED_SUBDIRS:
            if not (runtime_root / subdir).is_dir():
                issues.append(f"missing required subdir: {subdir}")
        for report in REPORT_NAMES:
            if not (runtime_root / "reports" / report).is_file():
                issues.append(f"missing report: {report}")
        for stem in MATRIX_STEMS:
            if not (runtime_root / "matrix" / f"{stem}.csv").is_file():
                issues.append(f"missing matrix CSV: {stem}")
            if not (runtime_root / "matrix" / f"{stem}.json").is_file():
                issues.append(f"missing matrix JSON: {stem}")
    for row in random_index or []:
        for key in ["affects_algorithm_input", "affects_metric", "toy_only", "pilot_only", "N9B2_full"]:
            if key not in row:
                issues.append(f"random row missing {key}: {row.get('case_id')}")
        if row.get("toy_only") is not False:
            issues.append(f"random row must be real, not toy: {row.get('case_id')}")
    for row in solver_index or []:
        if row.get("solver_run") is not False or row.get("official_evaluator_run") is not False:
            issues.append(f"solver/evaluator execution flag not false: {row}")
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _generate_case(
    case_id: str,
    runtime_root: Path,
    clean7: list[list[float]],
    clean15: list[list[float]],
    sources: SourcePaths,
    seed_rows: list[int],
    write_outputs: bool,
) -> dict[str, Any]:
    case_dir = runtime_root / "degraded_inputs" / case_id
    random_dir = runtime_root / "randomness" / case_id
    random_values_dir = random_dir / "random_values"
    if write_outputs:
        case_dir.mkdir(parents=True, exist_ok=True)
        random_values_dir.mkdir(parents=True, exist_ok=True)
    blocked: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    random_index: list[dict[str, Any]] = []
    random_seed_manifest: list[dict[str, Any]] = []
    random_value_manifest: list[dict[str, Any]] = []
    source_role = _source_role(case_id, sources)

    if not clean7:
        blocked.append(_block(case_id, "source_missing", "gnss1-status.csv unavailable or empty"))
    if case_id == "H_dual_yaw_noise_medium" and not clean15:
        blocked.append(_block(case_id, "source_missing", "15-col dual-yaw GNSS input unavailable or empty"))
    if clean7:
        if case_id == "A_outage_5s":
            rows7, mask7 = _apply_outage(clean7)
            generated += _write_input(case_dir, case_id, "single7", rows7, write_outputs, mask7)
        elif case_id == "B_gnss_downsample_2Hz":
            rows7, mask7, blocker = _apply_downsample(clean7, case_id)
            if blocker:
                blocked.append(blocker)
            generated += _write_input(case_dir, case_id, "single7", rows7, write_outputs, mask7)
        elif case_id == "C_position_noise_medium":
            for seed in seed_rows:
                rows7, values = _apply_position_noise(clean7, seed)
                random_index.append(_random_stats(case_id, seed, "python_random_gauss", values, random_values_dir / f"seed_{seed}_single7_noise.csv"))
                random_value_manifest.append(random_index[-1])
                random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
                if write_outputs:
                    _write_dict_rows(random_values_dir / f"seed_{seed}_single7_noise.csv", values)
                generated += _write_input(case_dir, case_id, f"single7_seed_{seed}", rows7, write_outputs)
        elif case_id == "D_position_spike_medium":
            for seed in seed_rows:
                rows7, values = _apply_position_spikes(clean7, seed)
                random_index.append(_random_stats(case_id, seed, "python_random_spike_trigger", values, random_values_dir / f"seed_{seed}_single7_spikes.csv"))
                random_value_manifest.append(random_index[-1])
                random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
                if write_outputs:
                    _write_dict_rows(random_values_dir / f"seed_{seed}_single7_spikes.csv", values)
                generated += _write_input(case_dir, case_id, f"single7_seed_{seed}", rows7, write_outputs)
        else:
            generated += _write_input(case_dir, case_id, "single7_clean", clean7, write_outputs)

    if clean15:
        if case_id == "A_outage_5s":
            rows15, mask15 = _apply_outage(clean15)
            generated += _write_input(case_dir, case_id, "dual15", rows15, write_outputs, mask15)
        elif case_id == "B_gnss_downsample_2Hz":
            rows15, mask15, blocker = _apply_downsample(clean15, case_id)
            if blocker:
                blocked.append(blocker)
            generated += _write_input(case_dir, case_id, "dual15", rows15, write_outputs, mask15)
        elif case_id == "C_position_noise_medium":
            for seed in seed_rows:
                rows15, values = _apply_position_noise(clean15, seed)
                random_index.append(_random_stats(case_id, seed, "python_random_gauss", values, random_values_dir / f"seed_{seed}_dual15_noise.csv"))
                random_value_manifest.append(random_index[-1])
                random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
                if write_outputs:
                    _write_dict_rows(random_values_dir / f"seed_{seed}_dual15_noise.csv", values)
                generated += _write_input(case_dir, case_id, f"dual15_seed_{seed}", rows15, write_outputs)
        elif case_id == "D_position_spike_medium":
            for seed in seed_rows:
                rows15, values = _apply_position_spikes(clean15, seed)
                random_index.append(_random_stats(case_id, seed, "python_random_spike_trigger", values, random_values_dir / f"seed_{seed}_dual15_spikes.csv"))
                random_value_manifest.append(random_index[-1])
                random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
                if write_outputs:
                    _write_dict_rows(random_values_dir / f"seed_{seed}_dual15_spikes.csv", values)
                generated += _write_input(case_dir, case_id, f"dual15_seed_{seed}", rows15, write_outputs)
        elif case_id == "H_dual_yaw_noise_medium":
            for seed in seed_rows:
                rows15, values = _apply_yaw_noise(clean15, seed)
                random_index.append(_random_stats(case_id, seed, "python_random_yaw_gauss_deg", values, random_values_dir / f"seed_{seed}_dual15_yaw_noise.csv"))
                random_value_manifest.append(random_index[-1])
                random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
                if write_outputs:
                    _write_dict_rows(random_values_dir / f"seed_{seed}_dual15_yaw_noise.csv", values)
                generated += _write_input(case_dir, case_id, f"dual15_seed_{seed}", rows15, write_outputs)
        else:
            generated += _write_input(case_dir, case_id, "dual15_clean", clean15, write_outputs)

    marker = _config_marker(case_id)
    if write_outputs:
        _write_json(case_dir / "degradation_manifest.json", _degradation_manifest(case_id, generated, blocked, marker))
        _write_json(case_dir / "source_role.json", source_role)
        _write_table_pair(case_dir / "generated_input_manifest", generated)
        _write_table_pair(case_dir / "random_seed_manifest", random_seed_manifest)
        _write_table_pair(case_dir / "random_value_manifest", random_value_manifest)
        (case_dir / "input_generation_log.txt").write_text(_case_log(case_id, generated, blocked), encoding="utf-8")
        _write_table_pair(random_dir / "random_seed_manifest", random_seed_manifest)
        _write_table_pair(random_dir / "random_value_manifest", random_value_manifest)
        _write_table_pair(random_dir / "hashes", [{"case_id": r["case_id"], "seed": r["seed"], "sha256": r["sha256"], "path": r["path"]} for r in random_index])
        if sources.imu and sources.imu.exists():
            shutil.copy2(sources.imu, case_dir / "test1.imu")
    return {"degraded_index": generated, "random_index": random_index, "blocked": blocked}


def _apply_outage(rows: list[list[float]]) -> tuple[list[list[float]], list[dict[str, Any]]]:
    kept: list[list[float]] = []
    mask: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        removed = 206.2 <= row[0] <= 211.2
        mask.append({"index": index, "time": row[0], "removed": removed})
        if not removed:
            kept.append(row)
    return kept, mask


def _apply_downsample(rows: list[list[float]], case_id: str) -> tuple[list[list[float]], list[dict[str, Any]], dict[str, Any] | None]:
    cadence = _median_delta([row[0] for row in rows])
    native_hz = 1.0 / cadence if cadence > 0 else 0.0
    if native_hz < 3.0:
        return rows, [], _block(case_id, "low_native_cadence", f"native cadence {native_hz:.3f} Hz is below 2 Hz target downsample precondition")
    step = max(1, round(native_hz / 2.0))
    kept = [row for index, row in enumerate(rows) if index % step == 0]
    mask = [{"index": index, "time": row[0], "kept": index % step == 0, "integer_step": step} for index, row in enumerate(rows)]
    return kept, mask, None


def _apply_position_noise(rows: list[list[float]], seed: int) -> tuple[list[list[float]], list[dict[str, Any]]]:
    rng = random.Random(1000 + seed)
    output: list[list[float]] = []
    values: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        n = rng.gauss(0.0, 1.5)
        e = rng.gauss(0.0, 1.5)
        u = rng.gauss(0.0, 2.5)
        output.append(_offset_position(row, n, e, u))
        values.append({"seed": seed, "index": index, "time": row[0], "noise_n_m": n, "noise_e_m": e, "noise_u_m": u})
    return output, values


def _apply_position_spikes(rows: list[list[float]], seed: int) -> tuple[list[list[float]], list[dict[str, Any]]]:
    rng = random.Random(2000 + seed)
    output: list[list[float]] = []
    values: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        triggered = rng.random() < 0.05
        if triggered:
            angle = rng.random() * math.tau
            n = math.cos(angle) * 4.0
            e = math.sin(angle) * 4.0
            u = (1.0 if rng.random() >= 0.5 else -1.0) * 2.0
        else:
            n = e = u = 0.0
        output.append(_offset_position(row, n, e, u))
        if triggered:
            values.append({"seed": seed, "index": index, "time": row[0], "spike_n_m": n, "spike_e_m": e, "spike_u_m": u})
    return output, values


def _apply_yaw_noise(rows: list[list[float]], seed: int) -> tuple[list[list[float]], list[dict[str, Any]]]:
    rng = random.Random(3000 + seed)
    output: list[list[float]] = []
    values: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        yaw_noise = rng.gauss(0.0, 3.0)
        new_row = list(row)
        new_row[13] += yaw_noise
        output.append(new_row)
        values.append({"seed": seed, "index": index, "time": row[0], "yaw_noise_deg": yaw_noise})
    return output, values


def _offset_position(row: list[float], north_m: float, east_m: float, up_m: float) -> list[float]:
    new_row = list(row)
    lat = row[1]
    lat_rad = math.radians(lat)
    new_row[1] = lat + math.degrees(north_m / 6378137.0)
    new_row[2] = row[2] + math.degrees(east_m / max(1e-9, 6378137.0 * math.cos(lat_rad)))
    new_row[3] = row[3] + up_m
    return new_row


def _load_clean_single_gnss(path: Path | None) -> list[list[float]]:
    if path is None or not path.exists():
        return []
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                time_s = float(row["sys_stamp.secs"]) + float(row["sys_stamp.nsecs"]) / 1e9 - GPS_TIME_OFFSET
                rows.append([
                    time_s,
                    float(row["pos_lat"]),
                    float(row["pos_lon"]),
                    float(row["pos_height"]),
                    float(row["pos_acc_h"]),
                    float(row["pos_acc_h"]),
                    float(row["pos_acc_v"]),
                ])
            except (KeyError, ValueError):
                continue
    return rows


def _load_space_matrix(path: Path | None, columns: int) -> list[list[float]]:
    if path is None or not path.exists():
        return []
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) != columns:
                continue
            try:
                rows.append([float(part) for part in parts])
            except ValueError:
                continue
    return rows


def _write_input(case_dir: Path, case_id: str, tag: str, rows: list[list[float]], write_outputs: bool, mask: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    filename = f"{tag}.gnss"
    path = case_dir / filename
    if write_outputs:
        _write_numeric_rows(path, rows)
        if mask is not None:
            _write_dict_rows(case_dir / f"{tag}_mask.csv", mask)
            _write_json(case_dir / f"{tag}_mask.json", mask)
    return [{
        "case_id": case_id,
        "input_tag": tag,
        "path": f"degraded_inputs/{case_id}/{filename}",
        "row_count": len(rows),
        "sha256": _sha256_file(path) if write_outputs and path.exists() else "",
        "algorithm_input": True,
        "solver_run": False,
    }]


def _build_solver_plans(
    runtime_root: Path,
    routing_rows: list[dict[str, str]],
    n9b1_rows: list[dict[str, str]],
    case_ready: dict[str, bool],
    degraded_index: list[dict[str, Any]],
    write_outputs: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    input_lookup: dict[str, list[str]] = {}
    for row in degraded_index:
        input_lookup.setdefault(row["case_id"], []).append(row["path"])
    n9b1_candidates = {
        (row["case_id"], row["algorithm_group"])
        for row in n9b1_rows
        if row.get("routing_status") == "applicable" and row.get("excluded_from_solver_execution") in {"false", "False", False}
    }
    n9b1_cases = {case_id for case_id, _algorithm in n9b1_candidates}
    rows: list[dict[str, Any]] = []
    wsl_rows: list[dict[str, Any]] = []
    for row in routing_rows:
        case_id = row.get("case_id", "")
        algorithm = row.get("algorithm_group", "")
        routing_status = row.get("routing_status")
        if case_id not in PILOT_CASE_IDS or routing_status not in {"applicable", "diagnostic_only"}:
            continue
        if routing_status == "diagnostic_only" and not _diagnostic_solver_plan_allowed(case_id, algorithm):
            continue
        if case_id in n9b1_cases:
            if (case_id, algorithm) not in n9b1_candidates:
                continue
        plan_dir = runtime_root / "solver_command_plan" / case_id / algorithm
        command = (
            "N9B1C_REAL_SOLVER_ENTRYPOINT_AND_CONFIG_MAPPING_REQUIRED "
            f"--case {case_id} --algorithm {algorithm} "
            f"--input-root ${{WSL_AUDIT_ROOT}}/{AUDIT_ROOT_NAME}/{STAGE}/degraded_inputs/{case_id} "
            f"--output-root ${{WSL_AUDIT_ROOT}}/{AUDIT_ROOT_NAME}/{STAGE}/future_solver_outputs/{case_id}/{algorithm}"
        )
        solver_json = {
            "stage": STAGE,
            "case_id": case_id,
            "algorithm": algorithm,
            "routing_status": routing_status,
            "degraded_input_paths": input_lookup.get(case_id, []),
            "command_plan_only": True,
            "solver_run": False,
            "official_evaluator_run": False,
            "trace_solver_input": False,
            "final_v23_solver_input": False,
            "command": command,
        }
        expected = {
            "future_expectation_only": True,
            "expected_outputs": ["NAV.csv", "STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"],
            "official_evaluator_command_plan": "future N9B1B only; not executed in N9B1A",
        }
        source_role = {"trace": "evaluation_only_not_solver_input", "final_v23": "reference_only_not_solver_input"}
        if write_outputs:
            plan_dir.mkdir(parents=True, exist_ok=True)
            _write_json(plan_dir / "solver_command.json", solver_json)
            _write_json(plan_dir / "expected_outputs.json", expected)
            _write_json(plan_dir / "source_role.json", source_role)
        rel_solver = f"solver_command_plan/{case_id}/{algorithm}/solver_command.json"
        rows.append({
            "case_id": case_id,
            "algorithm": algorithm,
            "routing_status": routing_status,
            "ready_for_N9B1B_solver_execution": bool(case_ready.get(case_id)) and bool(input_lookup.get(case_id)),
            "solver_command_json": rel_solver,
            "expected_outputs_json": f"solver_command_plan/{case_id}/{algorithm}/expected_outputs.json",
            "source_role_json": f"solver_command_plan/{case_id}/{algorithm}/source_role.json",
            "solver_run": False,
            "official_evaluator_run": False,
        })
        wsl_rows.append({
            "case_id": case_id,
            "algorithm": algorithm,
            "routing_status": routing_status,
            "dry_run_only": True,
            "working_directory": "${WSL_AUDIT_ROOT}",
            "command": command,
            "solver_command_json": rel_solver,
            "executed": False,
        })
    return rows, wsl_rows


def _diagnostic_solver_plan_allowed(case_id: str, algorithm: str) -> bool:
    return case_id == "J_go2_horizontal_velocity_missing" and algorithm in {"Go2_joint_EKF", "selected_feedback_EKF"}


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1A_INPUT_GENERATION_REPORT.json": result["input_generation_report"],
        "N9B1A_RANDOMNESS_REPORT.json": result["randomness_report"],
        "N9B1A_WSL_BRIDGE_PRECHECK_REPORT.json": result["wsl_bridge_precheck_report"],
        "N9B1A_SOLVER_COMMAND_PLAN_REPORT.json": result["solver_command_plan_report"],
        "N9B1A_PILOT_READY_REPORT.json": result["pilot_ready_report"],
        "N9B1A_SAFETY_GATE_REPORT.json": result["safety_gate_report"],
        "N9B1A_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1A_DEGRADED_INPUT_INDEX": result["degraded_input_index"],
        "N9B1A_RANDOM_VALUE_INDEX": result["random_value_index"],
        "N9B1A_WSL_COMMAND_PLAN": result["wsl_command_plan"],
        "N9B1A_SOLVER_COMMAND_PLAN_INDEX": result["solver_command_plan_index"],
        "N9B1A_PILOT_READY_MATRIX": result["pilot_ready_matrix"],
        "N9B1A_BLOCKED_ITEMS": result["blocked_items"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
    summaries = {
        "n9b1a_input_generation_summary.md": f"# N9B1A input generation\n\n- Cases: {len(PILOT_CASE_IDS)}\n- Degraded input rows: {len(result['degraded_input_index'])}\n- Solver run: false\n",
        "n9b1a_randomness_summary.md": f"# N9B1A randomness\n\n- Random value rows: {len(result['random_value_index'])}\n- toy_only=false\n- N9B2_full=false\n",
        "n9b1a_wsl_bridge_summary.md": f"# N9B1A WSL bridge\n\n- Dry-run command plans: {len(result['wsl_command_plan'])}\n- Executed: false\n",
        "n9b1a_pilot_readiness_summary.md": f"# N9B1A pilot readiness\n\n- Decision: {result['decision_report']['status']}\n- ready_for_N9B1B_solver_execution={str(result['decision_report']['ready_for_N9B1B_solver_execution']).lower()}\n- ready_for_solver_execution=false\n",
        "n9b1a_next_stage_recommendation.md": f"# N9B1A next stage recommendation\n\n- recommended_next_stage={result['decision_report']['recommended_next_stage']}\n- ready_for_N9B2_execution=false\n- ready_for_full_N9B_execution=false\n",
    }
    for name, text in summaries.items():
        (runtime_root / "summary" / name).write_text(text, encoding="utf-8")
    _write_json(runtime_root / "validation" / "N9B1A_VALIDATION_REPORT.json", result["validation"])


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def _extract_windows_paths(path: Path) -> list[Path]:
    paths: list[Path] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if len(text) > 3 and text[1:3] == ":\\":
            paths.append(Path(text))
    return paths


def _first_existing(candidates: list[Path], name: str | None = None) -> Path | None:
    for candidate in candidates:
        path = candidate / name if name and candidate.is_dir() else candidate
        if name and candidate.name != name and not candidate.is_dir():
            continue
        if path.exists():
            return path
    return None


def _load_aux_matrix(workspace_root: Path, stage: str, stem: str) -> list[dict[str, str]]:
    path = workspace_root / AUDIT_ROOT_NAME / stage / "matrix" / f"{stem}.csv"
    return load_csv_rows(path) if path.exists() else []


def _seed_rows(seed_plan: list[dict[str, str]]) -> dict[str, list[int]]:
    rows: dict[str, list[int]] = {case_id: [] for case_id in PILOT_CASE_IDS}
    for row in seed_plan:
        case_id = row.get("case_id", "")
        if case_id in RANDOM_CASE_IDS and row.get("seed", "").isdigit():
            rows[case_id].append(int(row["seed"]))
    return {case_id: sorted(set(values)) for case_id, values in rows.items()}


def _config_marker(case_id: str) -> dict[str, Any]:
    marker = {
        "G_raw_doppler_disabled": "raw_doppler_disabled_config_marker_only_no_raw_doppler_array_fabricated",
        "L_feedback_disabled": "feedback_disabled_config_marker_only",
        "I_source_aware_disabled": "source_aware_disabled_config_marker_only",
        "J_go2_horizontal_velocity_missing": "go2_horizontal_velocity_missing_source_role_marker_only",
    }.get(case_id, "")
    return {"config_marker": marker, "marker_only": bool(marker)}


def _source_role(case_id: str, sources: SourcePaths) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": case_id,
        "gnss1_status": "source_observation_for_7col_input",
        "dual_yaw_gnss": "source_observation_for_15col_input",
        "imu": "referenced_or_copied_runtime_input_not_mutated",
        "raw_doppler": "config_marker_only_no_NAV_PVT_velocity_fabrication",
        "go2": "diagnostic_source_marker_only_not_truth",
        "trace": "evaluation_only_not_solver_input",
        "final_v23": "reference_only_not_solver_input",
        "source_discovery": sources.source,
    }


def _degradation_manifest(case_id: str, generated: list[dict[str, Any]], blocked: list[dict[str, Any]], marker: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "case_id": case_id,
        "generated_input_count": len(generated),
        "blocked": bool(blocked),
        "blocked_items": blocked,
        "solver_run": False,
        "official_evaluator_run": False,
        "figures_generated": False,
        **marker,
    }


def _case_log(case_id: str, generated: list[dict[str, Any]], blocked: list[dict[str, Any]]) -> str:
    lines = [f"case_id={case_id}", "solver_run=false", "official_evaluator_run=false", f"generated_input_count={len(generated)}"]
    lines.extend(f"blocked={row['blocked_reason']}" for row in blocked)
    return "\n".join(lines) + "\n"


def _random_stats(case_id: str, seed: int, generator: str, values: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    numeric: list[float] = []
    for row in values:
        for key, value in row.items():
            if key not in {"seed", "index", "time"} and isinstance(value, (float, int)):
                numeric.append(float(value))
    digest = _sha256_rows(values)
    return {
        "case_id": case_id,
        "seed": seed,
        "generator": generator,
        "value_count": len(values),
        "shape": f"{len(values)}x{max((len(row) for row in values), default=0)}",
        "min": min(numeric) if numeric else 0.0,
        "max": max(numeric) if numeric else 0.0,
        "mean": mean(numeric) if numeric else 0.0,
        "std": pstdev(numeric) if len(numeric) > 1 else 0.0,
        "sha256": digest,
        "path": str(path).replace("\\", "/").split(f"{STAGE}/")[-1],
        "affects_algorithm_input": True,
        "affects_metric": True,
        "toy_only": False,
        "pilot_only": True,
        "N9B2_full": False,
    }


def _seed_manifest(case_id: str, seed: int, value_count: int, sha256: str) -> dict[str, Any]:
    return {"case_id": case_id, "seed": seed, "value_count": value_count, "sha256": sha256, "pilot_only": True, "N9B2_full": False}


def _build_pilot_ready(case_ready: dict[str, bool], solver_index: list[dict[str, Any]], blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_cases = {row["case_id"] for row in blocked}
    solver_cases = {row["case_id"] for row in solver_index if row["ready_for_N9B1B_solver_execution"]}
    candidate_cases = {row["case_id"] for row in solver_index}
    rows = []
    for case_id in PILOT_CASE_IDS:
        plan_ready = case_id not in candidate_cases or case_id in solver_cases
        ready = bool(case_ready.get(case_id)) and plan_ready and case_id not in blocked_cases
        rows.append({
            "case_id": case_id,
            "degraded_inputs_ready": bool(case_ready.get(case_id)),
            "solver_command_plan_ready": plan_ready,
            "ready_for_N9B1B_solver_execution": ready,
            "ready_for_solver_execution": False,
            "ready_for_N9B2_execution": False,
        })
    return rows


def _decision_and_next_stage(
    ready_for_n9b1b: bool,
    blocked: list[dict[str, Any]],
    validation: dict[str, Any],
) -> tuple[str, str]:
    if validation["status"] != "pass":
        return "N9B1A_safety_gate_failed", "repair_safety_violation"
    if ready_for_n9b1b and not blocked:
        return "N9B1A_real_pilot_inputs_and_wsl_bridge_ready", "human_review_N9B1A_then_N9B1B_solver_execution"
    return "N9B1A_degraded_input_generation_failed", "fix_input_generation"


def _dedupe_blockers(blocked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in blocked:
        key = (row["case_id"], row["blocked_stage"], row["blocked_reason"])
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _block(case_id: str, blocked_stage: str, reason: str) -> dict[str, Any]:
    return {"case_id": case_id, "blocked_stage": blocked_stage, "blocked_reason": reason, "ready_for_N9B1B_solver_execution": False}


def _source_report(sources: SourcePaths) -> dict[str, Any]:
    return {
        "source": sources.source,
        "gnss1_status_found": bool(sources.gnss1_status and sources.gnss1_status.exists()),
        "dual_yaw_gnss_found": bool(sources.dual_yaw_gnss and sources.dual_yaw_gnss.exists()),
        "imu_found": bool(sources.imu and sources.imu.exists()),
    }


def _median_delta(times: list[float]) -> float:
    if len(times) < 2:
        return 0.0
    deltas = sorted(max(0.0, b - a) for a, b in zip(times, times[1:]) if b > a)
    return deltas[len(deltas) // 2] if deltas else 0.0


def _write_numeric_rows(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(" ".join(f"{value:.9f}" for value in row) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _write_dict_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_table_pair(stem: Path, rows: list[dict[str, Any]]) -> None:
    _write_json(stem.with_suffix(".json"), rows)
    _write_dict_rows(stem.with_suffix(".csv"), rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256_rows(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
