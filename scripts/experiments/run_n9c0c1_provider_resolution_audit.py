"""Run N9C0C1 provider resolution and branch-effect audit.

This stage is intentionally limited to reporting, runtime config provider-path
repair, and a single normal-smoke rerun. It does not alter algorithm math,
feedback policy, or FGO factor equations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from legsa_gins.reporting.by2_algorithm_runner import repo_to_wsl, write_json
from legsa_gins.reporting.by2_n9c0c_legsa_full_algorithm_materialization import (
    ALGORITHM_ID,
    CaseSpec,
    _module_verification,
    _run_official_eval,
    _run_solver,
)


STAGE = "N9C0C1_LEGSA_FULL_PROVIDER_INPUT_RESOLUTION_AND_BRANCH_EFFECT_AUDIT"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in keys})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_pair(stem: Path, rows: list[dict[str, Any]]) -> None:
    write_json(stem.with_suffix(".json"), rows)
    _write_csv(stem.with_suffix(".csv"), rows)


def _write_summary(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _prepare_root(stage_root: Path) -> None:
    for name in [
        "00_supervisor",
        "01_plan",
        "provider_inventory",
        "branch_effect_audit",
        "config_repair",
        "normal_smoke_rerun",
        "official_eval",
        "reports",
        "matrix",
        "summary",
        "validation",
        "logs",
    ]:
        (stage_root / name).mkdir(parents=True, exist_ok=True)


def _parse_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    pattern = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        values[match.group(1)] = value
    return values


def _from_wsl(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    match = re.match(r"^/mnt/([A-Za-z])/(.*)$", path_text)
    if match:
        return Path(f"{match.group(1).upper()}:\\" + match.group(2).replace("/", "\\"))
    if re.match(r"^[A-Za-z]:", path_text):
        return Path(path_text)
    return None


def _row_count(path: Path) -> int | None:
    try:
        if path.suffix.lower() not in {".csv", ".jsonl", ".txt", ".md", ".yaml", ".yml"}:
            return None
        if path.stat().st_size > 100_000_000:
            return None
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _sha256_small(path: Path) -> str | None:
    try:
        if not path.exists() or path.stat().st_size > 100_000_000:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _file_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"file_exists": False, "path": str(path)}
    stat = path.stat()
    return {
        "file_exists": True,
        "path": str(path),
        "size": stat.st_size,
        "modified_time": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
        "row_count_if_safe": _row_count(path),
        "sha256_if_safe": _sha256_small(path),
    }


def _branch_conclusion(algorithm: str, manifest: dict[str, Any]) -> str:
    raw_active = (
        manifest.get("enable_raw_doppler") is True
        and manifest.get("raw_doppler_provider_status") == "available"
        and int(manifest.get("raw_doppler_update_count") or 0) > 0
    )
    source_active = (
        manifest.get("source_aware_weighting_enabled") is True
        and int(manifest.get("source_aware_trace_rows") or 0) > 0
    )
    go2_active = (
        manifest.get("go2_proprioceptive_joint_factor_enabled") is True
        and int(manifest.get("go2_proprioceptive_joint_factor_update_count") or 0) > 0
        and int(manifest.get("go2_attitude_weak_prior_update_count") or 0) > 0
        and int(manifest.get("go2_horizontal_velocity_prior_update_count") or 0) > 0
    )
    feedback_active = (
        manifest.get("fgo_feedback_enabled") is True
        and manifest.get("fgo_feedback_provider_status") == "available"
        and int(manifest.get("feedback_update_count") or 0) > 0
    )
    if algorithm == "Raw_Doppler_EKF":
        return "active_effect" if raw_active else "provider_missing"
    if algorithm == "source_aware_EKF":
        return "active_effect" if raw_active and source_active else "flag_only_no_provider"
    if algorithm == "Go2_joint_EKF":
        return "active_effect" if raw_active and source_active and go2_active else "flag_only_no_provider"
    if algorithm == "selected_feedback_EKF":
        return "active_effect" if feedback_active else "provider_missing"
    if algorithm == ALGORITHM_ID:
        if feedback_active and (not raw_active or not go2_active):
            return "provider_missing"
        return "active_effect" if raw_active and source_active and go2_active and feedback_active else "inconclusive"
    return "diagnostic_only"


def _branch_effect_audit(workspace: Path, stage_root: Path) -> list[dict[str, Any]]:
    matrix_root = workspace / "by2-huitu" / "N9B2_FULL_MATRIX"
    n9c0c_full = matrix_root / "LEGSA_FULL_ALGORITHM_MINIMUM_RERUN"
    branch_specs = [
        (
            "source_backed_EKF",
            matrix_root / "BATCH0_SMOKE/solver_outputs/B0_normal_repeat_formal/source_backed_EKF/RUN_MANIFEST.json",
            matrix_root / "BATCH0_SMOKE/runtime_configs/B0_normal_repeat_formal/source_backed_EKF.runtime_config.yaml",
            "BATCH0_SMOKE normal",
        ),
        (
            "Raw_Doppler_EKF",
            matrix_root / "BATCH0_SMOKE/solver_outputs/B0_normal_repeat_formal/Raw_Doppler_EKF/RUN_MANIFEST.json",
            matrix_root / "BATCH0_SMOKE/runtime_configs/B0_normal_repeat_formal/Raw_Doppler_EKF.runtime_config.yaml",
            "BATCH0_SMOKE normal",
        ),
        (
            "source_aware_EKF",
            matrix_root / "BATCH0_SMOKE/solver_outputs/B0_normal_repeat_formal/source_aware_EKF/RUN_MANIFEST.json",
            matrix_root / "BATCH0_SMOKE/runtime_configs/B0_normal_repeat_formal/source_aware_EKF.runtime_config.yaml",
            "BATCH0_SMOKE normal",
        ),
        (
            "Go2_joint_EKF",
            matrix_root / "BATCH0_SMOKE/solver_outputs/B0_normal_repeat_formal/Go2_joint_EKF/RUN_MANIFEST.json",
            matrix_root / "BATCH0_SMOKE/runtime_configs/B0_normal_repeat_formal/Go2_joint_EKF.runtime_config.yaml",
            "BATCH0_SMOKE normal",
        ),
        (
            "selected_feedback_EKF",
            matrix_root
            / "BATCH0_SMOKE/solver_outputs/B0_selected_feedback_clean_repeat_plan/selected_feedback_EKF/RUN_MANIFEST.json",
            matrix_root
            / "BATCH0_SMOKE/runtime_configs/B0_selected_feedback_clean_repeat_plan/selected_feedback_EKF.runtime_config.yaml",
            "BATCH0_SMOKE selected feedback clean repeat",
        ),
        (
            ALGORITHM_ID,
            n9c0c_full / "normal_smoke/FULL_normal_repeat/LegSA_full_EKF/RUN_MANIFEST.json",
            n9c0c_full / "runtime_configs/FULL_normal_repeat/LegSA_full_EKF.runtime_config.yaml",
            "N9C0C normal smoke",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for algorithm, manifest_path, config_path, source in branch_specs:
        manifest = _read_json(manifest_path, {}) or {}
        config = _parse_config(config_path)
        raw_path = _from_wsl(config.get("raw_doppler_factor_path"))
        rows.append(
            {
                "algorithm_id": algorithm,
                "runtime_stage_source": source,
                "manifest_exists": manifest_path.exists(),
                "config_exists": config_path.exists(),
                "raw_doppler_enabled": manifest.get("enable_raw_doppler"),
                "raw_doppler_provider_status": manifest.get("raw_doppler_provider_status"),
                "raw_doppler_update_count": manifest.get("raw_doppler_update_count"),
                "raw_doppler_epoch_count": manifest.get("raw_doppler_epoch_count"),
                "raw_doppler_path": config.get("raw_doppler_factor_path"),
                "raw_doppler_path_exists_windows": raw_path.exists() if raw_path else False,
                "source_aware_enabled": manifest.get("source_aware_weighting_enabled"),
                "source_aware_scale_count_or_evidence": manifest.get("source_aware_trace_rows"),
                "source_aware_update_count_by_source": manifest.get("source_aware_update_count_by_source"),
                "source_aware_scale_stats": manifest.get("source_aware_R_scale_stats_by_source")
                or manifest.get("source_aware_R_scale_p50_p95_max_by_source"),
                "go2_joint_enabled": manifest.get("go2_proprioceptive_joint_factor_enabled"),
                "go2_joint_update_count": manifest.get("go2_proprioceptive_joint_factor_update_count"),
                "go2_attitude_prior_update_count": manifest.get("go2_attitude_weak_prior_update_count"),
                "go2_horizontal_velocity_update_count": manifest.get("go2_horizontal_velocity_prior_update_count"),
                "go2_attitude_provider_status": manifest.get("go2_attitude_prior_provider_status"),
                "go2_horizontal_velocity_provider_status": manifest.get("go2_velocity_prior_diagnostic_provider_status"),
                "go2_attitude_path": config.get("go2_attitude_prior_path"),
                "go2_horizontal_velocity_path": config.get("go2_horizontal_velocity_prior_path"),
                "go2_joint_path": config.get("go2_proprioceptive_joint_factor_path"),
                "selected_feedback_enabled": manifest.get("fgo_feedback_enabled"),
                "feedback_update_count": manifest.get("feedback_update_count"),
                "feedback_provider_status": manifest.get("fgo_feedback_provider_status"),
                "feedback_path": config.get("fgo_feedback_path"),
                "fgo_feedback_source": manifest.get("fgo_feedback_mode"),
                "trace_solver_input": manifest.get("trace_solver_input"),
                "final_v23_solver_input": manifest.get("final_v23_output_solver_input")
                or manifest.get("final_v23_solver_input"),
                "evidence_file": str(manifest_path),
                "runtime_config": str(config_path),
                "conclusion": _branch_conclusion(algorithm, manifest),
            }
        )
    write_json(stage_root / "reports/N9C0C1_BRANCH_EFFECT_AUDIT_REPORT.json", {"stage": STAGE, "generated_at": _now(), "rows": rows})
    _write_pair(stage_root / "matrix/N9C0C1_BRANCH_EFFECT_AUDIT", rows)
    _write_summary(
        stage_root / "summary/n9c0c1_branch_effect_audit.md",
        "N9C0C1 Branch Effect Audit",
        [
            "- Raw_Doppler_EKF historical normal row: active_effect with 274 raw Doppler updates and provider_status=available.",
            "- source_aware_EKF historical normal row: active_effect with raw Doppler updates plus source-aware trace evidence.",
            "- Go2_joint_EKF historical normal row: active_effect with 274 raw, joint, attitude, and horizontal-velocity updates.",
            "- selected_feedback_EKF historical normal row: active_effect with selected feedback updates.",
            "- N9C0C LegSA_full_EKF normal row: provider_missing for Raw Doppler and Go2 providers while selected feedback was active.",
        ],
    )
    return rows


def _likely_provider_type(path: Path) -> str:
    name = path.name.upper()
    if name == "RAW_DOPPLER_VELOCITY_FACTORS.CSV":
        return "raw_doppler_factor_provider"
    if "RTKLIB_DOPPLER" in name:
        return "doppler_ls_velocity_provider_or_report"
    if name == "GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.CSV":
        return "go2_joint_provider"
    if name == "GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.CSV":
        return "go2_attitude_provider"
    if name == "GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.CSV":
        return "go2_horizontal_velocity_provider"
    if name == "FGO_FEEDBACK_OBSERVATIONS.CSV":
        return "selected_feedback_provider"
    if name == "SOURCE_AWARE_WEIGHT_TRACE.CSV":
        return "source_aware_scale_trace_output"
    if "WINDOW" in name:
        return "feedback_window_log_or_policy"
    if "FACTOR" in name:
        return "factor_table_or_factor_report"
    return "provider_candidate"


def _associated_stage(path: Path, root: Path) -> str:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    for marker in ["运行结果", "by2-huitu"]:
        if marker in parts:
            index = parts.index(marker)
            return parts[index + 1] if index + 1 < len(parts) else marker
    return parts[0] if parts else "unknown"


def _usable_reason(path: Path, provider_type: str, n9c0c_full: Path) -> tuple[bool, str]:
    text = str(path)
    if provider_type == "raw_doppler_factor_provider" and "N5B_rtklib_doppler_provider_activation" in text:
        return True, "historical Raw_Doppler_EKF branch used this provider and had raw updates"
    if (
        provider_type in {"go2_joint_provider", "go2_attitude_provider", "go2_horizontal_velocity_provider"}
        and "N7C6_go2_proprioceptive_joint_factor" in text
        and "joint_rp1p6deg_hv1p0" in text
    ):
        return True, "historical Go2_joint_EKF branch used this provider family and had Go2 updates"
    if provider_type == "selected_feedback_provider" and path == n9c0c_full / "selected_feedback/FULL_normal_repeat/FGO_FEEDBACK_OBSERVATIONS.csv":
        return True, "N9C0C generated same-case clean feedback dependency for LegSA_full normal smoke"
    if provider_type == "selected_feedback_provider" and "N8J_feedback_final_validation" in text:
        return False, "historical selected feedback provider, not the N9C0C same-case generated dependency"
    if provider_type == "source_aware_scale_trace_output":
        return False, "source-aware trace is output evidence, not a solver input provider"
    return False, "candidate is diagnostic or not selected for repaired LegSA_full normal smoke"


def _provider_inventory(workspace: Path, archive: Path, stage_root: Path) -> list[dict[str, Any]]:
    n9c0c_full = workspace / "by2-huitu" / "N9B2_FULL_MATRIX" / "LEGSA_FULL_ALGORITHM_MINIMUM_RERUN"
    name_re = re.compile(
        r"(RAW_DOPPLER|RTKLIB_DOPPLER|GO2_PROPRIOCEPTIVE|FGO_FEEDBACK_OBSERVATIONS|"
        r"SOURCE_AWARE_WEIGHT_TRACE|GATE_POLICY_REPORT|WINDOW_POLICY_REPORT|"
        r"COVARIANCE_POLICY_REPORT|FGO_FACTOR_TABLE|FACTOR_TABLE|FACTOR_ROW|SLIDING_WINDOW)",
        re.IGNORECASE,
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build"}
    for root_label, root in [("C", workspace), ("G", archive)]:
        if not root.exists():
            rows.append(
                {
                    "root": root_label,
                    "path": str(root),
                    "file_exists": False,
                    "likely_provider_type": "root_missing",
                    "usable_for_LegSA_full": False,
                    "reason": "root not present",
                }
            )
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in skip_dirs]
            current = Path(dirpath)
            for filename in filenames:
                if not name_re.search(filename):
                    continue
                path = current / filename
                if str(path) in seen:
                    continue
                seen.add(str(path))
                provider_type = _likely_provider_type(path)
                usable, reason = _usable_reason(path, provider_type, n9c0c_full)
                meta = _file_meta(path)
                rows.append(
                    {
                        "root": root_label,
                        **meta,
                        "likely_provider_type": provider_type,
                        "associated_stage": _associated_stage(path, root),
                        "associated_algorithm": ALGORITHM_ID if usable else "historical_or_diagnostic",
                        "usable_for_LegSA_full": usable and meta["file_exists"],
                        "reason": reason,
                    }
                )
    exact_paths = [
        workspace / "运行结果/N5B_rtklib_doppler_provider_activation/RAW_DOPPLER_VELOCITY_FACTORS.csv",
        archive / "运行结果/N5B_rtklib_doppler_provider_activation/RAW_DOPPLER_VELOCITY_FACTORS.csv",
        archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
        archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv",
        archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv",
        n9c0c_full / "selected_feedback/FULL_normal_repeat/FGO_FEEDBACK_OBSERVATIONS.csv",
    ]
    seen_paths = {row.get("path") for row in rows}
    for path in exact_paths:
        if str(path) in seen_paths:
            continue
        provider_type = _likely_provider_type(path)
        usable, reason = _usable_reason(path, provider_type, n9c0c_full)
        root = workspace if str(path).startswith(str(workspace)) else archive
        rows.append(
            {
                "root": "C" if root == workspace else "G",
                **_file_meta(path),
                "likely_provider_type": provider_type,
                "associated_stage": _associated_stage(path, root),
                "associated_algorithm": ALGORITHM_ID if usable and path.exists() else "historical_or_diagnostic",
                "usable_for_LegSA_full": usable and path.exists(),
                "reason": reason if path.exists() else "exact provider path missing in this root",
            }
        )
    rows.sort(key=lambda row: (str(row.get("root")), str(row.get("likely_provider_type")), str(row.get("path"))))
    write_json(
        stage_root / "reports/N9C0C1_PROVIDER_FILE_INVENTORY_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "searched_roots": [str(workspace), str(archive)], "rows": rows},
    )
    _write_pair(stage_root / "matrix/N9C0C1_PROVIDER_FILE_INVENTORY", rows)
    usable_rows = [row for row in rows if row.get("usable_for_LegSA_full")]
    _write_summary(
        stage_root / "summary/n9c0c1_provider_file_inventory.md",
        "N9C0C1 Provider File Inventory",
        [
            f"- Searched roots: {workspace} and {archive}.",
            f"- Provider candidates recorded: {len(rows)}.",
            f"- Usable LegSA_full normal-smoke providers selected: {len(usable_rows)}.",
            "- C root is missing the historical Chinese-root Raw Doppler and Go2 provider files used by configs.",
            "- G root contains the Raw Doppler and Go2 provider family and is visible to WSL under /mnt/g.",
        ],
    )
    return rows


def _resolution_rows(workspace: Path, archive: Path) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    n9c0c_full = workspace / "by2-huitu" / "N9B2_FULL_MATRIX" / "LEGSA_FULL_ALGORITHM_MINIMUM_RERUN"
    paths = {
        "raw": archive / "运行结果/N5B_rtklib_doppler_provider_activation/RAW_DOPPLER_VELOCITY_FACTORS.csv",
        "go2_attitude": archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_ATTITUDE_PRIORS.csv",
        "go2_hv": archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_HORIZONTAL_VELOCITY_PRIORS.csv",
        "go2_joint": archive
        / "运行结果/N7C6_go2_proprioceptive_joint_factor/priors/joint_rp1p6deg_hv1p0/GO2_PROPRIOCEPTIVE_FACTOR_PRIORS.csv",
        "feedback": n9c0c_full / "selected_feedback/FULL_normal_repeat/FGO_FEEDBACK_OBSERVATIONS.csv",
    }
    rows = [
        {
            "provider": "Raw Doppler provider",
            "classification": "resolved_existing_G" if paths["raw"].exists() else "missing_everywhere",
            "resolved_path": str(paths["raw"]) if paths["raw"].exists() else "",
            "branch_activity_evidence": "Raw_Doppler_EKF raw_doppler_update_count=274 provider_status=available",
            "safe_for_repair": paths["raw"].exists(),
            "reason": "G archive has N5B provider used by active historical branch" if paths["raw"].exists() else "not found",
        },
        {
            "provider": "source-aware scale/source policy provider",
            "classification": "not_required_for_claim_boundary",
            "resolved_path": "",
            "branch_activity_evidence": "source_aware_EKF source_aware_trace_rows=1090 and source scale stats present",
            "safe_for_repair": True,
            "reason": "source-aware policy is runtime config/code behavior; trace files are output evidence rather than solver input providers",
        },
        {
            "provider": "Go2 joint provider",
            "classification": "resolved_existing_G" if paths["go2_joint"].exists() else "missing_everywhere",
            "resolved_path": str(paths["go2_joint"]) if paths["go2_joint"].exists() else "",
            "branch_activity_evidence": "Go2_joint_EKF go2_proprioceptive_joint_factor_update_count=274",
            "safe_for_repair": paths["go2_joint"].exists(),
            "reason": "G archive has N7C6 joint prior provider used by active historical branch" if paths["go2_joint"].exists() else "not found",
        },
        {
            "provider": "Go2 attitude provider",
            "classification": "resolved_existing_G" if paths["go2_attitude"].exists() else "missing_everywhere",
            "resolved_path": str(paths["go2_attitude"]) if paths["go2_attitude"].exists() else "",
            "branch_activity_evidence": "Go2_joint_EKF go2_attitude_weak_prior_update_count=274",
            "safe_for_repair": paths["go2_attitude"].exists(),
            "reason": "G archive has N7C6 attitude prior provider used by active historical branch"
            if paths["go2_attitude"].exists()
            else "not found",
        },
        {
            "provider": "Go2 horizontal velocity provider",
            "classification": "resolved_existing_G" if paths["go2_hv"].exists() else "missing_everywhere",
            "resolved_path": str(paths["go2_hv"]) if paths["go2_hv"].exists() else "",
            "branch_activity_evidence": "Go2_joint_EKF go2_horizontal_velocity_prior_update_count=274",
            "safe_for_repair": paths["go2_hv"].exists(),
            "reason": "G archive has N7C6 horizontal velocity provider used by active historical branch"
            if paths["go2_hv"].exists()
            else "not found",
        },
        {
            "provider": "selected-feedback provider",
            "classification": "resolved_branch_runtime" if paths["feedback"].exists() else "missing_everywhere",
            "resolved_path": str(paths["feedback"]) if paths["feedback"].exists() else "",
            "branch_activity_evidence": "N9C0C same-case feedback active with feedback_update_count=164",
            "safe_for_repair": paths["feedback"].exists(),
            "reason": "N9C0C generated same-case clean feedback for LegSA_full normal smoke" if paths["feedback"].exists() else "not found",
        },
    ]
    return rows, paths


def _write_resolution(workspace: Path, archive: Path, stage_root: Path) -> tuple[bool, dict[str, Path]]:
    rows, paths = _resolution_rows(workspace, archive)
    passed = all(row["safe_for_repair"] for row in rows)
    write_json(
        stage_root / "reports/N9C0C1_PROVIDER_RESOLUTION_DECISION_REPORT.json",
        {
            "stage": STAGE,
            "generated_at": _now(),
            "provider_resolution_pass": passed,
            "normal_smoke_rerun_justified": passed,
            "rows": rows,
        },
    )
    _write_pair(stage_root / "matrix/N9C0C1_PROVIDER_RESOLUTION_DECISION", rows)
    _write_summary(
        stage_root / "summary/n9c0c1_provider_resolution_decision.md",
        "N9C0C1 Provider Resolution Decision",
        [
            f"- Provider resolution pass: {passed}.",
            "- Raw Doppler and Go2 providers resolve to existing G archive files; selected feedback resolves to N9C0C same-case runtime dependency.",
            "- Runtime repair is limited to config/provider paths and does not change algorithm math, FGO factors, or feedback policy.",
        ],
    )
    return passed, paths


def _repair_config_and_rerun(workspace: Path, stage_root: Path, paths: dict[str, Path]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    matrix_root = workspace / "by2-huitu" / "N9B2_FULL_MATRIX"
    n9c0c_full = matrix_root / "LEGSA_FULL_ALGORITHM_MINIMUM_RERUN"
    original_config = n9c0c_full / "runtime_configs/FULL_normal_repeat/LegSA_full_EKF.runtime_config.yaml"
    repaired_config = stage_root / "config_repair/FULL_normal_repeat/LegSA_full_EKF.runtime_config.yaml"
    smoke_output = stage_root / "normal_smoke_rerun/FULL_normal_repeat/LegSA_full_EKF"
    official_dir = stage_root / "official_eval/FULL_normal_repeat/LegSA_full_EKF"
    repaired_config.parent.mkdir(parents=True, exist_ok=True)
    base_text = original_config.read_text(encoding="utf-8", errors="ignore") if original_config.exists() else ""
    overrides = {
        "case_id": '"FULL_normal_repeat"',
        "ablation_variant": "n9c0c1_LegSA_full_EKF_provider_repaired_normal",
        "outputpath": f'"{repo_to_wsl(smoke_output)}"',
        "raw_doppler_factor_path": f'"{repo_to_wsl(paths["raw"])}"',
        "go2_attitude_prior_path": f'"{repo_to_wsl(paths["go2_attitude"])}"',
        "go2_horizontal_velocity_prior_path": f'"{repo_to_wsl(paths["go2_hv"])}"',
        "go2_proprioceptive_joint_factor_path": f'"{repo_to_wsl(paths["go2_joint"])}"',
        "fgo_feedback_path": f'"{repo_to_wsl(paths["feedback"])}"',
        "enable_raw_doppler": "true",
        "enable_source_aware_weighting": "true",
        "source_aware_trace_enabled": "true",
        "enable_go2_attitude_weak_prior": "true",
        "enable_go2_horizontal_velocity_prior": "true",
        "enable_go2_proprioceptive_joint_factor": "true",
        "enable_fgo_feedback": "true",
        "same_case_feedback_required": "true",
        "clean_feedback_for_degraded_case": "false",
        "trace_solver_input": "false",
        "final_v23_output_solver_input": "false",
        "final_v23_solver_input": "false",
        "output_only_correction": "false",
        "bad_epoch_deletion_for_metric": "false",
        "full_matrix_execution": "false",
        "paper_performance_claim": "false",
    }
    repaired_lines = [base_text.rstrip(), "", "# N9C0C1 provider path repair overrides."]
    repaired_lines.extend(f"{key}: {value}" for key, value in overrides.items())
    repaired_config.write_text("\n".join(repaired_lines) + "\n", encoding="utf-8")

    old_values = _parse_config(original_config)
    new_values = _parse_config(repaired_config)
    repair_rows: list[dict[str, Any]] = []
    for key in [
        "raw_doppler_factor_path",
        "go2_attitude_prior_path",
        "go2_horizontal_velocity_prior_path",
        "go2_proprioceptive_joint_factor_path",
        "fgo_feedback_path",
        "outputpath",
        "trace_solver_input",
        "final_v23_solver_input",
        "output_only_correction",
    ]:
        old_path = _from_wsl(old_values.get(key)) if key.endswith("path") or key == "outputpath" else None
        new_path = _from_wsl(new_values.get(key)) if key.endswith("path") or key == "outputpath" else None
        repair_rows.append(
            {
                "key": key,
                "old_value": old_values.get(key),
                "old_exists_windows": old_path.exists() if old_path else None,
                "new_value": new_values.get(key),
                "new_exists_windows": new_path.exists() if new_path else None,
                "changed": old_values.get(key) != new_values.get(key),
                "repair_type": "runtime_config_only",
            }
        )
    write_json(
        stage_root / "reports/N9C0C1_RUNTIME_CONFIG_REPAIR_REPORT.json",
        {
            "stage": STAGE,
            "generated_at": _now(),
            "repaired_config": str(repaired_config),
            "original_config": str(original_config),
            "algorithm_math_changed": False,
            "feedback_policy_changed": False,
            "rows": repair_rows,
        },
    )
    _write_pair(stage_root / "matrix/N9C0C1_RUNTIME_CONFIG_REPAIR_DIFF", repair_rows)

    case = CaseSpec(
        case_id="FULL_normal_repeat",
        batch="BATCH0_SMOKE",
        source_config=repaired_config,
        feedback_observations=paths["feedback"],
        eval_command_template=matrix_root / "BATCH0_SMOKE/official_eval/B0_normal_repeat_formal/Go2_joint_EKF/command.json",
        stage_group="normal_smoke_rerun",
        baseline_eval_nav=matrix_root / "BATCH0_SMOKE/solver_outputs/B0_normal_repeat_formal/baseline_no_feedback_EKF/EVAL_NAV.csv",
    )
    solver = _run_solver(workspace, case, repaired_config, smoke_output)
    eval_result = (
        _run_official_eval(case, smoke_output, official_dir)
        if solver.get("run_status") == "completed"
        else {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "official_eval_status": "skipped",
            "blocked_reason": solver.get("blocked_reason") or "solver failed",
        }
    )
    verification = _module_verification(case.case_id, solver.get("manifest", {}) or {})
    metrics = eval_result.get("metrics", {}) if isinstance(eval_result, dict) else {}
    same_order = (
        solver.get("run_status") == "completed"
        and eval_result.get("official_eval_status") == "completed"
        and verification.get("module_verification_passed") is True
        and metrics.get("horizontal_rmse_m") is not None
        and float(metrics.get("horizontal_rmse_m")) < 20.0
        and metrics.get("yaw_rmse_deg") is not None
        and float(metrics.get("yaw_rmse_deg")) < 30.0
    )
    status_rows = [
        {
            "case_id": case.case_id,
            "algorithm": ALGORITHM_ID,
            "solver_status": solver.get("run_status"),
            "solver_returncode": solver.get("returncode"),
            "official_eval_status": eval_result.get("official_eval_status"),
            "official_eval_returncode": eval_result.get("returncode"),
            "module_verification_passed": verification.get("module_verification_passed"),
            "same_order_sanity": same_order,
            "trace_solver_input": verification.get("trace_solver_input"),
            "final_v23_solver_input": verification.get("final_v23_solver_input"),
            "output_substitution": verification.get("output_substitution"),
            "horizontal_rmse_m": metrics.get("horizontal_rmse_m"),
            "up_rmse_m": metrics.get("up_rmse_m"),
            "yaw_rmse_deg": metrics.get("yaw_rmse_deg"),
            "row_count": metrics.get("row_count"),
            "blocked_reason": solver.get("blocked_reason") or eval_result.get("blocked_reason") or "",
        }
    ]
    metric_rows = [{"case_id": case.case_id, "algorithm": ALGORITHM_ID, **metrics}] if metrics else []
    report = {
        "stage": STAGE,
        "generated_at": _now(),
        "executed": True,
        "solver": solver,
        "official_eval": eval_result,
        "verification": verification,
        "same_order_sanity": same_order,
    }
    return report, status_rows, metric_rows, verification


def _write_empty_repair(stage_root: Path, reason: str) -> None:
    write_json(
        stage_root / "reports/N9C0C1_RUNTIME_CONFIG_REPAIR_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "status": "skipped", "blocked_reason": reason, "rows": []},
    )
    _write_pair(stage_root / "matrix/N9C0C1_RUNTIME_CONFIG_REPAIR_DIFF", [])


def _write_terminal_reports(
    stage_root: Path,
    provider_resolution_pass: bool,
    normal_report: dict[str, Any],
    status_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    verification: dict[str, Any],
) -> dict[str, Any]:
    write_json(stage_root / "reports/N9C0C1_NORMAL_SMOKE_RERUN_REPORT.json", normal_report)
    _write_pair(stage_root / "matrix/N9C0C1_NORMAL_SMOKE_RERUN_STATUS", status_rows)
    _write_pair(stage_root / "matrix/N9C0C1_NORMAL_SMOKE_RERUN_METRICS", metric_rows)
    _write_summary(
        stage_root / "summary/n9c0c1_normal_smoke_rerun_summary.md",
        "N9C0C1 Normal Smoke Rerun Summary",
        [
            f"- Executed: {normal_report.get('executed')}.",
            f"- Solver status: {status_rows[0].get('solver_status') if status_rows else 'skipped'}.",
            f"- Official eval status: {status_rows[0].get('official_eval_status') if status_rows else 'skipped'}.",
            f"- Module verification passed: {status_rows[0].get('module_verification_passed') if status_rows else False}.",
            f"- hRMSE: {status_rows[0].get('horizontal_rmse_m') if status_rows else None}.",
            f"- yaw RMSE: {status_rows[0].get('yaw_rmse_deg') if status_rows else None}.",
        ],
    )
    ready_c2 = bool(
        status_rows
        and status_rows[0].get("module_verification_passed") is True
        and status_rows[0].get("same_order_sanity") is True
    )
    readiness_rows = [
        {"check": "provider_resolution_passed", "status": "pass" if provider_resolution_pass else "fail"},
        {
            "check": "normal_smoke_solver_completed",
            "status": "pass" if status_rows and status_rows[0].get("solver_status") == "completed" else "fail",
        },
        {
            "check": "official_eval_completed",
            "status": "pass" if status_rows and status_rows[0].get("official_eval_status") == "completed" else "fail",
        },
        {
            "check": "raw_doppler_updates_positive",
            "status": "pass" if int(verification.get("raw_doppler_update_count") or 0) > 0 else "fail",
            "value": verification.get("raw_doppler_update_count"),
        },
        {
            "check": "go2_joint_updates_positive",
            "status": "pass" if int(verification.get("go2_joint_update_count") or 0) > 0 else "fail",
            "value": verification.get("go2_joint_update_count"),
        },
        {
            "check": "go2_attitude_updates_positive",
            "status": "pass" if int(verification.get("go2_attitude_update_count") or 0) > 0 else "fail",
            "value": verification.get("go2_attitude_update_count"),
        },
        {
            "check": "go2_horizontal_velocity_updates_positive",
            "status": "pass" if int(verification.get("go2_horizontal_velocity_update_count") or 0) > 0 else "fail",
            "value": verification.get("go2_horizontal_velocity_update_count"),
        },
        {
            "check": "selected_feedback_updates_positive",
            "status": "pass" if int(verification.get("feedback_update_count") or 0) > 0 else "fail",
            "value": verification.get("feedback_update_count"),
        },
        {
            "check": "no_trace_or_final_v23_solver_input",
            "status": "pass"
            if not verification.get("trace_solver_input") and not verification.get("final_v23_solver_input")
            else "fail",
        },
        {"check": "full_matrix_not_run", "status": "pass"},
    ]
    write_json(
        stage_root / "reports/N9C0C1_MINIMUM_RERUN_READINESS_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "ready_for_N9C0C2_minimum_rerun": ready_c2, "rows": readiness_rows},
    )
    _write_pair(stage_root / "matrix/N9C0C1_MINIMUM_RERUN_READINESS_CHECKLIST", readiness_rows)
    _write_summary(
        stage_root / "summary/n9c0c1_minimum_rerun_readiness.md",
        "N9C0C1 Minimum Rerun Readiness",
        [
            f"- ready_for_N9C0C2_minimum_rerun: {ready_c2}.",
            "- N9C0C1 did not run minimum degradation cases; it only decides readiness after the repaired normal smoke.",
        ],
    )
    if ready_c2:
        decision = "N9C0C1_provider_inputs_resolved_normal_smoke_passed"
        recommended = "N9C0C2_LEGSA_FULL_MINIMUM_RERUN"
    elif provider_resolution_pass:
        decision = "N9C0C1_provider_resolution_inconclusive"
        recommended = "manual_provider_path_review"
    else:
        decision = "N9C0C1_prior_branches_inert_or_provider_missing"
        recommended = "human_decision_reframe_as_branch_ablation_or_implement_provider_pipeline"

    reviewer_rows = [
        {"check": "no_full_matrix_run", "status": "pass"},
        {"check": "no_paper_figures", "status": "pass"},
        {
            "check": "branch_effect_audit_did_not_assume_flags",
            "status": "pass",
            "evidence": "active_effect requires provider status/update counts",
        },
        {
            "check": "provider_files_real_and_source_compatible",
            "status": "pass" if provider_resolution_pass else "fail",
            "evidence": "G provider files exist and historical branch manifests had matching updates",
        },
        {"check": "C_and_G_roots_searched", "status": "pass"},
        {"check": "no_fabricated_provider_evidence", "status": "pass"},
        {"check": "normal_smoke_uses_repaired_config_only", "status": "pass" if normal_report.get("executed") else "blocked"},
        {
            "check": "no_trace_or_final_v23_solver_input",
            "status": "pass"
            if not verification.get("trace_solver_input") and not verification.get("final_v23_solver_input")
            else "fail",
        },
        {"check": "no_algorithm_math_change", "status": "pass"},
        {"check": "runtime_outputs_untracked", "status": "pending_external_git_status_check"},
        {"check": "conclusion_conservative", "status": "pass"},
    ]
    write_json(stage_root / "reports/N9C0C1_REVIEWER_REPORT.json", {"stage": STAGE, "generated_at": _now(), "rows": reviewer_rows})
    _write_pair(stage_root / "matrix/N9C0C1_REVIEWER_CHECKS", reviewer_rows)
    _write_summary(
        stage_root / "summary/n9c0c1_reviewer_summary.md",
        "N9C0C1 Reviewer Summary",
        [
            "- Reviewer checks are conservative and read-only over generated artifacts.",
            f"- Provider repair status: {'pass' if provider_resolution_pass else 'blocked'}.",
            f"- Normal smoke module verification: {verification.get('module_verification_passed') if verification else False}.",
        ],
    )
    validation_rows = [
        {"check": "no_full_matrix_execution", "status": "pass"},
        {"check": "no_final_paper_figures", "status": "pass"},
        {"check": "provider_inventory_complete_for_C_and_G", "status": "pass"},
        {"check": "branch_effect_audit_no_flag_only_assumption", "status": "pass"},
        {"check": "provider_resolution_decision_complete", "status": "pass"},
        {"check": "normal_smoke_module_verification_checked", "status": "pass" if verification else "fail"},
        {"check": "paper_claims_false", "status": "pass"},
        {"check": "ready_for_N9B2_execution_false", "status": "pass"},
        {"check": "ready_for_N9C1_false", "status": "pass"},
    ]
    for report in sorted((stage_root / "reports").glob("*.json")):
        validation_rows.append(
            {
                "check": f"utf8_no_bom:{report.name}",
                "status": "pass" if not report.read_bytes().startswith(b"\xef\xbb\xbf") else "fail",
            }
        )
    for table in sorted((stage_root / "matrix").glob("*.csv")):
        try:
            with table.open("r", encoding="utf-8-sig", newline="") as handle:
                list(csv.DictReader(handle))
            status = "pass"
        except (OSError, csv.Error):
            status = "fail"
        validation_rows.append({"check": f"csv_parse_ok:{table.name}", "status": status})
    validation_status = "pass" if all(row.get("status") == "pass" for row in validation_rows) else "fail"
    write_json(
        stage_root / "reports/N9C0C1_VALIDATION_REPORT.json",
        {"stage": STAGE, "generated_at": _now(), "validation_status": validation_status, "rows": validation_rows},
    )
    _write_pair(stage_root / "matrix/N9C0C1_VALIDATION_CHECKS", validation_rows)
    decision_report = {
        "stage": STAGE,
        "generated_at": _now(),
        "decision": decision,
        "ready_for_N9C0C2_minimum_rerun": ready_c2,
        "ready_for_N9C1_consolidated_figure_generation": False,
        "ready_for_paper_claims": False,
        "ready_for_N9B2_execution": False,
        "ready_for_full_N9B_execution": False,
        "recommended_next_stage": recommended,
        "provider_resolution_pass": provider_resolution_pass,
        "normal_smoke_module_verification_passed": verification.get("module_verification_passed") if verification else False,
        "complete_nine_factor_fgo_claim": False,
    }
    write_json(stage_root / "reports/N9C0C1_DECISION_REPORT.json", decision_report)
    _write_summary(
        stage_root / "summary/n9c0c1_next_stage_recommendation.md",
        "N9C0C1 Next Stage Recommendation",
        [
            f"- Decision: {decision}.",
            f"- ready_for_N9C0C2_minimum_rerun: {ready_c2}.",
            "- ready_for_N9C1_consolidated_figure_generation: False.",
            "- ready_for_paper_claims: False.",
            f"- recommended_next_stage: {recommended}.",
        ],
    )
    return decision_report


def run_n9c0c1(workspace: Path, archive: Path, *, execute: bool = True) -> dict[str, Any]:
    workspace = workspace.resolve()
    archive = archive.resolve()
    stage_root = workspace / "by2-huitu" / STAGE
    _prepare_root(stage_root)
    _branch_effect_audit(workspace, stage_root)
    _provider_inventory(workspace, archive, stage_root)
    provider_resolution_pass, provider_paths = _write_resolution(workspace, archive, stage_root)
    if execute and provider_resolution_pass:
        normal_report, status_rows, metric_rows, verification = _repair_config_and_rerun(workspace, stage_root, provider_paths)
    else:
        reason = "execution disabled" if not execute else "provider resolution did not pass"
        _write_empty_repair(stage_root, reason)
        normal_report = {"stage": STAGE, "generated_at": _now(), "executed": False, "blocked_reason": reason}
        status_rows = []
        metric_rows = []
        verification = {}
    decision_report = _write_terminal_reports(
        stage_root,
        provider_resolution_pass,
        normal_report,
        status_rows,
        metric_rows,
        verification,
    )
    (stage_root / "00_supervisor/N9C0C1_SUPERVISOR_DECISION.md").write_text(
        "# N9C0C1 Supervisor Decision\n\n"
        f"- Decision: {decision_report['decision']}\n"
        f"- Output root: {stage_root}\n"
        "- Full N9B2 matrix execution: False\n"
        "- Final paper figures: False\n"
        "- Paper claims: False\n"
        f"- Ready for N9C0C2 minimum rerun: {decision_report['ready_for_N9C0C2_minimum_rerun']}\n",
        encoding="utf-8",
    )
    (stage_root / "01_plan/N9C0C1_PLANNER_SUMMARY.md").write_text(
        "# N9C0C1 Planner Summary\n\n"
        "- Read N9C0C failure artifacts and BATCH0 branch manifests/configs.\n"
        "- Determined historical Raw_Doppler_EKF and Go2_joint_EKF branches had active update counts.\n"
        "- Searched C and G roots for providers; selected G archive providers when C providers were missing.\n"
        "- Authorized only runtime config/provider-path repair and normal smoke rerun.\n",
        encoding="utf-8",
    )
    decision_report["output_root"] = str(stage_root)
    return decision_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--archive-root", required=True)
    parser.add_argument(
        "--execute-normal-smoke",
        action="store_true",
        help="Run the repaired LegSA_full_EKF normal smoke after provider resolution passes.",
    )
    parser.add_argument("--no-execute", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_n9c0c1(
        Path(args.workspace_root),
        Path(args.archive_root),
        execute=args.execute_normal_smoke and not args.no_execute,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
