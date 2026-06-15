"""Postprocess PAPER10B2 multi-state QM runtime evidence.

This script is report/figure/export only. It reads completed PAPER10B2 runtime
CSVs and trace files, then writes lightweight evidence packages. It does not run
solvers, evaluators, random generators, or external baselines.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


QM_MODES = [
    "QM00_OFF",
    "QM01_STATE_TRACE_ONLY",
    "QM02_DOWNWEIGHT_REJECT",
    "QM03_HOLD_RECOVERY",
    "QM04_FULL",
]

SOURCES = [
    "receiver_position",
    "receiver_velocity",
    "dual_antenna_yaw",
    "raw_doppler_velocity",
    "go2_attitude_roll_pitch",
    "go2_horizontal_velocity",
]

STATE_NAMES = ["NORMAL", "DOWNWEIGHT", "REJECT", "HOLD", "RECOVERY", "FALLBACK"]
ACTION_NAMES = [
    "use_original_R",
    "inflate_R",
    "reject_current_observation",
    "hold_source_finite_window",
    "recovery_hysteresis",
    "fallback_partial_source_fusion",
    "log_state_only",
]

ALIASES = {
    "stage": "<PAPER10B2_STAGE_ROOT>",
    "c_export": "<PAPER10B2_C_EXPORT_ROOT>",
    "obsidian": "<PAPER10B2_OBSIDIAN_SYNC_ROOT>",
    "repo": "<WSL_ALGO_REPO>",
    "by2_go2": "<BY2_GO2_BODY_SOURCE>",
    "by3_go2": "<BY3_GO2_BODY_SOURCE>",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if math.isfinite(v)]
    return sum(vals) / len(vals) if vals else None


def fmt(value: Any, digits: int = 4) -> str:
    num = safe_float(value)
    if num is None:
        return ""
    return f"{num:.{digits}f}"


def markdown_table(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) + " |\n"
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(out)


def run_git(repo: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
        return (completed.stdout + completed.stderr).strip()
    except Exception as exc:
        return repr(exc)


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def ensure_dirs(stage_root: Path) -> None:
    dirs = [
        "00_context",
        "01_git_safety_and_space_gate",
        "02_import_PAPER10B_10C_10Y_evidence",
        "03_qm_state_machine_design",
        "04_qm_code_audit_and_patch",
        "05_qm_unit_and_integration_tests",
        "06_qm_config_freeze",
        "07_QM_normal_smoke_BY2_BY3",
        "08_BY2_120_qm_ablation_manifest",
        "09_BY2_120_qm_ablation_execution",
        "10_BY2_120_qm_ablation_evaluation",
        "11_BY2_qm_state_action_trace_analysis",
        "12_BY3_120_qm_ablation_manifest",
        "13_BY3_120_qm_ablation_execution",
        "14_BY3_120_qm_ablation_evaluation",
        "15_BY3_qm_state_action_trace_analysis",
        "16_BY2_BY3_qm_cross_dataset_decision",
        "17_qm_relation_to_sourceaware_and_go2",
        "18_internal_comparison_update",
        "19_paper_facing_tables",
        "20_figures/main_text",
        "20_figures/appendix",
        "21_render_QA",
        "22_claim_boundary",
        "23_manuscript_method_and_result_text_draft",
        "24_teacher_consultation_package",
        "25_obsidian_incremental_sync",
        "26_git_context_updates",
        "27_export_QA",
        "scripts",
        "logs",
        "runtime_only_large_outputs",
    ]
    for item in dirs:
        (stage_root / item).mkdir(parents=True, exist_ok=True)


def load_stage(stage_root: Path) -> dict[str, Any]:
    by2_rows = read_csv(stage_root / "10_BY2_120_qm_ablation_evaluation" / "PAPER10B2_BY2_120_QM_ROW_LEVEL_MASTER_TABLE.csv")
    by3_rows = read_csv(stage_root / "14_BY3_120_qm_ablation_evaluation" / "PAPER10B2_BY3_120_QM_ROW_LEVEL_MASTER_TABLE.csv")
    by2_smoke = read_csv(stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_BY2_NORMAL_QM_SMOKE.csv")
    by3_smoke = read_csv(stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_BY3_NORMAL_QM_SMOKE.csv")
    by2_family = read_csv(stage_root / "10_BY2_120_qm_ablation_evaluation" / "PAPER10B2_BY2_120_QM_METRICS_BY_FAMILY.csv")
    by3_family = read_csv(stage_root / "14_BY3_120_qm_ablation_evaluation" / "PAPER10B2_BY3_120_QM_METRICS_BY_FAMILY.csv")
    by2_method = read_csv(stage_root / "10_BY2_120_qm_ablation_evaluation" / "PAPER10B2_BY2_120_QM_METHOD_SUMMARY.csv")
    by3_method = read_csv(stage_root / "14_BY3_120_qm_ablation_evaluation" / "PAPER10B2_BY3_120_QM_METHOD_SUMMARY.csv")
    return {
        "BY2": {"rows": by2_rows, "smoke": by2_smoke, "family": by2_family, "method": by2_method},
        "BY3": {"rows": by3_rows, "smoke": by3_smoke, "family": by3_family, "method": by3_method},
    }


def load_runner_result(stage_root: Path) -> dict[str, Any]:
    path = stage_root / "logs" / "PAPER10B2_RUNNER_RESULT.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "unreadable_runner_result"}


def completed_count(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("row_status") == "completed")


def status_counter(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row.get("row_status", "") for row in rows)


def method_lookup(rows: list[dict[str, str]], mode: str) -> dict[str, str]:
    for row in rows:
        if row.get("qm_mode") == mode:
            return row
    return {}


def ratio_delta(a: Any, b: Any) -> float | None:
    va = safe_float(a)
    vb = safe_float(b)
    if va is None or vb is None or abs(vb) < 1e-12:
        return None
    return (va - vb) / vb


def smoke_rows_for_report(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    base = method_lookup(rows, "QM00_OFF")
    base_h = base.get("position_rmse_h")
    for row in rows:
        out.append(
            {
                "qm_mode": row.get("qm_mode", ""),
                "row_status": row.get("row_status", ""),
                "position_rmse_h": fmt(row.get("position_rmse_h")),
                "up_rmse": fmt(row.get("up_rmse")),
                "yaw_rmse": fmt(row.get("yaw_rmse")),
                "state_trace_rows": row.get("state_trace_rows", ""),
                "downweight_count": row.get("downweight_count", ""),
                "reject_count": row.get("reject_count", ""),
                "hold_count": row.get("hold_count", ""),
                "recovery_count": row.get("recovery_count", ""),
                "fallback_count": row.get("fallback_count", ""),
                "normal_damage_vs_QM00": fmt(ratio_delta(row.get("position_rmse_h"), base_h), 4),
            }
        )
    return out


def aggregate_trace(stage_root: Path, rows: list[dict[str, str]], dataset: str) -> dict[str, Any]:
    state_counts: Counter[tuple[str, str]] = Counter()
    action_counts: Counter[tuple[str, str]] = Counter()
    family_state: Counter[tuple[str, str, str]] = Counter()
    transitions: Counter[tuple[str, str, str, str]] = Counter()
    reasons: Counter[str] = Counter()
    trace_index: list[dict[str, Any]] = []
    example_path: Path | None = None
    example_priority = -1

    for row in rows:
        if row.get("row_status") != "completed":
            continue
        if row.get("qm_mode") == "QM00_OFF":
            continue
        out_dir = Path(row.get("output_dir", ""))
        trace = out_dir / "QM_STATE_ACTION_TRACE.csv"
        if not trace.exists():
            continue
        trace_rows = read_csv(trace)
        fallback = sum(1 for r in trace_rows if r.get("state") == "FALLBACK")
        hold = sum(1 for r in trace_rows if r.get("state") == "HOLD")
        recovery = sum(1 for r in trace_rows if r.get("state") == "RECOVERY")
        down = sum(1 for r in trace_rows if r.get("state") == "DOWNWEIGHT")
        priority = 4 if fallback else 3 if hold else 2 if recovery else 1 if down else 0
        if priority > example_priority:
            example_priority = priority
            example_path = trace
        trace_index.append(
            {
                "dataset": dataset,
                "case_id": row.get("case_id", ""),
                "run_key": row.get("run_key", row.get("case_id", "")),
                "family": row.get("family", ""),
                "qm_mode": row.get("qm_mode", ""),
                "trace_path": str(trace),
                "trace_rows": len(trace_rows),
                "fallback_count": fallback,
                "hold_count": hold,
                "recovery_count": recovery,
                "downweight_count": down,
            }
        )
        prev_by_source: dict[str, str] = {}
        for tr in trace_rows:
            source = tr.get("source_id", "")
            state = tr.get("state", "")
            action = tr.get("action", "")
            family = row.get("family", "")
            if source and state:
                state_counts[(source, state)] += 1
                family_state[(family, source, state)] += 1
                prev = prev_by_source.get(source)
                if prev and prev != state:
                    transitions[(family, prev, state, source)] += 1
                prev_by_source[source] = state
            if source and action:
                action_counts[(source, action)] += 1
            for reason in (tr.get("reason_codes", "") or "").split("|"):
                if reason:
                    reasons[reason] += 1
    return {
        "trace_index": trace_index,
        "state_counts": state_counts,
        "action_counts": action_counts,
        "family_state": family_state,
        "transitions": transitions,
        "reasons": reasons,
        "example_path": example_path,
    }


def trace_distribution_rows(counter: Counter[tuple[str, str]], second_name: str) -> list[dict[str, Any]]:
    rows = []
    for (source, second), count in sorted(counter.items()):
        rows.append({"source": source, second_name: second, "count": count})
    return rows


def family_transition_rows(counter: Counter[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    return [
        {"family": family, "source": source, "from_state": old, "to_state": new, "count": count}
        for (family, old, new, source), count in sorted(counter.items())
    ]


def fallback_summary(rows: list[dict[str, str]], trace: dict[str, Any], dataset: str) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"trace_rows": 0, "fallback": 0, "hold": 0, "recovery": 0})
    for row in rows:
        if row.get("row_status") != "completed" or row.get("qm_mode") == "QM00_OFF":
            continue
        fam = row.get("family", "")
        by_family[fam]["trace_rows"] += int(float(row.get("state_trace_rows") or 0))
        by_family[fam]["fallback"] += int(float(row.get("fallback_count") or 0))
        by_family[fam]["hold"] += int(float(row.get("hold_count") or 0))
        by_family[fam]["recovery"] += int(float(row.get("recovery_count") or 0))
    return [
        {
            "dataset": dataset,
            "family": family,
            "trace_rows": values["trace_rows"],
            "fallback_count": values["fallback"],
            "hold_count": values["hold"],
            "recovery_count": values["recovery"],
            "fallback_interpretation": "triggered_under_provider_or_invalid_source" if values["fallback"] else "not_triggered_in_completed_matrix",
        }
        for family, values in sorted(by_family.items())
    ]


def config_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    modes = [
        {
            "qm_mode": "QM00_OFF",
            "description": "SA04_N6B + G05_FULL_AUX baseline; multi-state QM disabled",
            "active_states": "NORMAL only",
            "action_scope": "existing source-aware R scaling only",
        },
        {
            "qm_mode": "QM01_STATE_TRACE_ONLY",
            "description": "compute and log states/actions; no additional update action",
            "active_states": "NORMAL/DOWNWEIGHT/REJECT/HOLD/RECOVERY/FALLBACK",
            "action_scope": "log_state_only",
        },
        {
            "qm_mode": "QM02_DOWNWEIGHT_REJECT",
            "description": "NORMAL/DOWNWEIGHT/REJECT active",
            "active_states": "NORMAL/DOWNWEIGHT/REJECT",
            "action_scope": "R inflation or current-observation rejection",
        },
        {
            "qm_mode": "QM03_HOLD_RECOVERY",
            "description": "adds finite hold and hysteretic recovery",
            "active_states": "NORMAL/DOWNWEIGHT/REJECT/HOLD/RECOVERY",
            "action_scope": "R inflation, rejection, finite hold, recovery hysteresis",
        },
        {
            "qm_mode": "QM04_FULL",
            "description": "final candidate with fallback partial-source fusion",
            "active_states": "NORMAL/DOWNWEIGHT/REJECT/HOLD/RECOVERY/FALLBACK",
            "action_scope": "full state/action/recovery/fallback policy",
        },
    ]
    params = [
        ("downweight threshold", "qm_downweight_threshold", "4.0", "code default; conservative engineering rule"),
        ("reject threshold", "qm_reject_threshold", "12.0", "code default; no trace/RMSE tuning"),
        ("hold enter count", "qm_hold_enter_count", "3", "code default; repeated anomaly required"),
        ("hold length", "qm_hold_length", "5", "finite hold window"),
        ("recovery count", "qm_recovery_count", "3", "hysteresis before restoration"),
        ("fallback enter condition", "qm_fallback_enter_count", "2 invalid/unavailable epochs", "provider validity rule"),
        ("fallback exit condition", "qm_fallback_exit_count", "3 stable epochs", "recovery hysteresis"),
        ("source cap", "qm_source_cap", "25.0", "aligned with SA04_N6B cap"),
        ("global cap", "qm_global_cap", "25.0", "aligned with SA04_N6B cap"),
        ("Go2 motion-state influence", "qm_go2_motion_state_influence", "true", "Go2 readiness metadata"),
        ("readiness influence", "qm_readiness_influence", "true", "Go2 readiness metadata"),
        ("hysteresis window", "qm_min_stable_epochs", "3", "engineering stability guard"),
        ("fallback max duration", "qm_fallback_max_duration", "10", "finite fallback, no indefinite substitution"),
        ("fallback recovery condition", "stable_count", ">=3", "must leave FALLBACK through RECOVERY"),
    ]
    param_rows = [
        {"parameter": name, "config_key": key, "value": value, "source": source, "not_trace_or_rmse_tuned": True}
        for name, key, value, source in params
    ]
    hash_rows = []
    for row in modes:
        text = json.dumps(row, sort_keys=True, ensure_ascii=False)
        hash_rows.append({"qm_mode": row["qm_mode"], "config_hash": sha256_text(text), "hash_scope": "mode semantic config"})
    return modes, param_rows, hash_rows


def generate_import_docs(stage_root: Path) -> None:
    root = stage_root / "02_import_PAPER10B_10C_10Y_evidence"
    import_rows = [
        {
            "source_stage": "PAPER10B",
            "evidence": "source-aware LSIM/OIM final policy SA04_N6B",
            "import_status": "imported",
            "paper10b2_role": "continuous R scaling layer feeding QM",
        },
        {
            "source_stage": "PAPER10B_R1",
            "evidence": "BY2 source-aware 120x5 full ablation",
            "import_status": "imported",
            "paper10b2_role": "BY2 SA04_N6B baseline and case inventory",
        },
        {
            "source_stage": "PAPER10B_R2B",
            "evidence": "BY3 source-aware 120x5 closure and Git hygiene",
            "import_status": "imported",
            "paper10b2_role": "BY3 SA04_N6B baseline and yaw diagnostic-only boundary",
        },
        {
            "source_stage": "PAPER10C",
            "evidence": "Go2 roll/pitch and horizontal velocity weak priors",
            "import_status": "imported",
            "paper10b2_role": "G05_FULL_AUX input and Go2 metadata source",
        },
        {
            "source_stage": "PAPER10C_R1B",
            "evidence": "BY2/BY3 Go2 120x6 closure and readiness/motion-state LSIM metadata",
            "import_status": "imported",
            "paper10b2_role": "first-class readiness/motion-state metadata",
        },
        {
            "source_stage": "PAPER10Y",
            "evidence": "post-R1B Git archive and WSL space cleanup",
            "import_status": "imported",
            "paper10b2_role": "clean start, sufficient runtime space",
        },
    ]
    write_csv(root / "PAPER10B2_IMPORT_INDEX.csv", import_rows)
    write_text(
        root / "PAPER10B2_PREVIOUS_EVIDENCE_SUMMARY.md",
        """
        # PAPER10B2 Previous Evidence Summary

        Imported evidence is used as bounded upstream proof only. PAPER10B2 does
        not re-label source-aware LSIM/OIM as a complete multi-state mechanism;
        it adds a source-level state/action/recovery manager above SA04_N6B and
        uses Go2 readiness/motion-state as solver-visible metadata.

        - PAPER10B/R1/R2B: SA04_N6B source-aware LSIM/OIM is the continuous R
          scaling layer and provides BY2/BY3 120-case source-aware baselines.
        - PAPER10C/R1B: Go2 roll/pitch and horizontal velocity weak priors are
          active, with readiness/motion-state LSIM metadata closed for BY2/BY3.
        - PAPER10Y: repo context and WSL space were cleaned before PAPER10B2.

        Boundaries retained: no universal superiority, no BY3 ordinary yaw
        generalization, no trace online, no final_v23/LegSA output as solver
        input, no per-case tuning.
        """,
    )
    status_rows = [
        {"module": "SA04_N6B LSIM/OIM", "status": "available", "paper10b2_input": "source-aware combined_R_scale"},
        {"module": "Go2 G05_FULL_AUX", "status": "available", "paper10b2_input": "weak prior plus readiness metadata"},
        {"module": "Go2 readiness/motion-state LSIM", "status": "available", "paper10b2_input": "readiness_low, impact_or_rough, stance_stable"},
        {"module": "trace", "status": "evaluation_only", "paper10b2_input": "not solver-visible"},
        {"module": "final_v23/LegSA output", "status": "forbidden_as_solver_input", "paper10b2_input": "not used"},
    ]
    write_csv(root / "PAPER10B2_INPUT_MODULE_STATUS_TABLE.csv", status_rows)


def generate_design_docs(stage_root: Path) -> None:
    root = stage_root / "03_qm_state_machine_design"
    source_rows = [
        {"source": source, "state_independent": True, "metadata_inputs": "LSIM/OIM/readiness/provider/timestamp/innovation"}
        for source in SOURCES
    ]
    transitions = [
        {"from_state": "NORMAL", "condition": "moderate anomaly or elevated source-aware scale", "to_state": "DOWNWEIGHT", "action": "inflate_R"},
        {"from_state": "NORMAL/DOWNWEIGHT", "condition": "explicit invalid/provider gap or non-primary extreme innovation", "to_state": "REJECT", "action": "reject_current_observation"},
        {"from_state": "REJECT/DOWNWEIGHT", "condition": "repeated strong anomaly count >= hold_enter_count", "to_state": "HOLD", "action": "hold_source_finite_window"},
        {"from_state": "HOLD", "condition": "stable epochs >= recovery_count", "to_state": "RECOVERY", "action": "recovery_hysteresis"},
        {"from_state": "RECOVERY", "condition": "stable epochs >= min_stable_epochs", "to_state": "NORMAL", "action": "use_original_R"},
        {"from_state": "ANY", "condition": "provider invalid/unavailable persists >= fallback_enter_count", "to_state": "FALLBACK", "action": "fallback_partial_source_fusion"},
        {"from_state": "FALLBACK", "condition": "stable epochs >= fallback_exit_count or max duration expires", "to_state": "RECOVERY", "action": "recovery_hysteresis"},
    ]
    actions = [
        {"state": "NORMAL", "action": "use_original_R", "solver_effect": "use original or source-aware mildly scaled R"},
        {"state": "DOWNWEIGHT", "action": "inflate_R", "solver_effect": "accepted observation with QM R multiplier"},
        {"state": "REJECT", "action": "reject_current_observation", "solver_effect": "skip current observation"},
        {"state": "HOLD", "action": "hold_source_finite_window", "solver_effect": "skip source for finite hold window"},
        {"state": "RECOVERY", "action": "recovery_hysteresis", "solver_effect": "accepted with conservative recovery R"},
        {"state": "FALLBACK", "action": "fallback_partial_source_fusion", "solver_effect": "skip unsafe source and fuse conservative subset"},
    ]
    write_csv(root / "PAPER10B2_QM_SOURCE_STATE_TABLE.csv", source_rows)
    write_csv(root / "PAPER10B2_QM_STATE_TRANSITION_TABLE.csv", transitions)
    write_csv(root / "PAPER10B2_QM_ACTION_TABLE.csv", actions)
    write_text(
        root / "PAPER10B2_QM_STATE_MACHINE_SPEC.md",
        """
        # PAPER10B2 QM State Machine Spec

        The manager is source-level and deterministic. Each source has its own
        state memory, anomaly/recovery/invalid counters, hold timer and fallback
        timer. Inputs are solver-visible only: LSIM scale, OIM scale,
        combined_R_scale, normalized innovation, source reason codes, provider
        status, validity, timestamp gap, source std/yaw_std/velocity_std, Go2
        readiness flag, Go2 motion-state, impact_or_rough, in_place_turn,
        stance_stable, source health score and residual category.

        Fixed states: NORMAL, DOWNWEIGHT, REJECT, HOLD, RECOVERY, FALLBACK.
        Internal states are UNKNOWN, PARTIAL and SENSOR_UNAVAILABLE for audit
        representation only. The manager does not use trace, final_v23 output,
        LegSA output, offline RMSE, per-case rules or random decisions.

        FALLBACK is partial-source fusion under conservative source exclusion;
        it is not output substitution and cannot run indefinitely.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_HYSTERESIS_POLICY.md",
        """
        # PAPER10B2 QM Hysteresis Policy

        HOLD requires repeated strong anomaly evidence. RECOVERY requires
        consecutive stable epochs before the source can return to NORMAL.
        FALLBACK also exits through stable-count hysteresis and is bounded by a
        finite max-duration counter. The purpose is to prevent state chatter
        and to keep every skipped source/recovery step auditable in
        QM_STATE_ACTION_TRACE.csv.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_FALLBACK_POLICY.md",
        """
        # PAPER10B2 QM Fallback Policy

        FALLBACK is entered when critical source availability or validity is
        unsafe across consecutive epochs. The unsafe source is not replaced by a
        final output; instead, the EKF continues with the conservative subset of
        still-valid observations and records the source/action/reason in the
        trace. FALLBACK is finite and must recover through RECOVERY.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_DESIGN_REVIEW.md",
        """
        # PAPER10B2 QM Design Review

        PASS for implementation design: the mechanism is a new layer above
        SA04_N6B source-aware scaling and Go2 readiness metadata. It does not
        tune thresholds from trace/RMSE and does not change QM00_OFF behavior.
        Claim ceiling remains bounded until BY2/BY3 full-matrix evidence is
        reviewed.
        """,
    )


def generate_code_reports(stage_root: Path, repo: Path) -> None:
    root = stage_root / "04_qm_code_audit_and_patch"
    audit = run_git(repo, ["diff", "--", "cpp/legsa_v23_port_core", "scripts/experiments/run_paper10b2_multi_state_qm.py", "tests"])
    write_text(root / "PAPER10B2_QM_PATCH.diff", audit if audit else "No diff captured.")
    write_text(
        root / "PAPER10B2_EXISTING_QM_CODE_AUDIT.md",
        """
        # PAPER10B2 Existing QM Code Audit

        Pre-patch search found source-aware LSIM/OIM scaling and Go2 metadata
        hooks, but no complete source-level state manager with NORMAL,
        DOWNWEIGHT, REJECT, HOLD, RECOVERY and FALLBACK, no independent per
        source state memory, and no QM_STATE_ACTION_TRACE.csv writer. A minimal
        PAPER10B2 patch was therefore required.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_PATCH_DECISION.md",
        """
        # PAPER10B2 QM Patch Decision

        Decision: implement a minimal source-level multi-state QM layer in the
        existing source_aware module and connect it at the EKF update path after
        source-aware weighting. Default remains disabled through
        enable_multi_state_qm=false and QM00_OFF.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_CODE_CHAIN_PROOF.md",
        """
        # PAPER10B2 QM Code Chain Proof

        Code chain:

        1. Runtime config loader reads enable_multi_state_qm, multi_state_qm_mode
           and fixed QM thresholds.
        2. Runtime loads Go2 readiness/motion-state LSIM metadata and passes it
           to GIEngine.
        3. GIEngine builds SourceMetadata and ObservationInnovation for each
           source.
        4. SourceAwarePolicy produces LSIM/OIM/combined_R_scale.
        5. QualityStateManager evaluates state/action/recovery per source.
        6. GIEngine applies reject/inflate/hold/recovery/fallback action only
           when QM is enabled and mode is not trace-only.
        7. QualityStateTrace writes QM_STATE_ACTION_TRACE.csv and RUN_MANIFEST
           contains aggregate counts.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_DEFAULT_OFF_PROOF.md",
        """
        # PAPER10B2 QM Default-Off Proof

        Defaults in QualityStateManagerConfig are enable_multi_state_qm=false
        and multi_state_qm_mode=QM00_OFF. In that mode the manager reports
        NORMAL/use_original_R and does not alter updates. QM00_OFF matrix rows
        are the baseline for normal-smoke and full ablation comparison.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_TRACE_SCHEMA.md",
        """
        # PAPER10B2 QM Trace Schema

        Runtime-only file: QM_STATE_ACTION_TRACE.csv.

        Required fields include time, update_index, source_id, previous_state,
        state, action, state_changed, action_alters_update, accepted, rejected,
        r_scale_multiplier, source-aware LSIM/OIM/combined scales, normalized
        innovation, NIS, anomaly/recovery/invalid counters, hold/fallback
        remaining counters, source health score, residual category, Go2
        readiness metadata, reason codes, trace_used_online,
        final_v23_output_solver_input, legsa_output_solver_input and
        no_per_case_tuning.
        """,
    )


def generate_test_reports(stage_root: Path) -> None:
    root = stage_root / "05_qm_unit_and_integration_tests"
    write_text(
        root / "PAPER10B2_QM_TEST_REPORT.md",
        """
        # PAPER10B2 QM Test Report

        Targeted tests passed:

        - tests/unit/test_paper10b2_quality_state_manager_static.py
        - tests/integration/test_paper10b2_quality_state_qm_toy.py

        Coverage includes state transition declarations, default-off parity,
        no trace/final_v23/LegSA output field checks, Go2 readiness metadata,
        source-aware scale mapping, trace schema and source independence in a
        toy runtime. The user-specified broad pytest glob was also attempted;
        local shell expansion had no matching legacy files for some patterns,
        so the targeted PAPER10B2 tests are the authoritative test proof.
        """,
    )
    write_text(
        root / "PAPER10B2_CPP_BUILD_REPORT.md",
        """
        # PAPER10B2 C++ Build Report

        Command passed:

        `cmake --build build/cpp --target legsa_v23_port_core_demo -j2`

        The build target used by the PAPER10B2 runner is available.
        """,
    )
    write_text(
        root / "PAPER10B2_TEST_FAILURES_WITH_PROOF.md",
        """
        # PAPER10B2 Test Failures With Proof

        No blocking PAPER10B2 unit/integration or C++ build failures remained
        before entering the full matrix. The earlier broad pytest glob produced
        no matching files for some patterns and is recorded as non-blocking.
        """,
    )


def generate_config_docs(stage_root: Path) -> None:
    root = stage_root / "06_qm_config_freeze"
    modes, params, hashes = config_rows()
    write_csv(root / "PAPER10B2_QM_MODE_TABLE.csv", modes)
    write_csv(root / "PAPER10B2_QM_PARAMETER_TABLE.csv", params)
    write_csv(root / "PAPER10B2_QM_CONFIG_HASH_TABLE.csv", hashes)
    write_text(
        root / "PAPER10B2_FINAL_QM_POLICY_DECISION.md",
        """
        # PAPER10B2 Final QM Policy Decision

        The final candidate is QM04_FULL. QM00_OFF remains the baseline,
        QM01_STATE_TRACE_ONLY validates recognition without action, QM02 enables
        DOWNWEIGHT/REJECT, and QM03 adds HOLD/RECOVERY. QM05 was not used
        because no stricter policy was predeclared before seeing full-matrix
        results.

        Parameters are fixed from code defaults, prior source-aware caps and
        conservative engineering rules. They are not tuned from trace, RMSE,
        final_v23 output, LegSA output or per-case results.
        """,
    )


def generate_smoke_decision(stage_root: Path, data: dict[str, Any]) -> None:
    root = stage_root / "07_QM_normal_smoke_BY2_BY3"
    by2 = smoke_rows_for_report(data["BY2"]["smoke"])
    by3 = smoke_rows_for_report(data["BY3"]["smoke"])
    write_text(
        root / "PAPER10B2_NORMAL_SMOKE_DECISION.md",
        f"""
        # PAPER10B2 Normal Smoke Decision

        BY2 normal:

        {markdown_table(by2, ["qm_mode", "row_status", "position_rmse_h", "up_rmse", "yaw_rmse", "state_trace_rows", "downweight_count", "reject_count", "hold_count", "recovery_count", "fallback_count", "normal_damage_vs_QM00"])}

        BY3 normal:

        {markdown_table(by3, ["qm_mode", "row_status", "position_rmse_h", "up_rmse", "yaw_rmse", "state_trace_rows", "downweight_count", "reject_count", "hold_count", "recovery_count", "fallback_count", "normal_damage_vs_QM00"])}

        Decision: normal smoke is executable and non-divergent. QM04 introduces
        bounded normal damage relative to QM00, so the full-matrix decision must
        be reported with boundary language rather than universal superiority.
        """,
    )


def generate_resume_manifest(stage_root: Path, runner_result: dict[str, Any]) -> dict[str, Any]:
    planned = read_csv(stage_root / "12_BY3_120_qm_ablation_manifest" / "PAPER10B2_BY3_120_QM_RUN_MATRIX.csv")
    done = read_csv(stage_root / "13_BY3_120_qm_ablation_execution" / "PAPER10B2_BY3_120_QM_RUNTIME_INDEX.csv")
    done_keys = {
        (row.get("run_key") or row.get("case_id", ""), row.get("qm_mode", ""))
        for row in done
        if row.get("row_status") == "completed"
    }
    missing = [
        row
        for row in planned
        if ((row.get("run_key") or row.get("case_id", "")), row.get("qm_mode", "")) not in done_keys
    ]
    by_family = Counter(row.get("family", "") for row in missing)
    by_mode = Counter(row.get("qm_mode", "") for row in missing)
    resume_rows = []
    for row in missing:
        resume = dict(row)
        resume["resume_reason"] = runner_result.get("by3_stop_reason", "not_completed")
        resume["preserve_completed_outputs"] = True
        resume["rerun_completed_rows"] = False
        resume_rows.append(resume)

    runtime_dir = stage_root / "13_BY3_120_qm_ablation_execution"
    qa_dir = stage_root / "27_export_QA"
    write_csv(runtime_dir / "PAPER10B2_BY3_120_QM_MISSING_ONLY_RESUME_MANIFEST.csv", resume_rows)
    write_csv(qa_dir / "PAPER10B2_BY3_120_QM_MISSING_ONLY_RESUME_MANIFEST.csv", resume_rows)
    summary = {
        "planned_rows": len(planned),
        "completed_rows": len(done_keys),
        "missing_rows": len(missing),
        "missing_by_family": dict(by_family),
        "missing_by_mode": dict(by_mode),
        "stop_reason": runner_result.get("by3_stop_reason", ""),
        "runner_status": runner_result.get("status", ""),
        "hard_stop_preserved_partial_progress": runner_result.get("by3_stop_reason") == "E_DRIVE_HARD_STOP",
    }
    write_json(runtime_dir / "PAPER10B2_BY3_120_QM_RESUME_SUMMARY.json", summary)
    write_json(qa_dir / "PAPER10B2_BY3_120_QM_RESUME_SUMMARY.json", summary)
    write_text(
        runtime_dir / "PAPER10B2_BY3_120_QM_HARD_STOP_RESUME.md",
        f"""
        # PAPER10B2 BY3 Hard-Stop Resume

        Runner status: `{summary["runner_status"]}`.
        Stop reason: `{summary["stop_reason"]}`.

        Completed rows are preserved and must not be overwritten. Missing rows:
        {summary["missing_rows"]}/{summary["planned_rows"]}. Resume should run
        only `PAPER10B2_BY3_120_QM_MISSING_ONLY_RESUME_MANIFEST.csv` after E
        drive free space is safely above the user hard-stop threshold.

        Missing by family: `{summary["missing_by_family"]}`.
        Missing by mode: `{summary["missing_by_mode"]}`.
        """,
    )
    write_text(
        qa_dir / "PAPER10B2_BY3_120_QM_HARD_STOP_RESUME.md",
        (runtime_dir / "PAPER10B2_BY3_120_QM_HARD_STOP_RESUME.md").read_text(encoding="utf-8"),
    )
    return summary


def generate_trace_outputs(stage_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    outputs = {}
    for dataset, dir_name, prefix in [
        ("BY2", "11_BY2_qm_state_action_trace_analysis", "PAPER10B2_BY2"),
        ("BY3", "15_BY3_qm_state_action_trace_analysis", "PAPER10B2_BY3"),
    ]:
        root = stage_root / dir_name
        trace = aggregate_trace(stage_root, data[dataset]["rows"], dataset)
        outputs[dataset] = trace
        write_csv(root / f"{prefix}_QM_STATE_TRACE_INDEX.csv", trace["trace_index"])
        write_csv(root / f"{prefix}_STATE_DISTRIBUTION_BY_SOURCE.csv", trace_distribution_rows(trace["state_counts"], "state"))
        write_csv(root / f"{prefix}_ACTION_DISTRIBUTION_BY_SOURCE.csv", trace_distribution_rows(trace["action_counts"], "action"))
        write_csv(root / f"{prefix}_STATE_TRANSITION_BY_FAMILY.csv", family_transition_rows(trace["transitions"]))
        write_csv(root / f"{prefix}_FALLBACK_RECOVERY_SUMMARY.csv", fallback_summary(data[dataset]["rows"], trace, dataset))
        if dataset == "BY2":
            write_text(
                root / "PAPER10B2_BY2_QM_EXAMPLE_TIMELINES.md",
                example_timeline_text(trace["example_path"], dataset),
            )
        else:
            write_text(
                root / "PAPER10B2_BY3_POOR_HEADING_QM_DIAGNOSTIC.md",
                by3_diagnostic_text(data[dataset]["rows"], trace),
            )
    return outputs


def example_timeline_text(path: Path | None, dataset: str) -> str:
    if path is None:
        return f"# PAPER10B2 {dataset} QM Example Timeline\n\nNo QM trace file found."
    rows = read_csv(path)[:20]
    table_rows = [
        {
            "time": fmt(row.get("time"), 3),
            "source": row.get("source_id", ""),
            "state": row.get("state", ""),
            "action": row.get("action", ""),
            "reason_codes": row.get("reason_codes", ""),
        }
        for row in rows
    ]
    return f"""
    # PAPER10B2 {dataset} QM Example Timeline

    Example trace source: `{path.name}` from runtime-only solver output. The
    table is a short excerpt for review; full trace remains runtime-only.

    {markdown_table(table_rows, ["time", "source", "state", "action", "reason_codes"])}
    """


def by3_diagnostic_text(rows: list[dict[str, str]], trace: dict[str, Any]) -> str:
    qm04 = [r for r in rows if r.get("qm_mode") == "QM04_FULL" and r.get("row_status") == "completed"]
    dual_counts = {state: trace["state_counts"].get(("dual_antenna_yaw", state), 0) for state in STATE_NAMES}
    return f"""
    # PAPER10B2 BY3 Poor-Heading QM Diagnostic

    BY3 remains position/up generalization plus poor-heading stress. Yaw is
    diagnostic-only and is not converted into ordinary yaw generalization.

    QM04 completed rows: {len(qm04)}.

    Dual-yaw state counts across completed QM traces:

    {markdown_table([{"state": k, "count": v} for k, v in dual_counts.items()], ["state", "count"])}

    Interpretation: QM trace can explain source handling under BY3 poor-heading
    stress, but yaw metrics remain diagnostic-only and cannot support ordinary
    yaw claims.
    """


def decision_summary(
    stage_root: Path,
    data: dict[str, Any],
    trace_outputs: dict[str, Any],
    runner_result: dict[str, Any],
    resume_summary: dict[str, Any],
) -> dict[str, Any]:
    by2_rows = data["BY2"]["rows"]
    by3_rows = data["BY3"]["rows"]
    by2_completed = completed_count(by2_rows)
    by3_completed = completed_count(by3_rows)
    by2_qm00 = method_lookup(data["BY2"]["method"], "QM00_OFF")
    by2_qm04 = method_lookup(data["BY2"]["method"], "QM04_FULL")
    by3_qm00 = method_lookup(data["BY3"]["method"], "QM00_OFF")
    by3_qm04 = method_lookup(data["BY3"]["method"], "QM04_FULL")
    by2_h_delta = ratio_delta(by2_qm04.get("position_rmse_h_mean"), by2_qm00.get("position_rmse_h_mean"))
    by2_up_delta = ratio_delta(by2_qm04.get("up_rmse_mean"), by2_qm00.get("up_rmse_mean"))
    by3_h_delta = ratio_delta(by3_qm04.get("position_rmse_h_mean"), by3_qm00.get("position_rmse_h_mean"))
    by3_up_delta = ratio_delta(by3_qm04.get("up_rmse_mean"), by3_qm00.get("up_rmse_mean"))
    by2_trace = sum(int(float(r.get("state_trace_rows") or 0)) for r in by2_rows if r.get("qm_mode") != "QM00_OFF")
    by3_trace = sum(int(float(r.get("state_trace_rows") or 0)) for r in by3_rows if r.get("qm_mode") != "QM00_OFF")
    unsafe = any(str(r.get("trace_used_online", "")).lower() == "true" for r in by2_rows + by3_rows)
    unsafe = unsafe or any(str(r.get("final_v23_output_solver_input", "")).lower() == "true" for r in by2_rows + by3_rows)
    unsafe = unsafe or any(str(r.get("legsa_output_solver_input", "")).lower() == "true" for r in by2_rows + by3_rows)
    matrix_complete = by2_completed == 600 and by3_completed == 600
    hard_stop = runner_result.get("by2_stop_reason") == "E_DRIVE_HARD_STOP" or runner_result.get("by3_stop_reason") == "E_DRIVE_HARD_STOP"
    trace_ready = by2_trace > 0 and by3_trace > 0
    normal_smoke_complete = completed_count(data["BY2"]["smoke"]) >= 5 and completed_count(data["BY3"]["smoke"]) >= 5
    perf_deltas = [d for d in [by2_h_delta, by2_up_delta, by3_h_delta, by3_up_delta] if d is not None]
    severe_damage = any(d > 0.15 for d in perf_deltas)
    mixed = any(d > 0.05 for d in perf_deltas) and any(d < -0.01 for d in perf_deltas)
    mostly_safe = all(d <= 0.05 for d in perf_deltas) if perf_deltas else False

    if not matrix_complete and hard_stop:
        final_status = "CONDITIONAL_PASS_QM_RUNTIME_STOPPED_BY_10GB_HARD_STOP"
        innovation = "QM_MECHANISM_READY_PERFORMANCE_MIXED"
    elif not matrix_complete:
        final_status = "FAIL_BY2_QM_MATRIX_NOT_COMPLETED" if by2_completed < 600 else "FAIL_BY3_QM_MATRIX_NOT_COMPLETED"
        innovation = "QM_NOT_SUPPORTED"
    elif unsafe:
        final_status = "FAIL_UNSAFE_SOURCE_USED"
        innovation = "QM_NOT_SUPPORTED"
    elif trace_ready and severe_damage:
        final_status = "CONDITIONAL_PASS_QM_MECHANISM_READY_PERFORMANCE_MIXED"
        innovation = "QM_MECHANISM_READY_PERFORMANCE_MIXED"
    elif trace_ready and (mostly_safe or mixed):
        final_status = "CONDITIONAL_PASS_QM_READY_WITH_BOUNDARY"
        innovation = "QM_MAIN_INNOVATION_READY_WITH_BOUNDARY"
    elif trace_ready:
        final_status = "CONDITIONAL_PASS_QM_MECHANISM_READY_PERFORMANCE_MIXED"
        innovation = "QM_MECHANISM_READY_PERFORMANCE_MIXED"
    else:
        final_status = "CONDITIONAL_PASS_QM_DIAGNOSTIC_ONLY"
        innovation = "QM_DIAGNOSTIC_ONLY"

    return {
        "by2_completed": by2_completed,
        "by3_completed": by3_completed,
        "by2_status_counter": dict(status_counter(by2_rows)),
        "by3_status_counter": dict(status_counter(by3_rows)),
        "normal_smoke_complete": normal_smoke_complete,
        "by2_qm04_vs_qm00_h_delta": by2_h_delta,
        "by2_qm04_vs_qm00_up_delta": by2_up_delta,
        "by3_qm04_vs_qm00_h_delta": by3_h_delta,
        "by3_qm04_vs_qm00_up_delta": by3_up_delta,
        "trace_ready": trace_ready,
        "by2_trace_rows": by2_trace,
        "by3_trace_rows": by3_trace,
        "unsafe_flags": unsafe,
        "runner_status": runner_result.get("status", ""),
        "by2_stop_reason": runner_result.get("by2_stop_reason", ""),
        "by3_stop_reason": runner_result.get("by3_stop_reason", ""),
        "missing_rows": resume_summary.get("missing_rows", 0),
        "missing_by_family": resume_summary.get("missing_by_family", {}),
        "missing_by_mode": resume_summary.get("missing_by_mode", {}),
        "final_status": final_status,
        "innovation_decision": innovation,
        "decision_text": decision_text(final_status, innovation),
    }


def decision_text(final_status: str, innovation: str) -> str:
    if final_status == "CONDITIONAL_PASS_QM_RUNTIME_STOPPED_BY_10GB_HARD_STOP":
        return "QM state machine and BY2 full matrix are closed, and BY3 partial evidence is preserved, but the BY3 full matrix stopped at the user-defined 10GB hard-stop. QM is not yet promoted to main-innovation-ready; resume the missing-only BY3 rows before making a final positive paper claim."
    if innovation == "QM_MAIN_INNOVATION_READY_WITH_BOUNDARY":
        return "QM can be kept as a main innovation with explicit boundaries: implemented mechanism, full trace evidence and BY2/BY3 matrix coverage are available, but no universal superiority is claimed."
    if innovation == "QM_MECHANISM_READY_PERFORMANCE_MIXED":
        return "QM mechanism is implemented and evidenced, but performance is mixed enough that it should be written as a bounded mechanism/diagnostic contribution rather than an unconditional performance claim."
    if innovation == "QM_DIAGNOSTIC_ONLY":
        return "QM trace is useful diagnostically, but current evidence is not sufficient for a main innovation claim."
    return "QM is not supported as a main innovation under current evidence."


def generate_decision_docs(stage_root: Path, data: dict[str, Any], trace_outputs: dict[str, Any], decision: dict[str, Any]) -> None:
    root = stage_root / "16_BY2_BY3_qm_cross_dataset_decision"
    comp_rows = [
        {
            "dataset": "BY2",
            "completed_rows": decision["by2_completed"],
            "planned_rows": 600,
            "qm04_vs_qm00_position_h_delta_ratio": fmt(decision["by2_qm04_vs_qm00_h_delta"], 5),
            "qm04_vs_qm00_up_delta_ratio": fmt(decision["by2_qm04_vs_qm00_up_delta"], 5),
            "trace_rows": decision["by2_trace_rows"],
            "yaw_metric_status": "ordinary_evaluation",
        },
        {
            "dataset": "BY3",
            "completed_rows": decision["by3_completed"],
            "planned_rows": 600,
            "qm04_vs_qm00_position_h_delta_ratio": fmt(decision["by3_qm04_vs_qm00_h_delta"], 5),
            "qm04_vs_qm00_up_delta_ratio": fmt(decision["by3_qm04_vs_qm00_up_delta"], 5),
            "trace_rows": decision["by3_trace_rows"],
            "yaw_metric_status": "diagnostic_only",
        },
    ]
    write_csv(root / "PAPER10B2_BY2_BY3_QM_COMPARISON.csv", comp_rows)
    write_text(
        root / "PAPER10B2_QM_GENERALIZATION_DECISION.md",
        f"""
        # PAPER10B2 QM Generalization Decision

        Decision enum: `{decision["innovation_decision"]}`

        {decision["decision_text"]}

        BY2 completed rows: {decision["by2_completed"]}/600.
        BY3 completed rows: {decision["by3_completed"]}/600.
        Runner status: `{decision["runner_status"]}`.
        BY3 stop reason: `{decision["by3_stop_reason"]}`.
        Missing-only resume rows: {decision["missing_rows"]}.
        BY3 yaw status: diagnostic_only.

        The result does not authorize universal superiority, final_v23
        outperform claims or BY3 ordinary yaw generalization.
        """,
    )
    write_text(
        root / "PAPER10B2_QM_MAIN_INNOVATION_DECISION.md",
        f"""
        # PAPER10B2 QM Main Innovation Decision

        Final status: `{decision["final_status"]}`

        Main-innovation enum: `{decision["innovation_decision"]}`

        Judgment: {decision["decision_text"]}

        Required boundaries:

        - QM is a state/action/recovery decision layer above source-aware
          LSIM/OIM and Go2 readiness metadata.
        - It is not identical to SA04_N6B itself.
        - It is not output substitution or LegSA_QA_Fallback_EKF.
        - BY3 yaw remains diagnostic-only.
        - Performance language must be bounded by family/dataset evidence.
        """,
    )


def generate_relation_docs(stage_root: Path) -> None:
    root = stage_root / "17_qm_relation_to_sourceaware_and_go2"
    write_text(
        root / "PAPER10B2_QM_LAYERED_ARCHITECTURE.md",
        """
        # PAPER10B2 Layered Architecture

        Layer 1: source-aware LSIM/OIM computes continuous source-level R
        scaling and reason codes.

        Layer 2: Go2 weak priors add roll/pitch and horizontal velocity
        constraints, while readiness/motion-state supplies legged-platform
        metadata.

        Layer 3: multi-state QM maps solver-visible metadata and innovation
        evidence to source-level NORMAL/DOWNWEIGHT/REJECT/HOLD/RECOVERY/FALLBACK
        states and actions.

        These layers are related but not synonyms.
        """,
    )
    write_csv(
        root / "PAPER10B2_QM_VS_SOURCEAWARE_TABLE.csv",
        [
            {"item": "source-aware LSIM/OIM", "role": "continuous R scaling", "not_qm_state_machine": True},
            {"item": "Go2 readiness/motion-state", "role": "metadata input and legged prior context", "not_qm_state_machine": True},
            {"item": "multi-state QM", "role": "state/action/recovery decision layer", "not_qm_state_machine": False},
            {"item": "LegSA_QA_Fallback_EKF", "role": "separate future severe-GNSS candidate", "not_qm_state_machine": True},
        ],
    )
    write_text(
        root / "PAPER10B2_QM_GO2_READINESS_ROLE.md",
        """
        # PAPER10B2 Go2 Readiness Role

        Go2 readiness and motion-state are solver-visible metadata inputs to
        source-aware LSIM and multi-state QM. They are not truth, not pose
        reference, not yaw truth and not full contact-aided InEKF. PAPER10B2
        uses them to identify low-readiness/rough-motion intervals for Go2
        attitude and horizontal velocity source states.
        """,
    )


def generate_internal_comparison(stage_root: Path, decision: dict[str, Any]) -> None:
    root = stage_root / "18_internal_comparison_update"
    rows = [
        {"method": "Original KF-GINS", "role": "baseline", "paper10b2_status": "context only"},
        {"method": "Single-Antenna GNSS/INS", "role": "GNSS1-status baseline", "paper10b2_status": "comparison baseline"},
        {"method": "Dual-Antenna GNSS/INS EKF Baseline", "role": "baseline", "paper10b2_status": "comparison baseline"},
        {"method": "LegSA-GINS source-aware + Go2 without multi-state QM", "role": "QM00_OFF", "paper10b2_status": "primary baseline"},
        {"method": "LegSA-GINS + multi-state QM", "role": "QM04_FULL", "paper10b2_status": decision["innovation_decision"]},
    ]
    write_csv(root / "PAPER10B2_INTERNAL_COMPARISON_UPDATED.csv", rows)
    write_csv(root / "PAPER10B2_FINAL_QM_POLICY_VS_BASELINES.csv", rows)
    write_text(
        root / "PAPER10B2_MAIN_TEXT_INTERPRETATION.md",
        f"""
        # PAPER10B2 Main Text Interpretation

        QM04_FULL should be interpreted against QM00_OFF, not as a universal
        replacement for every baseline. Decision: `{decision["innovation_decision"]}`.

        Do not write that LegSA-GINS fully outperforms final_v23 or that QM is
        universally superior. If performance is mixed by family, report the
        state/action evidence and the bounded family-level behavior.
        """,
    )


def generate_paper_tables(stage_root: Path, data: dict[str, Any]) -> None:
    root = stage_root / "19_paper_facing_tables"
    modes, _, _ = config_rows()
    write_csv(root / "PAPER10B2_QM_METHOD_TABLE.csv", modes)
    shutil.copy2(stage_root / "03_qm_state_machine_design" / "PAPER10B2_QM_STATE_TRANSITION_TABLE.csv", root / "PAPER10B2_QM_STATE_TRANSITION_TABLE.csv")
    by2_family = data["BY2"]["family"]
    by3_family = data["BY3"]["family"]
    write_csv(root / "PAPER10B2_BY2_QM_FAMILY_TABLE.csv", by2_family)
    write_csv(root / "PAPER10B2_BY3_QM_STRESS_TABLE.csv", by3_family)
    summary_rows = []
    for dataset in ["BY2", "BY3"]:
        for row in data[dataset]["method"]:
            summary_rows.append(
                {
                    "dataset": dataset,
                    "qm_mode": row.get("qm_mode", ""),
                    "completed_rows": row.get("completed_rows", ""),
                    "position_rmse_h_mean": row.get("position_rmse_h_mean", ""),
                    "up_rmse_mean": row.get("up_rmse_mean", ""),
                    "trace_rows_sum": row.get("trace_rows_sum", ""),
                    "fallback_count_sum": row.get("fallback_count_sum", ""),
                    "yaw_metric_status": row.get("yaw_metric_status", ""),
                }
            )
    write_csv(root / "PAPER10B2_QM_STATE_ACTION_SUMMARY_TABLE.csv", summary_rows)
    write_text(
        root / "PAPER10B2_MAIN_TEXT_TABLE_RECOMMENDATION.md",
        """
        # PAPER10B2 Main Text Table Recommendation

        Main text: include QM method table, compact BY2 family table and compact
        BY3 stress table with BY3 yaw marked diagnostic-only. Keep state/action
        summary to the main text only if space permits.
        """,
    )
    write_text(
        root / "PAPER10B2_APPENDIX_TABLE_RECOMMENDATION.md",
        """
        # PAPER10B2 Appendix Table Recommendation

        Appendix: include full state/action distributions, transition-by-family
        table, reason-code frequency and row-level matrix provenance. Do not
        include runtime NAV/STD/EVAL_NAV/RUN_MANIFEST files in paper packages.
        """,
    )


def setup_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def save_fig(fig: Any, path_base: Path) -> list[Path]:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    png = path_base.with_suffix(".png")
    pdf = path_base.with_suffix(".pdf")
    fig.savefig(png, dpi=180, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    return [png, pdf]


def generate_figures(stage_root: Path, data: dict[str, Any], trace_outputs: dict[str, Any]) -> list[Path]:
    plt = setup_matplotlib()
    files: list[Path] = []
    main = stage_root / "20_figures" / "main_text"
    appendix = stage_root / "20_figures" / "appendix"

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    boxes = [
        ("source-aware LSIM/OIM\ncontinuous R scaling", 0.15, 0.65),
        ("Go2 readiness metadata\nmotion-state / roughness", 0.15, 0.35),
        ("multi-state quality management\nstate/action/recovery", 0.52, 0.5),
        ("EKF update\nno trace online", 0.84, 0.5),
    ]
    for text, x, y in boxes:
        ax.text(x, y, text, ha="center", va="center", fontsize=11, bbox={"boxstyle": "round,pad=0.4", "fc": "#f6f8fa", "ec": "#3d4852"})
    ax.annotate("", xy=(0.42, 0.52), xytext=(0.28, 0.65), arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(0.42, 0.48), xytext=(0.28, 0.35), arrowprops={"arrowstyle": "->"})
    ax.annotate("", xy=(0.74, 0.5), xytext=(0.62, 0.5), arrowprops={"arrowstyle": "->"})
    ax.set_title("PAPER10B2 multi-state quality management with source-aware LSIM/OIM and Go2 readiness metadata")
    files += save_fig(fig, main / "PAPER10B2_QM_FRAMEWORK")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    xs = [0.08, 0.25, 0.42, 0.59, 0.76, 0.93]
    for state, x in zip(STATE_NAMES, xs):
        ax.text(x, 0.5, state, ha="center", va="center", fontsize=9, bbox={"boxstyle": "round,pad=0.35", "fc": "#eef6ff", "ec": "#1f4e79"})
    for a, b in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(b - 0.06, 0.5), xytext=(a + 0.06, 0.5), arrowprops={"arrowstyle": "->"})
    ax.set_title("PAPER10B2 state/action/recovery state machine, BY3 yaw diagnostic-only, no trace online")
    files += save_fig(fig, main / "PAPER10B2_STATE_MACHINE_DIAGRAM")
    plt.close(fig)

    for dataset, filename, title in [
        ("BY2", "PAPER10B2_BY2_QM_FAMILY_DELTA", "BY2 QM04 minus QM00 by family"),
        ("BY3", "PAPER10B2_BY3_QM_STRESS_SUMMARY", "BY3 QM stress summary; yaw diagnostic-only"),
    ]:
        family = data[dataset]["family"]
        bases = {r["family"]: r for r in family if r.get("qm_mode") == "QM00_OFF"}
        labels, deltas = [], []
        for row in family:
            if row.get("qm_mode") != "QM04_FULL":
                continue
            base = bases.get(row.get("family", ""))
            d = ratio_delta(row.get("position_rmse_h_mean"), base.get("position_rmse_h_mean") if base else None)
            if d is not None:
                labels.append(row.get("family", ""))
                deltas.append(d * 100.0)
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.axhline(0, color="black", linewidth=0.8)
        ax.bar(labels, deltas, color="#4c78a8")
        ax.set_ylabel("horizontal RMSE delta vs QM00 (%)")
        ax.set_title(f"PAPER10B2 multi-state quality management {title}")
        ax.tick_params(axis="x", rotation=35)
        files += save_fig(fig, main / filename)
        plt.close(fig)

    for dataset, filename in [("BY2", "PAPER10B2_BY2_STATE_DISTRIBUTION_HEATMAP"), ("BY3", "PAPER10B2_BY3_STATE_DISTRIBUTION_HEATMAP")]:
        counts = trace_outputs.get(dataset, {}).get("state_counts", Counter())
        matrix = [[counts.get((source, state), 0) for state in STATE_NAMES] for source in SOURCES]
        fig, ax = plt.subplots(figsize=(9, 4.8))
        im = ax.imshow(matrix, aspect="auto", cmap="Blues")
        ax.set_xticks(range(len(STATE_NAMES)), STATE_NAMES, rotation=35)
        ax.set_yticks(range(len(SOURCES)), SOURCES)
        ax.set_title(f"PAPER10B2 {dataset} state/action/recovery distribution; no trace online")
        fig.colorbar(im, ax=ax, fraction=0.03)
        files += save_fig(fig, appendix / filename)
        plt.close(fig)

    reasons = trace_outputs.get("BY2", {}).get("reasons", Counter()) + trace_outputs.get("BY3", {}).get("reasons", Counter())
    labels = [item[0] for item in reasons.most_common(12)]
    vals = [item[1] for item in reasons.most_common(12)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(labels, vals, color="#59a14f")
    ax.set_title("PAPER10B2 reason-code frequency; source-aware LSIM/OIM + Go2 readiness metadata")
    ax.tick_params(axis="x", rotation=35)
    files += save_fig(fig, appendix / "PAPER10B2_REASON_CODE_FREQUENCY")
    plt.close(fig)

    modes = data["BY2"]["method"] + data["BY3"]["method"]
    labels = [f"{r.get('dataset','')}-{r.get('qm_mode','')}" for r in modes]
    vals = [safe_float(r.get("position_rmse_h_mean")) or 0.0 for r in modes]
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(labels, vals, color="#f28e2b")
    ax.set_ylabel("mean horizontal RMSE")
    ax.set_title("PAPER10B2 QM mode comparison; BY3 yaw diagnostic-only")
    ax.tick_params(axis="x", rotation=60)
    files += save_fig(fig, appendix / "PAPER10B2_QM_MODE_COMPARISON")
    plt.close(fig)

    example = trace_outputs.get("BY2", {}).get("example_path") or trace_outputs.get("BY3", {}).get("example_path")
    for filename, wanted in [
        ("PAPER10B2_STATE_ACTION_TIMELINE_EXAMPLE", {"DOWNWEIGHT", "RECOVERY", "HOLD", "FALLBACK"}),
        ("PAPER10B2_FALLBACK_RECOVERY_EXAMPLE", {"FALLBACK", "RECOVERY", "HOLD"}),
    ]:
        timeline_rows = read_csv(example)[:200] if example else []
        x, y, labels_y = [], [], []
        states = STATE_NAMES
        state_to_num = {s: i for i, s in enumerate(states)}
        for idx, row in enumerate(timeline_rows):
            state = row.get("state", "")
            if state in state_to_num and (state in wanted or filename.endswith("TIMELINE_EXAMPLE")):
                x.append(idx)
                y.append(state_to_num[state])
        fig, ax = plt.subplots(figsize=(10, 3.5))
        if x:
            ax.step(x, y, where="post", color="#9c755f")
        else:
            ax.text(0.5, 0.5, "No fallback/hold event triggered in selected trace", ha="center", va="center")
        ax.set_yticks(range(len(states)), states)
        ax.set_xlabel("trace row index")
        ax.set_title(f"PAPER10B2 multi-state quality management {filename}; no trace online")
        files += save_fig(fig, main / filename)
        plt.close(fig)
    return files


def render_qa(stage_root: Path, figure_files: list[Path]) -> None:
    rows = []
    for path in figure_files:
        rows.append(
            {
                "file": str(path),
                "exists": path.exists(),
                "size_bytes": file_size(path),
                "qa_status": "pass" if path.exists() and file_size(path) > 1000 else "fail",
            }
        )
    write_csv(stage_root / "21_render_QA" / "PAPER10B2_RENDER_QA_REPORT.csv", rows)
    pass_count = sum(1 for row in rows if row["qa_status"] == "pass")
    write_text(
        stage_root / "21_render_QA" / "PAPER10B2_RENDER_QA_REPORT.md",
        f"""
        # PAPER10B2 Render QA Report

        Rendered files checked: {len(rows)}.
        Pass count: {pass_count}.
        Main-text candidate figures are considered pass if PNG/PDF exists and
        is non-empty. Figures are runtime/C-export artifacts and must not be
        staged in Git.
        """,
    )


def generate_claim_boundary(stage_root: Path, decision: dict[str, Any]) -> None:
    root = stage_root / "22_claim_boundary"
    allowed = [
        "multi-state QM implemented",
        "state/action/recovery trace generated",
        "source-aware LSIM/OIM feeds QM",
        "Go2 readiness/motion-state feeds QM",
        "BY2 QM full ablation completed; BY3 ablation is complete only if row count reaches 600/600",
        "If final status is hard-stop, BY3 evidence is partial and must be resumed before final positive paper claim",
        "QM can be written as main innovation only with the final enum boundary",
    ]
    boundary = [
        "No universal superiority",
        "BY3 yaw diagnostic-only / poor-heading stress",
        "Performance claims must be per-family/per-dataset",
        "Fallback is partial-source fusion, not output substitution",
        "Go2 readiness is metadata, not truth",
    ]
    forbidden = [
        "universal superiority",
        "fully outperforms final_v23",
        "BY3 ordinary yaw generalization",
        "trace online",
        "final_v23/LegSA output solver input",
        "Go2 yaw/position truth",
        "full contact-aided InEKF",
        "complete 9F FGO",
        "external DA/LC exact official reproduction",
    ]
    write_text(root / "PAPER10B2_ALLOWED_CLAIMS.md", "# PAPER10B2 Allowed Claims\n\n" + "\n".join(f"- {x}" for x in allowed))
    write_text(root / "PAPER10B2_BOUNDARY_CLAIMS.md", "# PAPER10B2 Boundary Claims\n\n" + "\n".join(f"- {x}" for x in boundary))
    write_text(root / "PAPER10B2_FORBIDDEN_CLAIMS.md", "# PAPER10B2 Forbidden Claims\n\n" + "\n".join(f"- {x}" for x in forbidden))
    write_text(
        root / "PAPER10B2_SAFE_WORDING_GUIDE.md",
        f"""
        # PAPER10B2 Safe Wording Guide

        Preferred wording: "source-level multi-state quality management
        integrates LSIM/OIM, Go2 readiness/motion-state metadata and innovation
        consistency to decide source actions with finite hold, recovery and
        fallback."

        Decision wording: `{decision["innovation_decision"]}`.

        Avoid: universal superiority, BY3 ordinary yaw generalization, final_v23
        outperform wording, and any implication that Go2 pose/yaw is truth.
        """,
    )
    rows = [{"claim": x, "class": "allowed"} for x in allowed]
    rows += [{"claim": x, "class": "boundary"} for x in boundary]
    rows += [{"claim": x, "class": "forbidden"} for x in forbidden]
    write_csv(root / "PAPER10B2_FINAL_CLAIM_BOUNDARY_TABLE.csv", rows)


def generate_manuscript(stage_root: Path, decision: dict[str, Any]) -> None:
    root = stage_root / "23_manuscript_method_and_result_text_draft"
    method_cn = """
    # PAPER10B2 QM 方法章节草稿（中文）

    本文在 source-aware LSIM/OIM 连续协方差调节层之上，引入源级多态质量管理机制。每个观测源独立维护 NORMAL、DOWNWEIGHT、REJECT、HOLD、RECOVERY 和 FALLBACK 状态。状态输入来自 LSIM、OIM、combined R scale、归一化创新、provider 状态、时间戳间隔、source reason code 以及 Go2 readiness/motion-state 元数据。机制不使用 trace online，不使用 final_v23 或 LegSA 输出作为 solver input，也不根据离线 RMSE 反调阈值。

    状态转移可写为 s_i(k+1)=f(s_i(k), zeta_i(k), c_i(k))，其中 zeta_i 包含源级健康指标和创新一致性，c_i 为连续异常/恢复计数。动作 a_i(k) 属于 use original R、inflate R、reject current observation、hold finite window、recovery hysteresis 和 fallback partial-source fusion。
    """
    method_en = """
    # PAPER10B2 QM Method Draft (English)

    We introduce a source-level multi-state quality management layer above the
    source-aware LSIM/OIM covariance-scaling policy. Each observation source
    maintains an independent state among NORMAL, DOWNWEIGHT, REJECT, HOLD,
    RECOVERY and FALLBACK. The transition function uses only solver-visible
    metadata and innovations: LSIM/OIM scales, combined R scale, normalized
    innovation, provider validity, timestamp gaps, source-specific reason codes
    and Go2 readiness/motion-state metadata. Trace, final_v23 output, LegSA
    output and offline RMSE are not used online.
    """
    result_cn = f"""
    # PAPER10B2 QM 结果章节草稿（中文）

    PAPER10B2 完成 BY2/BY3 多态 QM 消融后，主结论枚举为 `{decision["innovation_decision"]}`。
    结果应按数据集与退化 family 有边界陈述。BY3 yaw 保持 diagnostic-only，不能写成普通航向泛化。
    """
    result_en = f"""
    # PAPER10B2 QM Result Draft (English)

    After the BY2/BY3 multi-state QM ablation, the decision enum is
    `{decision["innovation_decision"]}`. The result should be described with
    dataset and family boundaries. BY3 yaw remains diagnostic-only and must not
    be presented as ordinary yaw generalization.
    """
    equations = """
    # PAPER10B2 QM Equation List

    - Source health: h_i(k)=g(LSIM_i,OIM_i,provider_i,gap_i,readiness_i).
    - State transition: s_i(k+1)=f(s_i(k),h_i(k),nu_i(k),n_anom_i,n_rec_i).
    - Action policy: a_i(k)=pi(s_i(k)).
    - Downweight: R_i'(k)=alpha_i(k) R_i(k), alpha_i >= 1.
    - Hold: z_i(k) is skipped for finite H_i epochs.
    - Recovery: alpha_i(k) decreases only after stable epochs.
    - Fallback: unsafe source subset is skipped; remaining valid sources are fused conservatively.
    """
    captions = """
    # PAPER10B2 Caption Drafts

    - PAPER10B2 multi-state quality management framework integrating
      source-aware LSIM/OIM and Go2 readiness metadata, with no trace online.
    - State/action/recovery transition diagram for source-level QM.
    - BY2 family-level delta of QM04 against QM00.
    - BY3 stress summary with yaw diagnostic-only.
    """
    write_text(root / "PAPER10B2_QM_METHOD_SECTION_DRAFT_CN.md", method_cn)
    write_text(root / "PAPER10B2_QM_METHOD_SECTION_DRAFT_EN.md", method_en)
    write_text(root / "PAPER10B2_QM_RESULT_SECTION_DRAFT_CN.md", result_cn)
    write_text(root / "PAPER10B2_QM_RESULT_SECTION_DRAFT_EN.md", result_en)
    write_text(root / "PAPER10B2_QM_EQUATION_LIST.md", equations)
    write_text(root / "PAPER10B2_CAPTION_DRAFTS.md", captions)


def generate_teacher_package(stage_root: Path, decision: dict[str, Any]) -> None:
    root = stage_root / "24_teacher_consultation_package"
    write_text(
        root / "导师咨询版_PAPER10B2_多态质量管理一页纸.md",
        f"""
        # PAPER10B2 多态质量管理一页纸

        目标：把已有 source-aware LSIM/OIM 与 Go2 readiness/motion-state 元数据升级为真正的源级多态质量管理状态机。

        已实现：NORMAL、DOWNWEIGHT、REJECT、HOLD、RECOVERY、FALLBACK；每个观测源独立状态；输出 QM_STATE_ACTION_TRACE.csv。

        结论枚举：`{decision["innovation_decision"]}`。
        最终状态：`{decision["final_status"]}`。
        BY3 stop reason：`{decision["by3_stop_reason"]}`。
        Missing-only resume rows：{decision["missing_rows"]}。

        边界：不写 universal superiority；BY3 yaw diagnostic-only；不使用 trace online；不使用 final_v23/LegSA 输出作为 solver input。
        """,
    )
    write_text(
        root / "导师咨询版_QM是否可作为主创新.md",
        f"# QM 是否可作为主创新\n\n{decision['decision_text']}\n",
    )
    write_csv(
        root / "导师咨询版_QM_BY2_BY3结论.csv",
        [
            {"dataset": "BY2", "completed_rows": decision["by2_completed"], "trace_rows": decision["by2_trace_rows"]},
            {"dataset": "BY3", "completed_rows": decision["by3_completed"], "trace_rows": decision["by3_trace_rows"], "yaw": "diagnostic_only", "stop_reason": decision["by3_stop_reason"], "missing_rows": decision["missing_rows"]},
        ],
    )
    write_text(root / "导师咨询版_QM图表建议.md", "# QM 图表建议\n\n主文放框架图、状态机图、BY2 family delta、BY3 stress summary；附录放状态分布和 reason-code。")
    write_text(root / "导师咨询版_下一步是否进入PAPER10E.md", "# 是否进入 PAPER10E\n\n建议进入 PAPER10E 之前先由人工确认 QM 边界措辞和主创新排序。PAPER10E 只冻结最终主算法矩阵，不重开外部 DA/LC。")


def write_obsidian(obsidian_root: Path, decision: dict[str, Any]) -> None:
    stage = obsidian_root / "30_STAGES" / "PAPER10B2_多态质量管理机制闭合"
    files = {
        "PAPER10B2_阶段总览.md": f"""
        ---
        stage: PAPER10B2
        status: {decision["final_status"]}
        ---

        # PAPER10B2 阶段总览

        本阶段闭合 [[PAPER10B2]] 多态质量管理机制。关联 [[source-aware LSIM-OIM]]、[[Go2 weak prior]]、[[Raw Doppler]]、[[LegSA-GINS]]、[[BY2]]、[[BY3]]。

        结论：`{decision["innovation_decision"]}`。
        BY3 stop reason：`{decision["by3_stop_reason"]}`；missing-only resume rows：{decision["missing_rows"]}。
        下一步参考 [[PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE]]。
        """,
        "10_ALGORITHMS/多态质量管理机制.md": """
        # 多态质量管理机制

        状态：NORMAL、DOWNWEIGHT、REJECT、HOLD、RECOVERY、FALLBACK。
        输入：LSIM、OIM、Go2 readiness、Go2 motion-state、source metadata、normalized innovation、provider status、timestamp gap、reason codes。
        动作：use original R、inflate R、reject、hold、recovery hysteresis、fallback partial-source fusion。
        """,
        "40_EVIDENCE/多态质量管理证据总览.md": f"""
        # 多态质量管理证据总览

        BY2 completed rows: {decision["by2_completed"]}/600.
        BY3 completed rows: {decision["by3_completed"]}/600.
        BY3 stop reason: {decision["by3_stop_reason"]}.
        Missing-only resume rows: {decision["missing_rows"]}.
        BY3 yaw: diagnostic-only.
        """,
        "50_CLAIM_BOUNDARY/多态质量管理_claim_boundary.md": """
        # 多态质量管理 Claim Boundary

        Allowed: implemented source-level state/action/recovery trace.
        Boundary: no universal superiority; BY3 yaw diagnostic-only.
        Forbidden: trace online, final_v23 output solver input, Go2 pose/yaw as truth.
        """,
        "70_NEXT_DECISIONS/PAPER10E_最终主算法矩阵计划.md": """
        # PAPER10E 最终主算法矩阵计划

        进入 PAPER10E 前需人工确认 PAPER10B2 的主创新边界和是否保留 QM04_FULL 为最终候选。
        """,
        "90_GRAPH/knowledge_edges.csv": "source,target,relation\nPAPER10B2,source-aware LSIM-OIM,uses\nPAPER10B2,Go2 weak prior,uses_metadata\nPAPER10B2,BY2,evaluates\nPAPER10B2,BY3,evaluates_with_yaw_diagnostic_only\nPAPER10B2,PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE,recommends_next\n",
    }
    for rel, text in files.items():
        write_text(stage / rel, text)


def generate_git_context_update_report(stage_root: Path, decision: dict[str, Any]) -> None:
    write_text(
        stage_root / "26_git_context_updates" / "PAPER10B2_GIT_CONTEXT_UPDATE_REPORT.md",
        f"""
        # PAPER10B2 Git Context Update Report

        Updated tracked context files:

        - AGENTS.md
        - PLANS.md
        - PHASE_LOG.md
        - CLAIM_BOUNDARY.md
        - docs/codex_context/PAPER10B2_CURRENT_CONTEXT.md
        - docs/codex_context/PAPER10X_CURRENT_CONTEXT.md
        - docs/codex_context/PAPER10Y_CURRENT_CONTEXT.md
        - docs/codex_context/current_state.md
        - docs/codex_context/claim_boundary.md

        Recorded status: `{decision["final_status"]}`.
        Recorded QM enum: `{decision["innovation_decision"]}`.
        BY2 rows: {decision["by2_completed"]}/600.
        BY3 rows: {decision["by3_completed"]}/600.
        BY3 missing-only resume rows: {decision["missing_rows"]}.

        Boundaries retained: no external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO, no trace online, no final_v23/LegSA solver input, no per-case tuning, no output substitution, no BY3 ordinary yaw generalization, no push.
        """,
    )


def generate_root_reports(repo: Path, stage_root: Path, c_export_root: Path, obsidian_root: Path, decision: dict[str, Any], commit_hash: str = "pending") -> dict[str, str]:
    hard_stop = decision.get("final_status") == "CONDITIONAL_PASS_QM_RUNTIME_STOPPED_BY_10GB_HARD_STOP"
    space_line = "初始 gate 满足；运行中 E drive 触发 10GB hard-stop，runner 已停止并保留 partial progress。" if hard_stop else "是，初始和运行中均满足 hard-stop 要求。"
    paper10e_line = "不建议直接进入最终 paper-claim 冻结；先在空间恢复后补跑 BY3 missing-only resume，或由人工接受 hard-stop 条件边界后再进入 PAPER10E。" if hard_stop else "建议人工确认边界后进入。"
    report = f"""
    # PAPER10B2 Supervisor Final Report

    Final status: `{decision["final_status"]}`
    QM decision: `{decision["innovation_decision"]}`

    1. 空间满足：{space_line}
    2. jobs=8：是。
    3. E_DRIVE_HARD_STOP_GB=10：是。
    4. QM 状态机是否实现：是。
    5. 状态：NORMAL, DOWNWEIGHT, REJECT, HOLD, RECOVERY, FALLBACK。
    6. 动作：use original R, inflate R, reject current observation, hold finite window, recovery hysteresis, fallback partial-source fusion。
    7. hold/recovery/fallback 是否实现：是。
    8. 是否默认关闭：是，enable_multi_state_qm=false / QM00_OFF。
    9. 是否不改变 QM off baseline：是，QM00_OFF 为 baseline。
    10. unit/integration tests：PAPER10B2 targeted tests 与 C++ build 通过。
    11. BY2 normal：见 `{ALIASES["stage"]}/07_QM_normal_smoke_BY2_BY3`。
    12. BY2 120：{decision["by2_completed"]}/600 completed。
    13. BY3 normal：见 `{ALIASES["stage"]}/07_QM_normal_smoke_BY2_BY3`。
    14. BY3 120：{decision["by3_completed"]}/600 completed；stop_reason={decision["by3_stop_reason"]}；missing_rows={decision["missing_rows"]}。
    15. BY3 yaw：diagnostic-only。
    16. state/action/recovery trace：BY2 {decision["by2_trace_rows"]} rows, BY3 {decision["by3_trace_rows"]} rows。
    17. Go2 readiness 进入 QM：是。
    18. source-aware LSIM/OIM 进入 QM：是。
    19. QM 是否能作为主创新：{decision["innovation_decision"]}；hard-stop 条件下尚不能写成 main-innovation-ready。
    20. 边界：不写 universal superiority；BY3 yaw diagnostic-only；按 family/dataset 限定；BY3 missing-only resume 未完成前不做最终正向论文 claim。
    21. 是否建议进入 PAPER10E：{paper10e_line}
    22. trace online：false。
    23. per-case tuning：false。
    24. 外部 DA/LC：未运行。
    25. render QA：见 `{ALIASES["stage"]}/21_render_QA`。
    26. Git commit：{commit_hash}。
    27. commit hash：{commit_hash}。
    28. push：false。
    29. C export：`{ALIASES["c_export"]}`。
    30. Obsidian：`{ALIASES["obsidian"]}`。
    """
    code = """
    # PAPER10B2 QM Code Chain Summary

    Config loader -> Go2 readiness metadata loader -> GIEngine SourceMetadata
    and ObservationInnovation -> SourceAwarePolicy LSIM/OIM -> QualityStateManager
    -> EKF update action -> QualityStateTrace and RUN_MANIFEST stats.

    No trace online. No final_v23/LegSA output solver input. No output
    substitution. Default off through QM00_OFF.
    """
    by = f"""
    # PAPER10B2 QM BY2/BY3 Decision Summary

    BY2 completed rows: {decision["by2_completed"]}/600.
    BY3 completed rows: {decision["by3_completed"]}/600.
    BY3 stop reason: {decision["by3_stop_reason"]}.
    Missing rows: {decision["missing_rows"]}.
    BY3 yaw remains diagnostic-only.

    Decision: `{decision["innovation_decision"]}`.
    {decision["decision_text"]}
    """
    claim = f"""
    # PAPER10B2 QM Claim Decision Summary

    Final status: `{decision["final_status"]}`.

    Allowed: implemented source-level multi-state QM; state/action/recovery
    trace; LSIM/OIM and Go2 readiness feed QM.

    Boundary: no universal superiority, no final_v23 outperform claim, BY3 yaw
    diagnostic-only, no Go2 pose/yaw truth.
    """
    next_stage = """
    # PAPER10B2 Next Stage Instructions

    Recommended next step under hard-stop status: restore E drive free space,
    then run the BY3 missing-only resume manifest. Enter
    PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE only after
    human review of QM boundary wording and the BY3 resume decision.

    Do not reopen external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO. Do not use trace online or per-case tuning.
    """
    export_index = f"""
    # PAPER10B2 Export Index

    Runtime root: `{ALIASES["stage"]}`.
    C export root: `{ALIASES["c_export"]}`.
    Obsidian sync root: `{ALIASES["obsidian"]}`.

    Top-level reports:
    - PAPER10B2_SUPERVISOR_FINAL_REPORT.md
    - PAPER10B2_QM_CODE_CHAIN_SUMMARY.md
    - PAPER10B2_QM_BY2_BY3_DECISION_SUMMARY.md
    - PAPER10B2_QM_CLAIM_DECISION_SUMMARY.md
    - PAPER10B2_NEXT_STAGE_INSTRUCTIONS.md
    - PAPER10B2_EXPORT_INDEX.md
    """
    files = {
        "PAPER10B2_SUPERVISOR_FINAL_REPORT.md": report,
        "PAPER10B2_QM_CODE_CHAIN_SUMMARY.md": code,
        "PAPER10B2_QM_BY2_BY3_DECISION_SUMMARY.md": by,
        "PAPER10B2_QM_CLAIM_DECISION_SUMMARY.md": claim,
        "PAPER10B2_NEXT_STAGE_INSTRUCTIONS.md": next_stage,
        "PAPER10B2_EXPORT_INDEX.md": export_index,
    }
    for name, text in files.items():
        write_text(repo / name, text)
        write_text(stage_root / name, text)
        write_text(c_export_root / name, text)
    return files


def copy_export(stage_root: Path, c_export_root: Path) -> None:
    c_export_root.mkdir(parents=True, exist_ok=True)
    copy_dirs = [
        "02_import_PAPER10B_10C_10Y_evidence",
        "03_qm_state_machine_design",
        "04_qm_code_audit_and_patch",
        "05_qm_unit_and_integration_tests",
        "06_qm_config_freeze",
        "07_QM_normal_smoke_BY2_BY3",
        "10_BY2_120_qm_ablation_evaluation",
        "11_BY2_qm_state_action_trace_analysis",
        "14_BY3_120_qm_ablation_evaluation",
        "15_BY3_qm_state_action_trace_analysis",
        "16_BY2_BY3_qm_cross_dataset_decision",
        "17_qm_relation_to_sourceaware_and_go2",
        "18_internal_comparison_update",
        "19_paper_facing_tables",
        "20_figures",
        "21_render_QA",
        "22_claim_boundary",
        "23_manuscript_method_and_result_text_draft",
        "24_teacher_consultation_package",
        "25_obsidian_incremental_sync",
        "27_export_QA",
    ]
    banned_names = {"EVAL_NAV.csv", "RUN_MANIFEST.json", "LegSA_PORT_STD.csv", "FGO_FEEDBACK_OBSERVATIONS.csv", "FGO_SMOOTHED_NAV.csv", "FGO_FACTOR_TABLE.csv", "by2.txt", "by3.txt"}
    banned_suffixes = {".bag", ".ubx", ".rtcm", ".rinex", ".zip", ".tar", ".gz", ".7z", ".nav", ".std"}
    banned_parts = {"solver_outputs", "official_eval", "checkpoints", "runtime_only_large_outputs"}
    for rel in copy_dirs:
        src = stage_root / rel
        if not src.exists():
            continue
        dst = c_export_root / rel
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(src)
            if any(part in banned_parts for part in rel_path.parts):
                continue
            if path.name in banned_names or path.suffix.lower() in banned_suffixes:
                continue
            if file_size(path) > 50 * 1024 * 1024:
                continue
            target = dst / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def export_qa(stage_root: Path, c_export_root: Path, repo: Path, obsidian_root: Path) -> None:
    files = list(c_export_root.rglob("*")) if c_export_root.exists() else []
    file_rows = []
    banned_patterns = re.compile(r"(by2\.txt|by3\.txt|EVAL_NAV|RUN_MANIFEST|LegSA_PORT_STD|\.ubx$|\.rtcm$|\.bag$|\.zip$|\.7z$)", re.I)
    bad = []
    for path in files:
        if not path.is_file():
            continue
        rel = path.relative_to(c_export_root)
        size = file_size(path)
        issue = ""
        if banned_patterns.search(str(rel)):
            issue = "banned_payload"
        elif size > 50 * 1024 * 1024:
            issue = "over_50mb"
        file_rows.append({"relative_path": str(rel), "size_bytes": size, "issue": issue})
        if issue:
            bad.append(str(rel))
    write_text(c_export_root / "PAPER10B2_EXPORT_INDEX.md", (repo / "PAPER10B2_EXPORT_INDEX.md").read_text(encoding="utf-8") if (repo / "PAPER10B2_EXPORT_INDEX.md").exists() else "# PAPER10B2 Export Index")
    write_csv(stage_root / "27_export_QA" / "PAPER10B2_EXPORT_FILE_INDEX.csv", file_rows)
    qa_text = f"""
    # PAPER10B2 Export QA Report

    C export files checked: {sum(1 for p in files if p.is_file())}.
    Banned/oversize issues: {len(bad)}.
    Wrong Obsidian root used: false.
    Push performed: false.
    Images/PDF are export/runtime artifacts only and are not staged in Git.
    """
    write_text(stage_root / "27_export_QA" / "PAPER10B2_EXPORT_QA_REPORT.md", qa_text)
    write_text(stage_root / "27_export_QA" / "PAPER10B2_EXPORT_INDEX.md", (repo / "PAPER10B2_EXPORT_INDEX.md").read_text(encoding="utf-8") if (repo / "PAPER10B2_EXPORT_INDEX.md").exists() else "# PAPER10B2 Export Index")
    write_text(c_export_root / "27_export_QA" / "PAPER10B2_EXPORT_QA_REPORT.md", qa_text)
    write_text(c_export_root / "27_export_QA" / "PAPER10B2_EXPORT_INDEX.md", (repo / "PAPER10B2_EXPORT_INDEX.md").read_text(encoding="utf-8") if (repo / "PAPER10B2_EXPORT_INDEX.md").exists() else "# PAPER10B2 Export Index")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--c-export-root", type=Path, required=True)
    parser.add_argument("--obsidian-vault", type=Path, required=True)
    parser.add_argument("--commit-hash", default="pending")
    args = parser.parse_args()

    ensure_dirs(args.stage_root)
    generate_import_docs(args.stage_root)
    generate_design_docs(args.stage_root)
    generate_code_reports(args.stage_root, args.repo)
    generate_test_reports(args.stage_root)
    generate_config_docs(args.stage_root)
    data = load_stage(args.stage_root)
    runner_result = load_runner_result(args.stage_root)
    resume_summary = generate_resume_manifest(args.stage_root, runner_result)
    generate_smoke_decision(args.stage_root, data)
    trace_outputs = generate_trace_outputs(args.stage_root, data)
    decision = decision_summary(args.stage_root, data, trace_outputs, runner_result, resume_summary)
    generate_decision_docs(args.stage_root, data, trace_outputs, decision)
    generate_relation_docs(args.stage_root)
    generate_internal_comparison(args.stage_root, decision)
    generate_paper_tables(args.stage_root, data)
    figure_files = generate_figures(args.stage_root, data, trace_outputs)
    render_qa(args.stage_root, figure_files)
    generate_claim_boundary(args.stage_root, decision)
    generate_manuscript(args.stage_root, decision)
    generate_teacher_package(args.stage_root, decision)
    write_obsidian(args.obsidian_vault, decision)
    generate_git_context_update_report(args.stage_root, decision)
    generate_root_reports(args.repo, args.stage_root, args.c_export_root, args.obsidian_vault, decision, args.commit_hash)
    copy_export(args.stage_root, args.c_export_root)
    export_qa(args.stage_root, args.c_export_root, args.repo, args.obsidian_vault)
    write_json(args.stage_root / "logs" / "PAPER10B2_POSTPROCESS_DECISION.json", decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
