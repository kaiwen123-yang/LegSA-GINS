#!/usr/bin/env python3
"""Run N8A no-feedback FGO foundation.

中文说明：N8A 只构建 no-feedback factor graph foundation；FGO 输出不回写 EKF，
不替换 EKF NAV，不使用 trace/final_v23 作为 factor。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.fgo.fgo_backend_discovery import discover_fgo_backend, write_backend_report
from legsa_gins.fgo.fgo_dataset_builder import build_n8a_dataset, write_dataset_report, write_state_csv
from legsa_gins.fgo.fgo_decision import make_n8a_decision, write_decision
from legsa_gins.fgo.fgo_evaluator import evaluate_no_feedback_fgo, write_evaluation_report
from legsa_gins.fgo.fgo_factor_registry import build_default_factor_registry, write_factor_registry_report
from legsa_gins.fgo.fgo_no_feedback_smoother import run_no_feedback_smoother, write_smoother_outputs
from legsa_gins.fgo.fgo_visual_plots import generate_n8a_figures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7b4-root", required=True)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _write_case_review(path: Path, decision: dict) -> None:
    lines = [
        "# N8A no-feedback FGO foundation",
        "",
        f"- status: {decision.get('status')}",
        f"- backend: {decision.get('backend_selected')}",
        f"- state_count: {decision.get('state_count')}",
        f"- active_factor_count_estimate: {decision.get('active_factor_count_estimate')}",
        f"- diagnostic_candidate_factor_count_estimate: {decision.get('diagnostic_candidate_factor_count_estimate')}",
        "- FGO output is no-feedback and does not replace EKF NAV.",
        "- Trace/final_v23 outputs are evaluation-only and not factor inputs.",
        "- Go2 foot kinematic, yaw-rate, and relative odometry factors are diagnostic candidates only.",
        "- No paper performance claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    backend = discover_fgo_backend()
    write_backend_report(out / "N8A_BACKEND_DISCOVERY_REPORT.json", backend)
    registry = build_default_factor_registry()
    write_factor_registry_report(out / "N8A_FACTOR_REGISTRY_REPORT.json", registry)
    dataset, dataset_report = build_n8a_dataset(n7c6_root=args.n7c6_root)
    write_dataset_report(out / "N8A_DATASET_REPORT.json", dataset_report)
    write_state_csv(out / "N8A_EKF_STATE_NODES.csv", dataset)
    fgo_rows, smoother_report = run_no_feedback_smoother(dataset)
    write_smoother_outputs(out / "N8A_FGO_DIAGNOSTIC_STATES.csv", out / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json", fgo_rows, smoother_report)
    evaluation = evaluate_no_feedback_fgo(ekf_states=dataset.to_rows(), fgo_states=fgo_rows)
    write_evaluation_report(out / "N8A_EVALUATION_REPORT.json", evaluation)
    preliminary = make_n8a_decision(backend=backend, registry=registry, dataset=dataset_report, smoother=smoother_report, evaluation=evaluation, figures={"required_figures_generated": True, "required_figures_nonempty": True})
    figures = generate_n8a_figures(figure_output_dir=figs, backend=backend, registry=registry, dataset=dataset_report, smoother=smoother_report, evaluation=evaluation, decision=preliminary)
    (out / "N8A_FIGURE_MANIFEST.json").write_text(json.dumps(figures, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision = make_n8a_decision(backend=backend, registry=registry, dataset=dataset_report, smoother=smoother_report, evaluation=evaluation, figures=figures)
    write_decision(out / "N8A_NO_FEEDBACK_FGO_DECISION_REPORT.json", decision)
    _write_case_review(out / "n8a_no_feedback_fgo_case_review.md", decision)
    print(json.dumps({"decision": decision, "backend": backend.get("selected_backend")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
