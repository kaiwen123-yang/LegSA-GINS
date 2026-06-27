#!/usr/bin/env python3
"""Run the PAPER10M0 locked BY2 runner-mapping smoke.

中文说明：本脚本只执行 4 行 M0 smoke，并生成 M1 队列草案。它不运行
PAPER10M1/full matrix，不读取 trace 作为 solver 输入，也不把 runtime 输出写入 Git。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.paper10m0_guard_validator import validate_guard_state
from scripts.paper10m0_method_mode_loader import load_all, resolve_effective_feature_flags
from scripts.paper10m0_queue_builder import (
    build_paper10m1_queue,
    smoke_queue,
    write_csv,
)
from scripts.paper10m0_runner_adapter import Paper10M0Paths, provider_status_from_paths, run_all_smoke_rows
from src.legsa_gins.raw_gnss.raw_doppler_velocity_factor_builder import build_factor_file_from_provider


STAGE_DIRS = [
    "00_STAGE_REPORT",
    "01_GIT",
    "02_ENV",
    "03_STORAGE_AND_DATA",
    "04_QUEUE",
    "05_SMOKE",
    "06_GUARDS",
    "07_TESTS",
    "08_NEXT_STAGE",
    "09_EXPORT_CLEAN_FOR_GPT",
]


def _path_arg(value: str | None) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _exists(path: Path | None) -> bool:
    return bool(path and path.exists())


def _provider_status(paths: Paper10M0Paths) -> dict[str, bool]:
    status = provider_status_from_paths(paths)
    status["by2_imu"] = paths.by2_imu.is_file()
    status["by2_gnss"] = paths.by2_gnss.is_file()
    status["by2_body"] = paths.by2_body.is_file()
    status["by2_trace_eval_only"] = bool(paths.by2_trace and paths.by2_trace.is_file())
    return status


def _build_raw_doppler_factor(
    *,
    source_provider: Path | None,
    clean_gnss: Path,
    runtime_root: Path,
) -> tuple[Path | None, dict[str, Any]]:
    if not source_provider:
        return None, {"raw_doppler_solver_activation_allowed": False, "blocker_reasons": ["provider_arg_missing"]}
    result = build_factor_file_from_provider(
        source_provider,
        runtime_root / "providers" / "raw_doppler",
        clean_gnss_path=clean_gnss,
        source_type="rtklib_doppler_helper_velocity",
    )
    factor_path = Path(result["factor_csv_path"]) if result.get("factor_csv_generated") else None
    return factor_path, result


def _queue_summary(rows: list[dict[str, str]], smoke_rows: list[dict[str, str]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["method_mode_id"]] = counts.get(row["method_mode_id"], 0) + 1
    lines = [
        "# PAPER10M1 BY2 Full Matrix Queue Draft Summary",
        "",
        "- Stage: PAPER10M0_CANONICAL_BY2_FULL_MATRIX_PREFLIGHT_RUNNER_MAPPING_AND_SMOKE_LOCK",
        f"- Draft rows: {len(rows)}",
        f"- Smoke rows allowed in PAPER10M0: {len(smoke_rows)}",
        "- run_allowed_now: false for every PAPER10M1 row",
        "- human_approval_required: true for every PAPER10M1 row",
        "- This stage did not execute PAPER10M1 or any full matrix.",
        "",
        "## Rows By Method Mode",
    ]
    for mode_id, count in counts.items():
        lines.append(f"- {mode_id}: {count}")
    return "\n".join(lines) + "\n"


def _guard_report(guard: dict[str, Any]) -> str:
    issues = guard.get("issues", [])
    issue_text = "\n".join(f"- {issue}" for issue in issues) if issues else "- none"
    return (
        "# PAPER10M0 Guard Validation Report\n\n"
        f"- status: {guard['status']}\n"
        f"- paper10m1_queue_locked: {guard['paper10m1_queue_locked']}\n"
        f"- smoke_row_count: {guard['smoke_row_count']}\n"
        f"- full_matrix_run: {guard['full_matrix_run']}\n"
        f"- paper10m1_run: {guard['paper10m1_run']}\n"
        f"- paper10h_run: {guard['paper10h_run']}\n"
        f"- by3_xb_pg_matrix_run: {guard['by3_xb_pg_matrix_run']}\n"
        f"- benchmark_full_matrix_run: {guard['benchmark_full_matrix_run']}\n\n"
        "## Issues\n"
        f"{issue_text}\n"
    )


def _forbidden_input_rows(smoke_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "trace_used_online",
        "final_v23_output_used_as_input",
        "legsa_output_used_as_input",
        "benchmark_output_used_as_input",
        "per_case_tuning_used",
        "output_only_correction_used",
        "qa_fallback_as_final_method",
    ]
    rows = []
    for result in smoke_results:
        for key in keys:
            rows.append(
                {
                    "row_id": result["row_id"],
                    "method_mode_id": result["method_mode_id"],
                    "check": key,
                    "observed_value": result.get(key, False),
                    "status": "pass" if str(result.get(key, False)).lower() == "false" else "fail",
                }
            )
    return rows


def _runtime_proof_rows(smoke_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "row_id",
        "method_mode_id",
        "case_id",
        "runtime_output_alias",
        "runtime_config_alias",
        "runner_launched",
        "solver_completed",
        "nav_exists",
        "std_exists",
        "metrics_exists",
        "run_manifest_exists",
        "feature_flag_dump_exists",
        "dataset_role_dump_exists",
        "source_trace_exists_or_not_required",
        "qm_trace_exists_or_not_required",
        "status",
        "blocker",
    ]
    return [{field: result.get(field, "") for field in fields} for result in smoke_results]


def _sanitized_smoke_rows(smoke_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in smoke_results:
        row = dict(result)
        row.pop("runner_command", None)
        if "blocker" in row and isinstance(row["blocker"], str):
            row["blocker"] = row["blocker"].replace(str(REPO_ROOT), "<LEGSA_CODE_ROOT>")
        rows.append(row)
    return rows


def _contract_rows(smoke_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "nav_exists",
        "std_exists",
        "metrics_exists",
        "run_manifest_exists",
        "feature_flag_dump_exists",
        "dataset_role_dump_exists",
        "source_trace_exists_or_not_required",
        "qm_trace_exists_or_not_required",
        "trace_used_online",
        "final_v23_output_used_as_input",
        "legsa_output_used_as_input",
        "benchmark_output_used_as_input",
        "per_case_tuning_used",
        "output_only_correction_used",
    ]
    rows = []
    for result in smoke_results:
        for field in fields:
            expected = "false" if field.endswith("_used_online") or "_used_as_input" in field or field.endswith("_used") else "true"
            rows.append(
                {
                    "row_id": result["row_id"],
                    "method_mode_id": result["method_mode_id"],
                    "contract_item": field,
                    "observed_value": result.get(field, ""),
                    "expected": expected,
                    "status": "pass" if (
                        str(result.get(field, "")).lower() == expected
                        or field in {"source_trace_exists_or_not_required", "qm_trace_exists_or_not_required"}
                        and str(result.get(field, "")).lower() == "true"
                    ) else "fail",
                }
            )
    return rows


def _sanitized_raw_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    result = dict(raw_result)
    if result.get("factor_csv_path"):
        result["factor_csv_path"] = "<PAPER10M0_SMOKE_RUNTIME_ROOT>/providers/raw_doppler/RAW_DOPPLER_VELOCITY_FACTORS.csv"
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--by2-imu", required=True)
    parser.add_argument("--by2-gnss", required=True)
    parser.add_argument("--by2-body", required=True)
    parser.add_argument("--by2-trace")
    parser.add_argument("--raw-doppler-source-provider", required=True)
    parser.add_argument("--go2-attitude-provider", required=True)
    parser.add_argument("--go2-horizontal-velocity-provider", required=True)
    parser.add_argument("--go2-joint-provider", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    code_root = Path(args.code_root).resolve()
    project_root = Path(args.project_root).resolve()
    stage_root = Path(args.stage_root).resolve()
    runtime_root = Path(args.runtime_root).resolve()
    for dirname in STAGE_DIRS:
        (stage_root / dirname).mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    raw_factor_path, raw_result = _build_raw_doppler_factor(
        source_provider=_path_arg(args.raw_doppler_source_provider),
        clean_gnss=_path_arg(args.by2_gnss) or Path(args.by2_gnss),
        runtime_root=runtime_root,
    )
    paths = Paper10M0Paths(
        code_root=code_root,
        project_root=project_root,
        runtime_root=runtime_root,
        by2_imu=_path_arg(args.by2_imu) or Path(args.by2_imu),
        by2_gnss=_path_arg(args.by2_gnss) or Path(args.by2_gnss),
        by2_body=_path_arg(args.by2_body) or Path(args.by2_body),
        by2_trace=_path_arg(args.by2_trace),
        raw_doppler_provider=raw_factor_path,
        go2_attitude_provider=_path_arg(args.go2_attitude_provider),
        go2_horizontal_velocity_provider=_path_arg(args.go2_horizontal_velocity_provider),
        go2_joint_provider=_path_arg(args.go2_joint_provider),
    )
    provider_status = _provider_status(paths)
    loaded = load_all(code_root)
    mode_flags = {
        mode_id: resolve_effective_feature_flags(frozen.data, provider_status_from_paths(paths))
        for mode_id, frozen in loaded["method_modes"].items()
    }

    queue_rows = build_paper10m1_queue(mode_flags, "<PAPER10M1_FULL_MATRIX_ROOT>")
    smoke_rows = smoke_queue()
    write_csv(stage_root / "04_QUEUE" / "PAPER10M1_BY2_FULL_MATRIX_QUEUE_DRAFT.csv", queue_rows)
    _write_text(
        stage_root / "04_QUEUE" / "PAPER10M1_BY2_FULL_MATRIX_QUEUE_SUMMARY.md",
        _queue_summary(queue_rows, smoke_rows),
    )
    write_csv(stage_root / "05_SMOKE" / "PAPER10M0_SMOKE_QUEUE.csv", smoke_rows)

    smoke_results = run_all_smoke_rows(paths)
    sanitized_smoke_results = _sanitized_smoke_rows(smoke_results)
    _write_csv(stage_root / "05_SMOKE" / "PAPER10M0_SMOKE_RESULT_TABLE.csv", sanitized_smoke_results)
    _write_csv(stage_root / "05_SMOKE" / "PAPER10M0_RUNTIME_PROOF_TABLE.csv", _runtime_proof_rows(smoke_results))
    _write_csv(stage_root / "05_SMOKE" / "PAPER10M0_OUTPUT_CONTRACT_VALIDATION.csv", _contract_rows(smoke_results))

    guard = validate_guard_state(
        queue_rows=queue_rows,
        smoke_rows=smoke_rows,
        smoke_results=sanitized_smoke_results,
        repo_root=code_root,
    )
    _write_text(stage_root / "06_GUARDS" / "PAPER10M0_GUARD_VALIDATION_REPORT.md", _guard_report(guard))
    _write_csv(stage_root / "06_GUARDS" / "PAPER10M0_FORBIDDEN_INPUT_AUDIT.csv", _forbidden_input_rows(sanitized_smoke_results))

    summary = {
        "stage": "PAPER10M0_CANONICAL_BY2_FULL_MATRIX_PREFLIGHT_RUNNER_MAPPING_AND_SMOKE_LOCK",
        "queue_rows": len(queue_rows),
        "smoke_rows": len(smoke_results),
        "smoke_pass_rows": sum(1 for row in smoke_results if row["status"] == "pass"),
        "guard_status": guard["status"],
        "raw_doppler_alignment": _sanitized_raw_result(raw_result),
        "provider_status": provider_status,
        "paper10m1_executed": False,
        "full_matrix_executed": False,
        "paper10h_executed": False,
        "runtime_root_alias": "<PAPER10M0_SMOKE_RUNTIME_ROOT>",
    }
    _write_json(stage_root / "05_SMOKE" / "PAPER10M0_SMOKE_SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if guard["status"] == "pass" and summary["smoke_pass_rows"] == len(smoke_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
