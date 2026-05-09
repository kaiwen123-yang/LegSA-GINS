"""Reference-independence audit for N4H4R3B.

中文说明：clean GNSS/IMU 可以作为 port solver input；dual_final_v23/reference
只能用于 evaluation，不能进入 solver，也不能由 port output 反构。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(value: str | Path | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    path = Path(value)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _read_config(value: str | Path | dict[str, Any] | None) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if not value:
        return {}
    path = Path(value)
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, text = line.split(":", 1)
        out[key.strip()] = text.strip().strip('"').strip("'")
    return out


def _path_hits(path_text: str, needles: list[str]) -> bool:
    lowered = path_text.lower()
    return any(needle.lower() in lowered for needle in needles)


def analyze_reference_independence(
    run_manifest: str | Path | dict[str, Any] | None,
    config: str | Path | dict[str, Any] | None,
    runner_report: dict[str, Any] | None = None,
    evaluator_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _load_json(run_manifest)
    cfg = _read_config(config)
    runner_report = runner_report or {}
    evaluator_report = evaluator_report or {}
    solver_inputs = {
        "imu": cfg.get("imupath") or cfg.get("imu_path") or manifest.get("solver_input_files", {}).get("imu"),
        "gnss": cfg.get("gnsspath") or cfg.get("gnss_path") or manifest.get("solver_input_files", {}).get("gnss"),
    }
    solver_text = " ".join(str(value or "") for value in solver_inputs.values())
    trace_solver_input = bool(manifest.get("trace_solver_input", False)) or _path_hits(solver_text, ["trace"])
    final_solver_input = bool(manifest.get("final_v23_output_solver_input", False)) or _path_hits(
        solver_text,
        ["KF_GINS_Navresult", "KF_GINS_STD", "final_results", "dual_final_v23"],
    )
    reference_depends = bool(
        evaluator_report.get("reference_reconstruction_depends_on_port_output")
        or runner_report.get("reference_reconstruction_depends_on_port_output")
        or evaluator_report.get("evaluator_uses_port_output_to_build_reference")
    )
    evaluator_uses_port_output = bool(evaluator_report.get("evaluator_uses_port_output_to_build_reference", False))
    clean_gnss_eval_ref = bool(
        evaluator_report.get("clean_gnss_evaluation_reference", False)
        or str(evaluator_report.get("evaluation_reference_role", "")).lower().startswith("clean_gnss")
    )
    dual_eval_only = not bool(evaluator_report.get("dual_reference_as_solver_input", False))
    evidence_missing = not manifest and not cfg
    ok = not any([trace_solver_input, final_solver_input, reference_depends, evaluator_uses_port_output, clean_gnss_eval_ref])
    return {
        "phase": "N4H4R3B",
        "solver_input_files": solver_inputs,
        "evaluation_reference_files": evaluator_report.get("evaluation_reference_files", {}),
        "trace_solver_input": trace_solver_input,
        "final_v23_output_solver_input": final_solver_input,
        "dual_reference_eval_only": dual_eval_only,
        "clean_gnss_solver_input": bool(solver_inputs.get("gnss")),
        "clean_gnss_evaluation_reference": clean_gnss_eval_ref,
        "reference_reconstruction_depends_on_port_output": reference_depends,
        "evaluator_uses_port_output_to_build_reference": evaluator_uses_port_output,
        "reference_independence_ok": ok and not evidence_missing,
        "evidence_missing": evidence_missing,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
