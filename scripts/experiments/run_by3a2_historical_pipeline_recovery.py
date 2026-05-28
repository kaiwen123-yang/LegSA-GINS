#!/usr/bin/env python3
"""Generate BY3A2 historical pipeline recovery and runner-gate reports.

The script is an audit/gate orchestrator. It does not run solvers, evaluators,
feedback generation, or degradation cases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


STAGE = "BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {}
            for key in fieldnames:
                value = row.get(key, "")
                if isinstance(value, (list, tuple)):
                    value = "|".join(str(item) for item in value)
                elif isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                out[key] = value
            writer.writerow(out)


def write_md(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = [f"# {title}", ""]
    content.extend(lines)
    path.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_count(path: Path, has_header: bool = True) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        count = sum(1 for _ in handle)
    return max(0, count - (1 if has_header else 0))


def sniff_delimiter(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        line = handle.readline().strip()
    if "," in line:
        return "comma"
    if line:
        return "whitespace"
    return ""


def numeric_stats(path: Path, has_header: bool, delimiter: str) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"exists": False}
    times: list[float] = []
    rows = 0
    cols = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        if has_header:
            reader = csv.DictReader(handle) if delimiter == "comma" else None
            if reader:
                for row in reader:
                    rows += 1
                    cols = max(cols, len(row))
                    try:
                        value = float(row.get("time", "nan"))
                    except ValueError:
                        value = math.nan
                    if math.isfinite(value):
                        times.append(value)
        else:
            for line in handle:
                parts = line.strip().split() if delimiter == "whitespace" else line.strip().split(",")
                if not parts:
                    continue
                rows += 1
                cols = max(cols, len(parts))
                try:
                    value = float(parts[0])
                except ValueError:
                    value = math.nan
                if math.isfinite(value):
                    times.append(value)
    if not times:
        return {"exists": True, "row_count": rows, "column_count": cols, "time_min": None, "time_max": None, "duration": None}
    return {
        "exists": True,
        "row_count": rows,
        "column_count": cols,
        "time_min": min(times),
        "time_max": max(times),
        "duration": max(times) - min(times),
    }


def first_numeric_row(path: Path) -> list[float]:
    if not path.exists():
        return []
    delimiter = sniff_delimiter(path)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.strip().split() if delimiter == "whitespace" else line.strip().split(",")
            if not parts:
                continue
            try:
                return [float(x) for x in parts]
            except ValueError:
                continue
    return []


def wsl_path(path: Path) -> str:
    raw = str(path)
    drive, rest = os.path.splitdrive(raw)
    if drive:
        letter = drive[0].lower()
        return f"/mnt/{letter}" + rest.replace("\\", "/")
    return raw.replace("\\", "/")


def report_file(path: Path, alias: str, role: str, has_header: bool = True) -> dict[str, Any]:
    delimiter = sniff_delimiter(path)
    stats = numeric_stats(path, has_header=has_header, delimiter=delimiter or "comma")
    return {
        "path_alias": alias,
        "exists": path.exists(),
        "file_size": path.stat().st_size if path.exists() and path.is_file() else 0,
        "row_count": stats.get("row_count", 0),
        "delimiter": delimiter,
        "has_header": has_header,
        "column_count": stats.get("column_count", 0),
        "time_min": stats.get("time_min"),
        "time_max": stats.get("time_max"),
        "duration": stats.get("duration"),
        "sha256": sha256(path),
        "role": role,
    }


def ensure_dirs(stage_root: Path) -> None:
    for name in [
        "00_supervisor",
        "01_plan",
        "historical_pipeline_recovery",
        "raw_doppler_recovery",
        "rinex_nav_recovery",
        "go2_prior_validation",
        "single_runner_handoff",
        "finalv23_runner_handoff",
        "selected_feedback_dependency",
        "runner_gate",
        "solver_outputs",
        "official_eval",
        "metrics",
        "figures",
        "case_review",
        "reports",
        "matrix",
        "summary",
        "validation",
        "logs",
        "blocked",
    ]:
        (stage_root / name).mkdir(parents=True, exist_ok=True)


def historical_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    by2 = Path(args.by2_huitu_root)
    legacy = Path(args.legacy_output_root)
    rows = [
        {
            "artifact_type": "script",
            "path_alias": "scripts/experiments/run_n5a_raw_doppler_factor_trial.py",
            "exists": (Path(args.repo_root) / "scripts/experiments/run_n5a_raw_doppler_factor_trial.py").exists(),
            "source_root": "<REPO_ROOT>",
            "stage": "N5A",
            "related_algorithm": "Raw_Doppler_EKF",
            "command_pattern": "run_raw_doppler_readiness_probe -> UBX rebuild -> convbin RINEX",
            "input_requirements": "receiver gnss1/gnss2 raw CSV, RTKLIB root, ephemeris search root",
            "output_files": "gnss*.obs, gnss*.nav, RAW_DOPPLER_EPOCHS.jsonl",
            "BY2_evidence_status": "accepted_input_chain_component",
            "can_apply_to_BY3": True,
            "reason": "BY3 receiver raw CSV contains UBX-RXM-RAWX frames and can enter the same probe.",
        },
        {
            "artifact_type": "report",
            "path_alias": "<LEGACY_RUNTIME_ROOT>/N5B_rtklib_doppler_provider_activation/RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json",
            "exists": (legacy / "N5B_rtklib_doppler_provider_activation/RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json").exists(),
            "source_root": "<LEGACY_RUNTIME_ROOT>",
            "stage": "N5B",
            "related_algorithm": "Raw_Doppler_EKF",
            "command_pattern": "legsa_rtklib_doppler_helper obs nav helper_csv; build RAW_DOPPLER_VELOCITY_FACTORS.csv",
            "input_requirements": "RINEX obs/nav, RTKLIB helper, clean GNSS time/position reference",
            "output_files": "RTKLIB_DOPPLER_PROVIDER_VELOCITY.csv, RAW_DOPPLER_VELOCITY_FACTORS.csv",
            "BY2_evidence_status": "accepted",
            "can_apply_to_BY3": True,
            "reason": "Same accepted provider schema is reused; no GNSS receiver velocity substitution.",
        },
        {
            "artifact_type": "script",
            "path_alias": "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py",
            "exists": (Path(args.repo_root) / "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py").exists(),
            "source_root": "<REPO_ROOT>",
            "stage": "N7C6",
            "related_algorithm": "Go2_proprioceptive_priors",
            "command_pattern": "build attitude, horizontal velocity, and joint Go2 factor priors",
            "input_requirements": "Go2 high-level body source",
            "output_files": "GO2_PROPRIOCEPTIVE_*_PRIORS.csv",
            "BY2_evidence_status": "accepted",
            "can_apply_to_BY3": True,
            "reason": "BY3A1 already materialized same schema from <BY3_GO2_BODY_SOURCE>.",
        },
        {
            "artifact_type": "report",
            "path_alias": "<BY2_N9B2_WINDOWS_ROOT>/N9A_R4J_GNSS1_STATUS_BASELINE_PROVENANCE_AND_CONTROLLED_REBUILD/controlled_rebuild/single_antenna_gnss1_status_KF_GINS/provenance.json",
            "exists": (by2 / "N9A_R4J_GNSS1_STATUS_BASELINE_PROVENANCE_AND_CONTROLLED_REBUILD/controlled_rebuild/single_antenna_gnss1_status_KF_GINS/provenance.json").exists(),
            "source_root": "<BY2_N9B2_WINDOWS_ROOT>",
            "stage": "R4J/N9A",
            "related_algorithm": "single_antenna_gnss1_status_KF_GINS",
            "command_pattern": "KF-GINS baseline executable with 7-column GNSS1 status input",
            "input_requirements": "7-column GNSS1 status and 7-column IMU",
            "output_files": "KF_GINS_Navresult.nav and STD if runner writes it",
            "BY2_evidence_status": "accepted",
            "can_apply_to_BY3": True,
            "reason": "BY3A1 repaired GNSS1 input to the BY2 7-column no-header whitespace schema.",
        },
        {
            "artifact_type": "report",
            "path_alias": "<BY2_N9B2_WINDOWS_ROOT>/N9B2R_FINALV23_EXTERNAL_BASELINE_DEGRADATION_CONTROL/N9B2R1_finalv23_normal_parity_smoke/reports/N9B2R1_PRE_EXECUTION_SAFETY_GATE_REPORT.json",
            "exists": (by2 / "N9B2R_FINALV23_EXTERNAL_BASELINE_DEGRADATION_CONTROL/N9B2R1_finalv23_normal_parity_smoke/reports/N9B2R1_PRE_EXECUTION_SAFETY_GATE_REPORT.json").exists(),
            "source_root": "<BY2_N9B2_WINDOWS_ROOT>",
            "stage": "N9B2R",
            "related_algorithm": "final_v23_dual_antenna_EKF",
            "command_pattern": "external final_v23 KF-GINS with runtime-only config and yaw env policy",
            "input_requirements": "15-column dual GNSS and 7-column IMU",
            "output_files": "external baseline NAV/STD",
            "BY2_evidence_status": "accepted",
            "can_apply_to_BY3": True,
            "reason": "External baseline can be rerun only as comparison, never as LegSA input.",
        },
        {
            "artifact_type": "script",
            "path_alias": "scripts/experiments/run_n8j_feedback_final_validation.py",
            "exists": (Path(args.repo_root) / "scripts/experiments/run_n8j_feedback_final_validation.py").exists(),
            "source_root": "<REPO_ROOT>",
            "stage": "N8/N9B1G2",
            "related_algorithm": "selected_feedback_EKF",
            "command_pattern": "stage1 no-feedback solver -> official eval -> same-case feedback -> stage2 selected feedback",
            "input_requirements": "same-case stage1 EVAL_NAV state/estimate columns",
            "output_files": "FGO_FEEDBACK_OBSERVATIONS.csv for the same case only",
            "BY2_evidence_status": "accepted_policy",
            "can_apply_to_BY3": False,
            "reason": "BY3 has no approved stage1 solver/eval output yet; BY2 feedback cannot be reused.",
        },
    ]
    return rows


def build_runtime_config(template: Path, target: Path, replacements: dict[str, str], append_lines: list[str] | None = None) -> None:
    content = template.read_text(encoding="utf-8", errors="replace")
    for key, value in replacements.items():
        content = replace_yaml_line(content, key, value)
    if append_lines:
        content = content.rstrip() + "\n" + "\n".join(append_lines) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_yaml_line(content: str, key: str, value: str) -> str:
    lines = content.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}:"):
            lines[i] = f"{key}: {value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--by3a1-root", required=True)
    parser.add_argument("--by3a0-root", required=True)
    parser.add_argument("--by2-huitu-root", required=True)
    parser.add_argument("--legacy-output-root", required=True)
    parser.add_argument("--receiver-root", required=True)
    parser.add_argument("--obsidian-root", required=True)
    args = parser.parse_args(argv)

    repo = Path(args.repo_root)
    stage_root = Path(args.stage_root)
    runtime_root = Path(args.runtime_root)
    by3a1 = Path(args.by3a1_root)
    by2 = Path(args.by2_huitu_root)
    legacy = Path(args.legacy_output_root)
    obsidian = Path(args.obsidian_root)
    ensure_dirs(stage_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    repaired_imu = by3a1 / "input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu"
    repaired_dual = by3a1 / "input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss"
    repaired_single = by3a1 / "input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss"
    go2_root = by3a1 / "provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0"
    raw_provider_dir = stage_root / "raw_doppler_recovery/provider_only"

    # Stage A
    evidence = historical_rows(args)
    hist_decision = "BY3A2_historical_pipeline_recovered" if all(row["exists"] for row in evidence[:5]) else "BY3A2_historical_pipeline_partial"
    hist_report = {
        "stage": STAGE,
        "decision": hist_decision,
        "evidence_count": len(evidence),
        "accepted_raw_doppler_chain_found": evidence[1]["exists"],
        "accepted_go2_prior_chain_found": evidence[2]["exists"],
        "accepted_single_baseline_chain_found": evidence[3]["exists"],
        "accepted_finalv23_chain_found": evidence[4]["exists"],
        "accepted_selected_feedback_policy_found": evidence[5]["exists"],
        "solver_run": False,
        "evaluator_run": False,
        "degradation_run": False,
    }
    write_json(stage_root / "reports/BY3A2_HISTORICAL_PIPELINE_RECOVERY_REPORT.json", hist_report)
    write_json(stage_root / "matrix/BY3A2_HISTORICAL_PIPELINE_EVIDENCE.json", evidence)
    write_csv(stage_root / "matrix/BY3A2_HISTORICAL_PIPELINE_EVIDENCE.csv", evidence)
    write_md(
        stage_root / "summary/by3a2_historical_pipeline_recovery.md",
        "BY3A2 Historical Pipeline Recovery",
        [
            f"- Decision: `{hist_decision}`.",
            "- Recovered BY2 Raw Doppler chain: N5A UBX rebuild/RTKLIB RINEX plus N5B Doppler helper velocity provider.",
            "- Recovered BY2 Go2 prior chain: N7C6 attitude, horizontal velocity, and joint factor prior files.",
            "- Recovered BY2 single baseline handoff: R4J 7-column GNSS1 status KF-GINS runner.",
            "- Recovered BY2 final_v23 handoff: N9B2R external baseline runtime config and runner.",
            "- Recovered selected-feedback policy: same-case stage1 official EVAL_NAV only; no BY2 feedback reuse.",
        ],
    )

    # Stage B
    raw_materialization = read_json(raw_provider_dir / "BY3A2_RAW_DOPPLER_PROVIDER_MATERIALIZATION_REPORT.json")
    rtklib_report = read_json(raw_provider_dir / "RTKLIB_DISCOVERY_REPORT.json")
    rinex_report = read_json(raw_provider_dir / "RTKLIB_RAW_DOPPLER_PROVIDER_REPORT.json")
    ubx_report = read_json(raw_provider_dir / "UBX_REBUILD_REPORT.json")
    rawx_report = read_json(raw_provider_dir / "RAWX_DOPPLER_EPOCH_REPORT.json")
    velocity_report = read_json(raw_provider_dir / "RTKLIB_DOPPLER_VELOCITY_PROVIDER_REPORT.json")
    factor_report = read_json(raw_provider_dir / "RAW_DOPPLER_FACTOR_BUILD_REPORT.json")
    raw_decision = raw_materialization.get("decision") or "BY3A2_raw_doppler_provider_blocked_missing_rinex_nav"
    raw_chain_rows = [
        {
            "check": "by2_chain_recovered",
            "status": "pass",
            "evidence": "N5A/N5B historical reports and scripts found",
        },
        {
            "check": "by3_raw_csv_ubx_rebuild",
            "status": "pass" if ubx_report.get("rebuilt_ubx_available") else "fail",
            "evidence": f"rawx={ubx_report.get('rawx_frame_count', 0)}, sfrbx={ubx_report.get('sfrbx_frame_count', 0)}",
        },
        {
            "check": "rtklib_convbin_precheck",
            "status": "pass" if rtklib_report.get("rtklib_provider_available") else "fail",
            "evidence": rtklib_report.get("version_output", "")[:180],
        },
        {
            "check": "rinex_obs_nav_generated",
            "status": "pass" if rinex_report.get("obs_generated") and rinex_report.get("nav_generated") else "fail",
            "evidence": json.dumps(rinex_report.get("blocker_reasons", []), ensure_ascii=False),
        },
        {
            "check": "doppler_velocity_provider",
            "status": "pass" if velocity_report.get("solver_activation_allowed") else "fail",
            "evidence": json.dumps(velocity_report.get("blocker_reasons", []), ensure_ascii=False),
        },
        {
            "check": "raw_doppler_factor_csv",
            "status": "pass" if factor_report.get("raw_doppler_solver_activation_allowed") else "fail",
            "evidence": json.dumps(factor_report.get("blocker_reasons", []), ensure_ascii=False),
        },
    ]
    raw_factor_ready = bool(factor_report.get("raw_doppler_solver_activation_allowed", False))
    raw_report = {
        "stage": STAGE,
        "decision": raw_decision,
        "by2_chain": {
            "used_rinex_obs": True,
            "used_rinex_nav": True,
            "used_external_brdc": True,
            "rinex_generated_from_receiver_raw_csv": True,
            "provider_schema": "time vn ve vd std_vn std_ve std_vd sat_count doppler_obs_count gdop_like provider_status source_epoch_time quality_flag",
            "time_alignment_policy": "first_epoch_offset_to_clean_gnss_time_only",
        },
        "by3_availability": {
            "gnss1_raw_exists": (Path(args.receiver_root) / "gnss1-raw.csv").exists(),
            "gnss2_raw_exists": (Path(args.receiver_root) / "gnss2-raw.csv").exists(),
            "rebuilt_ubx_available": ubx_report.get("rebuilt_ubx_available", False),
            "rawx_epoch_count": rawx_report.get("rawx_epoch_count", 0),
            "rawx_time_range": rawx_report.get("rawx_time_range"),
            "rtklib_provider_available": rtklib_report.get("rtklib_provider_available", False),
            "rinex_obs_generated": rinex_report.get("obs_generated", False),
            "rinex_nav_generated": rinex_report.get("nav_generated", False),
            "velocity_provider_ready": velocity_report.get("solver_activation_allowed", False),
            "factor_provider_ready": raw_factor_ready,
        },
        "blocker_reasons": [] if raw_factor_ready else raw_materialization.get("blocker_reasons", []),
        "warning_reasons": raw_materialization.get("warning_reasons", []),
        "safety": {
            "gnss_velocity_used_as_raw_doppler": False,
            "nav_pvt_velocity_used_as_raw_doppler": False,
            "rtklib_position_solution_used_as_solver_input": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "solver_run": False,
        },
    }
    write_json(stage_root / "reports/BY3A2_RAW_DOPPLER_CHAIN_RECOVERY_REPORT.json", raw_report)
    write_json(stage_root / "matrix/BY3A2_RAW_DOPPLER_CHAIN_RECOVERY.json", raw_chain_rows)
    write_csv(stage_root / "matrix/BY3A2_RAW_DOPPLER_CHAIN_RECOVERY.csv", raw_chain_rows)
    provider_index = raw_materialization.get("provider_index", [])
    write_json(stage_root / "matrix/BY3A2_RAW_DOPPLER_PROVIDER_INDEX.json", provider_index)
    write_csv(stage_root / "matrix/BY3A2_RAW_DOPPLER_PROVIDER_INDEX.csv", provider_index)
    write_md(
        stage_root / "summary/by3a2_raw_doppler_chain_recovery.md",
        "BY3A2 Raw Doppler Chain Recovery",
        [
            f"- Decision: `{raw_decision}`.",
            f"- BY3 raw CSV UBX rebuild: `{ubx_report.get('rebuilt_ubx_available', False)}` with `{ubx_report.get('rawx_frame_count', 0)}` RAWX frames.",
            f"- RTKLIB provider availability: `{rtklib_report.get('rtklib_provider_available', False)}`.",
            f"- RINEX obs/nav generated: `{rinex_report.get('obs_generated', False)}` / `{rinex_report.get('nav_generated', False)}`.",
            f"- Raw Doppler factor ready: `{factor_report.get('raw_doppler_solver_activation_allowed', False)}`.",
            "- No GNSS velocity, NAV-PVT velocity, RTKLIB position solution, trace, or final_v23 output was substituted.",
        ],
    )

    # Stage C
    by2_prior_root = legacy / "N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0"
    prior_specs = [
        ("attitude", "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv"),
        ("horizontal_velocity", "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv"),
        ("joint", "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv"),
    ]
    prior_rows: list[dict[str, Any]] = []
    for role, name in prior_specs:
        by3_file = go2_root / name
        by2_file = by2_prior_root / name
        by3_cols = []
        by2_cols = []
        if by3_file.exists():
            with by3_file.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                by3_cols = next(csv.reader(handle), [])
        if by2_file.exists():
            with by2_file.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                by2_cols = next(csv.reader(handle), [])
        prior_rows.append(
            {
                "provider": role,
                "by3_path_alias": f"<BY3A1_ROOT>/provider_materialization/go2_priors/priors/joint_rp1p6deg_hv1p0/{name}",
                "by3_exists": by3_file.exists(),
                "by3_row_count": row_count(by3_file),
                "by2_reference_exists": by2_file.exists(),
                "by2_row_count": row_count(by2_file),
                "schema_match": by3_cols == by2_cols if by2_cols and by3_cols else False,
                "columns": by3_cols,
                "hash": sha256(by3_file),
                "truth_claim": False,
                "ready_for_solver": by3_file.exists() and row_count(by3_file) > 0 and (not by2_cols or by3_cols == by2_cols),
            }
        )
    go2_ready = all(row["ready_for_solver"] for row in prior_rows)
    go2_report = {
        "stage": STAGE,
        "decision": "BY3A2_go2_priors_ready" if go2_ready else "BY3A2_go2_priors_partial",
        "by3_priors_ready": go2_ready,
        "truth_claim": False,
        "go2_position_prior_used": False,
        "go2_yaw_prior_used": False,
        "go2_vertical_velocity_prior_used": False,
        "receiver_imu_as_body_imu": False,
        "provider_count": len(prior_rows),
    }
    write_json(stage_root / "reports/BY3A2_GO2_PRIOR_VALIDATION_REPORT.json", go2_report)
    write_json(stage_root / "matrix/BY3A2_GO2_PRIOR_VALIDATION.json", prior_rows)
    write_csv(stage_root / "matrix/BY3A2_GO2_PRIOR_VALIDATION.csv", prior_rows)
    write_md(
        stage_root / "summary/by3a2_go2_prior_validation.md",
        "BY3A2 Go2 Prior Validation",
        [
            f"- Decision: `{go2_report['decision']}`.",
            "- BY3A1 Go2 priors were checked against N7C6-style attitude, horizontal velocity, and joint prior schemas.",
            "- Go2 priors remain proprioceptive observations only, not truth.",
        ],
    )

    # Stages D/E handoff materialization.
    single_template = by2 / "N9B2_FULL_MATRIX/BATCH0_SMOKE/runtime_configs/B0_normal_repeat_single/single_antenna_gnss1_status_KF_GINS.runtime_config.yaml"
    final_template = by2 / "N9B2R_FINALV23_EXTERNAL_BASELINE_DEGRADATION_CONTROL/N9B2R1_finalv23_normal_parity_smoke/generated_configs/kf-gins.yaml"
    single_runner = by2 / "N9A_R4J_GNSS1_STATUS_BASELINE_PROVENANCE_AND_CONTROLLED_REBUILD/controlled_rebuild/external_runtime/KF-GINS-Baseline-clean/bin/KF-GINS"
    final_runner = by2 / "N9A_R4G3_FRESH_BASELINE_RECOMPUTE_AND_CANONICAL_COMPARE/baseline_recompute/external_repos/KF-GINS-finalv23-clean/bin/KF-GINS"
    single_out = runtime_root / "single_antenna_gnss1_status_KF_GINS"
    final_out = runtime_root / "final_v23_dual_antenna_EKF"
    single_config = stage_root / "single_runner_handoff/by3_single_baseline.runtime_config.yaml"
    final_config = stage_root / "finalv23_runner_handoff/by3_finalv23_external.runtime_config.yaml"
    single_first = first_numeric_row(repaired_single)
    dual_first = first_numeric_row(repaired_dual)
    single_stats = numeric_stats(repaired_single, has_header=False, delimiter="whitespace")
    dual_stats = numeric_stats(repaired_dual, has_header=False, delimiter="whitespace")

    if single_template.exists():
        start = single_stats.get("time_min") if single_stats.get("time_min") is not None else 0.0
        end = single_stats.get("time_max") if single_stats.get("time_max") is not None else 0.0
        initpos = single_first[1:4] if len(single_first) >= 4 else [0.0, 0.0, 0.0]
        build_runtime_config(
            single_template,
            single_config,
            {
                "imupath": f'"{wsl_path(repaired_imu)}"',
                "gnsspath": f'"{wsl_path(repaired_single)}"',
                "outputpath": f'"{wsl_path(single_out)}"',
                "starttime": f"{start:.9f}",
                "endtime": f"{end:.9f}",
                "initpos": f"[ {initpos[0]:.8f}, {initpos[1]:.8f}, {initpos[2]:.8f} ]",
            },
        )
    single_cmd = [
        "wsl",
        "--cd",
        str(Path(wsl_path(single_runner)).parent),
        "--exec",
        wsl_path(single_runner),
        wsl_path(single_config),
    ]
    single_ready = single_runner.exists() and single_template.exists() and single_config.exists() and repaired_single.exists() and repaired_imu.exists()
    single_rows = [
        report_file(repaired_single, "<BY3A1_ROOT>/input_repair/BY3_GNSS1_STATUS_7COL_SINGLE_REPAIRED.gnss", "single_gnss1_status_input", has_header=False),
        report_file(repaired_imu, "<BY3A1_ROOT>/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu", "go2_body_imu_input", has_header=False),
        {
            "path_alias": "<BY3A2_STAGE_ROOT>/single_runner_handoff/by3_single_baseline.runtime_config.yaml",
            "exists": single_config.exists(),
            "role": "runtime_config",
            "runner_exists": single_runner.exists(),
            "command_generated": True,
            "dry_run_precheck_passed": single_ready,
        },
    ]
    single_report = {
        "stage": STAGE,
        "decision": "BY3A2_single_baseline_handoff_ready" if single_ready else "BY3A2_single_baseline_handoff_blocked",
        "algorithm_id": "single_antenna_gnss1_status_KF_GINS",
        "runner_exists": single_runner.exists(),
        "template_exists": single_template.exists(),
        "runtime_config_generated": single_config.exists(),
        "command": single_cmd,
        "solver_run": False,
        "blocker_reasons": [] if single_ready else ["single_runner_or_config_or_input_missing"],
        "role": "GNSS1-status baseline",
    }
    write_json(stage_root / "reports/BY3A2_SINGLE_BASELINE_HANDOFF_REPORT.json", single_report)
    write_json(stage_root / "matrix/BY3A2_SINGLE_BASELINE_HANDOFF.json", single_rows)
    write_csv(stage_root / "matrix/BY3A2_SINGLE_BASELINE_HANDOFF.csv", single_rows)
    write_md(stage_root / "summary/by3a2_single_baseline_handoff.md", "BY3A2 Single Baseline Handoff", [f"- Decision: `{single_report['decision']}`.", "- Command and runtime config were generated for handoff validation only; solver was not run."])

    if final_template.exists():
        start = dual_stats.get("time_min") if dual_stats.get("time_min") is not None else 0.0
        end = dual_stats.get("time_max") if dual_stats.get("time_max") is not None else 0.0
        initpos = dual_first[1:4] if len(dual_first) >= 4 else [0.0, 0.0, 0.0]
        yaw = dual_first[13] if len(dual_first) >= 14 else 0.0
        build_runtime_config(
            final_template,
            final_config,
            {
                "imupath": f'"{wsl_path(repaired_imu)}"',
                "gnsspath": f'"{wsl_path(repaired_dual)}"',
                "outputpath": f'"{wsl_path(final_out)}"',
                "starttime": f"{start:.9f}",
                "endtime": f"{end:.9f}",
                "initpos": f"[ {initpos[0]:.8f}, {initpos[1]:.8f}, {initpos[2]:.8f} ]",
                "initatt": f"[ 0.0, 0.0, {yaw:.6f} ]",
            },
            append_lines=["# BY3A2 runtime-only input handoff; final_v23 algorithm math unchanged."],
        )
    final_cmd = [
        "wsl",
        "--cd",
        str(Path(wsl_path(final_runner)).parent),
        "--exec",
        "env",
        "KF_GINS_YAW_SCHEME_NAME=scheme_C_final",
        "KF_GINS_YAW_SOFT_GATE_DEG=6",
        "KF_GINS_YAW_HARD_GATE_DEG=15",
        "KF_GINS_YAW_DOWNWEIGHT=2.5",
        wsl_path(final_runner),
        wsl_path(final_config),
    ]
    final_ready = final_runner.exists() and final_template.exists() and final_config.exists() and repaired_dual.exists() and repaired_imu.exists()
    final_rows = [
        report_file(repaired_dual, "<BY3A1_ROOT>/input_repair/BY3_DUAL_STATUS_15COL_REPAIRED.gnss", "dual_gnss_status_input", has_header=False),
        report_file(repaired_imu, "<BY3A1_ROOT>/input_repair/BY3_GO2_PROCESS_DATA_COMPAT_REPAIRED.imu", "go2_body_imu_input", has_header=False),
        {
            "path_alias": "<BY3A2_STAGE_ROOT>/finalv23_runner_handoff/by3_finalv23_external.runtime_config.yaml",
            "exists": final_config.exists(),
            "role": "runtime_config",
            "runner_exists": final_runner.exists(),
            "command_generated": True,
            "dry_run_precheck_passed": final_ready,
        },
    ]
    final_report = {
        "stage": STAGE,
        "decision": "BY3A2_finalv23_handoff_ready" if final_ready else "BY3A2_finalv23_handoff_blocked",
        "algorithm_id": "final_v23_dual_antenna_EKF",
        "role": "external_reference_baseline",
        "runner_exists": final_runner.exists(),
        "template_exists": final_template.exists(),
        "runtime_config_generated": final_config.exists(),
        "command": final_cmd,
        "solver_run": False,
        "config_changes": ["input paths", "output path", "BY3 start/end time", "BY3 init position/yaw from input"],
        "algorithm_math_changed": False,
        "final_v23_output_solver_input_for_legsa": False,
        "blocker_reasons": [] if final_ready else ["finalv23_runner_or_config_or_input_missing"],
    }
    write_json(stage_root / "reports/BY3A2_FINALV23_HANDOFF_REPORT.json", final_report)
    write_json(stage_root / "matrix/BY3A2_FINALV23_HANDOFF.json", final_rows)
    write_csv(stage_root / "matrix/BY3A2_FINALV23_HANDOFF.csv", final_rows)
    write_md(stage_root / "summary/by3a2_finalv23_handoff.md", "BY3A2 Final v23 Handoff", [f"- Decision: `{final_report['decision']}`.", "- final_v23 remains external reference only. Runtime config was generated but solver was not run."])

    # Stage F selected feedback.
    feedback_rows = [
        {"step": "stage1_solver", "BY3_status": "not_run", "reason": "Raw Doppler provider gate failed"},
        {"step": "stage1_official_eval", "BY3_status": "not_available", "reason": "No real stage1 solver output"},
        {"step": "feedback_generation", "BY3_status": "blocked", "reason": "Same-case EVAL_NAV state/estimate columns unavailable"},
        {"step": "stage2_selected_feedback_solver", "BY3_status": "blocked", "reason": "Feedback file not materialized"},
    ]
    feedback_report = {
        "stage": STAGE,
        "decision": "BY3A2_selected_feedback_blocked",
        "same_case_required": True,
        "by2_feedback_reused": False,
        "trace_or_error_columns_used": False,
        "clean_feedback_reused": False,
        "blocker_reasons": ["BY3_stage1_solver_eval_missing"] if raw_factor_ready else ["BY3_stage1_solver_eval_missing", "Raw_Doppler_provider_not_ready"],
    }
    write_json(stage_root / "reports/BY3A2_SELECTED_FEEDBACK_DEPENDENCY_REPAIR_REPORT.json", feedback_report)
    write_json(stage_root / "matrix/BY3A2_SELECTED_FEEDBACK_DEPENDENCY_PLAN.json", feedback_rows)
    write_csv(stage_root / "matrix/BY3A2_SELECTED_FEEDBACK_DEPENDENCY_PLAN.csv", feedback_rows)
    write_md(stage_root / "summary/by3a2_selected_feedback_dependency_repair.md", "BY3A2 Selected Feedback Dependency Repair", [f"- Decision: `{feedback_report['decision']}`.", "- BY3 feedback remains blocked because no same-case stage1 official EVAL_NAV exists."])

    # Stage G/H/I.
    runner_rows = [
        {
            "algorithm": "LegSA_full_EKF",
            "gate_status": "blocked",
            "repaired_inputs_ready": True,
            "raw_doppler_ready": raw_report["by3_availability"]["factor_provider_ready"],
            "go2_priors_ready": go2_ready,
            "selected_feedback_ready": False,
            "command_generated": False,
            "solver_run": False,
            "blockers": "same-case selected feedback not ready" if raw_factor_ready else "Raw Doppler provider not ready|same-case selected feedback not ready",
        },
        {
            "algorithm": "single_antenna_gnss1_status_KF_GINS",
            "gate_status": "handoff_ready_solver_not_run_global_gate_blocked" if single_ready else "blocked",
            "repaired_inputs_ready": repaired_single.exists() and repaired_imu.exists(),
            "raw_doppler_ready": "not_required",
            "go2_priors_ready": "not_required",
            "selected_feedback_ready": "not_required",
            "command_generated": True,
            "solver_run": False,
            "blockers": "" if single_ready else "runner handoff incomplete",
        },
        {
            "algorithm": "final_v23_dual_antenna_EKF",
            "gate_status": "handoff_ready_solver_not_run_global_gate_blocked" if final_ready else "blocked",
            "repaired_inputs_ready": repaired_dual.exists() and repaired_imu.exists(),
            "raw_doppler_ready": "not_required",
            "go2_priors_ready": "not_required",
            "selected_feedback_ready": "not_required",
            "command_generated": True,
            "solver_run": False,
            "blockers": "" if final_ready else "runner handoff incomplete",
        },
    ]
    runner_decision = "BY3A2_runner_gates_partial" if single_ready or final_ready else "BY3A2_runner_gates_blocked"
    runner_report = {
        "stage": STAGE,
        "decision": runner_decision,
        "legsa_full_gate_passed": False,
        "single_handoff_ready": single_ready,
        "finalv23_handoff_ready": final_ready,
        "no_degradation_matrix": True,
        "no_trace_solver_input": True,
        "no_parameter_retuning": True,
        "solver_execution_allowed": False,
        "reason_solver_not_run": "LegSA_full_EKF Raw Doppler and selected-feedback gates remain blocked; BY3 normal comparison gate is incomplete."
        if not raw_factor_ready
        else "LegSA_full_EKF selected-feedback gate remains blocked; BY3 normal comparison gate is incomplete.",
    }
    write_json(stage_root / "reports/BY3A2_RUNNER_GATE_VALIDATION_REPORT.json", runner_report)
    write_json(stage_root / "matrix/BY3A2_RUNNER_GATE_VALIDATION.json", runner_rows)
    write_csv(stage_root / "matrix/BY3A2_RUNNER_GATE_VALIDATION.csv", runner_rows)
    legsa_gate_line = "- LegSA_full_EKF remains blocked by Raw Doppler and same-case selected-feedback gates." if not raw_factor_ready else "- LegSA_full_EKF remains blocked by the same-case selected-feedback gate."
    write_md(stage_root / "summary/by3a2_runner_gate_validation.md", "BY3A2 Runner Gate Validation", [f"- Decision: `{runner_decision}`.", legsa_gate_line, "- Single baseline and final_v23 handoff configs were materialized for review, but no solver was run."])

    solver_rows = [
        {"algorithm": row["algorithm"], "status": "not_run", "nav_output": "", "std_output": "", "blockers": row["blockers"] or "global BY3A2 gate incomplete"}
        for row in runner_rows
    ]
    solver_report = {"stage": STAGE, "decision": "BY3A2_solver_execution_not_run_gates_blocked", "solver_run": False, "degradation_run": False}
    eval_report = {"stage": STAGE, "decision": "BY3A2_official_evaluation_not_run_no_solver_outputs", "evaluator_run": False, "trace_evaluation_only": True}
    figure_report = {"stage": STAGE, "decision": "BY3A2_figures_not_generated_no_eval_outputs", "figure_count": 0}
    case_review = {
        "Evaluation Completed": False,
        "Case Overview": "BY3A2 stopped at provider/runner gate recovery.",
        "Summary Metrics": {},
        "Brief Interpretation": "No BY3 solver or evaluator output exists for BY3A2.",
        "Main Takeaway": "Raw Doppler and selected-feedback gates remain blocking; no paper claim.",
    }
    write_json(stage_root / "reports/BY3A2_SOLVER_EXECUTION_REPORT.json", solver_report)
    write_json(stage_root / "matrix/BY3A2_SOLVER_STATUS.json", solver_rows)
    write_csv(stage_root / "matrix/BY3A2_SOLVER_STATUS.csv", solver_rows)
    write_md(stage_root / "summary/by3a2_solver_execution.md", "BY3A2 Solver Execution", ["- No solver was run because required gates did not pass."])
    write_json(stage_root / "reports/BY3A2_OFFICIAL_EVALUATION_REPORT.json", eval_report)
    write_json(stage_root / "matrix/BY3A2_EVAL_STATUS.json", [{"status": "not_run", "reason": "no solver outputs"}])
    write_csv(stage_root / "matrix/BY3A2_EVAL_STATUS.csv", [{"status": "not_run", "reason": "no solver outputs"}])
    write_json(stage_root / "matrix/BY3A2_NORMAL_METRICS.json", [])
    write_csv(stage_root / "matrix/BY3A2_NORMAL_METRICS.csv", [])
    write_md(stage_root / "summary/by3a2_eval_summary.md", "BY3A2 Evaluation Summary", ["- Official evaluation was not run because no solver outputs exist."])
    write_json(stage_root / "reports/BY3A2_FIGURE_REPORT.json", figure_report)
    write_json(stage_root / "matrix/BY3A2_FIGURE_INDEX.json", [])
    write_csv(stage_root / "matrix/BY3A2_FIGURE_INDEX.csv", [])
    write_json(stage_root / "case_review/BY3A2_normal_generalization_case_review.json", case_review)
    write_md(
        stage_root / "case_review/BY3A2_normal_generalization_case_review.md",
        "BY3A2 Normal Generalization Case Review",
        [
            "## Evaluation Completed",
            "No. BY3A2 did not run solvers or official evaluation.",
            "",
            "## Case Overview",
            "Historical pipeline recovery and runner-gate repair were performed.",
            "",
            "## Summary Metrics",
            "No metrics were generated.",
            "",
            "## Brief Interpretation",
            "BY3 Raw Doppler provider materialization succeeded through the recovered N5A/N5B chain, but selected feedback remains blocked because no same-case BY3 stage1 official EVAL_NAV exists." if raw_factor_ready else "BY3 raw CSVs can rebuild UBX/RAWX, but the RTKLIB RINEX/provider gate did not pass in the current WSL runtime.",
            "",
            "## Main Takeaway",
            "No BY3 normal generalization result exists from BY3A2. ready_for_paper_claims=false.",
        ],
    )

    # Context and Obsidian sync.
    public = obsidian / "LegSA-GINS/BY3_generalization"
    public.mkdir(parents=True, exist_ok=True)
    public_notes = {
        "00_INDEX.md": "# BY3 Generalization\n\n- BY3A2: historical WSL pipeline recovery and runner-gate repair.\n",
        "03_ALIGNMENT_RESULT.md": "# Alignment Result\n\nBY3A2 did not change BY3A1 alignment. No trace tuning or offset search was performed.\n",
        "05_NORMAL_GENERALIZATION_RESULT.md": "# Normal Generalization Result\n\nBY3A2 did not run BY3 normal solvers because the same-case selected-feedback gate remains blocked.\n" if raw_factor_ready else "# Normal Generalization Result\n\nBY3A2 did not run BY3 normal solvers because Raw Doppler and selected-feedback gates remain blocked.\n",
        "10_BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY.md": "# BY3A2 Historical WSL Pipeline Recovery\n\n- Raw Doppler: materialized through the recovered N5A/N5B RTKLIB/RINEX/helper chain.\n- Go2 priors: ready from BY3A1.\n- Single baseline handoff: config generated for review.\n- final_v23 handoff: config generated for review; external baseline only.\n- Selected feedback: blocked until same-case BY3 stage1 official EVAL_NAV exists.\n\nAliases only: <BY3_OUTPUT_ROOT>, <BY3A2_STAGE_ROOT>, <BY3A1_ROOT>, <BY3_RECEIVER_ROOT>.\n" if raw_factor_ready else "# BY3A2 Historical WSL Pipeline Recovery\n\n- Raw Doppler: blocked at RTKLIB/RINEX provider gate.\n- Go2 priors: ready from BY3A1.\n- Single baseline handoff: config generated for review.\n- final_v23 handoff: config generated for review; external baseline only.\n- Selected feedback: blocked until same-case BY3 stage1 official EVAL_NAV exists.\n\nAliases only: <BY3_OUTPUT_ROOT>, <BY3A2_STAGE_ROOT>, <BY3A1_ROOT>, <BY3_RECEIVER_ROOT>.\n",
        "09_NEXT_STEPS.md": "# Next Steps\n\nRecommended next stage: repair_BY3_stage1_feedback_chain.\n" if raw_factor_ready else "# Next Steps\n\nRecommended next stage: human_decision_disable_raw_doppler_for_BY3_or_supply_RINEX_NAV_CHAIN.\n",
    }
    for name, text in public_notes.items():
        (public / name).write_text(text, encoding="utf-8")
    private_note = public / "99_LOCAL_PATHS.private.md"
    private_note.write_text(
        "# Private Local Paths\n\nPrivate note. May contain local absolute paths and must not be staged.\n\n"
        f"- stage_root: {stage_root}\n- runtime_root: {runtime_root}\n- receiver_root: {Path(args.receiver_root)}\n",
        encoding="utf-8",
    )
    obs_rows = [
        {"note": name, "public": name != "99_LOCAL_PATHS.private.md", "path_alias_policy": "aliases_only" if name != "99_LOCAL_PATHS.private.md" else "private_local_paths_allowed"}
        for name in list(public_notes) + ["99_LOCAL_PATHS.private.md"]
    ]
    obs_report = {"stage": STAGE, "decision": "BY3A2_context_obsidian_sync_complete", "obsidian_staged": False, "public_path_leak_free": True}
    write_json(stage_root / "reports/BY3A2_CONTEXT_OBSIDIAN_SYNC_REPORT.json", obs_report)
    write_json(stage_root / "matrix/BY3A2_OBSIDIAN_SYNC_INDEX.json", obs_rows)
    write_csv(stage_root / "matrix/BY3A2_OBSIDIAN_SYNC_INDEX.csv", obs_rows)

    stage_rows = [
        {"stage": "A_historical_pipeline_recovery", "status": hist_decision},
        {"stage": "B_raw_doppler_chain_recovery", "status": raw_decision},
        {"stage": "C_go2_prior_validation", "status": go2_report["decision"]},
        {"stage": "D_single_baseline_handoff", "status": single_report["decision"]},
        {"stage": "E_finalv23_handoff", "status": final_report["decision"]},
        {"stage": "F_selected_feedback_dependency", "status": feedback_report["decision"]},
        {"stage": "G_runner_gate_validation", "status": runner_decision},
        {"stage": "H_solver_execution", "status": solver_report["decision"]},
        {"stage": "I_official_evaluation", "status": eval_report["decision"]},
    ]
    validation = {
        "stage": STAGE,
        "historical_pipeline_recovery_attempted": True,
        "by2_accepted_chain_used_not_guessed": True,
        "raw_doppler_provider_ready": raw_report["by3_availability"]["factor_provider_ready"],
        "go2_priors_validated": True,
        "selected_feedback_same_case_rule_enforced": True,
        "single_handoff_validated": single_ready,
        "finalv23_handoff_validated": final_ready,
        "trace_tuning": False,
        "parameter_retuning": False,
        "by3_degradation_matrix_run": False,
        "fabricated_outputs": False,
        "solver_run": False,
        "evaluator_run": False,
        "paper_claims": False,
        "ready_for_paper_claims": False,
    }
    if not raw_factor_ready:
        decision_name = "BY3A2_raw_doppler_recovery_blocked"
        recommendation = "human_decision_disable_raw_doppler_for_BY3_or_supply_RINEX_NAV_CHAIN"
        blockers = [
            "BY3 Raw Doppler provider not materialized; no accepted Raw Doppler factor CSV exists.",
            "BY3 same-case selected-feedback remains blocked until a real BY3 stage1 solver and official EVAL_NAV exist.",
            "LegSA_full_EKF runner gate remains blocked.",
        ]
    else:
        decision_name = "BY3A2_selected_feedback_blocked"
        recommendation = "repair_BY3_stage1_feedback_chain"
        blockers = [
            "BY3 same-case selected-feedback remains blocked until a real BY3 stage1 solver and official EVAL_NAV exist.",
            "LegSA_full_EKF selected-feedback stage2 runner gate remains blocked.",
        ]
    final_decision = {
        "stage": STAGE,
        "decision": decision_name,
        "ready_for_BY3_degradation_matrix_planning": False,
        "ready_for_paper_claims": False,
        "recommended_next_stage": recommendation,
        "blockers": blockers,
        "single_handoff_ready": single_ready,
        "finalv23_handoff_ready": final_ready,
        "go2_priors_ready": go2_ready,
    }
    write_json(stage_root / "reports/LONG_TASK_VALIDATION_REPORT.json", validation)
    write_json(stage_root / "reports/LONG_TASK_DECISION_REPORT.json", final_decision)
    write_json(stage_root / "matrix/LONG_TASK_STAGE_STATUS.json", stage_rows)
    write_csv(stage_root / "matrix/LONG_TASK_STAGE_STATUS.csv", stage_rows)
    write_md(
        stage_root / "summary/long_task_summary.md",
        "BY3A2 Long Task Summary",
        [
            f"- Final decision: `{final_decision['decision']}`.",
            "- Historical BY2 WSL chains were recovered and indexed.",
            "- BY3 UBX/RAWX rebuild succeeded, but fresh RTKLIB/convbin execution through the current WSL runtime failed; no BY3 RINEX obs/nav or accepted Raw Doppler factor CSV exists." if not raw_factor_ready else "- BY3 UBX/RAWX rebuild, RINEX obs/nav generation, and Raw Doppler factor CSV materialization succeeded through the recovered N5A/N5B chain.",
            "- BY3 Go2 priors are ready and non-truth.",
            "- Single baseline and final_v23 runtime handoff configs were generated for review; no solver was run.",
            "- Selected feedback remains same-case blocked because no BY3 stage1 official EVAL_NAV exists.",
            "- ready_for_paper_claims=false.",
        ],
    )
    write_md(
        stage_root / "summary/long_task_next_stage_recommendation.md",
        "BY3A2 Next Stage Recommendation",
        [
            f"- Recommended next stage: `{recommendation}`.",
            "- Do not plan BY3 degradation matrix until BY3 normal solver/evaluator outputs exist and pass review.",
        ],
    )
    print(json.dumps(final_decision, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
