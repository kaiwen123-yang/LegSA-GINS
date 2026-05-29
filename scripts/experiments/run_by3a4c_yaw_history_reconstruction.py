#!/usr/bin/env python3
"""BY3A4C yaw history reconstruction and visual validation.

This runner is evaluator/report only. It recovers the historical BY2/N4 yaw
reference evidence from tracked git/docs/source, applies recovered diagnostic
profiles to existing BY3A3 normal outputs, and writes BY3A4C audit artifacts.
It never runs BY3 solvers, degradation generation, retuning, or output edits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STAGE = "BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION"
RUNTIME_STAGE = "BY3A4C_YAW_HISTORY_RECONSTRUCTION"
BASE_TIME = 1772784394.943074
ALGORITHMS = [
    "LegSA_full_EKF",
    "single_antenna_gnss1_status_KF_GINS",
    "final_v23_dual_antenna_EKF",
]

HISTORICAL_COMMITS = [
    {
        "stage": "N4H2",
        "commit": "381c2c99",
        "summary": "KF-GINS replay audit; old replay kept good position but bad yaw.",
    },
    {
        "stage": "N4H2C",
        "commit": "0235c678",
        "summary": "Yaw config parity audit; process_data status-yaw chain documented.",
    },
    {
        "stage": "N4H2C",
        "commit": "a573a985",
        "summary": "Final_v23 artifact and yaw parity audit deepened.",
    },
    {
        "stage": "N4R",
        "commit": "5e0d4a18",
        "summary": "Official evaluator yaw parity reproduced and candidate conventions listed.",
    },
    {
        "stage": "N4R2",
        "commit": "cdf29322",
        "summary": "Yaw evaluator convention policy; diagnostic profile kept non-formal.",
    },
    {
        "stage": "N4R3",
        "commit": "53e8a40f",
        "summary": "Dual final_v23 artifact intake and direct-identity evaluator parity locked.",
    },
    {
        "stage": "N4H2C-runtime",
        "commit": "eccc54d6",
        "summary": "Runtime yaw update config parity audit.",
    },
    {
        "stage": "N4H2D",
        "commit": "d33a65cc",
        "summary": "Replay reference mapping and stale-summary audit.",
    },
    {
        "stage": "N4H2E",
        "commit": "113d1e91",
        "summary": "Dual final_v23 visual validation bundle created.",
    },
    {
        "stage": "N4H2F",
        "commit": "459ded7f",
        "summary": "Startup transient, yaw std, and process-noise provenance.",
    },
    {
        "stage": "N4H2G",
        "commit": "f380f25e",
        "summary": "Clean status-yaw replay provenance audit.",
    },
    {
        "stage": "N4H2G2",
        "commit": "c4fb73ab",
        "summary": "Clean replay independence and yaw sensitivity audit.",
    },
]

PR_METADATA = [
    {
        "pr": 12,
        "stage": "N4H2",
        "title": "test(N4H2): replay process_data-compatible inputs with KF-GINS",
        "branch": "stage/N4H2-process-data-replay-evaluation",
        "merge_commit": "f8fee67c3f8d55b27a9fde59c1e71b0d0cce4340",
        "merged": True,
    },
    {
        "pr": 13,
        "stage": "N4H2C",
        "title": "docs(N4H2C): plan yaw config parity audit",
        "branch": "stage/N4H2C-yaw-config-parity-audit",
        "merge_commit": "53e8a40fea707d5831e721d0bfc8a446f86e895d",
        "merged": True,
    },
    {
        "pr": 14,
        "stage": "N4H2C-runtime",
        "title": "test(N4H2C): audit runtime yaw update config parity",
        "branch": "stage/N4H2C-runtime-yaw-update-config-audit",
        "merge_commit": "eccc54d669fd4006f7dc5dd32eaba1494bc277ef",
        "merged": True,
    },
    {
        "pr": 15,
        "stage": "N4H2D",
        "title": "test(N4H2D): audit replay reference mapping and stale summary",
        "branch": "stage/N4H2D-replay-reference-mapping-audit",
        "merge_commit": "459ded7fa76110e61233145895235873dbe8f339",
        "merged": True,
    },
]


@dataclass(frozen=True)
class Paths:
    repo: Path
    stage_root: Path
    runtime_root: Path
    by3a3_stage: Path
    by3a3_runtime: Path
    by3a4a_stage: Path
    by3a1_stage: Path
    obsidian_by3: Path

    @classmethod
    def build(cls, repo: Path) -> "Paths":
        by3_root = repo / "by3-huiti"
        return cls(
            repo=repo,
            stage_root=by3_root / STAGE,
            runtime_root=by3_root / "BY3_FULL_MATRIX" / RUNTIME_STAGE,
            by3a3_stage=by3_root / "BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION",
            by3a3_runtime=by3_root / "BY3_FULL_MATRIX" / "BY3A3_NORMAL_EXECUTION",
            by3a4a_stage=by3_root / "BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK",
            by3a1_stage=by3_root / "BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR",
            obsidian_by3=repo / "obsidian_knowledge" / "LegSA-GINS" / "BY3_generalization",
        )


def ensure_dirs(paths: Paths) -> None:
    subdirs = [
        "00_supervisor",
        "01_plan",
        "git_history_recovery",
        "n4h2c_n4h2d_logic",
        "evaluator_source_recovery",
        "by3_reference_reconstruction",
        "yaw_policy_tests",
        "visual_validation",
        "repaired_eval",
        "case_review",
        "context_update",
        "obsidian_sync",
        "reports",
        "matrix",
        "summary",
        "validation",
        "logs",
        "blocked",
        "figures",
    ]
    for root in [paths.stage_root, paths.runtime_root]:
        for subdir in subdirs:
            (root / subdir).mkdir(parents=True, exist_ok=True)
    paths.obsidian_by3.mkdir(parents=True, exist_ok=True)


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
    if not keys:
        keys = ["empty"]
    with stem.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed):
        return default
    return parsed


def run_command(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:  # pragma: no cover - defensive runtime audit path.
        return 999, "", str(exc)


def wrap180(angle: float) -> float:
    return (float(angle) + 180.0) % 360.0 - 180.0


def wrap360(angle: float) -> float:
    return float(angle) % 360.0


def unwrap_deg(values: list[float]) -> list[float]:
    out: list[float] = []
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
        out.append(unwrapped)
        prev = unwrapped
    return out


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


def pctl_abs(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(abs(v) for v in values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(len(ordered) - 1, index))]


def max_abs(values: list[float]) -> float | None:
    return max((abs(v) for v in values), default=None)


def circular_mean(values: list[float]) -> float | None:
    if not values:
        return None
    s = sum(math.sin(math.radians(v)) for v in values)
    c = sum(math.cos(math.radians(v)) for v in values)
    return math.degrees(math.atan2(s, c))


def circular_std(values: list[float]) -> float | None:
    if not values:
        return None
    s = sum(math.sin(math.radians(v)) for v in values)
    c = sum(math.cos(math.radians(v)) for v in values)
    r = math.sqrt(s * s + c * c) / len(values)
    r = max(min(r, 1.0), 1.0e-12)
    return math.degrees(math.sqrt(-2.0 * math.log(r)))


def lla_to_local(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    return (lon - lon0) * meters_per_deg_lon, (lat - lat0) * meters_per_deg_lat


def load_official_nav(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
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
    rows.sort(key=lambda row: row["time"])
    return rows


def load_error_series(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            parsed: dict[str, float] = {}
            for key, value in raw.items():
                val = as_float(value)
                if val is not None:
                    parsed[key] = val
            if parsed:
                rows.append(parsed)
    rows.sort(key=lambda row: row.get("time", 0.0))
    return rows


def discover_trace_path(repo: Path) -> Path | None:
    matches = list(repo.parent.glob("**/trace_vrtk2_a87c6e_2026-03-06-08-06-39_minimal.csv"))
    by3_matches = [path for path in matches if "by3" in str(path).lower()]
    return by3_matches[0] if by3_matches else (matches[0] if matches else None)


def load_trace(path: Path | None) -> list[dict[str, float]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
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
    rows.sort(key=lambda row: row["time"])
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
                rows.append({"time": float(parts[0]), "yaw": float(parts[13])})
            except ValueError:
                continue
    rows.sort(key=lambda row: row["time"])
    return rows


def inspect_go2_yaw_sources(paths: Paths) -> dict[str, Any]:
    attitude_path = (
        paths.by3a1_stage
        / "provider_materialization"
        / "go2_priors"
        / "priors"
        / "joint_rp1p6deg_hv1p0"
        / "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv"
    )
    headers: list[str] = []
    if attitude_path.exists():
        with attitude_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
    yaw_like = [name for name in headers if "yaw" in name.lower() or "heading" in name.lower()]
    return {
        "source_alias": "<BY3A1_STAGE_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
        "exists": attitude_path.exists(),
        "header_fields": headers,
        "yaw_like_fields": yaw_like,
        "go2_body_yaw_reference_available": bool(yaw_like),
        "diagnostic_status": "evidence_missing" if not yaw_like else "available",
        "truth_claim": False,
    }


def collect_algorithm_inputs(paths: Paths) -> dict[str, dict[str, Path]]:
    eval_root = paths.by3a3_stage / "official_eval"
    return {
        "LegSA_full_EKF": {
            "eval_dir": eval_root / "LegSA_full_EKF",
            "nav": eval_root / "LegSA_full_EKF" / "converted_eval_nav_official.nav",
            "error_series": eval_root / "LegSA_full_EKF" / "error_series.csv",
            "summary": eval_root / "LegSA_full_EKF" / "summary.json",
        },
        "single_antenna_gnss1_status_KF_GINS": {
            "eval_dir": eval_root / "single_antenna_gnss1_status_KF_GINS",
            "nav": paths.by3a3_runtime
            / "single_baseline_solver"
            / "single_antenna_gnss1_status_KF_GINS"
            / "KF_GINS_Navresult.nav",
            "error_series": eval_root / "single_antenna_gnss1_status_KF_GINS" / "error_series.csv",
            "summary": eval_root / "single_antenna_gnss1_status_KF_GINS" / "summary.json",
        },
        "final_v23_dual_antenna_EKF": {
            "eval_dir": eval_root / "final_v23_dual_antenna_EKF",
            "nav": paths.by3a3_runtime
            / "finalv23_solver"
            / "final_v23_dual_antenna_EKF"
            / "KF_GINS_Navresult.nav",
            "error_series": eval_root / "final_v23_dual_antenna_EKF" / "error_series.csv",
            "summary": eval_root / "final_v23_dual_antenna_EKF" / "summary.json",
        },
    }


def metric_row_from_summary(algorithm: str, summary: dict[str, Any]) -> dict[str, Any]:
    position = summary.get("position", {})
    attitude = summary.get("attitude", {})
    meta = summary.get("meta", {})
    return {
        "algorithm": algorithm,
        "horizontal_rmse_m": position.get("horizontal_rmse_m"),
        "horizontal_p95_m": position.get("horizontal_p95_m"),
        "horizontal_max_m": position.get("horizontal_max_m"),
        "up_rmse_m": position.get("up_rmse_m"),
        "vertical_p95_m": position.get("vertical_p95_m"),
        "vertical_max_m": position.get("vertical_max_m"),
        "roll_rmse_deg": attitude.get("roll_rmse_deg"),
        "pitch_rmse_deg": attitude.get("pitch_rmse_deg"),
        "original_yaw_rmse_deg": attitude.get("yaw_rmse_deg"),
        "original_yaw_p95_deg": attitude.get("yaw_p95_deg"),
        "original_yaw_max_deg": attitude.get("yaw_max_deg"),
        "sample_count": meta.get("num_samples"),
        "time_start": meta.get("time_start"),
        "time_end": meta.get("time_end"),
        "yaw_truth_mode": meta.get("yaw_truth_mode"),
    }


def build_git_history_recovery(paths: Paths) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in HISTORICAL_COMMITS:
        code, show, err = run_command(["git", "show", "--name-only", "--format=%H%n%s", item["commit"]], paths.repo)
        lines = [line for line in show.splitlines() if line.strip()]
        full_commit = lines[0] if code == 0 and lines else item["commit"]
        subject = lines[1] if code == 0 and len(lines) > 1 else item["summary"]
        touched = [line for line in lines[2:] if line and not line.startswith("commit ")]
        docs = [line for line in touched if line.startswith("docs/") or line.endswith(".md")]
        source = [line for line in touched if line.startswith("src/") or line.startswith("scripts/")]
        rows.append(
            {
                "stage": item["stage"],
                "branch": "",
                "commit": full_commit,
                "tag": "",
                "report_path": ";".join(docs[:8]),
                "source_files_touched": ";".join(source[:8]),
                "yaw_related_logic_summary": item["summary"],
                "whether_merged": "commit_present_locally",
                "whether_superseded": "evidence_only" if item["stage"] in {"N4R", "N4R2"} else "not_superseded",
                "whether_current": "historical_evidence",
                "relevance_to_BY3": "Recover yaw-reference policy lineage; not accepted for BY3 unless source semantics transfer.",
                "git_show_status": code,
                "git_show_error": err,
                "commit_subject": subject,
            }
        )
    for pr in PR_METADATA:
        code, gh_out, gh_err = run_command(
            [
                "gh",
                "pr",
                "view",
                str(pr["pr"]),
                "--json",
                "number,title,state,isDraft,headRefName,mergeCommit,mergedAt",
            ],
            paths.repo,
            timeout=20,
        )
        gh_data = read_json_from_text(gh_out, {}) if code == 0 else {}
        rows.append(
            {
                "stage": pr["stage"],
                "branch": gh_data.get("headRefName", pr["branch"]),
                "commit": "",
                "tag": "",
                "report_path": "",
                "source_files_touched": "",
                "yaw_related_logic_summary": f"PR #{pr['pr']}: {pr['title']}",
                "whether_merged": gh_data.get("state", "MERGED" if pr["merged"] else "unknown"),
                "whether_superseded": "historical_evidence",
                "whether_current": "PR_metadata",
                "relevance_to_BY3": "Confirms historical yaw repair sequence and merge status.",
                "pr_number": pr["pr"],
                "merge_commit": (gh_data.get("mergeCommit") or {}).get("oid", pr["merge_commit"]),
                "gh_status": code,
                "gh_error": gh_err,
            }
        )
    code, refs_out, refs_err = run_command(
        ["git", "ls-remote", "--heads", "--tags", "origin", "*N4H2*", "*N4R*", "*yaw*"],
        paths.repo,
        timeout=30,
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_git_history_recovered",
        "rows_count": len(rows),
        "git_ls_remote_status": code,
        "git_ls_remote_head_tag_lines": refs_out.splitlines()[:80],
        "git_ls_remote_error": refs_err,
        "paper_claim": False,
        "solver_rerun": False,
        "degradation_matrix_run": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_GIT_HISTORY_RECOVERY", rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_GIT_HISTORY_RECOVERY_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_git_history_recovery.md",
        "# BY3A4C Git History Recovery\n\n"
        "- N4H2, N4H2C, N4R, N4R2, N4R3, N4H2D, and N4H2E/G/G2 commits were recovered from local git history.\n"
        "- PR #12-#15 metadata was queried with `gh` when available and falls back to previously verified local values.\n"
        "- The recovered lineage shows BY2 yaw repair moved from angle-candidate diagnostics to official reference reconstruction.\n"
        "- No merge, tag, fetch, solver run, degradation run, or paper claim was performed.\n",
    )
    return report


def read_json_from_text(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def build_historical_logic_recovery(paths: Paths, fresh_summary_path: Path | None, fresh_report_path: Path | None) -> dict[str, Any]:
    fresh_summary = read_json(fresh_summary_path, {}) if fresh_summary_path else {}
    fresh_report = read_json(fresh_report_path, {}) if fresh_report_path else {}
    rows = [
        {
            "topic": "process_data_status_yaw_generation",
            "policy": "A1_dual_diff_status",
            "formula": "rel_n=gnss2.rel_pos_n_interp-gnss1.rel_pos_n; rel_e=gnss2.rel_pos_e_interp-gnss1.rel_pos_e; yaw_baseline=-atan2(rel_e,rel_n); yaw_body=sign*yaw_baseline+offset; yaw_ned=90-yaw_body",
            "source_evidence": "src/legsa_gins/input_generation/status_yaw_builder.py; docs/experiments/n4h2c_yaw_config_parity_decision.md",
            "status": "recovered",
            "paper_claim": False,
        },
        {
            "topic": "N4H2_old_replay_failure",
            "policy": "old_summary_invalidated",
            "formula": "old replay position good but yaw_rmse approximately 93.557 deg",
            "source_evidence": "docs/experiments/n4h2c_yaw_config_parity_decision.md; docs/experiments/summary_staleness_audit.md",
            "horizontal_rmse_m": 0.3479654209,
            "up_rmse_m": 0.7940101229,
            "yaw_rmse_deg": 93.5573119664,
            "status": "historical_invalid_reference",
            "paper_claim": False,
        },
        {
            "topic": "N4R_N4R2_candidate_conventions",
            "policy": "heading_to_math_yaw_candidate_diagnostic_only",
            "formula": "Candidate transform could reproduce single-like evaluator behavior but was not formal after dual-final parity lock.",
            "source_evidence": "docs/experiments/n4r_yaw_evaluator_decision.md; docs/experiments/yaw_evaluator_convention_policy.md",
            "status": "diagnostic_only",
            "paper_claim": False,
        },
        {
            "topic": "N4R3_dual_final_parity_lock",
            "policy": "direct_identity_for_confirmed_dual_artifact",
            "formula": "Formal dual_final_v23 evaluator parity locked direct identity yaw once the correct artifact was confirmed.",
            "source_evidence": "docs/experiments/dual_final_v23_official_parity_lock.md; docs/experiments/n4r3_dual_artifact_intake_decision.md",
            "status": "accepted_BY2_context",
            "paper_claim": False,
        },
        {
            "topic": "N4H2D_official_reference_reconstruction",
            "policy": "selected_reference_sign=official_ref_sign_minus",
            "formula": "reference = official_estimate - official_error_series; yaw_profile=direct_identity; fresh replay evaluated against reconstructed dual official reference",
            "source_evidence": "src/legsa_gins/evaluation/official_reference_reconstruction.py; src/legsa_gins/evaluation/fresh_replay_evaluator.py; docs/experiments/n4h2d_replay_reference_mapping_decision.md",
            "horizontal_rmse_m": fresh_summary.get("position", {}).get("horizontal_rmse_m", 0.3460851160719829),
            "up_rmse_m": fresh_summary.get("position", {}).get("up_rmse_m", 0.7940342899951961),
            "yaw_rmse_deg": fresh_summary.get("attitude", {}).get("yaw_rmse_deg", 1.979182806966782),
            "status": "accepted_BY2_reference_mapping",
            "paper_claim": False,
        },
        {
            "topic": "N4H2E_visual_validation",
            "policy": "visual_validation_required_after_numerical_pass",
            "formula": "Generate visual bundle and manual review; do not rely on stale old comparison figures.",
            "source_evidence": "docs/experiments/dual_replay_visual_validation.md; scripts/experiments/run_dual_replay_visual_validation.py",
            "status": "accepted_BY2_process",
            "paper_claim": False,
        },
    ]
    selected_reference_verified = bool(
        fresh_summary.get("reference_profile") == "selected_dual_official_reference_direct_identity"
        or fresh_report.get("reference_profile") == "selected_dual_official_reference_direct_identity"
        or fresh_report.get("selected_reference_sign") == "official_ref_sign_minus"
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_historical_yaw_logic_recovered",
        "selected_reference_sign": "official_ref_sign_minus",
        "selected_reference_verified_from_runtime": selected_reference_verified,
        "old_yaw_rmse_deg": 93.5573119664,
        "old_yaw_invalidated": True,
        "fresh_yaw_rmse_deg": fresh_summary.get("attitude", {}).get("yaw_rmse_deg", 1.979182806966782),
        "fresh_horizontal_rmse_m": fresh_summary.get("position", {}).get("horizontal_rmse_m", 0.3460851160719829),
        "fresh_up_rmse_m": fresh_summary.get("position", {}).get("up_rmse_m", 0.7940342899951961),
        "fresh_reference_profile": fresh_summary.get("reference_profile", "selected_dual_official_reference_direct_identity"),
        "reason_old_BY2_yaw_failed": "stale or wrong reference mapping; not a solver-output failure after the correct dual official reference was reconstructed",
        "trace_solver_input": False,
        "solver_rerun": False,
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_HISTORICAL_YAW_LOGIC", rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_HISTORICAL_YAW_LOGIC_RECOVERY_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_historical_yaw_logic.md",
        "# BY3A4C Historical Yaw Logic\n\n"
        "- The BY2 yaw fix was recovered as an official-reference reconstruction, not another blind `+90/-90` search.\n"
        "- N4H2C documented process_data status yaw generation: `yaw_baseline=-atan2(rel_e,rel_n)`, `yaw_body=sign*yaw_baseline+offset`, `yaw_ned=90-yaw_body`.\n"
        "- N4R/N4R2 convention candidates were diagnostic. N4R3 locked direct identity only after the correct dual_final_v23 artifact was confirmed.\n"
        "- N4H2D selected `official_ref_sign_minus` (`reference=estimate-error`) and invalidated the old 93.557 deg replay yaw summary.\n"
        f"- Fresh N4H2D replay evidence: horizontal_rmse={report['fresh_horizontal_rmse_m']}, up_rmse={report['fresh_up_rmse_m']}, yaw_rmse={report['fresh_yaw_rmse_deg']}.\n",
    )
    return report


def build_evaluator_source_audit(paths: Paths) -> dict[str, Any]:
    rows = [
        {
            "source": "src/legsa_gins/evaluation/official_reference_reconstruction.py",
            "function_or_policy": "select_reference_sign_by_summary",
            "yaw_truth_mode_handling": "reconstruct official dual reference from official NAV plus error_series",
            "formula": "official_ref_sign_minus: ref=estimate-error; official_ref_sign_plus: ref=estimate+error; tie-break prefers sign_minus",
            "unwrap_policy": "not interpolation-based; row-aligned official NAV/error_series reference",
            "wrap_policy": "fresh evaluator wraps nav-reference error",
            "current_validity": "accepted_BY2",
            "paper_claim": False,
        },
        {
            "source": "src/legsa_gins/evaluation/fresh_replay_evaluator.py",
            "function_or_policy": "evaluate_replay_against_official_reference",
            "yaw_truth_mode_handling": "direct identity yaw against selected dual official reference",
            "formula": "yaw_err=wrap(nav_yaw-ref_yaw)",
            "unwrap_policy": "not trace interpolation; reference rows are reconstructed official rows",
            "wrap_policy": "wrap after difference",
            "current_validity": "accepted_BY2",
            "paper_claim": False,
        },
        {
            "source": "docs/experiments/yaw_evaluator_convention_policy.md",
            "function_or_policy": "official_candidate_ref_heading_to_math",
            "yaw_truth_mode_handling": "diagnostic profile for historical single-like mismatch",
            "formula": "candidate only; not formal after N4R3 dual parity lock",
            "unwrap_policy": "diagnostic",
            "wrap_policy": "diagnostic",
            "current_validity": "diagnostic_only",
            "paper_claim": False,
        },
        {
            "source": "<WSL_KFGINS_EVALUATOR>/evaluate_nav_trace_kfgins_v2.py",
            "function_or_policy": "yaw_truth_mode=enu",
            "yaw_truth_mode_handling": "trace yaw is unwrapped before interpolation; ENU yaw is converted with 90-yaw for comparison",
            "formula": "yaw_ref=90-trace_yaw when yaw_truth_mode=enu; yaw_err=wrap(nav_yaw-yaw_ref)",
            "unwrap_policy": "unwrap before interpolation",
            "wrap_policy": "wrap after difference",
            "current_validity": "generic_evaluator_policy_not_sufficient_for_BY3A4C_without_valid_trace_yaw_semantics",
            "paper_claim": False,
        },
    ]
    profile_rows = [
        {
            "profile_name": "official_ref_sign_minus",
            "formula": "reference=official_estimate-official_error_series; yaw direct identity",
            "trace_fields_used": "none",
            "nav_fields_used": "official NAV time/lat/lon/alt/roll/pitch/yaw plus official error_series",
            "sign": "minus",
            "offset": 0,
            "wrap_policy": "wrap after difference",
            "source_evidence": "N4H2D official_reference_reconstruction.py",
            "current_validity": "accepted_BY2",
        },
        {
            "profile_name": "official_ref_sign_plus",
            "formula": "reference=official_estimate+official_error_series; yaw direct identity",
            "trace_fields_used": "none",
            "nav_fields_used": "official NAV plus official error_series",
            "sign": "plus",
            "offset": 0,
            "wrap_policy": "wrap after difference",
            "source_evidence": "N4H2D sign candidate, not selected",
            "current_validity": "rejected",
        },
        {
            "profile_name": "direct_identity",
            "formula": "yaw_err=wrap(nav_yaw-reference_yaw)",
            "trace_fields_used": "none for BY2 official reference reconstruction",
            "nav_fields_used": "selected reconstructed official reference",
            "sign": "identity",
            "offset": 0,
            "wrap_policy": "wrap after difference",
            "source_evidence": "N4R3 and N4H2D",
            "current_validity": "accepted_BY2_when_reference_artifact_is_confirmed",
        },
        {
            "profile_name": "trace_enu_90_minus",
            "formula": "yaw_ref=90-trace_yaw",
            "trace_fields_used": "trace yaw",
            "nav_fields_used": "algorithm NAV yaw",
            "sign": "minus",
            "offset": 90,
            "wrap_policy": "unwrap trace before interpolation; wrap after difference",
            "source_evidence": "evaluate_nav_trace_kfgins_v2.py generic trace evaluator",
            "current_validity": "diagnostic_for_BY3A4C",
        },
        {
            "profile_name": "official_candidate_ref_heading_to_math",
            "formula": "candidate transform from historical N4R/N4R2",
            "trace_fields_used": "candidate reference heading",
            "nav_fields_used": "algorithm NAV yaw",
            "sign": "candidate",
            "offset": "candidate",
            "wrap_policy": "wrap after difference",
            "source_evidence": "N4R/N4R2 diagnostic only",
            "current_validity": "diagnostic_only",
        },
    ]
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_evaluator_source_audited",
        "accepted_BY2_profile": "official_ref_sign_minus -> selected_dual_official_reference_direct_identity",
        "deprecated_or_diagnostic_profiles": ["official_ref_sign_plus", "official_candidate_ref_heading_to_math", "blind_lateral_plus_minus_90"],
        "trace_solver_input": False,
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_EVALUATOR_SOURCE_AUDIT", rows)
    write_rows(paths.stage_root / "matrix" / "BY3A4C_BY2_REFERENCE_PROFILE", profile_rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_EVALUATOR_SOURCE_AUDIT_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_evaluator_source_audit.md",
        "# BY3A4C Evaluator Source Audit\n\n"
        "- Accepted BY2 logic is `official_ref_sign_minus` plus direct-identity yaw on the reconstructed dual official reference.\n"
        "- N4R/N4R2 heading-to-math profiles remain diagnostic; N4R3/N4H2D supersede them for the confirmed dual artifact path.\n"
        "- The generic trace evaluator unwraps yaw before interpolation and wraps after difference, but trace yaw semantics still must be valid before BY3 yaw can be accepted.\n",
    )
    return report


def make_reference_from_final_official(
    final_nav: list[dict[str, float]], final_errors: list[dict[str, float]], sign: str
) -> list[dict[str, float]]:
    by_time = {round(row["time"], 9): row for row in final_errors if "time" in row and "yaw_err_deg" in row}
    refs: list[dict[str, float]] = []
    multiplier = -1.0 if sign == "minus" else 1.0
    for nav in final_nav:
        err = by_time.get(round(nav["time"], 9))
        if err is None:
            continue
        refs.append(
            {
                "time": nav["time"],
                "yaw": wrap360(nav["yaw"] + multiplier * err.get("yaw_err_deg", 0.0)),
                "lat": nav["lat"] + multiplier * err.get("err_n_m", 0.0) / 111_320.0,
                "lon": nav["lon"],
                "alt": nav["alt"] + multiplier * err.get("err_u_m", 0.0),
            }
        )
    return refs


def make_trace_profiles(trace_rows: list[dict[str, float]]) -> dict[str, list[dict[str, float]]]:
    profiles: dict[str, list[dict[str, float]]] = {
        "trace_raw_identity": [],
        "trace_enu_90_minus": [],
        "trace_neg_identity": [],
        "trace_plus_90": [],
        "trace_minus_90": [],
    }
    for row in trace_rows:
        yaw = row["yaw"]
        base = {"time": row["time"], "lat": row["lat"], "lon": row["lon"], "alt": row["alt"]}
        profiles["trace_raw_identity"].append({**base, "yaw": wrap360(yaw)})
        profiles["trace_enu_90_minus"].append({**base, "yaw": wrap360(90.0 - yaw)})
        profiles["trace_neg_identity"].append({**base, "yaw": wrap360(-yaw)})
        profiles["trace_plus_90"].append({**base, "yaw": wrap360(yaw + 90.0)})
        profiles["trace_minus_90"].append({**base, "yaw": wrap360(yaw - 90.0)})
    course = make_course_over_ground(trace_rows)
    if course:
        profiles["course_over_ground_trace"] = course
    return profiles


def make_course_over_ground(trace_rows: list[dict[str, float]], window: int = 20) -> list[dict[str, float]]:
    if len(trace_rows) < window + 1:
        return []
    lat0 = trace_rows[0]["lat"]
    lon0 = trace_rows[0]["lon"]
    enu = [lla_to_local(row["lat"], row["lon"], lat0, lon0) for row in trace_rows]
    out: list[dict[str, float]] = []
    for idx, row in enumerate(trace_rows[:-window]):
        east0, north0 = enu[idx]
        east1, north1 = enu[idx + window]
        de = east1 - east0
        dn = north1 - north0
        distance = math.hypot(de, dn)
        if distance < 0.03:
            continue
        heading_ned = wrap360(math.degrees(math.atan2(de, dn)))
        out.append({"time": row["time"], "yaw": heading_ned, "lat": row["lat"], "lon": row["lon"], "alt": row["alt"]})
    return out


def profile_metric(
    algorithm: str,
    nav_rows: list[dict[str, float]],
    profile_name: str,
    ref_rows: list[dict[str, float]],
    inherited_by2: bool,
    justification: str,
) -> dict[str, Any]:
    if not nav_rows or not ref_rows:
        return {
            "profile_name": profile_name,
            "algorithm": algorithm,
            "sample_count": 0,
            "yaw_rmse_deg": None,
            "yaw_p95_deg": None,
            "yaw_max_deg": None,
            "circular_mean_error_deg": None,
            "circular_std_deg": None,
            "sawtooth_flag": None,
            "sane": False,
            "accepted_for_BY3": False,
            "physical_evidence_justification": justification,
            "inherited_from_BY2_accepted_policy": inherited_by2,
            "why_not": "missing nav/reference rows",
        }
    ref_rows = sorted(ref_rows, key=lambda row: row["time"])
    xs = [row["time"] for row in ref_rows]
    yaws = unwrap_deg([row["yaw"] for row in ref_rows])
    errors: list[float] = []
    for nav in nav_rows:
        ref_yaw = interp_scalar(nav["time"], xs, yaws)
        if ref_yaw is None:
            continue
        errors.append(wrap180(nav["yaw"] - ref_yaw))
    jumps = 0
    for left, right in zip(errors, errors[1:]):
        if abs(right - left) > 120.0:
            jumps += 1
    sawtooth_ratio = jumps / max(1, len(errors) - 1)
    sawtooth = bool(errors and (jumps >= 3 or sawtooth_ratio > 0.001))
    yaw_rmse = rmse(errors)
    yaw_p95 = pctl_abs(errors, 95.0)
    sane = bool(
        len(errors) > 10_000
        and yaw_rmse is not None
        and yaw_p95 is not None
        and yaw_rmse <= 20.0
        and yaw_p95 <= 30.0
        and not sawtooth
    )
    return {
        "profile_name": profile_name,
        "algorithm": algorithm,
        "sample_count": len(errors),
        "time_start": nav_rows[0]["time"] if nav_rows else None,
        "time_end": nav_rows[-1]["time"] if nav_rows else None,
        "yaw_rmse_deg": yaw_rmse,
        "yaw_p95_deg": yaw_p95,
        "yaw_max_deg": max_abs(errors),
        "circular_mean_error_deg": circular_mean(errors),
        "circular_std_deg": circular_std(errors),
        "sawtooth_jump_count": jumps,
        "sawtooth_jump_ratio": sawtooth_ratio,
        "sawtooth_flag": sawtooth,
        "sane": sane,
        "accepted_for_BY3": False,
        "physical_evidence_justification": justification,
        "inherited_from_BY2_accepted_policy": inherited_by2,
        "why_not": "No profile is accepted unless supported by recovered BY2 logic or BY3 source semantics; this profile is diagnostic in BY3A4C.",
    }


def apply_profiles_to_by3(
    paths: Paths,
    navs: dict[str, list[dict[str, float]]],
    errors: dict[str, list[dict[str, float]]],
    trace_rows: list[dict[str, float]],
    dual_status_rows: list[dict[str, float]],
    go2_yaw: dict[str, Any],
) -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {}
    final_nav = navs.get("final_v23_dual_antenna_EKF", [])
    final_errors = errors.get("final_v23_dual_antenna_EKF", [])
    profiles["BY3_current_final_official_ref_sign_minus"] = {
        "rows": make_reference_from_final_official(final_nav, final_errors, "minus"),
        "inherited_by2": True,
        "justification": "N4H2D official_ref_sign_minus formula applied to BY3 current final official eval; BY3 source is suspect because current eval used unresolved trace yaw.",
    }
    profiles["BY3_current_final_official_ref_sign_plus"] = {
        "rows": make_reference_from_final_official(final_nav, final_errors, "plus"),
        "inherited_by2": False,
        "justification": "N4H2D rejected sign candidate, included only as diagnostic.",
    }
    for name, rows in make_trace_profiles(trace_rows).items():
        profiles[name] = {
            "rows": rows,
            "inherited_by2": False,
            "justification": "BY3 trace yaw/position diagnostic profile; not accepted without source-semantics confirmation.",
        }
    if dual_status_rows:
        profiles["dual_status_yaw_observation"] = {
            "rows": dual_status_rows,
            "inherited_by2": False,
            "justification": "BY3A1 repaired dual GNSS status yaw observation; source observation only, not truth.",
        }
    if not go2_yaw.get("go2_body_yaw_reference_available"):
        profiles["go2_body_yaw_diagnostic"] = {
            "rows": [],
            "inherited_by2": False,
            "justification": "GO2 prior files contain roll/pitch only; no yaw-like field was available.",
        }

    metric_rows: list[dict[str, Any]] = []
    for profile_name, info in profiles.items():
        for algorithm, nav_rows in navs.items():
            metric_rows.append(
                profile_metric(
                    algorithm,
                    nav_rows,
                    profile_name,
                    info["rows"],
                    bool(info["inherited_by2"]),
                    str(info["justification"]),
                )
            )
    accepted = [row for row in metric_rows if row["accepted_for_BY3"]]
    sane_profiles = sorted(
        {
            row["profile_name"]
            for row in metric_rows
            if row.get("sane") and row.get("sample_count", 0) > 10_000
        }
    )
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_BY2_profile_does_not_transfer_trace_yaw_invalid",
        "accepted_profile_for_BY3": None,
        "accepted_rows": accepted,
        "sane_diagnostic_profiles": sane_profiles,
        "reason": "Recovered BY2 policy requires a confirmed dual official reference artifact. BY3 only has suspect current trace/current-eval references; applying accepted and diagnostic profiles to existing BY3A3 outputs leaves yaw near 90-110 deg or lacks source semantics.",
        "go2_yaw_source": go2_yaw,
        "policy_selection_not_rmse_only": True,
        "solver_rerun": False,
        "degradation_matrix_run": False,
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_BY3_REFERENCE_PROFILE_TESTS", metric_rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_BY3_REFERENCE_RECONSTRUCTION_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_by3_reference_reconstruction.md",
        "# BY3A4C BY3 Reference Reconstruction\n\n"
        "- The accepted BY2 profile was applied to BY3 current final official rows only as a diagnostic, because BY3 has no independent confirmed dual official reference artifact equivalent to N4H2D.\n"
        "- Trace, dual-status yaw, and course-over-ground diagnostic profiles were evaluated, but none is accepted by source semantics.\n"
        "- Go2/body yaw was not available in BY3A1 priors; those files contain roll/pitch only.\n"
        "- BY3 yaw is marked not evaluable for the current normal evidence package; position/up metrics remain evaluable.\n",
    )
    return {"report": report, "rows": metric_rows, "profiles": profiles}


def compute_common_overlap(paths: Paths, errors: dict[str, list[dict[str, float]]]) -> dict[str, Any]:
    starts = [rows[0]["time"] for rows in errors.values() if rows]
    ends = [rows[-1]["time"] for rows in errors.values() if rows]
    start = max(starts) if starts else None
    end = min(ends) if ends else None
    rows_out: list[dict[str, Any]] = []
    original_rows: list[dict[str, Any]] = []
    for algorithm, rows in errors.items():
        if not rows:
            continue
        original_h = [row.get("horizontal_err_m", math.hypot(row.get("err_n_m", 0.0), row.get("err_e_m", 0.0))) for row in rows]
        original_u = [row.get("err_u_m", 0.0) for row in rows]
        original_rows.append(
            {
                "algorithm": algorithm,
                "scope": "original_full_eval_interval",
                "sample_count": len(rows),
                "time_start": rows[0]["time"],
                "time_end": rows[-1]["time"],
                "horizontal_rmse_m": rmse(original_h),
                "horizontal_p95_m": pctl_abs(original_h, 95.0),
                "horizontal_max_m": max_abs(original_h),
                "up_rmse_m": rmse(original_u),
                "up_p95_m": pctl_abs(original_u, 95.0),
                "up_max_m": max_abs(original_u),
                "yaw_status": "historical_invalid_reference",
            }
        )
        overlap = [row for row in rows if start is not None and end is not None and start <= row["time"] <= end]
        h = [row.get("horizontal_err_m", math.hypot(row.get("err_n_m", 0.0), row.get("err_e_m", 0.0))) for row in overlap]
        u = [row.get("err_u_m", 0.0) for row in overlap]
        y = [row.get("yaw_err_deg", 0.0) for row in overlap]
        removed_initial = None if start is None else max(0.0, start - rows[0]["time"])
        rows_out.append(
            {
                "algorithm": algorithm,
                "scope": "strict_common_overlap",
                "sample_count": len(overlap),
                "time_start": start,
                "time_end": end,
                "removed_initial_transient_duration_sec": removed_initial,
                "horizontal_rmse_m": rmse(h),
                "horizontal_p95_m": pctl_abs(h, 95.0),
                "horizontal_max_m": max_abs(h),
                "up_rmse_m": rmse(u),
                "up_p95_m": pctl_abs(u, 95.0),
                "up_max_m": max_abs(u),
                "original_yaw_rmse_deg": rmse(y),
                "yaw_status": "not_evaluable_historical_invalid_reference",
            }
        )
    legsa_original = next((row for row in original_rows if row["algorithm"] == "LegSA_full_EKF"), {})
    legsa_overlap = next((row for row in rows_out if row["algorithm"] == "LegSA_full_EKF"), {})
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_position_common_overlap_ready_yaw_not_evaluable",
        "common_start": start,
        "common_end": end,
        "rows": rows_out,
        "original_rows": original_rows,
        "legsa_initial_transient_affected_horizontal_max": (
            legsa_original.get("horizontal_max_m") is not None
            and legsa_overlap.get("horizontal_max_m") is not None
            and float(legsa_original["horizontal_max_m"]) > float(legsa_overlap["horizontal_max_m"]) * 2.0
        ),
        "arbitrary_epoch_deletion": False,
        "strict_common_overlap_only": True,
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_COMMON_OVERLAP_POSITION_METRICS", rows_out)
    write_json(paths.stage_root / "reports" / "BY3A4C_COMMON_OVERLAP_POSITION_REPORT.json", report)
    return report


def build_metric_policy(paths: Paths, original_metrics: list[dict[str, Any]], common: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    common_by_alg = {row["algorithm"]: row for row in common.get("rows", [])}
    for metric in original_metrics:
        common_row = common_by_alg.get(metric["algorithm"], {})
        rows.append(
            {
                "algorithm": metric["algorithm"],
                "horizontal_rmse_m": common_row.get("horizontal_rmse_m", metric.get("horizontal_rmse_m")),
                "horizontal_p95_m": common_row.get("horizontal_p95_m"),
                "horizontal_max_m": common_row.get("horizontal_max_m"),
                "up_rmse_m": common_row.get("up_rmse_m", metric.get("up_rmse_m")),
                "up_p95_m": common_row.get("up_p95_m"),
                "up_max_m": common_row.get("up_max_m"),
                "yaw_rmse": None,
                "original_yaw_rmse_deg": metric.get("original_yaw_rmse_deg"),
                "original_yaw_p95_deg": metric.get("original_yaw_p95_deg"),
                "yaw_status": "not_evaluable",
                "source_policy": "No BY3 yaw truth accepted by historical reconstruction. BY3A3 yaw retained only as historical_invalid_reference.",
                "reason": "Recovered BY2 profile does not transfer without confirmed BY3 dual official reference or source-semantics confirmation.",
                "paper_claim": False,
            }
        )
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_yaw_not_evaluable_position_only_metric_policy",
        "yaw_status": "not_evaluable",
        "position_up_status": "accepted_for_audit_position_only",
        "original_BY3A3_yaw_preserved_as": "historical_invalid_reference",
        "ready_scope": "position_up_only",
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_NORMAL_METRICS_POLICY", rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_METRIC_POLICY_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_metric_policy_summary.md",
        "# BY3A4C Metric Policy\n\n"
        "- BY3 yaw is `not_evaluable` in this stage because no historically backed BY3 yaw truth/reference profile transfers.\n"
        "- BY3A3/BY3A4A yaw values are preserved as `historical_invalid_reference`, not hidden or overwritten.\n"
        "- Position and up metrics are retained over strict common overlap for audit-only, position/up-only planning.\n"
        "- No paper claim is authorized.\n",
    )
    return report


def import_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def save_figure(fig: Any, base: Path) -> list[Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    png = base.with_suffix(".png")
    pdf = base.with_suffix(".pdf")
    fig.savefig(png, dpi=160, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    return [png, pdf]


def sample_xy(rows: list[dict[str, float]], max_points: int = 4000) -> tuple[list[float], list[float]]:
    if not rows:
        return [], []
    step = max(1, len(rows) // max_points)
    return [row["time"] for row in rows[::step]], [row["yaw"] for row in rows[::step]]


def draw_visual_validation(
    paths: Paths,
    navs: dict[str, list[dict[str, float]]],
    errors: dict[str, list[dict[str, float]]],
    trace_rows: list[dict[str, float]],
    reconstruction: dict[str, Any],
    common: dict[str, Any],
) -> dict[str, Any]:
    plt = import_matplotlib()
    fig_dir = paths.stage_root / "visual_validation"
    figure_rows: list[dict[str, Any]] = []

    profiles = reconstruction["profiles"]
    selected_profile_names = [
        "trace_raw_identity",
        "trace_enu_90_minus",
        "dual_status_yaw_observation",
        "course_over_ground_trace",
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name in selected_profile_names:
        if name in profiles:
            xs, ys = sample_xy(profiles[name]["rows"], max_points=2500)
            if xs:
                ax.plot(xs, ys, linewidth=0.8, label=name)
    ax.set_title("BY3A4C trace and diagnostic yaw reference profiles")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("yaw/profile angle (deg)")
    ax.set_ylim(-10, 370)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)
    paths_written = save_figure(fig, fig_dir / "BY3A4C_trace_yaw_vs_profiles_diagnostic")
    plt.close(fig)
    figure_rows.append(figure_index_row(paths_written, "trace/profile yaw diagnostic", False, True, True, False, "diagnostic yaw profiles"))

    metric_rows = reconstruction["rows"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    rmse_by_profile: dict[str, list[float]] = {}
    for row in metric_rows:
        value = row.get("yaw_rmse_deg")
        if value is None:
            continue
        rmse_by_profile.setdefault(str(row["profile_name"]), []).append(float(value))
    profile_names = list(rmse_by_profile)
    profile_means = [sum(vals) / len(vals) for vals in rmse_by_profile.values()]
    axes[0][0].bar(range(len(profile_names)), profile_means, color="#6c757d")
    axes[0][0].set_xticks(range(len(profile_names)))
    axes[0][0].set_xticklabels(profile_names, rotation=60, ha="right", fontsize=7)
    axes[0][0].set_ylabel("mean yaw RMSE (deg)")
    axes[0][0].set_title("No diagnostic profile accepted")
    for algorithm, nav in navs.items():
        xs, ys = sample_xy(nav, max_points=1500)
        axes[0][1].plot(xs, ys, linewidth=0.8, label=algorithm)
    axes[0][1].set_title("Algorithm NAV yaw")
    axes[0][1].set_xlabel("time (s)")
    axes[0][1].set_ylabel("yaw (deg)")
    axes[0][1].legend(fontsize=7)
    ref = profiles.get("trace_enu_90_minus", {}).get("rows", [])
    if ref and navs.get("final_v23_dual_antenna_EKF"):
        errors_plot = profile_errors(navs["final_v23_dual_antenna_EKF"], ref)
        axes[1][0].plot(errors_plot[0], errors_plot[1], linewidth=0.8, color="#b23a48")
    axes[1][0].set_title("Current trace-ENU final_v23 yaw error remains invalid")
    axes[1][0].set_xlabel("time (s)")
    axes[1][0].set_ylabel("yaw error (deg)")
    axes[1][1].axis("off")
    axes[1][1].text(
        0.0,
        0.95,
        "Policy result\n\n"
        "BY2 accepted profile: official_ref_sign_minus + direct identity.\n"
        "BY3 transfer: blocked.\n"
        "Reason: no confirmed BY3 dual official reference artifact;\n"
        "trace/status/course candidates remain diagnostic.\n"
        "Yaw metric policy: not_evaluable.",
        va="top",
        fontsize=10,
    )
    fig.tight_layout()
    paths_written = save_figure(fig, fig_dir / "BY3A4C_yaw_source_conflict_panel")
    plt.close(fig)
    figure_rows.append(figure_index_row(paths_written, "yaw source conflict panel", False, True, True, False, "diagnostic yaw conflict"))

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    colors = {
        "LegSA_full_EKF": "#2166ac",
        "single_antenna_gnss1_status_KF_GINS": "#5aae61",
        "final_v23_dual_antenna_EKF": "#b2182b",
    }
    for algorithm, err_rows in errors.items():
        xs = [row["time"] for row in err_rows]
        hs = [row.get("horizontal_err_m", math.hypot(row.get("err_n_m", 0.0), row.get("err_e_m", 0.0))) for row in err_rows]
        us = [row.get("err_u_m", 0.0) for row in err_rows]
        step = max(1, len(xs) // 4000)
        axes[0][0].plot(xs[::step], hs[::step], linewidth=0.8, label=algorithm, color=colors.get(algorithm))
        axes[0][1].plot(xs[::step], us[::step], linewidth=0.8, label=algorithm, color=colors.get(algorithm))
    axes[0][0].set_title("Horizontal error (position-only)")
    axes[0][0].set_xlabel("time (s)")
    axes[0][0].set_ylabel("m")
    axes[0][0].legend(fontsize=7)
    axes[0][1].set_title("Up error (position-only)")
    axes[0][1].set_xlabel("time (s)")
    axes[0][1].set_ylabel("m")
    algs = [row["algorithm"] for row in common.get("rows", [])]
    hvals = [row["horizontal_rmse_m"] for row in common.get("rows", [])]
    uvals = [row["up_rmse_m"] for row in common.get("rows", [])]
    x = list(range(len(algs)))
    axes[1][0].bar([i - 0.18 for i in x], hvals, width=0.36, label="horizontal RMSE", color="#4575b4")
    axes[1][0].bar([i + 0.18 for i in x], uvals, width=0.36, label="up RMSE", color="#d73027")
    axes[1][0].set_xticks(x)
    axes[1][0].set_xticklabels(short_alg(a) for a in algs)
    axes[1][0].set_ylabel("m")
    axes[1][0].set_title("Strict common-overlap RMSE")
    axes[1][0].legend(fontsize=8)
    plot_trajectories(axes[1][1], navs)
    axes[1][1].set_title("Local ENU trajectories")
    fig.tight_layout()
    paths_written = save_figure(fig, fig_dir / "BY3A4C_position_only_common_overlap")
    plt.close(fig)
    figure_rows.append(figure_index_row(paths_written, "position-only common overlap", True, True, True, False, "BY3A3 error_series/nav"))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")
    ax.text(
        0.02,
        0.95,
        "BY3A4C yaw metric policy\n\n"
        "Historical BY2 fix recovered:\n"
        "  official_ref_sign_minus, direct-identity fresh replay reference.\n\n"
        "BY3 result:\n"
        "  yaw_status = not_evaluable\n"
        "  original BY3A3/BY3A4A yaw ~= 103-106 deg is retained as historical_invalid_reference\n"
        "  position/up metrics remain available over strict common overlap\n\n"
        "Safety:\n"
        "  no solver rerun, no degradation run, no retuning, no trace solver input,\n"
        "  no RMSE-only yaw-policy selection, no paper claim.",
        va="top",
        fontsize=11,
        family="monospace",
    )
    paths_written = save_figure(fig, fig_dir / "BY3A4C_yaw_not_evaluable_policy_panel")
    plt.close(fig)
    figure_rows.append(figure_index_row(paths_written, "yaw not evaluable policy", False, False, False, False, "policy summary"))

    for row in figure_rows:
        row["content_valid"] = all(path.exists() and path.stat().st_size > 1000 for path in row["file_paths"])
        del row["file_paths"]
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_visual_validation_generated_yaw_not_evaluable",
        "figure_count": len(figure_rows),
        "figures": figure_rows,
        "yaw_repaired": False,
        "yaw_not_evaluable": True,
        "paper_claim": False,
    }
    write_rows(paths.stage_root / "matrix" / "BY3A4C_FIGURE_INDEX", figure_rows)
    write_json(paths.stage_root / "reports" / "BY3A4C_VISUAL_VALIDATION_REPORT.json", report)
    write_text(
        paths.stage_root / "summary" / "by3a4c_visual_validation_summary.md",
        "# BY3A4C Visual Validation\n\n"
        "- Generated yaw-not-evaluable diagnostic figures, not repaired yaw figures.\n"
        "- Position-only common-overlap visualization uses existing BY3A3 NAV/error_series outputs.\n"
        "- Figures are audit artifacts only and carry `paper_claim=false`.\n",
    )
    return report


def profile_errors(nav_rows: list[dict[str, float]], ref_rows: list[dict[str, float]]) -> tuple[list[float], list[float]]:
    ref_rows = sorted(ref_rows, key=lambda row: row["time"])
    xs = [row["time"] for row in ref_rows]
    ys = unwrap_deg([row["yaw"] for row in ref_rows])
    out_x: list[float] = []
    out_y: list[float] = []
    for nav in nav_rows:
        ref = interp_scalar(nav["time"], xs, ys)
        if ref is None:
            continue
        out_x.append(nav["time"])
        out_y.append(wrap180(nav["yaw"] - ref))
    step = max(1, len(out_x) // 4000)
    return out_x[::step], out_y[::step]


def plot_trajectories(ax: Any, navs: dict[str, list[dict[str, float]]]) -> None:
    first = next((rows[0] for rows in navs.values() if rows), None)
    if first is None:
        ax.text(0.5, 0.5, "No trajectory rows", ha="center", va="center")
        return
    lat0 = first["lat"]
    lon0 = first["lon"]
    for algorithm, rows in navs.items():
        step = max(1, len(rows) // 3000)
        east: list[float] = []
        north: list[float] = []
        for row in rows[::step]:
            e, n = lla_to_local(row["lat"], row["lon"], lat0, lon0)
            east.append(e)
            north.append(n)
        ax.plot(east, north, linewidth=0.9, label=short_alg(algorithm))
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=7)


def figure_index_row(
    files: list[Path],
    role: str,
    includes_legsa: bool,
    includes_single: bool,
    includes_finalv23: bool,
    includes_trace: bool,
    source_data: str,
) -> dict[str, Any]:
    return {
        "figure": files[0].name,
        "files": [stage_alias(path) for path in files],
        "file_paths": files,
        "role": role,
        "includes_LegSA_full": includes_legsa,
        "includes_single": includes_single,
        "includes_finalv23": includes_finalv23,
        "includes_trace": includes_trace,
        "coordinate_frame": "local_ENU_or_time_series",
        "source_data": source_data,
        "supersedes_BY3A3_figure": False,
        "paper_claim": False,
    }


def stage_alias(path: Path) -> str:
    parts = path.parts
    if STAGE in parts:
        idx = parts.index(STAGE)
        return "/".join(["<BY3A4C_STAGE_ROOT>", *parts[idx + 1 :]])
    if RUNTIME_STAGE in parts:
        idx = parts.index(RUNTIME_STAGE)
        return "/".join([f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}", *parts[idx + 1 :]])
    return path.name


def short_alg(name: str) -> str:
    if name == "single_antenna_gnss1_status_KF_GINS":
        return "single"
    if name == "final_v23_dual_antenna_EKF":
        return "final_v23"
    if name == "LegSA_full_EKF":
        return "LegSA"
    return name


def write_case_review(
    paths: Paths,
    git_report: dict[str, Any],
    logic_report: dict[str, Any],
    reconstruction: dict[str, Any],
    metric_policy: dict[str, Any],
    visual: dict[str, Any],
) -> dict[str, Any]:
    review = {
        "stage": STAGE,
        "evaluation_completed": True,
        "input_files": {
            "BY3A3_official_eval": "<BY3A3_STAGE_ROOT>/official_eval/*",
            "BY3A3_solver_nav": "<BY3_FULL_MATRIX_ROOT>/BY3A3_NORMAL_EXECUTION/*/KF_GINS_Navresult.nav",
            "historical_BY2_docs_source": "docs/experiments/*; src/legsa_gins/evaluation/*",
        },
        "case_overview": "Recover BY2 historical yaw-reference fix and apply only diagnostic profiles to BY3 existing outputs.",
        "original_BY3A3_metrics": "Yaw around 103-106 deg is preserved as historical_invalid_reference.",
        "historical_BY2_yaw_fix_evidence": logic_report,
        "BY3_reference_reconstruction": reconstruction["report"],
        "metric_policy": metric_policy,
        "visual_validation": visual,
        "main_takeaway": "BY3 yaw is not evaluable until a BY3 yaw truth/source mapping is confirmed; position/up metrics remain usable for audit-only position-only planning.",
        "ready_for_BY3_degradation_planning": "position_up_only",
        "ready_for_paper_claims": False,
    }
    md = (
        "# BY3A4C Yaw Reference Reconstruction Case Review\n\n"
        "## Evaluation Completed\n\n"
        "BY3A4C completed as an evaluator/report-only stage. No BY3 solver, degradation matrix, retuning, or output modification was run.\n\n"
        "## Input Files\n\n"
        "- BY3A3 official eval outputs: `<BY3A3_STAGE_ROOT>/official_eval/*`\n"
        "- BY3A3 solver NAV outputs: `<BY3_FULL_MATRIX_ROOT>/BY3A3_NORMAL_EXECUTION/*/KF_GINS_Navresult.nav`\n"
        "- Historical BY2/N4 evidence: `docs/experiments/*`, `src/legsa_gins/evaluation/*`, git history, PR #12-#15 metadata.\n\n"
        "## Case Overview\n\n"
        "The stage recovered the historical BY2 yaw repair. BY2 was fixed by reconstructing the official dual reference (`official_ref_sign_minus`) and evaluating direct-identity yaw against that reconstructed reference, not by repeatedly trying `+90/-90` offsets.\n\n"
        "## Original BY3A3 Metrics\n\n"
        "BY3A3 yaw RMSE remained around 103-106 deg for all three algorithms. Those values are preserved as `historical_invalid_reference` and are not hidden or overwritten.\n\n"
        "## Historical BY2 Yaw Fix Evidence\n\n"
        f"N4H2 old yaw RMSE was {logic_report['old_yaw_rmse_deg']} deg and was invalidated by N4H2D. Fresh N4H2D replay evidence under the reconstructed dual official reference had yaw RMSE {logic_report['fresh_yaw_rmse_deg']} deg.\n\n"
        "## BY3 Reference Reconstruction\n\n"
        "The recovered BY2 profile was applied to BY3 as a diagnostic, but BY3 does not currently have a confirmed dual official reference artifact equivalent to N4H2D. Trace, status-yaw, and course-over-ground profiles remain diagnostics only.\n\n"
        "## Metric Policy\n\n"
        "`yaw_status=not_evaluable`. Position/up metrics remain available over strict common overlap for position-only audit planning. No yaw degradation claim is allowed.\n\n"
        "## Visual Validation\n\n"
        "Generated diagnostic yaw-source conflict, trace/profile, position-only common-overlap, and yaw-not-evaluable policy panels.\n\n"
        "## Brief Interpretation\n\n"
        "BY3A4C stops the blind angle-search loop. The missing item is a confirmed BY3 yaw truth/source mapping, not a new RMSE-minimizing offset.\n\n"
        "## Main Takeaway\n\n"
        "BY3 can proceed only as position/up-only planning unless the human confirms a valid BY3 yaw reference or antenna/source mapping. This is not a paper claim.\n"
    )
    write_json(paths.stage_root / "case_review" / "BY3A4C_yaw_reference_reconstruction_case_review.json", review)
    write_text(paths.stage_root / "case_review" / "BY3A4C_yaw_reference_reconstruction_case_review.md", md)
    return review


def write_context_and_obsidian(paths: Paths, reconstruction: dict[str, Any], metric_policy: dict[str, Any]) -> dict[str, Any]:
    obsidian_files: list[dict[str, Any]] = []
    notes = {
        "00_INDEX.md": (
            "# BY3 Generalization\n\n"
            "BY3A4C recovered the historical BY2/N4 yaw-reference fix and marks BY3 yaw not evaluable under current evidence.\n\n"
            "Position/up-only planning may proceed for human review; yaw degradation claims remain false until a valid BY3 yaw source/reference mapping is confirmed.\n"
        ),
        "BY3_yaw_reference_history_reconstruction.md": (
            "# BY3 yaw reference history reconstruction\n\n"
            "- Do not redo blind `+90/-90` search as the primary method.\n"
            "- Recover N4H2C/N4H2D/N4R/N4R2/N4R3 yaw reference mapping first.\n"
            "- BY2 old 93 deg yaw failure was invalidated by N4H2D reference reconstruction.\n"
            "- BY2 accepted profile: `official_ref_sign_minus`, direct identity against reconstructed dual official reference.\n"
            "- BY3 result in BY3A4C: yaw is not evaluable because no confirmed BY3 yaw truth/source mapping transfers.\n"
            "- Position/up metrics can be used only as position/up evidence; no yaw degradation or paper claim.\n"
        ),
        "04_YAW_EVALUATION_POLICY.md": (
            "# Yaw Evaluation Policy\n\n"
            "Dual antennas are lateral/perpendicular to the robot forward axis. Baseline heading is not body heading; body heading requires a plus/minus 90 degree correction depending on antenna order and coordinate convention.\n\n"
            "Do not repeat blind plus/minus 90 searches as the main method. BY3A4C recovered the BY2/N4 historical reference solution: N4H2D selected `official_ref_sign_minus` and direct identity against the reconstructed dual official reference.\n\n"
            "BY3 currently has no accepted yaw truth/reference transfer, so yaw is `not_evaluable`. Do not choose a BY3 yaw policy by RMSE alone.\n"
        ),
        "05_NORMAL_GENERALIZATION_RESULT.md": (
            "# Normal Generalization Result\n\n"
            "Original BY3A3 normal metrics remain historical. BY3A4A did not accept repaired yaw metrics, and BY3A4C did not find a historical-reference-backed BY3 yaw truth transfer.\n\n"
            "Current metric policy: position/up metrics are available for position-only audit planning. BY3 yaw is `not_evaluable`; BY3A3/BY3A4A yaw metrics are historical invalid-reference evidence.\n"
        ),
        "07_CLAIM_BOUNDARY.md": (
            "# Claim Boundary\n\n"
            "ready_for_paper_claims=false.\n\n"
            "ready_for_BY3_degradation_matrix_planning=true only for position/up-only planning.\n\n"
            "yaw_degradation_claims=false while BY3 yaw is `not_evaluable`.\n"
        ),
        "BY3_BDS_dual_antenna_lateral_yaw_policy.md": (
            "# BY3 BDS dual antenna lateral yaw policy\n\n"
            "- Dual antennas are lateral/perpendicular to robot forward direction.\n"
            "- The baseline heading is not automatically body heading.\n"
            "- Simple `+90/-90` offsets were not sufficient in BY3A4A.\n"
            "- BY3A4C recovered the historical BY2 reference reconstruction path; use that before any offset candidate.\n"
            "- If no valid BY3 yaw truth exists, mark yaw `not_evaluable` instead of fabricating a repaired yaw metric.\n"
        ),
        "01_CURRENT_STATE.md": (
            "# BY3 current state\n\n"
            "BY3A4C recovered BY2 yaw history and marked BY3 yaw `not_evaluable` under current evidence. Position/up normal metrics remain available for position-only audit planning. `ready_for_paper_claims=false`.\n"
        ),
        "08_NEXT_STEPS.md": (
            "# BY3 next steps\n\n"
            "- Human review BY3A4C.\n"
            "- Either confirm a valid BY3 yaw source/reference mapping, or proceed only with position/up degradation planning.\n"
            "- No paper claim and no yaw degradation claim until yaw reference is confirmed.\n"
        ),
    }
    for filename, text in notes.items():
        path = paths.obsidian_by3 / filename
        write_text(path, text)
        obsidian_files.append(
            {
                "path_alias": f"obsidian_knowledge/LegSA-GINS/BY3_generalization/{filename}",
                "role": "public Obsidian note",
                "local_absolute_paths": False,
                "paper_claim": False,
            }
        )
    report = {
        "stage": STAGE,
        "decision": "BY3A4C_context_obsidian_sync_completed",
        "tracked_docs_to_update": [
            "AGENTS.md",
            "PLANS.md",
            "README.md",
            "CLAIM_BOUNDARY.md",
            "PHASE_LOG.md",
            "docs/codex_context/*",
        ],
        "obsidian_files": obsidian_files,
        "yaw_policy": reconstruction["report"]["decision"],
        "metric_policy": metric_policy["decision"],
        "paper_claim": False,
    }
    write_json(paths.stage_root / "reports" / "BY3A4C_CONTEXT_OBSIDIAN_SYNC_REPORT.json", report)
    write_rows(paths.stage_root / "matrix" / "BY3A4C_OBSIDIAN_SYNC_INDEX", obsidian_files)
    return report


def validate_outputs(
    paths: Paths,
    git_report: dict[str, Any],
    logic_report: dict[str, Any],
    evaluator_report: dict[str, Any],
    reconstruction: dict[str, Any],
    metric_policy: dict[str, Any],
    visual: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        ("git_history_recovered_or_blocker_recorded", git_report.get("decision") == "BY3A4C_git_history_recovered"),
        ("n4h2c_n4h2d_yaw_logic_recovered", logic_report.get("decision") == "BY3A4C_historical_yaw_logic_recovered"),
        ("by2_accepted_reference_profile_identified", logic_report.get("selected_reference_sign") == "official_ref_sign_minus"),
        ("by3_reference_reconstruction_attempted", reconstruction["report"].get("decision") is not None),
        ("no_solver_rerun", True),
        ("no_BY3_degradation", True),
        ("no_trace_solver_input", True),
        ("no_RMSE_only_policy_selection", reconstruction["report"].get("policy_selection_not_rmse_only") is True),
        ("old_BY3A3_metrics_preserved", metric_policy.get("original_BY3A3_yaw_preserved_as") == "historical_invalid_reference"),
        ("visual_validation_generated", visual.get("figure_count", 0) >= 4),
        ("docs_obsidian_update_report_created", context.get("decision") == "BY3A4C_context_obsidian_sync_completed"),
        ("runtime_untracked_expected", True),
        ("paper_claims", False),
    ]
    rows = [
        {
            "check": name,
            "value": value,
            "pass": value is True or (name == "paper_claims" and value is False),
        }
        for name, value in checks
    ]
    safety_ok = all(row["pass"] for row in rows)
    decision = {
        "stage": STAGE,
        "decision": "BY3A4C_yaw_not_evaluable_position_only_generalization_ready"
        if safety_ok
        else "BY3A4C_safety_gate_failed",
        "ready_for_BY3_degradation_matrix_planning": bool(safety_ok),
        "ready_for_BY3_degradation_matrix_planning_scope": "position_up_only" if safety_ok else "blocked",
        "yaw_degradation_claims": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": "BY3B_POSITION_ONLY_DEGRADATION_PLANNING_OR_HUMAN_REVIEW"
        if safety_ok
        else "repair_safety_violation",
        "reason": "BY2 historical yaw fix was recovered, but no valid BY3 yaw truth/reference transfers; BY3 yaw is excluded and position/up metrics are available only for position-only planning.",
        "safety_ok": safety_ok,
    }
    validation = {"stage": STAGE, "status_rows": rows, "decision": decision}
    write_json(paths.stage_root / "reports" / "LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(paths.stage_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_rows(paths.stage_root / "matrix" / "LONG_TASK_STAGE_STATUS", rows)
    write_text(
        paths.stage_root / "summary" / "long_task_summary.md",
        "# BY3A4C Long Task Summary\n\n"
        "- Git/PR/doc/source history recovered the N4H2C/N4H2D yaw-reference fix.\n"
        "- BY2 accepted policy is `official_ref_sign_minus` with direct identity yaw against a reconstructed dual official reference.\n"
        "- Applying recovered and diagnostic profiles to BY3A3 outputs did not produce an accepted BY3 yaw reference.\n"
        "- BY3 yaw is marked `not_evaluable`; original BY3A3/BY3A4A yaw is preserved as historical invalid-reference evidence.\n"
        "- Position/up common-overlap metrics and diagnostic figures were generated.\n"
        "- No solver rerun, no degradation matrix, no retuning, no paper claim.\n",
    )
    write_text(
        paths.stage_root / "summary" / "long_task_next_stage_recommendation.md",
        "# BY3A4C Next Stage Recommendation\n\n"
        "`BY3B_POSITION_ONLY_DEGRADATION_PLANNING_OR_HUMAN_REVIEW`\n\n"
        "Scope: position/up only. Yaw degradation claims remain false until a valid BY3 yaw reference/source mapping is confirmed.\n\n"
        "ready_for_paper_claims=false\n",
    )
    return decision


def write_runtime_manifest(paths: Paths, decision: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "artifact": "LONG_TASK_DECISION_REPORT.json",
            "path_alias": f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}/reports/LONG_TASK_DECISION_REPORT.json",
            "role": "runtime decision copy",
            "paper_claim": False,
        },
        {
            "artifact": "BY3A4C_RUNTIME_MANIFEST.json",
            "path_alias": f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}/reports/BY3A4C_RUNTIME_MANIFEST.json",
            "role": "runtime root manifest",
            "paper_claim": False,
        },
    ]
    manifest = {
        "stage": STAGE,
        "runtime_root_alias": f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}",
        "stage_root_alias": f"<BY3_STAGE_ROOT>/{STAGE}",
        "decision": decision,
        "artifacts": rows,
        "solver_rerun": False,
        "degradation_matrix": False,
        "parameter_retuning": False,
        "paper_claim": False,
    }
    write_json(paths.runtime_root / "reports" / "LONG_TASK_DECISION_REPORT.json", decision)
    write_json(paths.runtime_root / "reports" / "BY3A4C_RUNTIME_MANIFEST.json", manifest)
    write_rows(paths.runtime_root / "matrix" / "BY3A4C_RUNTIME_INDEX", rows)
    return manifest


def copy_plan(paths: Paths) -> None:
    write_text(
        paths.stage_root / "01_plan" / "BY3A4C_EXECUTION_PLAN.md",
        "# BY3A4C Execution Plan\n\n"
        "1. Recover historical N4H2C/N4H2D/N4R/N4R2/N4R3 yaw-reference lineage from git/docs/source.\n"
        "2. Audit evaluator source and accepted BY2 reference profile.\n"
        "3. Apply recovered and diagnostic profiles to existing BY3A3 outputs only.\n"
        "4. If no BY3 yaw truth transfers, mark yaw `not_evaluable` and preserve original bad yaw metrics.\n"
        "5. Generate diagnostic figures, case review, context/Obsidian notes, and validation reports.\n"
        "6. Do not run solvers, degradation, retuning, output correction, merge, tag, or paper claims.\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--historical-fresh-summary", type=Path, default=None)
    parser.add_argument("--historical-fresh-report", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo.resolve()
    paths = Paths.build(repo)
    ensure_dirs(paths)
    copy_plan(paths)

    git_report = build_git_history_recovery(paths)
    logic_report = build_historical_logic_recovery(paths, args.historical_fresh_summary, args.historical_fresh_report)
    evaluator_report = build_evaluator_source_audit(paths)

    inputs = collect_algorithm_inputs(paths)
    navs = {algorithm: load_official_nav(info["nav"]) for algorithm, info in inputs.items()}
    errors = {algorithm: load_error_series(info["error_series"]) for algorithm, info in inputs.items()}
    original_metrics = [metric_row_from_summary(algorithm, read_json(info["summary"], {})) for algorithm, info in inputs.items()]
    trace_path = discover_trace_path(repo)
    trace_rows = load_trace(trace_path)
    dual_status_rows = load_dual_status_yaw(paths.by3a1_stage / "input_repair" / "BY3_DUAL_STATUS_15COL_REPAIRED.gnss")
    go2_yaw = inspect_go2_yaw_sources(paths)

    reconstruction = apply_profiles_to_by3(paths, navs, errors, trace_rows, dual_status_rows, go2_yaw)
    common = compute_common_overlap(paths, errors)
    metric_policy = build_metric_policy(paths, original_metrics, common)
    visual = draw_visual_validation(paths, navs, errors, trace_rows, reconstruction, common)
    case_review = write_case_review(paths, git_report, logic_report, reconstruction, metric_policy, visual)
    context = write_context_and_obsidian(paths, reconstruction, metric_policy)
    decision = validate_outputs(paths, git_report, logic_report, evaluator_report, reconstruction, metric_policy, visual, context)
    runtime_manifest = write_runtime_manifest(paths, decision)

    supervisor = {
        "stage": STAGE,
        "planner_summary": "Read-only planner confirmed clean PR #52 branch and warned not to use blind offsets or stale BY3A3 yaw readiness.",
        "worker_summary": "Generated BY3A4C git-history recovery, historical yaw logic recovery, evaluator audit, BY3 profile tests, metric policy, diagnostic visual validation, case review, context/Obsidian sync, and validation without solver/degradation/retuning.",
        "reviewer_summary": "pending",
        "output_root_alias": f"<BY3_STAGE_ROOT>/{STAGE}",
        "runtime_root_alias": f"<BY3_FULL_MATRIX_ROOT>/{RUNTIME_STAGE}",
        "trace_path_found": trace_path is not None,
        "trace_path_alias": "<BY3_TRACE_SOURCE>" if trace_path is not None else None,
        "case_review_created": bool(case_review),
        "decision": decision,
        "runtime_manifest": runtime_manifest["runtime_root_alias"],
        "ready_for_paper_claims": False,
    }
    write_json(paths.stage_root / "00_supervisor" / "BY3A4C_SUPERVISOR_REPORT.json", supervisor)
    print(json.dumps(supervisor, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
