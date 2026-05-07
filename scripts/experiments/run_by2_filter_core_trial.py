#!/usr/bin/env python3
"""Run the N4G BY2 filter-core diagnostic candidate trial.

中文说明：本脚本先做时间域审计和 event-normalized algo_time_sec，再运行多候选
diagnostic trial；trace 只在 evaluation 阶段读取，且不用于 solver alignment。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.datasets.by2.dual_antenna_heading_convention import (  # noqa: E402
    candidate_heading_offsets,
    make_dual_antenna_heading_report,
)
from legsa_gins.datasets.by2.unitree_imu_semantics import (  # noqa: E402
    make_unitree_imu_semantics_report,
)
from legsa_gins.evaluation.case_review_report import generate_case_review  # noqa: E402
from legsa_gins.evaluation.gap_screen import make_gap_screen, write_gap_screen  # noqa: E402
from legsa_gins.evaluation.target_gates import (  # noqa: E402
    evaluate_target_gates,
    write_gate_report,
)
from legsa_gins.evaluation.trajectory_metrics import (  # noqa: E402
    align_by_timestamp,
    compute_errors,
    load_eval_nav,
    load_trace_reference,
    summary_metrics,
    write_error_series,
    write_summary,
)
from legsa_gins.experiments.by2_filter_trial import (  # noqa: E402
    convert_go2_body_state_to_imu_increments,
    make_receiver_measurement_trial_csv,
    select_receiver_status_csv,
    write_toy_standardized_inputs,
)
from legsa_gins.time_alignment.event_normalization import (  # noqa: E402
    add_algo_time_to_csv,
    make_event_normalization_report,
)


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _standardize_inputs(args: argparse.Namespace, inputs_dir: Path) -> None:
    if args.toy:
        write_toy_standardized_inputs(inputs_dir)
        return
    from scripts.datasets.standardize_by2_inputs import standardize_by2_inputs

    standardize_by2_inputs(
        fix_root=args.fix_root,
        body_imu=args.body_imu,
        output_dir=inputs_dir,
        max_status_rows=args.max_status_rows,
        max_raw_rows=args.max_raw_rows,
        max_body_messages=args.max_body_messages,
    )


def _write_trial_manifest(
    path: Path,
    *,
    root_output_dir: Path,
    trial_dir: Path,
    selected_receiver_source: str,
    imu_adapter_summary: dict[str, Any],
    receiver_adapter_summary: dict[str, Any],
    summary: dict[str, Any],
    classification: dict[str, Any],
    gate_report: dict[str, Any],
    gap_screen: dict[str, Any],
    toy: bool,
) -> None:
    manifest = {
        "phase": "N4G",
        "toy_inputs": toy,
        "root_output_dir": str(root_output_dir),
        "trial_dir": str(trial_dir),
        "selected_receiver_source": selected_receiver_source,
        "imu_propagation_mode": imu_adapter_summary["imu_propagation_mode"],
        "heading_offset_mode": receiver_adapter_summary["heading_offset_mode"],
        "heading_offset_deg": receiver_adapter_summary["heading_offset_deg"],
        "heading_mounting_diagnostic_only": True,
        "formal_heading_offset_selected": False,
        "event_normalized_time_axis": True,
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "trace_used_for_alignment": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "receiver_imu_as_body_imu": False,
        "go2_body_state_used_as_imu_propagation_diagnostic": True,
        "go2_prior_claim": False,
        "raw_doppler_claim": False,
        "source_aware_weighting_claim": False,
        "fgo_smoother_claim": False,
        "numerical_performance_claim": False,
        "final_v23_reference_context_only": True,
        "final_v23_output_substitution": False,
        "proposed_reads_final_v23_output": False,
        "imu_adapter": imu_adapter_summary,
        "receiver_adapter": receiver_adapter_summary,
        "summary": summary,
        "classification": classification,
        "gate_report": gate_report,
        "gap_screen": gap_screen,
    }
    _write_json(path, manifest)


def _normalize_inputs(
    *,
    inputs_dir: Path,
    receiver_status_csv: Path,
    trace_csv: Path,
    event_report: dict[str, Any],
) -> dict[str, Path]:
    end = float(event_report["end_algo_time_sec"])
    go2_start = float(event_report["go2_formal_start_raw_time"] or 0.0)
    gnss_start = float(event_report["gnss_formal_start_raw_time"] or 0.0)
    paths = {
        "go2": inputs_dir / "BY2_GO2_BODY_STATE_ALGO_TIME.csv",
        "gnss": inputs_dir / "BY2_RECEIVER_STATUS_ALGO_TIME.csv",
        "trace": inputs_dir / "BY2_TRACE_REFERENCE_ALGO_TIME.csv",
    }
    add_algo_time_to_csv(
        inputs_dir / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        paths["go2"],
        raw_time_field="timestamp",
        start_time=go2_start,
        end_algo_time_sec=end,
    )
    add_algo_time_to_csv(
        receiver_status_csv,
        paths["gnss"],
        raw_time_field="time_unix",
        start_time=gnss_start,
        end_algo_time_sec=end,
    )
    add_algo_time_to_csv(
        trace_csv,
        paths["trace"],
        raw_time_field="timestamp",
        start_time=gnss_start,
        end_algo_time_sec=end,
    )
    return paths


def _run_one_candidate(
    *,
    args: argparse.Namespace,
    root_output_dir: Path,
    trial_dir: Path,
    normalized_paths: dict[str, Path],
    selected_receiver_source: str,
    imu_mode: str,
    heading_mode: str,
    event_report_path: Path,
    imu_report_path: Path,
    heading_report_path: Path,
    event_report: dict[str, Any],
    imu_semantics_report: dict[str, Any],
) -> dict[str, Any]:
    trial_inputs = trial_dir / "inputs"
    run_dir = trial_dir / "run"
    evaluation_dir = trial_dir / "evaluation"
    trial_inputs.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    imu_csv = trial_inputs / "BY2_BODY_IMU_INCREMENT_STANDARD.csv"
    receiver_csv = trial_inputs / "BY2_RECEIVER_MEASUREMENT_TRIAL.csv"
    imu_summary = convert_go2_body_state_to_imu_increments(
        normalized_paths["go2"],
        imu_csv,
        max_rows=args.max_body_messages,
        imu_propagation_mode=imu_mode,
    )
    receiver_summary = make_receiver_measurement_trial_csv(
        normalized_paths["gnss"],
        receiver_csv,
        source_name=selected_receiver_source,
        heading_offset_mode=heading_mode,
    )

    command = [
        str(REPO_ROOT / "build/cpp/legsa_gins"),
        "--run-filter-csv",
        "--imu-csv",
        str(imu_csv),
        "--receiver-csv",
        str(receiver_csv),
        "--output-dir",
        str(run_dir),
        "--imu-propagation-mode",
        imu_mode,
        "--heading-offset-mode",
        heading_mode,
    ]
    if args.max_filter_epochs is not None:
        command.extend(["--max-epochs", str(args.max_filter_epochs)])
    _run(command)

    errors = compute_errors(
        align_by_timestamp(
            load_eval_nav(run_dir / "EVAL_NAV.csv"),
            load_trace_reference(normalized_paths["trace"]),
            max_dt=0.05,
        )
    )
    write_error_series(errors, evaluation_dir / "error_series.csv")
    summary = summary_metrics(errors)
    write_summary(summary, evaluation_dir / "summary.json")
    gate_report = evaluate_target_gates(summary)
    write_gate_report(gate_report, evaluation_dir / "gate_report.json")
    gap_report = make_gap_screen(
        summary=summary,
        gate_report=gate_report,
        event_report=event_report,
        imu_report=imu_semantics_report,
        imu_propagation_mode=imu_mode,
        heading_offset_mode=heading_mode,
    )
    write_gap_screen(gap_report, evaluation_dir / "gap_screen.json")

    trial_manifest_path = trial_dir / "BY2_FILTER_TRIAL_MANIFEST.json"
    _write_trial_manifest(
        trial_manifest_path,
        root_output_dir=root_output_dir,
        trial_dir=trial_dir,
        selected_receiver_source=selected_receiver_source,
        imu_adapter_summary=imu_summary,
        receiver_adapter_summary=receiver_summary,
        summary=summary,
        classification={},
        gate_report=gate_report,
        gap_screen=gap_report,
        toy=args.toy,
    )
    classification = generate_case_review(
        output_path=trial_dir / "case_review.md",
        run_dir=run_dir,
        input_manifest_path=root_output_dir / "inputs/BY2_INPUT_MANIFEST.json",
        trial_manifest_path=trial_manifest_path,
        summary_path=evaluation_dir / "summary.json",
        event_report_path=event_report_path,
        imu_report_path=imu_report_path,
        heading_report_path=heading_report_path,
        gate_report_path=evaluation_dir / "gate_report.json",
        gap_screen_path=evaluation_dir / "gap_screen.json",
    )
    _write_trial_manifest(
        trial_manifest_path,
        root_output_dir=root_output_dir,
        trial_dir=trial_dir,
        selected_receiver_source=selected_receiver_source,
        imu_adapter_summary=imu_summary,
        receiver_adapter_summary=receiver_summary,
        summary=summary,
        classification=classification,
        gate_report=gate_report,
        gap_screen=gap_report,
        toy=args.toy,
    )
    return {
        "candidate_name": f"{imu_mode}_{heading_mode}",
        "trial_dir": str(trial_dir),
        "imu_propagation_mode": imu_mode,
        "heading_offset_mode": heading_mode,
        "summary": summary,
        "gate_report": gate_report,
        "gap_screen": gap_report,
        "classification": classification,
    }


def run_trial(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    inputs_dir = output_dir / "inputs"
    alignment_dir = output_dir / "alignment"
    imu_dir = output_dir / "imu"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    alignment_dir.mkdir(parents=True, exist_ok=True)
    imu_dir.mkdir(parents=True, exist_ok=True)

    _standardize_inputs(args, inputs_dir)
    receiver_status_csv, selected_receiver_source = select_receiver_status_csv(inputs_dir)
    trace_csv = inputs_dir / "BY2_TRACE_REFERENCE_EVAL_ONLY.csv"

    event_report = make_event_normalization_report(
        go2_body_state_csv=inputs_dir / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        gnss_status_csv=receiver_status_csv,
        trace_csv=trace_csv,
        end_margin_sec=args.end_margin_sec,
    )
    event_report_path = alignment_dir / "EVENT_NORMALIZATION_REPORT.json"
    _write_json(event_report_path, event_report)
    normalized_paths = _normalize_inputs(
        inputs_dir=inputs_dir,
        receiver_status_csv=receiver_status_csv,
        trace_csv=trace_csv,
        event_report=event_report,
    )

    imu_semantics_report = make_unitree_imu_semantics_report(_read_csv(normalized_paths["go2"]))
    imu_report_path = imu_dir / "UNITREE_IMU_SEMANTICS_REPORT.json"
    _write_json(imu_report_path, imu_semantics_report)

    imu_modes = [item.strip() for item in args.imu_propagation_modes.split(",") if item.strip()]
    heading_modes = (
        [item["heading_offset_mode"] for item in candidate_heading_offsets()]
        if args.run_heading_offset_candidates
        else ["no_offset"]
    )
    heading_report_path = output_dir / "HEADING_OFFSET_CANDIDATE_REPORT.json"
    initial_heading_report = make_dual_antenna_heading_report({})
    _write_json(heading_report_path, initial_heading_report)

    _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
    _run(["cmake", "--build", "build/cpp"])

    candidates: list[dict[str, Any]] = []
    for imu_mode in imu_modes:
        for heading_mode in heading_modes:
            candidate = _run_one_candidate(
                args=args,
                root_output_dir=output_dir,
                trial_dir=output_dir / f"trial_{imu_mode}_{heading_mode}",
                normalized_paths=normalized_paths,
                selected_receiver_source=selected_receiver_source,
                imu_mode=imu_mode,
                heading_mode=heading_mode,
                event_report_path=event_report_path,
                imu_report_path=imu_report_path,
                heading_report_path=heading_report_path,
                event_report=event_report,
                imu_semantics_report=imu_semantics_report,
            )
            candidates.append(candidate)

    heading_report = make_dual_antenna_heading_report(
        {
            item["candidate_name"]: {
                "heading_offset_mode": item["heading_offset_mode"],
                "yaw_rmse_deg": item["summary"].get("yaw_rmse_deg"),
                "target_gate_pass": item["gate_report"].get("target_gate_pass"),
            }
            for item in candidates
        }
    )
    _write_json(heading_report_path, heading_report)
    imu_mode_report = {
        "phase": "N4G",
        "imu_propagation_modes": imu_modes,
        "raw_accel_direct_deprecated_diagnostic": True,
        "accel_contains_gravity": True,
        "gyro_only_zero_dvel_purpose": "isolate_accelerometer_gravity_vertical_divergence",
        "quaternion_gravity_compensated_status": "diagnostic_candidate_not_final_mechanization",
        "go2_prior_claim": False,
        "numerical_performance_claim": False,
    }
    _write_json(output_dir / "IMU_PROPAGATION_MODE_REPORT.json", imu_mode_report)

    best = min(
        candidates,
        key=lambda item: (
            float(item["summary"].get("horizontal_rmse_m") or 1.0e99),
            float(item["summary"].get("yaw_rmse_deg") or 1.0e99),
        ),
    )
    all_gap = {
        "phase": "N4G",
        "best_diagnostic_candidate": best["candidate_name"],
        "formal_heading_offset_selected": False,
        "target_gate_pass": best["gate_report"].get("target_gate_pass"),
        "ready_for_factor_stacking": best["gate_report"].get("ready_for_factor_stacking"),
        "recommended_next_stage": best["gap_screen"].get("recommended_next_stage"),
        "severe_horizontal_error": any(item["gap_screen"].get("severe_horizontal_error") for item in candidates),
        "severe_vertical_error": any(item["gap_screen"].get("severe_vertical_error") for item in candidates),
        "severe_yaw_error": any(item["gap_screen"].get("severe_yaw_error") for item in candidates),
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "event_normalized_time_axis": True,
        "trace_solver_input": False,
        "trace_used_for_alignment": False,
        "numerical_performance_claim": False,
        "candidates": {
            item["candidate_name"]: {
                "horizontal_rmse_m": item["summary"].get("horizontal_rmse_m"),
                "up_rmse_m": item["summary"].get("up_rmse_m"),
                "yaw_rmse_deg": item["summary"].get("yaw_rmse_deg"),
                "target_gate_pass": item["gate_report"].get("target_gate_pass"),
                "ready_for_factor_stacking": item["gate_report"].get("ready_for_factor_stacking"),
                "recommended_next_stage": item["gap_screen"].get("recommended_next_stage"),
                "trial_dir": item["trial_dir"],
            }
            for item in candidates
        },
    }
    _write_json(output_dir / "N4G_GAP_SCREEN_SUMMARY.json", all_gap)
    return {
        "output_dir": str(output_dir),
        "selected_receiver_source": selected_receiver_source,
        "event_report": event_report,
        "imu_report": imu_semantics_report,
        "heading_report": heading_report,
        "imu_mode_report": imu_mode_report,
        "gap_summary": all_gap,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", help="Local BY2 Fixposition root.")
    parser.add_argument("--body-imu", help="Local BY2 Go2 body-state text file.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-status-rows", type=int, default=None)
    parser.add_argument("--max-raw-rows", type=int, default=None)
    parser.add_argument("--max-body-messages", type=int, default=None)
    parser.add_argument("--max-filter-epochs", type=int, default=None)
    parser.add_argument("--end-margin-sec", type=float, default=5.0)
    parser.add_argument("--run-heading-offset-candidates", action="store_true")
    parser.add_argument(
        "--imu-propagation-modes",
        default="gyro_only_zero_dvel,quaternion_gravity_compensated",
    )
    parser.add_argument("--toy", action="store_true", help="Use toy standardized inputs.")
    args = parser.parse_args()
    if not args.toy and (not args.fix_root or not args.body_imu):
        parser.error("--fix-root and --body-imu are required unless --toy is used.")
    return args


def main() -> int:
    result = run_trial(_parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
