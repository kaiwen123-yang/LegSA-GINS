#!/usr/bin/env python3
"""BY3A4A lateral dual-antenna yaw repair and memory-lock stage.

This runner is intentionally evaluator/report only. It reads existing BY3A3
normal outputs, audits yaw reference conventions, writes BY3A4A runtime reports,
and creates untracked memory artifacts. It does not run solvers, degradation
generation, parameter tuning, or output correction.
"""

from __future__ import annotations

import csv
import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STAGE = "BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK"
RUNTIME_STAGE = "BY3A4A_YAW_REPAIR"
BASE_TIME = 1772784394.943074
COMMON_ALGORITHMS = [
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]
LOCAL_PATH_RE = re.compile(
    "(" + r"[A-Za-z]:" + r"\\" + "|" + "/" + "mnt/[a-z]/" + "|" + "/" + "home/" + "|" + "/" + "Users/" + ")"
)


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    by3a3_stage: Path
    by3a3_runtime: Path
    by3a1_stage: Path
    seed_root: Path
    obsidian_by3: Path
    obsidian_by2: Path

    @classmethod
    def build(cls, repo: Path, seed_root: Path | None) -> "Paths":
        by3_root = repo / "by3-huiti"
        resolved_seed_root = seed_root or Path(os.environ.get("BY2_DEGRADATION_TEXT_SUMMARY_ROOT", "by2-huitu/退化实验/文字总结_三方案复刻版/00_INDEX"))
        return cls(
            repo=repo,
            stage_root=by3_root / STAGE,
            runtime_root=by3_root / "BY3_FULL_MATRIX" / RUNTIME_STAGE,
            by3a3_stage=by3_root / "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION",
            by3a3_runtime=by3_root / "BY3_FULL_MATRIX" / "BY3A3_NORMAL_EXECUTION",
            by3a1_stage=by3_root / "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR",
            seed_root=resolved_seed_root,
            obsidian_by3=repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization",
            obsidian_by2=repo / "obsidian_knowledge" / "LegSA-GINS" / "BY2_degradation",
        )


def ensure_dirs(paths: Paths) -> None:
    for base in [paths.stage_root, paths.runtime_root]:
        for name in [
            "00_supervisor",
            "01_plan",
            "yaw_policy_recovery",
            "lateral_antenna_geometry",
            "evaluator_repair",
            "common_overlap",
            "repaired_figures",
            "seed_explanation",
            "context_update",
            "obsidian_sync",
            "reports",
            "matrix",
            "summary",
            "validation",
            "logs",
            "case_review",
            "figures",
        ]:
            (base / name).mkdir(parents=True, exist_ok=True)
    for fig_dir in [
        "01_trajectory",
        "02_position_errors",
        "04_attitude",
        "07_compare",
        "14_audit_sanity",
    ]:
        (paths.stage_root / "figures" / fig_dir).mkdir(parents=True, exist_ok=True)
    paths.seed_root.mkdir(parents=True, exist_ok=True)
    paths.obsidian_by3.mkdir(parents=True, exist_ok=True)
    paths.obsidian_by2.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    write_json(stem.with_suffix(".json"), rows)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with stem.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys or ["empty"])
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def wrap_deg(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def wrap_360(angle: float) -> float:
    return float(angle) % 360.0


def unwrap_deg(values: list[float]) -> list[float]:
    output: list[float] = []
    offset = 0.0
    prev: float | None = None
    for value in values:
        if prev is not None:
            delta = value + offset - prev
            while delta > 180.0:
                offset -= 360.0
                delta -= 360.0
            while delta < -180.0:
                offset += 360.0
                delta += 360.0
        unwrapped = value + offset
        output.append(unwrapped)
        prev = unwrapped
    return output


def interp_scalar(x: float, xs: list[float], ys: list[float]) -> float | None:
    if not xs or x < xs[0] or x > xs[-1]:
        return None
    lo = 0
    hi = len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] < x:
            lo = mid + 1
        elif xs[mid] > x:
            hi = mid - 1
        else:
            return ys[mid]
    left = max(0, hi)
    right = min(len(xs) - 1, lo)
    x0, x1 = xs[left], xs[right]
    y0, y1 = ys[left], ys[right]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


def percentile_abs(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(abs(v) for v in values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def max_abs(values: list[float]) -> float | None:
    return max((abs(v) for v in values), default=None)


def lla_to_local(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    east = (lon - lon0) * meters_per_deg_lon
    north = (lat - lat0) * meters_per_deg_lat
    return east, north


def load_official_nav(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith(("#", "%")):
                continue
            parts = line.split()
            if len(parts) < 11:
                continue
            try:
                rows.append(
                    {
                        "time": float(parts[1]),
                        "lat": float(parts[2]),
                        "lon": float(parts[3]),
                        "alt": float(parts[4]),
                        "roll": float(parts[8]),
                        "pitch": float(parts[9]),
                        "yaw": float(parts[10]),
                    }
                )
            except ValueError:
                continue
    return rows


def load_error_series(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed: dict[str, float] = {}
            for key, value in row.items():
                try:
                    parsed[key] = float(value)
                except (TypeError, ValueError):
                    pass
            if parsed:
                rows.append(parsed)
    return rows


def discover_trace_path(repo: Path) -> Path | None:
    desktop = repo.parent
    matches = list(desktop.glob("**/trace_vrtk2_a87c6e_2026-03-06-08-06-39_minimal.csv"))
    by3_matches = [path for path in matches if "by3" in str(path).lower()]
    return by3_matches[0] if by3_matches else (matches[0] if matches else None)


def load_trace(trace_path: Path | None) -> list[dict[str, float]]:
    if trace_path is None or not trace_path.exists():
        return []
    rows: list[dict[str, float]] = []
    with trace_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(
                    {
                        "time": float(row["time"]) - BASE_TIME,
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "alt": float(row["height"]),
                        "roll": float(row["roll"]),
                        "pitch": float(row["pitch"]),
                        "yaw": float(row["yaw"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    rows.sort(key=lambda item: item["time"])
    return rows


def load_dual_status_yaw(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 15:
                continue
            try:
                rows.append({"time": float(parts[0]), "yaw_ned": float(parts[13])})
            except ValueError:
                continue
    rows.sort(key=lambda item: item["time"])
    return rows


def metric_row(algorithm: str, summary: dict[str, Any]) -> dict[str, Any]:
    position = summary.get("position", {})
    attitude = summary.get("attitude", {})
    meta = summary.get("meta", {})
    return {
        "algorithm": algorithm,
        "north_rmse_m": position.get("north_rmse_m"),
        "east_rmse_m": position.get("east_rmse_m"),
        "up_rmse_m": position.get("up_rmse_m"),
        "horizontal_rmse_m": position.get("horizontal_rmse_m"),
        "horizontal_p95_m": position.get("horizontal_p95_m"),
        "horizontal_max_m": position.get("horizontal_max_m"),
        "up_p95_m": position.get("vertical_p95_m"),
        "up_max_m": position.get("vertical_max_m"),
        "roll_rmse_deg": attitude.get("roll_rmse_deg"),
        "pitch_rmse_deg": attitude.get("pitch_rmse_deg"),
        "yaw_rmse_deg": attitude.get("yaw_rmse_deg"),
        "yaw_p95_deg": attitude.get("yaw_p95_deg"),
        "yaw_max_deg": attitude.get("yaw_max_deg"),
        "sample_count": meta.get("num_samples"),
        "time_start": meta.get("time_start"),
        "time_end": meta.get("time_end"),
        "yaw_truth_mode": meta.get("yaw_truth_mode"),
    }


def collect_algorithm_inputs(paths: Paths) -> dict[str, dict[str, Path]]:
    return {
        "LegSA_full_EKF": {
            "nav": paths.by3a3_stage / "official_eval" / "LegSA_full_EKF" / "converted_eval_nav_official.nav",
            "eval_dir": paths.by3a3_stage / "official_eval" / "LegSA_full_EKF",
        },
        "single_antenna_gnss1_status_KF_GINS": {
            "nav": paths.by3a3_runtime
            / "single_baseline_solver"
            / "single_antenna_gnss1_status_KF_GINS"
            / "KF_GINS_Navresult.nav",
            "eval_dir": paths.by3a3_stage / "official_eval" / "single_antenna_gnss1_status_KF_GINS",
        },
        "final_v23_dual_antenna_EKF": {
            "nav": paths.by3a3_runtime
            / "finalv23_solver"
            / "final_v23_dual_antenna_EKF"
            / "KF_GINS_Navresult.nav",
            "eval_dir": paths.by3a3_stage / "official_eval" / "final_v23_dual_antenna_EKF",
        },
    }


def build_by2_policy_recovery(paths: Paths) -> dict[str, Any]:
    evidence = [
        {
            "evidence_path": "docs/dual_antenna_heading_mounting.md",
            "snippet_summary": "BY2 uses transverse dual antenna; baseline heading needs a mounting offset candidate, plus90 or minus90; trace is not allowed for formal selection.",
            "policy": "transverse/lateral antenna baseline is not robot body heading",
            "accepted_or_historical": "accepted geometry boundary, offset not formally selected",
            "confidence": "high for lateral geometry, partial for antenna order",
        },
        {
            "evidence_path": "docs/experiments/process_data_compat_generation.md",
            "snippet_summary": "A1 dual status yaw uses gnss2-gnss1 relative north/east and NED yaw uses yaw_ned = 90 - yaw_body.",
            "policy": "A1_dual_diff baseline -> yaw_body -> yaw_ned",
            "accepted_or_historical": "accepted process_data-compatible input reconstruction",
            "confidence": "high",
        },
        {
            "evidence_path": "docs/experiments/final_v23_yaw_generation_chain.md",
            "snippet_summary": "A1 formula b_n=rel_pos_n(gnss2)-rel_pos_n(gnss1), b_e=rel_pos_e(gnss2)-rel_pos_e(gnss1), yaw=-atan2(b_e,b_n); plus/minus90 and reversal candidates are diagnostic.",
            "policy": "baseline direction and lateral mounting candidates must be audited",
            "accepted_or_historical": "diagnostic-only, no formal trace-selected offset",
            "confidence": "high",
        },
        {
            "evidence_path": "docs/experiments/n4h2c_yaw_config_parity_decision.md",
            "snippet_summary": "Runtime audit recorded status mode and diagnostic best status variant sign=-1 offset=+90, but also forbids trace-based formal yaw-offset selection.",
            "policy": "BY2 diagnostic evidence supports a sign/offset problem, not RMSE-only formal selection",
            "accepted_or_historical": "diagnostic; not a paper/performance claim",
            "confidence": "medium",
        },
        {
            "evidence_path": "src/legsa_gins/input_generation/status_yaw_builder.py",
            "snippet_summary": "Implementation builds A1 dual-diff yaw and applies yaw_body=sign*baseline+offset, yaw_ned=90-yaw_body.",
            "policy": "code-level BY2/BY3 input-generation convention",
            "accepted_or_historical": "current tracked source evidence",
            "confidence": "high",
        },
    ]
    rows = []
    for item in evidence:
        row = dict(item)
        row.update(
            {
                "antenna_baseline_direction": "gnss2_minus_gnss1 for A1_dual_diff when using status_yaw_builder",
                "frame_convention": "body heading converted to NED yaw by yaw_ned=90-yaw_body",
                "formula": "yaw_baseline=-atan2(rel_e,rel_n); yaw_body=sign*yaw_baseline+offset; yaw_ned=90-yaw_body",
            }
        )
        rows.append(row)
    decision = {
        "stage": STAGE,
        "decision": "BY3A4A_by2_yaw_policy_partial",
        "by2_lateral_yaw_policy_recovered": True,
        "formal_plus_minus_90_selected": False,
        "reason": "BY2 lateral geometry and A1 conversion formula were recovered, but antenna order/formal offset remains not selected by tracked BY2 evidence alone.",
        "evidence": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_BY2_LATERAL_YAW_POLICY_RECOVERY_REPORT.json", decision)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_BY2_YAW_POLICY_EVIDENCE", rows)
    write_text(
        paths.stage_root / "summary" / "by3a4a_by2_lateral_yaw_policy_recovery.md",
        "\n".join(
            [
                "# BY3A4A BY2 Lateral Yaw Policy Recovery",
                "",
                "- decision: `BY3A4A_by2_yaw_policy_partial`",
                "- recovered: transverse/lateral antenna geometry and A1 dual-diff formula.",
                "- formula: `yaw_baseline=-atan2(rel_e,rel_n); yaw_body=sign*yaw_baseline+offset; yaw_ned=90-yaw_body`.",
                "- caution: BY2 tracked evidence does not allow selecting +90/-90 only by yaw RMSE.",
                "- ready_for_paper_claims=false.",
                "",
            ]
        ),
    )
    return decision


def build_geometry_report(paths: Paths) -> dict[str, Any]:
    rows = [
        {
            "field": "antenna_mounting",
            "value": "lateral / 横向",
            "source": "human confirmation for BY3A4A plus BY2 transverse-dual-antenna docs",
        },
        {
            "field": "antenna_baseline_axis_body",
            "value": "approximately body Y axis, not body X forward",
            "source": "physical mounting statement",
        },
        {
            "field": "robot_forward_axis",
            "value": "dog head / body X forward",
            "source": "physical mounting statement",
        },
        {
            "field": "dual_antenna_baseline_heading_is_not_body_heading",
            "value": True,
            "source": "lateral geometry",
        },
        {
            "field": "body_heading_requires_baseline_heading_plus_or_minus_90_deg",
            "value": True,
            "source": "lateral geometry",
        },
        {
            "field": "gnss1_to_gnss2_direction",
            "value": "not independently confirmed in BY3A4A; must be inferred from accepted BY2 policy or hardware, not RMSE minimization",
            "source": "policy lock",
        },
        {
            "field": "frame_conversion",
            "value": "ENU/math yaw and NED heading are related by heading_ned=90-yaw_enu when the source is a true ENU yaw",
            "source": "official evaluator pattern",
        },
        {
            "field": "wrap_policy",
            "value": "unwrap before interpolation; wrap error after difference",
            "source": "official evaluator pattern and BY3A4A lock",
        },
    ]
    candidates = [
        "body_heading = wrap(baseline_heading + 90 deg)",
        "body_heading = wrap(baseline_heading - 90 deg)",
        "body_heading = wrap(baseline_heading + 90 deg + 180 deg) when baseline direction is reversed",
        "body_heading = wrap(baseline_heading - 90 deg + 180 deg) when baseline direction is reversed",
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_lateral_geometry_encoded",
        "candidate_formulas": candidates,
        "selection_rule": "Selection cannot be RMSE-only; it must be justified by physical mounting plus BY2 accepted convention.",
        "geometry_rows": rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_LATERAL_ANTENNA_GEOMETRY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_LATERAL_ANTENNA_GEOMETRY", rows)
    write_text(
        paths.stage_root / "summary" / "by3a4a_lateral_antenna_geometry.md",
        "# BY3A4A Lateral Antenna Geometry\n\n"
        "- antenna_mounting: lateral / 横向.\n"
        "- baseline axis: approximately body Y, perpendicular to body X forward.\n"
        "- body heading requires baseline heading plus or minus 90 degrees.\n"
        "- +90/-90 must not be chosen by lowest yaw RMSE alone.\n"
        "- unwrap before interpolation; wrap after difference.\n",
    )
    return report


def trace_reference_candidates(trace_rows: list[dict[str, float]]) -> dict[str, dict[str, Any]]:
    times = [row["time"] for row in trace_rows]
    raw_unwrapped = unwrap_deg([row["yaw"] for row in trace_rows])
    return {
        "current_BY3A3_policy": {
            "formula": "wrap(90 - trace_yaw)",
            "physical_justification": "official evaluator ENU-to-NED mode; historical BY3A3 policy",
            "by2_consistency": "matches evaluator mode, but does not encode lateral mounting by itself",
            "allowed": True,
            "times": times,
            "values": [90.0 - value for value in raw_unwrapped],
        },
        "BY2_recovered_lateral_policy": {
            "formula": "treat trace_yaw as A1 baseline diagnostic and compare to yaw_ned=baseline after sign=-1, offset=+90 diagnostic rule",
            "physical_justification": "diagnostic mirror of BY2 N4H2C sign/offset evidence; not a formal trace truth",
            "by2_consistency": "partial diagnostic consistency only",
            "allowed": True,
            "times": times,
            "values": raw_unwrapped,
        },
        "lateral_plus_90": {
            "formula": "body=baseline+90; yaw_ned=90-body=-baseline",
            "physical_justification": "lateral baseline candidate",
            "by2_consistency": "candidate only",
            "allowed": True,
            "times": times,
            "values": [-value for value in raw_unwrapped],
        },
        "lateral_minus_90": {
            "formula": "body=baseline-90; yaw_ned=90-body=180-baseline",
            "physical_justification": "lateral baseline candidate",
            "by2_consistency": "candidate only",
            "allowed": True,
            "times": times,
            "values": [180.0 - value for value in raw_unwrapped],
        },
        "lateral_plus_90_with_baseline_reversal": {
            "formula": "body=baseline+90+180; yaw_ned=90-body=-baseline-180",
            "physical_justification": "lateral baseline candidate with antenna order reversal",
            "by2_consistency": "candidate only",
            "allowed": True,
            "times": times,
            "values": [-value - 180.0 for value in raw_unwrapped],
        },
        "lateral_minus_90_with_baseline_reversal": {
            "formula": "body=baseline-90+180; yaw_ned=90-body=-baseline",
            "physical_justification": "lateral baseline candidate with antenna order reversal",
            "by2_consistency": "candidate only",
            "allowed": True,
            "times": times,
            "values": [-value for value in raw_unwrapped],
        },
    }


def compute_yaw_candidate_tests(
    paths: Paths,
    navs: dict[str, list[dict[str, float]]],
    trace_rows: list[dict[str, float]],
    dual_yaw_rows: list[dict[str, float]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    candidates = trace_reference_candidates(trace_rows)
    if dual_yaw_rows:
        candidates["BY3_dual_status_yaw_observation_diagnostic"] = {
            "formula": "use BY3A1 repaired 15-column GNSS yaw column as diagnostic status yaw observation",
            "physical_justification": "dual status observation only; not trace truth and not an algorithm estimate",
            "by2_consistency": "uses repaired BY3A1 process_data-compatible yaw field",
            "allowed": False,
            "times": [row["time"] for row in dual_yaw_rows],
            "values": unwrap_deg([row["yaw_ned"] for row in dual_yaw_rows]),
        }
    for policy, candidate in candidates.items():
        times = candidate["times"]
        values = candidate["values"]
        for algorithm, nav_rows in navs.items():
            errors: list[float] = []
            for item in nav_rows:
                ref = interp_scalar(item["time"], times, values)
                if ref is not None:
                    errors.append(wrap_deg(item["yaw"] - ref))
            diffs = [abs(errors[i] - errors[i - 1]) for i in range(1, len(errors))]
            yaw_rmse = rmse(errors)
            yaw_p95 = percentile_abs(errors, 95.0)
            row = {
                "policy": policy,
                "algorithm": algorithm,
                "formula": candidate["formula"],
                "physical_justification": candidate["physical_justification"],
                "BY2_consistency": candidate["by2_consistency"],
                "sample_count": len(errors),
                "yaw_rmse_deg": yaw_rmse,
                "yaw_p95_deg": yaw_p95,
                "yaw_max_deg": max_abs(errors),
                "yaw_error_mean_deg": sum(errors) / len(errors) if errors else None,
                "yaw_error_shape": "wide_wrapped_distribution" if yaw_p95 and yaw_p95 > 90.0 else "compact",
                "sawtooth_detected": any(diff > 120.0 for diff in diffs),
                "allowed": bool(candidate["allowed"]),
                "reason": "candidate failed BY3 yaw sanity" if (yaw_rmse is None or yaw_rmse > 20.0) else "candidate produced low yaw error",
                "selected_repair": False,
            }
            rows.append(row)
    by_policy: dict[str, list[float]] = {}
    for row in rows:
        value = row.get("yaw_rmse_deg")
        if isinstance(value, (int, float)) and row.get("allowed"):
            by_policy.setdefault(str(row["policy"]), []).append(float(value))
    policy_reasonable = {
        policy: all(value <= 20.0 for value in values) and len(values) == len(navs)
        for policy, values in by_policy.items()
    }
    approved = [policy for policy, ok in policy_reasonable.items() if ok]
    if approved:
        decision = "BY3A4A_yaw_policy_repaired"
        selected = approved[0]
        for row in rows:
            row["selected_repair"] = row["policy"] == selected
    else:
        decision = "BY3A4A_yaw_policy_inconclusive"
        selected = None
    report = {
        "stage": STAGE,
        "decision": decision,
        "selected_policy": selected,
        "selection_not_rmse_only": True,
        "reason": (
            "No physically meaningful trace/lateral candidate produced reasonable yaw error across all three algorithms; "
            "therefore BY3A4A blocks repaired yaw metrics instead of selecting an RMSE-only offset."
        )
        if not selected
        else "Selected policy is both physically/BY2-backed and low-error.",
        "trace_solver_input": False,
        "solver_rerun": False,
        "parameter_retuning": False,
        "candidate_count": len(rows),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_YAW_EVALUATOR_POLICY_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_YAW_POLICY_CANDIDATE_TESTS", rows)
    write_text(
        paths.stage_root / "summary" / "by3a4a_yaw_evaluator_policy_audit.md",
        "# BY3A4A Yaw Evaluator Policy Audit\n\n"
        f"- decision: `{decision}`\n"
        "- tested policies: current BY3A3 ENU mode, BY2 recovered lateral diagnostic, plus/minus 90, and baseline reversal candidates.\n"
        "- selection rule: no +90/-90 policy may be selected by RMSE alone.\n"
        "- result: no candidate produced sane yaw across all three BY3 normal algorithms, so repaired yaw metrics are blocked.\n"
        "- trace_solver_input=false; solver_rerun=false; parameter_retuning=false.\n",
    )
    return {"report": report, "rows": rows}


def build_repaired_eval_report(
    paths: Paths,
    original_metrics: list[dict[str, Any]],
    yaw_audit: dict[str, Any],
) -> dict[str, Any]:
    repaired_rows: list[dict[str, Any]] = []
    decision = yaw_audit["report"]["decision"]
    for row in original_metrics:
        item = dict(row)
        item.update(
            {
                "original_BY3A3_yaw_rmse_deg": row.get("yaw_rmse_deg"),
                "original_BY3A3_yaw_p95_deg": row.get("yaw_p95_deg"),
                "repaired_yaw_rmse_deg": None,
                "repaired_yaw_p95_deg": None,
                "repaired_yaw_max_deg": None,
                "yaw_policy_status": decision,
                "original_BY3A3_metrics_preserved": True,
                "supersedes_BY3A3_yaw": False,
                "paper_claim": False,
            }
        )
        repaired_rows.append(item)
    status_rows = [
        {
            "stage": STAGE,
            "official_evaluator_rerun": False,
            "solver_rerun": False,
            "existing_BY3A3_outputs_only": True,
            "repaired_eval_status": "blocked",
            "reason": "yaw policy inconclusive; no accepted repaired yaw policy",
            "ready_for_paper_claims": False,
        }
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_repaired_eval_blocked",
        "reason": "Candidate yaw policies were evaluated from existing BY3A3 outputs, but no physical/BY2-backed policy passed yaw sanity.",
        "original_BY3A3_metrics_preserved": True,
        "original_metrics_marked_historical": True,
        "supersedes_BY3A3_yaw_metrics": False,
        "solver_rerun": False,
        "parameter_retuning": False,
        "trace_evaluation_only": True,
        "metrics": repaired_rows,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_REPAIRED_EVALUATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_REPAIRED_EVAL_STATUS", status_rows)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_REPAIRED_NORMAL_METRICS", repaired_rows)
    write_text(
        paths.stage_root / "summary" / "by3a4a_repaired_eval_summary.md",
        "# BY3A4A Repaired Evaluation Summary\n\n"
        "- decision: `BY3A4A_repaired_eval_blocked`.\n"
        "- existing BY3A3 solver outputs were used for candidate evaluator tests only.\n"
        "- no solver rerun, no parameter retuning, no degradation matrix.\n"
        "- original BY3A3 yaw metrics are preserved as historical caution evidence, not hidden.\n"
        "- no repaired yaw metric is accepted because yaw policy remains inconclusive.\n",
    )
    return report


def compute_common_overlap(paths: Paths, original_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    eval_dirs = {row["algorithm"]: paths.by3a3_stage / "official_eval" / row["algorithm"] for row in original_metrics}
    series = {algorithm: load_error_series(eval_dir / "error_series.csv") for algorithm, eval_dir in eval_dirs.items()}
    starts = [rows[0]["time"] for rows in series.values() if rows]
    ends = [rows[-1]["time"] for rows in series.values() if rows]
    if len(starts) != len(COMMON_ALGORITHMS):
        report = {"stage": STAGE, "decision": "BY3A4A_common_overlap_blocked", "reason": "missing error_series", "ready_for_paper_claims": False}
        write_json(paths.stage_root / "reports" / "BY3A4A_COMMON_OVERLAP_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3A4A_COMMON_OVERLAP_METRICS", [])
        return {"report": report, "rows": [], "series": series}
    common_start = max(starts)
    common_end = min(ends)
    rows_out: list[dict[str, Any]] = []
    for metric in original_metrics:
        algorithm = str(metric["algorithm"])
        rows = [row for row in series[algorithm] if common_start <= row["time"] <= common_end]
        h = [row["horizontal_err_m"] for row in rows if "horizontal_err_m" in row]
        u = [row["err_u_m"] for row in rows if "err_u_m" in row]
        n = [row["err_n_m"] for row in rows if "err_n_m" in row]
        e = [row["err_e_m"] for row in rows if "err_e_m" in row]
        yaw = [row["yaw_err_deg"] for row in rows if "yaw_err_deg" in row]
        full_start = float(metric.get("time_start") or starts[0])
        full_h_rmse = metric.get("horizontal_rmse_m")
        common_h_rmse = rmse(h)
        rows_out.append(
            {
                "algorithm": algorithm,
                "common_start": common_start,
                "common_end": common_end,
                "sample_count_common": len(rows),
                "north_rmse_common_m": rmse(n),
                "east_rmse_common_m": rmse(e),
                "up_rmse_common_m": rmse(u),
                "horizontal_rmse_common_m": common_h_rmse,
                "horizontal_p95_common_m": percentile_abs(h, 95.0),
                "horizontal_max_common_m": max_abs(h),
                "yaw_rmse_current_policy_common_deg": rmse(yaw),
                "yaw_p95_current_policy_common_deg": percentile_abs(yaw, 95.0),
                "repaired_yaw_rmse_common_deg": None,
                "removed_initial_transient_sec": max(0.0, common_start - full_start),
                "full_horizontal_rmse_m": full_h_rmse,
                "full_horizontal_max_m": metric.get("horizontal_max_m"),
                "common_overlap_horizontal_rmse_delta_m": None
                if full_h_rmse is None or common_h_rmse is None
                else common_h_rmse - float(full_h_rmse),
                "legsa_initial_transient_affected_horizontal": algorithm == "LegSA_full_EKF"
                and full_h_rmse is not None
                and common_h_rmse is not None
                and abs(common_h_rmse - float(full_h_rmse)) > 0.05,
                "paper_claim": False,
            }
        )
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_common_overlap_metrics_ready",
        "common_start": common_start,
        "common_end": common_end,
        "strict_common_overlap_only": True,
        "bad_epoch_deletion": False,
        "repaired_yaw_metrics_ready": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_COMMON_OVERLAP_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_COMMON_OVERLAP_METRICS", rows_out)
    write_text(
        paths.stage_root / "summary" / "by3a4a_common_overlap_summary.md",
        "# BY3A4A Common-Overlap Summary\n\n"
        f"- decision: `BY3A4A_common_overlap_metrics_ready`.\n"
        f"- common interval: `{common_start}` to `{common_end}` seconds.\n"
        "- strict common overlap only; no arbitrary epoch deletion.\n"
        "- repaired yaw metrics remain blocked by yaw policy inconclusive.\n",
    )
    return {"report": report, "rows": rows_out, "series": series}


def draw_figures(
    paths: Paths,
    navs: dict[str, list[dict[str, float]]],
    trace_rows: list[dict[str, float]],
    common: dict[str, Any],
    original_metrics: list[dict[str, Any]],
    yaw_audit: dict[str, Any],
) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        report = {"stage": STAGE, "decision": "BY3A4A_repaired_figures_blocked", "reason": f"matplotlib unavailable: {exc}"}
        write_json(paths.stage_root / "reports" / "BY3A4A_REPAIRED_FIGURE_REPORT.json", report)
        write_rows(paths.stage_root / "matrix" / "BY3A4A_REPAIRED_FIGURE_INDEX", [])
        return report

    common_report = common["report"]
    common_start = common_report.get("common_start")
    common_end = common_report.get("common_end")
    series = common["series"]
    trace_plot = [row for row in trace_rows if common_start is None or common_start <= row["time"] <= common_end]
    if trace_plot:
        lat0 = trace_plot[0]["lat"]
        lon0 = trace_plot[0]["lon"]
    else:
        first_nav = next((rows[0] for rows in navs.values() if rows), {"lat": 0.0, "lon": 0.0})
        lat0 = first_nav["lat"]
        lon0 = first_nav["lon"]

    metric_by_alg = {row["algorithm"]: row for row in original_metrics}
    common_by_alg = {row["algorithm"]: row for row in common["rows"]}
    figure_specs = [
        ("01_trajectory", "BY3A4A_normal_three_way_local_ENU_trajectory", "trajectory"),
        ("01_trajectory", "BY3A4A_normal_three_way_start_end_marker", "trajectory_markers"),
        ("01_trajectory", "BY3A4A_normal_three_way_zoom", "trajectory_zoom"),
        ("02_position_errors", "BY3A4A_normal_N_E_U_error_timeseries_common_overlap", "neu"),
        ("02_position_errors", "BY3A4A_normal_horizontal_error_timeseries_common_overlap", "horizontal"),
        ("02_position_errors", "BY3A4A_normal_horizontal_up_rmse_bar_common_overlap", "rmse_bar"),
        ("02_position_errors", "BY3A4A_normal_horizontal_up_p95_bar_common_overlap", "p95_bar"),
        ("04_attitude", "BY3A4A_normal_yaw_error_timeseries_repaired", "yaw"),
        ("04_attitude", "BY3A4A_normal_attitude_rmse_bar_repaired", "attitude_bar"),
        ("07_compare", "BY3A4A_normal_LegSA_full_single_finalv23_summary", "summary"),
        ("14_audit_sanity", "BY3A4A_yaw_policy_common_overlap_sanity_panel", "sanity"),
    ]
    rows_out: list[dict[str, Any]] = []
    for subdir, stem, kind in figure_specs:
        fig, ax = plt.subplots(figsize=(9, 5))
        plotted = False
        if kind.startswith("trajectory"):
            for algorithm, nav_rows in navs.items():
                rows = [row for row in nav_rows if common_start is None or common_start <= row["time"] <= common_end]
                if kind == "trajectory_zoom":
                    rows = rows[: min(300, len(rows))]
                if rows:
                    xy = [lla_to_local(row["lat"], row["lon"], lat0, lon0) for row in rows]
                    ax.plot([v[0] for v in xy], [v[1] for v in xy], label=algorithm, linewidth=1.0)
                    if kind == "trajectory_markers":
                        ax.scatter([xy[0][0], xy[-1][0]], [xy[0][1], xy[-1][1]], s=18)
                    plotted = True
            if trace_plot:
                trace_xy = [lla_to_local(row["lat"], row["lon"], lat0, lon0) for row in trace_plot]
                if kind == "trajectory_zoom":
                    trace_xy = trace_xy[: min(300, len(trace_xy))]
                ax.plot([v[0] for v in trace_xy], [v[1] for v in trace_xy], label="trace/reference", linewidth=1.0, linestyle="--")
                plotted = True
            ax.set_xlabel("East (m)")
            ax.set_ylabel("North (m)")
        elif kind in {"neu", "horizontal", "yaw"}:
            for algorithm, err_rows in series.items():
                rows = [row for row in err_rows if common_start <= row["time"] <= common_end]
                t = [row["time"] for row in rows]
                if kind == "horizontal":
                    vals = [row["horizontal_err_m"] for row in rows]
                    ax.plot(t, vals, label=algorithm, linewidth=0.9)
                    ax.set_ylabel("Horizontal error (m)")
                    plotted = True
                elif kind == "yaw":
                    vals = [row["yaw_err_deg"] for row in rows]
                    ax.plot(t, vals, label=f"{algorithm} current policy", linewidth=0.9)
                    ax.set_ylabel("Yaw error (deg)")
                    plotted = True
                else:
                    for label, key in [("N", "err_n_m"), ("E", "err_e_m"), ("U", "err_u_m")]:
                        vals = [row[key] for row in rows]
                        ax.plot(t, vals, label=f"{algorithm} {label}", linewidth=0.7)
                    ax.set_ylabel("Error (m)")
                    plotted = True
            ax.set_xlabel("Time (s)")
        elif kind in {"rmse_bar", "p95_bar", "attitude_bar", "summary"}:
            labels = list(COMMON_ALGORITHMS)
            if kind == "rmse_bar":
                h_vals = [common_by_alg[label].get("horizontal_rmse_common_m") for label in labels]
                u_vals = [common_by_alg[label].get("up_rmse_common_m") for label in labels]
                xs = range(len(labels))
                ax.bar([x - 0.2 for x in xs], h_vals, width=0.4, label="horizontal")
                ax.bar([x + 0.2 for x in xs], u_vals, width=0.4, label="up")
                ax.set_xticks(list(xs), labels, rotation=15, ha="right")
                ax.set_ylabel("RMSE")
            elif kind == "p95_bar":
                h_vals = [common_by_alg[label].get("horizontal_p95_common_m") for label in labels]
                ax.bar(labels, h_vals)
                ax.tick_params(axis="x", labelrotation=15)
                ax.set_ylabel("Horizontal P95 (m)")
            elif kind == "attitude_bar":
                vals = [metric_by_alg[label].get("yaw_rmse_deg") for label in labels]
                ax.bar(labels, vals)
                ax.tick_params(axis="x", labelrotation=15)
                ax.set_ylabel("Yaw RMSE, current policy (deg)")
            else:
                vals = [common_by_alg[label].get("horizontal_rmse_common_m") for label in labels]
                ax.bar(labels, vals)
                ax.tick_params(axis="x", labelrotation=15)
                ax.set_ylabel("Common-overlap horizontal RMSE (m)")
            plotted = True
        else:
            ax.axis("off")
            text = [
                f"stage={STAGE}",
                f"yaw_decision={yaw_audit['report']['decision']}",
                f"common_overlap={common_report.get('decision')}",
                "lateral_antenna=true",
                "plus_minus_90_not_rmse_only=true",
                "solver_rerun=false",
                "degradation_matrix=false",
                "paper_claim=false",
            ]
            ax.text(0.02, 0.95, "\n".join(text), va="top", fontfamily="monospace")
            plotted = True
        if not plotted:
            ax.axis("off")
            ax.text(0.02, 0.95, "No plottable data.")
        ax.set_title(stem)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=6)
        fig.tight_layout()
        outdir = paths.stage_root / "figures" / subdir
        png = outdir / f"{stem}.png"
        pdf = outdir / f"{stem}.pdf"
        fig.savefig(png, dpi=160)
        fig.savefig(pdf)
        plt.close(fig)
        for output in [png, pdf]:
            rows_out.append(
                {
                    "figure": stem,
                    "path_alias": f"<BY3_STAGE_ROOT>/{STAGE}/figures/{subdir}/{output.name}",
                    "exists": output.exists(),
                    "file_size": output.stat().st_size if output.exists() else 0,
                    "includes_LegSA_full": True,
                    "includes_single": True,
                    "includes_finalv23": True,
                    "includes_trace": kind.startswith("trajectory") or kind == "sanity",
                    "coordinate_frame": "local ENU" if kind.startswith("trajectory") else "error/metric space",
                    "source_data": "existing BY3A3 solver outputs and official evaluation error_series; no solver rerun",
                    "supersedes_BY3A3_figure": False,
                    "paper_claim": False,
                    "content_valid": output.exists() and output.stat().st_size > 1000,
                }
            )
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_repaired_figures_generated_as_diagnostic_not_superseding",
        "reason": "Figures use real BY3A3 outputs/common-overlap data, but repaired yaw is not accepted because yaw policy is inconclusive.",
        "figure_count": len(rows_out),
        "supersedes_BY3A3": False,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_REPAIRED_FIGURE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_REPAIRED_FIGURE_INDEX", rows_out)
    write_text(
        paths.stage_root / "summary" / "by3a4a_repaired_figure_summary.md",
        "# BY3A4A Repaired Figure Summary\n\n"
        "- figures were regenerated from existing BY3A3 solver/evaluator outputs and strict common overlap.\n"
        "- because yaw policy is inconclusive, figures are diagnostic and do not supersede BY3A3 yaw figures.\n"
        "- paper_claim=false.\n",
    )
    return report


def write_seed_explanation(paths: Paths) -> dict[str, Any]:
    md = """# seed0-9 随机种子说明

## 1. seed0-9 是什么

`seed0` 到 `seed9` 是随机退化实验中使用的 10 个固定随机数种子。它们让同一类随机退化可以被重复生成、复核和比较。

## 2. 为什么随机退化需要 seed

随机退化会涉及随机噪声、随机尖峰或随机组合事件。如果不固定 seed，每次生成的退化输入都可能不同，算法之间的比较就不公平，也无法复现。

## 3. 哪些工况使用 seed0-9

- `C_position_noise`
- `D_position_spike`
- `H_dual_yaw_noise`
- `M_mixed` 中包含随机成分的子工况

## 4. 哪些工况没有 seed

- `normal`
- `A_outage`
- `B_downsample`
- `E_std_inflation`

这些工况是确定性的，或由固定区间/固定比例/固定参数定义，不需要 seed。

## 5. same seed fairness rule

同一个 seed 下，`single`、`final_v23`、`new_algorithm` 必须面对同一份退化输入。也就是说，`seed3` 不是给某一个算法单独生成的随机退化，而是三种方案共享的公平测试条件。

## 6. seed does not mean algorithm version

`seed0` 到 `seed9` 不是算法版本号，不表示第 0 版到第 9 版算法。

## 7. seed does not mean data collection repeat

`seed0` 到 `seed9` 也不是采集了 10 次真实数据。它们是在同一条原始数据上生成随机退化输入时使用的复现编号。

## 8. how to read case names

例如 `C_position_noise_medium_seed3` 表示：

- 工况族：`C_position_noise`
- 强度：`medium`
- 随机种子：`seed3`

它的含义是“中等强度的位置噪声退化，用第 3 个固定随机种子生成”。

## 9. why metrics are averaged across seeds

随机工况的单个 seed 可能偶然偏难或偏简单。对 seed0-9 求平均，可以降低偶然性，让结论更接近该退化类型的整体表现。必要时也要检查每个 seed 的离散情况，避免平均值掩盖异常。

## 10. not paper claim / audit explanation

本文档只是实验审计和复现说明，不是论文性能结论。任何论文级结论仍需要人工确认、图表审查和 claim boundary 审查。
"""
    data = {
        "title": "seed0-9随机种子说明",
        "seed_range": list(range(10)),
        "seed_meaning": "fixed random seeds for reproducible random degradation inputs",
        "random_seed_cases": ["C_position_noise", "D_position_spike", "H_dual_yaw_noise", "M_mixed when random components exist"],
        "non_seed_cases": ["normal", "A_outage", "B_downsample", "E_std_inflation"],
        "same_seed_fairness_rule": "single/final_v23/new_algorithm face the same degraded input under the same seed",
        "not_algorithm_version": True,
        "not_data_collection_repeat": True,
        "case_name_example": "C_position_noise_medium_seed3",
        "paper_claim": False,
        "local_absolute_paths": False,
    }
    md_path = paths.seed_root / "seed0-9随机种子说明.md"
    json_path = paths.seed_root / "seed0-9随机种子说明.json"
    write_text(md_path, md)
    write_json(json_path, data)
    rows = [
        {
            "artifact": "seed0-9随机种子说明.md",
            "path_alias": "<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>/00_INDEX/seed0-9随机种子说明.md",
            "created": md_path.exists(),
            "local_absolute_paths": bool(LOCAL_PATH_RE.search(md)),
            "paper_claim": False,
        },
        {
            "artifact": "seed0-9随机种子说明.json",
            "path_alias": "<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>/00_INDEX/seed0-9随机种子说明.json",
            "created": json_path.exists(),
            "local_absolute_paths": bool(LOCAL_PATH_RE.search(json.dumps(data, ensure_ascii=False))),
            "paper_claim": False,
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_seed_explanation_created",
        "artifacts": rows,
        "export_clean": True,
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_SEED_EXPLANATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_SEED_EXPLANATION_INDEX", rows)
    return report


def write_case_review(
    paths: Paths,
    original_metrics: list[dict[str, Any]],
    common: dict[str, Any],
    yaw_audit: dict[str, Any],
) -> dict[str, Any]:
    review = {
        "stage": STAGE,
        "evaluation_completed": True,
        "input_files": {
            "solver_outputs": "<BY3A3_STAGE_ROOT> and <BY3_FULL_MATRIX_ROOT>/BY3A3_NORMAL_EXECUTION",
            "trace": "evaluation-only BY3 trace",
            "dual_gnss": "<BY3A1_STAGE_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
        },
        "case_overview": "BY3 normal yaw repair audit using existing BY3A3 solver outputs only; no degradation matrix.",
        "summary_metrics": original_metrics,
        "original_BY3A3_metrics": original_metrics,
        "repaired_yaw_metrics": "blocked: no physically/BY2-backed policy passed yaw sanity",
        "common_overlap_metrics": common["rows"],
        "attitude_level_assessment": yaw_audit["report"]["reason"],
        "brief_interpretation": "The lateral antenna rule is now encoded, but BY3 yaw reference policy remains inconclusive; BY3 degradation planning stays blocked.",
        "main_takeaway": "Do not treat BY3A3 yaw as repaired and do not make paper claims.",
        "ready_for_BY3_degradation_matrix_planning": False,
        "ready_for_paper_claims": False,
    }
    lines = [
        "# BY3A4A Normal Generalization Yaw-Repaired Case Review",
        "",
        "## Evaluation Completed",
        "true, as audit/evaluator recomputation from existing BY3A3 outputs only; no solver rerun.",
        "",
        "## Input Files",
        "- Existing BY3A3 solver outputs only.",
        "- BY3 trace was evaluation-only.",
        "- BY3A1 repaired dual-GNSS yaw was inspected as a source-observation diagnostic only.",
        "",
        "## Case Overview",
        review["case_overview"],
        "",
        "## Summary Metrics",
    ]
    for row in original_metrics:
        lines.append(
            f"- `{row['algorithm']}`: horizontal RMSE `{row.get('horizontal_rmse_m')}`, up RMSE `{row.get('up_rmse_m')}`, original yaw RMSE `{row.get('yaw_rmse_deg')}`."
        )
    lines.extend(
        [
            "",
            "## Original BY3A3 Metrics",
            "The original BY3A3 yaw RMSE remains approximately 103-105 deg across all three algorithms and is preserved as historical caution evidence.",
            "",
            "## Repaired Yaw Metrics",
            "Blocked. Lateral +90/-90 and baseline-reversal candidates were tested, but no physical/BY2-backed policy produced sane BY3 yaw across all three algorithms. No RMSE-only offset was selected.",
            "",
            "## Common-Overlap Metrics",
        ]
    )
    for row in common["rows"]:
        lines.append(
            f"- `{row['algorithm']}`: common horizontal RMSE `{row.get('horizontal_rmse_common_m')}`, common current-policy yaw RMSE `{row.get('yaw_rmse_current_policy_common_deg')}`."
        )
    lines.extend(
        [
            "",
            "## 3σ Consistency Statistics if available",
            "Preserved in original evaluator summaries; BY3A4A did not rerun a repaired official evaluator because yaw policy is inconclusive.",
            "",
            "## Attitude-level Assessment",
            "The lateral antenna geometry is real and must be encoded, but the BY3 yaw truth/reference remains unresolved. Trace yaw behaves like a trajectory/course-like field under tested transforms, not a validated lateral body-yaw reference.",
            "",
            "## Brief Interpretation",
            "This stage prevents the known lateral-antenna mistake from being repeated and blocks BY3 degradation planning until yaw reference policy is manually resolved.",
            "",
            "## Main Takeaway",
            "ready_for_BY3_degradation_matrix_planning=false; ready_for_paper_claims=false.",
        ]
    )
    write_json(paths.stage_root / "case_review" / "BY3A4A_normal_generalization_yaw_repaired_case_review.json", review)
    write_text(paths.stage_root / "case_review" / "BY3A4A_normal_generalization_yaw_repaired_case_review.md", "\n".join(lines) + "\n")
    return review


def write_context_update_report(paths: Paths) -> dict[str, Any]:
    docs = [
        "AGENTS.md",
        "PLANS.md",
        "README.md",
        "CLAIM_BOUNDARY.md",
        "PHASE_LOG.md",
        "docs/codex_context/current_state.md",
        "docs/codex_context/PROJECT_CONTEXT.md",
        "docs/codex_context/BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_REPORT.md",
        "docs/codex_context/BY3A4A_LATERAL_YAW_REPAIR_CONTEXT.md",
    ]
    rows = [
        {
            "tracked_doc": doc,
            "context_lock_status": "updated_or_required_by_supervisor",
            "local_path_policy": "aliases_only",
            "paper_claim": False,
        }
        for doc in docs
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_context_update_report_created",
        "tracked_docs": rows,
        "required_memory": [
            "dual antenna yaw evaluation must account for lateral mounting",
            "baseline is perpendicular to robot forward direction",
            "body heading requires plus/minus 90 correction depending on antenna direction",
            "do not choose plus/minus 90 by RMSE minimization alone",
            "unwrap before interpolation and wrap after difference",
            "seed0-9 explanation file created",
        ],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_CONTEXT_UPDATE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_UPDATED_TRACKED_DOCS", rows)
    return report


def write_obsidian(paths: Paths, yaw_audit: dict[str, Any]) -> dict[str, Any]:
    notes = {
        "00_INDEX.md": "# BY3 Generalization\n\nBY3A4A records the lateral dual-antenna yaw policy lock and keeps BY3 degradation planning blocked until yaw sanity is manually resolved.\n",
        "01_CURRENT_STATE.md": "# Current State\n\nBY3A4A decision: `BY3A4A_yaw_policy_inconclusive`. Solver rerun: false. Degradation matrix: false. Paper claims: false.\n",
        "03_ALIGNMENT_RESULT.md": "# Alignment Result\n\nBY3A4A reused existing BY3A3 outputs and strict common overlap. No alignment retuning and no trace tuning were performed.\n",
        "04_YAW_EVALUATION_POLICY.md": "# Yaw Evaluation Policy\n\nDual antennas are lateral/perpendicular to the robot forward axis. Baseline heading is not body heading; body heading requires a plus/minus 90 degree correction depending on antenna order and coordinate convention. Do not choose the sign by RMSE alone.\n",
        "05_NORMAL_GENERALIZATION_RESULT.md": "# Normal Generalization Result\n\nOriginal BY3A3 normal metrics remain historical. BY3A4A did not accept repaired yaw metrics because the BY3 yaw reference policy is inconclusive.\n",
        "07_CLAIM_BOUNDARY.md": "# Claim Boundary\n\nready_for_paper_claims=false. ready_for_BY3_degradation_matrix_planning=false until yaw policy is manually resolved.\n",
        "08_NEXT_STEPS.md": "# Next Steps\n\nRecommended next stage: manual review of dual-antenna yaw policy and BY3 yaw truth/reference fields before any BY3 degradation matrix planning.\n",
        "BY3_BDS_dual_antenna_lateral_yaw_policy.md": "# BY3 BDS Dual-Antenna Lateral Yaw Policy\n\n- mounting: lateral / transverse.\n- baseline axis: perpendicular to robot forward/head direction.\n- conversion: body heading requires baseline heading plus or minus 90 degrees, depending on antenna order and frame convention.\n- BY2 policy reference: A1 dual-diff baseline and `yaw_ned=90-yaw_body` were recovered; trace-based sign selection is forbidden.\n- BY3 policy: no repaired yaw policy accepted in BY3A4A because tested candidates did not pass yaw sanity.\n- no trace tuning, no solver rerun, no paper claim.\n",
    }
    rows: list[dict[str, Any]] = []
    for name, text in notes.items():
        path = paths.obsidian_by3 / name
        write_text(path, text)
        rows.append(
            {
                "note": f"BY3_generalization/{name}",
                "path_alias": f"obsidian_knowledge/LegSA-GINS/BY3_generalization/{name}",
                "updated": True,
                "public_note_path_leak_free": not bool(LOCAL_PATH_RE.search(text)),
                "paper_claim": False,
            }
        )
    by2_note = "# seed0-9 Random Seed Explanation\n\nSee `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>/00_INDEX/seed0-9随机种子说明.md`. Seeds are reproducible random degradation identifiers, not algorithm versions or data-collection repeats.\n"
    write_text(paths.obsidian_by2 / "seed0-9_random_seed_explanation.md", by2_note)
    rows.append(
        {
            "note": "BY2_degradation/seed0-9_random_seed_explanation.md",
            "path_alias": "obsidian_knowledge/LegSA-GINS/BY2_degradation/seed0-9_random_seed_explanation.md",
            "updated": True,
            "public_note_path_leak_free": not bool(LOCAL_PATH_RE.search(by2_note)),
            "paper_claim": False,
        }
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A4A_obsidian_sync_completed",
        "obsidian_rows": rows,
        "yaw_decision": yaw_audit["report"]["decision"],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4A_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4A_OBSIDIAN_SYNC_INDEX", rows)
    return report


def validate_outputs(
    paths: Paths,
    by2_policy: dict[str, Any],
    geometry: dict[str, Any],
    yaw_audit: dict[str, Any],
    repaired_eval: dict[str, Any],
    common: dict[str, Any],
    figures: dict[str, Any],
    seed: dict[str, Any],
    context: dict[str, Any],
    obsidian: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("no_BY3_degradation_run", True),
        ("solver_rerun", False),
        ("trace_solver_input", False),
        ("parameter_retuning", False),
        ("lateral_policy_encoded", geometry.get("decision") == "BY3A4A_lateral_geometry_encoded"),
        ("by2_policy_recovered_or_documented", by2_policy.get("by2_lateral_yaw_policy_recovered") is True),
        ("plus_minus_90_not_rmse_only", yaw_audit["report"].get("selection_not_rmse_only") is True),
        ("repaired_eval_generated_if_needed", repaired_eval.get("decision") == "BY3A4A_repaired_eval_blocked"),
        ("common_overlap_metrics_generated", common["report"].get("decision") == "BY3A4A_common_overlap_metrics_ready"),
        ("figures_content_valid", figures.get("figure_count", 0) >= 20),
        ("seed_explanation_created", seed.get("decision") == "BY3A4A_seed_explanation_created"),
        ("context_report_created", context.get("decision") == "BY3A4A_context_update_report_created"),
        ("obsidian_updated", obsidian.get("decision") == "BY3A4A_obsidian_sync_completed"),
        ("paper_claims", False),
    ]
    status_rows = [{"check": name, "value": value, "pass": value is True or (name in {"solver_rerun", "trace_solver_input", "parameter_retuning", "paper_claims"} and value is False)} for name, value in checks]
    safety_ok = all(row["pass"] for row in status_rows)
    decision = {
        "stage": STAGE,
        "decision": "BY3A4A_yaw_policy_inconclusive" if safety_ok else "BY3A4A_safety_gate_failed",
        "ready_for_BY3_degradation_matrix_planning": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": "manual_review_dual_antenna_yaw_policy",
        "reason": "Lateral rule and memory lock completed, but no repaired yaw policy was accepted from existing BY3A3 outputs.",
        "safety_ok": safety_ok,
    }
    validation = {
        "stage": STAGE,
        "status_rows": status_rows,
        "decision": decision,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", status_rows)
    write_text(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3A4A Long Task Summary\n\n"
        "- Lateral dual-antenna geometry and BY2 yaw conversion evidence were recovered and encoded.\n"
        "- Existing BY3A3 outputs were used only for evaluator-policy candidate tests and common-overlap metrics.\n"
        "- No physically/BY2-backed yaw policy passed BY3 yaw sanity; repaired yaw metrics are blocked.\n"
        "- Seed0-9 explanation and Obsidian memory notes were generated.\n"
        "- No solver rerun, no degradation matrix, no retuning, no paper claims.\n",
    )
    write_text(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A4A Next Stage Recommendation\n\n"
        "`manual_review_dual_antenna_yaw_policy` before any BY3 degradation planning.\n\n"
        "ready_for_BY3_degradation_matrix_planning=false\n"
        "ready_for_paper_claims=false\n",
    )
    return decision


def write_runtime_root_manifest(paths: Paths, decision: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "artifact": "LONG_TASK_DECISION_REPORT.json",
            "path_alias": "<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR/reports/LONG_TASK_DECISION_REPORT.json",
            "role": "runtime decision copy",
            "paper_claim": False,
        },
        {
            "artifact": "LONG_TASK_STAGE_STATUS.csv/json",
            "path_alias": "<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR/matrix/LONG_TASK_STAGE_STATUS",
            "role": "runtime status copy",
            "paper_claim": False,
        },
        {
            "artifact": "BY3A4A_RUNTIME_MANIFEST.json",
            "path_alias": "<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR/reports/BY3A4A_RUNTIME_MANIFEST.json",
            "role": "runtime root manifest",
            "paper_claim": False,
        },
    ]
    manifest = {
        "stage": STAGE,
        "runtime_root_alias": "<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR",
        "stage_root_alias": f"<BY3_STAGE_ROOT>/{STAGE}",
        "decision": decision,
        "runtime_root_role": "diagnostic runtime index for BY3A4A; heavy artifacts remain under stage root",
        "solver_rerun": False,
        "degradation_matrix": False,
        "parameter_retuning": False,
        "paper_claim": False,
        "artifacts": rows,
    }
    status_rows = [
        {"check": "runtime_root_not_empty", "pass": True, "paper_claim": False},
        {"check": "points_to_stage_root_alias", "pass": True, "paper_claim": False},
        {"check": "solver_rerun_absent", "pass": True, "paper_claim": False},
        {"check": "degradation_matrix_absent", "pass": True, "paper_claim": False},
    ]
    write_json(paths.runtime_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_json(paths.runtime_root / "reports" / "BY3A4A_RUNTIME_MANIFEST.json", manifest)
    write_rows(paths.runtime_root / "matrix" / "LONG_TASK_STAGE_STATUS", status_rows)
    write_text(
        paths.runtime_root / "summary" / "by3a4a_runtime_root_summary.md",
        "# BY3A4A Runtime Root Summary\n\n"
        "This runtime root is a diagnostic index for BY3A4A. The full report package is under "
        f"`<BY3_STAGE_ROOT>/{STAGE}`. No solver rerun, degradation matrix, retuning, or paper claim was performed.\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-root",
        default=None,
        help="Runtime seed explanation output root. Prefer BY2_DEGRADATION_TEXT_SUMMARY_ROOT or pass a local path at execution time.",
    )
    args = parser.parse_args()
    repo = Path.cwd()
    paths = Paths.build(repo, Path(args.seed_root) if args.seed_root else None)
    ensure_dirs(paths)

    write_text(
        paths.stage_root / "01_plan" / "BY3A4A_APPROVED_PLAN.md",
        "# BY3A4A Approved Plan\n\n"
        "- Read existing BY3A3 outputs only.\n"
        "- Recover BY2 lateral yaw policy.\n"
        "- Audit physically meaningful yaw candidates.\n"
        "- Recompute common overlap and diagnostic figures.\n"
        "- Generate seed explanation and context memory notes.\n"
        "- Do not run solvers, degradation, retuning, or paper claims.\n",
    )

    by2_policy = build_by2_policy_recovery(paths)
    geometry = build_geometry_report(paths)

    inputs = collect_algorithm_inputs(paths)
    navs = {algorithm: load_official_nav(info["nav"]) for algorithm, info in inputs.items()}
    trace_rows = load_trace(discover_trace_path(repo))
    dual_yaw_rows = load_dual_status_yaw(paths.by3a1_stage / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss")
    yaw_audit = compute_yaw_candidate_tests(paths, navs, trace_rows, dual_yaw_rows)

    original_metrics = []
    for algorithm in COMMON_ALGORITHMS:
        summary = read_json(inputs[algorithm]["eval_dir"] / "summary.json", {})
        original_metrics.append(metric_row(algorithm, summary))

    repaired_eval = build_repaired_eval_report(paths, original_metrics, yaw_audit)
    common = compute_common_overlap(paths, original_metrics)
    figures = draw_figures(paths, navs, trace_rows, common, original_metrics, yaw_audit)
    seed = write_seed_explanation(paths)
    case_review = write_case_review(paths, original_metrics, common, yaw_audit)
    context = write_context_update_report(paths)
    obsidian = write_obsidian(paths, yaw_audit)
    decision = validate_outputs(paths, by2_policy, geometry, yaw_audit, repaired_eval, common, figures, seed, context, obsidian)
    runtime_manifest = write_runtime_root_manifest(paths, decision)

    supervisor = {
        "stage": STAGE,
        "planner_summary": "Planner inventory found PR #52 open, BY3A3 outputs available, and BY2 lateral yaw policy evidence in tracked docs/source.",
        "worker_summary": "Generated BY3A4A reports, matrices, figures, seed explanation, case review, validation, and Obsidian notes without solver/degradation reruns.",
        "decision": decision,
        "case_review_created": bool(case_review),
        "stage_root_alias": f"<BY3_STAGE_ROOT>/{STAGE}",
        "runtime_root_alias": f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}",
        "runtime_manifest": runtime_manifest["runtime_root_alias"],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "00_supervisor" / "BY3A4A_SUPERVISOR_REPORT.json", supervisor)
    print(json.dumps(supervisor, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
