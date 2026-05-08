#!/usr/bin/env python3
"""Generate N4H2E dual_final_v23-only fresh replay visual validation bundle.

中文说明：本脚本只生成 dual_final_v23 / fresh replay 图像证据；不修改 solver
output，不提交 artifact，不做 formal performance claim。
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.error_series_parity import load_official_summary  # noqa: E402
from legsa_gins.evaluation.fresh_replay_evaluator import evaluate_replay_against_official_reference  # noqa: E402
from legsa_gins.evaluation.official_reference_reconstruction import (  # noqa: E402
    load_official_error_series,
    load_official_nav,
    select_reference_sign_by_summary,
)
from legsa_gins.evaluation.replay_reference_mapping_audit import locate_n4h2_replay_outputs  # noqa: E402
from legsa_gins.visualization.dual_replay_plot_loader import (  # noqa: E402
    load_dual_official_artifacts,
    load_n4h2_fresh_replay_artifacts,
)
from legsa_gins.visualization.dual_replay_plots import (  # noqa: E402
    PLOT_DIRS,
    generate_dual_replay_plots,
    write_visual_case_review,
)
from legsa_gins.visualization.plot_bundle_manifest import (  # noqa: E402
    build_figure_manifest,
    write_figure_manifest,
)
from legsa_gins.visualization.visual_sanity_checks import (  # noqa: E402
    build_visual_sanity_report,
    write_visual_sanity_report,
)
from legsa_gins.visualization.startup_transient_audit import (  # noqa: E402
    analyze_startup_transient,
    update_visual_case_review_with_audits,
    write_startup_transient_report,
)
from legsa_gins.visualization.yaw_std_source_audit import (  # noqa: E402
    analyze_yaw_std_source,
    write_yaw_std_source_report,
)
from legsa_gins.evaluation.actual_input_yaw_variant_match import (  # noqa: E402
    compare_actual_input_to_variants,
    write_actual_input_yaw_variant_match_report,
)
from legsa_gins.source_audit.process_data_noise_provenance import (  # noqa: E402
    audit_process_data_script,
    audit_run_final_mainline,
    generate_yaw_variant_inputs,
    make_process_data_noise_provenance_report,
    write_json_report,
)
from legsa_gins.evaluation.replay_reference_mapping_audit import locate_n4h2_replay_outputs  # noqa: E402


EXPECTED_N4H2D = {
    "horizontal_rmse_m": 0.3460851160719829,
    "up_rmse_m": 0.7940342899951961,
    "yaw_rmse_deg": 1.979182806966782,
}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_visual_output_dir() -> Path:
    return Path("/mnt") / "c" / "Users" / "ykw" / "Desktop" / "LegSA-GINS" / "绘图验证"


def _clean_previous_outputs(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for folder in PLOT_DIRS:
        target = output_dir / folder
        if target.exists():
            shutil.rmtree(target)
    for filename in ["figure_manifest.json", "VISUAL_VALIDATION_REPORT.json", "VISUAL_SANITY_CHECK_REPORT.json"]:
        target = output_dir / filename
        if target.exists():
            target.unlink()


def _gate_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "horizontal_gate_pass": bool(summary.get("horizontal_gate_pass")),
        "up_gate_pass": bool(summary.get("up_gate_pass")),
        "yaw_gate_pass": bool(summary.get("yaw_gate_pass")),
        "roll_strict_gate_pass": bool(summary.get("roll_strict_gate_pass")),
        "roll_relaxed_gate_pass": bool(summary.get("roll_relaxed_gate_pass")),
        "pitch_strict_gate_pass": bool(summary.get("pitch_strict_gate_pass")),
        "pitch_relaxed_gate_pass": bool(summary.get("pitch_relaxed_gate_pass")),
        "roll_pitch_relaxed_not_strict": bool(
            summary.get("roll_relaxed_gate_pass")
            and summary.get("pitch_relaxed_gate_pass")
            and (not summary.get("roll_strict_gate_pass") or not summary.get("pitch_strict_gate_pass"))
        ),
        "yaw_near_boundary": isinstance(summary.get("yaw_rmse_deg"), (int, float))
        and 1.8 <= float(summary["yaw_rmse_deg"]) <= 2.2,
    }


def _metric_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": summary.get("count"),
        "horizontal_rmse_m": summary.get("horizontal_rmse_m"),
        "up_rmse_m": summary.get("up_rmse_m"),
        "yaw_rmse_deg": summary.get("yaw_rmse_deg"),
        "roll_rmse_deg": summary.get("roll_rmse_deg"),
        "pitch_rmse_deg": summary.get("pitch_rmse_deg"),
        "horizontal_p95_m": summary.get("horizontal_p95_m"),
        "yaw_p95_deg": summary.get("yaw_p95_deg"),
    }


def _fresh_summary_matches_expected(summary: dict[str, Any]) -> bool:
    if not summary.get("count") or int(summary.get("count", 0)) < 1000:
        return True
    for key, expected in EXPECTED_N4H2D.items():
        value = summary.get(key)
        if not isinstance(value, (int, float)) or abs(float(value) - expected) > 0.02:
            return False
    return True


def _rebuild_fresh_replay(
    *,
    dual_root: Path,
    n4h2_root: Path,
    evaluation_dir: Path,
) -> dict[str, Any]:
    dual_summary = load_official_summary(dual_root / "summary.json")
    dual_nav = load_official_nav(dual_root / "KF_GINS_Navresult.nav")
    dual_errors = load_official_error_series(dual_root / "error_series.csv")
    reconstruction = select_reference_sign_by_summary(dual_nav, dual_errors, dual_summary)
    selected_reference = reconstruction["reference_candidates"][reconstruction["selected_reference_sign"]]
    locations = locate_n4h2_replay_outputs(n4h2_root)
    replay_nav_path = (locations.get("located_files") or {}).get("replay_nav")
    if not replay_nav_path:
        raise FileNotFoundError("N4H2 replay NAV not found")
    fresh_report = evaluate_replay_against_official_reference(replay_nav_path, selected_reference, evaluation_dir)
    return {
        "official_reference_reconstruction": reconstruction,
        "selected_reference": selected_reference,
        "fresh_report": fresh_report,
        "replay_locations": locations,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    dual_root = Path(args.dual_root)
    n4h2_root = Path(args.n4h2_artifacts_root)
    output_dir = Path(args.output_dir)
    _clean_previous_outputs(output_dir)
    evaluation_dir = output_dir / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    rebuild = _rebuild_fresh_replay(dual_root=dual_root, n4h2_root=n4h2_root, evaluation_dir=evaluation_dir)
    dual = load_dual_official_artifacts(dual_root)
    replay = load_n4h2_fresh_replay_artifacts(n4h2_root, evaluation_dir)
    if dual.get("evidence_status") != "loaded":
        raise FileNotFoundError(f"dual artifact evidence missing: {dual.get('evidence_missing')}")
    if not replay.get("replay_nav_rows") or not replay.get("fresh_error_rows"):
        raise FileNotFoundError(f"replay visual evidence missing: {replay.get('evidence_missing')}")

    selected_reference = rebuild["selected_reference"]
    fresh_summary = replay["fresh_summary"]
    metrics = _metric_snapshot(fresh_summary)
    gates = _gate_snapshot(fresh_summary)
    summary_matches_expected = _fresh_summary_matches_expected(fresh_summary)
    plot_report = generate_dual_replay_plots(
        output_dir=output_dir,
        replay_nav_rows=replay["replay_nav_rows"],
        reference_rows=selected_reference,
        error_rows=replay["fresh_error_rows"],
        replay_std_rows=replay["replay_std_rows"],
        input_rows=replay["input_rows"],
        metrics=fresh_summary,
        case_name=args.case_name,
        line_name=args.line_name,
    )
    if plot_report.get("plotting_status") != "completed":
        report = {
            "phase": "N4H2E",
            "plotting_status": "failed",
            "plot_report": plot_report,
            "manual_visual_review_required": True,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "numerical_performance_claim": False,
        }
        _write_json(output_dir / "VISUAL_VALIDATION_REPORT.json", report)
        raise RuntimeError(json.dumps(report, sort_keys=True))

    provisional_sanity = {
        "phase": "N4H2E",
        "status": "pending_final_visual_sanity",
        "manual_visual_review_required": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
    write_visual_case_review(
        output_dir,
        metrics=metrics,
        gates=gates,
        figure_paths=plot_report["figure_paths"],
        visual_sanity=provisional_sanity,
    )
    visual_sanity = build_visual_sanity_report(
        output_dir=output_dir,
        reference_rows=selected_reference,
        estimate_rows=replay["replay_nav_rows"],
        error_series=replay["fresh_error_rows"],
        metrics_snapshot=fresh_summary,
        expected_count=fresh_summary.get("count"),
        expected_min_figures=30,
    )
    write_visual_sanity_report(output_dir / "VISUAL_SANITY_CHECK_REPORT.json", visual_sanity)
    case_review = write_visual_case_review(
        output_dir,
        metrics=metrics,
        gates=gates,
        figure_paths=plot_report["figure_paths"],
        visual_sanity=visual_sanity,
    )
    manifest = build_figure_manifest(
        output_dir,
        metrics_snapshot=metrics,
        gates_snapshot=gates,
        visual_sanity=visual_sanity,
    )
    write_figure_manifest(output_dir / "figure_manifest.json", manifest)

    validation_report = {
        "phase": "N4H2E",
        "plotting_status": "completed",
        "plot_bundle_role": "dual_final_v23_only_visual_validation",
        "case_name": args.case_name,
        "line_name": args.line_name,
        "output_dir_role": "VISUAL_OUTPUT_DIR",
        "figure_count_total": manifest["figure_count_total"],
        "figure_counts_by_folder": manifest["figure_counts_by_folder"],
        "required_figures_generated": manifest["required_figures_generated"],
        "metrics_snapshot": metrics,
        "gates_snapshot": gates,
        "fresh_summary_matches_n4h2d_expected": summary_matches_expected,
        "visual_sanity": visual_sanity,
        "case_review": case_review,
        "old_summary_invalidated": True,
        "manual_visual_review_required": True,
        "manual_review_required": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "formal_paper_performance_claim": False,
    }
    if args.include_n4h2f_audits:
        review_dir = output_dir / "09_case_review"
        startup_report = analyze_startup_transient(
            evaluation_dir / "FRESH_REPLAY_ERROR_SERIES.csv",
            evaluation_dir / "FRESH_REPLAY_SUMMARY.json",
        )
        write_startup_transient_report(review_dir / "STARTUP_TRANSIENT_AUDIT_REPORT.json", startup_report)
        yaw_std_report = analyze_yaw_std_source(dual_root / "input.gnss", dual_root / "KF_GINS_STD.txt")
        write_yaw_std_source_report(review_dir / "YAW_STD_SOURCE_AUDIT_REPORT.json", yaw_std_report)
        external = Path(args.external_source_root)
        process_audit = audit_process_data_script(external / "bin" / "process_data.py")
        run_audit = audit_run_final_mainline(external / "scripts" / "run_final_mainline.py")
        variant_output = Path(tempfile.gettempdir()) / "legsa_n4h2f_yaw_variants"
        replay_locations = locate_n4h2_replay_outputs(n4h2_root)
        fallback_input = (replay_locations.get("located_files") or {}).get("input_gnss")
        generation = generate_yaw_variant_inputs(
            variant_output,
            process_data_path=external / "bin" / "process_data.py",
            fallback_input_gnss=fallback_input,
        )
        match = compare_actual_input_to_variants(dual_root / "input.gnss", generation.get("variant_inputs") or {})
        provenance = make_process_data_noise_provenance_report(process_audit, run_audit, generation, match)
        write_json_report(review_dir / "RUN_FINAL_MAINLINE_PROVENANCE_REPORT.json", run_audit)
        write_actual_input_yaw_variant_match_report(review_dir / "ACTUAL_INPUT_YAW_VARIANT_MATCH_REPORT.json", match)
        write_json_report(review_dir / "PROCESS_DATA_NOISE_PROVENANCE_REPORT.json", provenance)
        update_visual_case_review_with_audits(review_dir)
        validation_report["startup_transient_audit"] = startup_report
        validation_report["yaw_std_source_audit"] = yaw_std_report
        validation_report["process_data_noise_provenance"] = provenance
        validation_report["actual_input_yaw_variant_match"] = match
    _write_json(output_dir / "VISUAL_VALIDATION_REPORT.json", validation_report)
    return validation_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--n4h2-artifacts-root", default=str(Path.home() / "legsa_n4h2_artifacts"))
    parser.add_argument("--output-dir", default=str(_default_visual_output_dir()))
    parser.add_argument("--case-name", default="nominal_none")
    parser.add_argument("--line-name", default="dual_final_v23_replay")
    parser.add_argument("--external-source-root", default=str(Path.home() / "KF-GINS"))
    parser.add_argument("--include-n4h2f-audits", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        report = run(parse_args(argv))
    except Exception as exc:
        print(json.dumps({"plotting_status": "failed", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"plotting_status": report.get("plotting_status"), "output_dir": report.get("output_dir_role")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
