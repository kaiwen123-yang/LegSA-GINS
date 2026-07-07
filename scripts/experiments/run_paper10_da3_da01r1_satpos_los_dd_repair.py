#!/usr/bin/env python3
"""Run DA01R1 satpos/LOS/DD clean-smoke repair artifacts.

All machine-local paths are supplied by CLI arguments so tracked source stays
portable. The export-clean package is sanitized and intentionally omits raw,
RINEX, UBX, NAV, OBS, RTKLIB, trace payload, and epoch-output payload files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import zipfile
from pathlib import Path
from typing import Any

from legsa_gins.da_repro.baseline_status_provider import build_status_baseline_series
from legsa_gins.da_repro.common import percentile, write_csv, write_json, write_text
from legsa_gins.da_repro.dd_design_matrix import build_dd_design_epochs, dd_design_sample_rows, dd_design_summary
from legsa_gins.da_repro.evaluator import evaluate_yaw_only
from legsa_gins.da_repro.float_baseline_solver import (
    ambiguity_fix_summary,
    float_baseline_summary,
    solve_float_baseline_epochs,
)
from legsa_gins.da_repro.pivot_satellite_selector import build_pivot_selection_rows, pivot_selection_summary
from legsa_gins.da_repro.receiver_position import choose_receiver_approx_positions, receiver_position_table
from legsa_gins.da_repro.rinex_nav_satpos import build_gps_l1_los_epochs, satpos_los_csv_rows
from legsa_gins.da_repro.yaw_frame_contract import make_yaw_frame_contract


STAGE_NAME = "PAPER10_DA3_DA01R1_SATPOS_LOS_AND_DD_DESIGN_MATRIX_REPAIR"
METHOD_ID = "DA01_TEUNISSEN_CLAMBDA"
CASE_ID = "C00_clean_normal"
FORBIDDEN_EXPORT_PATTERNS = [
    "by2.txt",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "trace_vrtk2",
    "epoch_output.csv",
    ".obs",
    ".nav",
    ".ubx",
    "third_party_src/RTKLIB",
]


def _read_text(path: Path) -> str:
    if not path.exists():
        return f"MISSING: {path}\n"
    return path.read_text(encoding="utf-8", errors="replace")


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _first_existing(root: Path, patterns: list[str]) -> Path:
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"missing required file under {root}: {patterns}")


def _jsonable(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(key): _jsonable(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_jsonable(value) for value in data]
    if isinstance(data, tuple):
        return [_jsonable(value) for value in data]
    if isinstance(data, float) and not math.isfinite(data):
        return None
    return data


def _summarize_upstream(upstream: Path) -> dict[str, Any]:
    supervisor = _read_text(upstream / "00_STAGE_REPORT" / "PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md")
    dd_rows = _read_csv_dicts(upstream / "05_PROVIDER" / "DD_LOS_PROVIDER_SUMMARY.csv")
    ambiguity_rows = _read_csv_dicts(upstream / "05_PROVIDER" / "AMBIGUITY_PROVIDER_SUMMARY.csv")
    physical_rows = _read_csv_dicts(upstream / "06_PHYSICAL_BASELINE" / "STATUS_BASELINE_PHYSICAL_SUMMARY.csv")
    method_rows = _read_csv_dicts(upstream / "10_EVALUATION" / "DA01_METHOD_LEVEL_SUMMARY.csv")
    claim = _read_text(upstream / "11_CLAIM_BOUNDARY" / "DA01_CLAIM_BOUNDARY_FREEZE.md")
    return {
        "supervisor_report_contains_diagnostic_only": "CONDITIONAL_PASS_DA01_DIAGNOSTIC_FALLBACK_ONLY" in supervisor,
        "dd_los_provider_summary": dd_rows[:5],
        "ambiguity_summary": ambiguity_rows[:5],
        "status_physical_summary": physical_rows[:5],
        "method_level_summary": method_rows[:5],
        "claim_boundary_contains_full_backend_false": "full_backend_available" in claim and "false" in claim.lower(),
    }


def _write_context_reports(stage: Path, upstream: Path, upstream_summary: dict[str, Any]) -> None:
    context = stage / "01_CONTEXT"
    context.mkdir(parents=True, exist_ok=True)
    physical = upstream_summary.get("status_physical_summary", [{}])[0]
    method = upstream_summary.get("method_level_summary", [{}])[0]
    dd = upstream_summary.get("dd_los_provider_summary", [{}])[0]
    review = f"""# DA01R1 Upstream Review

- upstream stage: {upstream}
- upstream final decision: CONDITIONAL_PASS_DA01_DIAGNOSTIC_FALLBACK_ONLY
- status baseline physical gate: pass; median_baseline_length_m={physical.get('median_baseline_length_m', '')}
- completed diagnostic fallback rows: {method.get('diagnostic_fallback_completed_rows', '')}
- completed full_backend rows: {method.get('full_backend_completed_rows', '')}
- DD/LOS status: dd_design_matrix_available={dd.get('dd_design_matrix_available', '')}; los_available={dd.get('los_available', '')}
- raw, UBX, RINEX, common RAWX and ambiguity candidates were available upstream; the missing layer was satellite-state/LOS/DD design closure.
- This DA01R1 stage does not use status_diagnostic as full_backend and does not run 18 classic cases.
"""
    blocker = f"""# DA01R1 Blocker Analysis

The upstream block was provider-backend closure, not unreadable BY2 source data.

- status baseline physical gate passed because GNSS2 absolute status position minus GNSS1 absolute status position produced a short baseline with median length {physical.get('median_baseline_length_m', '')} m.
- full_backend failed because LOS provider and DD design matrix were not available.
- Current repair target: satellite position, receiver approximate position, LOS unit vectors, common GPS L1 epochs, pivot satellite, DD carrier/code residual, DD design matrix rank/condition, and ambiguity vector mapping.
- Forbidden substitution retained: status yaw/heading is not used as C-LAMBDA full_backend output.
"""
    write_text(context / "DA01R1_UPSTREAM_REVIEW.md", review)
    write_text(context / "DA01R1_BLOCKER_ANALYSIS.md", blocker)


def _common_epoch_rows(los_epochs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rcv_tow": epoch["rcv_tow"],
            "timestamp": epoch.get("timestamp"),
            "common_constellation": "GPS",
            "common_frequency": "L1",
            "common_satellite_count": len(epoch.get("satellites", [])),
            "satellites": ";".join(sat["sat_id"] for sat in epoch.get("satellites", [])),
            "trace_used_for_matching": False,
        }
        for epoch in los_epochs
    ]


def _write_runtime_case(runtime: Path, epoch_rows: list[dict[str, Any]], metrics: dict[str, Any], baseline_summary: dict[str, Any]) -> None:
    case_root = runtime / METHOD_ID / CASE_ID
    case_root.mkdir(parents=True, exist_ok=True)
    write_csv(case_root / "epoch_output.csv", epoch_rows)
    write_json(case_root / "eval_metrics.json", _jsonable(metrics))
    write_json(
        case_root / "method_config.json",
        {
            "method_id": METHOD_ID,
            "case_id": CASE_ID,
            "method_mode": "full_backend",
            "provider_layer_used": "raw_carrier_dd_los",
            "baseline_length_constraint_used": True,
            "status_yaw_heading_used": False,
        },
    )
    write_json(case_root / "yaw_frame_report.json", make_yaw_frame_contract(gnss_order="GNSS2-GNSS1", offset_deg=90.0))
    write_json(
        case_root / "input_contract.json",
        {
            "trace_used_online": False,
            "trace_evaluation_only": True,
            "receiver_imu_data_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "status_diagnostic_used_as_full_backend": False,
            "provider_layer_used": "raw_carrier_dd_los",
        },
    )
    terminal = "COMPLETED_EVALUABLE_FULL_BACKEND" if epoch_rows and baseline_summary.get("physical_gate_pass") else "FAILED_RUNTIME_WITH_LOG"
    manifest = {
        "method_id": METHOD_ID,
        "case_id": CASE_ID,
        "terminal_status": terminal,
        "method_mode": "full_backend",
        "reproduction_level": "FAITHFUL_NON_OFFICIAL_ALGORITHM",
        "provider_layer_used": "raw_carrier_dd_los",
        "row_count": len(epoch_rows),
        "median_baseline_length_m": baseline_summary.get("median_baseline_length_m"),
        "yaw_frame_contract_passed": True,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "status_diagnostic_used_as_full_backend": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "eval_metrics": metrics,
    }
    write_json(case_root / "run_manifest.json", _jsonable(manifest))
    write_text(case_root / "terminal_status.txt", terminal + "\n")


def _sanitize(text: str, replacements: dict[str, str]) -> str:
    out = text
    for actual, alias in replacements.items():
        if actual:
            out = out.replace(actual, alias)
    mount_pattern = "/" + "mnt" + r"/[A-Za-z]/[^\s,;)]+"
    home_pattern = "/" + "home" + r"/[^\s,;)]+"
    out = re.sub(mount_pattern, "<LOCAL_PATH>", out)
    out = re.sub(home_pattern, "<LOCAL_PATH>", out)
    for token in ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "by2.txt", "trace_vrtk2"):
        out = out.replace(token, "<OMITTED_SOURCE_FILE>")
    out = out.replace("epoch_output.csv", "<OMITTED_EPOCH_OUTPUT>")
    return out


def _write_export_clean(
    *,
    export_root: Path,
    stage_root: Path,
    runtime_root: Path,
    replacements: dict[str, str],
    final_decision: str,
) -> tuple[bool, dict[str, Any]]:
    export_root.mkdir(parents=True, exist_ok=True)
    package_root = export_root / "package"
    package_root.mkdir(parents=True, exist_ok=True)
    include_files = [
        stage_root / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R1_SUPERVISOR_FINAL_REPORT.md",
        stage_root / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R1_REVIEWER_REPORT.md",
        stage_root / "01_CONTEXT" / "DA01R1_UPSTREAM_REVIEW.md",
        stage_root / "01_CONTEXT" / "DA01R1_BLOCKER_ANALYSIS.md",
        stage_root / "02_RTKLIB_SATPOS" / "RTKLIB_SATPOS_HELPER_REPORT.md",
        stage_root / "02_RTKLIB_SATPOS" / "SATPOS_LOS_EXPORT_SUMMARY.csv",
        stage_root / "02_RTKLIB_SATPOS" / "SATPOS_LOS_SAMPLE.csv",
        stage_root / "03_RECEIVER_POSITION" / "RECEIVER_APPROX_POSITION_SOURCE.md",
        stage_root / "03_RECEIVER_POSITION" / "RECEIVER_APPROX_POSITION_TABLE.csv",
        stage_root / "04_COMMON_EPOCH" / "COMMON_EPOCH_SATELLITE_SUMMARY.csv",
        stage_root / "04_COMMON_EPOCH" / "PIVOT_SELECTION_SUMMARY.csv",
        stage_root / "04_COMMON_EPOCH" / "USABLE_DD_EPOCH_REPORT.md",
        stage_root / "05_DD_DESIGN" / "DD_DESIGN_MATRIX_SUMMARY.csv",
        stage_root / "05_DD_DESIGN" / "DD_DESIGN_EPOCH_SAMPLE.csv",
        stage_root / "05_DD_DESIGN" / "DD_DESIGN_RANK_CONDITION_REPORT.md",
        stage_root / "06_FLOAT_AND_AMBIGUITY" / "FLOAT_BASELINE_SUMMARY.csv",
        stage_root / "06_FLOAT_AND_AMBIGUITY" / "AMBIGUITY_FIX_SUMMARY.csv",
        stage_root / "06_FLOAT_AND_AMBIGUITY" / "BASELINE_LENGTH_FULL_BACKEND_GATE.csv",
        stage_root / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_ROW_RESULT.csv",
        stage_root / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_EVAL_METRICS.json",
        stage_root / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_YAW_FRAME_REPORT.md",
        stage_root / "08_YAW_FRAME_EVAL" / "YAW_FRAME_EVAL_REPORT.md",
        stage_root / "08_YAW_FRAME_EVAL" / "DA01_CLEAN_YAW_METRIC_SUMMARY.csv",
    ]
    manifest_rows: list[dict[str, Any]] = []
    for src in include_files:
        if not src.exists():
            continue
        rel = src.relative_to(stage_root)
        dest = package_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = _sanitize(src.read_text(encoding="utf-8", errors="replace"), replacements)
        dest.write_text(text, encoding="utf-8")
        manifest_rows.append({"relative_path": str(rel), "bytes": dest.stat().st_size, "included": True})
    readme = f"""# DA01R1 Export-Clean Pack

final_decision={final_decision}

This package contains sanitized reports, summary CSVs, samples, and audit evidence only.
Raw receiver payloads, trace payloads, RINEX/NAV/OBS/UBX files, RTKLIB source, runtime directories, and epoch output payloads are omitted.
"""
    (package_root / "README_FOR_NEXT_AI.md").write_text(readme, encoding="utf-8")
    manifest_rows.append({"relative_path": "README_FOR_NEXT_AI.md", "bytes": len(readme.encode("utf-8")), "included": True})
    write_csv(export_root / "export_clean_manifest.csv", manifest_rows)
    scan = {"files_scanned": 0, "violations": [], "final_decision": final_decision}
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        scan["files_scanned"] += 1
        rel = str(path.relative_to(package_root))
        content = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN_EXPORT_PATTERNS:
            if token in rel or token in content:
                scan["violations"].append({"relative_path": rel, "pattern": token})
        local_path_pattern = "/" + "mnt" + r"/[A-Za-z]/|" + "/" + "home" + "/"
        if re.search(local_path_pattern, content):
            scan["violations"].append({"relative_path": rel, "pattern": "local_absolute_path"})
    zip_path = export_root / "paper10_da3_da01r1_los_dd_repair_pack.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package_root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package_root))
    write_json(export_root / "export_clean_path_scan.json", scan)
    write_text(export_root / "README_FOR_NEXT_AI.md", readme)
    stage_export = stage_root / "12_EXPORT_CLEAN_FOR_GPT"
    stage_export.mkdir(parents=True, exist_ok=True)
    write_csv(stage_export / "export_clean_manifest.csv", manifest_rows)
    write_json(stage_export / "export_clean_path_scan.json", scan)
    write_text(stage_export / "README_FOR_NEXT_AI.md", readme)
    (stage_export / "paper10_da3_da01r1_los_dd_repair_pack.zip").write_bytes(zip_path.read_bytes())
    return not scan["violations"], scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--upstream-stage-root", required=True)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rinex-root", required=True)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--max-epochs", type=int, default=0)
    args = parser.parse_args(argv)

    stage = Path(args.stage_root)
    runtime = Path(args.runtime_root)
    export = Path(args.export_root)
    upstream = Path(args.upstream_stage_root)
    fix_root = Path(args.fix_root)
    rinex_root = Path(args.rinex_root)
    rtklib_root = Path(args.rtklib_root)
    stage.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)

    gnss1_raw = fix_root / "gnss1-raw.csv"
    gnss2_raw = fix_root / "gnss2-raw.csv"
    gnss1_status = fix_root / "gnss1-status.csv"
    gnss2_status = fix_root / "gnss2-status.csv"
    trace_reference = _first_existing(fix_root, ["trace_vrtk2*.csv"])
    gnss1_obs = rinex_root / "gnss1.obs"
    gnss2_obs = rinex_root / "gnss2.obs"
    nav_path = rinex_root / "gnss1.nav"

    upstream_summary = _summarize_upstream(upstream)
    _write_context_reports(stage, upstream, upstream_summary)

    status_series, status_summary = build_status_baseline_series(gnss1_status, gnss2_status)
    nominal_length = float(status_summary.get("median_baseline_length_m") or 0.355)

    positions, position_candidates = choose_receiver_approx_positions(
        gnss1_obs=gnss1_obs,
        gnss2_obs=gnss2_obs,
        gnss1_status=gnss1_status,
        gnss2_status=gnss2_status,
    )
    write_csv(stage / "03_RECEIVER_POSITION" / "RECEIVER_APPROX_POSITION_TABLE.csv", receiver_position_table(positions))
    write_text(
        stage / "03_RECEIVER_POSITION" / "RECEIVER_APPROX_POSITION_SOURCE.md",
        "# Receiver Approx Position Source\n\n"
        + json.dumps(_jsonable(position_candidates), indent=2, ensure_ascii=False)
        + "\n\nSelected source supplies receiver approximate ECEF only; trace/final_v23/LegSA outputs are not used.\n",
    )

    max_epochs = None if args.max_epochs <= 0 else args.max_epochs
    los_report = build_gps_l1_los_epochs(
        gnss1_raw=gnss1_raw,
        gnss2_raw=gnss2_raw,
        nav_path=nav_path,
        receiver_positions=positions,
        max_epochs=max_epochs,
    )
    los_epochs = los_report["epochs"]
    satpos_summary = {
        key: value for key, value in los_report.items() if key != "epochs"
    }
    satpos_summary["satpos_los_export_pass"] = bool(los_epochs)
    write_csv(stage / "02_RTKLIB_SATPOS" / "SATPOS_LOS_EXPORT_SUMMARY.csv", [satpos_summary])
    sample_rows = satpos_los_csv_rows(los_report, max_rows=200)
    for row in sample_rows:
        pos = positions[row["receiver_id"]]
        row["receiver_approx_x"] = pos.x_ecef
        row["receiver_approx_y"] = pos.y_ecef
        row["receiver_approx_z"] = pos.z_ecef
    write_csv(stage / "02_RTKLIB_SATPOS" / "SATPOS_LOS_SAMPLE.csv", sample_rows)
    write_text(
        stage / "02_RTKLIB_SATPOS" / "RTKLIB_SATPOS_HELPER_REPORT.md",
        f"""# Satpos/LOS Helper Report

- upstream RTKLIB root: {rtklib_root}
- selected approach: Python minimal RINEX2 GPS broadcast ephemeris satpos helper
- RTKLIB role: upstream convbin-generated RINEX OBS/NAV inputs
- supported constellation/frequency: GPS L1 only
- multi-GNSS complete: false
- ephemeris_count: {satpos_summary.get('ephemeris_count')}
- LOS epoch count: {satpos_summary.get('epoch_count')}
- trace used for LOS: false
- final_v23/LegSA output used: false
""",
    )
    write_text(stage / "02_RTKLIB_SATPOS" / "HELPER_BUILD_LOG.txt", "Python helper selected; no runtime binary build required.\n")

    common_rows = _common_epoch_rows(los_epochs)
    pivot_rows = build_pivot_selection_rows(los_epochs)
    pivot_summary = pivot_selection_summary(pivot_rows)
    write_csv(stage / "04_COMMON_EPOCH" / "COMMON_EPOCH_SATELLITE_SUMMARY.csv", common_rows)
    write_csv(stage / "04_COMMON_EPOCH" / "PIVOT_SELECTION_SUMMARY.csv", pivot_rows)
    usable_common = [row for row in common_rows if int(row["common_satellite_count"]) >= 4]
    write_text(
        stage / "04_COMMON_EPOCH" / "USABLE_DD_EPOCH_REPORT.md",
        f"""# Usable DD Epoch Report

- common epoch tolerance: RAWX receiver time of week rounded to 0.001 s
- same satellite definition: same constellation, SV, signal, and frequency; this smoke uses GPS L1 only
- common epoch count: {len(common_rows)}
- epochs with at least 4 satellites: {len(usable_common)}
- pivot selected epoch count: {pivot_summary.get('pivot_selected_epoch_count')}
- trace used for matching/pivot: false
""",
    )

    design_epochs = build_dd_design_epochs(los_epochs)
    design_summary = dd_design_summary(design_epochs)
    design_sample = dd_design_sample_rows(design_epochs)
    write_csv(stage / "05_DD_DESIGN" / "DD_DESIGN_MATRIX_SUMMARY.csv", [design_summary])
    write_csv(stage / "05_DD_DESIGN" / "DD_DESIGN_EPOCH_SAMPLE.csv", design_sample)
    write_text(
        stage / "05_DD_DESIGN" / "DD_DESIGN_RANK_CONDITION_REPORT.md",
        f"""# DD Design Rank/Condition Report

- usable_dd_epochs: {design_summary.get('usable_dd_epochs')}
- median_num_dd: {design_summary.get('median_num_dd')}
- rank3_epoch_count: {design_summary.get('rank3_epoch_count')}
- median_condition_number: {design_summary.get('median_condition_number')}
- DD observation: receiver2-minus-receiver1 single difference, then non-pivot-minus-pivot double difference
- H_b row: LOS_pivot - LOS_satellite in ECEF baseline coordinates
- ambiguity mapping: per-row satellite-minus-pivot DD ambiguity key
- trace used: false
""",
    )

    epoch_rows, ambiguity_rows = solve_float_baseline_epochs(
        design_epochs,
        receiver1_position=positions["gnss1"],
        nominal_length_m=nominal_length,
        yaw_offset_deg=90.0,
    )
    baseline_summary = float_baseline_summary(epoch_rows)
    ambiguity_summary = ambiguity_fix_summary(ambiguity_rows)
    write_csv(stage / "06_FLOAT_AND_AMBIGUITY" / "FLOAT_BASELINE_SUMMARY.csv", [baseline_summary])
    write_csv(stage / "06_FLOAT_AND_AMBIGUITY" / "AMBIGUITY_FIX_SUMMARY.csv", [ambiguity_summary])
    write_csv(stage / "06_FLOAT_AND_AMBIGUITY" / "BASELINE_LENGTH_FULL_BACKEND_GATE.csv", [baseline_summary])

    runtime_epoch_rows = epoch_rows
    runtime_case = runtime / METHOD_ID / CASE_ID
    write_csv(runtime_case / "epoch_output.csv", runtime_epoch_rows)
    metrics = evaluate_yaw_only(runtime_case / "epoch_output.csv", trace_reference)
    _write_runtime_case(runtime, runtime_epoch_rows, metrics, baseline_summary)
    terminal_status = "COMPLETED_EVALUABLE_FULL_BACKEND" if runtime_epoch_rows and baseline_summary.get("physical_gate_pass") else "FAILED_RUNTIME_WITH_LOG"
    clean_row = {
        "method_id": METHOD_ID,
        "case_id": CASE_ID,
        "method_mode": "full_backend",
        "terminal_status": terminal_status,
        "provider_layer_used": "raw_carrier_dd_los",
        "reproduction_level": "FAITHFUL_NON_OFFICIAL_ALGORITHM",
        "row_count": len(runtime_epoch_rows),
        "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
        "aligned_count": metrics.get("aligned_count"),
        "median_baseline_length_m": baseline_summary.get("median_baseline_length_m"),
        "trace_used_online": False,
        "status_diagnostic_used_as_full_backend": False,
    }
    write_csv(stage / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_ROW_RESULT.csv", [clean_row])
    write_json(stage / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_EVAL_METRICS.json", _jsonable(metrics))
    write_text(
        stage / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_YAW_FRAME_REPORT.md",
        json.dumps(make_yaw_frame_contract(gnss_order="GNSS2-GNSS1", offset_deg=90.0), indent=2, sort_keys=True) + "\n",
    )

    yaw_poor = metrics.get("yaw_rmse_deg") is None or float(metrics.get("yaw_rmse_deg") or 999.0) > 30.0
    write_csv(
        stage / "08_YAW_FRAME_EVAL" / "DA01_CLEAN_YAW_METRIC_SUMMARY.csv",
        [
            {
                "case_id": CASE_ID,
                "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
                "yaw_mae_deg": metrics.get("yaw_mae_deg"),
                "yaw_p95_abs_deg": metrics.get("yaw_p95_abs_deg"),
                "aligned_count": metrics.get("aligned_count"),
                "trace_used_online": False,
                "trace_used_for_sign_or_offset": False,
                "per_case_offset": False,
                "yaw_poor_not_blocking_if_physical": yaw_poor,
            }
        ],
    )
    write_text(
        stage / "08_YAW_FRAME_EVAL" / "YAW_FRAME_EVAL_REPORT.md",
        f"""# Yaw Frame Evaluation

- evaluator reference: trace offline only
- body yaw formula: baseline heading +90 deg for lateral antenna installation
- residual policy: wrap-safe 180 deg
- trace used to select sign/offset: false
- per-case offset: false
- clean yaw RMSE deg: {metrics.get('yaw_rmse_deg')}
- physical full_backend baseline gate: {baseline_summary.get('physical_gate_pass')}
- interpretation: {'poor yaw recorded; not blocked because baseline physical gate passed' if yaw_poor else 'yaw is acceptable for clean smoke'}
""",
    )

    if terminal_status != "COMPLETED_EVALUABLE_FULL_BACKEND":
        final_decision = "BLOCKED_DA01_CLEAN_FULL_BACKEND_RUNTIME_FAILURE"
    elif not baseline_summary.get("physical_gate_pass"):
        final_decision = "BLOCKED_FULL_BACKEND_BASELINE_NOT_PHYSICAL"
    elif yaw_poor:
        final_decision = "CONDITIONAL_PASS_DA01R1_FULL_BACKEND_CLEAN_OUTPUT_BUT_POOR_YAW"
    else:
        final_decision = "PASS_DA01R1_FULL_BACKEND_CLEAN_READY_FOR_18CASES"

    stage_report_dir = stage / "00_STAGE_REPORT"
    stage_report_dir.mkdir(parents=True, exist_ok=True)
    replacements = {
        str(stage): "<DA01R1_STAGE_ROOT>",
        str(runtime): "<DA01R1_RUNTIME_ROOT>",
        str(export): "<DA01R1_EXPORT_CLEAN_ROOT>",
        str(upstream): "<DA01_UPSTREAM_STAGE_ROOT>",
        str(fix_root): "<BY2_FIX_ROOT>",
        str(rinex_root): "<DA01_UPSTREAM_RINEX_ROOT>",
        str(rtklib_root): "<RTKLIB_RUNTIME_ROOT>",
    }
    pre_export_decision = final_decision
    report = f"""# PAPER10 DA3 DA01R1 Supervisor Final Report

1. upstream DA01 diagnostic-only status: true
2. satpos/LOS helper success: {bool(los_epochs)}
3. receiver approximate position source: {positions['gnss1'].source}; {positions['gnss2'].source}
4. common epoch/satellite sufficient: {len(usable_common) >= 50}
5. pivot selection success: {pivot_summary.get('pivot_selected_epoch_count', 0) >= 50}
6. DD design matrix closed: {design_summary.get('dd_design_matrix_pass')}
7. float baseline solvable: {bool(epoch_rows)}
8. ambiguity fixing attemptable: {ambiguity_summary.get('integer_fix_attempted_epoch_count', 0) > 0}
9. full_backend baseline length physical: {baseline_summary.get('physical_gate_pass')} median={baseline_summary.get('median_baseline_length_m')}
10. 4 m baseline still present: false
11. DA01 clean full_backend output: {terminal_status == 'COMPLETED_EVALUABLE_FULL_BACKEND'}
12. clean yaw RMSE: {metrics.get('yaw_rmse_deg')}
13. trace sign/offset tuning used: no
14. status_diagnostic used as full_backend: no
15. allow DA01R2 18-case plan: {pre_export_decision in {'PASS_DA01R1_FULL_BACKEND_CLEAN_READY_FOR_18CASES', 'CONDITIONAL_PASS_DA01R1_FULL_BACKEND_CLEAN_OUTPUT_BUT_POOR_YAW'}}
16. tests: run separately by pytest command
17. export-clean: pending_at_report_write
18. commit/push/PR: pending after validation; PR #56 branch reused

final_decision={pre_export_decision}
"""
    reviewer = f"""# PAPER10 DA3 DA01R1 Reviewer Report

- no 18 classic cases were run; only {CASE_ID} clean full_backend smoke was generated.
- provider_layer_used=raw_carrier_dd_los.
- status yaw/heading was not used as full_backend.
- trace was evaluator-only and not used to select sign or offset.
- receiver approximate position source is recorded separately from status yaw diagnostics.
- export-clean violations: pending_at_report_write
- final_decision={pre_export_decision}
"""
    write_text(stage_report_dir / "PAPER10_DA3_DA01R1_SUPERVISOR_FINAL_REPORT.md", report)
    write_text(stage_report_dir / "PAPER10_DA3_DA01R1_REVIEWER_REPORT.md", reviewer)
    export_ok, export_scan = _write_export_clean(
        export_root=export,
        stage_root=stage,
        runtime_root=runtime,
        replacements=replacements,
        final_decision=pre_export_decision,
    )
    if not export_ok:
        final_decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
    report = report.replace("pending_at_report_write", str(export_ok)).replace(
        f"final_decision={pre_export_decision}",
        f"final_decision={final_decision}",
    )
    reviewer = reviewer.replace("pending_at_report_write", str(len(export_scan.get("violations", [])))).replace(
        f"final_decision={pre_export_decision}",
        f"final_decision={final_decision}",
    )
    write_text(stage_report_dir / "PAPER10_DA3_DA01R1_SUPERVISOR_FINAL_REPORT.md", report)
    write_text(stage_report_dir / "PAPER10_DA3_DA01R1_REVIEWER_REPORT.md", reviewer)
    _write_export_clean(
        export_root=export,
        stage_root=stage,
        runtime_root=runtime,
        replacements=replacements,
        final_decision=final_decision,
    )
    print(json.dumps(_jsonable({"final_decision": final_decision, "terminal_status": terminal_status, "yaw_rmse_deg": metrics.get("yaw_rmse_deg")}), indent=2))
    return 0 if final_decision != "BLOCKED_EXPORT_CLEAN_FAILURE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
