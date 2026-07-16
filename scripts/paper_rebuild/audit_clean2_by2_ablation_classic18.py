#!/usr/bin/env python3
"""CLEAN2 audit/checkpoint CLI with an explicitly requested one-shot export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.clean2_ablation import load_ablation_catalog
from legsa_gins.paper_rebuild.clean2_classic_cases import load_classic_case_catalog
from legsa_gins.paper_rebuild.clean2_case_provider import validate_case_provider_index
from legsa_gins.paper_rebuild.clean2_evidence import (
    audit_clean2_formal_invariants,
    build_clean2_final_zip,
    build_clean2_terminal_gate_manifest,
    validate_clean2_terminal_gate,
    validate_complete_output_seal,
)
from legsa_gins.paper_rebuild.clean2_evaluator import (
    EXACT_EVALUATOR_SHA256,
    EXPECTED_TRACE_SHA256,
    load_and_crosscheck_evaluation_index,
    load_solver_artifact_index,
    validate_sealed_solver_artifact_index,
)
from legsa_gins.paper_rebuild.clean2_run_registry import read_run_registry, validate_run_registry_rows
from legsa_gins.paper_rebuild.clean2_stage_paths import (
    guard_clean2_export_root,
    guard_clean2_stage_path,
    load_clean2_stage_paths,
)
from legsa_gins.paper_rebuild.evidence import verify_by2_raw_22, write_raw_audit
from legsa_gins.paper_rebuild.final_v23_clean_input import raw_checkpoint_from_audit
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", required=True)
    parser.add_argument("--ablation", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_ablation_2pow4.yaml"))
    parser.add_argument("--mapping", default=str(REPO_ROOT / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml"))
    parser.add_argument("--registry")
    parser.add_argument("--case-provider-index")
    parser.add_argument("--complete-output-seal")
    parser.add_argument("--solver-artifact-index")
    parser.add_argument("--runtime-root")
    parser.add_argument("--invariants-output")
    parser.add_argument("--raw-root")
    parser.add_argument("--raw-hash-lock")
    parser.add_argument("--raw-lock-sha256")
    parser.add_argument(
        "--raw-phase",
        choices=("pre_provider", "post_generation", "post_provider", "post_run"),
    )
    parser.add_argument("--raw-audit-csv")
    parser.add_argument("--raw-checkpoint-json")
    parser.add_argument("--final-export-stage-root")
    parser.add_argument("--final-export-root")
    parser.add_argument("--final-export-timestamp")
    parser.add_argument("--offline-evaluation-index")
    parser.add_argument("--analysis-index")
    parser.add_argument("--figure-dir")
    parser.add_argument("--terminal-gate-output")
    parser.add_argument("--terminal-gate")
    parser.add_argument("--attempts")
    parser.add_argument("--attempts-audit")
    parser.add_argument("--raw-pre-provider-checkpoint")
    parser.add_argument("--raw-post-provider-checkpoint")
    parser.add_argument("--raw-post-run-checkpoint")
    parser.add_argument("--c00-structural-gate")
    parser.add_argument("--formal-invariants")
    parser.add_argument("--aggregate-crosscheck")
    parser.add_argument("--figure-manifest")
    parser.add_argument("--figure-qa")
    parser.add_argument("--final-review")
    parser.add_argument("--full-report-json")
    parser.add_argument("--full-report-md")
    args = parser.parse_args(argv)
    stage_paths = load_clean2_stage_paths(args.local_config)
    if stage_paths.clean.code_root != REPO_ROOT.resolve(strict=True):
        raise SystemExit("CLEAN2 local config code_root differs from this worktree")
    if Path(args.ablation).resolve(strict=True) != (REPO_ROOT / "configs/paper_rebuild/clean2_ablation_2pow4.yaml").resolve(strict=True):
        raise SystemExit("CLEAN2 audit must use the tracked frozen ablation catalog")
    if Path(args.mapping).resolve(strict=True) != (REPO_ROOT / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml").resolve(strict=True):
        raise SystemExit("CLEAN2 audit must use the tracked frozen Classic-18 mapping")

    def guarded_file(
        value: str,
        *,
        slot: str,
        name: str,
        role: str,
        must_exist: bool = True,
    ) -> str:
        return str(
            guard_clean2_stage_path(
                stage_paths,
                value,
                slot=slot,
                role=role,
                exact_name=name,
                must_exist=must_exist,
                regular_file=must_exist,
            )
        )

    fixed_files = (
        ("registry", "run_registry", "CLEAN2_RUN_REGISTRY.csv"),
        ("attempts", "run_registry", "CLEAN2_RUN_ATTEMPTS.csv"),
        ("attempts_audit", "audits", "CLEAN2_RUN_ATTEMPTS_AUDIT.json"),
        ("case_provider_index", "case_providers", "CLASSIC18_PROVIDER_INDEX.json"),
        ("complete_output_seal", "output_seal", "CLEAN2_COMPLETE_OUTPUT_SEAL.json"),
        ("solver_artifact_index", "output_seal", "CLEAN2_SOLVER_ARTIFACT_INDEX.json"),
        ("offline_evaluation_index", "offline_evaluation", "CLEAN2_OFFLINE_EVALUATION_INDEX.json"),
        ("analysis_index", "classic_analysis", "CLEAN2_ANALYSIS_INDEX.json"),
        ("c00_structural_gate", "audits", "CLEAN2_C00_STRUCTURAL_GATE.json"),
        ("formal_invariants", "audits", "CLEAN2_FORMAL_INVARIANTS.json"),
        ("aggregate_crosscheck", "classic_analysis", "CLEAN2_AGGREGATE_CROSSCHECK.json"),
        ("figure_manifest", "diagnostic_figures", "CLEAN2_FIGURE_MANIFEST.csv"),
        ("figure_qa", "diagnostic_figures", "CLEAN2_FIGURE_RENDER_QA.json"),
        ("final_review", "audits", "CLEAN2_FINAL_REVIEW.json"),
        ("full_report_json", "final_evidence", "CLEAN2_FULL_REPORT.json"),
        ("full_report_md", "final_evidence", "CLEAN2_FULL_REPORT.md"),
        ("terminal_gate", "final_evidence", "CLEAN2_TERMINAL_GATE.json"),
    )
    for field, slot, name in fixed_files:
        value = getattr(args, field)
        if value:
            setattr(args, field, guarded_file(value, slot=slot, name=name, role=f"CLEAN2 {field}"))
    if args.invariants_output:
        args.invariants_output = guarded_file(
            args.invariants_output,
            slot="audits",
            name="CLEAN2_FORMAL_INVARIANTS.json",
            role="CLEAN2 formal invariants output",
            must_exist=False,
        )
    if args.terminal_gate_output:
        args.terminal_gate_output = guarded_file(
            args.terminal_gate_output,
            slot="final_evidence",
            name="CLEAN2_TERMINAL_GATE.json",
            role="CLEAN2 terminal gate output",
            must_exist=False,
        )
    for field, phase in (
        ("raw_pre_provider_checkpoint", "pre_provider"),
        ("raw_post_provider_checkpoint", "post_provider"),
        ("raw_post_run_checkpoint", "post_run"),
    ):
        value = getattr(args, field)
        if value:
            setattr(
                args,
                field,
                guarded_file(
                    value,
                    slot="raw_audits",
                    name=f"CLEAN2_RAW_{phase.upper()}_CHECKPOINT.json",
                    role=f"CLEAN2 raw {phase} checkpoint",
                ),
            )
    if args.runtime_root:
        runtime = guard_clean2_stage_path(
            stage_paths,
            args.runtime_root,
            slot="formal_runs",
            role="CLEAN2 formal runtime root",
            must_exist=True,
        )
        if runtime != stage_paths.slot("formal_runs"):
            raise SystemExit("CLEAN2 runtime root must be exact slot 07")
        args.runtime_root = str(runtime)
    if args.figure_dir:
        figure_root = guard_clean2_stage_path(
            stage_paths,
            args.figure_dir,
            slot="diagnostic_figures",
            role="CLEAN2 figure root",
            must_exist=True,
        )
        if figure_root != stage_paths.slot("diagnostic_figures"):
            raise SystemExit("CLEAN2 figure root must be exact slot 12")
        args.figure_dir = str(figure_root)

    ablation = load_ablation_catalog(args.ablation)
    classic = load_classic_case_catalog(args.mapping)
    result = {"factorial_variant_count": len(ablation.variants), "classic_case_count": len(classic.cases), "trace_open_count": 0}
    if args.case_provider_index:
        validate_case_provider_index(args.case_provider_index)
        result["case_provider_index"] = "PASS"
    if args.registry:
        result["registry"] = validate_run_registry_rows(read_run_registry(args.registry))
    if args.complete_output_seal:
        validate_complete_output_seal(
            args.complete_output_seal,
            runtime_root=args.runtime_root,
            registry_path=args.registry,
        )
        result["complete_output_seal"] = "PASS"
    if args.invariants_output:
        required = {
            "case_provider_index": args.case_provider_index,
            "registry": args.registry,
            "complete_output_seal": args.complete_output_seal,
            "solver_artifact_index": args.solver_artifact_index,
            "offline_evaluation_index": args.offline_evaluation_index,
            "runtime_root": args.runtime_root,
        }
        missing = sorted(key for key, value in required.items() if not value)
        if missing:
            raise SystemExit("invariance audit missing arguments: " + ",".join(missing))
        invariants = audit_clean2_formal_invariants(
            registry_path=args.registry,
            runtime_root=args.runtime_root,
            complete_output_seal_path=args.complete_output_seal,
            solver_artifact_index_path=args.solver_artifact_index,
            offline_evaluation_index_path=args.offline_evaluation_index,
            case_provider_index_path=args.case_provider_index,
        )
        write_json_atomic(args.invariants_output, invariants)
        result["formal_invariants"] = "PASS"
    if args.offline_evaluation_index:
        required = {
            "registry": args.registry,
            "runtime_root": args.runtime_root,
            "complete_output_seal": args.complete_output_seal,
            "solver_artifact_index": args.solver_artifact_index,
            "attempts": args.attempts,
            "attempts_audit": args.attempts_audit,
        }
        missing = sorted(key for key, value in required.items() if not value)
        if missing:
            raise SystemExit(
                "offline evaluation audit missing arguments: " + ",".join(missing)
            )
        offline_path = Path(args.offline_evaluation_index).resolve(strict=True)
        offline = json.loads(offline_path.read_text(encoding="utf-8"))
        solver_artifacts = load_solver_artifact_index(
            args.solver_artifact_index, expected_runtime_root=args.runtime_root
        )
        validate_sealed_solver_artifact_index(
            artifact_index=solver_artifacts,
            complete_output_seal_path=args.complete_output_seal,
            require_action_traces=True,
        )
        _, row_crosscheck = load_and_crosscheck_evaluation_index(
            offline_path,
            expected_solver_artifact_index_sha256=solver_artifacts.metadata[
                "index_sha256"
            ],
            expected_complete_output_seal_sha256=sha256_file(
                args.complete_output_seal
            ),
            expected_registry_sha256=sha256_file(args.registry),
            expected_run_attempts_sha256=sha256_file(args.attempts),
            expected_run_attempts_audit_sha256=sha256_file(args.attempts_audit),
            expected_solver_artifacts=solver_artifacts,
        )
        if (
            offline.get("exact_evaluator_sha256") != EXACT_EVALUATOR_SHA256
            or offline.get("trace_sha256") != EXPECTED_TRACE_SHA256
            or offline.get("all_110_outputs_validated_before_trace") is not True
            or row_crosscheck.get("passed") is not True
        ):
            raise SystemExit("offline exact-evaluator evidence failed")
        result["offline_exact_evaluation"] = "PASS"
    if args.analysis_index:
        analysis = json.loads(Path(args.analysis_index).resolve(strict=True).read_text(encoding="utf-8"))
        tables = analysis.get("tables")
        if analysis.get("passed") is not True or not isinstance(tables, dict):
            raise SystemExit("CLEAN2 analysis index failed")
        crosscheck_path = guarded_file(
            str(tables.get("crosscheck") or ""),
            slot="classic_analysis",
            name="CLEAN2_AGGREGATE_CROSSCHECK.json",
            role="CLEAN2 aggregate crosscheck from analysis index",
        )
        aggregate = json.loads(Path(crosscheck_path).read_text(encoding="utf-8"))
        if aggregate.get("passed") is not True:
            raise SystemExit("FAIL_CLEAN2_AGGREGATE_CROSSCHECK")
        result["aggregate_crosscheck"] = "PASS"
    if args.figure_dir:
        figure_root = Path(args.figure_dir).resolve(strict=True)
        qa = json.loads((figure_root / "CLEAN2_FIGURE_RENDER_QA.json").read_text(encoding="utf-8"))
        if (
            qa.get("passed") is not True
            or len(list(figure_root.glob("*.png"))) != 18
            or len(list(figure_root.glob("*.pdf"))) != 18
        ):
            raise SystemExit("CLEAN2 diagnostic figure QA failed")
        result["figure_render_QA"] = "PASS"
    raw_values = {
        "raw_root": args.raw_root,
        "raw_hash_lock": args.raw_hash_lock,
        "raw_lock_sha256": args.raw_lock_sha256,
        "raw_phase": args.raw_phase,
        "raw_audit_csv": args.raw_audit_csv,
        "raw_checkpoint_json": args.raw_checkpoint_json,
    }
    if any(raw_values.values()):
        missing = sorted(key for key, value in raw_values.items() if not value)
        if missing:
            raise SystemExit("raw 22/22 checkpoint missing arguments: " + ",".join(missing))
        if Path(args.raw_root).resolve(strict=True) != stage_paths.clean.raw_root:
            raise SystemExit("CLEAN2 raw root differs from ignored local config")
        if Path(args.raw_hash_lock).resolve(strict=True) != stage_paths.clean.raw_hash_lock.resolve(strict=True):
            raise SystemExit("CLEAN2 raw hash lock differs from ignored local config")
        args.raw_audit_csv = str(
            guard_clean2_stage_path(
                stage_paths,
                args.raw_audit_csv,
                slot="raw_audits",
                role="CLEAN2 raw audit CSV",
                direct_child=True,
            )
        )
        args.raw_checkpoint_json = str(
            guard_clean2_stage_path(
                stage_paths,
                args.raw_checkpoint_json,
                slot="raw_audits",
                role="CLEAN2 raw checkpoint JSON",
                direct_child=True,
            )
        )
        # 只做外层 immutable raw 完整性哈希；不生成provider、不改raw，也不向solver/evaluator传trace。
        raw = verify_by2_raw_22(
            args.raw_root,
            args.raw_hash_lock,
            expected_lock_sha256=args.raw_lock_sha256,
            audit_phase=args.raw_phase,
        )
        write_raw_audit(args.raw_audit_csv, raw)
        write_json_atomic(args.raw_checkpoint_json, raw_checkpoint_from_audit(raw))
        result[f"raw_{args.raw_phase}"] = {
            "verified": raw.summary["verified"],
            "expected": raw.summary["expected"],
            "raw_mutation": raw.summary["raw_mutation"],
            "trace_provider_or_solver_input": False,
            "passed": raw.summary["passed"],
        }
    if args.terminal_gate_output:
        required = {
            "case_provider_index": args.case_provider_index,
            "registry": args.registry,
            "attempts": args.attempts,
            "attempts_audit": args.attempts_audit,
            "complete_output_seal": args.complete_output_seal,
            "solver_artifact_index": args.solver_artifact_index,
            "offline_evaluation_index": args.offline_evaluation_index,
            "runtime_root": args.runtime_root,
            "raw_pre_provider_checkpoint": args.raw_pre_provider_checkpoint,
            "raw_post_provider_checkpoint": args.raw_post_provider_checkpoint,
            "raw_post_run_checkpoint": args.raw_post_run_checkpoint,
            "c00_structural_gate": args.c00_structural_gate,
            "formal_invariants": args.formal_invariants,
            "aggregate_crosscheck": args.aggregate_crosscheck,
            "figure_manifest": args.figure_manifest,
            "figure_qa": args.figure_qa,
            "final_review": args.final_review,
            "full_report_json": args.full_report_json,
            "full_report_md": args.full_report_md,
        }
        missing = sorted(key for key, value in required.items() if not value)
        if missing:
            raise SystemExit("terminal gate missing arguments: " + ",".join(missing))
        result["terminal_gate"] = build_clean2_terminal_gate_manifest(
            stage_root=stage_paths.stage_root,
            runtime_root=args.runtime_root,
            case_provider_index_path=args.case_provider_index,
            registry_path=args.registry,
            attempts_path=args.attempts,
            attempts_audit_path=args.attempts_audit,
            complete_output_seal_path=args.complete_output_seal,
            solver_artifact_index_path=args.solver_artifact_index,
            offline_evaluation_index_path=args.offline_evaluation_index,
            raw_pre_provider_checkpoint_path=args.raw_pre_provider_checkpoint,
            raw_post_provider_checkpoint_path=args.raw_post_provider_checkpoint,
            raw_post_run_checkpoint_path=args.raw_post_run_checkpoint,
            c00_structural_gate_path=args.c00_structural_gate,
            invariants_path=args.formal_invariants,
            aggregate_crosscheck_path=args.aggregate_crosscheck,
            figure_manifest_path=args.figure_manifest,
            figure_qa_path=args.figure_qa,
            review_path=args.final_review,
            full_report_json_path=args.full_report_json,
            full_report_md_path=args.full_report_md,
            output_path=args.terminal_gate_output,
        )
    if args.terminal_gate:
        validate_clean2_terminal_gate(args.terminal_gate, stage_root=stage_paths.stage_root)
        result["terminal_gate_validation"] = "PASS"
    export_values = {
        "final_export_stage_root": args.final_export_stage_root,
        "final_export_root": args.final_export_root,
    }
    if any(export_values.values()):
        missing = sorted(key for key, value in export_values.items() if not value)
        if missing:
            raise SystemExit("one-shot final export missing arguments: " + ",".join(missing))
        if Path(args.final_export_stage_root).resolve(strict=True) != stage_paths.stage_root:
            raise SystemExit("CLEAN2 final export stage root differs from ignored local config")
        export_root = guard_clean2_export_root(stage_paths, args.final_export_root)
        if not args.terminal_gate:
            raise SystemExit("one-shot final export requires --terminal-gate")
        result["final_export"] = build_clean2_final_zip(
            stage_root=stage_paths.stage_root,
            export_root=export_root,
            terminal_gate_path=args.terminal_gate,
            timestamp=args.final_export_timestamp,
        )
    result["passed"] = True
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
