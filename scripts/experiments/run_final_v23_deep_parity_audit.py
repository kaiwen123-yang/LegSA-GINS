#!/usr/bin/env python3
"""Run N4H2C final_v23 deep input/source/framework parity audit.

中文说明：runner 只读取 runtime input、N4H2 artifacts 和外部 KF-GINS 源码证据；
输出写到用户指定目录，不提交 raw data，不复制外部源码，不使用 trace 作为 solver input。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.final_v23_input_diff import (  # noqa: E402
    compare_actual_final_v23_summary,
    compute_gnss_input_diff,
    parse_15col_gnss,
)
from legsa_gins.evaluation.kfgins_framework_parity import (  # noqa: E402
    compare_legsa_to_kfgins_framework,
)
from legsa_gins.source_audit.final_v23_deep_source_audit import (  # noqa: E402
    audit_gnss_loader_and_engine_source,
    audit_kfgins_core_flow,
    probe_final_v23_case_root,
    search_process_data_and_run_scripts,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _line_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def _probe_artifacts_root(root: Path) -> dict[str, Any]:
    expected = [
        "inputs/BY2_PROCESS_DATA_COMPAT.gnss",
        "inputs/BY2_PROCESS_DATA_COMPAT.imu",
        "replay/N4H2_REPLAY_REPORT.json",
        "replay/evaluation/FINAL_V23_TRACE_EVAL_SUMMARY.json",
        "replay/standardized/RUN_MANIFEST.json",
    ]
    files = {}
    for rel_path in expected:
        path = root / rel_path
        files[rel_path] = {
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "line_count": _line_count(path),
        }
    return {
        "artifacts_root_exists": root.exists(),
        "files": files,
        "evidence_status": "n4h2_artifacts_probe_complete"
        if root.exists() and any(item["exists"] for item in files.values())
        else "evidence_missing",
        "raw_data_committed": False,
    }


def _find_reconstructed_gnss(root: Path) -> Path | None:
    preferred = root / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss"
    if preferred.exists():
        return preferred
    if not root.exists():
        return None
    candidates = sorted(root.rglob("BY2_PROCESS_DATA_COMPAT.gnss"))
    if candidates:
        return candidates[0]
    candidates = sorted(path for path in root.rglob("*.gnss") if path.is_file())
    return candidates[0] if candidates else None


def _find_n4h2_summary(root: Path) -> Path | None:
    candidates = [
        root / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json",
        root / "replay" / "N4H2_REPLAY_REPORT.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = sorted(root.rglob("*SUMMARY*.json")) if root.exists() else []
    return found[0] if found else None


def _metric_from_nested(data: dict[str, Any] | None, field: str) -> float | None:
    if not data:
        return None
    stack: list[Any] = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key == field and isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return None


def _bool_from_nested(data: dict[str, Any] | None, field: str) -> bool | None:
    if not data:
        return None
    stack: list[Any] = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key == field and isinstance(value, bool):
                    return value
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return None


def _engine_lacks_runtime_yaw_velocity(engine_audit: dict[str, Any]) -> bool:
    columns = engine_audit.get("gnss_loader_columns_supported", {})
    return not (
        columns.get("fifteen_column_runtime_input")
        and engine_audit.get("uses_velocity_update")
        and engine_audit.get("uses_yaw_update")
    )


def _make_decision(
    *,
    case_probe: dict[str, Any],
    reconstructed_input_exists: bool,
    input_diff: dict[str, Any],
    engine_audit: dict[str, Any],
    framework_parity: dict[str, Any],
    n4h2_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    actual_input_exists = bool(case_probe.get("actual_input_gnss_exists"))
    replay_yaw = _metric_from_nested(n4h2_summary, "yaw_rmse_deg")
    replay_yaw_gate_pass = replay_yaw is not None and replay_yaw <= 2.0
    input_status = input_diff.get("input_diff_status")
    blocking: list[str] = []
    if not actual_input_exists:
        recommended = "N4H2C_actual_input_artifact_recovery_or_run_script_audit"
        blocking.append("actual_final_v23_input_missing")
    elif not reconstructed_input_exists:
        recommended = "N4H2C_actual_input_artifact_recovery_or_run_script_audit"
        blocking.append("reconstructed_input_missing")
    elif input_status == "input_position_matched_but_yaw_mismatch":
        recommended = "N4H2C_yaw_input_config_fix"
    elif input_status == "yaw_input_matched" and not replay_yaw_gate_pass:
        recommended = "N4H2C_runtime_yaw_update_config_audit"
    elif input_status == "yaw_input_matched" and replay_yaw_gate_pass:
        recommended = "N4H_full_kfgins_style_ekf_reconstruction"
    elif _engine_lacks_runtime_yaw_velocity(engine_audit):
        recommended = "N4H2C_runtime_source_branch_parity_audit"
    else:
        recommended = "N4H2C_runtime_yaw_update_config_audit"

    framework_missing = framework_parity.get("missing_in_legsa", [])
    return {
        "phase": "N4H2C",
        "actual_input_gnss_exists": actual_input_exists,
        "reconstructed_input_gnss_exists": reconstructed_input_exists,
        "input_diff_status": input_status,
        "position_diff_rmse_m": input_diff.get("position_diff_rmse_m"),
        "height_diff_rmse_m": input_diff.get("height_diff_rmse_m"),
        "velocity_diff_rmse_mps": input_diff.get("velocity_diff_rmse_mps"),
        "yaw_diff_rmse_deg": input_diff.get("yaw_diff_rmse_deg"),
        "yaw_diff_mean_deg": input_diff.get("yaw_diff_mean_deg"),
        "yaw_std_diff_mean_deg": input_diff.get("yaw_std_diff_mean_deg"),
        "n4h2_replay_yaw_rmse_deg": replay_yaw,
        "n4h2_replay_yaw_gate_pass": replay_yaw_gate_pass,
        "engine_uses_velocity_update": engine_audit.get("uses_velocity_update"),
        "engine_uses_yaw_update": engine_audit.get("uses_yaw_update"),
        "legsa_framework_missing_items": framework_missing,
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "trace_solver_input": False,
        "final_v23_is_proposed": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_data_committed": False,
        "numerical_performance_claim": False,
        "claim_boundary": "no formal performance claim; diagnostic source/input/runtime audit only",
        "framework_gap_note": "Do not start full EKF reconstruction until input/yaw parity is resolved.",
    }


def _role_path(path: Path | None, role: str) -> str:
    return role if path is not None and path.exists() else f"{role} missing"


def _write_case_review(
    path: Path,
    *,
    actual_input: Path | None,
    reconstructed_input: Path | None,
    case_probe: dict[str, Any],
    input_diff: dict[str, Any],
    process_audit: dict[str, Any],
    engine_audit: dict[str, Any],
    framework_parity: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    process_path = process_audit.get("process_data_path")
    run_count = len(process_audit.get("run_script_candidates", []))
    config_count = len(process_audit.get("config_candidates", []))
    lines = [
        "# N4H2C Yaw Config Parity Case Review",
        "",
        "## Runtime Inputs",
        "",
        f"- actual input.gnss: {_role_path(actual_input, 'ACTUAL_FINAL_V23_CASE_ROOT/input.gnss')}",
        f"- reconstructed input.gnss: {_role_path(reconstructed_input, 'N4H2_ARTIFACTS_ROOT/inputs/BY2_PROCESS_DATA_COMPAT.gnss')}",
        f"- final_v23 case probe status: {case_probe.get('evidence_status')}",
        "",
        "## Input Diff",
        "",
        f"- input_diff_status: {input_diff.get('input_diff_status')}",
        f"- position_diff_rmse_m: {input_diff.get('position_diff_rmse_m')}",
        f"- height_diff_rmse_m: {input_diff.get('height_diff_rmse_m')}",
        f"- velocity_diff_rmse_mps: {input_diff.get('velocity_diff_rmse_mps')}",
        f"- yaw_diff_rmse_deg: {input_diff.get('yaw_diff_rmse_deg')}",
        f"- yaw_diff_mean_deg: {input_diff.get('yaw_diff_mean_deg')}",
        f"- yaw_std_diff_mean_deg: {input_diff.get('yaw_std_diff_mean_deg')}",
        "",
        "## Source Audit",
        "",
        f"- process_data.py: {'PROCESS_DATA_PATH_FOUND' if process_path else 'evidence_missing'}",
        f"- run script candidates: {run_count}",
        f"- config candidates: {config_count}",
        f"- engine uses velocity update: {engine_audit.get('uses_velocity_update')}",
        f"- engine uses yaw update: {engine_audit.get('uses_yaw_update')}",
        "",
        "## Framework Parity",
        "",
        f"- missing_in_legsa: {framework_parity.get('missing_in_legsa')}",
        f"- implemented_as_toy_only: {framework_parity.get('implemented_as_toy_only')}",
        "",
        "## Decision",
        "",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "- trace_solver_input=false",
        "- final_v23_is_proposed=false",
        "- no formal performance claim",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    final_root = Path(args.final_v23_case_root)
    artifacts_root = Path(args.n4h2_artifacts_root)
    external_root = Path(args.external_source_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    case_probe = probe_final_v23_case_root(final_root)
    artifacts_probe = _probe_artifacts_root(artifacts_root)
    actual_input = final_root / "input.gnss" if (final_root / "input.gnss").exists() else None
    reconstructed_input = _find_reconstructed_gnss(artifacts_root)
    input_diff: dict[str, Any] = {
        "input_diff_status": "evidence_missing",
        "trace_solver_input": False,
        "output_only_correction": False,
        "numerical_performance_claim": False,
    }
    if actual_input and reconstructed_input:
        try:
            input_diff = compute_gnss_input_diff(
                parse_15col_gnss(actual_input),
                parse_15col_gnss(reconstructed_input),
            )
        except (OSError, ValueError) as exc:
            input_diff = {
                "input_diff_status": "evidence_missing",
                "error": str(exc),
                "trace_solver_input": False,
                "output_only_correction": False,
                "numerical_performance_claim": False,
            }

    actual_summary = final_root / "summary.json"
    n4h2_summary_path = _find_n4h2_summary(artifacts_root)
    summary_diff = (
        compare_actual_final_v23_summary(actual_summary, n4h2_summary_path)
        if n4h2_summary_path
        else {"evidence_status": "evidence_missing"}
    )
    n4h2_summary = _read_json_if_exists(n4h2_summary_path) if n4h2_summary_path else None

    process_audit = search_process_data_and_run_scripts(external_root)
    engine_audit = audit_gnss_loader_and_engine_source(external_root)
    core_flow = audit_kfgins_core_flow(external_root)
    framework_parity = compare_legsa_to_kfgins_framework(core_flow, REPO_ROOT)
    decision = _make_decision(
        case_probe=case_probe,
        reconstructed_input_exists=bool(reconstructed_input),
        input_diff=input_diff,
        engine_audit=engine_audit,
        framework_parity=framework_parity,
        n4h2_summary=n4h2_summary,
    )
    decision["summary_diff"] = summary_diff
    decision["artifacts_probe_status"] = artifacts_probe.get("evidence_status")

    _write_json(out / "FINAL_V23_CASE_ROOT_PROBE.json", case_probe)
    _write_json(out / "N4H2_ARTIFACTS_ROOT_PROBE.json", artifacts_probe)
    if actual_input and reconstructed_input:
        _write_json(out / "FINAL_V23_INPUT_DIFF_REPORT.json", input_diff)
    _write_json(out / "PROCESS_DATA_DEEP_AUDIT.json", process_audit)
    _write_json(out / "FINAL_V23_ENGINE_SOURCE_AUDIT.json", engine_audit)
    _write_json(out / "KFGINS_CORE_FLOW_AUDIT.json", core_flow)
    _write_json(out / "LEGSA_KFGINS_FRAMEWORK_PARITY_MATRIX.json", framework_parity)
    _write_json(out / "N4H2C_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n4h2c_yaw_config_parity_case_review.md",
        actual_input=actual_input,
        reconstructed_input=reconstructed_input,
        case_probe=case_probe,
        input_diff=input_diff,
        process_audit=process_audit,
        engine_audit=engine_audit,
        framework_parity=framework_parity,
        decision=decision,
    )
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-v23-case-root", required=True)
    parser.add_argument("--n4h2-artifacts-root", required=True)
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision["recommended_next_stage"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
