#!/usr/bin/env python3
"""Run N4H4E1 STD unit and plot semantics fix.

中文说明：该 runner 只生成 runtime-only 报告和图像；默认输出在 /tmp，
真实 Windows 桌面输出只能通过命令行参数传入，不能写入 tracked 常量。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.visualization.legsa_v23_port_plot_semantics_fix import generate_plot_semantics_fix
from legsa_gins.visualization.legsa_v23_port_std_unit_audit import (
    load_std_file,
    make_std_unit_audit_report,
    write_std_unit_audit_report,
)
from legsa_gins.visualization.legsa_v23_port_visual_e1_report import write_visual_e1_reports
from legsa_gins.visualization.legsa_v23_port_visual_loader import load_visual_inputs


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n4h4e-root", default=str(Path.home() / "legsa_n4h4e_visual_validation"))
    parser.add_argument("--r3-root", default=str(Path.home() / "legsa_n4h4r3_port_clean_parity"))
    parser.add_argument("--r3a-root", default=str(Path.home() / "legsa_n4h4r3a_update_timeline"))
    parser.add_argument("--r3b-root", default=str(Path.home() / "legsa_n4h4r3b_overclose_audit"))
    parser.add_argument("--r3c-root", default=str(Path.home() / "legsa_n4h4r3c_metric_namespace"))
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--report-output-dir", default="/tmp/legsa_n4h4e1_std_unit_plot_fix_reports")
    parser.add_argument("--figure-output-dir", default="/tmp/legsa_n4h4e1_std_unit_plot_fix_figures")
    parser.add_argument("--trace-path")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def run_pipeline(args: argparse.Namespace) -> dict:
    if not args.allow_run:
        raise RuntimeError("N4H4E1 visual fix requires --allow-run")
    report_dir = Path(args.report_output_dir)
    figure_dir = Path(args.figure_output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    inputs = load_visual_inputs(
        r3_root=args.r3_root,
        r3a_root=args.r3a_root,
        r3b_root=args.r3b_root,
        r3c_root=args.r3c_root,
        dual_root=args.dual_root,
        output_dir=report_dir,
        trace_path=args.trace_path,
    )
    missing = [name for name, ok in inputs["manifest"].items() if name.endswith("_found") and ok is False]
    if missing:
        raise FileNotFoundError("N4H4E1 visual input evidence missing: " + ", ".join(missing))

    port_std = load_std_file(inputs.get("port_std_path"), "source_backed_port_core")
    final_std = load_std_file(inputs.get("final_v23_std_path"), "final_v23_reference_baseline")
    std_report = make_std_unit_audit_report(
        port_std_rows=port_std,
        finalv23_std_rows=final_std,
        repo_root=ROOT,
    )
    write_std_unit_audit_report(report_dir / "STD_UNIT_AUDIT_REPORT.json", std_report)

    legacy_manifest = _load_json(Path(args.n4h4e_root) / "FIGURE_MANIFEST.json")
    plot_report = generate_plot_semantics_fix(
        inputs=inputs,
        std_unit_report=std_report,
        figure_output_dir=figure_dir,
        report_output_dir=report_dir,
        legacy_figure_manifest=legacy_manifest,
    )
    visual_report = write_visual_e1_reports(
        report_output_dir=report_dir,
        figure_output_dir=figure_dir,
        std_unit_report=std_report,
        plot_report=plot_report,
    )
    result = {
        "std_unit_report": std_report,
        "plot_semantics_report": plot_report,
        "visual_e1_report": visual_report,
    }
    print(json.dumps(visual_report, indent=2, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    run_pipeline(parse_args(argv or sys.argv[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
