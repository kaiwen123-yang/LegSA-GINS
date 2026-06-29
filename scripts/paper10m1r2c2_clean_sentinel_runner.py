#!/usr/bin/env python3
"""Run PAPER10M1R2C2 clean sentinel solver/evaluator rows only."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.yaw_clean_sentinel_gate import evaluate_clean_sentinel_gate  # noqa: E402
from legsa_gins.evaluation.yaw_provider_lineage import (  # noqa: E402
    read_csv_rows,
    repair_provider_rows_from_source_yaw,
    write_csv_rows,
)
from legsa_gins.evaluation.yaw_semantic_audit import (  # noqa: E402
    read_eval_nav_yaw,
    read_raw_trace_heading_to_math,
    summarize_errors,
    yaw_errors_for_reference,
)
from legsa_gins.input_generation.status_yaw_builder import (  # noqa: E402
    apply_yaw_install_and_ned,
    build_a1_dual_diff_yaw_rows,
)
from legsa_gins.qm.qm_counter_schema import split_manifest_counters  # noqa: E402
from scripts.paper10m0_method_mode_loader import load_all, resolve_effective_feature_flags, validate_mode_safety  # noqa: E402
from scripts.paper10m1r2c_full_algorithm_matrix import (  # noqa: E402
    RuntimePaths,
    first_last_time,
    load_case_maps,
    load_manifest,
    read_reference_from_clean_provider,
    row_output_dir,
    run_one_row,
    sha256_text,
    write_csv,
    write_json,
)


METHODS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]


def _first_15col_time(path: Path) -> float:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            parts = line.split()
            if parts:
                return float(parts[0])
    return 0.0


def _source_yaw_rows(by2_fix_root: Path) -> list[dict[str, float]]:
    gnss1 = by2_fix_root / "gnss1-status.csv"
    with gnss1.open("r", encoding="utf-8-sig") as handle:
        header = handle.readline().strip().split(",")
        first = handle.readline().strip().split(",")
    time_index = header.index("Time")
    first_time = float(first[time_index])
    base_time = math.floor(first_time / 100.0) * 100.0
    rows, _ = build_a1_dual_diff_yaw_rows(
        by2_fix_root / "gnss1-status.csv",
        by2_fix_root / "gnss2-status.csv",
        base_time=base_time,
    )
    rows = apply_yaw_install_and_ned(rows, sign=1.0, offset_deg=0.0)
    return [{"time": float(row["aligned_time"]), "yaw_deg": float(row["yaw_ned_deg"])} for row in rows]


def _copy_repaired_clean_provider(
    source_root: Path,
    dest_parent: Path,
    *,
    by2_fix_root: Path,
    by2_statusyaw_gnss: Path,
) -> dict[str, Any]:
    dest = dest_parent / "BY2_CLEAN_CANONICAL"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_root, dest)
    yaw_path = dest / "02_GENERATED_PROVIDERS" / "dual_yaw_provider.csv"
    source_rows = _source_yaw_rows(by2_fix_root)
    provider_to_source_time_offset_sec = _first_15col_time(by2_statusyaw_gnss)
    repaired, summary = repair_provider_rows_from_source_yaw(
        read_csv_rows(yaw_path),
        source_rows,
        provider_to_source_time_offset_sec=provider_to_source_time_offset_sec,
    )
    write_csv_rows(yaw_path, repaired)
    summary["source_provider_alias"] = "<DEGRADED_PROVIDER_ROOT>/BY2_CLEAN_CANONICAL"
    summary["repaired_provider_alias"] = (
        "<PAPER10M1R2C2_RUNTIME_ROOT>/01_REPAIRED_CLEAN_PROVIDER/BY2_CLEAN_CANONICAL"
    )
    summary["raw_provider_overwritten"] = False
    summary["m1r2b_provider_overwritten"] = False
    write_json(dest / "PAPER10M1R2C2_YAW_PROVIDER_REPAIR_SUMMARY.json", summary)
    return {"root": dest, "summary": summary}


def _trace_yaw_metrics(eval_nav: Path, raw_trace_csv: Path) -> dict[str, Any]:
    nav_rows = read_eval_nav_yaw(eval_nav)
    trace = read_raw_trace_heading_to_math(raw_trace_csv, name="trace_heading_to_math")
    errors = yaw_errors_for_reference(nav_rows, trace, transform_name="direct_yaw", nav_stride=1)
    summary = summarize_errors(errors)
    return {
        "trace_heading_to_math_yaw_rmse_deg": summary.get("yaw_rmse_deg", math.nan),
        "trace_heading_to_math_yaw_p95_abs_error_deg": summary.get("yaw_p95_abs_error_deg", math.nan),
        "trace_heading_to_math_yaw_max_abs_error_deg": summary.get("yaw_max_abs_error_deg", math.nan),
        "trace_heading_to_math_rows": summary.get("row_count", 0),
        "yaw_reference_role": "trace_evaluation_only",
        "trace_solver_input": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    code_root = Path(args.code_root).resolve()
    exe = code_root / "build" / "cpp" / "legsa_v23_port_core_demo"
    if not exe.is_file():
        raise SystemExit(f"missing solver executable: {exe}")
    stage_root = Path(args.stage_root).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    out = stage_root / "04_CLEAN_SENTINEL"
    out.mkdir(parents=True, exist_ok=True)
    repaired_info = _copy_repaired_clean_provider(
        Path(args.m1r2b_provider_root).resolve() / "BY2_CLEAN_CANONICAL",
        runtime_root / "01_REPAIRED_CLEAN_PROVIDER",
        by2_fix_root=Path(args.by2_fix_root).resolve(),
        by2_statusyaw_gnss=Path(args.by2_statusyaw_gnss).resolve(),
    )
    repaired_provider_parent = repaired_info["root"].parent
    paths = RuntimePaths(
        stage_root=stage_root,
        runtime_root=runtime_root,
        export_root=Path(args.export_root).resolve(),
        m1r2a_stage_root=Path(args.m1r2a_stage_root).resolve(),
        m1r2b_stage_root=Path(args.m1r2b_stage_root).resolve(),
        provider_root=repaired_provider_parent,
        by2_imu=Path(args.by2_imu).resolve(),
        by2_statusyaw_gnss=Path(args.by2_statusyaw_gnss).resolve(),
        code_root=code_root,
    )
    roots = {
        "LEGSA_CODE_ROOT": paths.code_root,
        "PAPER10M1R2A_STAGE_ROOT": paths.m1r2a_stage_root,
        "PAPER10M1R2B_STAGE_ROOT": paths.m1r2b_stage_root,
        "PAPER10M1R2C2_STAGE_ROOT": paths.stage_root,
        "PAPER10M1R2C2_RUNTIME_ROOT": paths.runtime_root,
        "DEGRADED_PROVIDER_ROOT": Path(args.m1r2b_provider_root).resolve(),
        "EXPORT_ROOT": paths.export_root,
        "BY2_FIX_ROOT": paths.by2_imu.parent,
    }
    loaded = load_all(code_root)
    cases, providers, _ = load_case_maps(paths)
    imu_first, imu_last, _ = first_last_time(paths.by2_imu)
    status_first, _, _ = first_last_time(paths.by2_statusyaw_gnss)
    clean_first, clean_last, _ = first_last_time(
        repaired_info["root"] / "02_GENERATED_PROVIDERS" / "gnss_position_provider.csv",
        delimiter=",",
        has_header=True,
    )
    time_offset = status_first - clean_first
    starttime = max(imu_first, status_first)
    endtime = min(imu_last, clean_last + time_offset)
    provider_reference = read_reference_from_clean_provider(repaired_info["root"], time_offset)
    provider_status = {
        "raw_doppler": True,
        "go2_roll_pitch": True,
        "go2_horizontal_velocity": True,
        "go2_joint_factor": True,
        "go2_readiness_motion_metadata": False,
        "multi_state_qm": True,
    }

    queue_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    runtime_proof_rows: list[dict[str, Any]] = []
    for index, method in enumerate(METHODS):
        row_id = f"PAPER10M1R2C2_clean_sentinel_{index:04d}_{method}"
        queue_row = {
            "row_id": row_id,
            "queue_id": row_id,
            "case_id": "BY2_CLEAN_CANONICAL",
            "case_index": 0,
            "dataset": "BY2",
            "degradation_type_id": "CLEAN",
            "seed_index": "none",
            "method_mode_id": method,
            "provider_root": "<PAPER10M1R2C2_RUNTIME_ROOT>/01_REPAIRED_CLEAN_PROVIDER/BY2_CLEAN_CANONICAL",
            "provider_root_actual": str(repaired_info["root"]),
            "provider_ready": "true",
            "run_allowed_now": "true",
            "sentinel_only": "true",
        }
        queue_rows.append(queue_row)
        mode = loaded["method_modes"][method].data
        effective = resolve_effective_feature_flags(mode, provider_status)
        safety = validate_mode_safety(mode, effective)
        if safety:
            raise SystemExit("; ".join(safety))
        raw_result = run_one_row(
            row=queue_row,
            case=cases["BY2_CLEAN_CANONICAL"],
            provider_manifest=providers["BY2_CLEAN_CANONICAL"],
            mode=mode,
            effective_flags=effective,
            config_sha256=loaded["config_sha256"],
            paths=paths,
            time_offset=time_offset,
            starttime=starttime,
            endtime=endtime,
            reference=provider_reference,
            roots=roots,
            force=bool(args.force),
        )
        output_dir = row_output_dir(paths, method, row_id)
        trace_metrics = _trace_yaw_metrics(output_dir / "EVAL_NAV.csv", Path(args.raw_trace_csv).resolve())
        manifest = load_manifest(output_dir / "RUN_MANIFEST.json")
        qm_fields = split_manifest_counters(
            manifest,
            qm_trace_required=bool(effective.get("enable_multi_state_qm")),
            qm_trace_file_exists=(output_dir / "QM_TRACE.csv").is_file(),
        )
        write_json(
            output_dir / "YAW_PROVIDER_DUMP.json",
            {
                "provider_alias": queue_row["provider_root"],
                "yaw_frame": "solver_visible_body_heading_ned_deg",
                "provider_repair_summary": repaired_info["summary"],
                "trace_tuned_yaw_fix": False,
                "trace_solver_input": False,
            },
        )
        result = dict(raw_result)
        result["provider_reference_yaw_rmse_deg"] = raw_result.get("yaw_rmse_deg", "")
        result["yaw_rmse_deg"] = trace_metrics["trace_heading_to_math_yaw_rmse_deg"]
        result.update(trace_metrics)
        result.update(qm_fields)
        result["yaw_provider_lineage"] = "BY2_A1_dual_diff_lateral_conversion"
        result["trace_tuned_yaw_fix"] = False
        result["final_v23_output_solver_input"] = False
        result["output_only_correction_used"] = False
        result["epoch_deleted_for_metric"] = False
        result_rows.append(result)
        runtime_proof_rows.append(
            {
                "row_id": row_id,
                "method_mode_id": method,
                "nav_exists": (output_dir / "NAV.csv").is_file() or (output_dir / "LegSA_PORT_NAV.nav").is_file(),
                "std_exists": (output_dir / "STD.csv").is_file() or (output_dir / "LegSA_PORT_STD.csv").is_file(),
                "nav_equivalent_file": "LegSA_PORT_NAV.nav",
                "std_equivalent_file": "LegSA_PORT_STD.csv",
                "eval_nav_exists": (output_dir / "EVAL_NAV.csv").is_file(),
                "run_manifest_exists": (output_dir / "RUN_MANIFEST.json").is_file(),
                "feature_flag_dump_exists": (output_dir / "FEATURE_FLAGS.json").is_file(),
                "dataset_role_dump_exists": (output_dir / "DATASET_ROLE_DUMP.json").is_file(),
                "method_mode_dump_exists": (output_dir / "METHOD_MODE_DUMP.json").is_file(),
                "yaw_provider_dump_exists": (output_dir / "YAW_PROVIDER_DUMP.json").is_file(),
                "forbidden_input_audit_exists": (output_dir / "FORBIDDEN_INPUT_CHECK.json").is_file(),
                "runtime_log_exists": (output_dir / "logs" / "stdout_attempt0.txt").is_file(),
                "solver_completed": raw_result.get("solver_completed", False),
                "evaluator_completed": raw_result.get("evaluator_completed", False),
            }
        )

    gate = evaluate_clean_sentinel_gate(result_rows)
    write_csv(out / "PAPER10M1R2C2_CLEAN_SENTINEL_QUEUE.csv", queue_rows)
    write_csv(out / "PAPER10M1R2C2_CLEAN_SENTINEL_RESULT_TABLE.csv", result_rows)
    write_csv(out / "PAPER10M1R2C2_CLEAN_SENTINEL_RUNTIME_PROOF.csv", runtime_proof_rows)
    gate_lines = [
        "# PAPER10M1R2C2 Clean Sentinel Yaw Gate",
        "",
        f"Gate status: `{gate['gate_status']}`.",
        "",
        "Yaw RMSE is computed against trace heading-to-math as evaluation-only reference.",
        "Provider-reference yaw RMSE is retained in `provider_reference_yaw_rmse_deg`.",
        "",
        "Blockers:",
    ]
    gate_lines.extend([f"- {item}" for item in gate["blockers"]] or ["- none"])
    (out / "PAPER10M1R2C2_CLEAN_SENTINEL_YAW_GATE.md").write_text(
        "\n".join(gate_lines) + "\n", encoding="utf-8"
    )
    return {"row_count": len(result_rows), "gate_status": gate["gate_status"], "gate_pass": gate["pass"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--export-root", required=True)
    parser.add_argument("--m1r2a-stage-root", required=True)
    parser.add_argument("--m1r2b-stage-root", required=True)
    parser.add_argument("--m1r2b-provider-root", required=True)
    parser.add_argument("--by2-imu", required=True)
    parser.add_argument("--by2-fix-root", required=True)
    parser.add_argument("--by2-statusyaw-gnss", required=True)
    parser.add_argument("--raw-trace-csv", required=True)
    parser.add_argument("--code-root", default=str(REPO_ROOT))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
