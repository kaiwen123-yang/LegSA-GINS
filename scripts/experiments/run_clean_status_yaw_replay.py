#!/usr/bin/env python3
"""Run N4H2G clean status-yaw no-noise replay audit.

中文说明：本 runner 生成 clean/no-noise/no-outlier/no-outage 的
process_data-compatible 输入，调用外部 KF-GINS baseline，并用 dual official
reference 做 evaluation-only 评价；不修改 solver、不提交 artifacts。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.clean_status_yaw_replay import (  # noqa: E402
    evaluate_clean_replay_against_dual_reference,
    generate_clean_process_data_input,
    run_external_kfgins_clean_replay,
)
from legsa_gins.evaluation.clean_vs_noisy_replay_comparison import compare_clean_vs_noisy_replay  # noqa: E402
from legsa_gins.evaluation.error_series_parity import load_official_summary  # noqa: E402
from legsa_gins.evaluation.official_reference_reconstruction import (  # noqa: E402
    load_official_error_series,
    load_official_nav,
    select_reference_sign_by_summary,
)
from legsa_gins.source_audit.clean_input_provenance_policy import (  # noqa: E402
    make_clean_input_provenance_policy_report,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decision_from_status(status: str, run_report: dict[str, Any]) -> str:
    if not run_report.get("completed"):
        return "N4H2G_replay_run_failure_audit"
    if status == "passed":
        return "N4H3_controlled_final_v23_reference_import_with_clean_replay_available"
    if status == "near_gate":
        return "N4H3_reference_import_with_clean_near_gate_caveat"
    if status == "failed_yaw":
        return "N4H2G_clean_yaw_config_audit"
    return "N4H2G_replay_run_failure_audit" if status == "evidence_missing" else "N4H2G_clean_position_or_up_audit"


def _write_markdown(path: Path, decision: dict[str, Any]) -> None:
    manifest = decision.get("clean_input_manifest") or {}
    summary = decision.get("clean_replay_summary") or {}
    comparison = decision.get("clean_vs_noisy_comparison") or {}
    policy = decision.get("clean_input_provenance_policy") or {}
    lines = [
        "# N4H2G clean status-yaw replay audit",
        "",
        "This stage reconstructs a clean status-yaw no-noise/no-outlier/no-outage baseline replay variant.",
        "",
        "## Boundary",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- bad_epoch_deletion_for_metric=false",
        "- numerical_performance_claim=false",
        "- clean replay is baseline diagnostic evidence, not proposed solver performance",
        "",
        "## Clean Input Manifest",
        "",
        f"- yaw_noise_std_deg: {manifest.get('yaw_noise_std_deg')}",
        f"- outlier_mode: {manifest.get('outlier_mode')}",
        f"- outlier_ratio: {manifest.get('outlier_ratio')}",
        f"- enable_outage: {manifest.get('enable_outage')}",
        f"- yaw_std_mode: {manifest.get('yaw_std_mode')}",
        "",
        "## Clean Replay Summary",
        "",
        f"- horizontal_rmse_m: {summary.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {summary.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {summary.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {summary.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {summary.get('pitch_rmse_deg')}",
        f"- yaw_gate_pass: {summary.get('yaw_gate_pass')}",
        "",
        "## Clean vs Noisy",
        "",
        f"- clean_replay_parity_status: {comparison.get('clean_replay_parity_status')}",
        f"- metric_delta_yaw: {comparison.get('metric_delta_yaw')}",
        f"- clean_vs_noisy_input_yaw_diff_rmse_deg: {comparison.get('clean_vs_noisy_input_yaw_diff_rmse_deg')}",
        f"- clean_vs_noisy_nav_yaw_diff_rmse_deg: {comparison.get('clean_vs_noisy_nav_yaw_diff_rmse_deg')}",
        "",
        "## Provenance Policy",
        "",
        f"- paper_should_not_call_noisy_actual_clean_nominal: {policy.get('paper_should_not_call_noisy_actual_clean_nominal')}",
        f"- clean_replay_is_not_historical_exact_final_v23_artifact: {policy.get('clean_replay_is_not_historical_exact_final_v23_artifact')}",
        "",
        "## Decision",
        "",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dual_root = Path(args.dual_root)

    clean_generation = generate_clean_process_data_input(
        args.fix_root,
        args.body_imu,
        out,
        base_time=args.base_time,
    )
    manifest = clean_generation["manifest"]

    run_report = run_external_kfgins_clean_replay(
        out,
        args.external_source_root,
        out,
        allow_build=args.allow_build,
        allow_run=args.allow_run,
    )

    dual_summary = load_official_summary(dual_root / "summary.json")
    dual_nav = load_official_nav(dual_root / "KF_GINS_Navresult.nav")
    dual_errors = load_official_error_series(dual_root / "error_series.csv")
    reconstruction = select_reference_sign_by_summary(dual_nav, dual_errors, dual_summary)
    selected_reference = reconstruction["reference_candidates"][reconstruction["selected_reference_sign"]]

    if run_report.get("completed"):
        evaluation = evaluate_clean_replay_against_dual_reference(
            out / "kfgins_output" / "KF_GINS_Navresult.nav",
            selected_reference,
            out,
        )
        clean_summary = evaluation["clean_replay_summary"]
    else:
        evaluation = {
            "phase": "N4H2G",
            "clean_replay_summary": {},
            "evidence_status": "replay_not_completed",
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }
        clean_summary = {}
        _write_json(out / "CLEAN_REPLAY_SUMMARY.json", clean_summary)
        _write_json(out / "CLEAN_REPLAY_EVALUATION_REPORT.json", evaluation)

    comparison = compare_clean_vs_noisy_replay(
        clean_summary=clean_summary,
        clean_input_gnss=out / "CLEAN_STATUS_YAW.gnss",
        noisy_input_gnss=dual_root / "input.gnss",
        clean_nav=out / "kfgins_output" / "KF_GINS_Navresult.nav" if run_report.get("completed") else None,
        noisy_nav=dual_root / "KF_GINS_Navresult.nav",
        output_dir=out,
    )
    policy = make_clean_input_provenance_policy_report(manifest, comparison, output_dir=out)
    status = comparison.get("clean_replay_parity_status")
    recommended = _decision_from_status(str(status), run_report)
    blocking: list[str] = []
    if not run_report.get("completed"):
        blocking.append("clean_replay_not_completed")
    if status not in {"passed", "near_gate"}:
        blocking.append(f"clean_replay_status_{status}")
    if policy.get("paper_should_not_call_noisy_actual_clean_nominal"):
        blocking.append("noisy_actual_not_clean_nominal")

    decision = {
        "phase": "N4H2G",
        "clean_input_manifest": manifest,
        "clean_replay_run_report": run_report,
        "official_reference_reconstruction": {
            "selected_reference_sign": reconstruction.get("selected_reference_sign"),
            "actual_dual_summary_reproduced": reconstruction.get("actual_dual_summary_reproduced"),
            "summary_diff": reconstruction.get("summary_diff"),
        },
        "clean_replay_summary": clean_summary,
        "clean_replay_evaluation": evaluation,
        "clean_vs_noisy_comparison": comparison,
        "clean_input_provenance_policy": policy,
        "recommended_next_stage": recommended,
        "blocking_issues": blocking,
        "clean_replay_metrics_are_baseline_diagnostics_only": True,
        "not_proposed_solver_performance": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "N4H2G_DECISION_REPORT.json", decision)
    _write_markdown(out / "n4h2g_clean_status_yaw_replay.md", decision)
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--body-imu", required=True)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h2g_clean_replay"))
    parser.add_argument("--base-time", type=float, default=1772784000.0)
    parser.add_argument("--allow-build", action="store_true")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision.get("recommended_next_stage")}, sort_keys=True))
    return 0 if decision.get("clean_replay_run_report", {}).get("completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
