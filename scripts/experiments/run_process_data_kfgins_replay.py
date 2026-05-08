#!/usr/bin/env python3
"""Run external KF-GINS on process_data-compatible BY2 inputs.

中文说明：本脚本只做 baseline replay / evaluator 工作；不修改外部
`/home/kaiwen/KF-GINS`，不把 trace/reference/user_io 输出作为 solver input，
不做 output-only correction，也不生成 proposed-method 性能结论。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
BASELINE_SCRIPT_ROOT = REPO_ROOT / "baseline/final_v23_reproduction/scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(BASELINE_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(BASELINE_SCRIPT_ROOT))

from legsa_gins.evaluation.trajectory_metrics import (  # noqa: E402
    align_by_timestamp,
    compute_errors,
    load_eval_nav,
    summary_metrics,
    write_error_series,
    write_summary,
)
from standardize_final_v23_outputs import standardize_outputs  # noqa: E402


DEFAULT_BASE_TIME = 1772784000.0
DEFAULT_STARTTIME = 66.0
DEFAULT_ENDTIME = 340.0
REPLAY_OUTPUTS = [
    "KF_GINS_Navresult.nav",
    "KF_GINS_STD.txt",
    "KF_GINS_IMU_ERR.txt",
]


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    json_path = Path(path)
    if not json_path.exists():
        return {"missing_report_path": str(json_path)}
    return json.loads(json_path.read_text(encoding="utf-8"))


def _count_nonempty_rows(path: str | Path) -> int:
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip())


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def write_replay_config(
    *,
    template_config: str | Path,
    gnss: str | Path,
    imu: str | Path,
    output_dir: str | Path,
    config_path: str | Path,
    starttime: float,
    endtime: float,
    imudatarate: int,
) -> Path:
    """Write a replay YAML by overriding path/time fields only."""

    # 中文说明：配置继承外部 KF-GINS 模板参数，只覆盖输入、输出和时间窗。
    # The external template keeps model parameters; this only rewires IO/time.
    template = yaml.safe_load(Path(template_config).read_text(encoding="utf-8"))
    template["imupath"] = str(Path(imu).resolve())
    template["gnsspath"] = str(Path(gnss).resolve())
    template["outputpath"] = str(Path(output_dir).resolve())
    template["imudatalen"] = 7
    template["imudatarate"] = int(imudatarate)
    template["imudataincremental"] = int(template.get("imudataincremental", 1))
    template["imudataformat"] = int(template.get("imudataformat", 0))
    template["gnss_format"] = int(template.get("gnss_format", 0))
    template["starttime"] = float(starttime)
    template["endtime"] = float(endtime)

    output = Path(config_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(template, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output


def run_external_kfgins(
    *,
    executable: str | Path,
    config: str | Path,
    timeout_sec: int,
) -> dict[str, Any]:
    exe = Path(executable)
    cfg = Path(config)
    result: dict[str, Any] = {
        "algorithm_role": "baseline",
        "executable": str(exe),
        "config": str(cfg),
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    if not exe.is_file():
        result["evidence_status"] = "executable_missing"
        result["returncode"] = None
        return result
    if not cfg.is_file():
        result["evidence_status"] = "config_missing"
        result["returncode"] = None
        return result
    try:
        completed = subprocess.run(
            [str(exe), str(cfg)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        result["evidence_status"] = "run_timeout"
        result["returncode"] = None
        result["stdout_tail"] = _tail(exc.stdout or "")
        result["stderr_tail"] = _tail(exc.stderr or "")
        return result

    result["returncode"] = completed.returncode
    result["stdout_tail"] = _tail(completed.stdout)
    result["stderr_tail"] = _tail(completed.stderr)
    result["evidence_status"] = (
        "executed_no_oracle_claim" if completed.returncode == 0 else "run_failed"
    )
    return result


def load_process_data_trace_reference(
    trace_path: str | Path, *, base_time: float
) -> list[dict[str, float]]:
    """Load Fixposition trace as evaluator-only reference rows."""

    rows: list[dict[str, float]] = []
    with Path(trace_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            timestamp = float(raw["time"])
            if timestamp > 1_000_000_000:
                timestamp -= base_time
            rows.append(
                {
                    "timestamp": timestamp,
                    "lat_deg": float(raw["lat"]),
                    "lon_deg": float(raw["lon"]),
                    "height_m": float(raw["height"]),
                    "roll_deg": float(raw["roll"]),
                    "pitch_deg": float(raw["pitch"]),
                    "yaw_deg": float(raw["yaw"]),
                }
            )
    rows.sort(key=lambda item: item["timestamp"])
    return rows


def evaluate_against_trace(
    *,
    eval_nav_csv: str | Path,
    trace_csv: str | Path,
    output_dir: str | Path,
    base_time: float,
    max_dt: float,
) -> dict[str, Any]:
    est_rows = load_eval_nav(eval_nav_csv)
    ref_rows = load_process_data_trace_reference(trace_csv, base_time=base_time)
    aligned = align_by_timestamp(est_rows, ref_rows, max_dt=max_dt)
    errors = compute_errors(aligned)
    summary = summary_metrics(errors)
    summary.update(
        {
            "phase": "N4H2",
            "algorithm_role": "baseline",
            "reference_role": "trace_evaluation_only",
            "trace_solver_input": False,
            "trace_used_for_tuning": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "formal_performance_claim_allowed": False,
            "max_alignment_dt_sec": float(max_dt),
            "est_row_count": len(est_rows),
            "trace_row_count": len(ref_rows),
            "aligned_row_count": len(aligned),
        }
    )
    out = Path(output_dir)
    write_error_series(errors, out / "FINAL_V23_TRACE_ERROR_SERIES.csv")
    write_summary(summary, out / "FINAL_V23_TRACE_EVAL_SUMMARY.json")
    return summary


def _output_inventory(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir)
    inventory: dict[str, Any] = {}
    for name in REPLAY_OUTPUTS:
        path = root / name
        inventory[name] = {
            "exists": path.exists(),
            "row_count": _count_nonempty_rows(path) if path.exists() else 0,
            "path": str(path),
        }
    return inventory


def write_markdown_report(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    generation = report.get("input_generation_report", {})
    coverage = report.get("input_generation_coverage", {})
    run = report.get("run_attempt", {})
    evaluation = report.get("evaluation", {})
    inventory = report.get("output_inventory", {})
    lines = [
        "# N4H2 process_data-compatible KF-GINS replay report",
        "",
        "## Verdict",
        "",
        f"- replay_attempted: {str(report['replay_attempted']).lower()}",
        f"- replay_success: {str(report['replay_success']).lower()}",
        f"- parse_success: {str(report['parse_success']).lower()}",
        f"- evaluation_success: {str(report['evaluation_success']).lower()}",
        "- formal_performance_claim_allowed: false",
        "- trace_solver_input: false",
        "- output_only_correction: false",
        "",
        "## Input Generation",
        "",
        f"- gnss_rows: {generation.get('gnss_row_count')}",
        f"- imu_rows: {generation.get('imu_row_count')}",
        f"- coverage_status: {coverage.get('coverage_status')}",
        f"- output_to_status_ratio: {coverage.get('output_to_status_ratio')}",
        f"- pvt_velocity_rows: {generation.get('pvt_velocity_row_count')}",
        f"- yaw_rows: {generation.get('yaw_row_count')}",
        "",
        "## Replay Outputs",
        "",
        f"- run_status: {run.get('evidence_status')}",
        f"- returncode: {run.get('returncode')}",
    ]
    for name, info in inventory.items():
        lines.append(f"- {name}: exists={info.get('exists')} rows={info.get('row_count')}")
    lines.extend(
        [
            "",
            "## Evaluation",
            "",
            f"- evidence_status: {evaluation.get('evidence_status')}",
            f"- aligned_rows: {evaluation.get('aligned_row_count')}",
            f"- horizontal_rmse_m: {evaluation.get('horizontal_rmse_m')}",
            f"- horizontal_p95_m: {evaluation.get('horizontal_p95_m')}",
            f"- up_rmse_m: {evaluation.get('up_rmse_m')}",
            f"- yaw_rmse_deg: {evaluation.get('yaw_rmse_deg')}",
            f"- yaw_p95_deg: {evaluation.get('yaw_p95_deg')}",
            "",
            "## Boundary",
            "",
            "This report is baseline replay evidence only. The generated `.gnss` / `.imu` "
            "files are process_data-compatible runtime inputs and are not proposed solver "
            "outputs. Trace is used only after replay for evaluation alignment.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kfgins-root", default="/home/kaiwen/KF-GINS")
    parser.add_argument("--executable", default="/home/kaiwen/KF-GINS/bin/KF-GINS")
    parser.add_argument("--template-config", default="/home/kaiwen/KF-GINS/config/kf-gins.yaml")
    parser.add_argument("--gnss", required=True)
    parser.add_argument("--imu", required=True)
    parser.add_argument("--trace")
    parser.add_argument("--input-report")
    parser.add_argument("--input-coverage-report")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-time", type=float, default=DEFAULT_BASE_TIME)
    parser.add_argument("--starttime", type=float, default=DEFAULT_STARTTIME)
    parser.add_argument("--endtime", type=float, default=DEFAULT_ENDTIME)
    parser.add_argument("--imudatarate", type=int, default=500)
    parser.add_argument("--max-dt", type=float, default=0.05)
    parser.add_argument("--timeout-sec", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    replay_dir = output_dir / "kfgins_output"
    standardized_dir = output_dir / "standardized"
    eval_dir = output_dir / "evaluation"
    replay_dir.mkdir(parents=True, exist_ok=True)

    config_path = output_dir / "kf-gins-n4h2-replay.yaml"
    write_replay_config(
        template_config=args.template_config,
        gnss=args.gnss,
        imu=args.imu,
        output_dir=replay_dir,
        config_path=config_path,
        starttime=args.starttime,
        endtime=args.endtime,
        imudatarate=args.imudatarate,
    )

    run_attempt = run_external_kfgins(
        executable=args.executable,
        config=config_path,
        timeout_sec=args.timeout_sec,
    )
    (output_dir / "RUN_ATTEMPT.json").write_text(
        json.dumps(run_attempt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    inventory = _output_inventory(replay_dir)
    replay_success = (
        run_attempt.get("returncode") == 0
        and all(item["exists"] and item["row_count"] > 0 for item in inventory.values())
    )

    parse_success = False
    evaluation_success = False
    evaluation: dict[str, Any] = {}
    if replay_success:
        standardize_outputs(
            nav=replay_dir / "KF_GINS_Navresult.nav",
            std=replay_dir / "KF_GINS_STD.txt",
            imu_err=replay_dir / "KF_GINS_IMU_ERR.txt",
            output_dir=standardized_dir,
            dataset_name="BY2_N4H2_process_data_kfgins_replay",
            source_root=args.kfgins_root,
        )
        parse_success = True
        if args.trace:
            evaluation = evaluate_against_trace(
                eval_nav_csv=standardized_dir / "FINAL_V23_EVAL_NAV.csv",
                trace_csv=args.trace,
                output_dir=eval_dir,
                base_time=args.base_time,
                max_dt=args.max_dt,
            )
            evaluation_success = bool(evaluation.get("aligned_row_count", 0) > 0)
    elif run_attempt.get("evidence_status") == "run_failed":
        evaluation = {"evidence_status": "not_evaluated_replay_failed"}
    else:
        evaluation = {"evidence_status": "not_evaluated_replay_not_available"}

    report: dict[str, Any] = {
        "phase": "N4H2",
        "algorithm_role": "baseline",
        "kfgins_root": args.kfgins_root,
        "config_path": str(config_path),
        "gnss_path": str(Path(args.gnss).resolve()),
        "imu_path": str(Path(args.imu).resolve()),
        "trace_path": args.trace,
        "input_generation_report": _load_json(args.input_report),
        "input_generation_coverage": _load_json(args.input_coverage_report),
        "run_attempt": run_attempt,
        "output_inventory": inventory,
        "evaluation": evaluation,
        "replay_attempted": True,
        "replay_success": replay_success,
        "parse_success": parse_success,
        "evaluation_success": evaluation_success,
        "trace_solver_input": False,
        "trace_used_for_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "formal_performance_claim_allowed": False,
        "raw_data_committed": False,
    }
    (output_dir / "N4H2_REPLAY_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = write_markdown_report(report, output_dir / "N4H2_REPLAY_REPORT.md")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"Wrote {report_path}")
    return 0 if replay_success and parse_success and (not args.trace or evaluation_success) else 1


if __name__ == "__main__":
    raise SystemExit(main())
