#!/usr/bin/env python3
"""Run N4H4R3A update timeline, overlap, and config parity audit.

中文说明：运行 port-core debug timeline，计算有效 overlap 期望更新数，并生成
runtime-only 报告；不使用 final_v23 输出作为 solver input。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import evaluate_port_clean_replay, write_json
from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import locate_clean_inputs, write_port_clean_config
from legsa_gins.evaluation.legsa_v23_port_config_parity import audit_port_clean_config
from legsa_gins.evaluation.legsa_v23_port_overlap_expectation import (
    classify_update_count,
    compute_overlap_expectation,
    parse_gnss_times,
    parse_imu_times,
)
from legsa_gins.evaluation.legsa_v23_port_runtime_loop_fix_decision import make_runtime_loop_fix_decision
from legsa_gins.evaluation.legsa_v23_port_update_timeline import analyze_runtime_loop_trace
from legsa_gins.evaluation.legsa_v23_port_parity_decision import make_port_parity_decision


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def _build(build_dir: str) -> None:
    for command in [["cmake", "-S", "cpp", "-B", build_dir], ["cmake", "--build", build_dir]]:
        completed = _run(command)
        if completed.returncode != 0:
            raise RuntimeError("command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_md(path: Path, overlap: dict, loop: dict, config: dict, decision: dict, summary: dict) -> None:
    path.write_text(
        "\n".join(
            [
                "# N4H4R3A Update Timeline Audit",
                "",
                "This diagnostic compares actual updates with effective IMU/GNSS overlap.",
                "It is not a performance result and it does not modify output for metrics.",
                "",
                f"- expected_update_count_min: {overlap.get('expected_update_count_min')}",
                f"- expected_update_count_max: {overlap.get('expected_update_count_max')}",
                f"- actual_update_count: {decision.get('actual_update_count')}",
                f"- update_count_low: {decision.get('update_count_low')}",
                f"- config_ok: {config.get('config_ok')}",
                f"- runtime_loop_fix_applied: {decision.get('runtime_loop_fix_applied')}",
                f"- recommended_next_stage: {decision.get('recommended_next_stage')}",
                f"- replay_H: {summary.get('horizontal_rmse_m')}",
                f"- replay_Up: {summary.get('up_rmse_m')}",
                f"- replay_Yaw: {summary.get('yaw_rmse_deg')}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_pipeline(args: argparse.Namespace) -> dict:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.allow_run:
        _build(args.build_dir)

    clean_inputs = locate_clean_inputs(args.clean_root)
    r3_config = Path(args.r3_root) / "config" / "legsa_v23_port_clean_replay.conf"
    config_path = r3_config if r3_config.exists() else Path(write_port_clean_config(clean_inputs, output)["config_path"])
    imu_times = parse_imu_times(clean_inputs["imu_path"]) if clean_inputs.get("imu_path") else []
    gnss_times = parse_gnss_times(clean_inputs["gnss_path"]) if clean_inputs.get("gnss_path") else []
    config_values = _read_config_times(config_path)
    overlap = compute_overlap_expectation(imu_times, gnss_times, config_values["starttime"], config_values["endtime"])

    run_dir = output / "run"
    command = [
        args.exe,
        "--config",
        str(config_path),
        "--output-dir",
        str(run_dir),
        "--debug-update-timeline",
        "--debug-output-dir",
        str(output),
    ]
    completed = _run(command) if args.allow_run else subprocess.CompletedProcess(command, 0, "", "")
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)

    snapshot = _load_json(output / "PORT_INPUT_TIMELINE_SNAPSHOT.json")
    loop_report = analyze_runtime_loop_trace(output / "PORT_RUNTIME_LOOP_TRACE.csv", output / "PORT_SKIPPED_GNSS_TRACE.csv")
    manifest = _load_json(run_dir / "RUN_MANIFEST.json")
    count_status = classify_update_count(overlap, int(manifest.get("actual_update_count", manifest.get("measurement_update_count", 0)) or 0))
    overlap.update(count_status)
    config_report = audit_port_clean_config(config_path, overlap, manifest)
    r3_gap = _load_json(Path(args.r3_root) / "LEGSA_PORT_CLEAN_REPLAY_GAP_SCREEN.json")
    decision = make_runtime_loop_fix_decision(
        overlap,
        loop_report,
        config_report,
        r3_gap,
        actual_update_count=int(manifest.get("actual_update_count", manifest.get("measurement_update_count", 0)) or 0),
        runtime_loop_fix_applied=bool(manifest.get("runtime_loop_fix_applied", False)),
    )

    summary = {}
    eval_nav = run_dir / "EVAL_NAV.csv"
    if eval_nav.exists() and (Path(args.dual_root) / "KF_GINS_Navresult.nav").exists():
        eval_report = evaluate_port_clean_replay(eval_nav, args.dual_root, output / "LEGSA_PORT_R3A_REPLAY_ERROR_SERIES.csv")
        summary = eval_report["summary"]
        write_json(output / "LEGSA_PORT_R3A_REPLAY_SUMMARY.json", summary)
        replay_decision = make_port_parity_decision(summary, {})
        write_json(output / "LEGSA_PORT_R3A_REPLAY_DECISION.json", replay_decision)
        decision["r3a_replay_parity_classification"] = replay_decision["parity_classification"]
        decision["r3a_replay_recommended_next_stage"] = replay_decision["recommended_next_stage"]

    write_json(output / "PORT_INPUT_TIMELINE_SNAPSHOT.json", snapshot)
    write_json(output / "PORT_OVERLAP_EXPECTATION_REPORT.json", overlap)
    write_json(output / "PORT_RUNTIME_LOOP_TRACE_REPORT.json", loop_report)
    write_json(output / "PORT_CLEAN_CONFIG_PARITY_REPORT.json", config_report)
    write_json(output / "PORT_RUNTIME_LOOP_FIX_DECISION_REPORT.json", decision)
    _write_md(output / "n4h4r3a_update_timeline_audit.md", overlap, loop_report, config_report, decision, summary)
    return {
        "snapshot": snapshot,
        "overlap": overlap,
        "runtime_loop": loop_report,
        "config": config_report,
        "decision": decision,
        "summary": summary,
    }


def _read_config_times(path: Path) -> dict[str, float]:
    start = 0.0
    end = 0.0
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() == "starttime":
            start = float(value.strip())
        elif key.strip() == "endtime":
            end = float(value.strip())
    return {"starttime": start, "endtime": end}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-root", default=str(Path.home() / "legsa_n4h2g_clean_replay"))
    parser.add_argument("--dual-root", default=str(Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"))
    parser.add_argument("--r3-root", default=str(Path.home() / "legsa_n4h4r3_port_clean_parity"))
    parser.add_argument("--output-dir", default=str(Path.home() / "legsa_n4h4r3a_update_timeline"))
    parser.add_argument("--build-dir", default="build/cpp")
    parser.add_argument("--exe", default="./build/cpp/legsa_v23_port_core_demo")
    parser.add_argument("--allow-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run_pipeline(parse_args(argv or sys.argv[1:]))
    print(json.dumps(report["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
