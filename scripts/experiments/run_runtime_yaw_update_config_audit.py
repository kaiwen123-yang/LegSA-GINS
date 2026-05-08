#!/usr/bin/env python3
"""Run N4H2C-runtime yaw update/config/source-version parity audit.

中文说明：该 runner 只读取 runtime-only artifacts 与 external source 的只读证据；
不复制 external source，不修改 solver output，不做 performance claim。
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

from legsa_gins.evaluation.actual_vs_replay_yaw_path import (  # noqa: E402
    make_actual_vs_replay_yaw_path_report,
)
from legsa_gins.evaluation.error_series_parity import load_official_summary  # noqa: E402
from legsa_gins.evaluation.yaw_runtime_path_diagnostics import classify_yaw_runtime_issue  # noqa: E402
from legsa_gins.source_audit.kfgins_yaw_source_history import (  # noqa: E402
    audit_current_yaw_update_source,
    search_yaw_update_history,
)
from legsa_gins.source_audit.runtime_yaw_update_config_audit import (  # noqa: E402
    compare_actual_and_replay_config,
    find_runtime_configs,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"evidence_status": "evidence_missing", "evidence_missing": [path.name]}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"evidence_status": "evidence_missing", "evidence_missing": [f"{path.name}_parse"], "error": str(exc)}


def _find_replay_input(root: Path) -> Path | None:
    candidates = [
        root / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss",
        root / "input.gnss",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = sorted(root.rglob("*.gnss")) if root.exists() else []
    return found[0] if found else None


def _find_replay_nav(root: Path) -> Path | None:
    candidates = [
        root / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav",
        root / "KF_GINS_Navresult.nav",
    ]
    for path in candidates:
        if path.exists():
            return path
    found = sorted(root.rglob("KF_GINS_Navresult.nav")) if root.exists() else []
    return found[0] if found else None


def _load_replay_summary(root: Path) -> dict[str, Any]:
    report = _read_json(root / "replay" / "N4H2_REPLAY_REPORT.json")
    evaluation = report.get("evaluation")
    if isinstance(evaluation, dict):
        return evaluation
    summary = _read_json(root / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json")
    if summary.get("evidence_status") != "evidence_missing":
        return summary
    return report


def _write_markdown(path: Path, decision: dict[str, Any]) -> None:
    actual_summary = decision.get("actual_dual_official_summary") or {}
    replay_summary = decision.get("n4h2_replay_summary") or {}
    input_report = decision.get("actual_input_vs_replay_input_yaw") or {}
    nav_report = decision.get("actual_nav_vs_replay_nav_yaw") or {}
    config = decision.get("config_audit") or {}
    source = decision.get("current_source_yaw_update") or {}
    lines = [
        "# N4H2C runtime yaw update/config parity audit",
        "",
        "This diagnostic exists because dual_final_v23 evaluator parity locked direct_identity while the N4H2 replay yaw remains far from the confirmed direct evaluator result.",
        "",
        "## Boundary",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- solver_output_changed=false",
        "- numerical_performance_claim=false",
        "- external KF-GINS source is read-only",
        "- full KF-GINS-style framework work waits until runtime/config parity is understood",
        "",
        "## Actual dual summary",
        "",
        f"- horizontal_rmse_m: {actual_summary.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {actual_summary.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {actual_summary.get('yaw_rmse_deg')}",
        "",
        "## N4H2 replay summary",
        "",
        f"- horizontal_rmse_m: {replay_summary.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {replay_summary.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {replay_summary.get('yaw_rmse_deg')}",
        "",
        "## Path comparison",
        "",
        f"- actual_input_vs_replay_input_yaw_rmse_deg: {input_report.get('input_yaw_diff_rmse_deg')}",
        f"- actual_nav_vs_replay_nav_yaw_rmse_deg: {nav_report.get('nav_yaw_diff_rmse_deg')}",
        f"- actual_input_vs_actual_nav: {(decision.get('actual_input_vs_actual_nav_yaw') or {}).get('classification')}",
        f"- replay_input_vs_replay_nav: {(decision.get('replay_input_vs_replay_nav_yaw') or {}).get('classification')}",
        "",
        "## Config/source evidence",
        "",
        f"- actual_config_status: {config.get('actual_config_status')}",
        f"- replay_config_status: {config.get('replay_config_status')}",
        f"- current_yaw_measurement_loaded: {source.get('current_yaw_measurement_loaded')}",
        f"- current_yaw_update_enabled: {source.get('current_yaw_update_enabled')}",
        f"- current_yaw_measurement_transform: {source.get('current_yaw_measurement_transform')}",
        f"- current_scheme_C_gate: {source.get('current_scheme_C_gate')}",
        "",
        "## Decision",
        "",
        f"- likely_issue_classification: {decision.get('likely_issue_classification')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _missing_report(reason: str) -> dict[str, Any]:
    return {
        "phase": "N4H2C-runtime",
        "evidence_status": "evidence_missing",
        "evidence_missing": [reason],
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    dual_root = Path(args.dual_root)
    n4h2_root = Path(args.n4h2_artifacts_root)
    external_root = Path(args.external_source_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    actual_input = dual_root / "input.gnss"
    actual_nav = dual_root / "KF_GINS_Navresult.nav"
    replay_input = _find_replay_input(n4h2_root)
    replay_nav = _find_replay_nav(n4h2_root)
    actual_summary = load_official_summary(dual_root / "summary.json")
    replay_summary = _load_replay_summary(n4h2_root)

    if replay_input is None or replay_nav is None or not actual_input.exists() or not actual_nav.exists():
        yaw_path_report = _missing_report("actual_or_replay_input_nav")
    else:
        yaw_path_report = make_actual_vs_replay_yaw_path_report(
            actual_input,
            replay_input,
            actual_nav,
            replay_nav,
        )
    _write_json(out / "ACTUAL_REPLAY_YAW_PATH_REPORT.json", yaw_path_report)

    config_search = find_runtime_configs(
        {
            "DUAL_FINAL_V23_ARTIFACT_ROOT": dual_root,
            "N4H2_ARTIFACTS_ROOT": n4h2_root,
            "EXTERNAL_KFGINS_ROOT": external_root,
        }
    )
    config_report = compare_actual_and_replay_config(
        config_search.get("best_actual_config"),
        config_search.get("best_replay_config"),
    )
    config_report["config_search"] = config_search
    _write_json(out / "RUNTIME_CONFIG_PARITY_REPORT.json", config_report)

    current_source = audit_current_yaw_update_source(external_root)
    source_history = search_yaw_update_history(external_root)
    _write_json(out / "CURRENT_YAW_UPDATE_SOURCE_AUDIT.json", current_source)
    _write_json(out / "YAW_UPDATE_SOURCE_HISTORY_REPORT.json", source_history)

    source_bundle = {"current_source_audit": current_source, "source_history": source_history}
    diagnostics = classify_yaw_runtime_issue(
        yaw_path_report,
        config_report,
        source_bundle,
        actual_summary=actual_summary,
        replay_summary=replay_summary,
    )
    _write_json(out / "YAW_RUNTIME_PATH_DIAGNOSTICS.json", diagnostics)

    decision = {
        "phase": "N4H2C-runtime",
        "actual_dual_official_summary": actual_summary,
        "n4h2_replay_summary": replay_summary,
        "actual_input_vs_replay_input_yaw": yaw_path_report.get("actual_input_vs_replay_input_yaw", {}),
        "actual_nav_vs_replay_nav_yaw": yaw_path_report.get("actual_nav_vs_replay_nav_yaw", {}),
        "actual_input_vs_actual_nav_yaw": yaw_path_report.get("actual_input_vs_actual_nav_yaw", {}),
        "replay_input_vs_replay_nav_yaw": yaw_path_report.get("replay_input_vs_replay_nav_yaw", {}),
        "likely_path_difference": yaw_path_report.get("likely_path_difference"),
        "config_audit": {
            "actual_config_status": config_report.get("actual_config_status"),
            "replay_config_status": config_report.get("replay_config_status"),
            "initatt_diff": config_report.get("initatt_diff"),
            "antlever_diff": config_report.get("antlever_diff"),
            "yaw_relevant_config_diff": config_report.get("yaw_relevant_config_diff"),
            "evidence_missing": config_report.get("evidence_missing"),
            "recommended_action": config_report.get("recommended_action"),
        },
        "current_source_yaw_update": {
            "yaw_measurement_loaded": current_source.get("current_yaw_measurement_loaded"),
            "yaw_update_enabled": current_source.get("current_yaw_update_enabled"),
            "yaw_residual_formula": current_source.get("current_yaw_residual_formula"),
            "yaw_measurement_transform": current_source.get("current_yaw_measurement_transform"),
            "scheme_C_gate": current_source.get("current_scheme_C_gate"),
            "current_yaw_measurement_loaded": current_source.get("current_yaw_measurement_loaded"),
            "current_yaw_update_enabled": current_source.get("current_yaw_update_enabled"),
            "current_yaw_residual_formula": current_source.get("current_yaw_residual_formula"),
            "current_yaw_measurement_transform": current_source.get("current_yaw_measurement_transform"),
            "current_scheme_C_gate": current_source.get("current_scheme_C_gate"),
        },
        "source_history": {
            "possible_source_version_mismatch": source_history.get("possible_source_version_mismatch"),
            "candidate_commit_count": source_history.get("candidate_commit_count"),
            "candidate_branch_count": source_history.get("candidate_branch_count"),
            "evidence_of_yaw_transform_variants": source_history.get("evidence_of_yaw_transform_variants"),
        },
        "likely_issue_classification": diagnostics.get("likely_issue_classification"),
        "recommended_next_stage": diagnostics.get("recommended_next_stage"),
        "blocking_issues": diagnostics.get("blocking_issues"),
        "full_kfgins_framework_needed": diagnostics.get("full_kfgins_framework_needed"),
        "full_ekf_should_wait_until_runtime_config_parity_resolved": diagnostics.get(
            "full_ekf_should_wait_until_runtime_config_parity_resolved"
        ),
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "N4H2C_RUNTIME_YAW_DECISION_REPORT.json", decision)
    _write_markdown(out / "n4h2c_runtime_yaw_update_config_audit.md", decision)
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision.get("recommended_next_stage")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
