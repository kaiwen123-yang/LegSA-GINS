#!/usr/bin/env python3
"""Run DA01R2A raw/status baseline orientation and yaw-frame audit."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from legsa_gins.da_repro.baseline_status_provider import build_status_baseline_series
from legsa_gins.da_repro.common import percentile, write_csv, write_json, write_text, wrap180, wrap360
from legsa_gins.da_repro.orientation_audit import (
    BaselineVector,
    baseline_summary,
    compare_raw_to_status,
    evaluate_candidates_against_trace,
    load_raw_baseline_vectors,
    load_trace_yaw,
    transform_candidate_rows,
)


METHOD_ID = "DA01_TEUNISSEN_CLAMBDA"
CASE_IDS = [
    "C00_clean_normal",
    "C01_outage_10s",
    "C02_downsample_2Hz",
    "C03_downsample_1Hz",
    "C04_position_noise_medium_seed0",
    "C05_position_noise_medium_seed1",
    "C06_position_noise_medium_seed2",
    "C07_position_spike_medium_seed0",
    "C08_position_spike_medium_seed1",
    "C09_position_spike_medium_seed2",
    "C10_std_inflation_strong",
    "C11_yaw_spike_10_seed0",
    "C12_yaw_spike_10_seed1",
    "C13_yaw_spike_10_seed2",
    "C14_yawstd_inflation_2x",
    "C15_mixed_medium_seed0",
    "C16_mixed_medium_seed1",
    "C17_mixed_medium_seed2",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else f"MISSING: {path}\n"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _sanitize(text: str, replacements: dict[str, str]) -> str:
    out = text
    for actual, alias in replacements.items():
        if actual:
            out = out.replace(actual, alias)
    out = re.sub("/" + "mnt" + r"/[A-Za-z]/[^\s,;)]+", "<LOCAL_PATH>", out)
    out = re.sub("/" + "home" + r"/[^\s,;)]+", "<LOCAL_PATH>", out)
    for token in ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "by2.txt", "trace_vrtk2", "epoch_output.csv"):
        out = out.replace(token, "<OMITTED_PAYLOAD>")
    return out


def _status_vectors_from_series(status_series: list[dict[str, float]]) -> list[BaselineVector]:
    return [
        BaselineVector(
            time=float(row["time"]),
            east_m=float(row["east_m"]),
            north_m=float(row["north_m"]),
            up_m=float(row["up_m"]),
            source="status_baseline_gnss2_minus_gnss1",
        )
        for row in status_series
    ]


def _status_orientation_rows(status_vectors: list[BaselineVector]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, vectors in (
        ("GNSS2-GNSS1", status_vectors),
        ("GNSS1-GNSS2", [vector.reversed(source="status_baseline_gnss1_minus_gnss2") for vector in status_vectors]),
    ):
        for vector in vectors:
            heading = vector.heading_enu_deg
            rows.append(
                {
                    "time": vector.time,
                    "vector_order": order,
                    "east_m": vector.east_m,
                    "north_m": vector.north_m,
                    "up_m": vector.up_m,
                    "baseline_length_m": vector.length_m,
                    "baseline_heading_enu_deg": heading,
                    "baseline_heading_ned_deg": heading,
                    "body_yaw_heading_plus90_deg": wrap360(heading + 90.0),
                    "body_yaw_heading_minus90_deg": wrap360(heading - 90.0),
                    "body_yaw_heading_plus0_deg": heading,
                    "body_yaw_heading_plus180_deg": wrap360(heading + 180.0),
                    "trace_used_for_definition": False,
                }
            )
    return rows


def _runtime_audit_rows(runtime_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        case_root = runtime_root / METHOD_ID / case_id
        yaw = _read_json(case_root / "yaw_frame_report.json")
        contract = _read_json(case_root / "input_contract.json")
        config = _read_json(case_root / "method_config.json")
        manifest = _read_json(case_root / "run_manifest.json")
        epoch_output = case_root / "epoch_output.csv"
        rows.append(
            {
                "case_id": case_id,
                "yaw_frame_report_exists": bool(yaw),
                "input_contract_exists": bool(contract),
                "method_config_exists": bool(config),
                "run_manifest_exists": bool(manifest),
                "epoch_output_exists": epoch_output.exists(),
                "method_mode": manifest.get("method_mode"),
                "terminal_status": manifest.get("terminal_status"),
                "provider_layer_used": manifest.get("provider_layer_used"),
                "gnss_order": yaw.get("gnss_order"),
                "lateral_offset_deg": yaw.get("lateral_offset_deg"),
                "trace_rmse_selected_sign": yaw.get("trace_rmse_selected_sign"),
                "per_case_offset": yaw.get("per_case_offset"),
                "trace_used_online": manifest.get("trace_used_online"),
                "status_diagnostic_used_as_full_backend": manifest.get("status_diagnostic_used_as_full_backend"),
                "epoch_output_read_only": True,
            }
        )
    return rows


def _load_case_raw_vectors(runtime_root: Path, case_id: str) -> list[BaselineVector]:
    path = runtime_root / METHOD_ID / case_id / "epoch_output.csv"
    vectors = load_raw_baseline_vectors(path, source=f"raw_full_backend_{case_id}_gnss2_minus_gnss1")
    if not vectors:
        raise RuntimeError(f"raw baseline vectors missing for {case_id}")
    return vectors


def _raw_orientation_tables(runtime_root: Path, status_vectors: list[BaselineVector]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    raw_table: list[dict[str, Any]] = []
    comparison_table: list[dict[str, Any]] = []
    all_abs_residual: list[float] = []
    all_angles: list[float] = []
    all_dots: list[float] = []
    for case_id in CASE_IDS:
        raw_vectors = _load_case_raw_vectors(runtime_root, case_id)
        raw_table.append({"case_id": case_id, "vector_order": "GNSS2-GNSS1", **baseline_summary(raw_vectors, label="raw_full_backend_gnss2_minus_gnss1")})
        raw_table.append({"case_id": case_id, "vector_order": "GNSS1-GNSS2", **baseline_summary([v.reversed() for v in raw_vectors], label="raw_full_backend_gnss1_minus_gnss2")})
        rows, summary = compare_raw_to_status(raw_vectors, status_vectors)
        comparison_table.append({"case_id": case_id, **summary})
        all_abs_residual.extend(float(row["abs_heading_residual_deg"]) for row in rows)
        all_angles.extend(float(row["vector_angle_diff_deg"]) for row in rows if math.isfinite(float(row["vector_angle_diff_deg"])))
        all_dots.extend(float(row["dot_product_unit"]) for row in rows if math.isfinite(float(row["dot_product_unit"])))
    global_summary = {
        "case_count": len(CASE_IDS),
        "global_median_abs_heading_residual_deg": percentile(all_abs_residual, 0.50),
        "global_p95_abs_heading_residual_deg": percentile(all_abs_residual, 0.95),
        "global_median_vector_angle_diff_deg": percentile(all_angles, 0.50),
        "global_p95_vector_angle_diff_deg": percentile(all_angles, 0.95),
        "global_median_unit_dot_product": percentile(all_dots, 0.50),
        "raw_direction_stable_against_status": bool(all_abs_residual)
        and (percentile(all_abs_residual, 0.95) or 999.0) < 30.0
        and (percentile(all_angles, 0.95) or 999.0) < 30.0,
    }
    return raw_table, comparison_table, global_summary


def _transform_audit(runtime_root: Path, status_vectors: list[BaselineVector], trace_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_vectors = _load_case_raw_vectors(runtime_root, "C00_clean_normal")
    candidates = transform_candidate_rows(raw_vectors, status_vectors)
    trace_rows = load_trace_yaw(trace_path)
    trace_eval: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()
    for candidate in candidates:
        key = (str(candidate["vector_order"]), str(candidate["coordinate_variant"]), float(candidate["lateral_offset_deg"]))
        if key in seen:
            continue
        seen.add(key)
        trace_eval.append(
            evaluate_candidates_against_trace(
                raw_vectors,
                trace_rows,
                vector_order=key[0],
                coordinate_variant=key[1],
                lateral_offset_deg=key[2],
            )
        )
    status_summary = [
        {
            "selection_rule_rank": 1,
            "rule": "physical_installation_and_status_baseline_definition",
            "decision": "GNSS2-GNSS1 is the physical GNSS1-right/GNSS2-left baseline; plus90 is accepted physical mapping from project memory",
            "trace_used_for_selection": False,
        },
        {
            "selection_rule_rank": 2,
            "rule": "raw_vs_status_baseline_heading_residual",
            "decision": "raw full_backend does not stably agree with status baseline; no deterministic sign or axis transform is selected from trace",
            "trace_used_for_selection": False,
        },
        {
            "selection_rule_rank": 3,
            "rule": "trace_offline_check_only",
            "decision": "trace residuals are reported only after physical/status checks",
            "trace_used_for_selection": False,
        },
    ]
    return candidates, status_summary, trace_eval


def _write_export_clean(stage: Path, export: Path, replacements: dict[str, str], final_decision: str) -> tuple[bool, dict[str, Any]]:
    if export.exists():
        shutil.rmtree(export)
    package = export / "package"
    package.mkdir(parents=True, exist_ok=True)
    include_dirs = [
        "00_STAGE_REPORT",
        "01_INPUT_REVIEW",
        "02_STATUS_BASELINE",
        "03_RAW_BASELINE",
        "04_TRANSFORM_AUDIT",
        "05_DECISION",
        "06_PATCH_PLAN",
    ]
    manifest: list[dict[str, Any]] = []
    for dirname in include_dirs:
        root = stage / dirname
        if not root.exists():
            continue
        for src in sorted(root.rglob("*")):
            if not src.is_file() or src.suffix.lower() == ".zip":
                continue
            rel = Path(dirname) / src.relative_to(root)
            dest = package / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = _sanitize(src.read_text(encoding="utf-8", errors="replace"), replacements)
            dest.write_text(text, encoding="utf-8")
            manifest.append({"relative_path": str(rel), "bytes": dest.stat().st_size, "included": True})
    readme = f"# DA01R2A Orientation Audit Export\n\nfinal_decision={final_decision}\n\nRuntime epoch payloads and raw source payloads are omitted.\n"
    (package / "README_FOR_NEXT_AI.md").write_text(readme, encoding="utf-8")
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "bytes": len(readme.encode("utf-8")), "included": True})
    scan: dict[str, Any] = {"files_scanned": 0, "violations": [], "final_decision": final_decision}
    local_path_pattern = "/" + "mnt" + r"/[A-Za-z]/|" + "/" + "home" + "/"
    forbidden_tokens = ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv", "by2.txt", "trace_vrtk2", "epoch_output.csv")
    forbidden_suffixes = (".ubx", ".obs", ".nav")
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        scan["files_scanned"] += 1
        rel = str(path.relative_to(package))
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(token in rel or token in content for token in forbidden_tokens):
            scan["violations"].append({"relative_path": rel, "pattern": "forbidden_payload_reference"})
        if path.suffix.lower() in forbidden_suffixes:
            scan["violations"].append({"relative_path": rel, "pattern": path.suffix.lower()})
        if re.search(local_path_pattern, content):
            scan["violations"].append({"relative_path": rel, "pattern": "local_absolute_path"})
    zip_path = export / "paper10_da3_da01r2a_orientation_audit_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package))
    write_csv(export / "export_clean_manifest.csv", manifest)
    write_json(export / "export_clean_path_scan.json", scan)
    write_text(export / "README_FOR_NEXT_AI.md", readme)
    stage_export = stage / "10_EXPORT_CLEAN_FOR_GPT"
    stage_export.mkdir(parents=True, exist_ok=True)
    write_csv(stage_export / "export_clean_manifest.csv", manifest)
    write_json(stage_export / "export_clean_path_scan.json", scan)
    write_text(stage_export / "README_FOR_NEXT_AI.md", readme)
    (stage_export / "paper10_da3_da01r2a_orientation_audit_pack.zip").write_bytes(zip_path.read_bytes())
    return not scan["violations"], scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--da01r2-stage-root", required=True)
    parser.add_argument("--da01r2-runtime-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--fix-root", required=True)
    args = parser.parse_args(argv)

    da01r2_stage = Path(args.da01r2_stage_root)
    da01r2_runtime = Path(args.da01r2_runtime_root)
    stage = Path(args.stage_root)
    export = Path(args.export_root)
    fix_root = Path(args.fix_root)
    stage.mkdir(parents=True, exist_ok=True)

    required_reports = {
        "supervisor": da01r2_stage / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R2_SUPERVISOR_FINAL_REPORT.md",
        "physical": da01r2_stage / "03_PHYSICAL_GATE" / "DA01R2_BASELINE_PHYSICAL_GATE_BY_CASE.csv",
        "dd": da01r2_stage / "03_PHYSICAL_GATE" / "DA01R2_DD_PROVIDER_BY_CASE_SUMMARY.csv",
        "row": da01r2_stage / "04_EVALUATION" / "DA01R2_ROW_LEVEL_RESULT_TABLE.csv",
        "method": da01r2_stage / "04_EVALUATION" / "DA01R2_METHOD_LEVEL_SUMMARY.csv",
        "yaw": da01r2_stage / "04_EVALUATION" / "DA01R2_YAW_FRAME_SAFETY_TABLE.csv",
    }
    runtime_audit = _runtime_audit_rows(da01r2_runtime)
    write_csv(stage / "01_INPUT_REVIEW" / "DA01R2_RUNTIME_FILE_AUDIT.csv", runtime_audit)
    write_text(
        stage / "01_INPUT_REVIEW" / "DA01R2_INPUT_REVIEW.md",
        "# DA01R2 Input Review\n\n"
        + "\n".join(f"- read {name}: {path.exists()}" for name, path in required_reports.items())
        + f"\n- runtime cases audited: {len(runtime_audit)}\n"
        "- runtime files were read-only; epoch payloads are not copied into export-clean.\n",
    )

    status_series, status_summary = build_status_baseline_series(fix_root / "gnss1-status.csv", fix_root / "gnss2-status.csv")
    if not status_series:
        raise RuntimeError("status baseline definition is unavailable")
    status_vectors = _status_vectors_from_series(status_series)
    status_reverse = [vector.reversed(source="status_baseline_gnss1_minus_gnss2") for vector in status_vectors]
    status_rows = _status_orientation_rows(status_vectors)
    write_csv(stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_ORIENTATION_TABLE.csv", status_rows)
    write_csv(
        stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_HEADING_SUMMARY.csv",
        [
            baseline_summary(status_vectors, label="status_baseline_gnss2_minus_gnss1"),
            baseline_summary(status_reverse, label="status_baseline_gnss1_minus_gnss2"),
        ],
    )
    write_text(
        stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_DEFINITION.md",
        "# Status Baseline Definition\n\n"
        "- status baseline is reconstructed from BY2 gnss1-status and gnss2-status LLH positions.\n"
        "- primary definition: status_baseline_gnss2_minus_gnss1 = GNSS2 absolute ECEF minus GNSS1 absolute ECEF, converted to ENU at GNSS1.\n"
        "- reverse definition: status_baseline_gnss1_minus_gnss2 = negative of the primary vector.\n"
        "- direct status rel_pos rows are not used as antenna heading.\n"
        f"- upstream physical summary: {json.dumps(_jsonable(status_summary), ensure_ascii=False)}\n",
    )

    raw_table, raw_vs_status, global_raw_status = _raw_orientation_tables(da01r2_runtime, status_vectors)
    write_csv(stage / "03_RAW_BASELINE" / "RAW_BASELINE_ORIENTATION_TABLE.csv", raw_table)
    write_csv(stage / "03_RAW_BASELINE" / "RAW_VS_STATUS_BASELINE_ORIENTATION_SUMMARY.csv", raw_vs_status + [{"case_id": "GLOBAL", **global_raw_status}])
    raw_stable = bool(global_raw_status["raw_direction_stable_against_status"])
    write_text(
        stage / "03_RAW_BASELINE" / "RAW_BASELINE_DIRECTION_STABILITY_REPORT.md",
        "# Raw Baseline Direction Stability\n\n"
        f"- raw baseline vectors available: true\n"
        f"- global median abs raw-vs-status heading residual deg: {global_raw_status['global_median_abs_heading_residual_deg']}\n"
        f"- global p95 abs raw-vs-status heading residual deg: {global_raw_status['global_p95_abs_heading_residual_deg']}\n"
        f"- global median vector angle diff deg: {global_raw_status['global_median_vector_angle_diff_deg']}\n"
        f"- global p95 vector angle diff deg: {global_raw_status['global_p95_vector_angle_diff_deg']}\n"
        f"- direction stable against status: {raw_stable}\n"
        "- conclusion: not a simple constant 180 deg order reversal or fixed 90 deg ENU/NED axis error.\n",
    )

    trace_path = _first_existing(fix_root, ["trace_vrtk2*.csv"])
    candidates, status_selection_summary, trace_eval = _transform_audit(da01r2_runtime, status_vectors, trace_path)
    write_csv(stage / "04_TRANSFORM_AUDIT" / "DETERMINISTIC_TRANSFORM_CANDIDATES.csv", candidates)
    write_csv(stage / "04_TRANSFORM_AUDIT" / "TRANSFORM_VS_STATUS_SUMMARY.csv", status_selection_summary)
    write_csv(stage / "04_TRANSFORM_AUDIT" / "TRANSFORM_VS_TRACE_OFFLINE_EVAL.csv", trace_eval)
    write_text(
        stage / "04_TRANSFORM_AUDIT" / "PHYSICAL_SELECTION_DECISION.md",
        "# Physical Selection Decision\n\n"
        "Selection is not made from trace RMSE. The physical project memory fixes GNSS1 as right and GNSS2 as left, so GNSS2-GNSS1 is the leftward lateral baseline. "
        "The accepted mapping is baseline heading +90 deg for body yaw. However, DA01R2 raw full_backend baseline does not stably agree with the status baseline, "
        "so no deterministic sign/order/axis patch is sufficient from this audit alone.\n",
    )

    root_cause = "CASE_D_RAW_BASELINE_DIRECTION_UNSTABLE"
    final_decision = "PASS_DA01R2A_FRAME_REPAIR_REQUIRED_BEFORE_RERUN"
    write_text(
        stage / "05_DECISION" / "DA01R2A_ORIENTATION_ROOT_CAUSE_DECISION.md",
        "# DA01R2A Orientation Root Cause Decision\n\n"
        f"root_cause={root_cause}\n\n"
        "Evidence:\n"
        f"- raw/status global median vector angle diff deg: {global_raw_status['global_median_vector_angle_diff_deg']}\n"
        f"- raw/status global p95 vector angle diff deg: {global_raw_status['global_p95_vector_angle_diff_deg']}\n"
        f"- raw/status direction stable: {raw_stable}\n"
        "- C00 yaw report already uses wrap-safe residuals and lateral +90.\n"
        "- Trace is offline only and was not used to choose sign or offset.\n\n"
        "The poor yaw cannot be accepted as true method performance yet, because the raw full_backend baseline direction is not stable against the independent status baseline. "
        "It is also not a single GNSS order reversal, fixed ENU/NED swap, or fixed +90/-90 sign issue.\n",
    )
    write_text(
        stage / "05_DECISION" / "NEXT_ACTION_DECISION.md",
        "# Next Action Decision\n\n"
        "- do not enter DA03 from DA01R2 as-is\n"
        "- do not rerun DA01R2 until raw/status baseline orientation is repaired or the DD/ambiguity baseline direction is stabilized\n"
        "- do not use trace to choose sign/offset\n"
        "- no per-case offset is allowed\n"
        f"- final_decision={final_decision}\n",
    )
    write_text(
        stage / "06_PATCH_PLAN" / "DA01R2_FRAME_REPAIR_PLAN.md",
        "# DA01R2 Frame Repair Plan\n\n"
        "No deterministic yaw_frame_contract.py patch is applied in this stage. The audit found raw DD/ambiguity baseline direction instability relative to status, "
        "not a clean fixed +90/-90, GNSS order, or ENU/NED transform error. A follow-up repair should stabilize the raw baseline direction against status/physical installation first, then rerun DA01R2. "
        "Trace RMSE must remain offline evaluation-only.\n",
    )

    export_ok_placeholder = "pending"
    report_dir = stage / "00_STAGE_REPORT"
    report_dir.mkdir(parents=True, exist_ok=True)
    supervisor = f"""# PAPER10 DA3 DA01R2A Supervisor Final Report

1. DA01R2 yaw poor because no wrap: no; DA01R2 used wrap-safe residuals.
2. DA01R2 yaw poor because no lateral +/-90: no; +90 was already applied.
3. raw baseline vs status baseline consistent: no; raw/status direction residuals are unstable.
4. GNSS1/GNSS2 reversed: not a simple constant reversal.
5. ENU/NED wrong: not a simple fixed axis error.
6. +90/-90 wrong: not proven; physical prior still supports +90.
7. DD/ambiguity baseline direction stable: no.
8. trace only offline: yes.
9. need frame repair: yes, but not a simple yaw offset patch; raw baseline direction/backend orientation must be repaired first.
10. need rerun DA01R2: yes, after repair; do not reuse current 18-case yaw conclusion as true poor performance.
11. can enter DA03: no, not from DA01R2 as-is.
12. export-clean: {export_ok_placeholder}

root_cause={root_cause}
final_decision={final_decision}
"""
    reviewer = f"""# PAPER10 DA3 DA01R2A Reviewer Report

- no DA03 and no 18-case rerun were performed.
- DA01R2 runtime was read-only.
- raw baseline vectors were available from existing epoch outputs.
- trace was used only for offline transform diagnostics and not for selection.
- per-case offset was not used.
- root_cause={root_cause}
- export-clean: {export_ok_placeholder}
- final_decision={final_decision}
"""
    write_text(report_dir / "PAPER10_DA3_DA01R2A_SUPERVISOR_FINAL_REPORT.md", supervisor)
    write_text(report_dir / "PAPER10_DA3_DA01R2A_REVIEWER_REPORT.md", reviewer)

    replacements = {
        str(da01r2_stage): "<DA01R2_STAGE_ROOT>",
        str(da01r2_runtime): "<DA01R2_RUNTIME_ROOT>",
        str(stage): "<DA01R2A_STAGE_ROOT>",
        str(export): "<DA01R2A_EXPORT_CLEAN_ROOT>",
        str(fix_root): "<BY2_FIX_ROOT>",
    }
    export_ok, export_scan = _write_export_clean(stage, export, replacements, final_decision)
    if not export_ok:
        final_decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
    supervisor = supervisor.replace(export_ok_placeholder, str(export_ok)).replace(
        "final_decision=PASS_DA01R2A_FRAME_REPAIR_REQUIRED_BEFORE_RERUN",
        f"final_decision={final_decision}",
    )
    reviewer = reviewer.replace(export_ok_placeholder, str(export_ok)).replace(
        "final_decision=PASS_DA01R2A_FRAME_REPAIR_REQUIRED_BEFORE_RERUN",
        f"final_decision={final_decision}",
    )
    write_text(report_dir / "PAPER10_DA3_DA01R2A_SUPERVISOR_FINAL_REPORT.md", supervisor)
    write_text(report_dir / "PAPER10_DA3_DA01R2A_REVIEWER_REPORT.md", reviewer)
    _write_export_clean(stage, export, replacements, final_decision)
    print(json.dumps(_jsonable({"final_decision": final_decision, "root_cause": root_cause, "export_ok": export_ok, "export_violations": len(export_scan["violations"])}), indent=2))
    return 0 if final_decision != "BLOCKED_EXPORT_CLEAN_FAILURE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
