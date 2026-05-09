#!/usr/bin/env python3
"""Run N4H4R3C metric namespace split audit.

中文说明：本 runner 只读取 runtime-only NAV/trace/reference artifacts，拆分
port-vs-final_v23 parity 与 trace absolute evaluation；不运行 solver 调参、
不做 output-only correction、不删除 epoch。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.error_series_parity import load_official_error_series
from legsa_gins.evaluation.legsa_v23_port_absolute_trace_eval import evaluate_nav_vs_trace
from legsa_gins.evaluation.legsa_v23_port_final_v23_parity_eval import evaluate_port_vs_final_v23_nav
from legsa_gins.evaluation.legsa_v23_port_metric_namespace_decision import make_metric_namespace_decision
from legsa_gins.evaluation.legsa_v23_port_overclose_audit import EXTERNAL_CLEAN_SUMMARY
from legsa_gins.evaluation.legsa_v23_port_parity_vs_absolute import compare_parity_and_absolute
from legsa_gins.evaluation.official_case_review_reproduction import (
    load_trace_reference_for_case,
    parse_kfgins_nav,
    reconstruct_reference_from_error_series,
)


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _newest(candidates: list[Path]) -> Path | None:
    existing = [path for path in candidates if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _find_output_file(roots: list[str | Path], names: list[str]) -> Path | None:
    candidates: list[Path] = []
    for root_value in roots:
        root = Path(root_value)
        if not root.exists():
            continue
        for name in names:
            direct = root / "run" / name
            candidates.append(direct)
            candidates.extend(root.glob(f"**/{name}"))
    return _newest(candidates)


def _find_port_nav(args: argparse.Namespace) -> dict[str, Any]:
    roots = [args.r3b_root, args.r3a_root, args.r3_root]
    eval_nav = _find_output_file(roots, ["EVAL_NAV.csv"])
    nav = _find_output_file(roots, ["LegSA_PORT_NAV.nav"])
    std = _find_output_file(roots, ["LegSA_PORT_STD.csv", "KF_GINS_STD.txt"])
    chosen = eval_nav or nav
    return {
        "port_nav_path": str(chosen) if chosen else None,
        "port_nav_role": "port_eval_nav_writer_output" if eval_nav else "port_nav_writer_output",
        "port_std_path": str(std) if std else None,
        "port_nav_missing": chosen is None,
    }


def _dual_artifact_group(dual_root: str | Path, n4h2_artifacts_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(dual_root)
    artifacts = {
        name: str(root / name)
        for name in ["KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "summary.json", "error_series.csv"]
        if (root / name).exists()
    }
    group: dict[str, Any] = {
        "group_id": "dual_final_v23_nominal",
        "role_alias": "dual_final_v23_nominal",
        "artifacts": artifacts,
    }
    if n4h2_artifacts_root:
        group["n4h2_artifacts_root"] = str(n4h2_artifacts_root)
    return group


def _recover_trace_reference(args: argparse.Namespace) -> dict[str, Any]:
    if args.trace_path:
        path = Path(args.trace_path)
        if path.exists():
            return {
                "reference_rows": str(path),
                "reference_source": "provided_trace_path_runtime_only",
                "trace_solver_input": False,
                "trace_evaluation_only": True,
                "evidence_status": "reference_path_available",
            }

    group = _dual_artifact_group(args.dual_root)
    bundle = load_trace_reference_for_case(group, Path.home() / "KF-GINS")
    if bundle.get("reference_rows") and bundle.get("reference_source") == "official_error_series_reference_fields":
        return bundle

    dual_nav = Path(args.dual_root) / "KF_GINS_Navresult.nav"
    error_series = Path(args.dual_root) / "error_series.csv"
    if dual_nav.exists() and error_series.exists():
        nav_rows = parse_kfgins_nav(dual_nav)
        error_rows = load_official_error_series(error_series)
        reference_rows = reconstruct_reference_from_error_series(nav_rows, error_rows)
        if reference_rows:
            return {
                "reference_rows": reference_rows,
                "reference_source": "dual_official_nav_plus_error_series_reconstruction",
                "trace_solver_input": False,
                "trace_evaluation_only": True,
                "evidence_status": "reference_loaded",
                "final_v23_output_solver_input": False,
                "reference_reconstruction_depends_on_port_output": False,
            }

    if bundle.get("reference_rows"):
        return bundle

    return {
        "reference_rows": [],
        "reference_source": "evidence_missing",
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "evidence_status": "evidence_missing",
    }


def _r3b_external_baseline(args: argparse.Namespace) -> dict[str, Any]:
    overclose = _load_json(Path(args.r3b_root) / "PORT_OVERCLOSE_AUDIT_REPORT.json")
    return {
        **EXTERNAL_CLEAN_SUMMARY,
        "namespace": "external_clean_kfgins_vs_trace_absolute",
        "solver_output_role": "external_clean_kfgins_nav",
        "reference_role": "trace_reference_trajectory_eval_only",
        "r3b_external_closeness_failed": overclose.get("external_closeness_failed"),
        "used_for_r3b_external_closeness_check": bool(overclose),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def _write_missing(path: Path, role: str) -> dict[str, Any]:
    report = {
        "phase": "N4H4R3C",
        "solver_output_role": role,
        "absolute_trace_evaluation_status": "evidence_missing",
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(path, report)
    return report


def _write_markdown(path: Path, reports: dict[str, Any]) -> None:
    parity = reports.get("port_vs_finalv23", {})
    final_abs = reports.get("finalv23_vs_trace", {})
    port_abs = reports.get("port_vs_trace", {})
    comparison = reports.get("comparison", {})
    decision = reports.get("decision", {})
    lines = [
        "# N4H4R3C Metric Namespace Audit",
        "",
        "This audit separates parity-to-baseline-output metrics from absolute trace/reference metrics.",
        "It does not modify solver output, tune parameters, delete epochs, or make a paper performance claim.",
        "",
        "## A. port_vs_final_v23_nav_parity",
        "",
        f"- aligned_count: {parity.get('aligned_count')}",
        f"- horizontal_rmse_m: {parity.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {parity.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {parity.get('yaw_rmse_deg')}",
        f"- roll_rmse_deg: {parity.get('roll_rmse_deg')}",
        f"- pitch_rmse_deg: {parity.get('pitch_rmse_deg')}",
        f"- parity_small: {parity.get('parity_small')}",
        "",
        "## B. port_vs_trace_absolute",
        "",
        f"- status: {port_abs.get('absolute_trace_evaluation_status')}",
        f"- horizontal_rmse_m: {port_abs.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {port_abs.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {port_abs.get('yaw_rmse_deg')}",
        "",
        "## C. final_v23_vs_trace_absolute",
        "",
        f"- status: {final_abs.get('absolute_trace_evaluation_status')}",
        f"- official_summary_reproduced: {final_abs.get('official_summary_reproduced')}",
        f"- horizontal_rmse_m: {final_abs.get('horizontal_rmse_m')}",
        f"- up_rmse_m: {final_abs.get('up_rmse_m')}",
        f"- yaw_rmse_deg: {final_abs.get('yaw_rmse_deg')}",
        "",
        "## Comparison",
        "",
        f"- parity_to_finalv23_small: {comparison.get('parity_to_finalv23_small')}",
        f"- port_absolute_close_to_finalv23_absolute: {comparison.get('port_absolute_close_to_finalv23_absolute')}",
        f"- r3b_external_closeness_misuse_detected: {comparison.get('r3b_external_closeness_misuse_detected')}",
        f"- corrected_parity_status: {comparison.get('corrected_parity_status')}",
        "",
        "## Decision",
        "",
        f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
        f"- engineering_backbone_candidate: {decision.get('engineering_backbone_candidate')}",
        "- paper_performance_claim: false",
        "- no_outperform_final_v23_claim: true",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if not args.allow_run:
        raise RuntimeError("N4H4R3C runner requires --allow-run for explicit runtime artifact reads")

    port = _find_port_nav(args)
    final_nav = Path(args.dual_root) / "KF_GINS_Navresult.nav"
    final_std = Path(args.dual_root) / "KF_GINS_STD.txt"
    trace_bundle = _recover_trace_reference(args)

    if not port["port_nav_path"]:
        raise RuntimeError("port NAV/EVAL_NAV not found in R3/R3A/R3B roots")
    if not final_nav.exists():
        raise RuntimeError("dual_final_v23 NAV not found under dual root")

    parity = evaluate_port_vs_final_v23_nav(port["port_nav_path"], final_nav, output)
    if trace_bundle.get("reference_rows"):
        final_abs = evaluate_nav_vs_trace(
            final_nav,
            final_std if final_std.exists() else None,
            trace_bundle,
            output,
            "final_v23_nav",
        )
        port_abs = evaluate_nav_vs_trace(
            port["port_nav_path"],
            port.get("port_std_path"),
            trace_bundle,
            output,
            "port_nav",
        )
    else:
        final_abs = _write_missing(output / "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json", "final_v23_nav")
        port_abs = _write_missing(output / "PORT_VS_TRACE_ABSOLUTE_REPORT.json", "port_nav")

    comparison = compare_parity_and_absolute(
        parity,
        port_abs,
        final_abs,
        _r3b_external_baseline(args),
        output,
    )
    decision = make_metric_namespace_decision({"comparison": comparison}, output)
    reports = {
        "phase": "N4H4R3C",
        "port_locator": port,
        "trace_reference": {
            "reference_source": trace_bundle.get("reference_source"),
            "evidence_status": trace_bundle.get("evidence_status"),
            "trace_solver_input": False,
            "trace_evaluation_only": True,
        },
        "port_vs_finalv23": parity,
        "finalv23_vs_trace": final_abs,
        "port_vs_trace": port_abs,
        "comparison": comparison,
        "decision": decision,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(output / "PORT_METRIC_NAMESPACE_RUN_REPORT.json", reports)
    _write_markdown(output / "n4h4r3c_metric_namespace_audit.md", reports)
    return reports


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(Path.home() / "legsa_n4h2g_clean_replay"))
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--r3-root", default=str(Path.home() / "legsa_n4h4r3_port_clean_parity"))
    parser.add_argument("--r3a-root", default=str(Path.home() / "legsa_n4h4r3a_update_timeline"))
    parser.add_argument("--r3b-root", default=str(Path.home() / "legsa_n4h4r3b_overclose_audit"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h4r3c_metric_namespace"))
    parser.add_argument("--trace-path")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run_pipeline(parse_args(argv or sys.argv[1:]))
    print(json.dumps(report["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
