#!/usr/bin/env python3
"""Run N7C6 Go2 proprioceptive joint observation factor evaluation.

中文说明：N7C6 只受控评估 roll/pitch + horizontal velocity 本体观测因子；
Go2 body-state 不是 truth，position/yaw/vertical velocity prior 始终禁用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_decision import (
    make_n7c6_joint_factor_decision,
    write_n7c6_joint_factor_decision,
)
from legsa_gins.go2_prior.go2_n7c6_visual_plots import generate_n7c6_visual_plots
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_ablation import (
    compare_n7c6_joint_variants,
    run_n7c6_joint_factor_matrix,
    write_n7c6_ablation_artifacts,
)
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_builder import (
    build_and_write_joint_factor_priors,
)
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_jacobian import (
    write_joint_factor_jacobian_contract,
)
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_nis import (
    build_n7c6_joint_factor_nis_report,
    write_n7c6_joint_factor_nis_report,
)
from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_policy import (
    REQUIRED_N7C6_VARIANT_IDS,
    build_n7c6_joint_factor_matrix,
)
from legsa_gins.raw_gnss.raw_doppler_visual_loader import find_factor_csv


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7a-root", required=True)
    parser.add_argument("--n7c-root", required=True)
    parser.add_argument("--n7c2-root", required=True)
    parser.add_argument("--n7c4-root", required=True)
    parser.add_argument("--n7c5-root", required=True)
    parser.add_argument("--n7c5a-root", required=True)
    parser.add_argument("--n7b5-root", required=True)
    parser.add_argument("--n5b-root", required=True)
    parser.add_argument("--n6b-root", required=True)
    parser.add_argument("--clean-root", required=True)
    parser.add_argument("--dual-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--run-stress", default="true")
    return parser.parse_args(argv)


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _require_n7c5a_passed(n7c5a_root: str | Path) -> dict[str, Any]:
    decision = _read_json(Path(n7c5a_root) / "N7C5A_VISUAL_DECISION_REPORT.json")
    if decision.get("status") != "n7c5_visual_review_passed":
        raise SystemExit(
            "N7C5A visual review has not passed; stop before N7C6. "
            f"status={decision.get('status')}"
        )
    return decision


def _find_go2_body_state(n7a_root: str | Path) -> Path:
    root = Path(n7a_root)
    candidate = root / "GO2_BODY_STATE_STANDARDIZED.csv"
    if candidate.exists():
        return candidate
    matches = sorted(root.rglob("GO2_BODY_STATE_STANDARDIZED.csv"))
    if matches:
        return matches[0]
    raise FileNotFoundError("GO2_BODY_STATE_STANDARDIZED.csv missing under N7A root")


def _find_horizontal_fixed_1p0(n7c4_root: str | Path, n7c_root: str | Path, n7b5_root: str | Path) -> Path:
    candidates = [
        Path(n7c4_root) / "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_1P0_PRIORS.csv",
        Path(n7c_root) / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv",
        Path(n7b5_root) / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for root in [Path(n7c4_root), Path(n7c_root), Path(n7b5_root)]:
        matches = sorted(root.rglob("*HORIZONTAL_VELOCITY*PRIORS*.csv"))
        if matches:
            return matches[0]
    raise FileNotFoundError("Go2 horizontal velocity prior CSV missing")


def _write_case_review(
    path: str | Path,
    *,
    n7c5a_decision: dict[str, Any],
    prior_report: dict[str, Any],
    jacobian_report: dict[str, Any],
    nis_report: dict[str, Any],
    comparison: dict[str, Any],
    decision: dict[str, Any],
    figures: dict[str, Any],
) -> None:
    lines = [
        "# N7C6 Go2 proprioceptive joint observation factor",
        "",
        f"- N7C5A visual decision: {n7c5a_decision.get('status')}",
        f"- N7C6 decision: {decision.get('status')}",
        f"- recommended_default: {decision.get('recommended_default')}",
        f"- sequential_equivalent: {prior_report.get('sequential_equivalent')}",
        f"- jacobian toy check: {jacobian_report.get('finite_difference_check_status')}",
        f"- NIS variants: {len(nis_report.get('variants', {}))}",
        f"- comparison keys: {list(comparison.get('comparisons', {}).keys())}",
        f"- figures generated: {figures.get('figure_count_total')}",
        "- Go2 roll/pitch/horizontal velocity are proprioceptive observations, not truth.",
        "- Go2 position/yaw/vertical velocity priors remain disabled.",
        "- No trace/final_v23 tuning, no output-only correction, no FGO, no paper performance claim.",
    ]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.allow_run:
        raise SystemExit("--allow-run is required for N7C6 runtime execution")
    out = Path(args.output_dir)
    figs = Path(args.figure_output_dir)
    out.mkdir(parents=True, exist_ok=True)
    figs.mkdir(parents=True, exist_ok=True)

    n7c5a_decision = _require_n7c5a_passed(args.n7c5a_root)
    go2_body_state_csv = _find_go2_body_state(args.n7a_root)
    horizontal_prior_csv = _find_horizontal_fixed_1p0(args.n7c4_root, args.n7c_root, args.n7b5_root)
    raw_doppler_factor_csv = find_factor_csv(args.n5b_root)

    prior_paths, prior_report = build_and_write_joint_factor_priors(
        output_dir=out,
        go2_body_state_csv=go2_body_state_csv,
        horizontal_prior_csv=horizontal_prior_csv,
    )
    matrix = build_n7c6_joint_factor_matrix(
        output_dir=out,
        raw_doppler_factor_path=raw_doppler_factor_csv,
        prior_paths=prior_paths,
        run_stress=_truthy(args.run_stress),
    )
    _runs, summaries = run_n7c6_joint_factor_matrix(
        matrix,
        clean_root=args.clean_root,
        exe=args.exe,
        output_dir=out,
        dual_reference=args.dual_root,
    )
    comparison = compare_n7c6_joint_variants(summaries)
    write_n7c6_ablation_artifacts(output_dir=out, matrix=matrix, summaries=summaries, comparison=comparison)
    nis_report = build_n7c6_joint_factor_nis_report(output_dir=out, variant_ids=REQUIRED_N7C6_VARIANT_IDS)
    write_n7c6_joint_factor_nis_report(out / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json", nis_report)
    jacobian_report = write_joint_factor_jacobian_contract(
        out / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_JACOBIAN_REPORT.json"
    )
    preliminary = make_n7c6_joint_factor_decision(
        comparison_report=comparison,
        nis_report=nis_report,
        figure_manifest={},
    )
    figures = generate_n7c6_visual_plots(
        figure_output_dir=figs,
        output_dir=out,
        variant_summaries=summaries,
        comparison_report=comparison,
        nis_report=nis_report,
        decision=preliminary,
    )
    _write_json(out / "N7C6_FIGURE_MANIFEST.json", figures)
    decision = make_n7c6_joint_factor_decision(
        comparison_report=comparison,
        nis_report=nis_report,
        figure_manifest=figures,
    )
    write_n7c6_joint_factor_decision(out / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", decision)
    _write_case_review(
        out / "n7c6_go2_proprioceptive_joint_factor_case_review.md",
        n7c5a_decision=n7c5a_decision,
        prior_report=prior_report,
        jacobian_report=jacobian_report,
        nis_report=nis_report,
        comparison=comparison,
        decision=decision,
        figures=figures,
    )
    run_report = {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "input_roles": {
            "n7a_root": "N7A_runtime_report_root",
            "n7c_root": "N7C_runtime_report_root",
            "n7c2_root": "N7C2_runtime_report_root",
            "n7c4_root": "N7C4_runtime_report_root",
            "n7c5_root": "N7C5_runtime_report_root",
            "n7c5a_root": "N7C5A_runtime_report_root",
            "n7b5_root": "N7B5_runtime_report_root",
            "n5b_root": "N5B_runtime_report_root",
            "n6b_root": "N6B_runtime_report_root",
            "clean_root": "clean_runtime_root",
            "dual_root": "dual_reference_runtime_root",
            "output_dir": "N7C6_runtime_output_root",
            "figure_output_dir": "N7C6_runtime_figure_root",
        },
        "n7c5a_decision": n7c5a_decision,
        "prior_build": prior_report,
        "matrix": matrix,
        "variant_summaries": {"variants": summaries, "paper_performance_claim": False},
        "comparison": comparison,
        "nis": nis_report,
        "jacobian_contract": jacobian_report,
        "decision": decision,
        "figure_manifest": figures,
        "go2_not_truth": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }
    _write_json(out / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_RUN_REPORT.json", run_report)
    print(
        json.dumps(
            {
                "n7c5a_decision": n7c5a_decision,
                "prior_build": prior_report,
                "jacobian": jacobian_report,
                "nis": nis_report,
                "decision": decision,
                "figures": figures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
