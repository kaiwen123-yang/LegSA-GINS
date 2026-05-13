#!/usr/bin/env python3
"""Run N7C6A final visual/metric sanity review.

中文说明：N7C6A 只做最终图像、指标口径、图名和合同一致性审查；
不改算法、不调参、不改 N7C6 结果。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.go2_prior.go2_n7c6_final_decision import make_n7c6a_final_decision, write_n7c6a_final_decision
from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import (
    build_n7c6a_visual_input_manifest,
    read_json,
    write_json,
    write_n7c6a_visual_input_manifest,
)
from legsa_gins.go2_prior.go2_n7c6_final_visual_plots import generate_n7c6a_readable_figures
from legsa_gins.go2_prior.go2_n7c6_metric_semantic_guard import (
    build_metric_semantic_guard_report,
    write_metric_semantic_guard_report,
)
from legsa_gins.go2_prior.go2_n7c6_plot_label_readability import (
    build_plot_label_readability_report,
    write_plot_label_readability_report,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n7c6-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--figure-output-dir", required=True)
    parser.add_argument("--allow-run", action="store_true")
    parser.add_argument("--rerun-missing-timeseries", default="true")
    return parser.parse_args(argv)


def _write_case_review(path: Path, decision: dict[str, Any], semantic: dict[str, Any], readability: dict[str, Any], figures: dict[str, Any]) -> None:
    lines = [
        "# N7C6A final review",
        "",
        f"- decision: {decision.get('status')}",
        f"- metric semantics: {semantic.get('metric_semantic_status')}",
        f"- original semantic issues: {len(semantic.get('original_issues', []))}",
        f"- plot readability: {readability.get('plot_label_readability_status')}",
        f"- readable figures: {figures.get('figure_count_total')}",
        "- N7C6A only clarifies figure/metric semantics and does not change solver math.",
        "- Go2 proprioceptive joint factor remains observation, not truth.",
        "- No trace/final_v23 solver input, no FGO, no output-only correction, no paper claim.",
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

    input_manifest = build_n7c6a_visual_input_manifest(args.n7c6_root)
    write_n7c6a_visual_input_manifest(out / "N7C6A_VISUAL_INPUT_MANIFEST.json", input_manifest)
    semantic = build_metric_semantic_guard_report(args.n7c6_root)
    write_metric_semantic_guard_report(out / "N7C6A_METRIC_SEMANTIC_GUARD_REPORT.json", semantic)
    readability = build_plot_label_readability_report(args.n7c6_root)
    write_plot_label_readability_report(out / "N7C6A_PLOT_LABEL_READABILITY_REPORT.json", readability)

    n7c6_decision = read_json(Path(args.n7c6_root) / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json")
    nis = read_json(Path(args.n7c6_root) / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json")
    figures = generate_n7c6a_readable_figures(
        n7c6_root=args.n7c6_root,
        figure_output_dir=figs,
        decision_report=n7c6_decision,
        semantic_report=semantic,
        readability_report=readability,
    )
    write_json(out / "N7C6A_FIGURE_MANIFEST.json", figures)
    decision = make_n7c6a_final_decision(
        input_manifest=input_manifest,
        semantic_report=semantic,
        readability_report=readability,
        figure_manifest=figures,
        n7c6_decision=n7c6_decision,
        nis_report=nis,
    )
    write_n7c6a_final_decision(str(out / "N7C6A_FINAL_REVIEW_DECISION_REPORT.json"), decision)
    _write_case_review(out / "n7c6a_final_review_case_review.md", decision, semantic, readability, figures)
    print(json.dumps({"decision": decision, "figure_count": figures.get("figure_count_total")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
