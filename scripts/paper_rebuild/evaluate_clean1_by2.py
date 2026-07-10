#!/usr/bin/env python3
"""Offline-only evaluator for the completed fixed CLEAN1 four-run set."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.formal_manifest import assert_formal_run_manifest
from legsa_gins.paper_rebuild.formal_runner import RUN_DIRECTORY_NAMES
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic
from legsa_gins.paper_rebuild.methods import FORMAL_METHOD_ORDER, load_method_catalog
from legsa_gins.paper_rebuild.paths import (
    CleanPaths,
    assert_clean1_path_contract,
    is_within,
    legacy_reason,
    load_clean_paths,
)
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group
from legsa_gins.paper_rebuild.evidence import (
    BY2_TRACE_RELATIVE_PATH,
    parse_strace_openat_paths,
)


def _evaluator_file_open_crosscheck(
    strace_path: Path,
    destination: Path,
    *,
    paths: CleanPaths,
    solver_output: Path,
    reference: Path,
    window: Path,
    evaluator: Path,
    method_output: Path,
) -> dict[str, object]:
    opened = parse_strace_openat_paths(strace_path, cwd=REPO_ROOT)
    expected = {
        "current_solver_output": solver_output.resolve(strict=True),
        "evaluation_only_trace": reference.resolve(strict=True),
        "window_contract": window.resolve(strict=True),
        "evaluator_contract": evaluator.resolve(strict=True),
    }
    counts = {
        role: sum(path == expected_path for path in opened)
        for role, expected_path in expected.items()
    }
    missing = sorted(role for role, count in counts.items() if count == 0)
    raw_reads = sorted(
        {
            path.relative_to(paths.raw_root).as_posix()
            for path in opened
            if is_within(path, paths.raw_root) and path != expected["evaluation_only_trace"]
        }
    )
    runtime_reads = sorted(
        {
            path.relative_to(paths.runtime_root).as_posix()
            for path in opened
            if is_within(path, paths.runtime_root) and path != expected["current_solver_output"]
        }
    )
    provider_reads = sum(is_within(path, paths.provider_root) for path in opened)
    allowed_clean_files = {
        expected["current_solver_output"],
        expected["window_contract"],
        expected["evaluator_contract"],
    }
    unexpected_clean = sorted(
        {
            path.relative_to(paths.clean_root).as_posix()
            for path in opened
            if is_within(path, paths.clean_root)
            and path not in allowed_clean_files
            and not is_within(path, method_output)
        }
    )
    legacy_read_count = sum(legacy_reason(path) is not None for path in opened)
    report: dict[str, object] = {
        "schema_version": "paper-rebuild-evaluator-file-open-crosscheck-v1",
        "strace_available": True,
        "strace_sha256": sha256_file(strace_path),
        "expected_role_open_counts": counts,
        "missing_expected_roles": missing,
        "unexpected_raw_root_relative_paths": raw_reads,
        "unexpected_runtime_root_relative_paths": runtime_reads,
        "provider_root_read_count": provider_reads,
        "unexpected_clean_root_relative_paths": unexpected_clean,
        "legacy_path_read_count": legacy_read_count,
        "opened_path_count": len(opened),
        "passed": not missing and not raw_reads and not runtime_reads and provider_reads == 0 and not unexpected_clean and legacy_read_count == 0,
    }
    write_json_atomic(destination, report)
    if report["passed"] is not True:
        raise RuntimeError("FAIL_CLEAN1_EVIDENCE_CONTAMINATION")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    paths = load_clean_paths(args.config)
    assert_clean1_path_contract(paths, REPO_ROOT)
    stage = paths.clean_root / "06_CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION"
    evaluator_path = stage / "02_PROTOCOL_FREEZE/EVALUATOR_CONTRACT.yaml"
    window_path = stage / "02_PROTOCOL_FREEZE/WINDOW_CONTRACT.yaml"
    catalog = load_method_catalog(REPO_ROOT / "configs/paper_rebuild/methods.yaml")
    expected_window_hash = sha256_file(window_path)
    expected_evaluator_hash = sha256_file(evaluator_path)
    manifests: dict[str, dict[str, object]] = {}
    frozen_outputs: list[dict[str, object]] = []
    common_commits: set[str] = set()
    for method_id, directory in zip(FORMAL_METHOD_ORDER, RUN_DIRECTORY_NAMES):
        run = paths.runtime_root / directory
        formal_manifest = run / "FORMAL_RUN_MANIFEST.json"
        eval_nav = run / "EVAL_NAV.csv"
        if not formal_manifest.is_file() or not eval_nav.is_file():
            raise RuntimeError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
        manifest = json.loads(formal_manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise RuntimeError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
        assert_formal_run_manifest(manifest, catalog, require_pass=True)
        if manifest.get("algorithm_id") != method_id or manifest.get("run_id") != directory:
            raise RuntimeError("FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH")
        if manifest.get("window_contract_hash") != expected_window_hash or manifest.get("evaluator_contract_hash") != expected_evaluator_hash:
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
        expected_hash = str((manifest.get("output_hashes") or {}).get("eval_nav") or "")
        actual_hash = sha256_file(eval_nav)
        if expected_hash != actual_hash:
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
        common_commits.add(str(manifest.get("code_commit") or ""))
        manifests[method_id] = manifest
        frozen_outputs.append(
            {
                "method_order": FORMAL_METHOD_ORDER.index(method_id) + 1,
                "algorithm_id": method_id,
                "path_alias": f"<RUNTIME_ROOT>/{directory}",
                "relative_path": "EVAL_NAV.csv",
                "sha256": actual_hash,
                "frozen_before_any_evaluation": True,
            }
        )
    if len(manifests) != 4 or len(common_commits) != 1 or "" in common_commits:
        raise RuntimeError("BLOCKED_CLEAN1_FOUR_METHOD_SET_INCOMPLETE")
    evaluation_root = stage / "07_EVALUATION"
    complete_root = evaluation_root / "FORMAL_EVALUATION"
    if complete_root.exists():
        raise RuntimeError("Fresh CLEAN1 formal evaluation already exists")
    attempt_root = evaluation_root / f".attempt-{uuid.uuid4().hex}"
    attempt_root.mkdir(parents=False, exist_ok=False)
    with (attempt_root / "FOUR_METHOD_OUTPUT_HASHES.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frozen_outputs[0]))
        writer.writeheader()
        writer.writerows(frozen_outputs)
    rows = []
    payload: dict[str, object] = {
        "schema_version": "paper-rebuild-clean1-four-method-metrics-v1",
        "title": "BY2 clean normal relative-to-evaluation-reference descriptive results",
        "reference_wording": "aligned evaluation-only reference",
        "reference_independence_established": False,
        "claim_boundary": (
            "在冻结的单一 BY2 clean normal 序列、统一窗口、统一初始化和冻结 evaluator 下，"
            "相对于 evaluation-only reference 的描述性结果。"
        ),
        "methods": {},
        "paper_performance_claim": False,
    }
    for method_id, directory in zip(FORMAL_METHOD_ORDER, RUN_DIRECTORY_NAMES):
        run = paths.runtime_root / directory
        eval_nav = run / "EVAL_NAV.csv"
        manifest = manifests[method_id]
        manifest_output_hashes = manifest.get("output_hashes")
        if not isinstance(manifest_output_hashes, dict):
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
        expected_output_hash = str(manifest_output_hashes.get("eval_nav") or "")
        method_output = attempt_root / directory
        strace_path = attempt_root / f".{directory}.EVALUATOR_FILE_OPEN_TRACE.raw"
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts/paper_rebuild/evaluate_clean1_by2_method.py"),
            "--config",
            str(paths.config_path),
            "--solver-output",
            str(eval_nav),
            "--window",
            str(window_path),
            "--evaluator",
            str(evaluator_path),
            "--output-dir",
            str(method_output),
            "--expected-output-sha256",
            expected_output_hash,
        ]
        strace = shutil.which("strace")
        executed = (
            [strace, "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(strace_path), *command]
            if strace
            else command
        )
        completed = run_process_group(
            executed,
            cwd=REPO_ROOT,
            timeout_seconds=900,
            timeout_message="formal evaluator timeout; entire process group terminated",
            launch_failure_message="formal evaluator launch failure",
        )
        (attempt_root / f"{directory}.stdout.txt").write_text(
            completed.stdout, encoding="utf-8"
        )
        (attempt_root / f"{directory}.stderr.txt").write_text(
            completed.stderr, encoding="utf-8"
        )
        write_json_atomic(
            attempt_root / f"{directory}.PROCESS_STATUS.json",
            {
                "algorithm_id": method_id,
                "returncode": completed.returncode,
                "failure_class": {
                    0: "",
                    124: "timeout",
                    127: "launch_failure",
                }.get(completed.returncode, "evaluator_nonzero_returncode"),
                "process_group_isolated": True,
                "terminal_success": completed.returncode == 0,
            },
        )
        if completed.returncode != 0 or not method_output.is_dir():
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
        if strace:
            _evaluator_file_open_crosscheck(
                strace_path,
                method_output / "EVALUATOR_FILE_OPEN_CROSSCHECK.json",
                paths=paths,
                solver_output=eval_nav,
                reference=paths.raw_root / BY2_TRACE_RELATIVE_PATH,
                window=window_path,
                evaluator=evaluator_path,
                method_output=method_output,
            )
            strace_path.rename(method_output / "EVALUATOR_FILE_OPEN_TRACE.raw")
        else:
            write_json_atomic(
                method_output / "EVALUATOR_FILE_OPEN_CROSSCHECK.json",
                {
                    "schema_version": "paper-rebuild-evaluator-file-open-crosscheck-v1",
                    "strace_available": False,
                    "fallback": "explicit_input_registry_static_dependency_audit",
                    "passed": True,
                },
            )
        aggregate = json.loads(
            (method_output / "AGGREGATE_METRICS.json").read_text(encoding="utf-8")
        )
        payload["methods"][method_id] = {  # type: ignore[index]
            **aggregate,
            "runtime_seconds": manifest["runtime_seconds"],
            "module_update_counts": manifest["module_update_counts"],
        }
        flat = {
            "method_order": FORMAL_METHOD_ORDER.index(method_id) + 1,
            "algorithm_id": method_id,
            "output_epoch_count": aggregate["output_epoch_count"],
            "matched_epoch_count": aggregate["matched_epoch_count"],
            "coverage_ratio": aggregate["coverage_ratio"],
            "runtime_seconds": manifest["runtime_seconds"],
            "module_update_counts_json": json.dumps(manifest["module_update_counts"], sort_keys=True),
        }
        for metric, statistics in aggregate["metrics"].items():
            for name, value in statistics.items():
                flat[f"{metric}_{name}"] = value
        rows.append(flat)
    for frozen in frozen_outputs:
        directory = RUN_DIRECTORY_NAMES[int(frozen["method_order"]) - 1]
        if sha256_file(paths.runtime_root / directory / "EVAL_NAV.csv") != frozen["sha256"]:
            raise RuntimeError("FAIL_CLEAN1_FINAL_OUTPUT_OR_METRIC_CROSSCHECK")
    write_json_atomic(attempt_root / "FOUR_METHOD_METRICS.json", payload)
    with (attempt_root / "FOUR_METHOD_METRICS.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    attempt_root.rename(complete_root)
    print(json.dumps({"formal_metric_rows": len(rows), "paper_performance_claim": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
