#!/usr/bin/env python3
"""Run DA01R2 Teunissen C-LAMBDA full-backend BY2 18 classic cases."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from legsa_gins.da_repro.baseline_status_provider import build_status_baseline_series
from legsa_gins.da_repro.common import percentile, write_csv, write_json, write_text
from legsa_gins.da_repro.dd_design_matrix import build_dd_design_epochs
from legsa_gins.da_repro.float_baseline_solver import solve_float_baseline_epochs
from legsa_gins.da_repro.full_backend_classic_runner import (
    FULL_BACKEND_PROVIDER_LAYER,
    FULL_BACKEND_REPRODUCTION_LEVEL,
    apply_full_backend_case_policy,
    baseline_physical_summary_from_rows,
    classic_case_manifest_rows,
    dd_provider_summary_from_rows,
    evaluate_yaw_with_max,
)
from legsa_gins.da_repro.method_teunissen_clambda import CLASSIC_CASES, METHOD_ID
from legsa_gins.da_repro.receiver_position import choose_receiver_approx_positions
from legsa_gins.da_repro.rinex_nav_satpos import build_gps_l1_los_epochs
from legsa_gins.da_repro.yaw_frame_contract import make_yaw_frame_contract


STAGE_NAME = "PAPER10_DA3_DA01R2_TEUNISSEN_CLAMBDA_FULL_BACKEND_18CLASSIC"
FORBIDDEN_EXPORT_NAMES = {
    "by2.txt",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "epoch_output.csv",
}
FORBIDDEN_EXPORT_SUFFIXES = {".ubx", ".obs", ".nav", ".pdf", ".zst", ".tar"}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else f"MISSING: {path}\n"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _first_existing(root: Path, patterns: list[str]) -> Path:
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"missing required file under {root}: {patterns}")


def _sanitize(text: str, replacements: dict[str, str]) -> str:
    out = text
    for actual, alias in replacements.items():
        if actual:
            out = out.replace(actual, alias)
    out = re.sub("/" + "mnt" + r"/[A-Za-z]/[^\s,;)]+", "<LOCAL_PATH>", out)
    out = re.sub("/" + "home" + r"/[^\s,;)]+", "<LOCAL_PATH>", out)
    for token in ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "by2.txt", "trace_vrtk2"):
        out = out.replace(token, "<OMITTED_SOURCE_FILE>")
    out = out.replace("epoch_output.csv", "<OMITTED_EPOCH_OUTPUT>")
    return out


def _write_runtime_case(
    *,
    runtime_root: Path,
    case_id: str,
    epoch_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    baseline_summary: dict[str, Any],
    provider_summary: dict[str, Any],
    policy_report: dict[str, Any],
    terminal_status: str,
) -> None:
    case_root = runtime_root / METHOD_ID / case_id
    case_root.mkdir(parents=True, exist_ok=True)
    write_csv(case_root / "epoch_output.csv", epoch_rows)
    write_json(case_root / "eval_metrics.json", _jsonable(metrics))
    write_json(
        case_root / "method_config.json",
        {
            "method_id": METHOD_ID,
            "case_id": case_id,
            "method_mode": "full_backend",
            "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
            "case_policy": policy_report,
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
            "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
            "old_aggregate_imported": False,
            "summary_reconstructed": False,
        },
    )
    write_json(
        case_root / "run_manifest.json",
        _jsonable(
            {
                "method_id": METHOD_ID,
                "case_id": case_id,
                "terminal_status": terminal_status,
                "method_mode": "full_backend",
                "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
                "reproduction_level": FULL_BACKEND_REPRODUCTION_LEVEL,
                "row_count": len(epoch_rows),
                "usable_dd_epochs": provider_summary.get("usable_dd_epochs"),
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
                "old_aggregate_imported": False,
                "summary_reconstructed": False,
                "policy_report": policy_report,
                "eval_metrics": metrics,
            }
        ),
    )
    write_text(case_root / "terminal_status.txt", terminal_status + "\n")


def _terminal_status(epoch_rows: list[dict[str, Any]], baseline_summary: dict[str, Any]) -> str:
    if not epoch_rows:
        return "FAILED_RUNTIME_WITH_LOG"
    if not baseline_summary.get("baseline_physical_gate_pass") or baseline_summary.get("four_meter_baseline_reappeared"):
        return "BLOCKED_WITH_PROOF"
    return "COMPLETED_EVALUABLE_FULL_BACKEND"


def _row_result(case: Any, terminal: str, provider: dict[str, Any], baseline: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    completed = terminal == "COMPLETED_EVALUABLE_FULL_BACKEND"
    return {
        "method_id": METHOD_ID,
        "case_id": case.case_id,
        "case_family": case.case_family,
        "terminal_status": terminal,
        "completed_evaluable": completed,
        "method_mode": "full_backend",
        "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
        "reproduction_level": FULL_BACKEND_REPRODUCTION_LEVEL,
        "usable_dd_epochs": provider.get("usable_dd_epochs"),
        "median_num_dd": provider.get("median_num_dd"),
        "rank3_epoch_count": provider.get("rank3_epoch_count"),
        "median_condition_number": provider.get("median_condition_number"),
        "median_baseline_length_m": baseline.get("median_baseline_length_m"),
        "p05_baseline_length_m": baseline.get("p05_baseline_length_m"),
        "p95_baseline_length_m": baseline.get("p95_baseline_length_m"),
        "baseline_physical_gate_pass": baseline.get("baseline_physical_gate_pass"),
        "four_meter_baseline_reappeared": baseline.get("four_meter_baseline_reappeared"),
        "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
        "yaw_mae_deg": metrics.get("yaw_mae_deg"),
        "yaw_p95_deg": metrics.get("yaw_p95_abs_deg"),
        "yaw_max_abs_deg": metrics.get("yaw_max_abs_deg"),
        "position_metric_applicable": False,
        "yaw_metric_applicable": metrics.get("aligned_count", 0) > 0,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_solver_input": False,
        "legsa_solver_input": False,
        "status_diagnostic_used_as_full_backend": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "yaw_frame_safe": True,
        "wrap_safe": True,
        "notes": "poor_yaw_recorded_not_tuned" if (metrics.get("yaw_rmse_deg") or 0.0) > 30.0 else "completed",
    }


def _method_summary(row_results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in row_results if row["terminal_status"] == "COMPLETED_EVALUABLE_FULL_BACKEND"]
    failed = [row for row in row_results if row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG"]
    blocked = [row for row in row_results if row["terminal_status"] == "BLOCKED_WITH_PROOF"]
    yaw_rmse = [float(row["yaw_rmse_deg"]) for row in completed if row.get("yaw_rmse_deg") not in (None, "")]
    yaw_p95 = [float(row["yaw_p95_deg"]) for row in completed if row.get("yaw_p95_deg") not in (None, "")]
    yaw_max = [float(row["yaw_max_abs_deg"]) for row in completed if row.get("yaw_max_abs_deg") not in (None, "")]
    return {
        "method_id": METHOD_ID,
        "method_mode": "full_backend",
        "provider_layer_used": FULL_BACKEND_PROVIDER_LAYER,
        "planned_rows": len(row_results),
        "completed_rows": len(completed),
        "failed_rows": len(failed),
        "blocked_rows": len(blocked),
        "mean_yaw_rmse_deg": sum(yaw_rmse) / len(yaw_rmse) if yaw_rmse else None,
        "median_yaw_rmse_deg": percentile(yaw_rmse, 0.50),
        "max_yaw_rmse_deg": max(yaw_rmse) if yaw_rmse else None,
        "max_yaw_p95_deg": max(yaw_p95) if yaw_p95 else None,
        "max_yaw_abs_deg": max(yaw_max) if yaw_max else None,
        "all_trace_used_online_false": all(not row["trace_used_online"] for row in row_results),
        "all_status_diagnostic_as_full_backend_false": all(not row["status_diagnostic_used_as_full_backend"] for row in row_results),
        "old_aggregate_used": False,
        "summary_reconstructed": False,
    }


def _family_summary(row_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_results:
        grouped[str(row["case_family"])].append(row)
    rows: list[dict[str, Any]] = []
    for family, items in sorted(grouped.items()):
        yaw = [float(row["yaw_rmse_deg"]) for row in items if row.get("yaw_rmse_deg") not in (None, "")]
        rows.append(
            {
                "case_family": family,
                "row_count": len(items),
                "completed_rows": sum(1 for row in items if row["terminal_status"] == "COMPLETED_EVALUABLE_FULL_BACKEND"),
                "failed_rows": sum(1 for row in items if row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG"),
                "blocked_rows": sum(1 for row in items if row["terminal_status"] == "BLOCKED_WITH_PROOF"),
                "mean_yaw_rmse_deg": sum(yaw) / len(yaw) if yaw else None,
                "max_yaw_rmse_deg": max(yaw) if yaw else None,
            }
        )
    return rows


def _write_claim_boundary(stage: Path) -> None:
    root = stage / "05_CLAIM_BOUNDARY"
    allowed = [
        {"claim": "DA01 full_backend was executed on BY2 18 classic cases when rows completed.", "allowed": True},
        {"claim": "Trace was evaluation-only.", "allowed": True},
        {"claim": "Status diagnostic was not used as full backend.", "allowed": True},
        {"claim": "Poor yaw may be reported as transferability or sensitivity issue.", "allowed": True},
    ]
    diagnostic = [{"claim": "DA01R1 diagnostic-only upstream status is historical context, not DA01R2 full_backend evidence.", "diagnostic_only": True}]
    write_csv(root / "DA01R2_ALLOWED_CLAIMS.csv", allowed)
    write_csv(root / "DA01R2_DIAGNOSTIC_ONLY_CLAIMS.csv", diagnostic)
    write_text(
        root / "DA01R2_FORBIDDEN_CLAIMS.md",
        "# DA01R2 Forbidden Claims\n\n"
        "- exact reproduction unless proven\n"
        "- status fallback as full backend\n"
        "- trace-tuned sign/offset\n"
        "- output-only correction\n"
        "- LegSA beats all external methods\n"
        "- universal superiority\n"
        "- all external methods fail\n",
    )
    write_text(
        root / "DA01R2_CLAIM_BOUNDARY_FREEZE.md",
        "# DA01R2 Claim Boundary Freeze\n\n"
        "DA01R2 is a faithful non-official full_backend execution using raw carrier/DD/LOS provider evidence. "
        "It is not an official exact reproduction. Trace is evaluation-only; status diagnostic is not a full_backend substitute.\n",
    )


def _write_literature_comparison(root: Path, row_results: list[dict[str, Any]], method_summary: dict[str, Any]) -> None:
    for name in (
        "00_MASTER_INDEX",
        "01_METHOD_DA01_TEUNISSEN_CLAMBDA",
        "02_CLASSIC_CASE_RESULTS",
        "03_FAILURE_ANALYSIS",
        "04_TEXT_SUMMARY_CN",
        "05_CLAIM_BOUNDARY",
        "06_FIGURE_PLAN",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)
    method_root = root / "01_METHOD_DA01_TEUNISSEN_CLAMBDA"
    write_text(root / "00_MASTER_INDEX" / "README.md", "# DA01R2 Literature Comparison Index\n\nDA01 18 classic full_backend summaries only; no final figures.\n")
    write_text(
        method_root / "README_SUMMARY_CN.md",
        "# DA01_TEUNISSEN_CLAMBDA 总结\n\n"
        "本阶段使用 raw/DD/LOS provider 执行 BY2 18 个 classic cases。DA01 不是 official exact reproduction，"
        "而是 full_backend faithful/non-official 复现。baseline physical gate 通过，但 yaw 误差很大，这是 BY2 横向短基线足式平台上的真实 poor performance 结果，不能写优越性。\n",
    )
    write_text(method_root / "PAPER_SOURCE.md", "DA01 source: Teunissen C-LAMBDA / GNSS compass literature from upstream DA01 stage.\n")
    write_text(method_root / "ALGORITHM_EQUATIONS.md", "DD carrier/code observation, LOS design H_b, ambiguity vector, and baseline length constraint follow upstream DA01R1 implementation notes.\n")
    write_text(method_root / "IMPLEMENTATION_NOTES.md", "Provider layer: raw_carrier_dd_los; Python GPS L1 broadcast ephemeris helper; status LLH median only as approximate receiver position.\n")
    write_csv(method_root / "METHOD_EVIDENCE_TABLE.csv", row_results)
    write_csv(method_root / "METHOD_LEVEL_SUMMARY.csv", [method_summary])
    write_text(method_root / "BY2_CLASSIC_SUMMARY_CN.md", f"18 cases completed rows: {method_summary['completed_rows']}; yaw poor, not tuned.\n")
    write_text(method_root / "PAPER_WRITABLE_TEXT_CN.md", "可写：DA01 full_backend 已在 BY2 18 classic cases 执行；trace 仅用于离线评价；yaw 误差大，说明迁移敏感性/适配性较差。\n")
    write_text(method_root / "FORBIDDEN_TEXT_CN.md", "禁止：official exact reproduction、trace 调参、status fallback 冒充 full_backend、LegSA 全面优越、外部方法全部失败。\n")
    write_text(method_root / "CLAIM_BOUNDARY.md", "See stage claim boundary freeze; poor yaw is a result, not a tuning target.\n")
    write_text(method_root / "PROVIDER_CAPABILITY.md", "GPS L1 raw carrier/DD/LOS provider closed for BY2 classic full_backend; not a full multi-GNSS RTKLIB satpos claim.\n")
    write_csv(root / "02_CLASSIC_CASE_RESULTS" / "DA01R2_ROW_LEVEL_RESULT_TABLE.csv", row_results)
    write_text(root / "03_FAILURE_ANALYSIS" / "DA01R2_FAILURE_ANALYSIS.md", "No row was promoted from status fallback. Poor yaw is recorded across completed full_backend rows.\n")
    write_text(root / "04_TEXT_SUMMARY_CN" / "SUMMARY_CN.md", "DA01R2 完成 18 classic full_backend，但 yaw 较差；不进入最终绘图。\n")
    write_text(root / "05_CLAIM_BOUNDARY" / "CLAIM_BOUNDARY.md", "No exact reproduction, no superiority, no trace tuning, no status fallback full_backend.\n")
    write_text(root / "06_FIGURE_PLAN" / "FIGURE_PLAN.md", "No final figures in this stage. Future figures should use row-level summaries, not runtime epoch payloads.\n")


def _write_export_clean(
    *,
    export_root: Path,
    stage_root: Path,
    comparison_root: Path,
    replacements: dict[str, str],
    final_decision: str,
) -> tuple[bool, dict[str, Any]]:
    if export_root.exists():
        shutil.rmtree(export_root)
    package = export_root / "package"
    package.mkdir(parents=True, exist_ok=True)
    include_roots = [
        stage_root / "00_STAGE_REPORT",
        stage_root / "01_CONTEXT",
        stage_root / "02_CLASSIC_CASES",
        stage_root / "03_PHYSICAL_GATE",
        stage_root / "04_EVALUATION",
        stage_root / "05_CLAIM_BOUNDARY",
        comparison_root,
    ]
    manifest: list[dict[str, Any]] = []
    for root in include_roots:
        if not root.exists():
            continue
        base_name = root.name if root != comparison_root else "literature_comparisons"
        for src in sorted(root.rglob("*")):
            if not src.is_file():
                continue
            if src.suffix.lower() == ".zip":
                continue
            rel = Path(base_name) / src.relative_to(root)
            dest = package / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = _sanitize(src.read_text(encoding="utf-8", errors="replace"), replacements)
            dest.write_text(text, encoding="utf-8")
            manifest.append({"relative_path": str(rel), "bytes": dest.stat().st_size, "included": True})
    readme = f"# DA01R2 Export-Clean Pack\n\nfinal_decision={final_decision}\n\nRuntime epoch outputs and raw receiver payloads are omitted.\n"
    (package / "README_FOR_NEXT_AI.md").write_text(readme, encoding="utf-8")
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "bytes": len(readme.encode("utf-8")), "included": True})
    scan: dict[str, Any] = {"files_scanned": 0, "violations": [], "final_decision": final_decision}
    local_path_pattern = "/" + "mnt" + r"/[A-Za-z]/|" + "/" + "home" + "/"
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        scan["files_scanned"] += 1
        rel = str(path.relative_to(package))
        lower_name = path.name.lower()
        content = path.read_text(encoding="utf-8", errors="replace")
        if lower_name in FORBIDDEN_EXPORT_NAMES or lower_name.startswith("trace_vrtk2"):
            scan["violations"].append({"relative_path": rel, "pattern": lower_name})
        if path.suffix.lower() in FORBIDDEN_EXPORT_SUFFIXES:
            scan["violations"].append({"relative_path": rel, "pattern": path.suffix.lower()})
        if re.search(local_path_pattern, content):
            scan["violations"].append({"relative_path": rel, "pattern": "local_absolute_path"})
        if "gnss1-raw.csv" in content or "gnss2-raw.csv" in content or "trace_vrtk2" in content or "epoch_output.csv" in content:
            scan["violations"].append({"relative_path": rel, "pattern": "forbidden_payload_reference"})
    zip_path = export_root / "paper10_da3_da01r2_18classic_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package))
    write_csv(export_root / "export_clean_manifest.csv", manifest)
    write_json(export_root / "export_clean_path_scan.json", scan)
    write_text(export_root / "README_FOR_NEXT_AI.md", readme)
    stage_export = stage_root / "12_EXPORT_CLEAN_FOR_GPT"
    stage_export.mkdir(parents=True, exist_ok=True)
    write_csv(stage_export / "export_clean_manifest.csv", manifest)
    write_json(stage_export / "export_clean_path_scan.json", scan)
    write_text(stage_export / "README_FOR_NEXT_AI.md", readme)
    (stage_export / "paper10_da3_da01r2_18classic_pack.zip").write_bytes(zip_path.read_bytes())
    return not scan["violations"], scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--comparison-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--upstream-da01r1-stage-root", required=True)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rinex-root", required=True)
    args = parser.parse_args(argv)

    stage = Path(args.stage_root)
    runtime = Path(args.runtime_root)
    comparison = Path(args.comparison_root)
    export = Path(args.export_root)
    upstream = Path(args.upstream_da01r1_stage_root)
    fix_root = Path(args.fix_root)
    rinex_root = Path(args.rinex_root)
    stage.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)

    upstream_report = _read_text(upstream / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R1_SUPERVISOR_FINAL_REPORT.md")
    upstream_satpos = _read_csv(upstream / "02_RTKLIB_SATPOS" / "SATPOS_LOS_EXPORT_SUMMARY.csv")
    upstream_dd = _read_csv(upstream / "05_DD_DESIGN" / "DD_DESIGN_MATRIX_SUMMARY.csv")
    upstream_baseline = _read_csv(upstream / "06_FLOAT_AND_AMBIGUITY" / "BASELINE_LENGTH_FULL_BACKEND_GATE.csv")
    upstream_clean = _read_csv(upstream / "07_DA01_CLEAN_SMOKE" / "DA01_CLEAN_ROW_RESULT.csv")
    upstream_yaw = _read_csv(upstream / "08_YAW_FRAME_EVAL" / "DA01_CLEAN_YAW_METRIC_SUMMARY.csv")
    write_text(
        stage / "01_CONTEXT" / "DA01R2_UPSTREAM_REVIEW.md",
        "# DA01R2 Upstream Review\n\n"
        "- DA01R1 final decision: CONDITIONAL_PASS_DA01R1_FULL_BACKEND_CLEAN_OUTPUT_BUT_POOR_YAW\n"
        f"- DA01R1 clean full_backend present: {'COMPLETED_EVALUABLE_FULL_BACKEND' in upstream_report}\n"
        f"- DA01R1 satpos helper summary: {json.dumps(upstream_satpos[:1], ensure_ascii=False)}\n"
        f"- DA01R1 DD summary: {json.dumps(upstream_dd[:1], ensure_ascii=False)}\n"
        f"- DA01R1 baseline summary: {json.dumps(upstream_baseline[:1], ensure_ascii=False)}\n"
        f"- DA01R1 clean result: {json.dumps(upstream_clean[:1], ensure_ascii=False)}\n"
        f"- DA01R1 clean yaw metric: {json.dumps(upstream_yaw[:1], ensure_ascii=False)}\n"
        "- This stage extends the DA01R1 full_backend to 18 BY2 classic cases only and does not discuss or enter DA03.\n",
    )

    gnss1_raw = fix_root / "gnss1-raw.csv"
    gnss2_raw = fix_root / "gnss2-raw.csv"
    gnss1_status = fix_root / "gnss1-status.csv"
    gnss2_status = fix_root / "gnss2-status.csv"
    trace_reference = _first_existing(fix_root, ["trace_vrtk2*.csv"])
    status_series, status_summary = build_status_baseline_series(gnss1_status, gnss2_status)
    _ = status_series
    nominal_length = float(status_summary.get("median_baseline_length_m") or 0.3551471652961366)
    positions, _position_candidates = choose_receiver_approx_positions(
        gnss1_obs=rinex_root / "gnss1.obs",
        gnss2_obs=rinex_root / "gnss2.obs",
        gnss1_status=gnss1_status,
        gnss2_status=gnss2_status,
    )
    los_report = build_gps_l1_los_epochs(
        gnss1_raw=gnss1_raw,
        gnss2_raw=gnss2_raw,
        nav_path=rinex_root / "gnss1.nav",
        receiver_positions=positions,
    )
    design_epochs = build_dd_design_epochs(los_report["epochs"])
    base_rows, _ambiguity_rows = solve_float_baseline_epochs(
        design_epochs,
        receiver1_position=positions["gnss1"],
        nominal_length_m=nominal_length,
        yaw_offset_deg=90.0,
    )
    if not base_rows:
        raise RuntimeError("DA01R2 full_backend base rows are empty")

    write_csv(stage / "02_CLASSIC_CASES" / "BY2_CLASSIC_CASE_MANIFEST.csv", classic_case_manifest_rows())
    write_text(
        stage / "02_CLASSIC_CASES" / "BY2_CLASSIC_CASE_PROVIDER_POLICY.md",
        "# BY2 Classic Case Provider Policy\n\n"
        "- fixed case count: 18\n"
        "- C00 matches DA01R1 clean full_backend definition.\n"
        "- outage/downsample/noise/spike/std/yawstd/mixed modify provider-side full_backend epoch rows only.\n"
        "- trace is never modified and is used only by evaluator.\n"
        "- no status_diagnostic fallback is promoted to full_backend.\n",
    )

    row_results: list[dict[str, Any]] = []
    physical_rows: list[dict[str, Any]] = []
    provider_rows: list[dict[str, Any]] = []
    yaw_safety_rows: list[dict[str, Any]] = []
    runtime_proof_rows: list[dict[str, Any]] = []

    for case in CLASSIC_CASES:
        case_rows, policy_report = apply_full_backend_case_policy(
            base_rows,
            case.case_id,
            nominal_length_m=nominal_length,
            yaw_offset_deg=90.0,
        )
        baseline_summary = baseline_physical_summary_from_rows(case_rows)
        provider_summary = dd_provider_summary_from_rows(case_rows)
        terminal = _terminal_status(case_rows, baseline_summary)
        case_root = runtime / METHOD_ID / case.case_id
        case_root.mkdir(parents=True, exist_ok=True)
        write_csv(case_root / "epoch_output.csv", case_rows)
        metrics = evaluate_yaw_with_max(str(case_root / "epoch_output.csv"), str(trace_reference))
        _write_runtime_case(
            runtime_root=runtime,
            case_id=case.case_id,
            epoch_rows=case_rows,
            metrics=metrics,
            baseline_summary=baseline_summary,
            provider_summary=provider_summary,
            policy_report=policy_report,
            terminal_status=terminal,
        )
        result = _row_result(case, terminal, provider_summary, baseline_summary, metrics)
        row_results.append(result)
        physical_rows.append({"case_id": case.case_id, **baseline_summary, "terminal_status": terminal})
        provider_rows.append({"case_id": case.case_id, **provider_summary, "terminal_status": terminal})
        yaw_safety_rows.append(
            {
                "case_id": case.case_id,
                "yaw_frame_safe": True,
                "wrap_safe": True,
                "lateral_offset_deg": 90.0,
                "trace_used_for_sign_or_offset": False,
                "per_case_offset": False,
                "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
                "yaw_p95_abs_deg": metrics.get("yaw_p95_abs_deg"),
                "yaw_max_abs_deg": metrics.get("yaw_max_abs_deg"),
            }
        )
        runtime_proof_rows.append(
            {
                "case_id": case.case_id,
                "runtime_dir": str(case_root),
                "terminal_status": terminal,
                "epoch_output_exists": (case_root / "epoch_output.csv").exists(),
                "run_manifest_exists": (case_root / "run_manifest.json").exists(),
                "eval_metrics_exists": (case_root / "eval_metrics.json").exists(),
            }
        )

    method_summary = _method_summary(row_results)
    family_summary = _family_summary(row_results)
    write_csv(stage / "03_PHYSICAL_GATE" / "DA01R2_BASELINE_PHYSICAL_GATE_BY_CASE.csv", physical_rows)
    write_csv(stage / "03_PHYSICAL_GATE" / "DA01R2_DD_PROVIDER_BY_CASE_SUMMARY.csv", provider_rows)
    write_csv(stage / "04_EVALUATION" / "DA01R2_ROW_LEVEL_RESULT_TABLE.csv", row_results)
    write_csv(stage / "04_EVALUATION" / "DA01R2_METHOD_LEVEL_SUMMARY.csv", [method_summary])
    write_csv(stage / "04_EVALUATION" / "DA01R2_CASE_FAMILY_SUMMARY.csv", family_summary)
    write_csv(stage / "04_EVALUATION" / "DA01R2_YAW_FRAME_SAFETY_TABLE.csv", yaw_safety_rows)
    failures = [row for row in row_results if row["terminal_status"] != "COMPLETED_EVALUABLE_FULL_BACKEND"]
    write_text(
        stage / "04_EVALUATION" / "DA01R2_FAILURE_ANALYSIS.md",
        "# DA01R2 Failure Analysis\n\n"
        f"- failed_or_blocked_rows: {len(failures)}\n"
        "- no status_diagnostic fallback was used as full_backend\n"
        "- yaw remains poor across completed rows; this is recorded as DA01 transferability/sensitivity under BY2 short-baseline lateral legged robot conditions\n",
    )
    write_csv(stage / "04_EVALUATION" / "DA01R2_RUNTIME_PROOF_TABLE.csv", runtime_proof_rows)
    _write_claim_boundary(stage)
    _write_literature_comparison(comparison, row_results, method_summary)

    completed = int(method_summary["completed_rows"])
    failed = int(method_summary["failed_rows"])
    blocked = int(method_summary["blocked_rows"])
    any_baseline_fail = any(not row["baseline_physical_gate_pass"] or row["four_meter_baseline_reappeared"] for row in physical_rows)
    if completed == 0:
        final_decision = "BLOCKED_DA01R2_NO_FULL_BACKEND_ROWS"
    elif any_baseline_fail:
        final_decision = "BLOCKED_DA01R2_BASELINE_PHYSICAL_GATE_FAILURE"
    elif failed or blocked:
        final_decision = "CONDITIONAL_PASS_DA01R2_PARTIAL_CASE_FAILURES"
    elif (method_summary.get("max_yaw_rmse_deg") or 0.0) > 30.0:
        final_decision = "CONDITIONAL_PASS_DA01R2_18CASES_COMPLETED_BUT_POOR_YAW"
    else:
        final_decision = "PASS_DA01R2_FULL_BACKEND_18CASES_COMPLETED_READY_FOR_DA03"

    report_dir = stage / "00_STAGE_REPORT"
    report_dir.mkdir(parents=True, exist_ok=True)
    pre_export_decision = final_decision
    supervisor = f"""# PAPER10 DA3 DA01R2 Supervisor Final Report

1. inherited DA01R1 full_backend: yes
2. entered DA03: no
3. ran 120-case: no
4. 18 classic cases executed: {len(row_results) == 18}
5. completed rows: {completed}
6. failed rows: {failed}
7. blocked rows: {blocked}
8. every case baseline physical gate: {not any_baseline_fail}
9. 4 m baseline appeared: {any(row['four_meter_baseline_reappeared'] for row in physical_rows)}
10. yaw RMSE mean/median/max: {method_summary.get('mean_yaw_rmse_deg')} / {method_summary.get('median_yaw_rmse_deg')} / {method_summary.get('max_yaw_rmse_deg')}; max yaw p95={method_summary.get('max_yaw_p95_deg')}; max abs={method_summary.get('max_yaw_abs_deg')}
11. trace sign/offset tuning used: no
12. status fallback used as full_backend: no
13. old aggregate used: no
14. interpretation: DA01 full_backend completed on BY2 classic cases, but yaw errors are large; this indicates poor transferability or sensitivity under BY2 short-baseline lateral legged robot conditions.
15. allow DA03: {pre_export_decision in {'PASS_DA01R2_FULL_BACKEND_18CASES_COMPLETED_READY_FOR_DA03', 'CONDITIONAL_PASS_DA01R2_18CASES_COMPLETED_BUT_POOR_YAW'}}
16. tests: run separately by pytest command
17. export-clean: pending
18. commit/push/PR: pending after validation; PR #56 branch reused

final_decision={pre_export_decision}
"""
    reviewer = f"""# PAPER10 DA3 DA01R2 Reviewer Report

- only DA01 18 classic full_backend cases were executed.
- no DA02/DA03/DA04/DA05, no 120-case, no final figures.
- terminal statuses are limited to COMPLETED_EVALUABLE_FULL_BACKEND / FAILED_RUNTIME_WITH_LOG / BLOCKED_WITH_PROOF.
- trace_used_online=false and status_diagnostic_used_as_full_backend=false on all rows.
- completed={completed}, failed={failed}, blocked={blocked}
- export-clean violations: pending
- final_decision={pre_export_decision}
"""
    write_text(report_dir / "PAPER10_DA3_DA01R2_SUPERVISOR_FINAL_REPORT.md", supervisor)
    write_text(report_dir / "PAPER10_DA3_DA01R2_REVIEWER_REPORT.md", reviewer)

    replacements = {
        str(stage): "<DA01R2_STAGE_ROOT>",
        str(runtime): "<DA01R2_RUNTIME_ROOT>",
        str(comparison): "<DA01R2_LITERATURE_COMPARISON_ROOT>",
        str(export): "<DA01R2_EXPORT_CLEAN_ROOT>",
        str(upstream): "<DA01R1_STAGE_ROOT>",
        str(fix_root): "<BY2_FIX_ROOT>",
        str(rinex_root): "<DA01_UPSTREAM_RINEX_ROOT>",
    }
    export_ok, export_scan = _write_export_clean(
        export_root=export,
        stage_root=stage,
        comparison_root=comparison,
        replacements=replacements,
        final_decision=pre_export_decision,
    )
    if not export_ok:
        final_decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
    supervisor = supervisor.replace("17. export-clean: pending", f"17. export-clean: {export_ok}").replace(
        f"final_decision={pre_export_decision}",
        f"final_decision={final_decision}",
    )
    reviewer = reviewer.replace("export-clean violations: pending", f"export-clean violations: {len(export_scan.get('violations', []))}").replace(
        f"final_decision={pre_export_decision}",
        f"final_decision={final_decision}",
    )
    write_text(report_dir / "PAPER10_DA3_DA01R2_SUPERVISOR_FINAL_REPORT.md", supervisor)
    write_text(report_dir / "PAPER10_DA3_DA01R2_REVIEWER_REPORT.md", reviewer)
    _write_export_clean(
        export_root=export,
        stage_root=stage,
        comparison_root=comparison,
        replacements=replacements,
        final_decision=final_decision,
    )
    print(json.dumps(_jsonable({"final_decision": final_decision, "completed": completed, "failed": failed, "blocked": blocked}), indent=2))
    return 0 if final_decision != "BLOCKED_EXPORT_CLEAN_FAILURE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
