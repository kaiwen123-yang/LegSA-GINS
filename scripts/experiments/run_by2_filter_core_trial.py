#!/usr/bin/env python3
"""Run the N4F BY2 filter-core diagnostic trial.

中文说明：本脚本编排真实或 toy diagnostic trial；trace 只在 evaluation 阶段读取。
"""

from __future__ import annotations

import argparse
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

from legsa_gins.evaluation.case_review_report import generate_case_review  # noqa: E402
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


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, check=True)


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
    output_dir: Path,
    selected_receiver_source: str,
    imu_adapter_summary: dict[str, Any],
    receiver_adapter_summary: dict[str, Any],
    summary: dict[str, Any],
    classification: dict[str, Any],
    toy: bool,
) -> None:
    manifest = {
        "phase": "N4F",
        "toy_inputs": toy,
        "output_dir": str(output_dir),
        "selected_receiver_source": selected_receiver_source,
        "trace_solver_input": False,
        "trace_evaluation_only": True,
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
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_trial(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    inputs_dir = output_dir / "inputs"
    run_dir = output_dir / "run"
    evaluation_dir = output_dir / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    _standardize_inputs(args, inputs_dir)

    imu_csv = inputs_dir / "BY2_BODY_IMU_INCREMENT_STANDARD.csv"
    imu_summary = convert_go2_body_state_to_imu_increments(
        inputs_dir / "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
        imu_csv,
        max_rows=args.max_body_messages,
    )

    receiver_status_csv, selected_receiver_source = select_receiver_status_csv(inputs_dir)
    receiver_csv = inputs_dir / "BY2_RECEIVER_MEASUREMENT_TRIAL.csv"
    receiver_summary = make_receiver_measurement_trial_csv(
        receiver_status_csv,
        receiver_csv,
        source_name=selected_receiver_source,
    )

    _run(["cmake", "-S", "cpp", "-B", "build/cpp"])
    _run(["cmake", "--build", "build/cpp"])
    command = [
        str(REPO_ROOT / "build/cpp/legsa_gins"),
        "--run-filter-csv",
        "--imu-csv",
        str(imu_csv),
        "--receiver-csv",
        str(receiver_csv),
        "--output-dir",
        str(run_dir),
    ]
    if args.max_filter_epochs is not None:
        command.extend(["--max-epochs", str(args.max_filter_epochs)])
    _run(command)

    est_rows = load_eval_nav(run_dir / "EVAL_NAV.csv")
    ref_rows = load_trace_reference(inputs_dir / "BY2_TRACE_REFERENCE_EVAL_ONLY.csv")
    errors = compute_errors(align_by_timestamp(est_rows, ref_rows, max_dt=0.05))
    write_error_series(errors, evaluation_dir / "error_series.csv")
    summary = summary_metrics(errors)
    write_summary(summary, evaluation_dir / "summary.json")

    trial_manifest_path = output_dir / "BY2_FILTER_TRIAL_MANIFEST.json"
    _write_trial_manifest(
        trial_manifest_path,
        output_dir=output_dir,
        selected_receiver_source=selected_receiver_source,
        imu_adapter_summary=imu_summary,
        receiver_adapter_summary=receiver_summary,
        summary=summary,
        classification={},
        toy=args.toy,
    )
    classification = generate_case_review(
        output_path=output_dir / "case_review.md",
        run_dir=run_dir,
        input_manifest_path=inputs_dir / "BY2_INPUT_MANIFEST.json",
        trial_manifest_path=trial_manifest_path,
        summary_path=evaluation_dir / "summary.json",
    )
    _write_trial_manifest(
        trial_manifest_path,
        output_dir=output_dir,
        selected_receiver_source=selected_receiver_source,
        imu_adapter_summary=imu_summary,
        receiver_adapter_summary=receiver_summary,
        summary=summary,
        classification=classification,
        toy=args.toy,
    )
    generate_case_review(
        output_path=output_dir / "case_review.md",
        run_dir=run_dir,
        input_manifest_path=inputs_dir / "BY2_INPUT_MANIFEST.json",
        trial_manifest_path=trial_manifest_path,
        summary_path=evaluation_dir / "summary.json",
    )
    return {
        "output_dir": str(output_dir),
        "summary": summary,
        "classification": classification,
        "selected_receiver_source": selected_receiver_source,
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
