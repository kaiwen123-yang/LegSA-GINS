#!/usr/bin/env python3
"""Run N4H4E source-backed port visual validation.

中文说明：本 runner 只生成 runtime-only 图像和报告；不修改 solver，不提交图像，
不做 paper performance claim。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.visualization.legsa_v23_port_visual_loader import load_visual_inputs
from legsa_gins.visualization.legsa_v23_port_visual_plots import generate_visual_plots
from legsa_gins.visualization.legsa_v23_port_visual_report import write_visual_reports
from legsa_gins.visualization.legsa_v23_port_visual_sanity import build_visual_sanity_report, write_visual_sanity_report


def _default_figure_output_dir() -> Path:
    return Path("/mnt") / "c" / "Users" / "ykw" / "Desktop" / "LegSA-GINS" / "绘图验证" / "N4H4E_source_backed_port"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r3-root", default=str(Path.home() / "legsa_n4h4r3_port_clean_parity"))
    parser.add_argument("--r3a-root", default=str(Path.home() / "legsa_n4h4r3a_update_timeline"))
    parser.add_argument("--r3b-root", default=str(Path.home() / "legsa_n4h4r3b_overclose_audit"))
    parser.add_argument("--r3c-root", default=str(Path.home() / "legsa_n4h4r3c_metric_namespace"))
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h4e_visual_validation"))
    parser.add_argument("--figure-output-dir", default=str(_default_figure_output_dir()))
    parser.add_argument("--trace-path")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def run_pipeline(args: argparse.Namespace) -> dict:
    if not args.allow_run:
        raise RuntimeError("N4H4E visual validation requires --allow-run")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_visual_inputs(
        r3_root=args.r3_root,
        r3a_root=args.r3a_root,
        r3b_root=args.r3b_root,
        r3c_root=args.r3c_root,
        dual_root=args.dual_root,
        output_dir=output_dir,
        trace_path=args.trace_path,
    )
    missing = [name for name, ok in inputs["manifest"].items() if name.endswith("_found") and ok is False]
    if missing:
        raise FileNotFoundError("visual input evidence missing: " + ", ".join(missing))
    plot_report = generate_visual_plots(
        inputs,
        output_dir=output_dir,
        figure_output_dir=args.figure_output_dir,
        r3a_root=args.r3a_root,
        r3b_root=args.r3b_root,
    )
    sanity = build_visual_sanity_report(
        inputs=inputs,
        plot_report=plot_report,
        figure_output_dir=args.figure_output_dir,
    )
    write_visual_sanity_report(output_dir / "VISUAL_SANITY_REPORT.json", sanity)
    report = write_visual_reports(
        output_dir=output_dir,
        figure_output_dir=args.figure_output_dir,
        sanity=sanity,
        figure_manifest=plot_report,
        input_manifest=inputs["manifest"],
    )
    result = {
        "input_manifest": inputs["manifest"],
        "figure_manifest": {key: value for key, value in plot_report.items() if key != "errors"},
        "visual_sanity": sanity,
        "visual_report": report,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    run_pipeline(parse_args(argv or sys.argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
