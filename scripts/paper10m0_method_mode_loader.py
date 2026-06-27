#!/usr/bin/env python3
"""Load and validate PAPER10M0 method-mode freeze inputs.

中文说明：本模块只读取 PAPER10L 冻结配置并形成 M0 runner 映射所需的
静态视图；不运行 solver，不读取 trace，不写 runtime 输出。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


METHOD_MODE_IDS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]

FORBIDDEN_FEATURE_FLAGS = [
    "enable_benchmark_methods",
    "enable_qa_fallback",
    "enable_trace_online",
    "enable_final_v23_output_input",
    "enable_legsa_output_input",
    "enable_per_case_tuning",
    "enable_output_only_correction",
]

CONTRACT_IDS = [
    "solver_input_contract",
    "runner_contract",
    "evaluator_contract",
    "output_contract",
    "path_guard_contract",
    "benchmark_isolation_contract",
    "claim_boundary_contract",
]


@dataclass(frozen=True)
class FrozenConfig:
    path: Path
    data: dict[str, Any]
    sha256: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def paper10_config_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "configs" / "paper10"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"PAPER10 config is expected to be JSON-compatible YAML: {path}") from exc


def load_frozen_config(path: str | Path) -> FrozenConfig:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    return FrozenConfig(path=source, data=_load_json_yaml(source), sha256=_sha256(source))


def load_method_modes(root: Path | None = None) -> dict[str, FrozenConfig]:
    cfg_root = paper10_config_root(root) / "method_modes"
    modes = {
        mode_id: load_frozen_config(cfg_root / f"{mode_id}.yaml")
        for mode_id in METHOD_MODE_IDS
    }
    for mode_id, frozen in modes.items():
        actual = frozen.data.get("method_mode_id")
        if actual != mode_id:
            raise ValueError(f"method_mode_id mismatch for {frozen.path}: {actual!r}")
    return modes


def load_feature_flags(root: Path | None = None) -> FrozenConfig:
    return load_frozen_config(paper10_config_root(root) / "feature_flags" / "final_candidate_feature_flags.yaml")


def load_contracts(root: Path | None = None) -> dict[str, FrozenConfig]:
    cfg_root = paper10_config_root(root) / "contracts"
    return {
        contract_id: load_frozen_config(cfg_root / f"{contract_id}.yaml")
        for contract_id in CONTRACT_IDS
    }


def combined_config_sha256(configs: list[FrozenConfig]) -> str:
    digest = hashlib.sha256()
    for frozen in sorted(configs, key=lambda item: str(item.path)):
        digest.update(str(frozen.path.relative_to(repo_root())).encode("utf-8", errors="ignore"))
        digest.update(b"\0")
        digest.update(frozen.sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def provider_default_status() -> dict[str, bool]:
    return {
        "raw_doppler": False,
        "go2_roll_pitch": False,
        "go2_horizontal_velocity": False,
        "go2_joint_factor": False,
        "go2_readiness_motion_metadata": False,
        "multi_state_qm": True,
    }


def resolve_effective_feature_flags(mode: dict[str, Any], provider_status: dict[str, bool] | None = None) -> dict[str, bool]:
    providers = {**provider_default_status(), **(provider_status or {})}
    requested = mode.get("feature_flags", {})
    effective: dict[str, bool] = {}
    for flag, value in requested.items():
        if isinstance(value, bool):
            effective[flag] = value
        elif value == "true_when_provider_valid":
            effective[flag] = bool(providers["raw_doppler"])
        elif value == "true_optional":
            if flag == "enable_go2_roll_pitch_prior":
                effective[flag] = bool(providers["go2_roll_pitch"])
            elif flag == "enable_go2_horizontal_velocity_prior":
                effective[flag] = bool(providers["go2_horizontal_velocity"])
            elif flag == "enable_go2_readiness_motion_metadata":
                effective[flag] = bool(providers["go2_readiness_motion_metadata"])
            else:
                effective[flag] = False
        elif value == "optional_supporting_or_appendix":
            effective[flag] = bool(providers["go2_joint_factor"])
        elif value == "optional_for_full_candidate":
            effective[flag] = bool(providers["multi_state_qm"])
        elif value in {"false_or_diagnostic", "false_or_secondary_appendix"}:
            effective[flag] = False
        else:
            effective[flag] = False
    return effective


def validate_mode_safety(mode: dict[str, Any], effective_flags: dict[str, bool]) -> list[str]:
    issues: list[str] = []
    for key in FORBIDDEN_FEATURE_FLAGS:
        if effective_flags.get(key) is not False:
            issues.append(f"{mode.get('method_mode_id')}: forbidden flag enabled: {key}")
    if mode.get("trace_online_allowed") is not False:
        issues.append(f"{mode.get('method_mode_id')}: trace_online_allowed must be false")
    if mode.get("final_v23_output_solver_input_allowed") is not False:
        issues.append(f"{mode.get('method_mode_id')}: final_v23 output input must be false")
    if mode.get("legsa_output_solver_input_allowed") is not False:
        issues.append(f"{mode.get('method_mode_id')}: LegSA output input must be false")
    if mode.get("per_case_tuning_allowed") is not False:
        issues.append(f"{mode.get('method_mode_id')}: per-case tuning must be false")
    if mode.get("output_only_correction_allowed") is not False:
        issues.append(f"{mode.get('method_mode_id')}: output-only correction must be false")
    if mode.get("benchmark_code_allowed_in_solver") is not False:
        issues.append(f"{mode.get('method_mode_id')}: benchmark solver mixing must be false")
    return issues


def load_all(root: Path | None = None) -> dict[str, Any]:
    modes = load_method_modes(root)
    flags = load_feature_flags(root)
    contracts = load_contracts(root)
    config_hash = combined_config_sha256([*modes.values(), flags, *contracts.values()])
    return {
        "method_modes": modes,
        "feature_flags": flags,
        "contracts": contracts,
        "config_sha256": config_hash,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else repo_root()
    loaded = load_all(root)
    rows = []
    issues: list[str] = []
    for mode_id, frozen in loaded["method_modes"].items():
        effective = resolve_effective_feature_flags(frozen.data)
        issues.extend(validate_mode_safety(frozen.data, effective))
        rows.append(
            {
                "method_mode_id": mode_id,
                "sha256": frozen.sha256,
                "effective_flags": effective,
                "claim_level": frozen.data.get("claim_level", ""),
            }
        )
    print(json.dumps({"status": "pass" if not issues else "fail", "issues": issues, "rows": rows}, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
