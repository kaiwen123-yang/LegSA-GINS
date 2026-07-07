"""DA01 matrix runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import write_csv, write_json
from .evaluator import evaluate_yaw_only
from .method_teunissen_clambda import CLASSIC_CASES, METHOD_ID, blocked_full_backend_result, full_backend_ready, run_status_diagnostic_case


def matrix_queue_rows() -> list[dict[str, Any]]:
    return [
        {
            "row_id": f"{METHOD_ID}__{case.case_id}",
            "method_id": METHOD_ID,
            "case_id": case.case_id,
            "case_family": case.case_family,
            "planned_status": "RUN_CLEAN_FIRST" if case.case_id == "C00_clean_normal" else "RUN_AFTER_CLEAN",
            "trace_used_online": "false",
            "receiver_imu_data_as_body_imu": "false",
            "final_v23_output_solver_input": "false",
            "LegSA_output_solver_input": "false",
        }
        for case in CLASSIC_CASES
    ]


def run_da01_matrix(
    *,
    runtime_root: str | Path,
    status_series: list[dict[str, float]],
    trace_reference: str | Path,
    provider_capability: dict[str, Any],
    yaw_offset_deg: float = 90.0,
) -> dict[str, Any]:
    runtime = Path(runtime_root)
    method_root = runtime / METHOD_ID
    method_root.mkdir(parents=True, exist_ok=True)
    ready, full_blockers = full_backend_ready(provider_capability)
    row_results: list[dict[str, Any]] = []
    runtime_proof: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    clean_terminal_status = ""

    for case in CLASSIC_CASES:
        case_root = method_root / case.case_id
        case_root.mkdir(parents=True, exist_ok=True)
        write_json(case_root / "method_config.json", {"method_id": METHOD_ID, "case": case.__dict__, "full_backend_ready": ready})
        write_json(
            case_root / "input_contract.json",
            {
                "trace_used_online": False,
                "trace_evaluation_only": True,
                "receiver_imu_data_as_body_imu": False,
                "final_v23_output_solver_input": False,
                "LegSA_output_solver_input": False,
                "status_diagnostic_is_full_backend": False,
            },
        )
        write_json(case_root / "yaw_frame_report.json", {"yaw_offset_deg": yaw_offset_deg, "trace_rmse_selected_sign": False})

        if ready:
            # Placeholder for a future complete raw-carrier backend. This branch
            # is intentionally unreachable until provider_capability proves LOS
            # and DD design closure.
            manifest = blocked_full_backend_result(case.case_id, {**provider_capability, "los_provider_pass": False})
        else:
            full_block = blocked_full_backend_result(case.case_id, provider_capability)
            blocked_rows.append({"case_id": case.case_id, "terminal_status": "BLOCKED_WITH_PROOF", "blocker_reasons": ";".join(full_block["blocker_reasons"])})
            epoch_rows, manifest = run_status_diagnostic_case(status_series, case, yaw_offset_deg=yaw_offset_deg)
            write_csv(case_root / "epoch_output.csv", epoch_rows)
            metrics = evaluate_yaw_only(case_root / "epoch_output.csv", trace_reference)
            manifest["full_backend_blocker_reasons"] = full_blockers
            manifest["full_backend_terminal_status"] = full_block["terminal_status"]
            manifest["eval_metrics"] = metrics
            write_json(case_root / "eval_metrics.json", metrics)
        write_json(case_root / "run_manifest.json", manifest)
        (case_root / "terminal_status.txt").write_text(str(manifest["terminal_status"]) + "\n", encoding="utf-8")

        metrics = manifest.get("eval_metrics", {})
        row = {
            "row_id": f"{METHOD_ID}__{case.case_id}",
            "method_id": METHOD_ID,
            "case_id": case.case_id,
            "case_family": case.case_family,
            "method_mode": manifest["method_mode"],
            "terminal_status": manifest["terminal_status"],
            "reproduction_level": manifest["reproduction_level"],
            "provider_layer_used": manifest["provider_layer_used"],
            "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
            "yaw_p95_abs_deg": metrics.get("yaw_p95_abs_deg"),
            "aligned_count": metrics.get("aligned_count"),
            "trace_used_online": False,
            "receiver_imu_data_as_body_imu": False,
            "final_v23_output_solver_input": False,
            "LegSA_output_solver_input": False,
            "per_case_tuning": False,
            "output_only_correction": False,
            "epoch_deleted_for_metric": False,
        }
        row_results.append(row)
        runtime_proof.append(
            {
                "case_id": case.case_id,
                "case_runtime_dir": str(case_root),
                "epoch_output_exists": (case_root / "epoch_output.csv").exists(),
                "eval_metrics_exists": (case_root / "eval_metrics.json").exists(),
                "run_manifest_exists": (case_root / "run_manifest.json").exists(),
                "terminal_status": manifest["terminal_status"],
            }
        )
        if case.case_id == "C00_clean_normal":
            clean_terminal_status = str(manifest["terminal_status"])
            if not clean_terminal_status.startswith("COMPLETED"):
                break

    return {
        "row_results": row_results,
        "runtime_proof": runtime_proof,
        "blocked_rows": blocked_rows,
        "clean_terminal_status": clean_terminal_status,
        "full_backend_ready": ready,
        "full_backend_blocker_reasons": full_blockers,
    }
