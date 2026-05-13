"""Run N7B5 frame-sensitivity diagnostic activation variants.

中文说明：N7B5 只复用 C++ diagnostic Go2 velocity prior path；horizontal-only
variant 的 vertical component 通过 prior CSV std_vd=999 关闭，不启用正式 prior。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .go2_diagnostic_activation_runner import _append_config, _read_eval_nav, _run_variant, _state_delta_summary, _write_json
from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config


VARIANT_IDS = [
    "baseline_no_go2_velocity",
    "best_frame_full_3d_diagnostic",
    "yaw_only_full_3d_diagnostic",
    "best_frame_horizontal_only_diagnostic",
    "yaw_only_horizontal_only_diagnostic",
    "probability_weighted_horizontal_only_diagnostic",
    "contact_weighted_horizontal_only_diagnostic",
]


def _manifest_int(manifest: dict[str, Any], key: str) -> int:
    try:
        return int(manifest.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _horizontal_manifest_fields(variant_id: str, manifest: dict[str, Any], updates: int) -> tuple[bool, int, bool]:
    horizontal_variant = "horizontal_only" in variant_id
    enabled = bool(manifest.get("go2_horizontal_velocity_prior_diagnostic_enabled", False))
    vertical_disabled = bool(manifest.get("go2_horizontal_velocity_prior_vertical_disabled", False))
    horizontal_updates = _manifest_int(manifest, "go2_horizontal_velocity_prior_update_count")
    if horizontal_variant and updates > 0:
        enabled = True if "go2_horizontal_velocity_prior_diagnostic_enabled" not in manifest else enabled
        vertical_disabled = True if "go2_horizontal_velocity_prior_vertical_disabled" not in manifest else vertical_disabled
        horizontal_updates = horizontal_updates or updates
    return enabled, horizontal_updates, vertical_disabled


def run_n7b5_frame_sensitivity_variants(
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
        "best_frame_full_3d_diagnostic": prior_paths.get("best_frame_full_3d"),
        "yaw_only_full_3d_diagnostic": prior_paths.get("yaw_only_full_3d"),
        "best_frame_horizontal_only_diagnostic": prior_paths.get("best_frame_horizontal_only"),
        "yaw_only_horizontal_only_diagnostic": prior_paths.get("yaw_only_horizontal_only"),
        "probability_weighted_horizontal_only_diagnostic": prior_paths.get("probability_weighted_horizontal_only"),
        "contact_weighted_horizontal_only_diagnostic": prior_paths.get("contact_weighted_horizontal_only"),
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
            updates = _manifest_int(manifest, "go2_velocity_prior_update_count")
            rejects = _manifest_int(manifest, "go2_velocity_prior_reject_count")
            horizontal_enabled, horizontal_updates, vertical_disabled = _horizontal_manifest_fields(variant_id, manifest, updates)
            state_delta = (
                {"count": len(baseline_rows), "evidence_status": "baseline", "state_delta_not_truth_error": True}
                if variant_id == "baseline_no_go2_velocity"
                else _state_delta_summary(variant_dir, baseline_rows)
            )
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
                    "go2_horizontal_velocity_prior_diagnostic_enabled": horizontal_enabled,
                    "go2_horizontal_velocity_prior_update_count": horizontal_updates,
                    "go2_horizontal_velocity_prior_vertical_disabled": vertical_disabled,
                    "measurement_update_count": _manifest_int(manifest, "measurement_update_count"),
                    "raw_doppler_update_count": _manifest_int(manifest, "raw_doppler_update_count"),
                    "state_delta_summary": state_delta,
                    "diagnostic_only": True,
                    "paper_performance_claim": False,
                    "go2_velocity_truth_claim": False,
                    "formal_go2_velocity_prior": False,
                    "formal_go2_yaw_prior": False,
                    "fgo": False,
                }
            )
    degraded = any(row.get("diagnostic_label") == "diagnostic_degradation" for row in summaries)
    stable_with_updates = [
        str(row.get("variant_id"))
        for row in summaries
        if row.get("diagnostic_label") == "diagnostic_stable_state_delta_only"
    ]
    stable_horizontal = [
        str(row.get("variant_id"))
        for row in summaries
        if row.get("diagnostic_label") == "diagnostic_stable_state_delta_only"
        and row.get("go2_horizontal_velocity_prior_update_count", 0)
    ]
    total_updates = sum(int(row.get("go2_velocity_prior_update_count", 0) or 0) for row in summaries)
    report = {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "variants_requested": VARIANT_IDS,
        "variants_run": [row.get("variant_id") for row in summaries if row.get("run_status") != "blocked"],
        "variant_count": len(summaries),
        "stable_with_updates": stable_with_updates,
        "stable_horizontal_variants": stable_horizontal,
        "total_go2_velocity_prior_update_count": total_updates,
        "diagnostic_degradation_detected": degraded,
        "blocker_reasons": sorted(set(blockers)),
        "metric_namespace": "diagnostic_state_delta_not_paper_performance",
        "diagnostic_only": True,
        "formal_go2_velocity_prior": False,
        "formal_go2_yaw_prior": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_frame_tuning": False,
        "final_v23_frame_tuning": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    variant_summaries = {
        "stage": "N7B5_go2_velocity_frame_horizontal_diagnostic",
        "variants": summaries,
        "runs": runs,
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    _write_json(out / "N7B5_FRAME_SENSITIVITY_REPORT.json", report)
    _write_json(out / "N7B5_DIAGNOSTIC_VARIANT_SUMMARIES.json", variant_summaries)
    return report, variant_summaries


def load_n7b5_variant_summaries(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
