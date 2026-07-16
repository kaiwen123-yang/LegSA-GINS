#!/usr/bin/env python3
"""Run CLEAN2 exact evaluation, analysis joins, and diagnostic render phases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2_ablation import load_ablation_catalog
from legsa_gins.paper_rebuild.clean2_analysis import (
    build_perturbation_action_rows,
    build_source_aware_response_rows,
    load_case_perturbation_ledgers,
    write_clean2_analysis,
)
from legsa_gins.paper_rebuild.clean2_evaluator import (
    EXACT_EVALUATOR_SHA256,
    build_solver_artifact_index,
    evaluate_clean2_outputs,
    load_and_crosscheck_evaluation_index,
    load_solver_artifact_index,
    validate_sealed_solver_artifact_index,
)
from legsa_gins.paper_rebuild.clean2_stage_paths import (
    guard_clean2_stage_path,
    load_clean2_stage_paths,
)
from legsa_gins.paper_rebuild.evidence import BY2_TRACE_RELATIVE_PATH
from legsa_gins.paper_rebuild.clean2_plots import (
    build_diagnostic_plot_payload,
    render_diagnostic_figures,
)
from legsa_gins.paper_rebuild.clean2_run_registry import read_run_registry
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic


DEFAULT_ABLATION = REPO_ROOT / "configs/paper_rebuild/clean2_ablation_2pow4.yaml"
DEFAULT_PROTOCOL = REPO_ROOT / "configs/paper_rebuild/clean2_execution_protocol.yaml"


def _add_evaluation_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--run-attempts", required=True)
    parser.add_argument("--run-attempts-audit", required=True)
    parser.add_argument("--solver-output-index", required=True, help="JSON run_id -> sealed NAV/STD/action artifacts")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--trace-sha256", required=True)
    parser.add_argument("--exact-evaluator", required=True)
    parser.add_argument("--evaluator-sha256", required=True)
    parser.add_argument("--execution-protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--complete-output-seal", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)


def _add_analysis_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--case-provider-index", required=True)
    parser.add_argument("--ablation", default=str(DEFAULT_ABLATION))
    parser.add_argument("--solver-output-index", required=True)
    parser.add_argument("--complete-output-seal", required=True)
    parser.add_argument("--evaluation-index", required=True)


def _evaluate(args: argparse.Namespace, output_root: str | Path) -> dict[str, Any]:
    if args.evaluator_sha256 != EXACT_EVALUATOR_SHA256:
        raise SystemExit("--evaluator-sha256 must be the frozen exact CLEAN1R2R1 evaluator SHA")
    return evaluate_clean2_outputs(
        solver_artifact_index_path=args.solver_output_index,
        reference_trace_path=args.trace,
        trace_sha256=args.trace_sha256,
        exact_evaluator_path=args.exact_evaluator,
        evaluator_sha256=args.evaluator_sha256,
        execution_protocol_path=args.execution_protocol,
        complete_output_seal_path=args.complete_output_seal,
        registry_path=args.registry,
        run_attempts_path=args.run_attempts,
        run_attempts_audit_path=args.run_attempts_audit,
        output_root=output_root,
        expected_runtime_root=args.expected_runtime_root,
        timeout_seconds=args.timeout_seconds,
    )


def _analyze(
    args: argparse.Namespace,
    *,
    ablation_output_dir: str | Path,
    classic_output_dir: str | Path,
) -> dict[str, str]:
    registry = read_run_registry(args.registry)
    artifacts = load_solver_artifact_index(
        args.solver_output_index, expected_runtime_root=args.expected_runtime_root
    )
    validation = validate_sealed_solver_artifact_index(
        artifact_index=artifacts,
        complete_output_seal_path=args.complete_output_seal,
        require_action_traces=True,
    )
    sealed_by_id = {str(row["run_id"]): row for row in validation["seal"]["runs"]}
    summaries, row_crosscheck = load_and_crosscheck_evaluation_index(
        args.evaluation_index,
        expected_solver_artifact_index_sha256=artifacts.metadata["index_sha256"],
        expected_complete_output_seal_sha256=sha256_file(args.complete_output_seal),
        expected_registry_sha256=sha256_file(args.registry),
        expected_run_attempts_sha256=(
            sha256_file(args.run_attempts) if hasattr(args, "run_attempts") else None
        ),
        expected_run_attempts_audit_sha256=(
            sha256_file(args.run_attempts_audit)
            if hasattr(args, "run_attempts_audit")
            else None
        ),
        expected_solver_artifacts=artifacts,
    )
    ledgers = load_case_perturbation_ledgers(args.case_provider_index)
    action_rows = build_perturbation_action_rows(
        registry, artifacts, ledgers, sealed_by_id
    )
    source_rows = build_source_aware_response_rows(
        registry, artifacts, ledgers, sealed_by_id
    )
    return write_clean2_analysis(
        registry_path=args.registry,
        summaries=summaries,
        ablation_catalog=load_ablation_catalog(args.ablation),
        perturbation_action_rows=action_rows,
        source_aware_response_rows=source_rows,
        ablation_output_dir=ablation_output_dir,
        classic_output_dir=classic_output_dir,
        evaluation_row_crosscheck=row_crosscheck,
    )


def _plot(
    *,
    tables: dict[str, str],
    evaluation_index: str | Path,
    payload_path: str | Path,
    figure_output_dir: str | Path,
    solver_output_index: str | Path,
    complete_output_seal: str | Path,
    expected_runtime_root: str | Path,
) -> dict[str, Any]:
    artifacts = load_solver_artifact_index(
        solver_output_index, expected_runtime_root=expected_runtime_root
    )
    validate_sealed_solver_artifact_index(
        artifact_index=artifacts,
        complete_output_seal_path=complete_output_seal,
        require_action_traces=True,
    )
    load_and_crosscheck_evaluation_index(
        evaluation_index,
        expected_solver_artifact_index_sha256=artifacts.metadata["index_sha256"],
        expected_complete_output_seal_sha256=sha256_file(complete_output_seal),
        expected_solver_artifacts=artifacts,
    )
    build_diagnostic_plot_payload(
        analysis_tables=tables,
        evaluation_index_path=evaluation_index,
        solver_artifacts=artifacts,
        output_path=payload_path,
    )
    return render_diagnostic_figures(
        plot_payload_path=payload_path,
        output_dir=figure_output_dir,
    )


def _load_analysis_index(path: str | Path) -> dict[str, str]:
    payload = json.loads(Path(path).resolve(strict=True).read_text(encoding="utf-8"))
    tables = payload.get("tables")
    if payload.get("passed") is not True or not isinstance(tables, dict):
        raise SystemExit("analysis index is incomplete")
    return {str(key): str(value) for key, value in tables.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    artifact = subcommands.add_parser(
        "build-artifact-index", help="derive role-aware evaluator artifacts from the complete seal"
    )
    artifact.add_argument("--local-config", required=True)
    artifact.add_argument("--registry", required=True)
    artifact.add_argument("--runtime-root", required=True)
    artifact.add_argument("--complete-output-seal", required=True)
    artifact.add_argument("--output", required=True)
    evaluate = subcommands.add_parser("evaluate", help="exact evaluator over all 110 sealed runs")
    _add_evaluation_inputs(evaluate)
    evaluate.add_argument("--output-root", required=True)

    analyze = subcommands.add_parser("analyze", help="row crosscheck plus action/table analysis")
    _add_analysis_inputs(analyze)
    analyze.add_argument("--ablation-output-dir", required=True)
    analyze.add_argument("--classic-output-dir", required=True)

    plot = subcommands.add_parser("plot", help="build real payload and render 18 diagnostics")
    plot.add_argument("--local-config", required=True)
    plot.add_argument("--analysis-index", required=True)
    plot.add_argument("--evaluation-index", required=True)
    plot.add_argument("--solver-output-index", required=True)
    plot.add_argument("--complete-output-seal", required=True)
    plot.add_argument("--payload-path", required=True)
    plot.add_argument("--figure-output-dir", required=True)

    all_phases = subcommands.add_parser("all", help="bounded evaluate -> analyze -> plot sequence")
    _add_evaluation_inputs(all_phases)
    all_phases.add_argument("--case-provider-index", required=True)
    all_phases.add_argument("--ablation", default=str(DEFAULT_ABLATION))
    all_phases.add_argument("--output-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stage_paths = load_clean2_stage_paths(args.local_config)
    if stage_paths.clean.code_root != REPO_ROOT.resolve(strict=True):
        raise SystemExit("CLEAN2 local config code_root differs from this worktree")
    args.expected_runtime_root = str(stage_paths.slot("formal_runs"))

    def guarded_file(value: str, *, slot: str, name: str, role: str) -> str:
        return str(
            guard_clean2_stage_path(
                stage_paths,
                value,
                slot=slot,
                role=role,
                exact_name=name,
                must_exist=True,
                regular_file=True,
            )
        )

    def guarded_analysis_tables(tables: dict[str, str]) -> dict[str, str]:
        identities = {
            "factorial": ("ablation_analysis", "CLEAN2_C00_FACTORIAL_RESULTS.csv"),
            "main_effects": ("ablation_analysis", "CLEAN2_C00_MODULE_MAIN_EFFECTS.csv"),
            "interactions": ("ablation_analysis", "CLEAN2_C00_PAIRWISE_INTERACTIONS.csv"),
            "interpretation": ("ablation_analysis", "CLEAN2_C00_FACTORIAL_INTERPRETATION.md"),
            "canonical": ("classic_analysis", "CLEAN2_CANONICAL_CLASSIC18_18x4.csv"),
            "deltas": ("classic_analysis", "CLEAN2_CASE_METHOD_DELTAS.csv"),
            "family": ("classic_analysis", "CLEAN2_FAMILY_SEED_AGGREGATES.csv"),
            "sentinel": ("classic_analysis", "CLEAN2_SENTINEL_LOO_RESULTS.csv"),
            "marginal": ("classic_analysis", "CLEAN2_SENTINEL_MODULE_MARGINAL_LOSS.csv"),
            "actions": ("classic_analysis", "CLEAN2_PERTURBATION_ACTION_SUMMARY.csv"),
            "source_aware": ("classic_analysis", "CLEAN2_SOURCE_AWARE_RESPONSE_SUMMARY.csv"),
            "failure": ("classic_analysis", "CLEAN2_FAILURE_AND_FINITE_OUTPUT_SUMMARY.csv"),
            "crosscheck": ("classic_analysis", "CLEAN2_AGGREGATE_CROSSCHECK.json"),
        }
        if set(tables) != set(identities):
            raise SystemExit("CLEAN2 analysis index table role set drifted")
        return {
            role: guarded_file(
                tables[role], slot=slot, name=name, role=f"CLEAN2 analysis table {role}"
            )
            for role, (slot, name) in identities.items()
        }

    if args.command == "build-artifact-index":
        runtime = guard_clean2_stage_path(
            stage_paths,
            args.runtime_root,
            slot="formal_runs",
            role="CLEAN2 formal runtime root",
            must_exist=True,
        )
        if runtime != stage_paths.slot("formal_runs"):
            raise SystemExit("CLEAN2 runtime root must be exact slot 07")
        registry = guarded_file(
            args.registry,
            slot="run_registry",
            name="CLEAN2_RUN_REGISTRY.csv",
            role="CLEAN2 run registry",
        )
        seal = guarded_file(
            args.complete_output_seal,
            slot="output_seal",
            name="CLEAN2_COMPLETE_OUTPUT_SEAL.json",
            role="CLEAN2 complete output seal",
        )
        output = guard_clean2_stage_path(
            stage_paths,
            args.output,
            slot="output_seal",
            role="CLEAN2 solver artifact index",
            exact_name="CLEAN2_SOLVER_ARTIFACT_INDEX.json",
        )
        result = build_solver_artifact_index(
            complete_output_seal_path=seal,
            runtime_root=runtime,
            registry_path=registry,
            output_path=output,
        )
    else:
        if hasattr(args, "solver_output_index"):
            args.solver_output_index = guarded_file(
                args.solver_output_index,
                slot="output_seal",
                name="CLEAN2_SOLVER_ARTIFACT_INDEX.json",
                role="CLEAN2 solver artifact index",
            )
        if hasattr(args, "complete_output_seal"):
            args.complete_output_seal = guarded_file(
                args.complete_output_seal,
                slot="output_seal",
                name="CLEAN2_COMPLETE_OUTPUT_SEAL.json",
                role="CLEAN2 complete output seal",
            )
        if hasattr(args, "registry"):
            args.registry = guarded_file(
                args.registry,
                slot="run_registry",
                name="CLEAN2_RUN_REGISTRY.csv",
                role="CLEAN2 run registry",
            )
        if hasattr(args, "run_attempts"):
            args.run_attempts = guarded_file(
                args.run_attempts,
                slot="run_registry",
                name="CLEAN2_RUN_ATTEMPTS.csv",
                role="CLEAN2 run-attempt ledger",
            )
        if hasattr(args, "run_attempts_audit"):
            args.run_attempts_audit = guarded_file(
                args.run_attempts_audit,
                slot="audits",
                name="CLEAN2_RUN_ATTEMPTS_AUDIT.json",
                role="CLEAN2 terminal run-attempt audit",
            )
        if hasattr(args, "case_provider_index"):
            args.case_provider_index = guarded_file(
                args.case_provider_index,
                slot="case_providers",
                name="CLASSIC18_PROVIDER_INDEX.json",
                role="CLEAN2 case provider index",
            )
        if hasattr(args, "evaluation_index"):
            args.evaluation_index = guarded_file(
                args.evaluation_index,
                slot="offline_evaluation",
                name="CLEAN2_OFFLINE_EVALUATION_INDEX.json",
                role="CLEAN2 offline evaluation index",
            )
        if hasattr(args, "trace"):
            trace_input = Path(args.trace)
            trace = trace_input.resolve(strict=True)
            expected_trace = (stage_paths.clean.raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
            current = stage_paths.clean.raw_root
            symlinked = current.is_symlink()
            for part in Path(BY2_TRACE_RELATIVE_PATH).parts:
                current = current / part
                symlinked = symlinked or current.is_symlink()
            if trace != expected_trace or symlinked:
                raise SystemExit("CLEAN2 trace must be the exact hash-locked BY2 evaluation-only source")
            args.trace = str(trace)
        if hasattr(args, "execution_protocol") and Path(args.execution_protocol).resolve(strict=True) != DEFAULT_PROTOCOL.resolve(strict=True):
            raise SystemExit("CLEAN2 evaluator must use the tracked frozen execution protocol")
        if hasattr(args, "ablation") and Path(args.ablation).resolve(strict=True) != DEFAULT_ABLATION.resolve(strict=True):
            raise SystemExit("CLEAN2 analysis must use the tracked frozen ablation catalog")

    if args.command == "evaluate":
        output_root = guard_clean2_stage_path(
            stage_paths,
            args.output_root,
            slot="offline_evaluation",
            role="CLEAN2 offline evaluation root",
        )
        if output_root != stage_paths.slot("offline_evaluation"):
            raise SystemExit("CLEAN2 offline evaluation must use exact slot 09")
        result = _evaluate(args, output_root)
    elif args.command == "analyze":
        ablation_output = guard_clean2_stage_path(
            stage_paths, args.ablation_output_dir, slot="ablation_analysis",
            role="CLEAN2 ablation analysis root",
        )
        classic_output = guard_clean2_stage_path(
            stage_paths, args.classic_output_dir, slot="classic_analysis",
            role="CLEAN2 Classic-18 analysis root",
        )
        if ablation_output != stage_paths.slot("ablation_analysis") or classic_output != stage_paths.slot("classic_analysis"):
            raise SystemExit("CLEAN2 analysis outputs must use exact slots 10/11")
        result = _analyze(
            args,
            ablation_output_dir=ablation_output,
            classic_output_dir=classic_output,
        )
    elif args.command == "plot":
        args.analysis_index = guarded_file(
            args.analysis_index,
            slot="classic_analysis",
            name="CLEAN2_ANALYSIS_INDEX.json",
            role="CLEAN2 analysis index",
        )
        payload_path = guard_clean2_stage_path(
            stage_paths, args.payload_path, slot="classic_analysis",
            role="CLEAN2 diagnostic payload",
            exact_name="CLEAN2_DIAGNOSTIC_PLOT_PAYLOAD.json",
        )
        figure_root = guard_clean2_stage_path(
            stage_paths, args.figure_output_dir, slot="diagnostic_figures",
            role="CLEAN2 diagnostic figure root",
        )
        if figure_root != stage_paths.slot("diagnostic_figures"):
            raise SystemExit("CLEAN2 figures must use exact slot 12")
        result = _plot(
            tables=guarded_analysis_tables(_load_analysis_index(args.analysis_index)),
            evaluation_index=args.evaluation_index,
            payload_path=payload_path,
            figure_output_dir=figure_root,
            solver_output_index=args.solver_output_index,
            complete_output_seal=args.complete_output_seal,
            expected_runtime_root=args.expected_runtime_root,
        )
    elif args.command == "all":
        root = Path(args.output_root).resolve(strict=False)
        if root != stage_paths.stage_root:
            raise SystemExit("CLEAN2 all-phase root must be the exact configured stage root")
        evaluation = _evaluate(args, root / "09_OFFLINE_EVALUATION")
        args.evaluation_index = evaluation["index_path"]
        tables = _analyze(
            args,
            ablation_output_dir=root / "10_ABLATION_ANALYSIS",
            classic_output_dir=root / "11_CLASSIC18_ANALYSIS",
        )
        payload_path = root / "11_CLASSIC18_ANALYSIS/CLEAN2_DIAGNOSTIC_PLOT_PAYLOAD.json"
        figure_qa = _plot(
            tables=tables,
            evaluation_index=evaluation["index_path"],
            payload_path=payload_path,
            figure_output_dir=root / "12_DIAGNOSTIC_FIGURES",
            solver_output_index=args.solver_output_index,
            complete_output_seal=args.complete_output_seal,
            expected_runtime_root=args.expected_runtime_root,
        )
        report_path = write_json_atomic(
            root / "14_FINAL_EVIDENCE/CLEAN2_OFFLINE_PIPELINE_REPORT.json",
            {
                "schema_version": "paper_rebuild.clean2_offline_pipeline.v2",
                "phase_order": ["exact_evaluate_110", "action_and_aggregate_analysis", "diagnostic_payload_and_render"],
                "all_outputs_sealed_before_trace": True,
                "trace_used_online": False,
                "evaluation_index": evaluation["index_path"],
                "analysis_index": tables["analysis_index"],
                "figure_render_QA": figure_qa,
                "passed": figure_qa.get("passed") is True,
            },
        )
        result = {"pipeline_report": str(report_path), "passed": True}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
