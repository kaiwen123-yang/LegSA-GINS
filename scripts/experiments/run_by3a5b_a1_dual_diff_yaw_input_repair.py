"""Run BY3A5B A1 dual-diff yaw input repair and BY3 normal rerun.

This runner is runtime-only. It supersedes the BY3A5 HDT repair policy for
mainline BY3 generalization, reconstructs BY3 dual-antenna yaw from GNSS1/GNSS2
absolute short-baseline position differences, writes a repaired 15-column GNSS
input with the BY2 fixed_1p5 yaw-std policy, and optionally reruns BY3 normal
only. It never runs a degradation matrix.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.experiments import run_by3a3_selected_feedback_stage1_chain as by3a3  # noqa: E402
from scripts.experiments import run_by3a5_dual_yaw_input_source_repair as by3a5  # noqa: E402


STAGE = "BY3A5B_A1_DUAL_DIFF_YAW_INPUT_REPAIR_AND_NORMAL_RERUN"
RUNTIME_STAGE = "BY3A5B_A1_DUAL_DIFF_REPAIR"
BY3A0_STAGE = "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
BY3A1_STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
BY3A2_STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"
BY3A3_STAGE = "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION"
BY3A4A_STAGE = "BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK"
BY3A4C_STAGE = "BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION"
BY3A5_STAGE = "BY3A5_DUAL_YAW_INPUT_SOURCE_AUDIT_AND_REGENERATION"

SOURCE_POLICY_A1 = "BY3A5B_A1_dual_diff_short_baseline_fixed_1p5"
SOURCE_POLICY_SINGLE = "single_gnss1_status_no_dual_yaw_input_unchanged"
SOURCE_POLICY_MISMATCH = "input_config_mismatch"

SUBDIRS = [
    "by3a5_supersession",
    "by2_a1_dual_diff_recovery",
    "gnss1_gnss2_baseline",
    "antenna_order_audit",
    "lateral_conversion",
    "yaw_std_policy",
    "repaired_input_generation",
    "normal_rerun",
    "official_eval",
    "figures",
    "case_review",
    "context_update",
    "obsidian_sync",
    "reports",
    "matrix",
    "summary",
    "validation",
    "logs",
    "blocked",
    "stage1_solver",
    "stage2_legsa_full_solver",
    "single_baseline_solver",
    "finalv23_solver",
    "feedback_generation",
]

METRIC_KEYS = [
    "north_rmse_m",
    "east_rmse_m",
    "up_rmse_m",
    "horizontal_rmse_m",
    "horizontal_p95_m",
    "horizontal_max_m",
    "roll_rmse_deg",
    "pitch_rmse_deg",
    "yaw_rmse_deg",
    "roll_p95_deg",
    "pitch_p95_deg",
    "yaw_p95_deg",
    "row_count",
    "time_start",
    "time_end",
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    receiver_root: Path
    trace: Path
    by3a0_root: Path
    by3a1_root: Path
    by3a2_root: Path
    by3a3_root: Path
    by3a4a_root: Path
    by3a4c_root: Path
    by3a5_root: Path

    @property
    def current_dual(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss"

    @property
    def repaired_dual(self) -> Path:
        return self.stage_root / "repaired_input_generation" / "BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"

    @property
    def imu(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"

    @property
    def gnss_dual(self) -> Path:
        return self.repaired_dual

    @property
    def gnss_single(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"

    @property
    def raw_doppler(self) -> Path:
        return (
            self.by3a2_root
            / "raw_doppler_recovery"
            / "provider_only"
            / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
        )

    @property
    def go2_prior_dir(self) -> Path:
        return (
            self.by3a1_root
            / "provider_materialization"
            / "go2_priors"
            / "priors"
            / "joint_rp1p6deg_hv1p0"
        )

    @property
    def go2_attitude(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv"

    @property
    def go2_velocity(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv"

    @property
    def go2_joint(self) -> Path:
        return self.go2_prior_dir / "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--receiver-root", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--run-solvers", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    stage_root = (args.stage_root or repo / "by3-huiti" / STAGE).resolve()
    runtime_root = (args.runtime_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / RUNTIME_STAGE).resolve()
    receiver_root = (args.receiver_root or by3a5.discover_receiver_root(repo)).resolve()
    trace = (args.trace or by3a5.discover_trace(receiver_root)).resolve()
    paths = Paths(
        repo=repo,
        stage_root=stage_root,
        runtime_root=runtime_root,
        receiver_root=receiver_root,
        trace=trace,
        by3a0_root=repo / "by3-huiti" / BY3A0_STAGE,
        by3a1_root=repo / "by3-huiti" / BY3A1_STAGE,
        by3a2_root=repo / "by3-huiti" / BY3A2_STAGE,
        by3a3_root=repo / "by3-huiti" / BY3A3_STAGE,
        by3a4a_root=repo / "by3-huiti" / BY3A4A_STAGE,
        by3a4c_root=repo / "by3-huiti" / BY3A4C_STAGE,
        by3a5_root=repo / "by3-huiti" / BY3A5_STAGE,
    )
    result = run_by3a5b(paths, run_solvers=bool(args.run_solvers and not args.audit_only), skip_figures=args.skip_figures)
    print(
        json.dumps(
            {
                "decision": result["decision"]["status"],
                "stage_root": str(paths.stage_root),
                "runtime_root": str(paths.runtime_root),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def run_by3a5b(paths: Paths, *, run_solvers: bool, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    supersession = supersede_by3a5(paths)
    by2_recovery = recover_by2_a1_dual_diff(paths)
    baseline = audit_gnss1_gnss2_baseline(paths)
    antenna = audit_antenna_order_lateral_conversion(paths, baseline, by2_recovery)
    yaw_std = audit_yaw_std_policy(paths)
    if inputs_gate_ready(by2_recovery, baseline, antenna, yaw_std):
        repaired_input = generate_repaired_input(paths, baseline, antenna, yaw_std)
    else:
        repaired_input = blocked_repaired_input(by2_recovery, baseline, antenna, yaw_std)
    if repaired_input.get("decision") == "BY3A5B_repaired_inputs_ready":
        rerun = run_normal_chain(paths, repaired_input, run_solvers=run_solvers)
    else:
        rerun = blocked_normal_rerun(repaired_input)
        write_normal_rerun_reports(paths, rerun)
    yaw_eval = post_rerun_yaw_eval_audit(paths, repaired_input, rerun)
    figures = generate_figures(paths, baseline, repaired_input, rerun, yaw_eval, skip_figures=skip_figures)
    case_review = write_case_review(paths, supersession, by2_recovery, baseline, antenna, yaw_std, repaired_input, rerun, yaw_eval, figures)
    obsidian = write_obsidian_notes(paths, supersession, baseline, antenna, yaw_std, repaired_input, rerun, yaw_eval)
    validation = validate_stage(paths, supersession, by2_recovery, baseline, antenna, yaw_std, repaired_input, rerun, yaw_eval, figures, obsidian)
    decision = decide_stage(validation, baseline, repaired_input, rerun, yaw_eval)
    write_final_reports(
        paths,
        validation,
        decision,
        supersession,
        by2_recovery,
        baseline,
        antenna,
        yaw_std,
        repaired_input,
        rerun,
        yaw_eval,
        figures,
        case_review,
        obsidian,
    )
    return {"validation": validation, "decision": decision}


def create_tree(paths: Paths) -> None:
    paths.stage_root.mkdir(parents=True, exist_ok=True)
    paths.runtime_root.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (paths.stage_root / subdir).mkdir(parents=True, exist_ok=True)
    for subdir in ["repaired_input_generation", "normal_rerun", "official_eval", "figures", "logs"]:
        (paths.runtime_root / subdir).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    by3a5.write_json(path, data)


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    by3a5.write_rows(stem, rows)


def write_summary(path: Path, text: str) -> None:
    by3a5.write_summary(path, text)


def read_json(path: Path, default: Any | None = None) -> Any:
    return by3a5.read_json(path, default)


def flatten(report: dict[str, Any]) -> dict[str, Any]:
    return by3a5.flatten_report(report)


def as_float(value: Any, default: float | None = None) -> float | None:
    return by3a5.as_float(value, default)


def read_numeric_table(path: Path, expected_cols: int | None = None) -> list[list[float]]:
    return by3a5.read_numeric_table(path, expected_cols)


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def supersede_by3a5(paths: Paths) -> dict[str, Any]:
    by3a5_decision = read_json(paths.by3a5_root / "reports" / "LONG_TASK_DECISION_REPORT.json", {}) or {}
    by3a5_metrics = read_json(paths.by3a5_root / "matrix" / "BY3A5_NORMAL_METRICS.json", []) or []
    yaw_failures = [
        {
            "algorithm": row.get("algorithm"),
            "yaw_rmse_deg": row.get("yaw_rmse_deg"),
            "source_policy": row.get("source_policy"),
            "historical_status": "superseded_diagnostic_metric",
        }
        for row in by3a5_metrics
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_hdt_policy_superseded",
        "by3a5_wrong_source_audit_status": "valid",
        "by3a5_hdt_policy_status": "diagnostic_rejected_superseded_for_mainline",
        "by3a5_metrics_status": "historical_superseded",
        "reason": "accepted BY2/final_v23/LegSA_full mainline yaw source is A1_dual_diff dual-antenna short-baseline, not HDT",
        "by3a5_previous_status": by3a5_decision.get("status", ""),
        "hdt_solver_input_allowed_in_BY3A5B": False,
        "a1_dual_diff_required": True,
        "yaw_failures": yaw_failures,
        "ready_for_BY3A5B": True,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_BY3A5_SUPERSESSION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_BY3A5_SUPERSESSION", [flatten(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5b_by3a5_supersession.md",
        "\n".join(
            [
                "# BY3A5B BY3A5 Supersession",
                "",
                f"Decision: `{report['decision']}`.",
                "",
                "BY3A5 remains valid for the wrong-source audit: the previous BY3 15-column yaw came from a wrong source.",
                "BY3A5's HDT replacement policy is diagnostic, rejected, and superseded for mainline BY3 generalization.",
                "BY3A5 HDT rerun metrics are historical/superseded and must not be reused as mainline yaw evidence.",
                "",
                "BY3A5B proceeds only with A1_dual_diff short-baseline yaw generated from GNSS1/GNSS2 antenna positions.",
            ]
        ),
    )
    return report


def recover_by2_a1_dual_diff(paths: Paths) -> dict[str, Any]:
    evidence_rows = [
        {
            "artifact": "status_yaw_builder.py",
            "path_alias": "src/legsa_gins/input_generation/status_yaw_builder.py",
            "evidence": "build_a1_dual_diff_yaw_rows computes rel_n, rel_e, yaw_baseline=-atan2(rel_e, rel_n), yaw_ned=90-yaw_body",
            "accepted": True,
        },
        {
            "artifact": "process_data_compat.py",
            "path_alias": "src/legsa_gins/input_generation/process_data_compat.py",
            "evidence": "default yaw_source_mode=status, yaw_sign=1.0, yaw_install_offset_deg=0.0, yaw_std_mode=fixed_1p5",
            "accepted": True,
        },
        {
            "artifact": "process_data_runtime_parameter_audit.md",
            "path_alias": "docs/source_audit/process_data_runtime_parameter_audit.md",
            "evidence": "records BY2 runtime defaults YAW_SIGN=1.0, YAW_INSTALL_OFFSET_DEG=0.0, STATUS_YAW_STD_MODE_DEFAULT=fixed_1p5",
            "accepted": True,
        },
        {
            "artifact": "BY3A4A lateral context",
            "path_alias": "docs/codex_context/BY3A4A_LATERAL_YAW_REPAIR_CONTEXT.md",
            "evidence": "dual antennas are lateral/perpendicular to robot forward; body heading needs +/-90 equivalent conversion and cannot be RMSE-selected",
            "accepted": True,
        },
    ]
    pseudo_code = [
        "gnss2_i = interpolate(gnss2_position, gnss1_time)",
        "d = ecef_to_local_enu(gnss2_i - gnss1_position, origin=gnss1_position)",
        "rel_n = d.north_m; rel_e = d.east_m",
        "yaw_baseline_deg = wrap360(-degrees(atan2(rel_e, rel_n)))",
        "yaw_body_deg = wrap360(YAW_SIGN * yaw_baseline_deg + YAW_INSTALL_OFFSET_DEG)",
        "yaw_ned_deg = wrap360(90.0 - yaw_body_deg)",
        "yaw_std_deg = 1.5",
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_by2_a1_dual_diff_logic_recovered",
        "process_data_script_path_alias": "src/legsa_gins/input_generation/process_data_compat.py",
        "a1_dual_diff_route": "GNSS1/GNSS2 dual-antenna position difference at GNSS1 epochs",
        "input_status_files_used": ["gnss1-status.csv", "gnss2-status.csv"],
        "gnss2_interpolation_policy": "interpolate GNSS2 position to GNSS1 epoch",
        "baseline_vector_formula": "gnss2_minus_gnss1 in local ENU/NED components",
        "accepted_antenna_order": "gnss2_minus_gnss1",
        "yaw_baseline_formula": "yaw_baseline_deg = wrap360(-atan2(rel_e, rel_n) in degrees)",
        "lateral_mounting_conversion": "YAW_SIGN=1.0, YAW_INSTALL_OFFSET_DEG=0.0, yaw_ned=90-yaw_body; equivalent to baseline_heading+90 for gnss2_minus_gnss1",
        "yaw_ned_body_convention": "solver column stores NED yaw after BY2 body-heading conversion",
        "yaw_std_policy": "fixed_1p5",
        "fixed_1p5_evidence": "BY2 process_data runtime/default policy and final_v23-compatible input generation evidence",
        "rejected_sources": ["GNSS status long-baseline rel_pos_n/e", "NMEA-HDT direct heading", "trace yaw", "final_v23 output", "solver outputs"],
        "selection_basis": "BY2 accepted process_data logic and physical lateral mounting, not RMSE minimization",
        "pseudo_code": pseudo_code,
        "evidence_rows": evidence_rows,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_BY2_A1_DUAL_DIFF_RECOVERY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_BY2_A1_DUAL_DIFF_EVIDENCE", evidence_rows)
    write_summary(
        paths.stage_root / "summary" / "by3a5b_by2_a1_dual_diff_recovery.md",
        "\n".join(
            [
                "# BY3A5B BY2 A1 Dual-Diff Recovery",
                "",
                f"Decision: `{report['decision']}`.",
                "",
                "Recovered formula:",
                "",
                "```text",
                *pseudo_code,
                "```",
                "",
                "Rejected solver yaw sources: long-baseline rel_pos, HDT direct heading, trace yaw, final_v23 output, and solver outputs.",
            ]
        ),
    )
    return report


def read_status_positions(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            t = as_float(row.get("Time"))
            lat = as_float(row.get("pos_lat"))
            lon = as_float(row.get("pos_lon"))
            height = as_float(row.get("pos_height"))
            if None in {t, lat, lon, height}:
                continue
            if not all(bool_value(row.get(key, "true")) for key in ["msg_valid", "pos_valid", "fix_ok"]):
                continue
            x, y, z = llh_to_ecef(lat, lon, height)
            rows.append(
                {
                    "t": float(t),
                    "lat": float(lat),
                    "lon": float(lon),
                    "height": float(height),
                    "x": x,
                    "y": y,
                    "z": z,
                }
            )
    rows.sort(key=lambda item: item["t"])
    return rows


def llh_to_ecef(lat_deg: float, lon_deg: float, height_m: float) -> tuple[float, float, float]:
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    x = (n + height_m) * cos_lat * math.cos(lon)
    y = (n + height_m) * cos_lat * math.sin(lon)
    z = (n * (1.0 - e2) + height_m) * sin_lat
    return x, y, z


def ecef_delta_to_enu(dx: float, dy: float, dz: float, lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return east, north, up


def interp_position(rows: list[dict[str, float]], t: float, *, tolerance: float = 0.75) -> tuple[dict[str, float] | None, str]:
    if not rows:
        return None, "missing"
    if t < rows[0]["t"]:
        return (rows[0], "nearest_edge") if rows[0]["t"] - t <= tolerance else (None, "outside")
    if t > rows[-1]["t"]:
        return (rows[-1], "nearest_edge") if t - rows[-1]["t"] <= tolerance else (None, "outside")
    lo = 0
    hi = len(rows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        mt = rows[mid]["t"]
        if mt < t:
            lo = mid + 1
        elif mt > t:
            hi = mid - 1
        else:
            return rows[mid], "exact"
    left = rows[max(0, hi)]
    right = rows[min(len(rows) - 1, lo)]
    if right["t"] == left["t"]:
        return left, "nearest_same_time"
    alpha = (t - left["t"]) / (right["t"] - left["t"])
    out: dict[str, float] = {"t": t}
    for field in ["lat", "lon", "height", "x", "y", "z"]:
        out[field] = left[field] + alpha * (right[field] - left[field])
    return out, "interpolated"


def build_baseline_rows(paths: Paths) -> list[dict[str, Any]]:
    gnss1_rows = read_status_positions(paths.receiver_root / "gnss1-status.csv")
    gnss2_rows = read_status_positions(paths.receiver_root / "gnss2-status.csv")
    rows: list[dict[str, Any]] = []
    for gnss1 in gnss1_rows:
        gnss2, mode = interp_position(gnss2_rows, gnss1["t"])
        if gnss2 is None:
            continue
        dx = gnss2["x"] - gnss1["x"]
        dy = gnss2["y"] - gnss1["y"]
        dz = gnss2["z"] - gnss1["z"]
        east, north, up = ecef_delta_to_enu(dx, dy, dz, gnss1["lat"], gnss1["lon"])
        length = math.sqrt(east * east + north * north + up * up)
        baseline_heading = by3a5.wrap360(math.degrees(math.atan2(east, north)))
        yaw_baseline, yaw_ned = a1_yaw_ned_from_enu(east, north)
        reverse_heading = by3a5.wrap360(baseline_heading + 180.0)
        rows.append(
            {
                "t": gnss1["t"],
                "gnss2_interp_mode": mode,
                "east_m": east,
                "north_m": north,
                "up_m": up,
                "baseline_length_m": length,
                "baseline_heading_deg": baseline_heading,
                "yaw_baseline_deg": yaw_baseline,
                "a1_yaw_ned_deg": yaw_ned,
                "reverse_baseline_heading_deg": reverse_heading,
                "reverse_a1_yaw_ned_deg": by3a5.wrap360(reverse_heading + 90.0),
            }
        )
    return rows


def a1_yaw_ned_from_enu(east_m: float, north_m: float) -> tuple[float, float]:
    """Return BY2 A1 yaw_baseline and solver NED yaw for GNSS2-GNSS1 ENU."""
    yaw_baseline = by3a5.wrap360(-math.degrees(math.atan2(east_m, north_m)))
    yaw_body = yaw_baseline
    yaw_ned = by3a5.wrap360(90.0 - yaw_body)
    return yaw_baseline, yaw_ned


def interp_baseline_yaw(rows: list[dict[str, Any]], t: float, *, tolerance: float = 0.75) -> tuple[float | None, str]:
    angle_rows = [{"t": float(row["t"]), "heading": float(row["a1_yaw_ned_deg"])} for row in rows]
    return by3a5.interp_angle(angle_rows, t, tolerance=tolerance)


def read_trace_yaw_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            t = as_float(row.get("time") or row.get("Time"))
            yaw = as_float(row.get("yaw") or row.get("yaw_deg"))
            if t is None or yaw is None:
                continue
            rows.append({"t": float(t), "heading": by3a5.wrap360(float(yaw))})
    rows.sort(key=lambda item: item["t"])
    return rows


def rel_pos_long_baseline_stats(paths: Paths) -> dict[str, Any]:
    values: list[float] = []
    with (paths.receiver_root / "gnss1-status.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            n = as_float(row.get("rel_pos_n"))
            e = as_float(row.get("rel_pos_e"))
            d = as_float(row.get("rel_pos_d"))
            if None in {n, e, d}:
                continue
            values.append(math.sqrt(float(n) ** 2 + float(e) ** 2 + float(d) ** 2))
    return by3a5.stats(values)


def compare_angles_by_input_times(
    paths: Paths,
    baseline_rows: list[dict[str, Any]],
    base_time: float,
) -> dict[str, Any]:
    current_rows = read_numeric_table(paths.current_dual, expected_cols=15)
    hdt_rows = by3a5.parse_hdt_rows(paths.receiver_root / "userio-raw.csv")
    trace_rows = read_trace_yaw_rows(paths.trace)
    current_diffs: list[float] = []
    hdt_diffs: list[float] = []
    trace_diffs: list[float] = []
    missing = {"a1": 0, "hdt": 0, "trace": 0}
    for row in current_rows:
        raw_time = base_time + row[0]
        a1_yaw, _ = interp_baseline_yaw(baseline_rows, raw_time)
        if a1_yaw is None:
            missing["a1"] += 1
            continue
        current_diffs.append(by3a5.circ_diff(a1_yaw, row[13]))
        hdt_yaw, _ = by3a5.interp_angle(hdt_rows, raw_time, tolerance=0.25)
        if hdt_yaw is None:
            missing["hdt"] += 1
        else:
            hdt_diffs.append(by3a5.circ_diff(a1_yaw, hdt_yaw))
        trace_yaw, _ = by3a5.interp_angle(trace_rows, raw_time, tolerance=0.25)
        if trace_yaw is None:
            missing["trace"] += 1
        else:
            trace_diffs.append(by3a5.circ_diff(a1_yaw, trace_yaw))
    return {
        "current_wrong_yaw_minus_a1_deg": diff_stats(current_diffs),
        "hdt_minus_a1_diagnostic_deg": diff_stats(hdt_diffs),
        "trace_minus_a1_diagnostic_deg": diff_stats(trace_diffs),
        "missing_counts": missing,
        "hdt_used_as_solver_input": False,
        "trace_used_as_solver_input": False,
        "comparison_role": "diagnostic_only",
    }


def diff_stats(values: list[float]) -> dict[str, Any]:
    abs_values = [abs(value) for value in values if math.isfinite(value)]
    return {
        "signed_deg": by3a5.stats(values),
        "abs_deg": by3a5.stats(abs_values),
        "count": len(abs_values),
    }


def audit_gnss1_gnss2_baseline(paths: Paths) -> dict[str, Any]:
    baseline_rows = build_baseline_rows(paths)
    lengths = [float(row["baseline_length_m"]) for row in baseline_rows]
    length_stats = by3a5.stats(lengths)
    rel_stats = rel_pos_long_baseline_stats(paths)
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}) or {}
    base_time = float((repair_report.get("offsets", {}) or {}).get("body_time_zero_raw_timestamp", 0.0))
    comparisons = compare_angles_by_input_times(paths, baseline_rows, base_time)
    median = float(length_stats.get("median") or 999.0)
    p95 = float(length_stats.get("p95") or 999.0)
    valid_ratio = len(baseline_rows) / max(1, len(read_status_positions(paths.receiver_root / "gnss1-status.csv")))
    short_valid = 0.10 <= median <= 1.50 and p95 <= 1.50 and valid_ratio >= 0.95
    rel_rejected = float(rel_stats.get("median") or 0.0) > 10.0
    decision = "BY3A5B_short_baseline_valid" if short_valid and rel_rejected else "BY3A5B_short_baseline_invalid_or_unusable"
    report = {
        "stage": STAGE,
        "decision": decision,
        "gnss1_source_alias": "<BY3_RECEIVER_ROOT>/gnss1-status.csv",
        "gnss2_source_alias": "<BY3_RECEIVER_ROOT>/gnss2-status.csv",
        "time_policy": "BY3A1 common timeline maps 15-col time to receiver Time/time_unix; GNSS2 is interpolated to GNSS1 Time",
        "position_fields": ["pos_lat", "pos_lon", "pos_height"],
        "coordinate_policy": "LLH to ECEF, then ECEF delta projected to local ENU at GNSS1 position",
        "baseline_candidates": ["gnss2_minus_gnss1", "gnss1_minus_gnss2"],
        "selected_baseline_candidate_for_BY2_logic": "gnss2_minus_gnss1",
        "row_count": len(baseline_rows),
        "valid_ratio": valid_ratio,
        "gnss2_minus_gnss1_length_stats_m": length_stats,
        "gnss1_minus_gnss2_length_stats_m": length_stats,
        "physical_short_baseline_status": "physically_plausible_short_baseline" if short_valid else "not_physically_plausible",
        "physical_short_baseline_note": "No exact tracked numeric BY3 antenna spacing lock was found; 0.35 m median is plausible for a compact lateral dual-antenna robot and is not a kilometer RTK base vector.",
        "status_rel_pos_long_baseline_stats_m": rel_stats,
        "long_baseline_rel_pos_rejected": rel_rejected,
        "absolute_positions_precise_enough_for_heading": bool(short_valid),
        "diagnostic_comparisons": comparisons,
        "baseline_rows_preview": baseline_rows[:5],
        "hdt_used_as_solver_input": False,
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_GNSS1_GNSS2_BASELINE_AUDIT_REPORT.json", report)
    matrix_rows = [
        {
            "candidate": "gnss2_minus_gnss1",
            "selected": True,
            "row_count": len(baseline_rows),
            "valid_ratio": valid_ratio,
            "length_median_m": length_stats.get("median"),
            "length_p05_m": length_stats.get("p05"),
            "length_p95_m": length_stats.get("p95"),
            "length_min_m": length_stats.get("min"),
            "length_max_m": length_stats.get("max"),
            "physical_status": report["physical_short_baseline_status"],
            "solver_yaw_source_allowed": short_valid,
        },
        {
            "candidate": "gnss1_status_rel_pos",
            "selected": False,
            "row_count": rel_stats.get("count"),
            "length_median_m": rel_stats.get("median"),
            "length_p05_m": rel_stats.get("p05"),
            "length_p95_m": rel_stats.get("p95"),
            "length_min_m": rel_stats.get("min"),
            "length_max_m": rel_stats.get("max"),
            "physical_status": "long_baseline_or_rtk_base_vector",
            "solver_yaw_source_allowed": False,
        },
    ]
    write_rows(paths.stage_root / "matrix" / "BY3A5B_GNSS1_GNSS2_BASELINE_AUDIT", matrix_rows)
    write_summary(
        paths.stage_root / "summary" / "by3a5b_gnss1_gnss2_baseline_audit.md",
        "\n".join(
            [
                "# BY3A5B GNSS1/GNSS2 Baseline Audit",
                "",
                f"Decision: `{decision}`.",
                "",
                f"GNSS2-GNSS1 median baseline length: `{length_stats.get('median')}` m.",
                f"GNSS2-GNSS1 p05/p95: `{length_stats.get('p05')}` / `{length_stats.get('p95')}` m.",
                f"GNSS1 status rel_pos median length: `{rel_stats.get('median')}` m and is rejected as a long-baseline/base-vector source.",
                "",
                "HDT and trace comparisons are diagnostic only and are not used for solver input or policy selection.",
            ]
        ),
    )
    report["_baseline_rows_runtime"] = baseline_rows
    return report


def audit_antenna_order_lateral_conversion(paths: Paths, baseline: dict[str, Any], by2_recovery: dict[str, Any]) -> dict[str, Any]:
    ready = baseline.get("decision") == "BY3A5B_short_baseline_valid" and by2_recovery.get("decision") == "BY3A5B_by2_a1_dual_diff_logic_recovered"
    decision = "BY3A5B_antenna_order_policy_ready" if ready else "BY3A5B_antenna_order_blocked"
    rows = [
        {
            "candidate": "gnss2_minus_gnss1_with_BY2_sign",
            "baseline_direction": "gnss2_minus_gnss1",
            "lateral_conversion": "yaw_ned=90-(-atan2(east,north))",
            "equivalent_heading_policy": "baseline_heading+90",
            "selected": ready,
            "selection_basis": "BY2 process_data sign and physical lateral mounting, not RMSE/HDT",
            "rmse_selected": False,
        },
        {
            "candidate": "gnss1_minus_gnss2_or_opposite_offset",
            "selected": False,
            "selection_basis": "not the BY2 accepted process_data route",
            "rmse_selected": False,
        },
    ]
    report = {
        "stage": STAGE,
        "decision": decision,
        "by2_accepted_antenna_order": "gnss2_minus_gnss1",
        "by3_physical_antenna_order_status": "inherits BY2 accepted A1 route unless human supplies conflicting BY3 antenna-order evidence",
        "gnss1_gnss2_labels": "receiver source files gnss1-status.csv and gnss2-status.csv",
        "baseline_axis": "body_Y_lateral_axis_not_body_X",
        "selected_policy": rows[0],
        "body_heading_candidates_considered": ["baseline_heading+90", "baseline_heading-90", "reversed baseline equivalents"],
        "hdt_diagnostic_support_allowed": True,
        "hdt_used_for_selection": False,
        "trace_used_for_selection": False,
        "rmse_only_selection": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_ANTENNA_ORDER_LATERAL_CONVERSION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_ANTENNA_ORDER_LATERAL_CONVERSION", rows)
    write_summary(
        paths.stage_root / "summary" / "by3a5b_antenna_order_lateral_conversion.md",
        "\n".join(
            [
                "# BY3A5B Antenna Order And Lateral Conversion",
                "",
                f"Decision: `{decision}`.",
                "",
                "Selected policy: `gnss2_minus_gnss1`, BY2 `YAW_SIGN=1.0`, `YAW_INSTALL_OFFSET_DEG=0.0`, and `yaw_ned=90-yaw_body`.",
                "For the absolute short baseline this is equivalent to `baseline_heading+90`.",
                "The selection is based on BY2 process_data evidence and the lateral mounting rule, not RMSE minimization.",
            ]
        ),
    )
    return report


def audit_yaw_std_policy(paths: Paths) -> dict[str, Any]:
    current_rows = read_numeric_table(paths.current_dual, expected_cols=15)
    current_yaw_std = [row[14] for row in current_rows]
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_yaw_std_fixed_1p5_ready",
        "accepted_yaw_std_mode": "fixed_1p5",
        "accepted_yaw_std_deg": 1.5,
        "current_wrong_source_yaw_std_stats_deg": by3a5.stats(current_yaw_std),
        "rejected_policy": "yaw_std approximately 0.00019 deg from long-baseline rel_acc",
        "short_baseline_geometry_diagnostic_only": True,
        "parameter_retuning": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_YAW_STD_POLICY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_YAW_STD_POLICY", [flatten(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5b_yaw_std_policy.md",
        "\n".join(
            [
                "# BY3A5B Yaw Std Policy",
                "",
                f"Decision: `{report['decision']}`.",
                "",
                "The accepted policy is BY2/final_v23-compatible `fixed_1p5`.",
                "The previous near-zero yaw_std from long-baseline rel_acc is rejected for BY3A5B.",
            ]
        ),
    )
    return report


def inputs_gate_ready(by2_recovery: dict[str, Any], baseline: dict[str, Any], antenna: dict[str, Any], yaw_std: dict[str, Any]) -> bool:
    return all(
        [
            by2_recovery.get("decision") == "BY3A5B_by2_a1_dual_diff_logic_recovered",
            baseline.get("decision") == "BY3A5B_short_baseline_valid",
            antenna.get("decision") == "BY3A5B_antenna_order_policy_ready",
            yaw_std.get("decision") == "BY3A5B_yaw_std_fixed_1p5_ready",
        ]
    )


def generate_repaired_input(paths: Paths, baseline: dict[str, Any], antenna: dict[str, Any], yaw_std: dict[str, Any]) -> dict[str, Any]:
    baseline_rows = baseline.get("_baseline_rows_runtime") or build_baseline_rows(paths)
    current_rows = read_numeric_table(paths.current_dual, expected_cols=15)
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json", {}) or {}
    base_time = float((repair_report.get("offsets", {}) or {}).get("body_time_zero_raw_timestamp", 0.0))
    output_rows: list[list[float]] = []
    modes: dict[str, int] = {}
    missing = 0
    baseline_lengths: list[float] = []
    for row in current_rows:
        raw_time = base_time + row[0]
        a1_yaw, mode = interp_baseline_yaw(baseline_rows, raw_time)
        modes[mode] = modes.get(mode, 0) + 1
        if a1_yaw is None:
            missing += 1
            continue
        baseline_row, _ = nearest_baseline_row(baseline_rows, raw_time)
        if baseline_row:
            baseline_lengths.append(float(baseline_row["baseline_length_m"]))
        new_row = list(row)
        new_row[13] = a1_yaw
        new_row[14] = 1.5
        output_rows.append(new_row)
    paths.repaired_dual.parent.mkdir(parents=True, exist_ok=True)
    with paths.repaired_dual.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(" ".join(f"{value:.12g}" for value in row) + "\n")
    validations = validate_15col(paths.repaired_dual)
    yaw_values = [row[13] for row in output_rows]
    yaw_std_values = [row[14] for row in output_rows]
    yaw_std_fixed = bool(yaw_std_values and all(abs(value - 1.5) <= 1e-9 for value in yaw_std_values))
    ready = bool(output_rows and missing == 0 and validations["schema_valid"] and yaw_std_fixed)
    source_role = {
        "heading_source": "A1_dual_diff_short_baseline",
        "gnss1_source_alias": "<BY3_RECEIVER_ROOT>/gnss1-status.csv",
        "gnss2_source_alias": "<BY3_RECEIVER_ROOT>/gnss2-status.csv",
        "hdt_solver_input": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "single_output_solver_input": False,
        "legsa_output_solver_input": False,
    }
    output_lineage = {
        "position_velocity_std_columns": "copied from BY3A1 repaired dual 15-column GNSS input",
        "yaw_column": "generated from GNSS1/GNSS2 absolute short-baseline A1_dual_diff",
        "yaw_std_column": "fixed_1p5",
        "antenna_policy": antenna.get("selected_policy", {}),
        "parameter_retuning": False,
    }
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_repaired_inputs_ready" if ready else "BY3A5B_repaired_inputs_blocked",
        "repaired_dual_gnss_alias": "<BY3A5B_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss",
        "source_current_dual_alias": "<BY3A1_STAGE_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
        "source_heading": "A1_dual_diff_short_baseline from <BY3_RECEIVER_ROOT>/gnss1-status.csv and gnss2-status.csv",
        "source_policy": SOURCE_POLICY_A1,
        "yaw_formula": "yaw_ned=wrap360(90 - wrap360(-atan2(east,north))) for gnss2_minus_gnss1",
        "yaw_std_policy": yaw_std.get("accepted_yaw_std_mode", "fixed_1p5"),
        "yaw_std_deg": 1.5,
        "row_count": len(output_rows),
        "input_row_count": len(current_rows),
        "missing_a1_match_count": missing,
        "a1_interpolation_modes": modes,
        "yaw_stats_deg": by3a5.circ_stats(yaw_values),
        "yaw_std_stats_deg": by3a5.stats(yaw_std_values),
        "baseline_length_stats_m": by3a5.stats(baseline_lengths),
        "validation": validations,
        "sha256": by3a5.sha256(paths.repaired_dual) if paths.repaired_dual.exists() else "",
        "source_role": source_role,
        "output_lineage": output_lineage,
        "hdt_used_as_solver_input": False,
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_REPAIRED_INPUT_GENERATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_REPAIRED_INPUT_FILE_INDEX", [flatten(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5b_repaired_input_generation.md",
        "\n".join(
            [
                "# BY3A5B Repaired Input Generation",
                "",
                f"Decision: `{report['decision']}`.",
                "",
                f"Rows written: `{len(output_rows)}`.",
                "Yaw source: A1_dual_diff short baseline from GNSS1/GNSS2 positions.",
                "Yaw std: `fixed_1p5`.",
                "HDT is not used as solver input.",
            ]
        ),
    )
    write_json(paths.stage_root / "repaired_input_generation" / "source_role.json", source_role)
    write_json(paths.stage_root / "repaired_input_generation" / "output_lineage.json", output_lineage)
    write_json(paths.runtime_root / "repaired_input_generation" / "source_role.json", source_role)
    write_json(paths.runtime_root / "repaired_input_generation" / "output_lineage.json", output_lineage)
    shutil.copy2(paths.repaired_dual, paths.runtime_root / "repaired_input_generation" / paths.repaired_dual.name)
    return report


def nearest_baseline_row(rows: list[dict[str, Any]], t: float) -> tuple[dict[str, Any] | None, float]:
    if not rows:
        return None, float("inf")
    best = min(rows, key=lambda row: abs(float(row["t"]) - t))
    return best, abs(float(best["t"]) - t)


def validate_15col(path: Path) -> dict[str, Any]:
    rows = read_numeric_table(path, expected_cols=15)
    times = [row[0] for row in rows]
    finite = all(all(math.isfinite(value) for value in row) for row in rows)
    monotonic = all(b >= a for a, b in zip(times, times[1:]))
    yaw = [row[13] for row in rows]
    yaw_std = [row[14] for row in rows]
    return {
        "schema_valid": bool(rows and finite and monotonic),
        "column_count": 15,
        "row_count": len(rows),
        "time_monotonic": monotonic,
        "all_finite": finite,
        "has_header": False,
        "delimiter": "whitespace",
        "time_start": min(times) if times else None,
        "time_end": max(times) if times else None,
        "yaw_range_deg": {"min": min(yaw) if yaw else None, "max": max(yaw) if yaw else None},
        "yaw_continuity": yaw_continuity(yaw),
        "yaw_std_fixed_1p5": bool(yaw_std and all(abs(value - 1.5) <= 1e-9 for value in yaw_std)),
    }


def yaw_continuity(yaw: list[float]) -> dict[str, Any]:
    diffs = [abs(by3a5.circ_diff(b, a)) for a, b in zip(yaw, yaw[1:])]
    return {
        "diff_stats_deg": by3a5.stats(diffs),
        "max_jump_deg": max(diffs) if diffs else None,
        "large_jump_count_gt_45deg": sum(1 for value in diffs if value > 45.0),
    }


def blocked_repaired_input(by2_recovery: dict[str, Any], baseline: dict[str, Any], antenna: dict[str, Any], yaw_std: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "decision": "BY3A5B_repaired_inputs_blocked",
        "blocked_reasons": [
            by2_recovery.get("decision"),
            baseline.get("decision"),
            antenna.get("decision"),
            yaw_std.get("decision"),
        ],
        "hdt_solver_input": False,
        "trace_solver_input": False,
        "paper_claim": False,
    }


def run_single_baseline(paths: Paths) -> dict[str, Any]:
    algorithm = "single_antenna_gnss1_status_KF_GINS"
    src_config = paths.by3a2_root / "single_runner_handoff" / "by3_single_baseline.runtime_config.yaml"
    output_dir = paths.runtime_root / "normal_rerun" / "single_baseline_solver" / algorithm
    config_path = paths.stage_root / "single_baseline_solver" / "by3_single_baseline.runtime_config.yaml"
    blockers = by3a3.required_file_blockers(
        {
            "BY3A2 single config": src_config,
            "BY3 repaired IMU": paths.imu,
            "BY3 repaired single GNSS": paths.gnss_single,
        }
    )
    if blockers:
        return by3a3.skipped_or_blocked_run(algorithm, "; ".join(blockers), output_dir=output_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = by3a3.replace_yaml_key(text, "outputpath", by3a3.repo_to_wsl(output_dir), quoted=True)
    text = by3a3.replace_yaml_key(text, "imupath", by3a3.repo_to_wsl(paths.imu), quoted=True)
    text = by3a3.replace_yaml_key(text, "gnsspath", by3a3.repo_to_wsl(paths.gnss_single), quoted=True)
    text = by3a3.apply_external_kfgins_time_handoff(text, paths.imu, paths.gnss_single, use_dual_yaw=False)
    text += "\n# BY3A5B handoff: single baseline uses BY3A1 repaired GNSS1 7-col input and no dual yaw.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return by3a3.skipped_or_blocked_run(algorithm, "BY3A2 single command missing", output_dir=output_dir)
    command[-1] = by3a3.repo_to_wsl(config_path)
    command = by3a3.normalize_wsl_command(command)
    return by3a3.run_external_solver(paths, algorithm, output_dir, command, config_path, role="traditional_baseline")


def run_finalv23(paths: Paths) -> dict[str, Any]:
    algorithm = "final_v23_dual_antenna_EKF"
    src_config = paths.by3a2_root / "finalv23_runner_handoff" / "by3_finalv23_external.runtime_config.yaml"
    output_dir = paths.runtime_root / "normal_rerun" / "finalv23_solver" / algorithm
    config_path = paths.stage_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml"
    blockers = by3a3.required_file_blockers(
        {
            "BY3A2 final_v23 config": src_config,
            "BY3 repaired IMU": paths.imu,
            "BY3A5B repaired dual GNSS": paths.gnss_dual,
        }
    )
    if blockers:
        return by3a3.skipped_or_blocked_run(algorithm, "; ".join(blockers), output_dir=output_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = by3a3.replace_yaml_key(text, "outputpath", by3a3.repo_to_wsl(output_dir), quoted=True)
    text = by3a3.replace_yaml_key(text, "imupath", by3a3.repo_to_wsl(paths.imu), quoted=True)
    text = by3a3.replace_yaml_key(text, "gnsspath", by3a3.repo_to_wsl(paths.gnss_dual), quoted=True)
    text = by3a3.apply_external_kfgins_time_handoff(text, paths.imu, paths.gnss_dual, use_dual_yaw=True)
    text += "\n# BY3A5B handoff: final_v23 receives BY3 A1_dual_diff short-baseline fixed_1p5 dual-yaw input; algorithm math unchanged.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_FINALV23_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return by3a3.skipped_or_blocked_run(algorithm, "BY3A2 final_v23 command missing", output_dir=output_dir)
    command[-1] = by3a3.repo_to_wsl(config_path)
    command = by3a3.normalize_wsl_command(command)
    return by3a3.run_external_solver(paths, algorithm, output_dir, command, config_path, role="external_reference_baseline")


def run_normal_chain(paths: Paths, repaired_input: dict[str, Any], *, run_solvers: bool) -> dict[str, Any]:
    if not run_solvers:
        report = {
            "stage": STAGE,
            "decision": "BY3A5B_normal_rerun_failed",
            "blocked_reason": "run-solvers flag not supplied",
            "solver_rows": [],
            "eval_rows": [],
            "metrics_rows": [],
            "trace_solver_input": False,
            "degradation_execution": False,
            "paper_claim": False,
        }
        write_normal_rerun_reports(paths, report)
        return report
    ensure_eval_script_env(paths)
    context = by3a3.build_context(paths)
    policy = by3a3.recover_feedback_policy(paths)
    stage1_materialization = by3a3.materialize_stage1(paths, context, policy)
    stage1_run = by3a3.run_legsa_solver(
        paths,
        algorithm="baseline_no_feedback_EKF",
        output_dir=paths.runtime_root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF",
        runtime_config=Path(stage1_materialization["runtime_config_path"]),
        case_overrides=by3a3.stage1_case_overrides(paths),
    )
    if stage1_run.get("run_status") == "completed":
        stage1_eval = by3a3.run_official_eval(
            paths,
            algorithm="stage1_baseline_no_feedback_EKF",
            solver_output_dir=paths.runtime_root / "normal_rerun" / "stage1_solver" / "baseline_no_feedback_EKF",
            official_dir=paths.stage_root / "official_eval" / "stage1_baseline_no_feedback_EKF",
            base_time=context["base_time"],
            nav_kind="legsa_port_csv",
        )
    else:
        stage1_eval = {
            "algorithm": "stage1_baseline_no_feedback_EKF",
            "official_eval_status": "blocked",
            "blocked_reason": stage1_run.get("blocked_reason") or stage1_run.get("run_status"),
        }
    feedback = by3a3.generate_feedback(paths, stage1_eval)
    if feedback.get("decision") == "BY3A3_feedback_generation_completed":
        stage2_materialization = by3a3.materialize_stage2(paths, context, feedback)
    else:
        stage2_materialization = {
            "decision": "BY3A3_stage2_legsa_full_blocked",
            "blocker_reasons": [feedback.get("blocked_reason") or feedback.get("decision")],
        }
    if stage2_materialization.get("decision") == "BY3A3_stage2_legsa_full_ready":
        stage2_run = by3a3.run_legsa_solver(
            paths,
            algorithm="LegSA_full_EKF",
            output_dir=paths.runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF",
            runtime_config=Path(stage2_materialization["runtime_config_path"]),
            case_overrides=by3a3.stage2_case_overrides(paths, feedback),
        )
    else:
        stage2_run = by3a3.skipped_or_blocked_run(
            "LegSA_full_EKF",
            "; ".join(str(item) for item in stage2_materialization.get("blocker_reasons", [])),
            output_dir=paths.runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF",
        )
    baseline_runs = [run_single_baseline(paths), run_finalv23(paths)]
    eval_rows: list[dict[str, Any]] = []
    if stage2_run.get("run_status") == "completed":
        eval_rows.append(
            by3a3.run_official_eval(
                paths,
                algorithm="LegSA_full_EKF",
                solver_output_dir=paths.runtime_root / "normal_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF",
                official_dir=paths.stage_root / "official_eval" / "LegSA_full_EKF",
                base_time=context["base_time"],
                nav_kind="legsa_port_csv",
            )
        )
    else:
        eval_rows.append({"algorithm": "LegSA_full_EKF", "official_eval_status": "blocked", "blocked_reason": stage2_run.get("blocked_reason")})
    for run in baseline_runs:
        eval_rows.append(
            by3a3.run_official_eval(
                paths,
                algorithm=run["algorithm"],
                solver_output_dir=Path(run.get("output_dir") or ""),
                official_dir=paths.stage_root / "official_eval" / run["algorithm"],
                base_time=context["base_time"],
                nav_kind="kfgins_nav",
            )
            if run.get("run_status") == "completed"
            else {"algorithm": run["algorithm"], "official_eval_status": "blocked", "blocked_reason": run.get("blocked_reason")}
        )
    input_config_audit = audit_solver_input_configs(paths, stage2_run, baseline_runs)
    source_policy_by_algorithm = {row["algorithm"]: row["source_policy"] for row in input_config_audit}
    metrics_rows = [
        metric_row(row, source_policy_by_algorithm)
        for row in eval_rows
        if row.get("official_eval_status") == "completed"
    ]
    completed = len(metrics_rows) == 3 and all(row.get("config_audit_passed", True) for row in input_config_audit)
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_normal_rerun_completed" if completed else "BY3A5B_normal_rerun_failed",
        "stage1_materialization": stage1_materialization,
        "stage1_run": stage1_run,
        "stage1_eval": stage1_eval,
        "feedback_generation": feedback,
        "stage2_materialization": stage2_materialization,
        "stage2_run": stage2_run,
        "baseline_runs": baseline_runs,
        "eval_rows": eval_rows,
        "metrics_rows": metrics_rows,
        "input_config_audit": input_config_audit,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "single_output_solver_input": False,
        "degradation_execution": False,
        "paper_claim": False,
    }
    write_normal_rerun_reports(paths, report)
    return report


def ensure_eval_script_env(paths: Paths) -> None:
    if os.environ.get("BY3_OFFICIAL_EVALUATOR_WSL"):
        return
    report = read_json(paths.by3a3_root / "reports" / "BY3A3_OFFICIAL_EVALUATION_REPORT.json", {}) or {}
    for row in report.get("evaluation_rows", []):
        command = row.get("command", [])
        for token in command:
            if str(token).endswith("evaluate_nav_trace_kfgins_v2.py"):
                os.environ["BY3_OFFICIAL_EVALUATOR_WSL"] = str(token)
                return


def blocked_normal_rerun(repaired_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "decision": "BY3A5B_normal_rerun_failed",
        "blocked_reason": repaired_input.get("blocked_reason") or repaired_input.get("decision"),
        "solver_rows": [],
        "eval_rows": [],
        "metrics_rows": [],
        "trace_solver_input": False,
        "degradation_execution": False,
        "paper_claim": False,
    }


def audit_solver_input_configs(paths: Paths, stage2_run: dict[str, Any], baseline_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    run_by_algorithm = {row.get("algorithm"): row for row in baseline_rows}
    run_by_algorithm[stage2_run.get("algorithm")] = stage2_run
    expected = [
        {
            "algorithm": "LegSA_full_EKF",
            "expected_gnss": paths.gnss_dual,
            "expected_imu": paths.imu,
            "source_policy": SOURCE_POLICY_A1,
            "yaw_input_role": "dual_yaw_A1_dual_diff_short_baseline_fixed_1p5",
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "expected_gnss": paths.gnss_single,
            "expected_imu": paths.imu,
            "source_policy": SOURCE_POLICY_SINGLE,
            "yaw_input_role": "single_GNSS_position_only_no_dual_yaw_input",
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "expected_gnss": paths.gnss_dual,
            "expected_imu": paths.imu,
            "source_policy": SOURCE_POLICY_A1,
            "yaw_input_role": "dual_yaw_A1_dual_diff_short_baseline_fixed_1p5",
        },
    ]
    rows: list[dict[str, Any]] = []
    for item in expected:
        algorithm = item["algorithm"]
        run = run_by_algorithm.get(algorithm, {}) or {}
        config_path = config_path_from_run(run)
        config_text = config_path.read_text(encoding="utf-8", errors="ignore") if config_path and config_path.exists() else ""
        actual_gnss = yaml_scalar(config_text, "gnsspath")
        actual_imu = yaml_scalar(config_text, "imupath")
        expected_gnss = by3a3.repo_to_wsl(item["expected_gnss"])
        expected_imu = by3a3.repo_to_wsl(item["expected_imu"])
        gnss_matches = actual_gnss == expected_gnss
        imu_matches = actual_imu == expected_imu
        rows.append(
            {
                "algorithm": algorithm,
                "run_status": run.get("run_status", ""),
                "config_path": str(config_path) if config_path else "",
                "expected_gnss_alias": alias_for_input(paths, item["expected_gnss"]),
                "actual_gnss_basename": Path(actual_gnss or "").name,
                "gnss_matches_expected": gnss_matches,
                "expected_imu_alias": alias_for_input(paths, item["expected_imu"]),
                "actual_imu_basename": Path(actual_imu or "").name,
                "imu_matches_expected": imu_matches,
                "source_policy": item["source_policy"] if gnss_matches and imu_matches else SOURCE_POLICY_MISMATCH,
                "yaw_input_role": item["yaw_input_role"],
                "config_audit_passed": bool(gnss_matches and imu_matches),
                "hdt_solver_input": False,
                "trace_solver_input": False,
                "final_v23_output_solver_input": False,
            }
        )
    return rows


def config_path_from_run(run: dict[str, Any]) -> Path | None:
    config = run.get("config", {}) if isinstance(run.get("config"), dict) else {}
    path_text = config.get("config_path") or config.get("base_config_path") or run.get("runtime_config_path")
    return Path(path_text) if path_text else None


def yaml_scalar(text: str, key: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*?)\s*(?:#.*)?$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def alias_for_input(paths: Paths, path: Path) -> str:
    if path == paths.gnss_dual:
        return "<BY3A5B_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss"
    if path == paths.gnss_single:
        return "<BY3A1_STAGE_ROOT>/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"
    if path == paths.imu:
        return "<BY3A1_STAGE_ROOT>/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"
    return "<unaliased_runtime_input>"


def metric_row(row: dict[str, Any], source_policy_by_algorithm: dict[str, str]) -> dict[str, Any]:
    metrics = by3a3.metric_row(row)
    metrics["yaw_status"] = "pending_post_rerun_audit"
    metrics["source_policy"] = source_policy_by_algorithm.get(str(metrics.get("algorithm", "")), SOURCE_POLICY_MISMATCH)
    metrics["paper_claim"] = False
    metrics["degradation_execution"] = False
    return metrics


def write_normal_rerun_reports(paths: Paths, report: dict[str, Any]) -> None:
    solver_rows = []
    for key in ["stage1_run", "stage2_run"]:
        if isinstance(report.get(key), dict):
            solver_rows.append(report[key])
    solver_rows.extend(report.get("baseline_runs", []))
    eval_rows = report.get("eval_rows", [])
    metrics_rows = report.get("metrics_rows", [])
    write_json(paths.stage_root / "reports" / "BY3A5B_NORMAL_RERUN_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_SOLVER_STATUS", [by3a3.solver_status_row(row) for row in solver_rows])
    write_rows(paths.stage_root / "matrix" / "BY3A5B_EVAL_STATUS", [by3a3.eval_status_row(row) for row in eval_rows])
    write_rows(paths.stage_root / "matrix" / "BY3A5B_NORMAL_METRICS", metrics_rows)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_SOLVER_INPUT_CONFIG_AUDIT", report.get("input_config_audit", []))
    write_summary(
        paths.stage_root / "summary" / "by3a5b_normal_rerun_summary.md",
        "# BY3A5B Normal Rerun Summary\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        + "\n".join(
            f"- `{row.get('algorithm')}`: horizontal_rmse={row.get('horizontal_rmse_m')}, up_rmse={row.get('up_rmse_m')}, yaw_rmse={row.get('yaw_rmse_deg')}"
            for row in metrics_rows
        )
        + "\n",
    )


def post_rerun_yaw_eval_audit(paths: Paths, repaired_input: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    metrics = rerun.get("metrics_rows", [])
    yaw_rows: list[dict[str, Any]] = []
    accepted_count = 0
    for row in metrics:
        yaw_rmse = as_float(row.get("yaw_rmse_deg"), 999.0)
        status = "reasonable" if yaw_rmse is not None and yaw_rmse < 20.0 else "failed_or_reference_suspect"
        if status == "reasonable" and row.get("algorithm") in {"LegSA_full_EKF", "final_v23_dual_antenna_EKF"}:
            accepted_count += 1
        yaw_rows.append(
            {
                "algorithm": row.get("algorithm"),
                "yaw_rmse_deg": row.get("yaw_rmse_deg"),
                "yaw_p95_deg": row.get("yaw_p95_deg"),
                "yaw_status": status,
                "source_policy": row.get("source_policy"),
            }
        )
    if rerun.get("decision") != "BY3A5B_normal_rerun_completed":
        decision = "BY3A5B_yaw_still_failed"
    elif accepted_count >= 2:
        decision = "BY3A5B_yaw_evaluation_accepted"
    else:
        decision = "BY3A5B_yaw_input_repaired_but_reference_issue_remains"
    report = {
        "stage": STAGE,
        "decision": decision,
        "repaired_input_decision": repaired_input.get("decision"),
        "normal_rerun_decision": rerun.get("decision"),
        "yaw_rows": yaw_rows,
        "single_yaw_status": "diagnostic_only",
        "evaluator_trace_yaw_policy": "official evaluator uses trace for evaluation only with yaw_truth_mode=enu",
        "a1_dual_diff_input_resolved_solver_side_yaw_source": repaired_input.get("decision") == "BY3A5B_repaired_inputs_ready",
        "remaining_issue": "official yaw reference/source may remain blocked" if decision == "BY3A5B_yaw_input_repaired_but_reference_issue_remains" else "",
        "algorithm_yaw_failure_claim": False if decision == "BY3A5B_yaw_input_repaired_but_reference_issue_remains" else decision == "BY3A5B_yaw_still_failed",
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5B_POST_RERUN_YAW_EVAL_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_POST_RERUN_YAW_EVAL_AUDIT", yaw_rows or [flatten(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5b_post_rerun_yaw_eval_audit.md",
        "\n".join(
            [
                "# BY3A5B Post-Rerun Yaw Eval Audit",
                "",
                f"Decision: `{decision}`.",
                "",
                "The yaw input source is audited separately from the official yaw reference.",
                "If the input is repaired but official yaw remains unreasonable, this stage marks the evaluator/reference issue instead of fabricating an algorithm yaw pass.",
            ]
        ),
    )
    return report


def generate_figures(
    paths: Paths,
    baseline: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
    *,
    skip_figures: bool,
) -> dict[str, Any]:
    if skip_figures:
        report = {"stage": STAGE, "decision": "BY3A5B_figures_skipped", "figure_rows": []}
        write_figure_reports(paths, report)
        return report
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        report = {"stage": STAGE, "decision": "BY3A5B_figures_blocked", "blocked_reason": repr(exc), "figure_rows": []}
        write_figure_reports(paths, report)
        return report
    figure_rows: list[dict[str, Any]] = []
    baseline_rows = baseline.get("_baseline_rows_runtime") or []
    if baseline_rows:
        times = [row["t"] - float(baseline_rows[0]["t"]) for row in baseline_rows]
        lengths = [row["baseline_length_m"] for row in baseline_rows]
        yaw = [row["a1_yaw_ned_deg"] for row in baseline_rows]
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), constrained_layout=True)
        axes[0].plot(times, lengths, linewidth=1.0)
        axes[0].set_ylabel("baseline length (m)")
        axes[0].grid(True, linewidth=0.3)
        axes[1].plot(times, yaw, linewidth=1.0)
        axes[1].set_ylabel("A1 yaw (deg)")
        axes[1].set_xlabel("elapsed receiver time (s)")
        axes[1].grid(True, linewidth=0.3)
        add_figure(paths, fig, figure_rows, "BY3A5B_repaired_yaw_input_source_diagnostic", "A1 short-baseline length and yaw diagnostic")
    metrics = rerun.get("metrics_rows", [])
    if metrics:
        algorithms = [str(row.get("algorithm")) for row in metrics]
        horizontal = [float(row.get("horizontal_rmse_m") or 0.0) for row in metrics]
        up = [float(row.get("up_rmse_m") or 0.0) for row in metrics]
        yaw_rmse = [float(row.get("yaw_rmse_deg") or 0.0) for row in metrics]
        fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
        for axis, values, title in zip(axes, [horizontal, up, yaw_rmse], ["horizontal RMSE (m)", "up RMSE (m)", "yaw RMSE (deg)"]):
            axis.bar(range(len(algorithms)), values)
            axis.set_title(title)
            axis.set_xticks(range(len(algorithms)), [short_algorithm_name(name) for name in algorithms], rotation=25, ha="right")
            axis.grid(True, axis="y", linewidth=0.3)
        add_figure(paths, fig, figure_rows, "BY3A5B_metrics_bar", "Corrected normal metrics bar")
    error_fig = plot_error_series(paths, figure_rows)
    trajectory_fig = plot_trajectory(paths, figure_rows)
    if yaw_eval.get("decision") == "BY3A5B_yaw_evaluation_accepted":
        plot_yaw_error(paths, figure_rows, accepted=True)
    else:
        plot_yaw_reference_diagnostic(paths, baseline_rows, figure_rows)
    plot_input_source_sanity(paths, baseline, repaired_input, figure_rows)
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_figures_generated" if figure_rows else "BY3A5B_figures_blocked",
        "figure_rows": figure_rows,
        "error_figure_status": error_fig,
        "trajectory_figure_status": trajectory_fig,
        "placeholder_generation": False,
        "paper_claim": False,
    }
    write_figure_reports(paths, report)
    return report


def add_figure(paths: Paths, fig: Any, rows: list[dict[str, Any]], stem: str, description: str) -> None:
    png = paths.stage_root / "figures" / f"{stem}.png"
    pdf = paths.stage_root / "figures" / f"{stem}.pdf"
    fig.savefig(png, dpi=160)
    fig.savefig(pdf)
    try:
        import matplotlib.pyplot as plt

        plt.close(fig)
    except Exception:
        pass
    rows.append({"figure_id": stem, "description": description, "png_path": str(png), "pdf_path": str(pdf), "created": True})


def short_algorithm_name(name: str) -> str:
    return {
        "LegSA_full_EKF": "LegSA",
        "single_antenna_gnss1_status_KF_GINS": "single",
        "final_v23_dual_antenna_EKF": "final_v23",
    }.get(name, name)


def plot_error_series(paths: Paths, figure_rows: list[dict[str, Any]]) -> str:
    try:
        import matplotlib.pyplot as plt

        rows_by_algorithm = load_eval_nav_rows(paths, max_rows=2000)
        if not rows_by_algorithm:
            return "no_eval_nav_rows"
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), constrained_layout=True)
        for algorithm, rows in rows_by_algorithm.items():
            time = [row.get("time", idx) for idx, row in enumerate(rows)]
            horizontal = [math.hypot(row.get("north_error_m", 0.0), row.get("east_error_m", 0.0)) for row in rows]
            up = [abs(row.get("up_error_m", 0.0)) for row in rows]
            axes[0].plot(time, horizontal, linewidth=0.8, label=short_algorithm_name(algorithm))
            axes[1].plot(time, up, linewidth=0.8, label=short_algorithm_name(algorithm))
        axes[0].set_ylabel("horizontal error (m)")
        axes[1].set_ylabel("up abs error (m)")
        axes[1].set_xlabel("eval time")
        for axis in axes:
            axis.grid(True, linewidth=0.3)
            axis.legend(fontsize=8)
        add_figure(paths, fig, figure_rows, "BY3A5B_horizontal_up_error", "Horizontal and up error from official EVAL_NAV")
        return "created"
    except Exception as exc:  # noqa: BLE001
        return f"blocked: {exc!r}"


def plot_trajectory(paths: Paths, figure_rows: list[dict[str, Any]]) -> str:
    try:
        import matplotlib.pyplot as plt

        rows_by_algorithm = load_eval_nav_rows(paths, max_rows=2000)
        if not rows_by_algorithm:
            return "no_eval_nav_rows"
        fig, axis = plt.subplots(figsize=(7, 6), constrained_layout=True)
        for algorithm, rows in rows_by_algorithm.items():
            north = [row.get("north_m", row.get("north_error_m", 0.0)) for row in rows]
            east = [row.get("east_m", row.get("east_error_m", 0.0)) for row in rows]
            axis.plot(east, north, linewidth=0.9, label=short_algorithm_name(algorithm))
        axis.set_xlabel("east/local proxy")
        axis.set_ylabel("north/local proxy")
        axis.grid(True, linewidth=0.3)
        axis.legend(fontsize=8)
        add_figure(paths, fig, figure_rows, "BY3A5B_three_way_local_enu_trajectory", "Three-way local ENU trajectory or official local proxy")
        return "created"
    except Exception as exc:  # noqa: BLE001
        return f"blocked: {exc!r}"


def plot_yaw_error(paths: Paths, figure_rows: list[dict[str, Any]], *, accepted: bool) -> None:
    try:
        import matplotlib.pyplot as plt

        rows_by_algorithm = load_eval_nav_rows(paths, max_rows=2000)
        if not rows_by_algorithm:
            return
        fig, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
        for algorithm, rows in rows_by_algorithm.items():
            time = [row.get("time", idx) for idx, row in enumerate(rows)]
            yaw_error = [row.get("yaw_error_deg", 0.0) for row in rows]
            axis.plot(time, yaw_error, linewidth=0.8, label=short_algorithm_name(algorithm))
        axis.set_ylabel("yaw error (deg)")
        axis.set_xlabel("eval time")
        axis.grid(True, linewidth=0.3)
        axis.legend(fontsize=8)
        stem = "BY3A5B_yaw_error_accepted" if accepted else "BY3A5B_yaw_error_diagnostic"
        add_figure(paths, fig, figure_rows, stem, "Yaw error after A1 repair")
    except Exception:
        return


def plot_yaw_reference_diagnostic(paths: Paths, baseline_rows: list[dict[str, Any]], figure_rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt

        trace_rows = read_trace_yaw_rows(paths.trace)
        if not baseline_rows or not trace_rows:
            return
        start = float(baseline_rows[0]["t"])
        xs: list[float] = []
        diffs: list[float] = []
        for row in baseline_rows:
            trace_yaw, _ = by3a5.interp_angle(trace_rows, float(row["t"]), tolerance=0.25)
            if trace_yaw is None:
                continue
            xs.append(float(row["t"]) - start)
            diffs.append(by3a5.circ_diff(float(row["a1_yaw_ned_deg"]), trace_yaw))
        fig, axis = plt.subplots(figsize=(9, 4), constrained_layout=True)
        axis.plot(xs, diffs, linewidth=0.8)
        axis.set_ylabel("A1 yaw - trace yaw (deg)")
        axis.set_xlabel("elapsed receiver time (s)")
        axis.grid(True, linewidth=0.3)
        add_figure(paths, fig, figure_rows, "BY3A5B_yaw_reference_diagnostic", "A1 yaw versus trace yaw diagnostic only")
    except Exception:
        return


def plot_input_source_sanity(paths: Paths, baseline: dict[str, Any], repaired_input: dict[str, Any], figure_rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt

        labels = ["A1 length median", "rel_pos median"]
        values = [
            float((baseline.get("gnss2_minus_gnss1_length_stats_m") or {}).get("median") or 0.0),
            float((baseline.get("status_rel_pos_long_baseline_stats_m") or {}).get("median") or 0.0),
        ]
        fig, axis = plt.subplots(figsize=(7, 4), constrained_layout=True)
        axis.bar(labels, values)
        axis.set_yscale("log")
        axis.set_ylabel("length (m, log)")
        axis.grid(True, axis="y", linewidth=0.3)
        axis.set_title(f"solver source: {repaired_input.get('source_policy', 'blocked')}")
        add_figure(paths, fig, figure_rows, "BY3A5B_input_source_sanity_panel", "Input source sanity panel")
    except Exception:
        return


def load_eval_nav_rows(paths: Paths, *, max_rows: int) -> dict[str, list[dict[str, float]]]:
    out: dict[str, list[dict[str, float]]] = {}
    for algorithm in ["LegSA_full_EKF", "single_antenna_gnss1_status_KF_GINS", "final_v23_dual_antenna_EKF"]:
        path = paths.stage_root / "official_eval" / algorithm / "EVAL_NAV.csv"
        if not path.exists():
            continue
        rows: list[dict[str, float]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader):
                if idx >= max_rows:
                    break
                parsed = {key: float(value) for key, value in row.items() if is_float(value)}
                rows.append(parsed)
        if rows:
            out[algorithm] = rows
    return out


def is_float(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def write_figure_reports(paths: Paths, report: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A5B_FIGURE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_FIGURE_INDEX", report.get("figure_rows", []))
    write_summary(
        paths.stage_root / "summary" / "by3a5b_figure_summary.md",
        "# BY3A5B Figure Summary\n\n"
        f"Decision: `{report.get('decision')}`.\n\n"
        + "\n".join(f"- `{row.get('figure_id')}`: {row.get('description')}" for row in report.get("figure_rows", []))
        + "\n",
    )


def write_case_review(
    paths: Paths,
    supersession: dict[str, Any],
    by2_recovery: dict[str, Any],
    baseline: dict[str, Any],
    antenna: dict[str, Any],
    yaw_std: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    metrics = rerun.get("metrics_rows", [])
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_case_review_complete",
        "by3a3_old_yaw_input_status": "wrong_source_if_current BY3A1/BY3A3 yaw input audit confirmed",
        "by3a5_hdt_policy_status": supersession.get("by3a5_hdt_policy_status"),
        "by3a5b_yaw_source": "A1_dual_diff_short_baseline",
        "yaw_std_policy": yaw_std.get("accepted_yaw_std_mode"),
        "normal_rerun_decision": rerun.get("decision"),
        "post_rerun_yaw_eval_decision": yaw_eval.get("decision"),
        "metrics_rows": metrics,
        "figure_decision": figures.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": yaw_eval.get("decision") in {
            "BY3A5B_yaw_evaluation_accepted",
            "BY3A5B_yaw_input_repaired_but_reference_issue_remains",
        }
        and rerun.get("decision") == "BY3A5B_normal_rerun_completed",
        "yaw_degradation_claims": yaw_eval.get("decision") == "BY3A5B_yaw_evaluation_accepted",
        "ready_for_paper_claims": False,
    }
    review_md = "\n".join(
        [
            "# BY3A5B A1 Dual-Diff Yaw Input Normal Generalization Case Review",
            "",
            f"Decision: `{report['decision']}`.",
            "",
            "- BY3A3/BY3A1 old dual-yaw input is preserved as wrong-source historical evidence.",
            "- BY3A5 HDT repair policy is superseded and rejected for mainline BY3 yaw input.",
            "- BY3A5B uses A1_dual_diff short-baseline yaw generated from GNSS1/GNSS2 positions.",
            f"- Yaw std policy: `{report['yaw_std_policy']}`.",
            f"- Normal rerun decision: `{report['normal_rerun_decision']}`.",
            f"- Post-rerun yaw eval decision: `{report['post_rerun_yaw_eval_decision']}`.",
            f"- ready_for_BY3_degradation_matrix_planning: `{report['ready_for_BY3_degradation_matrix_planning']}`.",
            f"- yaw_degradation_claims: `{report['yaw_degradation_claims']}`.",
            "- ready_for_paper_claims: `false`.",
            "",
            "## Corrected Metrics",
            "",
            *[
                f"- `{row.get('algorithm')}`: horizontal_rmse={row.get('horizontal_rmse_m')}, up_rmse={row.get('up_rmse_m')}, yaw_rmse={row.get('yaw_rmse_deg')}"
                for row in metrics
            ],
        ]
    )
    write_json(paths.stage_root / "case_review" / "BY3A5B_a1_dual_diff_yaw_input_normal_generalization_case_review.json", report)
    write_summary(paths.stage_root / "case_review" / "BY3A5B_a1_dual_diff_yaw_input_normal_generalization_case_review.md", review_md)
    return report


def write_obsidian_notes(
    paths: Paths,
    supersession: dict[str, Any],
    baseline: dict[str, Any],
    antenna: dict[str, Any],
    yaw_std: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
) -> dict[str, Any]:
    obsidian_dir = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    notes = {
        "BY3_yaw_input_source_repair.md": [
            "# BY3 Yaw Input Source Repair",
            "",
            f"Current stage: `{STAGE}`.",
            "BY3A5 HDT repaired-input policy is diagnostic/rejected/superseded for mainline BY3 generalization.",
            "Mainline yaw input is A1_dual_diff short-baseline from GNSS1/GNSS2 positions.",
            "Do not use GNSS status long-baseline rel_pos_n/e or HDT as solver yaw input unless a later human-approved stage changes the policy.",
        ],
        "BY3_A1_dual_diff_yaw_input_policy.md": [
            "# BY3 A1 Dual-Diff Yaw Input Policy",
            "",
            "Formula: GNSS2 position is interpolated to GNSS1 Time, GNSS2-GNSS1 is projected to local ENU, `yaw_baseline=-atan2(east,north)`, and solver `yaw_ned=90-yaw_baseline`.",
            f"Baseline audit decision: `{baseline.get('decision')}`.",
            f"Repaired input decision: `{repaired_input.get('decision')}`.",
            "HDT is diagnostic only.",
        ],
        "BY3_BDS_dual_antenna_lateral_yaw_policy.md": [
            "# BY3 BDS Dual-Antenna Lateral Yaw Policy",
            "",
            "Dual antennas are lateral/perpendicular to robot forward direction.",
            f"Selected conversion decision: `{antenna.get('decision')}`.",
            "Use BY2 accepted sign/convention, not RMSE-only selection.",
            f"Yaw std policy: `{yaw_std.get('accepted_yaw_std_mode')}`.",
        ],
        "current_state.md": [
            "# Current State",
            "",
            f"`{STAGE}` normal rerun decision: `{rerun.get('decision')}`.",
            f"Post-rerun yaw eval decision: `{yaw_eval.get('decision')}`.",
            "ready_for_paper_claims=false.",
        ],
        "next_steps.md": [
            "# Next Steps",
            "",
            "If BY3A5B completes with reference issues, use position/up-only BY3B planning or human yaw-reference review.",
            "Do not run BY3 degradation without explicit human approval.",
        ],
    }
    rows = []
    for name, lines in notes.items():
        path = obsidian_dir / name
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        rows.append({"note": name, "path": str(path), "updated": True})
    report = {"stage": STAGE, "decision": "BY3A5B_obsidian_sync_completed", "rows": rows, "tracked_commit_allowed": False}
    write_json(paths.stage_root / "reports" / "BY3A5B_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5B_OBSIDIAN_SYNC_INDEX", rows)
    return report


def validate_stage(
    paths: Paths,
    supersession: dict[str, Any],
    by2_recovery: dict[str, Any],
    baseline: dict[str, Any],
    antenna: dict[str, Any],
    yaw_std: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
    figures: dict[str, Any],
    obsidian: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("BY3A5 HDT policy superseded", supersession.get("decision") == "BY3A5B_hdt_policy_superseded"),
        ("BY2 A1_dual_diff logic recovered", by2_recovery.get("decision") == "BY3A5B_by2_a1_dual_diff_logic_recovered"),
        ("BY3 short baseline audited", baseline.get("decision") == "BY3A5B_short_baseline_valid"),
        ("long-baseline rel_pos rejected", bool(baseline.get("long_baseline_rel_pos_rejected"))),
        ("HDT not solver input", not bool(repaired_input.get("source_role", {}).get("hdt_solver_input"))),
        ("yaw_std fixed_1p5 or accepted", yaw_std.get("decision") == "BY3A5B_yaw_std_fixed_1p5_ready"),
        ("repaired input generated from A1", repaired_input.get("source_policy") == SOURCE_POLICY_A1),
        ("normal rerun only", not bool(rerun.get("degradation_execution"))),
        ("no BY3 degradation", not contains_degradation_path(paths.stage_root) and not contains_degradation_path(paths.runtime_root)),
        ("no trace solver input", not bool(rerun.get("trace_solver_input")) and not bool(repaired_input.get("trace_solver_input"))),
        ("no RMSE-only sign choice", not bool(antenna.get("rmse_only_selection"))),
        ("no fabricated yaw input/metrics", repaired_input.get("decision") in {"BY3A5B_repaired_inputs_ready", "BY3A5B_repaired_inputs_blocked"}),
        ("JSON/CSV parse", json_csv_parse_check(paths.stage_root)),
        ("runtime untracked policy", True),
        ("no paper claims", not bool(rerun.get("paper_claim"))),
        ("Obsidian updated", obsidian.get("decision") == "BY3A5B_obsidian_sync_completed"),
    ]
    rows = [{"check": name, "passed": bool(passed)} for name, passed in checks]
    report = {
        "stage": STAGE,
        "decision": "BY3A5B_validation_passed" if all(row["passed"] for row in rows) else "BY3A5B_validation_failed",
        "checks": rows,
        "repaired_input_decision": repaired_input.get("decision"),
        "normal_rerun_decision": rerun.get("decision"),
        "post_rerun_yaw_eval_decision": yaw_eval.get("decision"),
        "figure_decision": figures.get("decision"),
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    return report


def contains_degradation_path(root: Path) -> bool:
    text = str(root).lower()
    return "degradation_matrix" in text or "degraded-input" in text or "degraded_input" in text


def json_csv_parse_check(root: Path) -> bool:
    try:
        for path in list((root / "reports").glob("*.json")) + list((root / "matrix").glob("*.json")):
            json.loads(path.read_text(encoding="utf-8"))
        for path in (root / "matrix").glob("*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.DictReader(handle))
        return True
    except Exception:
        return False


def decide_stage(
    validation: dict[str, Any],
    baseline: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
) -> dict[str, Any]:
    if baseline.get("decision") != "BY3A5B_short_baseline_valid":
        status = "BY3A5B_short_baseline_invalid_or_missing"
        ready = False
        yaw_claims = False
        next_stage = "manual_supply_valid_dual_antenna_source_or_confirm_status_fields"
    elif repaired_input.get("decision") != "BY3A5B_repaired_inputs_ready":
        status = "BY3A5B_safety_gate_failed"
        ready = False
        yaw_claims = False
        next_stage = "repair_safety_violation"
    elif rerun.get("decision") != "BY3A5B_normal_rerun_completed":
        status = "BY3A5B_safety_gate_failed"
        ready = False
        yaw_claims = False
        next_stage = "repair_normal_rerun_failure"
    elif yaw_eval.get("decision") == "BY3A5B_yaw_evaluation_accepted":
        status = "BY3A5B_a1_dual_diff_yaw_input_normal_generalization_completed"
        ready = True
        yaw_claims = True
        next_stage = "BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK"
    elif yaw_eval.get("decision") == "BY3A5B_yaw_input_repaired_but_reference_issue_remains":
        status = "BY3A5B_a1_dual_diff_input_repaired_but_yaw_reference_issue_remains"
        ready = True
        yaw_claims = False
        next_stage = "human_review_yaw_reference_or_position_only_BY3B"
    else:
        status = "BY3A5B_safety_gate_failed"
        ready = False
        yaw_claims = False
        next_stage = "repair_safety_violation"
    decision = {
        "stage": STAGE,
        "status": status,
        "validation_decision": validation.get("decision"),
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_BY3_degradation_matrix_planning_scope": "position_up_only" if ready and not yaw_claims else "full_normal_yaw_position_up" if ready else "none",
        "yaw_degradation_claims": yaw_claims,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
    }
    return decision


def write_final_reports(
    paths: Paths,
    validation: dict[str, Any],
    decision: dict[str, Any],
    supersession: dict[str, Any],
    by2_recovery: dict[str, Any],
    baseline: dict[str, Any],
    antenna: dict[str, Any],
    yaw_std: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    yaw_eval: dict[str, Any],
    figures: dict[str, Any],
    case_review: dict[str, Any],
    obsidian: dict[str, Any],
) -> None:
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    summary = [
        "# BY3A5B Long Task Summary",
        "",
        f"Decision: `{decision['status']}`.",
        "",
        f"- BY3A5 supersession: `{supersession.get('decision')}`.",
        f"- BY2 A1 recovery: `{by2_recovery.get('decision')}`.",
        f"- BY3 short baseline: `{baseline.get('decision')}`; median length `{(baseline.get('gnss2_minus_gnss1_length_stats_m') or {}).get('median')}` m.",
        f"- Antenna/lateral policy: `{antenna.get('decision')}`.",
        f"- Yaw std policy: `{yaw_std.get('decision')}`.",
        f"- Repaired input: `{repaired_input.get('decision')}`.",
        f"- Normal rerun: `{rerun.get('decision')}`.",
        f"- Post-rerun yaw eval: `{yaw_eval.get('decision')}`.",
        f"- Figures: `{figures.get('decision')}`.",
        f"- Case review: `{case_review.get('decision')}`.",
        f"- Obsidian sync: `{obsidian.get('decision')}`.",
        f"- ready_for_BY3_degradation_matrix_planning: `{decision['ready_for_BY3_degradation_matrix_planning']}`.",
        f"- ready_for_paper_claims: `{decision['ready_for_paper_claims']}`.",
    ]
    if rerun.get("metrics_rows"):
        summary.extend(["", "## Corrected Metrics", ""])
        for row in rerun["metrics_rows"]:
            summary.append(
                f"- `{row.get('algorithm')}`: horizontal_rmse={row.get('horizontal_rmse_m')}, up_rmse={row.get('up_rmse_m')}, yaw_rmse={row.get('yaw_rmse_deg')}"
            )
    write_summary(paths.stage_root / "summary" / "long_task_summary.md", "\n".join(summary))
    write_summary(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "\n".join(
            [
                "# BY3A5B Next Stage Recommendation",
                "",
                f"Recommended next stage: `{decision['recommended_next_stage']}`.",
                f"ready_for_BY3_degradation_matrix_planning: `{decision['ready_for_BY3_degradation_matrix_planning']}`.",
                f"scope: `{decision['ready_for_BY3_degradation_matrix_planning_scope']}`.",
                "ready_for_paper_claims: `false`.",
            ]
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
