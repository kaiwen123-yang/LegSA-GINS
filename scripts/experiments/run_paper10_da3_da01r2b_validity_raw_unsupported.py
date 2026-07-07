#!/usr/bin/env python3
"""Run DA01R2B implementation-validity and BY2 raw ambiguity-boundary proof."""

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

from legsa_gins.da_repro.common import write_csv, write_json, write_text
from legsa_gins.da_repro.dd_design_matrix import build_dd_design_epochs
from legsa_gins.da_repro.real_raw_failure_diag import diagnose_real_raw_failure
from legsa_gins.da_repro.receiver_position import choose_receiver_approx_positions
from legsa_gins.da_repro.rinex_nav_satpos import build_gps_l1_los_epochs
from legsa_gins.da_repro.rtklib_independent_check import parse_rtklib_pos, summarize_rtklib_rows
from legsa_gins.da_repro.semisynthetic_by2_geometry_validation import (
    load_status_vectors_from_orientation_table,
    run_semisynthetic_validation,
)
from legsa_gins.da_repro.synthetic_clambda_validation import validate_synthetic_suite
from legsa_gins.da_repro.synthetic_dd_generator import generate_synthetic_suite, synthetic_test_case_rows


STAGE_NAME = "PAPER10_DA3_DA01R2B_IMPLEMENTATION_VALIDITY_AND_BY2_RAW_AMBIGUITY_UNSUPPORTED_PROOF"
FORBIDDEN_TOKENS = (
    "by2.txt",
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    "trace_vrtk2",
    "epoch_output.csv",
)
FORBIDDEN_SUFFIXES = (".ubx", ".obs", ".nav", ".pdf", ".png", ".tar", ".zst")


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


def _sanitize(text: str, replacements: dict[str, str]) -> str:
    out = text
    for actual, alias in replacements.items():
        if actual:
            out = out.replace(actual, alias)
    out = re.sub("/" + "mnt" + r"/[A-Za-z]/[^\s,;)]+", "<LOCAL_PATH>", out)
    out = re.sub("/" + "home" + r"/[^\s,;)]+", "<LOCAL_PATH>", out)
    for token in FORBIDDEN_TOKENS:
        out = out.replace(token, "<OMITTED_PAYLOAD>")
    return out


def _write_export_clean(
    *,
    stage_root: Path,
    export_root: Path,
    replacements: dict[str, str],
    final_decision: str,
) -> tuple[bool, dict[str, Any]]:
    if export_root.exists():
        shutil.rmtree(export_root)
    package = export_root / "package"
    package.mkdir(parents=True, exist_ok=True)
    include_dirs = [
        "00_STAGE_REPORT",
        "01_CONTEXT",
        "02_SYNTHETIC_VALIDATION",
        "03_SEMISYNTHETIC_BY2",
        "04_REAL_BY2_RAW_DIAG",
        "05_RTKLIB_INDEPENDENT",
        "06_DECISION",
        "07_CLAIM_BOUNDARY",
    ]
    manifest: list[dict[str, Any]] = []
    for dirname in include_dirs:
        root = stage_root / dirname
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
    readme = (
        "# DA01R2B Export-Clean Pack\n\n"
        f"stage={STAGE_NAME}\n\n"
        f"final_decision={final_decision}\n\n"
        "This package contains reports, synthetic/semi-synthetic summaries, real raw diagnostics, RTKLIB diagnostics, "
        "decision docs, and claim-boundary docs. Raw receiver payloads, epoch payloads, RINEX, RTKLIB source, figures, "
        "and local path locks are omitted.\n"
    )
    (package / "README_FOR_NEXT_AI.md").write_text(readme, encoding="utf-8")
    manifest.append({"relative_path": "README_FOR_NEXT_AI.md", "bytes": len(readme.encode("utf-8")), "included": True})
    scan: dict[str, Any] = {"files_scanned": 0, "violations": [], "final_decision": final_decision}
    local_path_pattern = "/" + "mnt" + r"/[A-Za-z]/|" + "/" + "home" + "/"
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        scan["files_scanned"] += 1
        rel = str(path.relative_to(package))
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(token in rel or token in content for token in FORBIDDEN_TOKENS):
            scan["violations"].append({"relative_path": rel, "pattern": "forbidden_payload_reference"})
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            scan["violations"].append({"relative_path": rel, "pattern": path.suffix.lower()})
        if re.search(local_path_pattern, content):
            scan["violations"].append({"relative_path": rel, "pattern": "local_absolute_path"})
    zip_path = export_root / "paper10_da3_da01r2b_validity_raw_unsupported_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in package.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(package))
    write_csv(export_root / "export_clean_manifest.csv", manifest)
    write_json(export_root / "export_clean_path_scan.json", scan)
    write_text(export_root / "README_FOR_NEXT_AI.md", readme)
    stage_export = stage_root / "10_EXPORT_CLEAN_FOR_GPT"
    stage_export.mkdir(parents=True, exist_ok=True)
    write_csv(stage_export / "export_clean_manifest.csv", manifest)
    write_json(stage_export / "export_clean_path_scan.json", scan)
    write_text(stage_export / "README_FOR_NEXT_AI.md", readme)
    (stage_export / "paper10_da3_da01r2b_validity_raw_unsupported_pack.zip").write_bytes(zip_path.read_bytes())
    return not scan["violations"], scan


def _write_context(da01r2_stage: Path, da01r2a_stage: Path, stage: Path) -> None:
    required_r2 = {
        "supervisor": da01r2_stage / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R2_SUPERVISOR_FINAL_REPORT.md",
        "physical": da01r2_stage / "03_PHYSICAL_GATE" / "DA01R2_BASELINE_PHYSICAL_GATE_BY_CASE.csv",
        "dd_provider": da01r2_stage / "03_PHYSICAL_GATE" / "DA01R2_DD_PROVIDER_BY_CASE_SUMMARY.csv",
        "row_result": da01r2_stage / "04_EVALUATION" / "DA01R2_ROW_LEVEL_RESULT_TABLE.csv",
        "method_summary": da01r2_stage / "04_EVALUATION" / "DA01R2_METHOD_LEVEL_SUMMARY.csv",
        "yaw_safety": da01r2_stage / "04_EVALUATION" / "DA01R2_YAW_FRAME_SAFETY_TABLE.csv",
        "claim_boundary": da01r2_stage / "05_CLAIM_BOUNDARY" / "DA01R2_CLAIM_BOUNDARY_FREEZE.md",
    }
    required_r2a = {
        "supervisor": da01r2a_stage / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R2A_SUPERVISOR_FINAL_REPORT.md",
        "status": da01r2a_stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_ORIENTATION_TABLE.csv",
        "raw_status": da01r2a_stage / "03_RAW_BASELINE" / "RAW_VS_STATUS_BASELINE_ORIENTATION_SUMMARY.csv",
        "transform": da01r2a_stage / "04_TRANSFORM_AUDIT" / "TRANSFORM_VS_STATUS_SUMMARY.csv",
        "decision": da01r2a_stage / "05_DECISION" / "DA01R2A_ORIENTATION_ROOT_CAUSE_DECISION.md",
        "next_action": da01r2a_stage / "05_DECISION" / "NEXT_ACTION_DECISION.md",
    }
    method_summary = _read_csv(required_r2["method_summary"])
    raw_status_summary = _read_csv(required_r2a["raw_status"])
    global_raw = next((row for row in raw_status_summary if row.get("case_id") == "GLOBAL"), {})
    write_text(
        stage / "01_CONTEXT" / "DA01R2B_UPSTREAM_REVIEW.md",
        "# DA01R2B Upstream Review\n\n"
        "Read status:\n"
        + "\n".join(f"- DA01R2 {name}: {path.exists()}" for name, path in required_r2.items())
        + "\n"
        + "\n".join(f"- DA01R2A {name}: {path.exists()}" for name, path in required_r2a.items())
        + "\n\nKey inherited facts:\n"
        f"- DA01R2 method summary first row: {json.dumps(method_summary[:1], ensure_ascii=False)}\n"
        f"- DA01R2A global raw/status summary: {json.dumps(global_raw, ensure_ascii=False)}\n"
        "- DA01R2 completed the 18 classic full_backend cases but had poor yaw.\n"
        "- DA01R2A already excluded no-wrap, missing lateral conversion, simple receiver reversal, fixed ENU/NED, trace sign selection, and per-case offset as sufficient explanations.\n",
    )
    write_text(
        stage / "01_CONTEXT" / "DA01R2B_PROOF_OBJECTIVE.md",
        "# DA01R2B Proof Objective\n\n"
        "- This stage is not a performance repair and is not trying to make DA01 yaw better.\n"
        "- This stage validates whether the implementation and geometry definitions are internally rigorous.\n"
        "- If synthetic and semi-synthetic validations pass while real BY2 raw remains direction-unstable, the allowed conclusion is an applicability boundary for DA01/C-LAMBDA-style methods under BY2 raw-carrier short-baseline dynamic conditions.\n"
        "- If synthetic or semi-synthetic validation fails, the conclusion must be code/frame bug indicated; external-method unsuitability cannot be claimed.\n"
        "- Trace is not used to choose sign/offset, no per-case offset is allowed, and status baseline is not substituted as the real DA01 full_backend output.\n",
    )


def _build_design_epochs(fix_root: Path, rinex_root: Path, max_epochs: int | None) -> tuple[list[dict[str, Any]], dict[str, Any], Any]:
    positions, position_candidates = choose_receiver_approx_positions(
        gnss1_obs=rinex_root / "gnss1.obs",
        gnss2_obs=rinex_root / "gnss2.obs",
        gnss1_status=fix_root / "gnss1-status.csv",
        gnss2_status=fix_root / "gnss2-status.csv",
    )
    los_report = build_gps_l1_los_epochs(
        gnss1_raw=fix_root / "gnss1-raw.csv",
        gnss2_raw=fix_root / "gnss2-raw.csv",
        nav_path=rinex_root / "gnss1.nav",
        receiver_positions=positions,
        max_epochs=max_epochs,
    )
    design_epochs = build_dd_design_epochs(los_report["epochs"])
    context = {
        "receiver_position_candidates": position_candidates,
        "los_provider": {key: value for key, value in los_report.items() if key != "epochs"},
        "design_epoch_count": len(design_epochs),
        "trace_used": False,
        "per_case_offset": False,
    }
    return design_epochs, context, positions["gnss1"]


def _write_synthetic(stage: Path) -> dict[str, Any]:
    cases = generate_synthetic_suite()
    validation_rows, summary = validate_synthetic_suite(cases)
    write_csv(stage / "02_SYNTHETIC_VALIDATION" / "SYNTHETIC_DD_TEST_CASES.csv", synthetic_test_case_rows(cases))
    write_csv(stage / "02_SYNTHETIC_VALIDATION" / "SYNTHETIC_SOLVER_VALIDATION_RESULT.csv", validation_rows + [{"case_id": "SUMMARY", **summary}])
    write_text(
        stage / "02_SYNTHETIC_VALIDATION" / "SYNTHETIC_YAW_FRAME_VALIDATION.md",
        "# Synthetic Yaw-Frame Validation\n\n"
        f"- validation_pass: {summary['synthetic_validation_pass']}\n"
        f"- max_length_error_m: {summary['max_length_error_m']}\n"
        f"- max_noise_free_direction_error_deg: {summary['max_noise_free_direction_error_deg']}\n"
        f"- max_noise_free_yaw_abs_error_deg: {summary['max_noise_free_yaw_abs_error_deg']}\n"
        f"- wrap_179_minus179_pass: {summary['wrap_179_minus179_pass']}\n"
        f"- swap_180_pass: {summary['swap_180_pass']}\n"
        f"- lateral_plus90_pass: {summary['lateral_plus90_pass']}\n"
        "- trace_used: false\n",
    )
    return summary


def _write_semisynthetic(
    *,
    stage: Path,
    da01r2a_stage: Path,
    fix_root: Path,
    rinex_root: Path,
    max_epochs: int | None,
) -> dict[str, Any]:
    status_vectors = load_status_vectors_from_orientation_table(
        str(da01r2a_stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_ORIENTATION_TABLE.csv")
    )
    design_epochs, context, receiver1 = _build_design_epochs(fix_root, rinex_root, max_epochs)
    rows, summary = run_semisynthetic_validation(
        design_epochs=design_epochs,
        status_vectors=status_vectors,
        receiver_lat_deg=receiver1.lat_deg,
        receiver_lon_deg=receiver1.lon_deg,
        max_epochs=max_epochs,
    )
    write_csv(stage / "03_SEMISYNTHETIC_BY2" / "SEMISYNTHETIC_BY2_GEOMETRY_VALIDATION.csv", rows)
    write_csv(stage / "03_SEMISYNTHETIC_BY2" / "SEMISYNTHETIC_BY2_METHOD_LEVEL_SUMMARY.csv", [{**context, **summary}])
    write_text(
        stage / "03_SEMISYNTHETIC_BY2" / "SEMISYNTHETIC_BY2_YAW_FRAME_REPORT.md",
        "# Semi-Synthetic BY2 Geometry Yaw-Frame Report\n\n"
        f"- validation_pass: {summary['semisynthetic_validation_pass']}\n"
        f"- usable_epochs: {summary['usable_epochs']}\n"
        f"- median_recovered_baseline_length_m: {summary['median_recovered_baseline_length_m']}\n"
        f"- median_baseline_vs_status_angle_deg: {summary['median_baseline_vs_status_angle_deg']}\n"
        f"- body_yaw_vs_status_rmse_deg: {summary['body_yaw_vs_status_rmse_deg']}\n"
        "- trace_used: false\n"
        "- per_case_offset: false\n"
        "- status_used_as_real_full_backend_output: false\n",
    )
    return summary


def _write_real_raw(stage: Path, da01r2a_stage: Path, da01r2_runtime: Path) -> dict[str, Any]:
    status_vectors = load_status_vectors_from_orientation_table(
        str(da01r2a_stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_ORIENTATION_TABLE.csv")
    )
    summary_rows, epoch_rows, ambiguity_rows, global_summary = diagnose_real_raw_failure(
        runtime_root=da01r2_runtime,
        status_vectors=status_vectors,
    )
    write_csv(stage / "04_REAL_BY2_RAW_DIAG" / "REAL_BY2_RAW_FAILURE_DIAGNOSTICS.csv", summary_rows + [{"case_id": "GLOBAL", **global_summary}])
    write_csv(stage / "04_REAL_BY2_RAW_DIAG" / "RAW_STATUS_DIRECTION_INSTABILITY_BY_EPOCH.csv", epoch_rows)
    write_csv(stage / "04_REAL_BY2_RAW_DIAG" / "AMBIGUITY_AND_RATIO_SUMMARY.csv", ambiguity_rows)
    write_text(
        stage / "04_REAL_BY2_RAW_DIAG" / "REAL_RAW_FAILURE_EXPLANATION.md",
        "# Real BY2 Raw Failure Explanation\n\n"
        f"- raw_direction_unstable: {global_summary['raw_direction_unstable']}\n"
        f"- global_median_vector_angle_diff_deg: {global_summary['global_median_vector_angle_diff_deg']}\n"
        f"- global_p95_vector_angle_diff_deg: {global_summary['global_p95_vector_angle_diff_deg']}\n"
        f"- yaw_error_correlation_with_provider_angle: {global_summary['yaw_error_correlation_with_median_angle']}\n"
        "- implementation_fails: false, conditional on synthetic and semi-synthetic validation passing.\n"
        "- frame_fails: false, conditional on synthetic and semi-synthetic yaw-frame validation passing.\n"
        "- by2_raw_ambiguity_unsupported: supported when synthetic/semi-synthetic pass and real raw remains direction-unstable.\n"
        "- real_raw_poor_geometry_dynamic_short_baseline_sensitivity: supported as a bounded diagnostic explanation.\n"
        "- unknown: false when required diagnostics are present; unavailable C/N0 and lock fields remain diagnostic gaps, not solver inputs.\n",
    )
    return global_summary


def _write_rtklib(stage: Path, da01r2a_stage: Path, rtklib_pos: list[str]) -> dict[str, Any]:
    status_vectors = load_status_vectors_from_orientation_table(
        str(da01r2a_stage / "02_STATUS_BASELINE" / "STATUS_BASELINE_ORIENTATION_TABLE.csv")
    )
    rows_out: list[dict[str, Any]] = []
    summary_out: list[dict[str, Any]] = []
    if not rtklib_pos:
        summary = {
            "solution_id": "rtklib_not_available",
            "usable_epochs": 0,
            "rtklib_status": "blocked_not_available",
            "baseline_direction_stable": None,
            "rtklib_also_fails_to_stabilize_heading": None,
            "used_as_solver_input": False,
        }
        summary_out.append(summary)
    else:
        for index, pos_path in enumerate(rtklib_pos):
            solution_id = f"rtklib_solution_{index}"
            rows = parse_rtklib_pos(pos_path, solution_id=solution_id)
            rows_out.extend(rows[:5000])
            summary = summarize_rtklib_rows(rows, status_vectors=status_vectors) if rows else {
                "usable_epochs": 0,
                "rtklib_status": "blocked_empty_or_missing",
                "baseline_direction_stable": None,
                "rtklib_also_fails_to_stabilize_heading": None,
                "used_as_solver_input": False,
            }
            summary_out.append({"solution_id": solution_id, "input_path_alias": f"<RTKLIB_POS_{index}>", **summary})
    write_csv(stage / "05_RTKLIB_INDEPENDENT" / "RTKLIB_MOVING_BASE_INDEPENDENT_CHECK.csv", rows_out if rows_out else summary_out)
    write_csv(stage / "05_RTKLIB_INDEPENDENT" / "RTKLIB_VS_STATUS_DIRECTION_SUMMARY.csv", summary_out)
    any_stable = any(row.get("baseline_direction_stable") is True and row.get("direction_matches_status") is True for row in summary_out)
    any_unstable = any(row.get("rtklib_also_fails_to_stabilize_heading") is True for row in summary_out)
    conclusion = "rtklib_not_contradicting"
    if any_stable:
        conclusion = "rtklib_succeeds_our_provider_bug_indicated"
    elif any_unstable:
        conclusion = "rtklib_also_unstable_supports_boundary"
    write_text(
        stage / "05_RTKLIB_INDEPENDENT" / "RTKLIB_DIAGNOSTIC_CONCLUSION.md",
        "# RTKLIB Diagnostic Conclusion\n\n"
        f"- conclusion: {conclusion}\n"
        "- RTKLIB output is independent diagnostic only and is not used as DA01 solver input.\n"
        "- trace_used: false\n"
        "- final_v23_used: false\n"
        "- LegSA_used: false\n"
        "- If RTKLIB succeeds and our provider fails, the decision must be provider-bug indicated; otherwise RTKLIB is non-contradicting support.\n",
    )
    return {
        "rtklib_conclusion": conclusion,
        "rtklib_succeeds_against_status": any_stable,
        "rtklib_also_unstable": any_unstable,
        "rtklib_rows": sum(int(row.get("usable_epochs") or 0) for row in summary_out),
    }


def _decision(
    synthetic: dict[str, Any],
    semisynthetic: dict[str, Any],
    real_raw: dict[str, Any],
    rtklib: dict[str, Any],
) -> str:
    if not synthetic.get("synthetic_validation_pass"):
        return "BLOCKED_DA01R2B_SYNTHETIC_SOLVER_OR_YAW_FRAME_FAILS"
    if not semisynthetic.get("semisynthetic_validation_pass"):
        return "BLOCKED_DA01R2B_SEMISYNTHETIC_BY2_GEOMETRY_OR_FRAME_FAILS"
    if rtklib.get("rtklib_succeeds_against_status"):
        return "BLOCKED_DA01R2B_RTKLIB_SUCCEEDS_OUR_PROVIDER_FAILS"
    if real_raw.get("raw_direction_unstable"):
        return "PASS_DA01R2B_CODE_VALIDATED_REAL_BY2_RAW_UNSUPPORTED"
    return "BLOCKED_DA01R2B_INCONCLUSIVE_NEEDS_MORE_DATA"


def _write_decision_and_claims(
    *,
    stage: Path,
    final_decision: str,
    synthetic: dict[str, Any],
    semisynthetic: dict[str, Any],
    real_raw: dict[str, Any],
    rtklib: dict[str, Any],
) -> None:
    decision_class = {
        "PASS_DA01R2B_CODE_VALIDATED_REAL_BY2_RAW_UNSUPPORTED": "CODE_AND_FRAME_VALIDATED_REAL_BY2_RAW_UNSUPPORTED",
        "BLOCKED_DA01R2B_RTKLIB_SUCCEEDS_OUR_PROVIDER_FAILS": "OUR_PROVIDER_BUG_INDICATED",
        "BLOCKED_DA01R2B_SYNTHETIC_SOLVER_OR_YAW_FRAME_FAILS": "CODE_OR_FRAME_BUG_INDICATED",
        "BLOCKED_DA01R2B_SEMISYNTHETIC_BY2_GEOMETRY_OR_FRAME_FAILS": "CODE_OR_FRAME_BUG_INDICATED",
    }.get(final_decision, "INCONCLUSIVE_NEEDS_MORE_DATA")
    write_text(
        stage / "06_DECISION" / "DA01R2B_SOURCE_LINEAGE_DECISION.md",
        "# DA01R2B Source-Lineage Decision\n\n"
        f"decision_class={decision_class}\n"
        f"final_decision={final_decision}\n\n"
        f"- synthetic_pass: {synthetic.get('synthetic_validation_pass')}\n"
        f"- semisynthetic_pass: {semisynthetic.get('semisynthetic_validation_pass')}\n"
        f"- real_raw_direction_unstable: {real_raw.get('raw_direction_unstable')}\n"
        f"- rtklib_conclusion: {rtklib.get('rtklib_conclusion')}\n"
        "- trace_used_for_sign_or_offset: false\n"
        "- per_case_offset: false\n"
        "- status_baseline_used_as_real_full_backend: false\n",
    )
    can_write = final_decision == "PASS_DA01R2B_CODE_VALIDATED_REAL_BY2_RAW_UNSUPPORTED"
    write_text(
        stage / "06_DECISION" / "DA01R2B_CAN_WE_WRITE_POOR_PERFORMANCE.md",
        "# Can We Write Poor Performance?\n\n"
        f"can_write_bounded_applicability_boundary={can_write}\n\n"
        "Allowed only if synthetic and semi-synthetic validations pass and real BY2 raw remains direction-unstable without RTKLIB contradiction. "
        "This is not a claim of DA01 exact reproduction, DA01 good performance, or universal superiority.\n",
    )
    write_text(
        stage / "06_DECISION" / "DA01R2B_NEXT_ACTION.md",
        "# DA01R2B Next Action\n\n"
        "- do not rerun DA01R2 18-case matrix in this stage\n"
        "- do not enter DA03 from this task\n"
        "- if decision is pass, freeze claim boundary and carry bounded wording only\n"
        "- if blocked, repair code/provider first and do not write external-method unsupported claims\n"
        f"- final_decision={final_decision}\n",
    )
    write_csv(
        stage / "07_CLAIM_BOUNDARY" / "DA01R2B_ALLOWED_CLAIMS.csv",
        [
            {
                "claim": "DA01 implementation and yaw-frame were validated on synthetic and semi-synthetic BY2 geometry.",
                "allowed": can_write,
            },
            {
                "claim": "Real BY2 raw-carrier data leads to unstable baseline direction under DA01/C-LAMBDA-style full backend.",
                "allowed": can_write,
            },
            {
                "claim": "General GNSS compass/C-LAMBDA-style methods face a caveated applicability boundary on BY2 short-baseline lateral legged robot data.",
                "allowed": can_write,
            },
        ],
    )
    write_csv(
        stage / "07_CLAIM_BOUNDARY" / "DA01R2B_DIAGNOSTIC_ONLY_CLAIMS.csv",
        [
            {"claim": "RTKLIB moving-base output is an independent diagnostic only.", "diagnostic_only": True},
            {"claim": "Unavailable C/N0 or lock indicators remain diagnostic gaps.", "diagnostic_only": True},
            {"claim": "Status baseline is known truth only for semi-synthetic validation, not a real DA01 output.", "diagnostic_only": True},
        ],
    )
    write_text(
        stage / "07_CLAIM_BOUNDARY" / "DA01R2B_FORBIDDEN_CLAIMS.md",
        "# DA01R2B Forbidden Claims\n\n"
        "- DA01 exact reproduction\n"
        "- DA01 performance is good\n"
        "- all external algorithms fail\n"
        "- LegSA beats all external methods\n"
        "- trace-tuned sign\n"
        "- per-case offset\n"
        "- status baseline used as real full_backend\n"
        "- universal superiority\n",
    )
    write_text(
        stage / "07_CLAIM_BOUNDARY" / "DA01R2B_CLAIM_BOUNDARY_FREEZE.md",
        "# DA01R2B Claim Boundary Freeze\n\n"
        f"final_decision={final_decision}\n\n"
        "This evidence validates DA01R2B implementation/yaw-frame behavior on controlled synthetic and semi-synthetic BY2 geometry when those gates pass. "
        "It supports only a caveated BY2 raw-carrier applicability boundary when real raw baseline direction remains unstable. "
        "It does not authorize exact reproduction, superiority, trace tuning, per-case offsets, or status-as-full_backend claims.\n",
    )


def _write_stage_reports(
    *,
    stage: Path,
    final_decision: str,
    synthetic: dict[str, Any],
    semisynthetic: dict[str, Any],
    real_raw: dict[str, Any],
    rtklib: dict[str, Any],
    export_ok: bool | str,
    commit_status: str,
) -> None:
    supervisor = f"""# PAPER10 DA3 DA01R2B Supervisor Final Report

1. yaw repair objective: no
2. implementation rigor proof objective: yes
3. synthetic validation passed: {synthetic.get('synthetic_validation_pass')}
4. semi-synthetic BY2 geometry validation passed: {semisynthetic.get('semisynthetic_validation_pass')}
5. real BY2 raw instability: median vector angle diff={real_raw.get('global_median_vector_angle_diff_deg')}, p95={real_raw.get('global_p95_vector_angle_diff_deg')}; direction_unstable={real_raw.get('raw_direction_unstable')}
6. RTKLIB independent check: {rtklib.get('rtklib_conclusion')}; rows={rtklib.get('rtklib_rows')}
7. DA01R2 large yaw due to missing wrap: no
8. due to missing lateral conversion: no
9. due to trace sign selection: no
10. due to per-case offset: no
11. due to our code/geometry bug: no if synthetic and semi-synthetic pass; otherwise blocked
12. can write BY2 applicability boundary: {final_decision == 'PASS_DA01R2B_CODE_VALIDATED_REAL_BY2_RAW_UNSUPPORTED'}
13. need rerun DA01R2: no for this proof stage
14. can enter DA03: no
15. claim boundary: frozen in 07_CLAIM_BOUNDARY
16. tests: run by requested pytest command after generation
17. export-clean: {export_ok}
18. commit/push status: {commit_status}

final_decision={final_decision}
"""
    reviewer = f"""# PAPER10 DA3 DA01R2B Reviewer Report

- no DA03, no DA01R2 18-case rerun, no 120-case.
- synthetic validation gate: {synthetic.get('synthetic_validation_pass')}
- semi-synthetic validation gate: {semisynthetic.get('semisynthetic_validation_pass')}
- real raw direction unstable: {real_raw.get('raw_direction_unstable')}
- RTKLIB contradiction: {rtklib.get('rtklib_succeeds_against_status')}
- trace sign/offset selection: false
- per-case offset: false
- status baseline as real full_backend: false
- export-clean: {export_ok}
- final_decision={final_decision}
"""
    write_text(stage / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R2B_SUPERVISOR_FINAL_REPORT.md", supervisor)
    write_text(stage / "00_STAGE_REPORT" / "PAPER10_DA3_DA01R2B_REVIEWER_REPORT.md", reviewer)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--da01r2-stage-root", required=True)
    parser.add_argument("--da01r2a-stage-root", required=True)
    parser.add_argument("--da01r2-runtime-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--rinex-root", required=True)
    parser.add_argument("--rtklib-pos", action="append", default=[])
    parser.add_argument("--semisynthetic-max-epochs", type=int, default=1500)
    parser.add_argument("--commit-status", default="pending")
    args = parser.parse_args(argv)

    da01r2_stage = Path(args.da01r2_stage_root)
    da01r2a_stage = Path(args.da01r2a_stage_root)
    da01r2_runtime = Path(args.da01r2_runtime_root)
    stage = Path(args.stage_root)
    runtime = Path(args.runtime_root)
    export = Path(args.export_root)
    fix_root = Path(args.fix_root)
    rinex_root = Path(args.rinex_root)
    stage.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)

    _write_context(da01r2_stage, da01r2a_stage, stage)
    synthetic = _write_synthetic(stage)
    if not synthetic.get("synthetic_validation_pass"):
        semisynthetic = {"semisynthetic_validation_pass": False}
        real_raw = {"raw_direction_unstable": None}
        rtklib = {"rtklib_conclusion": "not_run_after_synthetic_block"}
        final_decision = "BLOCKED_DA01R2B_SYNTHETIC_SOLVER_OR_YAW_FRAME_FAILS"
    else:
        semisynthetic = _write_semisynthetic(
            stage=stage,
            da01r2a_stage=da01r2a_stage,
            fix_root=fix_root,
            rinex_root=rinex_root,
            max_epochs=args.semisynthetic_max_epochs,
        )
        if not semisynthetic.get("semisynthetic_validation_pass"):
            real_raw = {"raw_direction_unstable": None}
            rtklib = {"rtklib_conclusion": "not_run_after_semisynthetic_block"}
            final_decision = "BLOCKED_DA01R2B_SEMISYNTHETIC_BY2_GEOMETRY_OR_FRAME_FAILS"
        else:
            real_raw = _write_real_raw(stage, da01r2a_stage, da01r2_runtime)
            rtklib = _write_rtklib(stage, da01r2a_stage, list(args.rtklib_pos))
            final_decision = _decision(synthetic, semisynthetic, real_raw, rtklib)
    _write_decision_and_claims(
        stage=stage,
        final_decision=final_decision,
        synthetic=synthetic,
        semisynthetic=semisynthetic,
        real_raw=real_raw,
        rtklib=rtklib,
    )
    _write_stage_reports(
        stage=stage,
        final_decision=final_decision,
        synthetic=synthetic,
        semisynthetic=semisynthetic,
        real_raw=real_raw,
        rtklib=rtklib,
        export_ok="pending",
        commit_status=args.commit_status,
    )
    replacements = {
        str(da01r2_stage): "<DA01R2_STAGE_ROOT>",
        str(da01r2a_stage): "<DA01R2A_STAGE_ROOT>",
        str(da01r2_runtime): "<DA01R2_RUNTIME_ROOT>",
        str(stage): "<DA01R2B_STAGE_ROOT>",
        str(runtime): "<DA01R2B_RUNTIME_ROOT>",
        str(export): "<DA01R2B_EXPORT_CLEAN_ROOT>",
        str(fix_root): "<BY2_FIX_ROOT>",
        str(rinex_root): "<BY2_RINEX_ROOT>",
    }
    for index, path in enumerate(args.rtklib_pos):
        replacements[str(Path(path))] = f"<RTKLIB_POS_{index}>"
    export_ok, export_scan = _write_export_clean(
        stage_root=stage,
        export_root=export,
        replacements=replacements,
        final_decision=final_decision,
    )
    if not export_ok:
        final_decision = "BLOCKED_EXPORT_CLEAN_FAILURE"
        _write_decision_and_claims(
            stage=stage,
            final_decision=final_decision,
            synthetic=synthetic,
            semisynthetic=semisynthetic,
            real_raw=real_raw,
            rtklib=rtklib,
        )
        _write_stage_reports(
            stage=stage,
            final_decision=final_decision,
            synthetic=synthetic,
            semisynthetic=semisynthetic,
            real_raw=real_raw,
            rtklib=rtklib,
            export_ok=export_ok,
            commit_status=args.commit_status,
        )
        _write_export_clean(stage_root=stage, export_root=export, replacements=replacements, final_decision=final_decision)
    else:
        _write_stage_reports(
            stage=stage,
            final_decision=final_decision,
            synthetic=synthetic,
            semisynthetic=semisynthetic,
            real_raw=real_raw,
            rtklib=rtklib,
            export_ok=export_ok,
            commit_status=args.commit_status,
        )
        _write_export_clean(stage_root=stage, export_root=export, replacements=replacements, final_decision=final_decision)
    print(
        json.dumps(
            _jsonable(
                {
                    "final_decision": final_decision,
                    "synthetic_pass": synthetic.get("synthetic_validation_pass"),
                    "semisynthetic_pass": semisynthetic.get("semisynthetic_validation_pass"),
                    "real_raw_direction_unstable": real_raw.get("raw_direction_unstable"),
                    "rtklib_conclusion": rtklib.get("rtklib_conclusion"),
                    "export_ok": export_ok,
                    "export_violations": len(export_scan.get("violations", [])),
                }
            ),
            indent=2,
        )
    )
    return 0 if final_decision == "PASS_DA01R2B_CODE_VALIDATED_REAL_BY2_RAW_UNSUPPORTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
