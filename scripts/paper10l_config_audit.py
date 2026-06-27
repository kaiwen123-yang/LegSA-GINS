#!/usr/bin/env python3
"""PAPER10L config-freeze audit helpers.

The PAPER10L checks are intentionally static. They validate method-mode,
feature-flag, and contract files without running solvers, evaluators, or any
experiment matrix.

中文说明：本脚本只做 PAPER10L 配置静态审计，不运行求解器、评估器或大矩阵。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAPER10 = ROOT / "configs" / "paper10"
METHOD_MODE_DIR = PAPER10 / "method_modes"
FEATURE_FLAG_FILE = PAPER10 / "feature_flags" / "final_candidate_feature_flags.yaml"
CONTRACT_DIR = PAPER10 / "contracts"

METHOD_MODES = {
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
}

FEATURE_FLAGS = {
    "enable_raw_doppler",
    "enable_source_aware",
    "enable_go2_roll_pitch_prior",
    "enable_go2_horizontal_velocity_prior",
    "enable_go2_joint_factor",
    "enable_go2_readiness_motion_metadata",
    "enable_multi_state_qm",
    "enable_fgo_no_feedback",
    "enable_fgo_feedback",
    "enable_benchmark_methods",
    "enable_qa_fallback",
    "enable_trace_online",
    "enable_final_v23_output_input",
    "enable_legsa_output_input",
    "enable_per_case_tuning",
    "enable_output_only_correction",
}

FORBIDDEN_ENABLE_FLAGS = {
    "enable_benchmark_methods",
    "enable_qa_fallback",
    "enable_trace_online",
    "enable_final_v23_output_input",
    "enable_legsa_output_input",
    "enable_per_case_tuning",
    "enable_output_only_correction",
}

GUARD_FIELDS = {
    "trace_online_allowed",
    "final_v23_output_solver_input_allowed",
    "legsa_output_solver_input_allowed",
    "per_case_tuning_allowed",
    "output_only_correction_allowed",
    "benchmark_code_allowed_in_solver",
}

REQUIRED_MODE_FIELDS = {
    "method_mode_id",
    "description",
    "allowed_dataset_roles",
    "solver_core",
    "feature_flags",
    "required_inputs",
    "forbidden_inputs",
    "output_contract",
    "claim_level",
    "paper10m_allowed_after_human_approval",
    "paper10h_allowed_after_human_approval",
    "run_allowed_now",
    *GUARD_FIELDS,
}

FORBIDDEN_INPUT_TOKENS = {
    "trace",
    "final_v23",
    "legsa_output",
    "benchmark",
    "per_case",
    "output_only",
}

LOCAL_PATH_PATTERNS = [
    re.compile("C:" + r"\\Users\\", re.IGNORECASE),
    re.compile("/" + "mnt" + "/" + "c" + "/" + "Users" + "/", re.IGNORECASE),
    re.compile("/" + "home" + "/" + "kaiwen" + "/"),
    re.compile("/" + "media" + "/" + "kaiwen" + "/"),
]


def load_json_yaml(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_method_modes() -> dict[str, dict[str, Any]]:
    modes = {}
    for path in sorted(METHOD_MODE_DIR.glob("*.yaml")):
        data = load_json_yaml(path)
        modes[data["method_mode_id"]] = data
    return modes


def load_feature_flags() -> dict[str, Any]:
    return load_json_yaml(FEATURE_FLAG_FILE)


def load_contract(name: str) -> dict[str, Any]:
    return load_json_yaml(CONTRACT_DIR / f"{name}.yaml")


def assert_false(value: Any, label: str) -> None:
    if value is not False:
        raise AssertionError(f"{label} must be false, got {value!r}")


def audit_method_modes() -> list[str]:
    modes = load_method_modes()
    if set(modes) != METHOD_MODES:
        raise AssertionError(f"method modes mismatch: {sorted(modes)}")
    messages = []
    for mode_id, mode in sorted(modes.items()):
        missing = REQUIRED_MODE_FIELDS - set(mode)
        if missing:
            raise AssertionError(f"{mode_id} missing fields: {sorted(missing)}")
        if mode["method_mode_id"] != mode_id:
            raise AssertionError(f"{mode_id} has mismatched method_mode_id")
        assert_false(mode["run_allowed_now"], f"{mode_id}.run_allowed_now")
        for field in GUARD_FIELDS:
            assert_false(mode[field], f"{mode_id}.{field}")
        flags = mode["feature_flags"]
        if set(flags) != FEATURE_FLAGS:
            raise AssertionError(f"{mode_id} feature flags mismatch")
        for flag in FORBIDDEN_ENABLE_FLAGS:
            assert_false(flags[flag], f"{mode_id}.{flag}")
        forbidden_inputs = " ".join(mode["forbidden_inputs"]).lower()
        for token in FORBIDDEN_INPUT_TOKENS:
            if token not in forbidden_inputs:
                raise AssertionError(f"{mode_id} does not forbid {token}")
        if mode_id == "basic_dual_baseline":
            for flag, value in flags.items():
                assert_false(value, f"basic_dual_baseline.{flag}")
        if mode_id == "strong_dual_yaw_baseline":
            for flag, value in flags.items():
                assert_false(value, f"strong_dual_yaw_baseline.{flag}")
        if mode_id == "legsa_without_qm":
            assert_false(flags["enable_multi_state_qm"], "legsa_without_qm.enable_multi_state_qm")
        messages.append(f"{mode_id}: passed")
    return messages


def audit_feature_flags() -> list[str]:
    config = load_feature_flags()
    assert_false(config["paper10m_ready"], "paper10m_ready")
    assert_false(config["paper10h_ready"], "paper10h_ready")
    assert_false(config["run_allowed_now"], "run_allowed_now")
    flags = config["flags"]
    if set(flags) != FEATURE_FLAGS:
        raise AssertionError(f"feature flag mismatch: {sorted(flags)}")
    messages = []
    for flag, record in sorted(flags.items()):
        required = {
            "default_value",
            "default_runtime_enabled",
            "allowed_modes",
            "forbidden_modes",
            "status",
            "claim_level",
            "requires_provider",
            "requires_human_approval",
            "paper10l_test_required",
            "paper10m_run_required",
            "notes",
        }
        missing = required - set(record)
        if missing:
            raise AssertionError(f"{flag} missing fields: {sorted(missing)}")
        assert_false(record["default_runtime_enabled"], f"{flag}.default_runtime_enabled")
        if flag in FORBIDDEN_ENABLE_FLAGS:
            assert_false(record["default_value"], f"{flag}.default_value")
            if record["allowed_modes"]:
                raise AssertionError(f"{flag} must not have allowed modes")
        if not record["requires_human_approval"]:
            raise AssertionError(f"{flag} must require human approval")
        messages.append(f"{flag}: passed")
    return messages


def audit_path_config_guards() -> list[str]:
    contract = load_contract("path_guard_contract")
    assert_false(contract["local_absolute_paths_allowed_in_tracked_docs_configs_scripts"], "local path guard")
    assert_false(contract["raw_data_copy_allowed"], "raw data copy")
    assert_false(contract["runtime_output_commit_allowed"], "runtime output commit")
    scan_roots = [
        PAPER10,
        ROOT / "scripts" / "paper10l_config_audit.py",
        *ROOT.glob("scripts/audit_paper10l_*.py"),
        *ROOT.glob("tests/audit/test_paper10l_*.py"),
    ]
    leaks = []
    for scan_root in scan_roots:
        paths = [scan_root] if scan_root.is_file() else list(scan_root.rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in LOCAL_PATH_PATTERNS:
                if pattern.search(text):
                    leaks.append(str(path.relative_to(ROOT)))
    if leaks:
        raise AssertionError(f"local path leaks: {leaks}")
    return ["path/config guard: passed"]


def audit_benchmark_isolation() -> list[str]:
    flags = load_feature_flags()["flags"]
    benchmark = load_contract("benchmark_isolation_contract")
    assert_false(flags["enable_benchmark_methods"]["default_value"], "enable_benchmark_methods.default_value")
    assert_false(benchmark["benchmark_code_allowed_in_solver"], "benchmark code in solver")
    assert_false(benchmark["benchmark_output_solver_input_allowed"], "benchmark output solver input")
    assert_false(benchmark["enable_benchmark_methods_default"], "benchmark default")
    assert_false(benchmark["lse_absolute_yaw_method_claim_allowed"], "LSE absolute yaw claim")
    return ["benchmark isolation: passed"]


def audit_claim_boundary() -> list[str]:
    contract = load_contract("claim_boundary_contract")
    forbidden = set(contract["forbidden_claims"])
    required = {
        "comprehensive_final_v23_superiority",
        "universal_superiority",
        "BY3_yaw_generalization",
        "XB_PG_high_precision_severe_GNSS_proof",
        "Go2_position_truth",
        "Go2_yaw_truth",
        "Go2_velocity_truth",
        "trace_online",
        "final_v23_output_as_solver_input",
        "LegSA_output_as_solver_input",
        "QA_fallback_as_final_method",
        "LSE_as_absolute_yaw_method",
        "complete_nine_factor_FGO_as_fully_paper_validated",
        "exact_external_reproduction_unless_proven",
        "per_case_tuning",
        "output_only_correction",
        "deleting_bad_epochs",
        "benchmark_method_mixed_into_solver",
        "FGO_output_substitution",
    }
    missing = required - forbidden
    if missing:
        raise AssertionError(f"forbidden claim list missing: {sorted(missing)}")
    return ["claim boundary: passed"]


def audit_no_large_run() -> list[str]:
    runner = load_contract("runner_contract")
    assert_false(runner["large_run_allowed_now"], "large_run_allowed_now")
    assert_false(runner["degradation_matrix_allowed_now"], "degradation_matrix_allowed_now")
    assert_false(runner["literature_benchmark_full_matrix_allowed_now"], "benchmark full matrix")
    assert_false(runner["run_allowed_now"], "runner.run_allowed_now")
    if not runner["paper10m_queue_locked_by_default"]:
        raise AssertionError("PAPER10M queue must be locked")
    if not runner["paper10h_queue_locked_by_default"]:
        raise AssertionError("PAPER10H queue must be locked")
    for mode_id, mode in load_method_modes().items():
        assert_false(mode["run_allowed_now"], f"{mode_id}.run_allowed_now")
    return ["no large-run guard: passed"]


def audit_output_contract() -> list[str]:
    contract = load_contract("output_contract")
    required = {
        "NAV",
        "STD",
        "EVAL_NAV_or_metric_csv_json",
        "RUN_MANIFEST",
        "SOURCE_TRACE_if_enabled",
        "QM_TRACE_if_enabled",
        "FEATURE_FLAG_DUMP",
        "DATASET_ROLE_DUMP",
        "NO_HIDDEN_CONFIG",
    }
    outputs = set(contract["required_outputs"])
    missing = required - outputs
    if missing:
        raise AssertionError(f"output contract missing: {sorted(missing)}")
    assert_false(contract["hidden_config_allowed"], "hidden config")
    assert_false(contract["hand_edited_nav_std_allowed"], "hand-edited NAV/STD")
    return ["output contract: passed"]


def audit_solver_contract() -> list[str]:
    solver = load_contract("solver_input_contract")
    for field in [
        "trace_online_allowed",
        "final_v23_output_solver_input_allowed",
        "legsa_output_solver_input_allowed",
        "benchmark_output_solver_input_allowed",
        "per_case_tuning_allowed",
        "output_only_correction_allowed",
    ]:
        assert_false(solver[field], field)
    forbidden = " ".join(solver["solver_input_forbidden"]).lower()
    for token in FORBIDDEN_INPUT_TOKENS:
        if token not in forbidden:
            raise AssertionError(f"solver input contract does not forbid {token}")
    return ["solver input contract: passed"]


AUDITS = {
    "method_modes": audit_method_modes,
    "feature_flags": audit_feature_flags,
    "path_config_guards": audit_path_config_guards,
    "benchmark_isolation": audit_benchmark_isolation,
    "claim_boundary": audit_claim_boundary,
    "no_large_run": audit_no_large_run,
    "output_contract": audit_output_contract,
    "solver_contract": audit_solver_contract,
}


def run_audit(name: str) -> list[str]:
    if name not in AUDITS:
        raise KeyError(f"unknown PAPER10L audit: {name}")
    return AUDITS[name]()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = sorted(AUDITS)
    for name in args:
        messages = run_audit(name)
        for message in messages:
            print(message)
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
