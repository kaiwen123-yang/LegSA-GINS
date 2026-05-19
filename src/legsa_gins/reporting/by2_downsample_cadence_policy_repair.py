"""N9B1A1 GNSS downsample cadence policy repair.

This reporting-only module repairs the N9B1 pilot downsample case from an
unsupported absolute 2 Hz target to a deterministic ratio case that keeps every
second locked GNSS observation. It does not run solvers, evaluators, figures, or
algorithm code.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from legsa_gins.reporting.by2_degradation_runner_precheck import (
    FORBIDDEN_EXECUTION_OUTPUT_NAMES,
    discover_cleaned_matrix_root,
    load_csv_rows,
    load_matrix_bundle,
)
from legsa_gins.reporting.by2_real_pilot_input_generator import (
    AUDIT_ROOT_NAME,
    GPS_TIME_OFFSET,
    RANDOM_CASE_IDS,
    SourcePaths,
    _apply_outage,
    _apply_position_noise,
    _apply_position_spikes,
    _apply_yaw_noise,
    _load_aux_matrix,
    _load_clean_single_gnss,
    _load_space_matrix,
    _median_delta,
    _sha256_file,
    _source_report,
    _source_role,
    _write_input,
    discover_runtime_sources,
)


STAGE = "N9B1A1_DOWNSAMPLE_CADENCE_POLICY_REPAIR"
OLD_DOWNSAMPLE_CASE_ID = "B_gnss_downsample_2Hz"
REPAIRED_DOWNSAMPLE_CASE_ID = "B_gnss_downsample_every2"
REPAIRED_PILOT_CASE_IDS = [
    "M_normal_baseline_repeat",
    "A_outage_5s",
    "C_position_noise_medium",
    "D_position_spike_medium",
    REPAIRED_DOWNSAMPLE_CASE_ID,
    "H_dual_yaw_noise_medium",
    "G_raw_doppler_disabled",
    "L_feedback_disabled",
    "I_source_aware_disabled",
    "J_go2_horizontal_velocity_missing",
]
REQUIRED_SUBDIRS = [
    "cadence_audit",
    "repaired_matrices",
    "repaired_inputs",
    "randomness",
    "solver_command_plan",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
]
REPORT_NAMES = [
    "N9B1A1_GNSS_CADENCE_AUDIT_REPORT.json",
    "N9B1A1_DOWNSAMPLE_POLICY_REPAIR_REPORT.json",
    "N9B1A1_PILOT_PLAN_REPAIR_REPORT.json",
    "N9B1A1_INPUT_REPAIR_REPORT.json",
    "N9B1A1_SAFETY_GATE_REPORT.json",
    "N9B1A1_DECISION_REPORT.json",
]
MATRIX_STEMS = [
    "N9B1A1_GNSS_CADENCE_AUDIT",
    "N9B1A1_DOWNSAMPLE_CASE_REPAIR_DIFF",
    "N9B1A1_PILOT_CASE_PLAN_REPAIRED",
    "N9B1A1_DEGRADED_INPUT_INDEX_REPAIRED",
    "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED",
    "N9B1A1_PILOT_READY_MATRIX_REPAIRED",
    "N9B1A1_FULL_MATRIX_DOWNSAMPLE_REPAIR",
]


def default_n9b1a1_runtime_root(workspace_root: Path) -> Path:
    return workspace_root / AUDIT_ROOT_NAME / STAGE


def run_downsample_cadence_policy_repair(
    workspace_root: Path,
    runtime_root: Path | None = None,
    matrix_root: Path | None = None,
    write_outputs: bool = True,
    source_paths: SourcePaths | None = None,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    runtime_root = runtime_root or default_n9b1a1_runtime_root(workspace_root)
    matrix_root = matrix_root or discover_cleaned_matrix_root(workspace_root)
    bundle = load_matrix_bundle(matrix_root)
    sources = source_paths or discover_runtime_sources(workspace_root)
    if write_outputs:
        _create_runtime_tree(runtime_root)

    clean7 = _load_clean_single_gnss(sources.gnss1_status) if sources.gnss1_status else []
    clean15 = _load_space_matrix(sources.dual_yaw_gnss, 15) if sources.dual_yaw_gnss else []
    cadence_audit = _build_cadence_audit(workspace_root, clean7, clean15, sources)
    pilot_plan = _repair_pilot_plan(bundle.pilot)
    repair_diff = _build_repair_diff(cadence_audit)
    full_matrix_repair = _build_full_matrix_downsample_repair(bundle.full, cadence_audit)
    seed_rows = _seed_rows(bundle.seed_plan)

    degraded_index: list[dict[str, Any]] = []
    random_index: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    case_ready: dict[str, bool] = {}
    for case_id in REPAIRED_PILOT_CASE_IDS:
        outputs = _generate_repaired_case(case_id, runtime_root, clean7, clean15, sources, seed_rows.get(case_id, []), write_outputs)
        degraded_index.extend(outputs["degraded_index"])
        random_index.extend(outputs["random_index"])
        blocked.extend(outputs["blocked"])
        case_ready[case_id] = not outputs["blocked"] and bool(outputs["degraded_index"])

    routing_rows = _load_aux_matrix(workspace_root, "N9B0B_DEGRADATION_RUNNER_IMPLEMENTATION_AND_DRYRUN_PRECHECK", "N9B0B_ALGORITHM_ROUTING_MATRIX")
    solver_index = _build_repaired_solver_plan(runtime_root, pilot_plan, routing_rows, degraded_index, case_ready, write_outputs)
    pilot_ready = _build_repaired_pilot_ready(pilot_plan, solver_index, case_ready, blocked)
    validation = validate_downsample_cadence_policy_repair(runtime_root, degraded_index, random_index, solver_index, pilot_ready, False)
    all_ready = validation["status"] == "pass" and all(row["ready_for_N9B1B_solver_execution"] for row in pilot_ready)

    result = {
        "gnss_cadence_audit_report": {
            "stage": STAGE,
            "source_discovery": _source_report(sources),
            "locked_source_count": len(cadence_audit),
            "absolute_2hz_supported": any(row["approved_for_current_runner"] and row["supports_2Hz_downsample"] for row in cadence_audit),
            "approved_high_cadence_source_available": any(row["approved_for_current_runner"] and row["estimated_hz"] >= 2.0 for row in cadence_audit),
            "policy_decision": "replace pilot absolute 2Hz with deterministic ratio keep_every_2",
        },
        "downsample_policy_repair_report": {
            "stage": STAGE,
            "old_case_id": OLD_DOWNSAMPLE_CASE_ID,
            "repaired_case_id": REPAIRED_DOWNSAMPLE_CASE_ID,
            "repair": "deterministic ratio downsample, keep rows where source_index % 2 == 0",
            "seed": "none",
            "random_values_required": False,
            "old_absolute_2hz_status": "blocked_not_executable_for_current_locked_about_1hz_inputs",
            "upsampling": False,
            "gnss1_raw_switch": False,
        },
        "pilot_plan_repair_report": {
            "stage": STAGE,
            "pilot_case_count": len(pilot_plan),
            "old_case_present": any(row["case_id"] == OLD_DOWNSAMPLE_CASE_ID for row in pilot_plan),
            "repaired_case_present": any(row["case_id"] == REPAIRED_DOWNSAMPLE_CASE_ID for row in pilot_plan),
            "all_10_ready": all_ready,
        },
        "input_repair_report": {
            "stage": STAGE,
            "degraded_input_rows": len(degraded_index),
            "random_value_rows": len(random_index),
            "blocked_count": len(blocked),
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
        },
        "safety_gate_report": {
            "stage": STAGE,
            "status": "pass" if all_ready else "blocked",
            "no_solver_run": True,
            "no_official_evaluator_run": True,
            "no_figures": True,
            "no_n9b2_execution": True,
            "no_upsampling": True,
            "no_fake_high_cadence_source": True,
            "ready_for_solver_execution": False,
            "ready_for_N9B2_execution": False,
            "issues": validation["issues"],
        },
        "decision_report": {
            "stage": STAGE,
            "status": "N9B1A1_downsample_cadence_repair_complete" if all_ready else "N9B1A1_downsample_replacement_blocked",
            "ready_for_N9B1B_solver_execution": all_ready,
            "ready_for_solver_execution": False,
            "ready_for_N9B2_execution": False,
            "ready_for_full_N9B_execution": False,
            "recommended_next_stage": "human_review_N9B1A1_then_N9B1B_solver_execution" if all_ready else "repair_N9B1A1_inputs_or_policy",
            "blockers": blocked,
        },
        "gnss_cadence_audit": cadence_audit,
        "downsample_case_repair_diff": repair_diff,
        "pilot_case_plan_repaired": pilot_plan,
        "degraded_input_index_repaired": degraded_index,
        "random_value_index": random_index,
        "solver_command_plan_index_repaired": solver_index,
        "pilot_ready_matrix_repaired": pilot_ready,
        "full_matrix_downsample_repair": full_matrix_repair,
        "validation": validation,
    }
    if write_outputs:
        _write_outputs(runtime_root, result)
    return result


def validate_downsample_cadence_policy_repair(
    runtime_root: Path,
    degraded_index: list[dict[str, Any]] | None = None,
    random_index: list[dict[str, Any]] | None = None,
    solver_index: list[dict[str, Any]] | None = None,
    pilot_ready: list[dict[str, Any]] | None = None,
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
    case_ids = {row.get("case_id") for row in degraded_index or []}
    if set(REPAIRED_PILOT_CASE_IDS) - case_ids:
        issues.append(f"missing degraded inputs for repaired pilot cases: {sorted(set(REPAIRED_PILOT_CASE_IDS) - case_ids)}")
    if OLD_DOWNSAMPLE_CASE_ID in case_ids:
        issues.append("old absolute 2Hz pilot case must not appear in repaired degraded input index")
    for row in random_index or []:
        if row.get("case_id") == REPAIRED_DOWNSAMPLE_CASE_ID:
            issues.append("repaired downsample case must not create random value rows")
        if row.get("toy_only") is not False or row.get("N9B2_full") is not False:
            issues.append(f"random row must be real pilot-only, not toy/full: {row.get('case_id')}")
    for row in solver_index or []:
        if row.get("solver_run") is not False or row.get("official_evaluator_run") is not False:
            issues.append(f"solver/evaluator execution flag not false: {row}")
    if pilot_ready is not None:
        if len(pilot_ready) != 10:
            issues.append(f"repaired pilot ready matrix must have 10 rows, got {len(pilot_ready)}")
        if any(not row.get("ready_for_N9B1B_solver_execution") for row in pilot_ready):
            issues.append("all repaired pilot cases must be ready for N9B1B command-plan review")
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _build_cadence_audit(
    workspace_root: Path,
    clean7: list[list[float]],
    clean15: list[list[float]],
    sources: SourcePaths,
) -> list[dict[str, Any]]:
    final_v23_path = _discover_final_v23_15col_source(sources)
    final_v23_rows = _load_space_matrix(final_v23_path, 15) if final_v23_path else []
    raw_path = _find_local_path_by_name(workspace_root, "gnss1-raw.csv")
    raw_nav_pvt_times = _load_raw_nav_pvt_times(raw_path) if raw_path else []
    candidates = [
        (
            "single7_clean_input",
            clean7,
            sources.gnss1_status,
            "derived locked 7-col GNSS1-status pilot input",
            True,
        ),
        (
            "dual15_clean_input",
            clean15,
            sources.dual_yaw_gnss,
            "locked 15-col dual-yaw GNSS pilot input",
            True,
        ),
        (
            "gnss1_status_source",
            clean7,
            sources.gnss1_status,
            "GNSS1 status position/std source",
            True,
        ),
        (
            "final_v23_15col_source",
            final_v23_rows,
            final_v23_path,
            "final_v23-style 15-col source; reference lineage only, not solver input",
            False,
        ),
        (
            "gnss1_raw_nav_pvt_candidate",
            [[time_s] for time_s in raw_nav_pvt_times],
            raw_path,
            "GNSS1 raw NAV-PVT higher-cadence observation candidate; not approved for current runner",
            False,
        ),
    ]
    return [
        _cadence_row(source_id, source_rows, path, source_role, approved)
        for source_id, source_rows, path, source_role, approved in candidates
        if source_rows or path is not None
    ]


def _cadence_row(
    source_id: str,
    source_rows: list[list[float]],
    path: Path | None,
    source_role: str,
    approved_for_current_runner: bool,
) -> dict[str, Any]:
    times = [float(row[0]) for row in source_rows]
    deltas = sorted(max(0.0, b - a) for a, b in zip(times, times[1:]) if b > a)
    median_dt = _median_delta(times)
    p95_dt = _percentile(deltas, 95.0)
    estimated_hz = 1.0 / median_dt if median_dt > 0 else 0.0
    row_count = len(source_rows)
    time_start = times[0] if times else ""
    time_end = times[-1] if times else ""
    duration = (time_end - time_start) if times else 0.0
    return {
        "source_id": source_id,
        "path": str(path) if path else "",
        "row_count": row_count,
        "time_start": time_start,
        "time_end": time_end,
        "duration": duration,
        "median_dt": median_dt,
        "p95_dt": p95_dt,
        "estimated_hz": estimated_hz,
        "native_hz": estimated_hz,
        "supports_5Hz_downsample": estimated_hz >= 5.0,
        "supports_2Hz_downsample": estimated_hz >= 2.0,
        "supports_1Hz_downsample": estimated_hz >= 0.8,
        "supports_ratio_every2": row_count >= 4,
        "supports_ratio_every5": row_count >= 10,
        "source_role": source_role,
        "approved_for_current_runner": approved_for_current_runner,
        "absolute_1hz_interpretation": "native_no_op_or_redundant" if 0.8 <= estimated_hz <= 1.2 else "not_native",
        "recommended_ratio_cases": "every2;every5;every10" if row_count >= 20 else "insufficient_rows_for_ratio_family",
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(round((percentile / 100.0) * (len(values) - 1)))))
    return values[index]


def _discover_final_v23_15col_source(sources: SourcePaths) -> Path | None:
    if not sources.dual_yaw_gnss:
        return None
    root = sources.dual_yaw_gnss.parent
    for name in [
        "test1_statusyaw_fixed_1p5_case1.gnss",
        "test1_statusyaw_v23.gnss",
        "test1.gnss",
    ]:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _find_local_path_by_name(workspace_root: Path, filename: str) -> Path | None:
    local = workspace_root / "docs" / "codex_context" / "DATA_PATHS.local.md"
    if not local.exists():
        return None
    for line in local.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if len(text) > 3 and text[1:3] == ":\\" and text.endswith(filename):
            path = Path(text)
            if path.exists():
                return path
    return None


def _load_raw_nav_pvt_times(path: Path | None) -> list[float]:
    if path is None or not path.exists():
        return []
    times: list[float] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("name") != "UBX-NAV-PVT":
                continue
            try:
                times.append(float(row["Time"]) - GPS_TIME_OFFSET)
            except (KeyError, ValueError):
                continue
    return times


def _repair_pilot_plan(pilot_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in pilot_rows:
        repaired: dict[str, Any] = dict(row)
        if row.get("case_id") == OLD_DOWNSAMPLE_CASE_ID:
            repaired.update({
                "pilot_case_id": "downsample_every2",
                "case_id": REPAIRED_DOWNSAMPLE_CASE_ID,
                "case_name": "downsample_every2",
                "requested_pilot_case": "downsample_every2",
                "pilot_role": "deterministic GNSS ratio downsample keep every 2nd locked observation",
                "blocked_reason": "repaired from unsupported absolute 2Hz; old absolute 2Hz remains blocked under current locked about 1Hz inputs",
                "random_seed_need": "none",
                "random_value_manifest_need": "false",
                "execution_status": "not_run",
            })
        output.append(repaired)
    return output


def _build_repair_diff(cadence_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    native_rates = ";".join(f"{row['source_id']}={row['estimated_hz']:.3f}Hz" for row in cadence_audit)
    return [{
        "old_case_id": OLD_DOWNSAMPLE_CASE_ID,
        "new_case_id": REPAIRED_DOWNSAMPLE_CASE_ID,
        "old_policy": "absolute target_rate=2Hz",
        "new_policy": "ratio keep_every=2 from current locked input",
        "native_rates": native_rates,
        "old_status": "blocked_not_executable",
        "new_status": "ready_command_plan_only",
        "seed": "none",
        "random_values_required": False,
        "upsampling": False,
        "source_switch": False,
    }]


def _build_full_matrix_downsample_repair(full_rows: list[dict[str, str]], cadence_audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    approved_rows = [row for row in cadence_audit if row["approved_for_current_runner"] and row["row_count"] > 1]
    row_count = max((int(row["row_count"]) for row in approved_rows), default=0)
    native_hz = min((float(row["estimated_hz"]) for row in approved_rows), default=0.0)
    output: list[dict[str, Any]] = []
    for row in full_rows:
        case_id = row.get("case_id", "")
        if not case_id.startswith("B_gnss_downsample"):
            continue
        if case_id in {"B_gnss_downsample_5Hz", "B_gnss_downsample_2Hz"}:
            repair_status = "blocked_not_executable_current_locked_cadence"
            recommendation = "do_not_run_absolute_rate; use ratio cases every2/every5/every10"
        elif case_id in {"B_gnss_downsample_1Hz", "B_gnss_downsample_native"}:
            repair_status = "native_no_op_or_redundant"
            recommendation = "keep as audit metadata only; not a degradation case for current about 1Hz source"
        else:
            repair_status = "unchanged"
            recommendation = "review manually"
        output.append({
            "case_id": case_id,
            "family": row.get("family", "B"),
            "parameters": row.get("parameters", ""),
            "current_locked_min_native_hz": native_hz,
            "repair_status": repair_status,
            "recommended_replacement": recommendation,
            "random_seed": "none",
            "random_values_required": False,
            "execution_status": "not_run",
        })
    for every in [2, 5, 10]:
        output.append({
            "case_id": f"B_gnss_downsample_every{every}",
            "family": "B",
            "parameters": f"keep_every={every}",
            "current_locked_min_native_hz": native_hz,
            "repair_status": "recommended_ratio_case" if row_count >= every * 2 else "recommended_ratio_case_needs_more_rows",
            "recommended_replacement": "deterministic ratio downsample from locked input",
            "random_seed": "none",
            "random_values_required": False,
            "execution_status": "not_run",
        })
    return output


def _seed_rows(seed_plan: list[dict[str, str]]) -> dict[str, list[int]]:
    rows: dict[str, list[int]] = {case_id: [] for case_id in REPAIRED_PILOT_CASE_IDS}
    for row in seed_plan:
        case_id = row.get("case_id", "")
        if case_id in RANDOM_CASE_IDS and row.get("seed", "").isdigit():
            rows[case_id].append(int(row["seed"]))
    return {case_id: sorted(set(values)) for case_id, values in rows.items()}


def _generate_repaired_case(
    case_id: str,
    runtime_root: Path,
    clean7: list[list[float]],
    clean15: list[list[float]],
    sources: SourcePaths,
    seed_rows: list[int],
    write_outputs: bool,
) -> dict[str, Any]:
    case_dir = runtime_root / "repaired_inputs" / case_id
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

    if not clean7:
        blocked.append(_block(case_id, "source_missing", "gnss1-status.csv unavailable or empty"))
    if case_id == "H_dual_yaw_noise_medium" and not clean15:
        blocked.append(_block(case_id, "source_missing", "15-col dual-yaw GNSS input unavailable or empty"))

    if clean7:
        generated.extend(_generate_for_source(case_id, "single7", clean7, case_dir, random_values_dir, seed_rows, random_index, random_seed_manifest, random_value_manifest, write_outputs))
    if clean15:
        generated.extend(_generate_for_source(case_id, "dual15", clean15, case_dir, random_values_dir, seed_rows, random_index, random_seed_manifest, random_value_manifest, write_outputs))

    if write_outputs:
        _write_json(case_dir / "degradation_manifest.json", {
            "stage": STAGE,
            "case_id": case_id,
            "generated_input_count": len(generated),
            "blocked": bool(blocked),
            "blocked_items": blocked,
            "solver_run": False,
            "official_evaluator_run": False,
            "figures_generated": False,
        })
        _write_json(case_dir / "source_role.json", {**_source_role(case_id, sources), "stage": STAGE})
        _write_table_pair(case_dir / "generated_input_manifest", generated)
        _write_table_pair(case_dir / "random_seed_manifest", random_seed_manifest)
        _write_table_pair(case_dir / "random_value_manifest", random_value_manifest)
        (case_dir / "input_generation_log.txt").write_text(_case_log(case_id, generated, blocked), encoding="utf-8")
        _write_table_pair(random_dir / "random_seed_manifest", random_seed_manifest)
        _write_table_pair(random_dir / "random_value_manifest", random_value_manifest)
        _write_table_pair(random_dir / "hashes", [{"case_id": r["case_id"], "seed": r["seed"], "sha256": r["sha256"], "path": r["path"]} for r in random_index])
    return {"degraded_index": generated, "random_index": random_index, "blocked": blocked}


def _generate_for_source(
    case_id: str,
    tag: str,
    rows: list[list[float]],
    case_dir: Path,
    random_values_dir: Path,
    seed_rows: list[int],
    random_index: list[dict[str, Any]],
    random_seed_manifest: list[dict[str, Any]],
    random_value_manifest: list[dict[str, Any]],
    write_outputs: bool,
) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    if case_id == "A_outage_5s":
        output, mask = _apply_outage(rows)
        generated += _write_repaired_input(case_dir, case_id, tag, output, write_outputs, mask)
    elif case_id == REPAIRED_DOWNSAMPLE_CASE_ID:
        output, mask = _apply_downsample_every_n(rows, 2)
        generated += _write_repaired_input(case_dir, case_id, tag, output, write_outputs, mask)
    elif case_id == "C_position_noise_medium":
        for seed in seed_rows:
            output, values = _apply_position_noise(rows, seed)
            path = random_values_dir / f"seed_{seed}_{tag}_noise.csv"
            random_index.append(_random_stats(case_id, seed, "python_random_gauss", values, path))
            random_value_manifest.append(random_index[-1])
            random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
            if write_outputs:
                _write_dict_rows(path, values)
            generated += _write_repaired_input(case_dir, case_id, f"{tag}_seed_{seed}", output, write_outputs)
    elif case_id == "D_position_spike_medium":
        for seed in seed_rows:
            output, values = _apply_position_spikes(rows, seed)
            path = random_values_dir / f"seed_{seed}_{tag}_spikes.csv"
            random_index.append(_random_stats(case_id, seed, "python_random_spike_trigger", values, path))
            random_value_manifest.append(random_index[-1])
            random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
            if write_outputs:
                _write_dict_rows(path, values)
            generated += _write_repaired_input(case_dir, case_id, f"{tag}_seed_{seed}", output, write_outputs)
    elif case_id == "H_dual_yaw_noise_medium" and tag == "dual15":
        for seed in seed_rows:
            output, values = _apply_yaw_noise(rows, seed)
            path = random_values_dir / f"seed_{seed}_{tag}_yaw_noise.csv"
            random_index.append(_random_stats(case_id, seed, "python_random_yaw_gauss_deg", values, path))
            random_value_manifest.append(random_index[-1])
            random_seed_manifest.append(_seed_manifest(case_id, seed, len(values), random_index[-1]["sha256"]))
            if write_outputs:
                _write_dict_rows(path, values)
            generated += _write_repaired_input(case_dir, case_id, f"{tag}_seed_{seed}", output, write_outputs)
    elif case_id == "H_dual_yaw_noise_medium":
        generated += _write_repaired_input(case_dir, case_id, f"{tag}_clean", rows, write_outputs)
    else:
        generated += _write_repaired_input(case_dir, case_id, f"{tag}_clean", rows, write_outputs)
    return generated


def _write_repaired_input(
    case_dir: Path,
    case_id: str,
    tag: str,
    rows: list[list[float]],
    write_outputs: bool,
    mask: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    generated = _write_input(case_dir, case_id, tag, rows, write_outputs, mask)
    for row in generated:
        row["path"] = row["path"].replace("degraded_inputs/", "repaired_inputs/", 1)
    return generated


def _apply_downsample_every_n(rows: list[list[float]], every_n: int = 2) -> tuple[list[list[float]], list[dict[str, Any]]]:
    kept = [row for index, row in enumerate(rows) if index % every_n == 0]
    mask = [{"index": index, "time": row[0], "kept": index % every_n == 0, "keep_every_n": every_n} for index, row in enumerate(rows)]
    return kept, mask


def _build_repaired_solver_plan(
    runtime_root: Path,
    pilot_plan: list[dict[str, Any]],
    routing_rows: list[dict[str, str]],
    degraded_index: list[dict[str, Any]],
    case_ready: dict[str, bool],
    write_outputs: bool,
) -> list[dict[str, Any]]:
    old_route_lookup = {(row.get("case_id", ""), row.get("algorithm_group", "")): row for row in routing_rows}
    input_lookup: dict[str, list[str]] = {}
    for row in degraded_index:
        input_lookup.setdefault(row["case_id"], []).append(row["path"])
    output: list[dict[str, Any]] = []
    for row in pilot_plan:
        case_id = row["case_id"]
        algorithms = _split_algorithms(row.get("applicable_algorithms", "")) + _split_algorithms(row.get("diagnostic_only_algorithms", ""))
        for algorithm in algorithms:
            if algorithm == "none":
                continue
            route_key = (OLD_DOWNSAMPLE_CASE_ID if case_id == REPAIRED_DOWNSAMPLE_CASE_ID else case_id, algorithm)
            routing_status = old_route_lookup.get(route_key, {}).get("routing_status") or ("diagnostic_only" if algorithm in _split_algorithms(row.get("diagnostic_only_algorithms", "")) else "applicable")
            plan_dir = runtime_root / "solver_command_plan" / case_id / algorithm
            command = (
                "python -m legsa_gins.future_solver_entry "
                f"--case {case_id} --algorithm {algorithm} "
                f"--input-root ${{WSL_AUDIT_ROOT}}/{AUDIT_ROOT_NAME}/{STAGE}/repaired_inputs/{case_id} "
                f"--output-root ${{WSL_AUDIT_ROOT}}/{AUDIT_ROOT_NAME}/{STAGE}/future_solver_outputs/{case_id}/{algorithm}"
            )
            if write_outputs:
                plan_dir.mkdir(parents=True, exist_ok=True)
                _write_json(plan_dir / "solver_command.json", {
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
                })
                _write_json(plan_dir / "expected_outputs.json", {
                    "future_expectation_only": True,
                    "expected_outputs": ["NAV.csv", "STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"],
                    "official_evaluator_command_plan": "future N9B1B only; not executed in N9B1A1",
                })
                _write_json(plan_dir / "source_role.json", {"trace": "evaluation_only_not_solver_input", "final_v23": "reference_only_not_solver_input"})
            output.append({
                "case_id": case_id,
                "algorithm": algorithm,
                "routing_status": routing_status,
                "ready_for_N9B1B_solver_execution": bool(case_ready.get(case_id)) and bool(input_lookup.get(case_id)),
                "solver_command_json": f"solver_command_plan/{case_id}/{algorithm}/solver_command.json",
                "expected_outputs_json": f"solver_command_plan/{case_id}/{algorithm}/expected_outputs.json",
                "source_role_json": f"solver_command_plan/{case_id}/{algorithm}/source_role.json",
                "solver_run": False,
                "official_evaluator_run": False,
            })
    return output


def _build_repaired_pilot_ready(
    pilot_plan: list[dict[str, Any]],
    solver_index: list[dict[str, Any]],
    case_ready: dict[str, bool],
    blocked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocked_cases = {row["case_id"] for row in blocked}
    solver_cases = {row["case_id"] for row in solver_index if row["ready_for_N9B1B_solver_execution"]}
    candidate_cases = {row["case_id"] for row in solver_index}
    output = []
    for row in pilot_plan:
        case_id = row["case_id"]
        plan_ready = case_id not in candidate_cases or case_id in solver_cases
        ready = bool(case_ready.get(case_id)) and plan_ready and case_id not in blocked_cases
        output.append({
            "case_id": case_id,
            "degraded_inputs_ready": bool(case_ready.get(case_id)),
            "solver_command_plan_ready": plan_ready,
            "ready_for_N9B1B_solver_execution": ready,
            "ready_for_solver_execution": False,
            "ready_for_N9B2_execution": False,
        })
    return output


def _split_algorithms(value: str) -> list[str]:
    if not value or value == "none":
        return []
    return [item.split(":", 1)[0] for item in value.split(";") if item and item != "none"]


def _write_outputs(runtime_root: Path, result: dict[str, Any]) -> None:
    reports = {
        "N9B1A1_GNSS_CADENCE_AUDIT_REPORT.json": result["gnss_cadence_audit_report"],
        "N9B1A1_DOWNSAMPLE_POLICY_REPAIR_REPORT.json": result["downsample_policy_repair_report"],
        "N9B1A1_PILOT_PLAN_REPAIR_REPORT.json": result["pilot_plan_repair_report"],
        "N9B1A1_INPUT_REPAIR_REPORT.json": result["input_repair_report"],
        "N9B1A1_SAFETY_GATE_REPORT.json": result["safety_gate_report"],
        "N9B1A1_DECISION_REPORT.json": result["decision_report"],
    }
    for name, payload in reports.items():
        _write_json(runtime_root / "reports" / name, payload)
    matrices = {
        "N9B1A1_GNSS_CADENCE_AUDIT": result["gnss_cadence_audit"],
        "N9B1A1_DOWNSAMPLE_CASE_REPAIR_DIFF": result["downsample_case_repair_diff"],
        "N9B1A1_PILOT_CASE_PLAN_REPAIRED": result["pilot_case_plan_repaired"],
        "N9B1A1_DEGRADED_INPUT_INDEX_REPAIRED": result["degraded_input_index_repaired"],
        "N9B1A1_SOLVER_COMMAND_PLAN_INDEX_REPAIRED": result["solver_command_plan_index_repaired"],
        "N9B1A1_PILOT_READY_MATRIX_REPAIRED": result["pilot_ready_matrix_repaired"],
        "N9B1A1_FULL_MATRIX_DOWNSAMPLE_REPAIR": result["full_matrix_downsample_repair"],
    }
    for stem, rows in matrices.items():
        _write_table_pair(runtime_root / "matrix" / stem, rows)
        if stem in {"N9B1A1_PILOT_CASE_PLAN_REPAIRED", "N9B1A1_FULL_MATRIX_DOWNSAMPLE_REPAIR"}:
            _write_table_pair(runtime_root / "repaired_matrices" / stem, rows)
    _write_table_pair(runtime_root / "cadence_audit" / "N9B1A1_GNSS_CADENCE_AUDIT", result["gnss_cadence_audit"])
    summaries = {
        "n9b1a1_gnss_cadence_audit.md": _summary_cadence(result),
        "n9b1a1_downsample_policy_repair.md": _summary_policy(result),
        "n9b1a1_pilot_plan_repaired.md": _summary_pilot(result),
        "n9b1a1_full_matrix_downsample_repair.md": _summary_full(result),
    }
    for name, text in summaries.items():
        (runtime_root / "summary" / name).write_text(text, encoding="utf-8")
    _write_json(runtime_root / "validation" / "N9B1A1_VALIDATION_REPORT.json", result["validation"])


def _summary_cadence(result: dict[str, Any]) -> str:
    lines = ["# N9B1A1 GNSS cadence audit", ""]
    for row in result["gnss_cadence_audit"]:
        lines.append(
            f"- {row['source_id']}: rows={row['row_count']}, "
            f"median_dt={row['median_dt']:.6f}, p95_dt={row['p95_dt']:.6f}, "
            f"estimated_hz={row['estimated_hz']:.3f}, "
            f"supports_2Hz_downsample={str(row['supports_2Hz_downsample']).lower()}, "
            f"approved_for_current_runner={str(row['approved_for_current_runner']).lower()}"
        )
    lines.append("- Decision: absolute 2Hz is blocked for the current locked about 1Hz inputs.")
    return "\n".join(lines) + "\n"


def _summary_policy(result: dict[str, Any]) -> str:
    report = result["downsample_policy_repair_report"]
    return (
        "# N9B1A1 downsample policy repair\n\n"
        f"- Old case: {report['old_case_id']}.\n"
        f"- Repaired case: {report['repaired_case_id']}.\n"
        "- Policy: deterministic keep every 2nd locked observation by source index.\n"
        "- Seed: none; random_values_required=false.\n"
        "- Solver/evaluator/figures run: false.\n"
    )


def _summary_pilot(result: dict[str, Any]) -> str:
    return (
        "# N9B1A1 repaired pilot plan\n\n"
        f"- Pilot cases: {len(result['pilot_case_plan_repaired'])}.\n"
        f"- Ready rows: {sum(1 for row in result['pilot_ready_matrix_repaired'] if row['ready_for_N9B1B_solver_execution'])}.\n"
        f"- Decision: {result['decision_report']['status']}.\n"
        "- ready_for_solver_execution=false; ready_for_N9B2_execution=false.\n"
    )


def _summary_full(result: dict[str, Any]) -> str:
    return (
        "# N9B1A1 full matrix downsample repair\n\n"
        "- Absolute 5Hz and 2Hz cases are blocked for current locked about 1Hz inputs.\n"
        "- Native/1Hz cases are no-op or redundant under the current source cadence.\n"
        "- Recommended deterministic ratio cases: every2, every5, every10 when enough rows exist.\n"
        f"- Repair rows: {len(result['full_matrix_downsample_repair'])}.\n"
    )


def _create_runtime_tree(runtime_root: Path) -> None:
    for subdir in REQUIRED_SUBDIRS:
        (runtime_root / subdir).mkdir(parents=True, exist_ok=True)


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
        "path": _runtime_rel(path),
        "affects_algorithm_input": True,
        "affects_metric": True,
        "toy_only": False,
        "pilot_only": True,
        "N9B2_full": False,
    }


def _seed_manifest(case_id: str, seed: int, value_count: int, sha256: str) -> dict[str, Any]:
    return {"case_id": case_id, "seed": seed, "value_count": value_count, "sha256": sha256, "pilot_only": True, "N9B2_full": False}


def _case_log(case_id: str, generated: list[dict[str, Any]], blocked: list[dict[str, Any]]) -> str:
    lines = [f"case_id={case_id}", "solver_run=false", "official_evaluator_run=false", f"generated_input_count={len(generated)}"]
    lines.extend(f"blocked={row['blocked_reason']}" for row in blocked)
    return "\n".join(lines) + "\n"


def _block(case_id: str, blocked_stage: str, reason: str) -> dict[str, Any]:
    return {"case_id": case_id, "blocked_stage": blocked_stage, "blocked_reason": reason, "ready_for_N9B1B_solver_execution": False}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _sha256_rows(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _runtime_rel(path: Path) -> str:
    parts = path.as_posix().split(f"{STAGE}/", 1)
    return parts[-1] if len(parts) == 2 else path.name


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
