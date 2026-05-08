"""Read-only process_data yaw-noise provenance audit for N4H2F.

中文说明：本模块只读外部 KF-GINS 脚本并可将 variant `.gnss` 生成到临时目录；
不修改外部源码，不把 trace-yaw diagnostic 当作 solver input。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.actual_vs_replay_yaw_path import parse_15col_gnss, wrap_deg180


DEFAULT_VARIANTS: list[dict[str, Any]] = [
    {
        "name": "status_safe_no_noise",
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "formal_allowed": True,
    },
    {
        "name": "status_fixed_std_only",
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "formal_allowed": True,
    },
    {
        "name": "status_gaussian_1p5_no_outlier",
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 1.5,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "seed": 42,
        "formal_allowed": True,
    },
    {
        "name": "status_gaussian_1p5_legacy15",
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 1.5,
        "outlier_mode": "legacy15",
        "outlier_ratio": 0.15,
        "enable_outage": False,
        "seed": 42,
        "formal_allowed": True,
    },
    {
        "name": "status_gaussian_1p5_legacy15_outage",
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 1.5,
        "outlier_mode": "legacy15",
        "outlier_ratio": 0.15,
        "enable_outage": True,
        "outage_duration_sec": 10.0,
        "seed": 42,
        "formal_allowed": True,
    },
    {
        "name": "trace_yaw_diagnostic_only",
        "yaw_source_mode": "trace",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "formal_allowed": False,
    },
]


CONSTANT_KEYS = [
    "BASE_TIME",
    "USE_STATUS_YAW",
    "YAW_SOURCE_MODE",
    "YAW_SIGN",
    "YAW_INSTALL_OFFSET_DEG",
    "AUTO_APPLY_BEST_INSTALL",
    "YAW_NOISE_STD_DEG",
    "OUTLIER_RATIO_DEFAULT",
    "OUTLIER_MODE_DEFAULT",
    "OUTAGE_DURATION_SEC",
    "STATUS_YAW_STD_MODE_DEFAULT",
    "STATUS_FIXED_YAW_STD_DEG_DEFAULT",
    "YAW_STD_MODE_DEFAULT",
]


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def _literal_constants(text: str) -> dict[str, Any]:
    constants: dict[str, Any] = {}
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in CONSTANT_KEYS:
                try:
                    constants[name] = ast.literal_eval(node.value)
                except Exception:
                    constants[name] = ast.unparse(node.value) if hasattr(ast, "unparse") else None
    return constants


def audit_process_data_script(process_data_path: str | Path) -> dict[str, Any]:
    """Read process_data.py and identify yaw std/noise/outlier controls."""

    path = Path(process_data_path)
    text = _read_text(path)
    constants = _literal_constants(text)
    process_gnss_match = re.search(r"def\s+process_gnss\s*\((.*?)\)\s*->", text, re.DOTALL)
    process_gnss_signature = process_gnss_match.group(1) if process_gnss_match else ""
    defaults = {key.lower(): value for key, value in constants.items()}
    gaussian = "np.random.normal" in text and "yaw_noise_std_deg" in text and "yaw_ned = wrap_deg(yaw_ned + noise)" in text
    legacy = "legacy15" in text and "np.random.uniform(15.0, 25.0)" in text
    cli_flags = {
        "--yaw_noise_std_deg": "--yaw_noise_std_deg" in text,
        "--outlier_ratio": "--outlier_ratio" in text,
        "--outlier_mode": "--outlier_mode" in text,
        "--enable_outage": "--enable_outage" in text,
        "--yaw_std_mode": "--yaw_std_mode" in text,
        "--yaw_source_mode": "--yaw_source_mode" in text,
    }
    default_enable_outage = "enable_outage: bool = True" in process_gnss_signature
    main_defaults_outage_true = "enable_outage = True if args.enable_outage is None" in text
    return {
        "phase": "N4H2F",
        "process_data_path": str(path),
        "defaults": defaults,
        "default_enable_outage_in_process_gnss": default_enable_outage,
        "default_enable_outage_in_main_when_omitted": main_defaults_outage_true,
        "process_gnss_adds_gaussian_yaw_noise": gaussian,
        "process_gnss_adds_legacy_outliers": legacy,
        "process_gnss_can_disable_outlier_outage_noise_via_cli": all(cli_flags.values()),
        "cli_flags": cli_flags,
        "fixed_yaw_std_default_detected": constants.get("STATUS_YAW_STD_MODE_DEFAULT") == "fixed_1p5",
        "yaw_std_is_not_yaw_noise": True,
        "evidence_status": "read_only_source_audited",
        "no_source_modification": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _extract_cases(text: str) -> list[dict[str, Any]]:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "CASES":
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CASES":
                    return ast.literal_eval(node.value)
    return []


def audit_run_final_mainline(run_script_path: str | Path) -> dict[str, Any]:
    """Read final mainline batch script and classify its role."""

    path = Path(run_script_path)
    text = _read_text(path)
    cases = _extract_cases(text)
    all_noise = bool(cases) and all(float(case.get("yaw_noise_std_deg", 0.0)) > 0.0 for case in cases)
    all_outlier = bool(cases) and all(float(case.get("outlier_ratio", 0.0)) > 0.0 for case in cases)
    any_outage = any(bool(case.get("enable_outage")) for case in cases)
    all_outage = bool(cases) and all(bool(case.get("enable_outage")) for case in cases)
    process_invocation_flags = {
        "--yaw_std_mode": "--yaw_std_mode" in text,
        "--yaw_noise_std_deg": "--yaw_noise_std_deg" in text,
        "--outlier_ratio": "--outlier_ratio" in text,
        "--outlier_mode": "--outlier_mode" in text,
        "--enable_outage": "--enable_outage" in text,
    }
    degradation_batch = bool(len(cases) >= 3 and all_noise and all_outlier and any_outage)
    return {
        "phase": "N4H2F",
        "run_final_mainline_path": str(path),
        "case_count": len(cases),
        "cases": cases,
        "yaw_noise_std_deg_per_case": [case.get("yaw_noise_std_deg") for case in cases],
        "outlier_ratio_per_case": [case.get("outlier_ratio") for case in cases],
        "enable_outage_per_case": [case.get("enable_outage") for case in cases],
        "process_data_invocation_flags": process_invocation_flags,
        "script_role": "degradation_batch_or_final_stress_pipeline" if degradation_batch else "evidence_inconclusive",
        "run_final_mainline_degradation_batch": degradation_batch,
        "not_clean_nominal_by_default": bool(all_noise or all_outlier or any_outage),
        "all_cases_have_yaw_noise": all_noise,
        "all_cases_have_outlier": all_outlier,
        "any_case_has_outage": any_outage,
        "all_cases_have_outage": all_outage,
        "cannot_treat_as_nominal_none_clean_source": bool(all_noise or all_outlier or any_outage),
        "evidence_status": "read_only_source_audited",
        "no_source_modification": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _load_process_data_module(process_data_path: Path):
    spec = importlib.util.spec_from_file_location("external_process_data_runtime_only", process_data_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load process_data module: {process_data_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_gnss_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                "{time:.9f} {lat:.12f} {lon:.12f} {height:.6f} {std_n:.6f} {std_e:.6f} {std_d:.6f} "
                "{vn:.9f} {ve:.9f} {vd:.9f} {std_vn:.6f} {std_ve:.6f} {std_vd:.6f} {yaw:.9f} {yaw_std:.9f}\n".format(
                    **row
                )
            )


def _noise_vector(count: int, std_deg: float, outlier_mode: str, outlier_ratio: float) -> list[float]:
    try:
        import numpy as np

        np.random.seed(42)
        noise = np.random.normal(loc=0.0, scale=float(std_deg), size=count)
        if outlier_mode in {"legacy15", "legacy"} and outlier_ratio > 0.0:
            mild_ratio = outlier_ratio * (2.0 / 3.0)
            for index in range(count):
                rand_val = np.random.rand()
                if rand_val < mild_ratio:
                    noise[index] += np.random.choice([1, -1]) * np.random.uniform(5.0, 10.0)
                elif rand_val < outlier_ratio:
                    noise[index] += np.random.choice([1, -1]) * np.random.uniform(15.0, 25.0)
        return [float(value) for value in noise]
    except Exception:  # pragma: no cover - numpy is present in runtime but keep deterministic fallback
        import random

        rng = random.Random(42)
        noise = [rng.gauss(0.0, float(std_deg)) for _ in range(count)]
        if outlier_mode in {"legacy15", "legacy"} and outlier_ratio > 0.0:
            mild_ratio = outlier_ratio * (2.0 / 3.0)
            for index in range(count):
                rand_val = rng.random()
                if rand_val < mild_ratio:
                    noise[index] += rng.choice([1, -1]) * rng.uniform(5.0, 10.0)
                elif rand_val < outlier_ratio:
                    noise[index] += rng.choice([1, -1]) * rng.uniform(15.0, 25.0)
        return noise


def _generate_variants_from_fallback_input(
    fallback_input_gnss: str | Path,
    output: Path,
    variants: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = parse_15col_gnss(fallback_input_gnss)
    generated: dict[str, Any] = {}
    for variant in variants:
        name = str(variant["name"])
        rows = [dict(row) for row in baseline]
        if variant.get("yaw_source_mode") == "trace":
            evidence_status = "generated_fallback_trace_diagnostic_not_formal"
        else:
            evidence_status = "generated_fallback_from_process_data_compatible_input"
        noise = _noise_vector(
            len(rows),
            float(variant.get("yaw_noise_std_deg", 0.0)),
            str(variant.get("outlier_mode", "none")),
            float(variant.get("outlier_ratio", 0.0)),
        )
        for row, delta in zip(rows, noise):
            row["yaw"] = wrap_deg180(float(row["yaw"]) + float(delta))
            row["yaw_std"] = 1.5 if variant.get("yaw_std_mode") == "fixed_1p5" else float(row["yaw_std"])
        if variant.get("enable_outage"):
            duration = float(variant.get("outage_duration_sec", 10.0))
            start = variant.get("outage_start")
            if start is None and rows:
                times = [float(row["time"]) for row in rows]
                start_t = sorted(times)[len(times) // 2]
            else:
                start_t = float(start)
            end_t = start_t + duration
            rows = [row for row in rows if not (start_t <= float(row["time"]) <= end_t)]
        out_path = output / f"{name}.gnss"
        _write_gnss_rows(out_path, rows)
        generated[name] = {
            "path": str(out_path),
            "formal_allowed": bool(variant.get("formal_allowed", True)),
            "parameters": variant,
            "evidence_status": evidence_status,
            "fallback_input_role": "N4H2_ARTIFACTS_ROOT/process_data_compatible_input",
        }
    return generated


def generate_yaw_variant_inputs(
    output_dir: str | Path,
    variants: list[dict[str, Any]] | None = None,
    *,
    process_data_path: str | Path | None = None,
    fallback_input_gnss: str | Path | None = None,
) -> dict[str, Any]:
    """Generate process_data variants to a runtime-only output directory."""

    variants = variants or DEFAULT_VARIANTS
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    process_path = Path(process_data_path) if process_data_path else Path.home() / "KF-GINS" / "bin" / "process_data.py"
    report: dict[str, Any] = {
        "phase": "N4H2F",
        "variant_output_dir": str(output),
        "variant_inputs": {},
        "generation_status": "not_started",
        "evidence_missing": [],
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
    try:
        module = _load_process_data_module(process_path)
    except Exception as exc:
        report.update({"generation_status": "failed", "error": str(exc), "evidence_missing": ["process_data_import"]})
        return report
    for variant in variants:
        name = str(variant["name"])
        out_path = output / f"{name}.gnss"
        try:
            module.process_gnss(
                yaw_source_mode=variant.get("yaw_source_mode", "status"),
                gnss_output_path=str(out_path),
                write_status_report=False,
                yaw_std_mode=variant.get("yaw_std_mode"),
                yaw_noise_std_deg=float(variant.get("yaw_noise_std_deg", 0.0)),
                enable_outage=bool(variant.get("enable_outage", False)),
                outage_start=variant.get("outage_start"),
                outage_duration_sec=float(variant.get("outage_duration_sec", 10.0)),
                outlier_ratio=float(variant.get("outlier_ratio", 0.0)),
                outlier_mode=str(variant.get("outlier_mode", "none")),
                status_yaw_std_mode=str(variant.get("status_yaw_std_mode", "fixed_1p5")),
                status_fixed_yaw_std_deg=float(variant.get("status_fixed_yaw_std_deg", 1.5)),
            )
            report["variant_inputs"][name] = {
                "path": str(out_path),
                "formal_allowed": bool(variant.get("formal_allowed", True)),
                "parameters": variant,
                "evidence_status": "generated",
            }
        except Exception as exc:  # pragma: no cover - depends on external data availability
            report["variant_inputs"][name] = {
                "path": str(out_path),
                "formal_allowed": bool(variant.get("formal_allowed", True)),
                "parameters": variant,
                "evidence_status": "evidence_missing",
                "error": str(exc),
            }
            report["evidence_missing"].append(name)
    generated = [name for name, item in report["variant_inputs"].items() if item.get("evidence_status") == "generated"]
    if not generated and fallback_input_gnss and Path(fallback_input_gnss).exists():
        fallback_generated = _generate_variants_from_fallback_input(fallback_input_gnss, output, variants)
        report["variant_inputs"] = fallback_generated
        report["fallback_generation_used"] = True
        report["fallback_input_role"] = "N4H2_ARTIFACTS_ROOT/process_data_compatible_input"
        generated = list(fallback_generated)
        report["evidence_missing"] = []
    report["generation_status"] = "generated" if generated else "failed"
    report["generated_variant_count"] = len(generated)
    return report


def make_process_data_noise_provenance_report(
    process_data_audit: dict[str, Any],
    run_final_mainline_audit: dict[str, Any],
    generation_report: dict[str, Any],
    variant_match_report: dict[str, Any],
) -> dict[str, Any]:
    """Combine source, batch, generation, and actual input match evidence."""

    status = variant_match_report.get("actual_yaw_noise_injection_status")
    nominal_clean = bool(variant_match_report.get("nominal_clean_claim_allowed"))
    return {
        "phase": "N4H2F",
        "process_data_audit": process_data_audit,
        "run_final_mainline_audit": run_final_mainline_audit,
        "yaw_variant_generation": generation_report,
        "actual_input_yaw_variant_match": variant_match_report,
        "fixed_yaw_std_1p5_detected": None,
        "fixed_yaw_std_1p5_detected_independent_from_yaw_noise": True,
        "yaw_std_is_not_yaw_noise": True,
        "actual_yaw_noise_injection_status": status,
        "nominal_clean_claim_allowed": nominal_clean,
        "recommended_action": "manual_review_then_merge_PR15_if_no_new_visual_issue"
        if nominal_clean
        else "manual_review_with_yaw_noise_provenance_caveat_before_N4H3",
        "evidence_status": "computed",
        "no_source_modification": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def write_json_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
