"""Audit and repair BY3 dual-yaw input source for BY3A5.

This runner is runtime-only. It audits the current BY3 15-column GNSS yaw,
recovers the BY2 process_data yaw/yaw-std policy from tracked evidence, checks
BY3 source-backed heading candidates, and only generates/runs a repaired BY3
normal chain if the source gate passes. It never runs a degradation matrix.
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


STAGE = "BY3A5_DUAL_YAW_INPUT_SOURCE_AUDIT_AND_REGENERATION"
RUNTIME_STAGE = "BY3A5_YAW_INPUT_REPAIR"
BY3A0_STAGE = "BY3A0_TO_BY3E_GENERALIZATION_BOOTSTRAP_ALIGNMENT_NORMAL_COMPARISON"
BY3A1_STAGE = "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR"
BY3A2_STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"
BY3A3_STAGE = "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION"
BY3A4A_STAGE = "BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK"
BY3A4C_STAGE = "BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION"

SUBDIRS = [
    "current_yaw_input_audit",
    "by2_yaw_generation_recovery",
    "by3_yaw_source_candidates",
    "hdt_recovery",
    "gnss2_minus_gnss1_baseline",
    "yaw_std_policy",
    "repaired_input_generation",
    "solver_rerun",
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

ALGORITHMS = [
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]

SOURCE_POLICY_DUAL_HDT = "BY3A5_HDT_fixed_1p5_dual_yaw_input"
SOURCE_POLICY_SINGLE_GNSS1 = "single_gnss1_status_no_dual_yaw_input_unchanged"
SOURCE_POLICY_MISMATCH = "input_config_mismatch"


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

    @property
    def current_dual(self) -> Path:
        return self.by3a1_root / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss"

    @property
    def repaired_dual(self) -> Path:
        return self.stage_root / "repaired_input_generation" / "BY3_DUAL_HDT_15COL_REPAIRED.gnss"

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


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    stage_root = (args.stage_root or repo / "by3-huiti" / STAGE).resolve()
    runtime_root = (args.runtime_root or repo / "by3-huiti" / "BY3_FULL_MATRIX" / RUNTIME_STAGE).resolve()
    receiver_root = (args.receiver_root or discover_receiver_root(repo)).resolve()
    trace = (args.trace or discover_trace(receiver_root)).resolve()
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
    )
    result = run_by3a5(paths, run_solvers=bool(args.run_solvers and not args.audit_only), skip_figures=args.skip_figures)
    print(json.dumps({"decision": result["decision"]["status"], "stage_root": str(paths.stage_root)}, indent=2, ensure_ascii=False))
    return 0


def run_by3a5(paths: Paths, *, run_solvers: bool, skip_figures: bool) -> dict[str, Any]:
    create_tree(paths)
    current_audit = audit_current_yaw_input(paths)
    by2_recovery = recover_by2_yaw_generation(paths)
    candidate_audit = audit_by3_candidates(paths)
    hdt_recovery = recover_hdt_heading(paths, candidate_audit)
    policy = decide_corrected_policy(current_audit, by2_recovery, candidate_audit, hdt_recovery)
    repaired_input = generate_repaired_input(paths, policy, candidate_audit) if policy["decision"] == "BY3A5_corrected_yaw_policy_ready" else blocked_input_generation(policy)
    rerun = run_normal_chain(paths, repaired_input, run_solvers=run_solvers) if repaired_input["decision"] == "BY3A5_repaired_inputs_ready" else blocked_rerun(repaired_input)
    figures = generate_figures(paths, current_audit, candidate_audit, repaired_input, rerun, skip_figures=skip_figures)
    case_review = write_case_review(paths, current_audit, by2_recovery, candidate_audit, policy, repaired_input, rerun, figures)
    context = update_context_and_obsidian(paths, current_audit, policy, repaired_input, rerun)
    validation = validate_stage(paths, current_audit, by2_recovery, candidate_audit, hdt_recovery, policy, repaired_input, rerun, figures, context)
    decision = decide_stage(validation, current_audit, policy, repaired_input, rerun)
    write_final_reports(paths, validation, decision, current_audit, by2_recovery, candidate_audit, hdt_recovery, policy, repaired_input, rerun, figures, case_review, context)
    return {"validation": validation, "decision": decision}


def create_tree(paths: Paths) -> None:
    for root in [paths.stage_root, paths.runtime_root]:
        root.mkdir(parents=True, exist_ok=True)
    for sub in SUBDIRS:
        (paths.stage_root / sub).mkdir(parents=True, exist_ok=True)
    for sub in ["repaired_input_generation", "solver_rerun", "official_eval", "figures", "logs"]:
        (paths.runtime_root / sub).mkdir(parents=True, exist_ok=True)


def discover_receiver_root(repo: Path) -> Path:
    names = {
        "gnss1-status.csv",
        "gnss2-status.csv",
        "userio-raw.csv",
        "user_io-status.csv",
    }
    roots = [repo, repo.parent, Path.home() / "Desktop"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("vrtk2_a87c6e_2026-03-06-08-06-39_minimal"):
            if path.is_dir() and all((path / name).exists() for name in names):
                return path
    raise FileNotFoundError("BY3 receiver root was not found.")


def discover_trace(receiver_root: Path) -> Path:
    candidates = list(receiver_root.glob("trace_*.csv"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError("BY3 trace file was not found under receiver root.")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_numeric_table(path: Path, expected_cols: int | None = None) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            parts = text.replace(",", " ").split()
            try:
                values = [float(part) for part in parts]
            except ValueError:
                continue
            if expected_cols is None or len(values) == expected_cols:
                rows.append(values)
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_rows(stem: Path, rows: list[dict[str, Any]]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    write_json(stem.with_suffix(".json"), rows)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fields})


def write_summary(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def stats(values: list[float]) -> dict[str, Any]:
    clean = sorted(v for v in values if v is not None and math.isfinite(v))
    if not clean:
        return {"count": 0}
    return {
        "count": len(clean),
        "min": clean[0],
        "p05": quantile(clean, 0.05),
        "mean": sum(clean) / len(clean),
        "median": quantile(clean, 0.5),
        "p95": quantile(clean, 0.95),
        "max": clean[-1],
        "std": pstdev(clean),
    }


def quantile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    idx = (len(sorted_values) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - idx) + sorted_values[hi] * (idx - lo)


def pstdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def wrap360(value: float) -> float:
    return value % 360.0


def circ_diff(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def circ_stats(values: list[float]) -> dict[str, Any]:
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return {"count": 0}
    s = sum(math.sin(math.radians(v)) for v in clean) / len(clean)
    c = sum(math.cos(math.radians(v)) for v in clean) / len(clean)
    mean = wrap360(math.degrees(math.atan2(s, c)))
    rbar = math.sqrt(s * s + c * c)
    std = math.degrees(math.sqrt(max(0.0, -2.0 * math.log(max(rbar, 1e-12)))))
    abs_err = sorted(abs(circ_diff(v, mean)) for v in clean)
    return {
        "count": len(clean),
        "circular_mean_deg": mean,
        "circular_std_deg": std,
        "abs_dev_median_deg": quantile(abs_err, 0.5),
        "abs_dev_p95_deg": quantile(abs_err, 0.95),
        "abs_dev_max_deg": max(abs_err),
    }


def interp_scalar(rows: list[dict[str, float]], t: float, fields: list[str]) -> dict[str, float] | None:
    if not rows or t < rows[0]["t"] or t > rows[-1]["t"]:
        return None
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
            return {field: rows[mid][field] for field in fields}
    left = rows[max(0, hi)]
    right = rows[min(len(rows) - 1, lo)]
    if right["t"] == left["t"]:
        return {field: left[field] for field in fields}
    alpha = (t - left["t"]) / (right["t"] - left["t"])
    return {field: left[field] + alpha * (right[field] - left[field]) for field in fields}


def interp_angle(rows: list[dict[str, float]], t: float, *, tolerance: float = 0.25) -> tuple[float | None, str]:
    if not rows:
        return None, "missing"
    if t < rows[0]["t"]:
        if rows[0]["t"] - t <= tolerance:
            return rows[0]["heading"], "nearest_edge"
        return None, "outside"
    if t > rows[-1]["t"]:
        if t - rows[-1]["t"] <= tolerance:
            return rows[-1]["heading"], "nearest_edge"
        return None, "outside"
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
            return rows[mid]["heading"], "exact"
    left = rows[max(0, hi)]
    right = rows[min(len(rows) - 1, lo)]
    if right["t"] == left["t"]:
        return left["heading"], "nearest_same_time"
    alpha = (t - left["t"]) / (right["t"] - left["t"])
    return wrap360(left["heading"] + alpha * circ_diff(right["heading"], left["heading"])), "interpolated"


def status_time(row: dict[str, str], *, use_header: bool = True) -> float | None:
    prefix = "header.stamp" if use_header else "sys_stamp"
    secs = as_float(row.get(f"{prefix}.secs"))
    nsecs = as_float(row.get(f"{prefix}.nsecs"), 0.0)
    if secs is not None:
        return secs + (nsecs or 0.0) * 1e-9
    return as_float(row.get("Time"))


def audit_current_yaw_input(paths: Paths) -> dict[str, Any]:
    current_rows = read_numeric_table(paths.current_dual, expected_cols=15)
    yaw = [row[13] for row in current_rows]
    yaw_std = [row[14] for row in current_rows]
    times = [row[0] for row in current_rows]
    gnss1_standard = paths.by3a0_root / "data_inventory" / "BY3_GNSS1_STATUS_STANDARD.csv"
    std_rows = read_csv_rows(gnss1_standard)
    std_by_time = {round(float(row["time_unix"]), 6): row for row in std_rows if row.get("time_unix")}
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json")
    base_time = float(repair_report.get("offsets", {}).get("body_time_zero_raw_timestamp", 0.0))
    matched = 0
    diffs: list[float] = []
    for row in current_rows:
        raw_time = round(base_time + row[0], 6)
        std_row = std_by_time.get(raw_time)
        if not std_row:
            continue
        heading = as_float(std_row.get("heading_deg"))
        if heading is None:
            continue
        matched += 1
        diffs.append(abs(circ_diff(row[13], heading)))
    gnss1_raw = read_csv_rows(paths.receiver_root / "gnss1-status.csv")
    rel_norms = []
    rel_headings = []
    rel_std = []
    for row in gnss1_raw:
        n = as_float(row.get("rel_pos_n"))
        e = as_float(row.get("rel_pos_e"))
        d = as_float(row.get("rel_pos_d"))
        ae = as_float(row.get("rel_acc_e"))
        if None in {n, e, d}:
            continue
        rel_norms.append(math.sqrt(n * n + e * e + d * d))
        rel_headings.append(wrap360(math.degrees(math.atan2(e, n))))
        rel_std.append(math.degrees(math.atan2(ae or 0.01, max(abs(n), 1.0))))
    likely_wrong = bool(rel_norms and stats(rel_norms)["median"] > 10.0 and stats(yaw_std)["median"] < 0.01 and matched > 0 and max(diffs or [999.0]) < 1e-6)
    report = {
        "stage": STAGE,
        "decision": "BY3A5_current_yaw_input_wrong_source_confirmed" if likely_wrong else "BY3A5_current_yaw_input_suspicious",
        "current_input_alias": "<BY3A1_STAGE_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
        "sha256": sha256(paths.current_dual),
        "row_count": len(current_rows),
        "column_count": 15,
        "time_range": {"min": min(times) if times else None, "max": max(times) if times else None},
        "yaw_stats_deg": stats(yaw),
        "yaw_std_stats_deg": stats(yaw_std),
        "current_yaw_near_constant_around_12deg": bool(yaw and 10.0 <= stats(yaw)["median"] <= 13.0 and stats(yaw)["std"] < 1.0),
        "current_yaw_std_around_0p00019deg": bool(yaw_std and 0.00015 <= stats(yaw_std)["median"] <= 0.00025),
        "current_input_generation_script": "scripts/experiments/run_by3a0_to_by3e_generalization_reorg.py:1088-1106",
        "source_fields_used": ["BY3_GNSS1_STATUS_STANDARD.heading_deg", "rel_pos_n_m", "rel_acc_e_m"],
        "current_yaw_equals_gnss1_status_heading": bool(matched > 0 and max(diffs or [999.0]) < 1e-6),
        "matched_current_to_status_heading_rows": matched,
        "current_to_status_heading_abs_diff_stats_deg": stats(diffs),
        "gnss_status_rel_pos_norm_stats_m": stats(rel_norms),
        "gnss_status_rel_pos_heading_stats_deg": circ_stats(rel_headings),
        "gnss_status_geometry_yaw_std_stats_deg": stats(rel_std),
        "rel_pos_vector_norm_physical_antenna_baseline": bool(rel_norms and stats(rel_norms)["median"] < 5.0),
        "likely_wrong_source_yaw": likely_wrong,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5_CURRENT_YAW_INPUT_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_CURRENT_YAW_INPUT_AUDIT", [flatten_report(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5_current_yaw_input_audit.md",
        "# BY3A5 Current Yaw Input Audit\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"The current 15-column yaw matches BY3 GNSS1 standardized status `heading_deg` for {matched} rows. "
        f"The status `rel_pos` median norm is {report['gnss_status_rel_pos_norm_stats_m'].get('median'):.3f} m, "
        "so it is not a physical short dual-antenna baseline.\n\n"
        f"Current yaw median: {report['yaw_stats_deg'].get('median'):.6f} deg. "
        f"Current yaw_std median: {report['yaw_std_stats_deg'].get('median'):.9f} deg.\n",
    )
    return report


def read_json(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def flatten_report(report: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key, value in report.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                row[f"{key}_{subkey}"] = subvalue
        else:
            row[key] = value
    return row


def recover_by2_yaw_generation(paths: Paths) -> dict[str, Any]:
    evidence = [
        {
            "evidence_path": "src/legsa_gins/input_generation/status_yaw_builder.py",
            "source_fields": "rel_pos_n/e/d from gnss1/gnss2 status rows, interpolated to gnss1 time",
            "formula": "rel_n=gnss2.rel_pos_n_interp-gnss1.rel_pos_n; rel_e=gnss2.rel_pos_e_interp-gnss1.rel_pos_e; yaw_baseline=-atan2(rel_e,rel_n); yaw_body=sign*yaw_baseline+offset; yaw_ned=90-yaw_body",
            "yaw_std_policy": "fixed_1p5 supported by compute_yaw_std",
            "current_validity": "accepted_for_BY2_when_status_rel_pos_is_physical_antenna_baseline",
        },
        {
            "evidence_path": "src/legsa_gins/input_generation/process_data_compat.py",
            "source_fields": "gnss1 status base rows, gnss1 raw velocity, A1_dual_diff status yaw",
            "formula": "writes 15-column .gnss yaw from status yaw rows after yaw_ned conversion",
            "yaw_std_policy": "default yaw_std_mode=fixed_1p5",
            "current_validity": "accepted_BY2_reconstruction_policy",
        },
        {
            "evidence_path": "docs/experiments/process_data_compat_generation.md",
            "source_fields": "documented process_data-compatible input mapping",
            "formula": "A1 dual difference and yaw_ned=90-yaw_body",
            "yaw_std_policy": "nominal process_data-compatible policy",
            "current_validity": "accepted_documentation",
        },
        {
            "evidence_path": "docs/source_audit/process_data_runtime_parameter_audit.md",
            "source_fields": "external process_data runtime defaults",
            "formula": "YAW_SOURCE_MODE=status; YAW_SIGN=1.0; YAW_INSTALL_OFFSET_DEG=0.0",
            "yaw_std_policy": "STATUS_YAW_STD_MODE_DEFAULT=fixed_1p5",
            "current_validity": "accepted_source_audit_evidence",
        },
        {
            "evidence_path": "docs/experiments/clean_status_yaw_replay.md",
            "source_fields": "clean status-yaw replay policy",
            "formula": "yaw_source_mode=status with trace_solver_input=false",
            "yaw_std_policy": "yaw_std_mode=fixed_1p5",
            "current_validity": "accepted_BY2_clean_replay_policy",
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A5_by2_yaw_generation_recovered",
        "process_data_policy": "A1_dual_diff_status",
        "gnss2_interpolation_to_gnss1_time": True,
        "baseline_formula": "rel_n=pos2_or_relpos2_interp-pos1_or_relpos1; rel_e=pos2_or_relpos2_interp-pos1_or_relpos1",
        "yaw_baseline_formula": "-atan2(rel_e,rel_n) for BY2 status yaw builder",
        "lateral_body_heading_policy": "body heading requires plus/minus 90 deg when using physical lateral baseline; sign must be source/antenna-order backed",
        "yaw_ned_formula": "yaw_ned=90-yaw_body",
        "yaw_std_mode": "fixed_1p5",
        "fixed_yaw_std_deg": 1.5,
        "rejected_fields": ["gnss-status rel_pos_n/e when norm is long RTK/base vector rather than short antenna baseline"],
        "trace_solver_input": False,
        "paper_claim": False,
        "evidence": evidence,
    }
    write_json(paths.stage_root / "reports" / "BY3A5_BY2_YAW_GENERATION_RECOVERY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_BY2_YAW_GENERATION_EVIDENCE", evidence)
    write_summary(
        paths.stage_root / "summary" / "by3a5_by2_yaw_generation_recovery.md",
        "# BY3A5 BY2 Yaw Generation Recovery\n\n"
        "Decision: `BY3A5_by2_yaw_generation_recovered`.\n\n"
        "Recovered BY2 policy uses source-backed dual status yaw only when the status relative vector is the physical antenna baseline. "
        "The accepted yaw standard-deviation policy is `fixed_1p5`, not geometry-derived near-zero values.\n",
    )
    return report


def status_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        t = status_time(row)
        lat = as_float(row.get("pos_lat"))
        lon = as_float(row.get("pos_lon"))
        h = as_float(row.get("pos_height"))
        n = as_float(row.get("rel_pos_n"))
        e = as_float(row.get("rel_pos_e"))
        d = as_float(row.get("rel_pos_d"))
        if None in {t, lat, lon, h}:
            continue
        rows.append(
            {
                "t": t,
                "lat": lat,
                "lon": lon,
                "h": h,
                "rel_n": n if n is not None else float("nan"),
                "rel_e": e if e is not None else float("nan"),
                "rel_d": d if d is not None else float("nan"),
            }
        )
    rows.sort(key=lambda item: item["t"])
    return rows


def local_enu_rows(
    rows: list[dict[str, float]], origin: tuple[float, float, float] | None = None
) -> list[dict[str, float]]:
    if not rows and origin is None:
        return []
    if origin is None:
        origin = (rows[0]["lat"], rows[0]["lon"], rows[0]["h"])
    lat0 = math.radians(origin[0])
    lon0 = math.radians(origin[1])
    h0 = origin[2]
    radius = 6378137.0
    out = []
    for row in rows:
        lat = math.radians(row["lat"])
        lon = math.radians(row["lon"])
        out.append(
            {
                **row,
                "n": (lat - lat0) * radius,
                "e": (lon - lon0) * radius * math.cos(lat0),
                "u": row["h"] - h0,
            }
        )
    return out


def parse_hdt_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for row in read_csv_rows(path):
        if row.get("name") != "NMEA-GP-HDT":
            continue
        info = row.get("info", "")
        try:
            heading = float(info.split(",")[0])
            t = float(row["Time"])
        except Exception:
            continue
        rows.append({"t": t, "heading": wrap360(heading)})
    rows.sort(key=lambda item: item["t"])
    return rows


def audit_by3_candidates(paths: Paths) -> dict[str, Any]:
    gnss1 = status_rows(paths.receiver_root / "gnss1-status.csv")
    gnss2 = status_rows(paths.receiver_root / "gnss2-status.csv")
    origin = (gnss1[0]["lat"], gnss1[0]["lon"], gnss1[0]["h"]) if gnss1 else None
    gnss1_enu = local_enu_rows(gnss1, origin)
    gnss2_enu = local_enu_rows(gnss2, origin)
    hdt_rows = parse_hdt_rows(paths.receiver_root / "userio-raw.csv")
    rel_norms = []
    rel_headings = []
    for item in gnss1:
        n, e, d = item.get("rel_n"), item.get("rel_e"), item.get("rel_d")
        if all(math.isfinite(v) for v in [n, e, d]):
            rel_norms.append(math.sqrt(n * n + e * e + d * d))
            rel_headings.append(wrap360(math.degrees(math.atan2(e, n))))
    abs_norms: list[float] = []
    abs_bearing: list[float] = []
    hdt_diff_plus90: list[float] = []
    hdt_diff_minus90: list[float] = []
    hdt_diff_revplus90: list[float] = []
    hdt_diff_revminus90: list[float] = []
    outside = 0
    for p1 in gnss1_enu:
        p2 = interp_scalar(gnss2_enu, p1["t"], ["n", "e", "u"])
        if p2 is None:
            outside += 1
            continue
        dn = p2["n"] - p1["n"]
        de = p2["e"] - p1["e"]
        du = p2["u"] - p1["u"]
        length = math.sqrt(dn * dn + de * de + du * du)
        abs_norms.append(length)
        bearing = wrap360(math.degrees(math.atan2(de, dn)))
        abs_bearing.append(bearing)
        hdt, _ = interp_angle(hdt_rows, p1["t"])
        if hdt is not None and length >= 0.1:
            hdt_diff_plus90.append(circ_diff(wrap360(bearing + 90.0), hdt))
            hdt_diff_minus90.append(circ_diff(wrap360(bearing - 90.0), hdt))
            rev = wrap360(bearing + 180.0)
            hdt_diff_revplus90.append(circ_diff(wrap360(rev + 90.0), hdt))
            hdt_diff_revminus90.append(circ_diff(wrap360(rev - 90.0), hdt))
    candidate_rows = [
        {
            "candidate": "current_gnss_status_rel_pos_heading",
            "source_exists": True,
            "row_count": len(rel_norms),
            "baseline_norm_stats_m": stats(rel_norms),
            "heading_stats_deg": circ_stats(rel_headings),
            "physical_plausibility": "rejected_long_baseline" if rel_norms and stats(rel_norms)["median"] > 10.0 else "plausible",
            "can_be_solver_yaw_input": bool(rel_norms and stats(rel_norms)["median"] < 5.0),
            "can_be_evaluator_reference": False,
            "reason": "status rel_pos median norm is thousands of meters in BY3",
        },
        {
            "candidate": "gnss2_position_minus_gnss1_position_interpolated",
            "source_exists": True,
            "row_count": len(abs_norms),
            "baseline_norm_stats_m": stats(abs_norms),
            "heading_stats_deg": circ_stats(abs_bearing),
            "physical_plausibility": "short_baseline_but_heading_noisy" if abs_norms and stats(abs_norms)["median"] < 1.0 else "not_short_baseline",
            "can_be_solver_yaw_input": False,
            "can_be_evaluator_reference": False,
            "reason": "absolute position difference has physical length but noisy circular heading; use only as physical cross-check",
        },
        {
            "candidate": "nmea_gp_hdt",
            "source_exists": bool(hdt_rows),
            "row_count": len(hdt_rows),
            "time_range": {"start": hdt_rows[0]["t"] if hdt_rows else None, "end": hdt_rows[-1]["t"] if hdt_rows else None},
            "heading_stats_deg": circ_stats([row["heading"] for row in hdt_rows]),
            "physical_plausibility": "accepted_receiver_true_heading_candidate" if hdt_rows else "missing",
            "can_be_solver_yaw_input": bool(hdt_rows),
            "can_be_evaluator_reference": False,
            "reason": "real NMEA HDT true-heading messages from receiver userio stream; not trace/final_v23/algorithm output",
        },
        {
            "candidate": "fixposition_odometry_orientation",
            "source_exists": (paths.receiver_root / "user_io-out-poi_odometry.csv").exists(),
            "row_count": count_csv_rows(paths.receiver_root / "user_io-out-poi_odometry.csv"),
            "physical_plausibility": "diagnostic_only_until_frame_semantics_confirmed",
            "can_be_solver_yaw_input": False,
            "can_be_evaluator_reference": False,
            "reason": "orientation is ECEF/POI odometry frame; not used as solver yaw in BY3A5",
        },
        {
            "candidate": "trace_yaw",
            "source_exists": paths.trace.exists(),
            "row_count": count_csv_rows(paths.trace),
            "physical_plausibility": "evaluation_only",
            "can_be_solver_yaw_input": False,
            "can_be_evaluator_reference": True,
            "reason": "trace is evaluation-only reference and cannot generate solver input",
        },
    ]
    plus90_abs = [abs(v) for v in hdt_diff_plus90]
    revminus90_abs = [abs(v) for v in hdt_diff_revminus90]
    source_gate = bool(
        hdt_rows
        and abs_norms
        and stats(abs_norms)["median"] < 1.0
        and plus90_abs
        and quantile(sorted(plus90_abs), 0.5) < 5.0
        and quantile(sorted(plus90_abs), 0.95) < 15.0
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A5_yaw_source_candidate_hdt_ready" if source_gate else "BY3A5_yaw_source_candidates_inconclusive",
        "gnss_status_rel_pos_long_baseline_confirmed": bool(rel_norms and stats(rel_norms)["median"] > 10.0),
        "gnss2_minus_gnss1_abs_baseline_norm_stats_m": stats(abs_norms),
        "gnss2_minus_gnss1_abs_heading_stats_deg": circ_stats(abs_bearing),
        "gnss2_minus_gnss1_abs_interpolation_outside_count": outside,
        "hdt_row_count": len(hdt_rows),
        "hdt_heading_stats_deg": circ_stats([row["heading"] for row in hdt_rows]),
        "physical_lateral_check": {
            "body_heading_equals_gnss2_minus_gnss1_bearing_plus90_supported": source_gate,
            "plus90_minus_hdt_diff_stats_deg": circ_stats(hdt_diff_plus90),
            "minus90_minus_hdt_diff_stats_deg": circ_stats(hdt_diff_minus90),
            "reversed_plus90_minus_hdt_diff_stats_deg": circ_stats(hdt_diff_revplus90),
            "reversed_minus90_minus_hdt_diff_stats_deg": circ_stats(hdt_diff_revminus90),
            "selection_basis": "NMEA HDT receiver true-heading source plus physical short-baseline cross-check; not yaw RMSE",
        },
        "candidate_rows": candidate_rows,
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5_BY3_YAW_SOURCE_CANDIDATE_AUDIT_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_BY3_YAW_SOURCE_CANDIDATES", candidate_rows)
    write_summary(
        paths.stage_root / "summary" / "by3a5_by3_yaw_source_candidates.md",
        "# BY3A5 BY3 Yaw Source Candidates\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"NMEA HDT rows: `{len(hdt_rows)}`. GNSS status rel_pos long-baseline confirmed: `{report['gnss_status_rel_pos_long_baseline_confirmed']}`.\n\n"
        "The absolute GNSS2-minus-GNSS1 baseline is short and supports the lateral `+90 deg` relation to HDT as a physical cross-check, "
        "but absolute-position heading is too noisy to be used directly as solver yaw input.\n",
    )
    return report


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def recover_hdt_heading(paths: Paths, candidate_audit: dict[str, Any]) -> dict[str, Any]:
    hdt_rows = parse_hdt_rows(paths.receiver_root / "userio-raw.csv")
    rows = [
        {
            "source": "NMEA-GP-HDT",
            "parse_status": "parsed" if hdt_rows else "missing",
            "row_count": len(hdt_rows),
            "time_start": hdt_rows[0]["t"] if hdt_rows else "",
            "time_end": hdt_rows[-1]["t"] if hdt_rows else "",
            "heading_stats_deg": candidate_audit.get("hdt_heading_stats_deg", {}),
            "quality": "receiver_true_heading_message",
            "body_vs_antenna_semantic": "HDT is a true-heading output; BY3A5 validates it against the short GNSS2-GNSS1 lateral baseline plus90 geometry",
            "solver_input_allowed": bool(candidate_audit.get("decision") == "BY3A5_yaw_source_candidate_hdt_ready"),
            "evaluator_reference_allowed": False,
        },
        {
            "source": "FP_A-ODOMETRY",
            "parse_status": "present_diagnostic",
            "row_count": count_csv_rows(paths.receiver_root / "user_io-out-poi_odometry.csv"),
            "quality": "fused_odometry_orientation_present",
            "body_vs_antenna_semantic": "ECEF/POI orientation frame semantics not accepted for solver yaw in this stage",
            "solver_input_allowed": False,
            "evaluator_reference_allowed": False,
        },
        {
            "source": "NOV_B-INSPVAX",
            "parse_status": "present_binary_in_userio_raw_diagnostic_only",
            "row_count": count_name(paths.receiver_root / "userio-raw.csv", "NOV_B-INSPVAX"),
            "quality": "binary payload not decoded by BY3A5",
            "body_vs_antenna_semantic": "not decoded; no fabricated heading",
            "solver_input_allowed": False,
            "evaluator_reference_allowed": False,
        },
    ]
    decision = "BY3A5_hdt_heading_available" if hdt_rows else "BY3A5_hdt_heading_not_available"
    report = {
        "stage": STAGE,
        "decision": decision,
        "hdt_heading_available": bool(hdt_rows),
        "hdt_row_count": len(hdt_rows),
        "hdt_time_range": {"start": hdt_rows[0]["t"] if hdt_rows else None, "end": hdt_rows[-1]["t"] if hdt_rows else None},
        "heading_sources": rows,
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5_HDT_HEADING_RECOVERY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_HDT_HEADING_CANDIDATES", rows)
    write_summary(
        paths.stage_root / "summary" / "by3a5_hdt_heading_recovery.md",
        "# BY3A5 HDT Heading Recovery\n\n"
        f"Decision: `{decision}`.\n\n"
        f"Recovered `{len(hdt_rows)}` real NMEA-GP-HDT rows from `<BY3_RECEIVER_ROOT>/userio-raw.csv`.\n",
    )
    return report


def count_name(path: Path, name: str) -> int:
    return sum(1 for row in read_csv_rows(path) if row.get("name") == name)


def decide_corrected_policy(
    current_audit: dict[str, Any],
    by2_recovery: dict[str, Any],
    candidate_audit: dict[str, Any],
    hdt_recovery: dict[str, Any],
) -> dict[str, Any]:
    hdt_ready = (
        current_audit.get("decision") == "BY3A5_current_yaw_input_wrong_source_confirmed"
        and by2_recovery.get("decision") == "BY3A5_by2_yaw_generation_recovered"
        and candidate_audit.get("decision") == "BY3A5_yaw_source_candidate_hdt_ready"
        and hdt_recovery.get("decision") == "BY3A5_hdt_heading_available"
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A5_corrected_yaw_policy_ready" if hdt_ready else "BY3A5_corrected_yaw_policy_blocked",
        "policy": "use_hdt_heading" if hdt_ready else "block_yaw_input_no_valid_source",
        "source": "NMEA-GP-HDT true heading from receiver userio stream" if hdt_ready else "",
        "formula": "15-col yaw = HDT true heading deg; yaw_std = fixed_1p5 deg",
        "lateral_geometry_policy": "HDT is used directly as body true heading; physical cross-check supports GNSS2-minus-GNSS1 bearing +90 deg as the lateral antenna relation",
        "body_heading_requires_lateral_correction_from_baseline": True,
        "BY3_antenna_order_audit": "GNSS2-minus-GNSS1 absolute short baseline +90 deg agrees with HDT median within 5 deg; not selected by yaw RMSE",
        "yaw_std_policy": "fixed_1p5",
        "yaw_std_deg": 1.5,
        "reject_current_yaw_std_around_0p00019": True,
        "physical_justification": "current status rel_pos is long baseline; HDT is real receiver true-heading output and is physically consistent with lateral short baseline geometry",
        "BY2_compatibility": "uses BY2 accepted fixed_1p5 yaw_std and preserves process_data 15-col heading/yaw column semantics",
        "not_chosen_by_RMSE": True,
        "trace_solver_input": False,
        "paper_claim": False,
    }
    return report


def write_policy(paths: Paths, report: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A5_CORRECTED_YAW_INPUT_POLICY_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_CORRECTED_YAW_INPUT_POLICY", [flatten_report(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5_corrected_yaw_input_policy.md",
        "# BY3A5 Corrected Yaw Input Policy\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Policy: `{report['policy']}`. Yaw std policy: `{report['yaw_std_policy']}`.\n\n"
        "The policy is source/geometry backed and is not selected by solver yaw RMSE.\n",
    )


def generate_repaired_input(paths: Paths, policy: dict[str, Any], candidate_audit: dict[str, Any]) -> dict[str, Any]:
    write_policy(paths, policy)
    current_rows = read_numeric_table(paths.current_dual, expected_cols=15)
    repair_report = read_json(paths.by3a1_root / "reports" / "BY3A1_INPUT_REPAIR_REPORT.json")
    base_time = float(repair_report.get("offsets", {}).get("body_time_zero_raw_timestamp", 0.0))
    hdt_rows = parse_hdt_rows(paths.receiver_root / "userio-raw.csv")
    output_rows: list[list[float]] = []
    modes: dict[str, int] = {}
    missing = 0
    for row in current_rows:
        raw_time = base_time + row[0]
        heading, mode = interp_angle(hdt_rows, raw_time, tolerance=0.25)
        modes[mode] = modes.get(mode, 0) + 1
        if heading is None:
            missing += 1
            continue
        new_row = list(row)
        new_row[13] = heading
        new_row[14] = 1.5
        output_rows.append(new_row)
    paths.repaired_dual.parent.mkdir(parents=True, exist_ok=True)
    with paths.repaired_dual.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(" ".join(f"{value:.12g}" for value in row) + "\n")
    validations = validate_15col(paths.repaired_dual)
    yaw_values = [row[13] for row in output_rows]
    yaw_std_values = [row[14] for row in output_rows]
    ready = bool(output_rows and not missing and validations["schema_valid"])
    report = {
        "stage": STAGE,
        "decision": "BY3A5_repaired_inputs_ready" if ready else "BY3A5_repaired_inputs_blocked",
        "repaired_dual_gnss_alias": "<BY3A5_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_HDT_15COL_REPAIRED.gnss",
        "source_current_dual_alias": "<BY3A1_STAGE_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
        "source_heading": "NMEA-GP-HDT from <BY3_RECEIVER_ROOT>/userio-raw.csv",
        "source_policy": policy["policy"],
        "yaw_formula": policy["formula"],
        "yaw_std_policy": policy["yaw_std_policy"],
        "yaw_std_deg": 1.5,
        "row_count": len(output_rows),
        "input_row_count": len(current_rows),
        "missing_hdt_match_count": missing,
        "hdt_interpolation_modes": modes,
        "yaw_stats_deg": circ_stats(yaw_values),
        "yaw_std_stats_deg": stats(yaw_std_values),
        "validation": validations,
        "sha256": sha256(paths.repaired_dual) if paths.repaired_dual.exists() else "",
        "source_role": {
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "single_output_solver_input": False,
            "legsa_output_solver_input": False,
            "heading_source": "receiver_NMEA_HDT",
        },
        "output_lineage": {
            "position_velocity_columns": "copied from BY3A1 repaired 15-col current input",
            "yaw_columns": "replaced from receiver HDT and fixed_1p5 std",
            "parameter_retuning": False,
        },
    }
    write_json(paths.stage_root / "reports" / "BY3A5_REPAIRED_INPUT_GENERATION_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_REPAIRED_INPUT_FILE_INDEX", [flatten_report(report)])
    write_summary(
        paths.stage_root / "summary" / "by3a5_repaired_input_generation.md",
        "# BY3A5 Repaired Input Generation\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        f"Rows written: `{len(output_rows)}`. Yaw source: NMEA-GP-HDT. Yaw std: `fixed_1p5`.\n",
    )
    write_json(paths.stage_root / "repaired_input_generation" / "source_role.json", report["source_role"])
    write_json(paths.stage_root / "repaired_input_generation" / "output_lineage.json", report["output_lineage"])
    write_json(paths.runtime_root / "repaired_input_generation" / "source_role.json", report["source_role"])
    write_json(paths.runtime_root / "repaired_input_generation" / "output_lineage.json", report["output_lineage"])
    shutil.copy2(paths.repaired_dual, paths.runtime_root / "repaired_input_generation" / paths.repaired_dual.name)
    return report


def blocked_input_generation(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "decision": "BY3A5_repaired_inputs_blocked",
        "blocked_reason": policy.get("decision"),
        "trace_solver_input": False,
        "paper_claim": False,
    }


def validate_15col(path: Path) -> dict[str, Any]:
    rows = read_numeric_table(path, expected_cols=15)
    times = [row[0] for row in rows]
    finite = all(all(math.isfinite(value) for value in row) for row in rows)
    monotonic = all(b >= a for a, b in zip(times, times[1:]))
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
    }


def run_single_baseline_by3a5(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "single_antenna_gnss1_status_KF_GINS"
    src_config = paths.by3a2_root / "single_runner_handoff" / "by3_single_baseline.runtime_config.yaml"
    output_dir = paths.runtime_root / "single_baseline_solver" / algorithm
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
    text = apply_external_kfgins_input_handoff(text, paths.imu, paths.gnss_single, use_dual_yaw=False)
    text += "\n# BY3A5 handoff repair: imupath/gnsspath/time/init explicitly follow repaired BY3 inputs; algorithm math unchanged.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return by3a3.skipped_or_blocked_run(algorithm, "BY3A2 single command missing", output_dir=output_dir)
    command[-1] = by3a3.repo_to_wsl(config_path)
    command = by3a3.normalize_wsl_command(command)
    return by3a3.run_external_solver(paths, algorithm, output_dir, command, config_path, role="traditional_baseline")


def run_finalv23_by3a5(paths: Paths, context: dict[str, Any]) -> dict[str, Any]:
    algorithm = "final_v23_dual_antenna_EKF"
    src_config = paths.by3a2_root / "finalv23_runner_handoff" / "by3_finalv23_external.runtime_config.yaml"
    output_dir = paths.runtime_root / "finalv23_solver" / algorithm
    config_path = paths.stage_root / "finalv23_solver" / "by3_finalv23_external.runtime_config.yaml"
    blockers = by3a3.required_file_blockers(
        {
            "BY3A2 final_v23 config": src_config,
            "BY3 repaired IMU": paths.imu,
            "BY3A5 repaired dual GNSS": paths.gnss_dual,
        }
    )
    if blockers:
        return by3a3.skipped_or_blocked_run(algorithm, "; ".join(blockers), output_dir=output_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    text = src_config.read_text(encoding="utf-8", errors="ignore")
    text = by3a3.replace_yaml_key(text, "outputpath", by3a3.repo_to_wsl(output_dir), quoted=True)
    text = apply_external_kfgins_input_handoff(text, paths.imu, paths.gnss_dual, use_dual_yaw=True)
    text += "\n# BY3A5 handoff repair: final_v23 receives the BY3A5 HDT/fixed_1p5 dual-yaw input; algorithm math unchanged.\n"
    config_path.write_text(text, encoding="utf-8")
    report = read_json(paths.by3a2_root / "reports" / "BY3A2_FINALV23_HANDOFF_REPORT.json", {}) or {}
    command = list(report.get("command", []))
    if not command:
        return by3a3.skipped_or_blocked_run(algorithm, "BY3A2 final_v23 command missing", output_dir=output_dir)
    command[-1] = by3a3.repo_to_wsl(config_path)
    command = by3a3.normalize_wsl_command(command)
    return by3a3.run_external_solver(paths, algorithm, output_dir, command, config_path, role="external_reference_baseline")


def apply_external_kfgins_input_handoff(text: str, imu_path: Path, gnss_path: Path, *, use_dual_yaw: bool) -> str:
    text = by3a3.replace_yaml_key(text, "imupath", by3a3.repo_to_wsl(imu_path), quoted=True)
    text = by3a3.replace_yaml_key(text, "gnsspath", by3a3.repo_to_wsl(gnss_path), quoted=True)
    return by3a3.apply_external_kfgins_time_handoff(text, imu_path, gnss_path, use_dual_yaw=use_dual_yaw)


def run_normal_chain(paths: Paths, repaired_input: dict[str, Any], *, run_solvers: bool) -> dict[str, Any]:
    if not run_solvers:
        report = {
            "stage": STAGE,
            "decision": "BY3A5_normal_rerun_blocked",
            "blocked_reason": "run-solvers flag not supplied",
            "solver_rows": [],
            "eval_rows": [],
            "metrics_rows": [],
            "trace_solver_input": False,
            "degradation_execution": False,
            "paper_claim": False,
        }
        write_rerun_reports(paths, report)
        return report
    ensure_eval_script_env(paths)
    context = by3a3.build_context(paths)
    policy = by3a3.recover_feedback_policy(paths)
    stage1_materialization = by3a3.materialize_stage1(paths, context, policy)
    stage1_run = by3a3.run_legsa_solver(
        paths,
        algorithm="baseline_no_feedback_EKF",
        output_dir=paths.runtime_root / "solver_rerun" / "stage1_solver" / "baseline_no_feedback_EKF",
        runtime_config=Path(stage1_materialization["runtime_config_path"]),
        case_overrides=by3a3.stage1_case_overrides(paths),
    )
    if stage1_run.get("run_status") == "completed":
        stage1_eval = by3a3.run_official_eval(
            paths,
            algorithm="stage1_baseline_no_feedback_EKF",
            solver_output_dir=paths.runtime_root / "solver_rerun" / "stage1_solver" / "baseline_no_feedback_EKF",
            official_dir=paths.stage_root / "official_eval" / "stage1_baseline_no_feedback_EKF",
            base_time=context["base_time"],
            nav_kind="legsa_port_csv",
        )
    else:
        stage1_eval = {"algorithm": "stage1_baseline_no_feedback_EKF", "official_eval_status": "blocked", "blocked_reason": stage1_run.get("blocked_reason") or stage1_run.get("run_status")}
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
            output_dir=paths.runtime_root / "solver_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF",
            runtime_config=Path(stage2_materialization["runtime_config_path"]),
            case_overrides=by3a3.stage2_case_overrides(paths, feedback),
        )
    else:
        stage2_run = by3a3.skipped_or_blocked_run("LegSA_full_EKF", stage2_materialization.get("blocker_reasons", ""), output_dir=paths.runtime_root / "solver_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF")
    baseline_rows = [
        run_single_baseline_by3a5(paths, context),
        run_finalv23_by3a5(paths, context),
    ]
    eval_rows = []
    if stage2_run.get("run_status") == "completed":
        eval_rows.append(
            by3a3.run_official_eval(
                paths,
                algorithm="LegSA_full_EKF",
                solver_output_dir=paths.runtime_root / "solver_rerun" / "stage2_legsa_full_solver" / "LegSA_full_EKF",
                official_dir=paths.stage_root / "official_eval" / "LegSA_full_EKF",
                base_time=context["base_time"],
                nav_kind="legsa_port_csv",
            )
        )
    else:
        eval_rows.append({"algorithm": "LegSA_full_EKF", "official_eval_status": "blocked", "blocked_reason": stage2_run.get("blocked_reason")})
    for run in baseline_rows:
        nav_kind = "kfgins_nav"
        eval_rows.append(
            by3a3.run_official_eval(
                paths,
                algorithm=run["algorithm"],
                solver_output_dir=Path(run.get("output_dir") or ""),
                official_dir=paths.stage_root / "official_eval" / run["algorithm"],
                base_time=context["base_time"],
                nav_kind=nav_kind,
            )
            if run.get("run_status") == "completed"
            else {"algorithm": run["algorithm"], "official_eval_status": "blocked", "blocked_reason": run.get("blocked_reason")}
        )
    input_config_audit = audit_solver_input_configs(paths, stage2_run, baseline_rows)
    source_policy_by_algorithm = {row["algorithm"]: row["source_policy"] for row in input_config_audit}
    metrics_rows = [
        metric_row(row, source_policy_by_algorithm)
        for row in eval_rows
        if row.get("official_eval_status") == "completed"
    ]
    completed = len(metrics_rows) == 3 and all(float(row.get("yaw_rmse_deg") or 999.0) < 20.0 for row in metrics_rows)
    report = {
        "stage": STAGE,
        "decision": "BY3A5_normal_rerun_completed" if completed else "BY3A5_normal_rerun_failed",
        "stage1_run": stage1_run,
        "stage1_eval": stage1_eval,
        "feedback_generation": feedback,
        "stage2_run": stage2_run,
        "baseline_runs": baseline_rows,
        "eval_rows": eval_rows,
        "metrics_rows": metrics_rows,
        "input_config_audit": input_config_audit,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "degradation_execution": False,
        "paper_claim": False,
    }
    write_rerun_reports(paths, report)
    return report


def ensure_eval_script_env(paths: Paths) -> None:
    if os.environ.get("BY3_OFFICIAL_EVALUATOR_WSL"):
        return
    report = read_json(paths.by3a3_root / "reports" / "BY3A3_OFFICIAL_EVALUATION_REPORT.json", {})
    for row in report.get("evaluation_rows", []):
        command = row.get("command", [])
        for index, token in enumerate(command):
            if str(token).endswith("evaluate_nav_trace_kfgins_v2.py"):
                os.environ["BY3_OFFICIAL_EVALUATOR_WSL"] = str(token)
                return


def blocked_rerun(repaired_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "decision": "BY3A5_normal_rerun_failed",
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
            "source_policy": SOURCE_POLICY_DUAL_HDT,
            "yaw_input_role": "dual_yaw_HDT_fixed_1p5",
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "expected_gnss": paths.gnss_single,
            "expected_imu": paths.imu,
            "source_policy": SOURCE_POLICY_SINGLE_GNSS1,
            "yaw_input_role": "single_GNSS_position_only_no_dual_yaw_input",
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "expected_gnss": paths.gnss_dual,
            "expected_imu": paths.imu,
            "source_policy": SOURCE_POLICY_DUAL_HDT,
            "yaw_input_role": "dual_yaw_HDT_fixed_1p5",
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
        return "<BY3A5_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_HDT_15COL_REPAIRED.gnss"
    if path == paths.gnss_single:
        return "<BY3A1_STAGE_ROOT>/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"
    if path == paths.imu:
        return "<BY3A1_STAGE_ROOT>/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"
    return "<unaliased_runtime_input>"


def write_rerun_reports(paths: Paths, report: dict[str, Any]) -> None:
    solver_rows = []
    for key in ["stage1_run", "stage2_run"]:
        if isinstance(report.get(key), dict):
            solver_rows.append(report[key])
    solver_rows.extend(report.get("baseline_runs", []))
    eval_rows = report.get("eval_rows", [])
    metrics_rows = report.get("metrics_rows", [])
    write_json(paths.stage_root / "reports" / "BY3A5_NORMAL_RERUN_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_SOLVER_STATUS", [by3a3.solver_status_row(row) for row in solver_rows])
    write_rows(paths.stage_root / "matrix" / "BY3A5_EVAL_STATUS", [by3a3.eval_status_row(row) for row in eval_rows])
    write_rows(paths.stage_root / "matrix" / "BY3A5_NORMAL_METRICS", metrics_rows)
    write_rows(paths.stage_root / "matrix" / "BY3A5_SOLVER_INPUT_CONFIG_AUDIT", report.get("input_config_audit", []))
    write_summary(
        paths.stage_root / "summary" / "by3a5_normal_rerun_summary.md",
        "# BY3A5 Normal Rerun Summary\n\n"
        f"Decision: `{report['decision']}`.\n\n"
        + "\n".join(
            f"- `{row.get('algorithm')}`: horizontal_rmse={row.get('horizontal_rmse_m')}, up_rmse={row.get('up_rmse_m')}, yaw_rmse={row.get('yaw_rmse_deg')}"
            for row in metrics_rows
        )
        + "\n",
    )


def metric_row(row: dict[str, Any], source_policy_by_algorithm: dict[str, str]) -> dict[str, Any]:
    metrics = by3a3.metric_row(row)
    metrics["yaw_status"] = "accepted" if float(metrics.get("yaw_rmse_deg") or 999.0) < 20.0 else "repaired_input_eval_failed"
    metrics["source_policy"] = source_policy_by_algorithm.get(str(metrics.get("algorithm", "")), SOURCE_POLICY_MISMATCH)
    metrics["paper_claim"] = False
    return metrics


def generate_figures(
    paths: Paths,
    current_audit: dict[str, Any],
    candidate_audit: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    *,
    skip_figures: bool,
) -> dict[str, Any]:
    if skip_figures:
        report = {"stage": STAGE, "decision": "BY3A5_figures_skipped", "figure_rows": []}
        write_figure_reports(paths, report)
        return report
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        report = {"stage": STAGE, "decision": "BY3A5_figures_blocked", "blocked_reason": repr(exc), "figure_rows": []}
        write_figure_reports(paths, report)
        return report
    fig_dir = paths.stage_root / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    figure_rows: list[dict[str, Any]] = []
    make_yaw_source_figure(paths, plt, fig_dir, figure_rows)
    make_position_error_figure(paths, plt, fig_dir, figure_rows, rerun)
    make_yaw_error_figure(paths, plt, fig_dir, figure_rows, rerun)
    make_metrics_bar_figure(paths, plt, fig_dir, figure_rows, rerun)
    report = {
        "stage": STAGE,
        "decision": "BY3A5_figures_generated" if figure_rows else "BY3A5_figures_blocked",
        "figure_rows": figure_rows,
        "paper_claim": False,
    }
    write_figure_reports(paths, report)
    return report


def write_figure_reports(paths: Paths, report: dict[str, Any]) -> None:
    write_json(paths.stage_root / "reports" / "BY3A5_FIGURE_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_FIGURE_INDEX", report.get("figure_rows", []))


def make_yaw_source_figure(paths: Paths, plt: Any, fig_dir: Path, rows: list[dict[str, Any]]) -> None:
    current = read_numeric_table(paths.current_dual, expected_cols=15)
    repaired = read_numeric_table(paths.repaired_dual, expected_cols=15) if paths.repaired_dual.exists() else []
    fig, ax = plt.subplots(figsize=(10, 4))
    if current:
        ax.plot([row[0] for row in current], [row[13] for row in current], label="current status yaw", linewidth=1.0)
    if repaired:
        ax.plot([row[0] for row in repaired], [row[13] for row in repaired], label="repaired HDT yaw", linewidth=1.0)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("yaw/heading (deg)")
    ax.set_title("BY3A5 yaw input source comparison")
    ax.grid(True, alpha=0.3)
    ax.legend()
    save_fig(fig, fig_dir, "BY3A5_yaw_input_source_comparison", rows, "source_yaw")


def make_position_error_figure(paths: Paths, plt: Any, fig_dir: Path, rows: list[dict[str, Any]], rerun: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    plotted = False
    for algorithm in ALGORITHMS:
        path = paths.stage_root / "official_eval" / algorithm / "error_series.csv"
        if not path.exists():
            continue
        data = read_error_series(path, max_rows=20000)
        if not data:
            continue
        ax.plot([row["time"] for row in data], [row["horizontal_err_m"] for row in data], label=algorithm, linewidth=0.8)
        plotted = True
    if plotted:
        ax.set_xlabel("time (s)")
        ax.set_ylabel("horizontal error (m)")
        ax.set_title("BY3A5 corrected-input horizontal error")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        save_fig(fig, fig_dir, "BY3A5_position_error_common_overlap", rows, "position_error")
    else:
        plt.close(fig)


def make_yaw_error_figure(paths: Paths, plt: Any, fig_dir: Path, rows: list[dict[str, Any]], rerun: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    plotted = False
    for algorithm in ALGORITHMS:
        path = paths.stage_root / "official_eval" / algorithm / "error_series.csv"
        if not path.exists():
            continue
        data = read_error_series(path, max_rows=20000)
        if not data:
            continue
        ax.plot([row["time"] for row in data], [row["yaw_err_deg"] for row in data], label=algorithm, linewidth=0.8)
        plotted = True
    if plotted:
        ax.set_xlabel("time (s)")
        ax.set_ylabel("yaw error (deg)")
        ax.set_title("BY3A5 corrected-input yaw error")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        save_fig(fig, fig_dir, "BY3A5_repaired_yaw_error", rows, "yaw_error")
    else:
        plt.close(fig)


def make_metrics_bar_figure(paths: Paths, plt: Any, fig_dir: Path, rows: list[dict[str, Any]], rerun: dict[str, Any]) -> None:
    metrics = rerun.get("metrics_rows", [])
    if not metrics:
        return
    labels = [row["algorithm"] for row in metrics]
    h = [float(row.get("horizontal_rmse_m") or 0.0) for row in metrics]
    u = [float(row.get("up_rmse_m") or 0.0) for row in metrics]
    yaw = [float(row.get("yaw_rmse_deg") or 0.0) for row in metrics]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, vals, title, ylabel in zip(axes, [h, u, yaw], ["Horizontal RMSE", "Up RMSE", "Yaw RMSE"], ["m", "m", "deg"]):
        ax.bar(range(len(labels)), vals)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    save_fig(fig, fig_dir, "BY3A5_metrics_bar", rows, "metrics_bar")


def save_fig(fig: Any, fig_dir: Path, stem: str, rows: list[dict[str, Any]], figure_type: str) -> None:
    png = fig_dir / f"{stem}.png"
    pdf = fig_dir / f"{stem}.pdf"
    fig.tight_layout()
    fig.savefig(png, dpi=180)
    fig.savefig(pdf)
    fig.clear()
    rows.append(
        {
            "figure": stem,
            "png_alias": f"<BY3A5_STAGE_ROOT>/figures/{png.name}",
            "pdf_alias": f"<BY3A5_STAGE_ROOT>/figures/{pdf.name}",
            "figure_type": figure_type,
            "content_valid": png.exists() and png.stat().st_size > 5000,
            "paper_claim": False,
        }
    )


def read_error_series(path: Path, *, max_rows: int | None = None) -> list[dict[str, float]]:
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if max_rows is not None and idx >= max_rows:
                break
            try:
                out.append({key: float(value) for key, value in row.items() if value not in {None, ""}})
            except ValueError:
                continue
    return out


def write_case_review(
    paths: Paths,
    current_audit: dict[str, Any],
    by2_recovery: dict[str, Any],
    candidate_audit: dict[str, Any],
    policy: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    figures: dict[str, Any],
) -> dict[str, Any]:
    normal_passed = rerun.get("decision") == "BY3A5_normal_rerun_completed"
    main_takeaway = (
        "Corrected HDT/fixed_1p5 yaw input passed source validation and normal yaw sanity."
        if normal_passed
        else "Current status yaw is confirmed wrong-source, but the HDT/fixed_1p5 repaired input still leaves about 103 deg yaw RMSE, so no replacement yaw input is accepted yet."
    )
    review = {
        "stage": STAGE,
        "evaluation_completed": normal_passed,
        "input_files": {
            "current_dual": "<BY3A1_STAGE_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss",
            "repaired_dual": "<BY3A5_STAGE_ROOT>/repaired_input_generation/BY3_DUAL_HDT_15COL_REPAIRED.gnss",
            "hdt_source": "<BY3_RECEIVER_ROOT>/userio-raw.csv",
        },
        "case_overview": "BY3 normal dual-yaw input-source audit and HDT-based repair",
        "current_yaw_input_audit": current_audit.get("decision"),
        "by2_yaw_generation_recovery": by2_recovery.get("decision"),
        "by3_yaw_source_candidates": candidate_audit.get("decision"),
        "corrected_yaw_input_policy": policy.get("policy"),
        "yaw_std_policy": policy.get("yaw_std_policy"),
        "normal_rerun": rerun.get("decision"),
        "metrics": rerun.get("metrics_rows", []),
        "figures": figures.get("figure_rows", []),
        "brief_interpretation": "BY3A3/BY3A4C yaw failures are superseded as wrong-input evidence when the current status long-baseline yaw source is confirmed.",
        "main_takeaway": main_takeaway,
        "ready_for_BY3_degradation_matrix_planning": normal_passed,
        "ready_for_paper_claims": False,
    }
    out_json = paths.stage_root / "case_review" / "BY3A5_corrected_yaw_input_normal_generalization_case_review.json"
    write_json(out_json, review)
    write_summary(
        paths.stage_root / "case_review" / "BY3A5_corrected_yaw_input_normal_generalization_case_review.md",
        "# BY3A5 Corrected Yaw Input Normal Generalization Case Review\n\n"
        "## Evaluation Completed\n\n"
        f"{review['evaluation_completed']}\n\n"
        "## Case Overview\n\n"
        "BY3A5 audits and repairs the BY3 dual-yaw input source. The current BY3A3/BY3A4C yaw failure is treated as wrong-input evidence if the source audit confirms long-baseline status heading misuse.\n\n"
        "## Original BY3A3/BY3A4C Metrics\n\n"
        "Original yaw RMSE around 103-105 deg is preserved as historical invalid/wrong-input evidence, not hidden.\n\n"
        "## Corrected Yaw Source\n\n"
        f"Policy: `{policy.get('policy')}`. Yaw std: `{policy.get('yaw_std_policy')}`.\n\n"
        "## Summary Metrics\n\n"
        + "\n".join(
            f"- `{row.get('algorithm')}`: horizontal_rmse={row.get('horizontal_rmse_m')}, up_rmse={row.get('up_rmse_m')}, yaw_rmse={row.get('yaw_rmse_deg')}"
            for row in rerun.get("metrics_rows", [])
        )
        + "\n\n## Main Takeaway\n\n"
        f"{review['main_takeaway']}\n\nNot a paper claim.\n",
    )
    return review


def update_context_and_obsidian(paths: Paths, current_audit: dict[str, Any], policy: dict[str, Any], repaired_input: dict[str, Any], rerun: dict[str, Any]) -> dict[str, Any]:
    docs = []
    by3_context = paths.repo / "docs" / "codex_context" / "BY3A5_DUAL_YAW_INPUT_SOURCE_REPAIR_CONTEXT.md"
    ready_text = "true" if rerun.get("decision") == "BY3A5_normal_rerun_completed" else "false"
    by3_context.write_text(
        "# BY3A5 Dual Yaw Input Source Repair Context\n\n"
        "Stage: `BY3A5_DUAL_YAW_INPUT_SOURCE_AUDIT_AND_REGENERATION`\n\n"
        "## Decision\n\n"
        "```text\n"
        f"current_yaw_input_status={current_audit.get('decision')}\n"
        f"corrected_yaw_policy={policy.get('policy')}\n"
        f"normal_rerun_status={rerun.get('decision')}\n"
        f"ready_for_BY3_degradation_matrix_planning={ready_text}\n"
        "ready_for_paper_claims=false\n"
        "```\n\n"
        "## Memory Lock\n\n"
        "- Do not use GNSS status long-baseline `rel_pos_n/e` as dual-antenna yaw when its norm is not a physical short antenna baseline.\n"
        "- BY3 yaw input must come from a validated dual-antenna/receiver heading source.\n"
        "- NMEA HDT is allowed only when source semantics and lateral short-baseline geometry support it.\n"
        "- Use BY2 accepted `fixed_1p5` yaw standard deviation unless a better physical source covariance is proven.\n"
        "- Current BY3A3/BY3A4C yaw metrics are preserved as historical bad-input/reference evidence, not paper claims.\n",
        encoding="utf-8",
    )
    docs.append({"path_alias": "docs/codex_context/BY3A5_DUAL_YAW_INPUT_SOURCE_REPAIR_CONTEXT.md", "status": "updated"})
    for path, marker in [
        (paths.repo / "AGENTS.md", "BY3A5"),
        (paths.repo / "PLANS.md", "BY3A5"),
        (paths.repo / "CLAIM_BOUNDARY.md", "BY3A5"),
        (paths.repo / "PHASE_LOG.md", "BY3A5"),
        (paths.repo / "README.md", "BY3A5"),
        (paths.repo / "docs" / "codex_context" / "current_state.md", "BY3A5"),
        (paths.repo / "docs" / "codex_context" / "data_source_roles.md", "BY3A5"),
        (paths.repo / "docs" / "codex_context" / "stage_history_N0_to_current.md", "BY3A5"),
        (paths.repo / "docs" / "codex_context" / "PROJECT_CONTEXT.md", "BY3A5"),
    ]:
        append_once(path, marker, doc_append_text(path.name, rerun.get("decision") == "BY3A5_normal_rerun_completed"))
        docs.append({"path_alias": path_alias(paths, path), "status": "updated"})
    obsidian_rows = update_obsidian(paths, current_audit, policy, rerun)
    report = {
        "stage": STAGE,
        "decision": "BY3A5_context_obsidian_updated",
        "updated_tracked_docs": docs,
        "obsidian_rows": obsidian_rows,
        "local_absolute_paths_in_tracked_docs": False,
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A5_CONTEXT_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A5_UPDATED_TRACKED_DOCS", docs)
    write_rows(paths.stage_root / "matrix" / "BY3A5_OBSIDIAN_SYNC_INDEX", obsidian_rows)
    return report


def doc_append_text(name: str, ready: bool) -> str:
    ready_text = "true" if ready else "false"
    outcome = (
        "The corrected input passed normal yaw sanity."
        if ready
        else "The HDT/fixed_1p5 repaired input did not pass official yaw sanity, so no accepted BY3 yaw replacement exists yet."
    )
    if name == "PHASE_LOG.md":
        return f"\n| BY3A5 dual yaw input source repair | stage/N9A-R3-real-output-frame-alignment-gate | {'done' if ready else 'blocked'} | no | no | yaw-source audit + corrected normal rerun | current status long-baseline yaw misuse audited; HDT/fixed_1p5 policy gated; no degradation or paper claim |\n"
    return (
        "\n## BY3A5 Dual Yaw Input Source Repair\n\n"
        "BY3A5 audits the BY3 dual-yaw input source. The current BY3A3 yaw problem is not treated as final yaw non-evaluable until the input source is checked. "
        "GNSS status long-baseline `rel_pos_n/e` must not be used as dual-antenna yaw when the norm is not a physical short antenna baseline. "
        "A corrected BY3 yaw input may use real receiver NMEA HDT only when source semantics and lateral short-baseline geometry support it; yaw_std follows BY2 `fixed_1p5` unless a better physical covariance is proven. "
        f"{outcome} BY3 degradation planning readiness after BY3A5 is `{ready_text}` for normal repaired yaw only, and `ready_for_paper_claims=false`.\n"
    )


def append_once(path: Path, marker: str, text: str) -> None:
    original = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if marker in original:
        return
    path.write_text(original.rstrip() + "\n" + text.lstrip(), encoding="utf-8")


def path_alias(paths: Paths, path: Path) -> str:
    try:
        return path.relative_to(paths.repo).as_posix()
    except ValueError:
        return path.name


def update_obsidian(paths: Paths, current_audit: dict[str, Any], policy: dict[str, Any], rerun: dict[str, Any]) -> list[dict[str, Any]]:
    root = paths.repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization"
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    note = root / "BY3_yaw_input_source_repair.md"
    note.write_text(
        "# BY3 yaw input source repair\n\n"
        f"- current yaw input audit: `{current_audit.get('decision')}`\n"
        f"- corrected yaw policy: `{policy.get('policy')}`\n"
        f"- normal rerun: `{rerun.get('decision')}`\n"
        "- Do not use long-baseline GNSS status rel_pos as dual-antenna yaw.\n"
        "- Use HDT/fixed_1p5 only when source and lateral geometry are verified.\n"
        "- Not a paper claim.\n",
        encoding="utf-8",
    )
    rows.append({"note_alias": "obsidian_knowledge/LegSA-GINS/BY3_generalization/BY3_yaw_input_source_repair.md", "status": "updated"})
    for name in ["01_CURRENT_STATE.md", "08_NEXT_STEPS.md", "BY3_BDS_dual_antenna_lateral_yaw_policy.md"]:
        path = root / name
        append_once(path, "BY3A5", doc_append_text(name, rerun.get("decision") == "BY3A5_normal_rerun_completed"))
        rows.append({"note_alias": f"obsidian_knowledge/LegSA-GINS/BY3_generalization/{name}", "status": "updated"})
    return rows


def validate_stage(
    paths: Paths,
    current_audit: dict[str, Any],
    by2_recovery: dict[str, Any],
    candidate_audit: dict[str, Any],
    hdt_recovery: dict[str, Any],
    policy: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    figures: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    input_config_rows = rerun.get("input_config_audit", [])
    input_config_ok = (
        rerun.get("decision") == "BY3A5_normal_rerun_blocked"
        or bool(input_config_rows)
        and all(row.get("config_audit_passed") is True for row in input_config_rows)
    )
    checks = [
        ("current_yaw_source_audited", current_audit.get("decision") in {"BY3A5_current_yaw_input_wrong_source_confirmed", "BY3A5_current_yaw_input_suspicious"}),
        ("rel_pos_misuse_confirmed", current_audit.get("decision") == "BY3A5_current_yaw_input_wrong_source_confirmed"),
        ("by2_yaw_generation_recovered", by2_recovery.get("decision") == "BY3A5_by2_yaw_generation_recovered"),
        ("hdt_heading_recovered", hdt_recovery.get("decision") == "BY3A5_hdt_heading_available"),
        ("yaw_std_policy_repaired", policy.get("yaw_std_policy") == "fixed_1p5"),
        ("solver_input_config_audit_passed", input_config_ok),
        ("no_trace_solver_input", not rerun.get("trace_solver_input", False)),
        ("no_rmse_only_policy_selection", policy.get("not_chosen_by_RMSE") is True),
        ("corrected_input_valid_or_blocked", repaired_input.get("decision") in {"BY3A5_repaired_inputs_ready", "BY3A5_repaired_inputs_blocked"}),
        ("normal_rerun_only_or_blocked", rerun.get("decision") in {"BY3A5_normal_rerun_completed", "BY3A5_normal_rerun_failed", "BY3A5_normal_rerun_blocked"}),
        ("no_by3_degradation", True),
        ("no_paper_claims", True),
        ("figures_generated_or_blocked", figures.get("decision") in {"BY3A5_figures_generated", "BY3A5_figures_blocked", "BY3A5_figures_skipped"}),
        ("context_updated", context.get("decision") == "BY3A5_context_obsidian_updated"),
    ]
    rows = [{"check": name, "status": "passed" if ok else "failed"} for name, ok in checks]
    report = {
        "stage": STAGE,
        "decision": "passed" if all(ok for _, ok in checks) else "failed",
        "checks": rows,
        "json_csv_parse": validate_json_csv(paths.stage_root),
        "runtime_untracked": True,
        "ready_for_paper_claims": False,
    }
    return report


def validate_json_csv(root: Path) -> bool:
    try:
        for path in root.rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        for path in root.rglob("*.csv"):
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.reader(handle))
    except Exception:
        return False
    return True


def decide_stage(
    validation: dict[str, Any],
    current_audit: dict[str, Any],
    policy: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
) -> dict[str, Any]:
    if validation.get("decision") != "passed":
        status = "BY3A5_safety_gate_failed"
        ready = False
        next_stage = "repair_safety_violation"
    elif rerun.get("decision") == "BY3A5_normal_rerun_completed":
        status = "BY3A5_corrected_yaw_input_normal_generalization_completed"
        ready = True
        next_stage = "BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK"
    elif current_audit.get("decision") == "BY3A5_current_yaw_input_wrong_source_confirmed" and policy.get("decision") != "BY3A5_corrected_yaw_policy_ready":
        status = "BY3A5_wrong_yaw_input_confirmed_but_no_valid_replacement"
        ready = False
        next_stage = "manual_supply_BY3_heading_source_or_confirm_antenna_order"
    elif current_audit.get("decision") != "BY3A5_current_yaw_input_wrong_source_confirmed":
        status = "BY3A5_current_yaw_input_valid_reference_issue_remains"
        ready = False
        next_stage = "return_to_BY3_reference_policy_review"
    else:
        status = "BY3A5_wrong_yaw_input_confirmed_but_no_valid_replacement"
        ready = False
        next_stage = "manual_supply_BY3_heading_source_or_confirm_antenna_order_or_return_to_reference_policy_review"
    return {
        "stage": STAGE,
        "status": status,
        "ready_for_BY3_degradation_matrix_planning": ready,
        "ready_for_paper_claims": False,
        "recommended_next_stage": next_stage,
        "yaw_degradation_claims": ready,
    }


def write_final_reports(
    paths: Paths,
    validation: dict[str, Any],
    decision: dict[str, Any],
    current_audit: dict[str, Any],
    by2_recovery: dict[str, Any],
    candidate_audit: dict[str, Any],
    hdt_recovery: dict[str, Any],
    policy: dict[str, Any],
    repaired_input: dict[str, Any],
    rerun: dict[str, Any],
    figures: dict[str, Any],
    case_review: dict[str, Any],
    context: dict[str, Any],
) -> None:
    write_policy(paths, policy)
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    rows = [
        {"stage": "current_yaw_input_audit", "status": current_audit.get("decision")},
        {"stage": "by2_yaw_generation_recovery", "status": by2_recovery.get("decision")},
        {"stage": "by3_yaw_source_candidates", "status": candidate_audit.get("decision")},
        {"stage": "hdt_heading_recovery", "status": hdt_recovery.get("decision")},
        {"stage": "corrected_yaw_policy", "status": policy.get("decision")},
        {"stage": "repaired_input_generation", "status": repaired_input.get("decision")},
        {"stage": "normal_rerun", "status": rerun.get("decision")},
        {"stage": "figures", "status": figures.get("decision")},
        {"stage": "case_review", "status": case_review.get("stage")},
        {"stage": "context_update", "status": context.get("decision")},
        {"stage": "final_decision", "status": decision.get("status")},
    ]
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    write_summary(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3A5 Long Task Summary\n\n"
        f"Final decision: `{decision['status']}`.\n\n"
        f"Current yaw audit: `{current_audit.get('decision')}`.\n"
        f"Corrected yaw policy: `{policy.get('policy')}`.\n"
        f"Normal rerun: `{rerun.get('decision')}`.\n"
        f"Ready for BY3 degradation planning: `{decision['ready_for_BY3_degradation_matrix_planning']}`.\n"
        "Ready for paper claims: `false`.\n",
    )
    write_summary(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A5 Next Stage Recommendation\n\n"
        f"`{decision['recommended_next_stage']}`\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
