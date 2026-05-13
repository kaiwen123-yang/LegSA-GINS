"""Run N7B4 diagnostic-only Go2 velocity activation variants.

中文说明：这里只使用已存在的 C++ diagnostic velocity prior path；所有 variant
均为 diagnostic-only，不启用正式 Go2 velocity/yaw prior，不做性能 claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .go2_diagnostic_activation_runner import _append_config, _read_eval_nav, _run_variant, _state_delta_summary, _write_json
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config


VARIANT_IDS = [
    "baseline_no_go2_velocity",
    "probability_weighted_go2_velocity_diagnostic",
    "high_confidence_only_go2_velocity_diagnostic",
    "low_weight_all_epochs_go2_velocity_diagnostic",
    "top2_frame_probability_weighted_diagnostic",
    "yaw_rate_report_only",
]


def run_n7b4_diagnostic_activation_variants(
    *,
    clean_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    raw_doppler_factor_path: str | Path | None,
    prior_paths: dict[str, Path],
    allow_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_config = find_clean_config(clean_root)
    blockers: list[str] = []
    if base_config is None:
        blockers.append("clean_replay_config_missing")
    if not Path(exe).exists():
        blockers.append("cpp_demo_executable_missing")
    if not allow_run:
        blockers.append("allow_run_false")
    variant_to_prior = {
        "baseline_no_go2_velocity": None,
        "probability_weighted_go2_velocity_diagnostic": prior_paths.get("probability_weighted"),
        "high_confidence_only_go2_velocity_diagnostic": prior_paths.get("high_confidence_only"),
        "low_weight_all_epochs_go2_velocity_diagnostic": prior_paths.get("low_weight_all_epochs"),
        "top2_frame_probability_weighted_diagnostic": prior_paths.get("top2_frame_probability_weighted"),
        "yaw_rate_report_only": None,
    }
    runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    baseline_rows = []
    if blockers:
        for variant_id in VARIANT_IDS:
            summaries.append(
                {
                    "variant_id": variant_id,
                    "run_status": "blocked",
                    "blocker_reasons": blockers,
                    "diagnostic_only": True,
                    "paper_performance_claim": False,
                }
            )
    else:
        assert base_config is not None
        for variant_id in VARIANT_IDS:
            prior = variant_to_prior[variant_id]
            config = _append_config(
                base_config=base_config,
                output_path=out / "runtime_configs" / f"{variant_id}.yaml",
                variant_id=variant_id,
                raw_doppler_factor_path=raw_doppler_factor_path,
                velocity_prior_path=prior if prior and prior.exists() else None,
                yaw_rate_prior_path=None,
            )
            variant_dir = out / "variants" / variant_id
            run = _run_variant(exe, config, variant_dir)
            run["variant_id"] = variant_id
            runs.append(run)
            if variant_id == "baseline_no_go2_velocity":
                baseline_rows = _read_eval_nav(variant_dir / "EVAL_NAV.csv")
            manifest = run.get("manifest", {})
            state_delta = (
                {"count": len(baseline_rows), "evidence_status": "baseline", "state_delta_not_truth_error": True}
                if variant_id == "baseline_no_go2_velocity"
                else _state_delta_summary(variant_dir, baseline_rows)
            )
            updates = int(manifest.get("go2_velocity_prior_update_count", 0) or 0)
            rejects = int(manifest.get("go2_velocity_prior_reject_count", 0) or 0)
            if run["returncode"] != 0:
                label = "diagnostic_degradation"
            elif variant_id == "baseline_no_go2_velocity":
                label = "baseline"
            elif updates > 0:
                label = "diagnostic_stable_state_delta_only"
            else:
                label = "diagnostic_no_effect_no_updates"
            summaries.append(
                {
                    "variant_id": variant_id,
                    "run_status": "stable_no_reference_metric" if run["returncode"] == 0 else "diagnostic_activation_failed",
                    "diagnostic_label": label,
                    "returncode": run["returncode"],
                    "go2_velocity_prior_diagnostic_enabled": bool(manifest.get("go2_velocity_prior_diagnostic_enabled", False)),
                    "go2_velocity_prior_update_count": updates,
                    "go2_velocity_prior_reject_count": rejects,
                    "go2_yaw_rate_prior_diagnostic_enabled": bool(manifest.get("go2_yaw_rate_prior_diagnostic_enabled", False)),
                    "go2_yaw_rate_prior_update_count": int(manifest.get("go2_yaw_rate_prior_update_count", 0) or 0),
                    "go2_yaw_rate_activation_status": manifest.get("go2_yaw_rate_prior_activation_status", ""),
                    "measurement_update_count": int(manifest.get("measurement_update_count", 0) or 0),
                    "raw_doppler_update_count": int(manifest.get("raw_doppler_update_count", 0) or 0),
                    "state_delta_summary": state_delta,
                    "diagnostic_only": True,
                    "paper_performance_claim": False,
                    "go2_velocity_truth_claim": False,
                    "formal_go2_velocity_prior": False,
                }
            )
    degraded = any(row.get("diagnostic_label") == "diagnostic_degradation" for row in summaries)
    stable_with_updates = [
        str(row.get("variant_id"))
        for row in summaries
        if row.get("diagnostic_label") == "diagnostic_stable_state_delta_only"
    ]
    report = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "variants_requested": VARIANT_IDS,
        "variants_run": [row.get("variant_id") for row in summaries if row.get("run_status") != "blocked"],
        "variant_count": len(summaries),
        "stable_with_updates": stable_with_updates,
        "diagnostic_degradation_detected": degraded,
        "blocker_reasons": sorted(set(blockers)),
        "metric_namespace": "diagnostic_state_delta_not_paper_performance",
        "diagnostic_only": True,
        "formal_go2_velocity_prior": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    variant_summaries = {
        "stage": "N7B4_literature_informed_contact_velocity",
        "variants": summaries,
        "runs": runs,
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    _write_json(out / "N7B4_DIAGNOSTIC_ACTIVATION_REPORT.json", report)
    _write_json(out / "N7B4_DIAGNOSTIC_VARIANT_SUMMARIES.json", variant_summaries)
    return report, variant_summaries


def load_n7b4_variant_summaries(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
