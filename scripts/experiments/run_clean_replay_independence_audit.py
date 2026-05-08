#!/usr/bin/env python3
"""Run N4H2G2 clean replay independence and yaw sensitivity audit.

中文说明：本 runner 只生成仓库外诊断 artifacts，用于检查 clean replay 是否
独立、新鲜且对 yaw 输入敏感；不修改 solver，不提交生成数据。
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

from legsa_gins.evaluation.clean_replay_fresh_summary_audit import recompute_clean_summary_from_nav  # noqa: E402
from legsa_gins.evaluation.clean_replay_independence_audit import force_clean_replay_rerun  # noqa: E402
from legsa_gins.evaluation.replay_artifact_hash_audit import compare_artifact_hashes, hash_replay_artifacts  # noqa: E402
from legsa_gins.evaluation.yaw_input_sensitivity_probe import (  # noqa: E402
    create_yaw_shifted_gnss,
    run_yaw_shift_sensitivity,
)


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _summary_diff(fresh: dict[str, Any], old: dict[str, Any]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]:
        if isinstance(fresh.get(key), (int, float)) and isinstance(old.get(key), (int, float)):
            result[key] = float(fresh[key]) - float(old[key])
        else:
            result[key] = None
    return result


def _load_json(path: str | Path) -> dict[str, Any]:
    item = Path(path)
    if not item.exists():
        return {}
    return json.loads(item.read_text(encoding="utf-8"))


def _summary_matches(diff: dict[str, float | None], tol: float = 1.0e-9) -> bool:
    return all(value is None or abs(value) <= tol for value in diff.values())


def _decide(
    *,
    independence: dict[str, Any],
    fresh_audit: dict[str, Any],
    old_vs_fresh: dict[str, Any],
    noisy_vs_fresh: dict[str, Any],
    yaw_probe: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    blocking: list[str] = []
    if not independence.get("independent_rerun_completed"):
        blocking.append("fresh_clean_rerun_not_completed")
        return "N4H2G_clean_replay_run_failure_audit", {"clean_replay_independent": False}, blocking
    if not independence.get("clean_output_files_newer_than_run_start"):
        blocking.append("clean_output_mtime_not_new")
        return "N4H2G_cache_staleness_fix", {"cache_staleness_detected": True}, blocking

    diff = fresh_audit.get("fresh_vs_old_summary_diff") or {}
    if not _summary_matches(diff):
        blocking.append("fresh_summary_differs_from_old_clean_summary")
        return "N4H2G_recompute_clean_summary_and_update_policy", {"fresh_summary_differs_from_old_clean": True}, blocking

    if (
        noisy_vs_fresh.get("clean_input_differs_from_noisy_input")
        and not noisy_vs_fresh.get("clean_nav_differs_from_noisy_nav")
        and yaw_probe.get("yaw_input_has_low_runtime_effect_or_update_rejected")
    ):
        blocking.append("yaw_input_low_effect_with_identical_nav_hash")
        return "N4H2G_yaw_update_usage_audit", {"yaw_input_usage_suspect": True}, blocking

    classification = {
        "clean_replay_independent": True,
        "cache_staleness_detected": False,
        "old_summary_used": False,
        "fresh_summary_matches_old_clean_summary": True,
        "old_clean_vs_fresh_clean_nav_hash_differs": old_vs_fresh.get("clean_nav_differs_from_noisy_nav"),
        "yaw_input_affects_runtime": yaw_probe.get("yaw_input_affects_runtime"),
        "yaw_input_runtime_effect_bounded": yaw_probe.get("yaw_input_runtime_effect_bounded"),
        "yaw_input_has_low_runtime_effect_or_update_rejected": yaw_probe.get("yaw_input_has_low_runtime_effect_or_update_rejected"),
    }
    return "N4H3_controlled_final_v23_reference_import_with_clean_replay_available", classification, blocking


def _write_markdown(path: Path, decision: dict[str, Any]) -> None:
    fresh = decision.get("fresh_clean_summary") or {}
    yaw_probe = decision.get("yaw_input_sensitivity_probe") or {}
    lines = [
        "# N4H2G2 clean replay independence audit",
        "",
        "This audit checks whether the clean status-yaw replay is a fresh independent run rather than a cached or stale summary artifact.",
        "",
        "## Boundary",
        "",
        "- trace_solver_input=false",
        "- output_only_correction=false",
        "- solver_output_changed=false",
        "- bad_epoch_deletion_for_metric=false",
        "- numerical_performance_claim=false",
        "- yaw sensitivity probe is diagnostic only",
        "",
        "## Independence",
        "",
        f"- independent_rerun_completed: {decision.get('clean_independence', {}).get('independent_rerun_completed')}",
        f"- clean_output_files_newer_than_run_start: {decision.get('clean_independence', {}).get('clean_output_files_newer_than_run_start')}",
        f"- old_clean_summary_used_as_input: {decision.get('fresh_summary_audit', {}).get('old_clean_summary_used_as_input')}",
        "",
        "## Fresh Summary",
        "",
        f"- horizontal_rmse_m: {fresh.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {fresh.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {fresh.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {fresh.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {fresh.get('pitch_rmse_deg')}",
        "",
        "## Yaw Sensitivity",
        "",
        f"- shifted_input_vs_clean_input_yaw_diff_rmse: {yaw_probe.get('shifted_input_vs_clean_input_yaw_diff_rmse')}",
        f"- shifted_nav_vs_clean_nav_yaw_diff_rmse: {yaw_probe.get('shifted_nav_vs_clean_nav_yaw_diff_rmse')}",
        f"- yaw_input_affects_runtime: {yaw_probe.get('yaw_input_affects_runtime')}",
        f"- yaw_input_has_low_runtime_effect_or_update_rejected: {yaw_probe.get('yaw_input_has_low_runtime_effect_or_update_rejected')}",
        "",
        "## Decision",
        "",
        f"- likely_issue_classification: {decision.get('likely_issue_classification')}",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- blocking_issues: {decision.get('blocking_issues')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    noisy_hashes = hash_replay_artifacts(args.dual_root, "historical_noisy_dual_final_v23")
    n4h2_hashes = hash_replay_artifacts(args.n4h2_root, "n4h2_replay_artifacts")
    old_clean_hashes = hash_replay_artifacts(args.n4h2g_root, "old_n4h2g_clean_replay")

    independence = force_clean_replay_rerun(
        args.fix_root,
        args.body_imu,
        args.external_source_root,
        out,
        args.dual_root,
        base_time=args.base_time,
        allow_build=args.allow_build,
        allow_run=args.allow_run,
    )
    rerun_dir = Path(independence["rerun_dir"])
    fresh_clean_hashes = hash_replay_artifacts(rerun_dir, "fresh_n4h2g2_clean_rerun")

    fresh_audit = recompute_clean_summary_from_nav(
        rerun_dir / "kfgins_output" / "KF_GINS_Navresult.nav",
        independence.get("selected_reference") or [],
        out,
        old_clean_summary_path=Path(args.n4h2g_root) / "CLEAN_REPLAY_SUMMARY.json",
    ) if independence.get("independent_rerun_completed") else {
        "fresh_summary_computed": False,
        "fresh_summary": {},
        "old_clean_summary_used_as_input": False,
        "fresh_vs_old_summary_diff": {},
        "summary_staleness_status": "rerun_not_completed",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    if not independence.get("independent_rerun_completed"):
        _write_json(out / "CLEAN_REPLAY_FRESH_SUMMARY_AUDIT.json", fresh_audit)

    old_vs_fresh = compare_artifact_hashes(fresh_clean_hashes, old_clean_hashes, clean_run_start_time=independence.get("run_start_time"))
    noisy_vs_fresh = compare_artifact_hashes(fresh_clean_hashes, noisy_hashes, clean_run_start_time=independence.get("run_start_time"))
    noisy_vs_old_clean = compare_artifact_hashes(old_clean_hashes, noisy_hashes)
    hash_report = {
        "phase": "N4H2G2",
        "noisy_hashes": noisy_hashes,
        "n4h2_hashes": n4h2_hashes,
        "old_clean_hashes": old_clean_hashes,
        "fresh_clean_hashes": fresh_clean_hashes,
        "old_clean_vs_fresh_clean": old_vs_fresh,
        "noisy_vs_fresh_clean": noisy_vs_fresh,
        "noisy_vs_old_clean": noisy_vs_old_clean,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "CLEAN_REPLAY_ARTIFACT_HASH_REPORT.json", hash_report)

    yaw_probe: dict[str, Any]
    if args.run_yaw_sensitivity_probe and independence.get("independent_rerun_completed"):
        shifted_gnss = out / "yaw_shift_probe" / "SHIFTED_STATUS_YAW_PLUS30.gnss"
        create_yaw_shifted_gnss(rerun_dir / "CLEAN_STATUS_YAW.gnss", shifted_gnss, yaw_shift_deg=30.0)
        yaw_probe = run_yaw_shift_sensitivity(
            rerun_dir,
            shifted_gnss,
            args.external_source_root,
            out,
            clean_nav=rerun_dir / "kfgins_output" / "KF_GINS_Navresult.nav",
            dual_reference=independence.get("selected_reference") or [],
            clean_summary=fresh_audit.get("fresh_summary") or {},
            allow_build=args.allow_build,
            allow_run=args.allow_run,
        )
    else:
        yaw_probe = {
            "phase": "N4H2G2",
            "evidence_status": "not_run",
            "yaw_input_affects_runtime": False,
            "yaw_input_has_low_runtime_effect_or_update_rejected": False,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }
        _write_json(out / "YAW_INPUT_SENSITIVITY_PROBE_REPORT.json", yaw_probe)

    recommended, classification, blockers = _decide(
        independence=independence,
        fresh_audit=fresh_audit,
        old_vs_fresh=old_vs_fresh,
        noisy_vs_fresh=noisy_vs_fresh,
        yaw_probe=yaw_probe,
    )
    old_summary = _load_json(Path(args.n4h2g_root) / "CLEAN_REPLAY_SUMMARY.json")
    fresh_summary = fresh_audit.get("fresh_summary") or {}
    decision = {
        "phase": "N4H2G2",
        "clean_independence": independence,
        "artifact_hash_report": {
            "old_clean_vs_fresh_clean": old_vs_fresh,
            "noisy_vs_fresh_clean": noisy_vs_fresh,
            "noisy_vs_old_clean": noisy_vs_old_clean,
        },
        "fresh_summary_audit": fresh_audit,
        "fresh_clean_summary": fresh_summary,
        "old_clean_summary": old_summary,
        "fresh_vs_old_clean_summary_diff": _summary_diff(fresh_summary, old_summary),
        "yaw_input_sensitivity_probe": yaw_probe,
        "likely_issue_classification": classification,
        "recommended_next_stage": recommended,
        "blocking_issues": blockers,
        "baseline_replay_diagnostics_only": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "N4H2G2_DECISION_REPORT.json", decision)
    _write_markdown(out / "n4h2g2_clean_replay_independence_audit.md", decision)
    return decision


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--body-imu", required=True)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--n4h2g-root", default=str(Path.home() / "legsa_n4h2g_clean_replay"))
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h2g2_clean_independence"))
    parser.add_argument("--base-time", type=float, default=1772784000.0)
    parser.add_argument("--allow-build", action="store_true")
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-yaw-sensitivity-probe", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    decision = run(parse_args(argv))
    print(json.dumps({"recommended_next_stage": decision.get("recommended_next_stage")}, sort_keys=True))
    return 0 if decision.get("clean_independence", {}).get("independent_rerun_completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
