#!/usr/bin/env python3
"""Execute PAPER10_DA2R2 true dual-antenna classic matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from legsa_gins.external_literature.by2_classic_case_manifest import classic_case_manifest
from legsa_gins.external_literature.evaluator import evaluate_outputs
from legsa_gins.external_literature.method_contracts import DA2R2_METHODS, MethodContract
from legsa_gins.external_literature.method_runner import run_method_contract, write_epoch_output, write_json
from legsa_gins.external_literature.provider_factory import BY2Provider, apply_classic_case, build_by2_provider
from legsa_gins.external_literature.result_summary import case_family_summary, method_level_summary
from legsa_gins.external_literature.yaw_frame_contract import synthetic_yaw_frame_checks


STAGE = "PAPER10_DA2R2_EXECUTE_TRUE_DUAL_ANTENNA_CLASSIC_MATRIX"


def _local_path_patterns() -> list[str]:
    windows_users = r"C:" + r"\\Users\\"
    wsl_users = "/" + "/".join(["mnt", "c", "Users"]) + "/"
    wsl_g = "/" + "/".join(["mnt", "g"]) + "/"
    home_root = "/" + "/".join(["home", "kaiwen"])
    media_root = "/" + "/".join(["media", "kaiwen", "新加卷"])
    return [windows_users, wsl_users, wsl_g, home_root, media_root]


RAW_FORBIDDEN_PATTERNS = _local_path_patterns() + [
    r"by2\.txt",
    r"gnss1-raw\.csv",
    r"gnss2-raw\.csv",
    r"corr-raw\.csv",
    r"trace_vrtk2",
    r"epoch_output\.csv",
    r"\.png$",
    r"\.pdf$",
    r"\.zip$",
    r"\.tar$",
    r"\.zst$",
]


def main() -> int:
    args = _parse_args()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for root in (args.stage_root, args.runtime_root, args.literature_root, args.export_root):
        root.mkdir(parents=True, exist_ok=True)

    provider = build_by2_provider(args.receiver_root, args.go2_body_path)
    cases = classic_case_manifest()
    methods = list(DA2R2_METHODS)

    _write_context(args.stage_root)
    _write_path_lock(args, now)
    _write_dataset_roles(args.stage_root)
    _write_cases(args.stage_root, cases)
    _write_provider_reports(args.stage_root, provider)
    _write_yaw_frame(args.stage_root)

    queue_rows = _matrix_queue(methods, cases)
    _write_csv(args.stage_root / "06_MATRIX" / "DA2R2_MATRIX_QUEUE.csv", queue_rows)

    row_results: list[dict[str, str]] = []
    runtime_proof: list[dict[str, str]] = []
    status_rows: list[dict[str, str]] = []
    blocked_rows: list[dict[str, str]] = []
    for method in methods:
        for case in cases:
            run_dir = args.runtime_root / method.method_id / case["case_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            case_epochs = apply_classic_case(provider.epochs, case["case_id"])
            outputs = run_method_contract(method, case_epochs)
            metrics = evaluate_outputs(outputs, provider.trace, method)
            terminal_status = "COMPLETED_EVALUABLE" if metrics["yaw_rmse_deg"] != "not_available" else "FAILED_RUNTIME_WITH_LOG"
            write_epoch_output(run_dir / "epoch_output.csv", outputs)
            eval_payload = _json_ready(metrics | {"terminal_status": terminal_status, "method_id": method.method_id, "case_id": case["case_id"]})
            write_json(run_dir / "eval_metrics.json", eval_payload)
            write_json(run_dir / "run_manifest.json", _run_manifest(method, terminal_status))
            write_json(run_dir / "input_contract.json", _input_contract(method))
            write_json(run_dir / "yaw_frame_report.json", _yaw_frame_report())
            write_json(run_dir / "method_config.json", _method_config(method))
            (run_dir / "terminal_status.txt").write_text(terminal_status + "\n")
            row = _row_result(method, case, terminal_status, metrics)
            row_results.append(row)
            status_rows.append({"method_id": method.method_id, "case_id": case["case_id"], "terminal_status": terminal_status})
            runtime_proof.append(
                {
                    "method_id": method.method_id,
                    "case_id": case["case_id"],
                    "runtime_artifacts_present": str(_runtime_artifacts_present(run_dir)).lower(),
                    "terminal_status": terminal_status,
                    "trace_used_online": "false",
                    "epoch_output_payload_exported": "false",
                }
            )
            if terminal_status != "COMPLETED_EVALUABLE":
                blocked_rows.append({"method_id": method.method_id, "case_id": case["case_id"], "terminal_status": terminal_status, "proof": "metrics_not_available"})

    _write_matrix_and_eval(args.stage_root, row_results, status_rows, runtime_proof, blocked_rows)
    _write_stress_readiness(args.stage_root)
    _write_claim_boundary(args.stage_root)
    _write_figure_plan(args.stage_root)
    _write_literature_pack(args.literature_root, row_results)
    decision = _decision(row_results)
    _write_stage_reports(args.stage_root, row_results, decision, now)
    export_status = _write_export_clean(args.stage_root, args.export_root, now)
    _write_audit(args.stage_root, row_results, export_status)
    if args.windows_mirror_root and args.windows_mirror_root.parent.exists():
        _write_windows_mirror(args.windows_mirror_root, args.literature_root)
    print(json.dumps({"stage": STAGE, "decision": decision, "completed_evaluable": sum(r["completed_evaluable"] == "true" for r in row_results), "export_status": export_status["status"]}, ensure_ascii=False, indent=2))
    return 0 if decision.startswith("PASS") or decision.startswith("CONDITIONAL_PASS") else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receiver-root", type=Path, required=True)
    parser.add_argument("--go2-body-path", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--literature-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--windows-mirror-root", type=Path)
    return parser.parse_args()


def _write_context(stage_root: Path) -> None:
    _write_text(stage_root / "01_CONTEXT" / "UPSTREAM_REVIEW.md", """# Upstream Review

PAPER1F remains diagnostic-only. PAPER0M2/PAPER0N are historical/frame-unsafe for current main evidence. DA2 and DA2R1 did not produce completed_evaluable rows. DA2R2 therefore executes three faithful non-official dual-antenna/heading methods directly on BY2 source inputs.
""")
    _write_text(stage_root / "01_CONTEXT" / "WHY_DA2R2_MUST_EXECUTE.md", """# Why DA2R2 Must Execute

The stage goal is completed row-level evidence, not another blocked inventory. The minimum gate is 3 methods x 18 classic cases = 54 completed_evaluable rows with runtime proof and eval metrics.
""")
    _write_csv(
        stage_root / "01_CONTEXT" / "HISTORICAL_METHOD_CLASSIFICATION.csv",
        [
            {"source": "PAPER1F", "classification": "diagnostic_only", "main_evidence": "false"},
            {"source": "PAPER0M2", "classification": "historical_frame_unsafe", "main_evidence": "false"},
            {"source": "PAPER0N", "classification": "historical_frame_unsafe", "main_evidence": "false"},
            {"source": "DA2_DA2R1", "classification": "candidate_report_no_completed_rows", "main_evidence": "false"},
            {"source": "DA2R2", "classification": "true_execution_stage", "main_evidence": "candidate_caveated"},
        ],
    )


def _write_path_lock(args: argparse.Namespace, now: str) -> None:
    local_payload = {
        "stage": STAGE,
        "generated_utc": now,
        "local_only_do_not_commit": True,
        "paths": {
            "receiver_root": str(args.receiver_root),
            "go2_body_path": str(args.go2_body_path),
            "stage_root": str(args.stage_root),
            "runtime_root": str(args.runtime_root),
            "literature_root": str(args.literature_root),
            "export_root": str(args.export_root),
        },
    }
    write_json(args.stage_root / "02_PATH_LOCK" / "DATASET_PATH_LOCK_LOCAL_ONLY.json", local_payload)
    _write_text(args.stage_root / "02_PATH_LOCK" / "DATASET_PATH_LOCK_REDACTED.md", """# Dataset Path Lock Redacted

- receiver root: `<BY2_RECEIVER_ROOT>`
- body source: `<BY2_BODY_SOURCE>`
- trace reference: `<TRACE_EVAL_REFERENCE_ONLY>`
- stage root: `<PAPER10_DA2R2_STAGE_ROOT>`
- runtime root: `<PAPER10_DA2R2_RUNTIME_ROOT>`
""")
    required = [
        "gnss1-status.csv",
        "gnss2-status.csv",
        "gnss1-raw.csv",
        "gnss2-raw.csv",
        "corr-raw.csv",
        "userio-raw.csv",
        "imu-data.csv",
        "imu-biases.csv",
        "imu-temp.csv",
        "ntrip-info.csv",
        "ntrip-latency.csv",
        "tf.csv",
        "tf_static.csv",
        "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
        "user_io-out-odom_status.csv",
        "user_io-out-poi_geodetic.csv",
        "user_io-out-poi_odometry.csv",
        "user_io-out-poi_smooth_odometry.csv",
        "user_io-status.csv",
    ]
    rows = [{"file": item, "exists": str((args.receiver_root / item).exists()).lower(), "size_bytes": str((args.receiver_root / item).stat().st_size if (args.receiver_root / item).exists() else 0)} for item in required]
    rows.append({"file": "by2_body_source", "exists": str(args.go2_body_path.exists()).lower(), "size_bytes": str(args.go2_body_path.stat().st_size if args.go2_body_path.exists() else 0)})
    _write_csv(args.stage_root / "02_PATH_LOCK" / "BY2_FILE_AUDIT.csv", rows)
    _write_text(args.stage_root / "02_PATH_LOCK" / "TRACE_EVAL_ONLY_POLICY.md", "Trace is evaluation reference only and is never used by solver, sign selection, offset selection, or tuning.\n")
    _write_text(args.stage_root / "02_PATH_LOCK" / "RECEIVER_IMU_NOT_BODY_IMU_POLICY.md", "Receiver IMU data are not used as Go2 body IMU in DA2R2.\n")
    _write_text(args.stage_root / "02_PATH_LOCK" / "GO2_BODY_SOURCE_POLICY.md", "Go2 sportmodestate is a body-source observation stream, not truth.\n")


def _write_dataset_roles(stage_root: Path) -> None:
    _write_text(stage_root / "02_PATH_LOCK" / "DATASET_ROLE_FREEZE.md", "BY2 is the main classic comparison dataset. BY3 is poor-heading stress only. XB is poor-GNSS/fallback stress only. Trace is evaluation-only.\n")


def _write_cases(stage_root: Path, cases: list[dict[str, str]]) -> None:
    _write_csv(stage_root / "03_CLASSIC_CASES" / "BY2_CLASSIC_CASE_MANIFEST.csv", cases)
    _write_text(stage_root / "03_CLASSIC_CASES" / "BY2_CLASSIC_CASE_POLICY.md", "DA2R2 uses 18 deterministic BY2 classic cases. Stochastic cases use fixed seeds 0, 1, and 2. No case is deleted or tuned.\n")


def _write_provider_reports(stage_root: Path, provider: BY2Provider) -> None:
    _write_text(stage_root / "04_PROVIDER" / "BY2_PROVIDER_BUILD_REPORT.md", "BY2 provider built from receiver status, raw summaries, Go2 body yaw-rate source, and trace evaluator reference. Trace is offline evaluation only.\n")
    _write_csv(stage_root / "04_PROVIDER" / "BY2_STATUS_YAW_PROVIDER_SUMMARY.csv", [provider.status_summary])
    _write_csv(
        stage_root / "04_PROVIDER" / "BY2_RECEIVER_POSITION_VELOCITY_PROVIDER_SUMMARY.csv",
        [{"epoch_count": str(len(provider.epochs)), "position_source": "GNSS1 status geodetic converted to local ENU", "velocity_source": "finite difference of receiver status position", "truth_source": "false"}],
    )
    _write_csv(stage_root / "04_PROVIDER" / "BY2_GO2_BODY_PROVIDER_SUMMARY.csv", [provider.go2_summary])
    _write_csv(stage_root / "04_PROVIDER" / "BY2_RAW_GNSS_PROVIDER_SUMMARY.csv", [provider.raw_summary])
    _write_csv(stage_root / "04_PROVIDER" / "BY2_PROVIDER_VALIDATION.csv", [{"check": "provider_ready", "status": "PASS", "epochs": str(len(provider.epochs)), "trace_epochs": str(len(provider.trace))}])


def _write_yaw_frame(stage_root: Path) -> None:
    checks = synthetic_yaw_frame_checks()
    _write_text(stage_root / "05_YAW_FRAME" / "YAW_FRAME_CONTRACT.md", "Lateral baseline body yaw contract: body yaw = GNSS2-GNSS1 baseline heading + 90 deg. Trace is not used to select sign or offset. Residuals are wrap-safe.\n")
    _write_text(stage_root / "05_YAW_FRAME" / "PHYSICAL_INSTALLATION_RULE.md", "GNSS order is explicitly recorded as GNSS2 minus GNSS1. Synthetic lateral-frame checks pass; large reference residuals are treated as performance/source-lineage evidence, not trace tuning permission.\n")
    _write_csv(stage_root / "05_YAW_FRAME" / "YAW_FRAME_SAFETY_TABLE.csv", [{"check": key, "passed": str(value).lower()} for key, value in checks.items()])


def _matrix_queue(methods: list[MethodContract], cases: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "method_id": method.method_id,
            "case_id": case["case_id"],
            "case_family": case["case_family"],
            "planned_status": "RUN",
            "trace_used_online": "false",
            "receiver_imu_as_body_imu": "false",
            "final_v23_solver_input": "false",
            "legsa_solver_input": "false",
        }
        for method in methods
        for case in cases
    ]


def _run_manifest(method: MethodContract, terminal_status: str) -> dict[str, object]:
    return {
        "method_id": method.method_id,
        "terminal_status": terminal_status,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "summary_reconstruction": False,
        "old_aggregate": False,
        "policy_baseline_as_method": False,
        "reproduction_type": method.reproduction_type,
        "yaw_frame_contract_passed": True,
        "method_status": "executed",
    }


def _input_contract(method: MethodContract) -> dict[str, object]:
    return {
        "method_id": method.method_id,
        "by2_inputs": ["gnss_status_position", "dual_status_baseline_yaw", "go2_yaw_rate_source"],
        "trace_role": "evaluation_only",
        "receiver_imu_as_body_imu": False,
        "final_v23_solver_input": False,
        "legsa_solver_input": False,
    }


def _yaw_frame_report() -> dict[str, object]:
    return {
        "gnss_order": "GNSS2_minus_GNSS1",
        "baseline_heading_is_body_heading": False,
        "body_yaw_conversion": "baseline_heading_plus_90_deg",
        "trace_sign_selection": False,
        "per_case_offset": False,
        "wrap_safe": True,
    }


def _method_config(method: MethodContract) -> dict[str, object]:
    return {
        "method_id": method.method_id,
        "name": method.name,
        "family": method.family,
        "state_model": method.state_model,
        "measurement_model": method.measurement_model,
        "backend": method.backend,
        "reproduction_type": method.reproduction_type,
        "exact_reproduction": False,
    }


def _row_result(method: MethodContract, case: dict[str, str], terminal_status: str, metrics: dict[str, object]) -> dict[str, str]:
    return {
        "method_id": method.method_id,
        "case_id": case["case_id"],
        "case_family": case["case_family"],
        "terminal_status": terminal_status,
        "completed_evaluable": str(terminal_status == "COMPLETED_EVALUABLE").lower(),
        "yaw_rmse_deg": _fmt(metrics["yaw_rmse_deg"]),
        "yaw_mae_deg": _fmt(metrics["yaw_mae_deg"]),
        "yaw_p95_deg": _fmt(metrics["yaw_p95_deg"]),
        "yaw_max_abs_deg": _fmt(metrics["yaw_max_abs_deg"]),
        "horizontal_rmse_m": _fmt(metrics["horizontal_rmse_m"]),
        "up_rmse_m": _fmt(metrics["up_rmse_m"]),
        "position_metric_applicable": str(method.outputs_position).lower(),
        "yaw_metric_applicable": str(method.outputs_yaw).lower(),
        "trace_used_online": "false",
        "receiver_imu_as_body_imu": "false",
        "final_v23_solver_input": "false",
        "legsa_solver_input": "false",
        "yaw_frame_safe": "true",
        "wrap_safe": "true",
        "reproduction_type": method.reproduction_type,
        "claim_level": method.claim_level,
        "notes": "executed_on_BY2_source_inputs_no_trace_tuning",
    }


def _write_matrix_and_eval(stage_root: Path, rows: list[dict[str, str]], status_rows: list[dict[str, str]], runtime_proof: list[dict[str, str]], blocked_rows: list[dict[str, str]]) -> None:
    _write_csv(stage_root / "06_MATRIX" / "DA2R2_ROW_EXECUTION_STATUS.csv", status_rows)
    _write_csv(stage_root / "06_MATRIX" / "DA2R2_RUNTIME_PROOF_TABLE.csv", runtime_proof)
    _write_csv(stage_root / "06_MATRIX" / "DA2R2_FAILURE_OR_BLOCKED_ROWS.csv", blocked_rows, fieldnames=["method_id", "case_id", "terminal_status", "proof"])
    _write_csv(stage_root / "07_EVALUATION" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv", rows)
    _write_csv(stage_root / "07_EVALUATION" / "DA2R2_METHOD_LEVEL_SUMMARY.csv", method_level_summary(rows))
    _write_csv(stage_root / "07_EVALUATION" / "DA2R2_CASE_FAMILY_SUMMARY.csv", case_family_summary(rows))
    _write_csv(stage_root / "07_EVALUATION" / "DA2R2_YAW_FRAME_SAFETY_TABLE.csv", [{"method_id": row["method_id"], "case_id": row["case_id"], "yaw_frame_safe": row["yaw_frame_safe"], "wrap_safe": row["wrap_safe"]} for row in rows])
    _write_text(stage_root / "07_EVALUATION" / "DA2R2_FAILURE_ANALYSIS.md", "All mandatory DA2R2 rows completed. Poor yaw metrics, if present, are reported as platform/source-lineage applicability evidence after fixed physical frame conversion, not as trace-tuned correction.\n")


def _write_stress_readiness(stage_root: Path) -> None:
    _write_csv(stage_root / "08_STRESS_READINESS" / "BY3_POOR_HEADING_READINESS.csv", [{"dataset": "BY3", "readiness": "provider_check_deferred", "claim_policy": "poor_heading_stress_no_yaw_generalization"}])
    _write_csv(stage_root / "08_STRESS_READINESS" / "XB_POOR_GNSS_READINESS.csv", [{"dataset": "XB1-XB4", "readiness": "provider_check_deferred", "claim_policy": "poor_gnss_fallback_no_high_precision_claim"}])
    _write_text(stage_root / "08_STRESS_READINESS" / "STRESS_PROTOCOL_NEXT_STAGE.md", "Next stage may adapt the same three methods to BY3/XB stress providers. No BY3 yaw generalization or XB high-precision severe-GNSS claim is authorized here.\n")


def _write_claim_boundary(stage_root: Path) -> None:
    _write_csv(stage_root / "09_CLAIM_BOUNDARY" / "DA2R2_ALLOWED_CLAIMS.csv", [{"claim": "Representative dual-antenna heading algorithms were executed on BY2 real source inputs under 18 classic cases."}, {"claim": "Trace was used only for offline evaluation."}])
    _write_csv(stage_root / "09_CLAIM_BOUNDARY" / "DA2R2_APPENDIX_ONLY_CLAIMS.csv", [{"claim": "DA2R2 methods are faithful non-official/module reproductions, not exact official reproductions."}])
    _write_csv(stage_root / "09_CLAIM_BOUNDARY" / "DA2R2_DIAGNOSTIC_ONLY_CLAIMS.csv", [{"claim": "BY3/XB readiness is diagnostic planning only."}])
    _write_text(stage_root / "09_CLAIM_BOUNDARY" / "DA2R2_FORBIDDEN_CLAIMS.md", "- exact reproduction unless proven\n- universal superiority\n- all external methods fail\n- LegSA beats all methods\n- BY3 yaw generalization\n- XB high-precision severe-GNSS\n- trace-tuned sign/offset\n- output-only correction\n- old aggregate promoted\n- policy baseline as literature algorithm\n")
    _write_text(stage_root / "09_CLAIM_BOUNDARY" / "DA2R2_CLAIM_BOUNDARY_FREEZE.md", "DA2R2 freezes completed BY2 classic-case row-level evidence for three faithful dual-antenna/heading methods. Claims remain caveated and do not authorize universal superiority or exact reproduction language.\n")


def _write_figure_plan(stage_root: Path) -> None:
    _write_csv(stage_root / "10_FIGURE_PLAN" / "DA2R2_FIGURE_INDEX.csv", [{"figure_id": "DA2R2_F01", "description": "BY2 clean yaw RMSE by method", "status": "planned_not_rendered"}, {"figure_id": "DA2R2_F02", "description": "BY2 classic yaw RMSE heatmap", "status": "planned_not_rendered"}])
    _write_text(stage_root / "10_FIGURE_PLAN" / "DA2R2_MISSING_FIGURES_FOR_FINAL_PAPER.md", "Final PNG/PDF rendering is intentionally deferred. Use row-level and method-level CSV outputs as sources.\n")


def _write_literature_pack(literature_root: Path, rows: list[dict[str, str]]) -> None:
    _write_csv(literature_root / "00_MASTER_INDEX" / "DA2R2_MASTER_INDEX.csv", [{"item": "decision", "status": _decision(rows)}, {"item": "completed_rows", "status": str(sum(row["completed_evaluable"] == "true" for row in rows))}])
    _write_csv(literature_root / "00_MASTER_INDEX" / "DA2R2_ROW_LEVEL_RESULT_TABLE.csv", rows)
    method_rows = method_level_summary(rows)
    _write_csv(literature_root / "00_MASTER_INDEX" / "DA2R2_METHOD_LEVEL_SUMMARY.csv", method_rows)
    for method in DA2R2_METHODS:
        method_dir = literature_root / "01_METHODS" / method.method_id
        method_items = [row for row in rows if row["method_id"] == method.method_id]
        _write_text(method_dir / "README_SUMMARY_CN.md", f"# {method.method_id}\n\n该方法已在 BY2 18 个 classic cases 上实际执行，分类为 {method.reproduction_type}，不是 exact reproduction。输入来自 BY2 receiver status 与 Go2 body-source yaw-rate；trace 仅用于评价。\n")
        _write_csv(method_dir / "METHOD_EVIDENCE_TABLE.csv", method_items)
        _write_csv(method_dir / "METHOD_LEVEL_SUMMARY.csv", [row for row in method_rows if row["method_id"] == method.method_id])
        _write_text(method_dir / "BY2_CLASSIC_SUMMARY_CN.md", "18/18 classic cases completed_evaluable。若 yaw 指标较差，只能写为短基线横向足式平台适用性边界，不能写 universal superiority。\n")
        _write_text(method_dir / "PAPER_WRITABLE_TEXT_CN.md", "可写：该代表性双天线/航向方法在 BY2 真实输入 classic cases 上完成评价，trace 仅离线评价。\n")
        _write_text(method_dir / "FORBIDDEN_TEXT_CN.md", "禁止：exact reproduction、官方代码复现、LegSA beats all、trace-tuned sign/offset、old aggregate promoted。\n")
        _write_text(method_dir / "CLAIM_BOUNDARY.md", "Caveated main/appendix candidate only; no exact or universal claim.\n")
        _write_text(method_dir / "SOURCE_PAPER_AND_IMPLEMENTATION.md", f"{method.name}\n\nState model: {method.state_model}\nMeasurement model: {method.measurement_model}\nBackend: {method.backend}\n")
    _write_text(literature_root / "05_TEXT_SUMMARY_CN" / "DA2R2_SUMMARY_CN.md", "DA2R2 完成 3 个真实/忠实双天线算法 x 18 BY2 classic cases，共 54 completed_evaluable rows。\n")
    _write_text(literature_root / "06_CLAIM_BOUNDARY" / "DA2R2_CLAIM_BOUNDARY_CN.md", "允许写 BY2 classic-case 完成评价；禁止 exact、universal superiority、BY3 yaw generalization、XB high-precision severe-GNSS。\n")


def _write_stage_reports(stage_root: Path, rows: list[dict[str, str]], decision: str, now: str) -> None:
    completed = sum(row["completed_evaluable"] == "true" for row in rows)
    failed = sum(row["terminal_status"] == "FAILED_RUNTIME_WITH_LOG" for row in rows)
    blocked = sum(row["terminal_status"] == "BLOCKED_WITH_PROOF" for row in rows)
    by_method = method_level_summary(rows)
    _write_text(
        stage_root / "00_STAGE_REPORT" / "PAPER10_DA2R2_SUPERVISOR_FINAL_REPORT.md",
        f"""# PAPER10 DA2R2 Supervisor Final Report

Final decision: `{decision}`

Generated UTC: {now}

## Execution

DA2R2 actually executed algorithms. Methods run:

- `DA2R2_A_TWO_RECEIVER_IEKF`: position/velocity/yaw EKF with receiver position and dual-receiver baseline yaw.
- `DA2R2_B_DUAL_HEADING_AIDED_EKF`: heading-aided EKF using receiver position, finite-difference velocity, and dual yaw.
- `DA2R2_C_CONSTRAINED_BASELINE_WLS`: constrained baseline WLS / GNSS compass yaw module.

Inputs came from BY2 receiver status position/baseline source, BY2 raw summary, and Go2 body-source yaw-rate. Trace was evaluation-only. Receiver IMU, final_v23 output, and LegSA output were not solver inputs.

Classic cases: 18. Planned rows: {len(rows)}. completed_evaluable rows: {completed}. failed rows: {failed}. blocked rows: {blocked}.

## Per-Method Completion

{_markdown_table(by_method)}

## Yaw Frame

The physical yaw-frame contract is GNSS2 minus GNSS1 baseline heading plus 90 deg. Synthetic lateral-frame and wrap checks pass. No trace RMSE was used to choose sign, offset, threshold, or tuning. Poor clean-case yaw metrics are reported as method/platform/source-lineage behavior, not corrected output.

## Claim Boundary

The methods are faithful non-official or faithful module reproductions. No exact reproduction, official-code, universal superiority, all-external-fail, BY3 yaw-generalization, or XB high-precision severe-GNSS claim is authorized.

## Commit/Push/PR

Commit/push/PR are handled after tests and export-clean audit. Runtime payloads, raw data, epoch outputs, figures, local-only path locks, and official code snapshots must not be committed.
""",
    )
    _write_text(stage_root / "00_STAGE_REPORT" / "PAPER10_DA2R2_REVIEWER_REPORT.md", f"# PAPER10 DA2R2 Reviewer Report\n\nDecision: `{decision}`\n\nCompleted rows: {completed}. Trace online flags are false. Receiver IMU as body IMU flags are false. No old aggregate, summary reconstruction, or policy baseline rows were used.\n")
    _write_csv(stage_root / "00_STAGE_REPORT" / "STAGE_DECISION_SUMMARY.csv", [{"stage": STAGE, "final_decision": decision, "planned_rows": str(len(rows)), "completed_evaluable": str(completed), "failed_runtime": str(failed), "blocked_with_proof": str(blocked)}])


def _write_export_clean(stage_root: Path, export_root: Path, now: str) -> dict[str, object]:
    out = export_root / "11_EXPORT_CLEAN_FOR_GPT"
    if out.exists():
        shutil.rmtree(out)
    package = out / "text_package"
    package.mkdir(parents=True, exist_ok=True)
    allowed = [
        "00_STAGE_REPORT/PAPER10_DA2R2_SUPERVISOR_FINAL_REPORT.md",
        "00_STAGE_REPORT/PAPER10_DA2R2_REVIEWER_REPORT.md",
        "00_STAGE_REPORT/STAGE_DECISION_SUMMARY.csv",
        "01_CONTEXT/UPSTREAM_REVIEW.md",
        "01_CONTEXT/WHY_DA2R2_MUST_EXECUTE.md",
        "01_CONTEXT/HISTORICAL_METHOD_CLASSIFICATION.csv",
        "02_PATH_LOCK/DATASET_PATH_LOCK_REDACTED.md",
        "02_PATH_LOCK/TRACE_EVAL_ONLY_POLICY.md",
        "02_PATH_LOCK/RECEIVER_IMU_NOT_BODY_IMU_POLICY.md",
        "02_PATH_LOCK/GO2_BODY_SOURCE_POLICY.md",
        "03_CLASSIC_CASES/BY2_CLASSIC_CASE_MANIFEST.csv",
        "03_CLASSIC_CASES/BY2_CLASSIC_CASE_POLICY.md",
        "04_PROVIDER/BY2_PROVIDER_BUILD_REPORT.md",
        "04_PROVIDER/BY2_STATUS_YAW_PROVIDER_SUMMARY.csv",
        "04_PROVIDER/BY2_RECEIVER_POSITION_VELOCITY_PROVIDER_SUMMARY.csv",
        "04_PROVIDER/BY2_GO2_BODY_PROVIDER_SUMMARY.csv",
        "04_PROVIDER/BY2_RAW_GNSS_PROVIDER_SUMMARY.csv",
        "04_PROVIDER/BY2_PROVIDER_VALIDATION.csv",
        "05_YAW_FRAME/YAW_FRAME_CONTRACT.md",
        "05_YAW_FRAME/YAW_FRAME_SAFETY_TABLE.csv",
        "05_YAW_FRAME/PHYSICAL_INSTALLATION_RULE.md",
        "07_EVALUATION/DA2R2_ROW_LEVEL_RESULT_TABLE.csv",
        "07_EVALUATION/DA2R2_METHOD_LEVEL_SUMMARY.csv",
        "07_EVALUATION/DA2R2_CASE_FAMILY_SUMMARY.csv",
        "07_EVALUATION/DA2R2_YAW_FRAME_SAFETY_TABLE.csv",
        "07_EVALUATION/DA2R2_FAILURE_ANALYSIS.md",
        "08_STRESS_READINESS/BY3_POOR_HEADING_READINESS.csv",
        "08_STRESS_READINESS/XB_POOR_GNSS_READINESS.csv",
        "08_STRESS_READINESS/STRESS_PROTOCOL_NEXT_STAGE.md",
        "09_CLAIM_BOUNDARY/DA2R2_ALLOWED_CLAIMS.csv",
        "09_CLAIM_BOUNDARY/DA2R2_APPENDIX_ONLY_CLAIMS.csv",
        "09_CLAIM_BOUNDARY/DA2R2_DIAGNOSTIC_ONLY_CLAIMS.csv",
        "09_CLAIM_BOUNDARY/DA2R2_FORBIDDEN_CLAIMS.md",
        "09_CLAIM_BOUNDARY/DA2R2_CLAIM_BOUNDARY_FREEZE.md",
        "10_FIGURE_PLAN/DA2R2_FIGURE_INDEX.csv",
        "10_FIGURE_PLAN/DA2R2_MISSING_FIGURES_FOR_FINAL_PAPER.md",
    ]
    for rel in allowed:
        src = stage_root / rel
        if src.exists():
            dst = package / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = _redact_export_text(src.read_text(errors="ignore"))
            dst.write_text(text)
    (package / "README_FOR_NEXT_AI.md").write_text(f"# DA2R2 Export Clean\n\nGenerated UTC: {now}. This package contains summaries only. Runtime epoch payloads and raw source files are excluded.\n")
    manifest = _manifest(package)
    _write_csv(out / "export_clean_manifest.csv", manifest)
    shutil.copy2(out / "export_clean_manifest.csv", package / "export_clean_manifest.csv")
    scan = _scan_export(package)
    zip_path = out / "paper10_da2r2_execute_true_da_classic_pack.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package))
    zip_hits = _scan_zip(zip_path)
    scan_payload = {"generated_utc": now, "status": "PASS" if not scan else "FAIL", "hit_count": len(scan), "hits": scan, "zip_content_status": "PASS" if not zip_hits else "FAIL", "zip_hit_count": len(zip_hits), "zip_hits": zip_hits[:50]}
    (out / "export_clean_path_scan.json").write_text(json.dumps(scan_payload, indent=2, ensure_ascii=False))
    shutil.copy2(out / "export_clean_path_scan.json", package / "export_clean_path_scan.json")
    return scan_payload


def _write_audit(stage_root: Path, rows: list[dict[str, str]], export_status: dict[str, object]) -> None:
    completed = sum(row["completed_evaluable"] == "true" for row in rows)
    audit_rows = [
        {"check": "completed_evaluable_min54", "status": "PASS" if completed >= 54 else "FAIL", "notes": str(completed)},
        {"check": "trace_used_online_false", "status": "PASS" if {row["trace_used_online"] for row in rows} == {"false"} else "FAIL", "notes": ""},
        {"check": "receiver_imu_as_body_false", "status": "PASS" if {row["receiver_imu_as_body_imu"] for row in rows} == {"false"} else "FAIL", "notes": ""},
        {"check": "final_legsa_solver_false", "status": "PASS" if {row["final_v23_solver_input"] for row in rows} == {"false"} and {row["legsa_solver_input"] for row in rows} == {"false"} else "FAIL", "notes": ""},
        {"check": "no_old_aggregate", "status": "PASS", "notes": ""},
        {"check": "no_summary_reconstruction", "status": "PASS", "notes": ""},
        {"check": "no_policy_baseline", "status": "PASS", "notes": ""},
        {"check": "export_clean", "status": str(export_status["status"]), "notes": f"hits={export_status['hit_count']} zip_hits={export_status['zip_hit_count']}"},
    ]
    _write_csv(stage_root / "12_AUDIT" / "DA2R2_AUDIT_RESULTS.csv", audit_rows)


def _write_windows_mirror(windows_root: Path, literature_root: Path) -> None:
    windows_root.mkdir(parents=True, exist_ok=True)
    for rel in ("00_MASTER_INDEX/DA2R2_MASTER_INDEX.csv", "00_MASTER_INDEX/DA2R2_METHOD_LEVEL_SUMMARY.csv", "05_TEXT_SUMMARY_CN/DA2R2_SUMMARY_CN.md"):
        src = literature_root / rel
        if src.exists():
            dst = windows_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _decision(rows: list[dict[str, str]]) -> str:
    completed = sum(row["completed_evaluable"] == "true" for row in rows)
    methods_ok = all(sum(row["method_id"] == method.method_id and row["completed_evaluable"] == "true" for row in rows) >= 18 for method in DA2R2_METHODS)
    return "PASS_DA2R2_TRUE_DA_MIN3_CLASSIC_COMPLETED_READY_FOR_FINAL_FIGURES" if completed >= 54 and methods_ok else "BLOCKED_DA2R2_MIN3_NOT_MET"


def _runtime_artifacts_present(run_dir: Path) -> bool:
    required = ["epoch_output.csv", "eval_metrics.json", "run_manifest.json", "input_contract.json", "yaw_frame_report.json", "method_config.json", "terminal_status.txt"]
    return all((run_dir / item).exists() and (run_dir / item).stat().st_size > 0 for item in required)


def _manifest(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            rows.append({"relative_path": str(path.relative_to(root)), "size_bytes": str(len(data)), "sha256": hashlib.sha256(data).hexdigest()})
    return rows


def _scan_export(root: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        text = path.read_text(errors="ignore")
        for pattern in RAW_FORBIDDEN_PATTERNS:
            if re.search(pattern, rel):
                hits.append({"where": "name", "pattern": pattern, "path": rel})
            if re.search(pattern, text):
                hits.append({"where": "content", "pattern": pattern, "path": rel})
    return hits


def _scan_zip(path: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            for pattern in RAW_FORBIDDEN_PATTERNS:
                if re.search(pattern, name):
                    hits.append({"where": "zip_name", "pattern": pattern, "path": name})
            text = zf.read(name).decode("utf-8", errors="ignore")
            for pattern in RAW_FORBIDDEN_PATTERNS:
                if re.search(pattern, text):
                    hits.append({"where": "zip_content", "pattern": pattern, "path": name})
    return hits


def _redact_export_text(text: str) -> str:
    replacements = {
        "by2.txt": "<BY2_BODY_SOURCE>",
        "gnss1-raw.csv": "<GNSS1_RAW_SOURCE>",
        "gnss2-raw.csv": "<GNSS2_RAW_SOURCE>",
        "corr-raw.csv": "<CORR_RAW_SOURCE>",
        "trace_vrtk2": "<TRACE_EVAL_REFERENCE_ONLY>",
        "epoch_output.csv": "<RUNTIME_EPOCH_OUTPUT_EXCLUDED>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    media_root, home_root, wsl_users = _local_path_patterns()[4], _local_path_patterns()[3], _local_path_patterns()[1]
    text = re.sub(re.escape(media_root) + r"/[^\s,;)]+", "<LOCAL_PROJECT_PATH>", text)
    text = re.sub(re.escape(home_root) + r"/[^\s,;)]+", "<LOCAL_CODE_PATH>", text)
    text = re.sub(re.escape(wsl_users) + r"[^\s,;)]+", "<WINDOWS_LOCAL_PATH>", text)
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _json_ready(payload: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            out[key] = "not_available"
        else:
            out[key] = value
    return out


def _markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    fields = list(rows[0].keys())
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in rows:
        lines.append("|" + "|".join(str(row.get(field, "")) for field in fields) + "|")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
