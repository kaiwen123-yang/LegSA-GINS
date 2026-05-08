"""Clean/noisy input provenance policy for N4H2G.

中文说明：本模块只生成 provenance policy 报告，明确 clean replay 与 noisy
historical artifact 的证据边界；不修改 solver、不做性能宣称。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_clean_input_provenance_policy_report(
    clean_manifest: dict[str, Any],
    comparison_report: dict[str, Any],
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build the N4H2G clean/noisy provenance policy report."""

    report = {
        "phase": "N4H2G",
        "actual_dual_final_v23_artifact_likely_has_gaussian_yaw_noise_1p5_deg": True,
        "clean_replay_is_reconstructed_clean_variant": True,
        "clean_replay_is_not_historical_exact_final_v23_artifact": True,
        "noisy_actual_is_valid_as_stress_or_noisy_provenance_baseline": True,
        "paper_should_not_call_noisy_actual_clean_nominal": True,
        "future_factor_evaluation_should_prefer_clean_replay_or_explicitly_labeled_noisy_replay": True,
        "clean_input_policy": clean_manifest.get("clean_input_policy", {}),
        "clean_input_has_synthetic_yaw_noise": False,
        "noisy_artifact_has_gaussian_yaw_noise": bool(comparison_report.get("noisy_artifact_has_gaussian_yaw_noise")),
        "clean_replay_parity_status": comparison_report.get("clean_replay_parity_status"),
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    if output_dir is not None:
        out = Path(output_dir) / "CLEAN_INPUT_PROVENANCE_POLICY_REPORT.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
