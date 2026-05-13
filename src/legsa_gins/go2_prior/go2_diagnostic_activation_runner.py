"""Run N7B3 diagnostic-only Go2 velocity/yaw-rate EKF activation variants.

中文说明：runner 只创建 runtime-only config 并调用 C++ demo；variant 结果只做
diagnostic state delta，不写 paper performance claim。
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config


VARIANT_IDS = [
    "baseline_no_go2_velocity",
    "go2_velocity_direct_weak_diagnostic",
    "go2_velocity_frame_best_weak_diagnostic",
    "go2_velocity_contact_gated_diagnostic",
    "go2_standing_zero_velocity_diagnostic",
    "go2_yaw_rate_diagnostic",
]


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_eval_nav(path: str | Path) -> list[dict[str, float]]:
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, float]] = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({key: _f(value) for key, value in row.items()})
    return rows


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _nearest(rows: list[dict[str, float]], time_value: float, start: int) -> tuple[dict[str, float] | None, int]:
    if not rows:
        return None, start
    index = max(0, min(start, len(rows) - 1))
    while index + 1 < len(rows) and abs(rows[index + 1].get("time", 0.0) - time_value) <= abs(
        rows[index].get("time", 0.0) - time_value
    ):
        index += 1
    row = rows[index]
    return (row if abs(row.get("time", 0.0) - time_value) <= 0.01 else None), index


def _state_delta_summary(variant_dir: Path, baseline_rows: list[dict[str, float]]) -> dict[str, Any]:
    rows = _read_eval_nav(variant_dir / "EVAL_NAV.csv")
    if not rows or not baseline_rows:
        return {"count": 0, "evidence_status": "eval_nav_missing"}
    index = 0
    pos_proxy: list[float] = []
    vel_delta: list[float] = []
    yaw_delta: list[float] = []
    for row in rows:
        base, index = _nearest(baseline_rows, row.get("time", math.nan), index)
        if not base:
            continue
        # Position is intentionally a state-delta proxy, not a truth error.
        dlat = (row.get("lat_deg", 0.0) - base.get("lat_deg", 0.0)) * 111_000.0
        dlon = (row.get("lon_deg", 0.0) - base.get("lon_deg", 0.0)) * 111_000.0
        dh = row.get("height_m", 0.0) - base.get("height_m", 0.0)
        pos_proxy.append(math.sqrt(dlat * dlat + dlon * dlon + dh * dh))
        dv = [
            row.get(axis, 0.0) - base.get(axis, 0.0)
            for axis in ("vn", "ve", "vd")
        ]
        vel_delta.append(math.sqrt(sum(value * value for value in dv)))
        dyaw = row.get("yaw_deg", 0.0) - base.get("yaw_deg", 0.0)
        while dyaw > 180.0:
            dyaw -= 360.0
        while dyaw <= -180.0:
            dyaw += 360.0
        yaw_delta.append(abs(dyaw))
    return {
        "count": len(vel_delta),
        "state_delta_not_truth_error": True,
        "position_delta_proxy_mean_m": sum(pos_proxy) / len(pos_proxy) if pos_proxy else None,
        "velocity_delta_mean_mps": sum(vel_delta) / len(vel_delta) if vel_delta else None,
        "velocity_delta_p95_mps": sorted(vel_delta)[int(0.95 * (len(vel_delta) - 1))] if vel_delta else None,
        "yaw_delta_mean_deg": sum(yaw_delta) / len(yaw_delta) if yaw_delta else None,
        "evidence_status": "state_delta_to_baseline_only",
    }


def _append_config(
    *,
    base_config: Path,
    output_path: Path,
    variant_id: str,
    raw_doppler_factor_path: str | Path | None,
    velocity_prior_path: str | Path | None = None,
    yaw_rate_prior_path: str | Path | None = None,
) -> Path:
    content = base_config.read_text(encoding="utf-8", errors="ignore")
    lines = [
        "",
        "# N7B3 runtime-only diagnostic Go2 velocity/contact activation config.",
        "# 中文说明：Go2 velocity/contact/yaw-rate 仅 diagnostic-only；不读取 trace/final_v23 output，不做正式 prior claim。",
        f"ablation_variant: {variant_id}",
        "enable_receiver_velocity_update: true",
        "receiver_velocity_stress_mode: none",
        "receiver_velocity_std_scale: 1.0",
        "diagnostic_only: true",
        "diagnostic_stress_only: false",
        "go2_diagnostic_prior_only: true",
        "proposed_factor_claim: false",
        "paper_performance_claim: false",
        "no_outperform_final_v23_claim: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "output_only_correction: false",
        "bad_epoch_deletion_for_metric: false",
        "fgo: false",
        "enable_source_aware_weighting: true",
        "source_aware_policy_version: n6b_conservative_innovation_covariance",
        "source_aware_mode: lsim_oim",
        "source_aware_use_innovation_covariance: true",
        "source_aware_trace_enabled: true",
        "source_aware_no_R_shrink: true",
        "source_aware_global_cap: 25.0",
        "source_aware_max_R_scale: 25.0",
    ]
    if raw_doppler_factor_path:
        lines.extend(
            [
                "enable_raw_doppler: true",
                f'raw_doppler_factor_path: "{raw_doppler_factor_path}"',
                "raw_doppler_factor_source: RTKLIB_DOPPLER_PROVIDER",
                "raw_doppler_time_tolerance_sec: 0.08",
                "raw_doppler_min_sat: 5",
                "raw_doppler_residual_gate_mps: 3.0",
                "raw_doppler_R_scale: 1.0",
                "raw_doppler_mode: doppler_ls_velocity",
            ]
        )
    else:
        lines.append("enable_raw_doppler: false")
    if velocity_prior_path:
        lines.extend(
            [
                "enable_go2_velocity_prior_diagnostic: true",
                f'go2_velocity_prior_diagnostic_path: "{velocity_prior_path}"',
                "go2_velocity_prior_std_scale: 1.0",
            ]
        )
    else:
        lines.extend(
            [
                "enable_go2_velocity_prior_diagnostic: false",
                'go2_velocity_prior_diagnostic_path: ""',
                "go2_velocity_prior_std_scale: 1.0",
            ]
        )
    if yaw_rate_prior_path:
        lines.extend(
            [
                "enable_go2_yaw_rate_prior_diagnostic: true",
                f'go2_yaw_rate_prior_diagnostic_path: "{yaw_rate_prior_path}"',
            ]
        )
    else:
        lines.extend(
            [
                "enable_go2_yaw_rate_prior_diagnostic: false",
                'go2_yaw_rate_prior_diagnostic_path: ""',
            ]
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content + "\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _run_variant(exe: str | Path, config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(exe), "--config", str(config_path), "--output-dir", str(out)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    return {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "manifest": _read_json(out / "RUN_MANIFEST.json"),
    }


def run_n7b3_diagnostic_activation_variants(
    *,
    clean_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    raw_doppler_factor_path: str | Path | None,
    velocity_prior_paths: dict[str, Path],
    yaw_rate_prior_path: Path | None,
    allow_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_config = find_clean_config(clean_root)
    runs: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    blockers: list[str] = []
    if base_config is None:
        blockers.append("clean_replay_config_missing")
    if not Path(exe).exists():
        blockers.append("cpp_demo_executable_missing")
    if not allow_run:
        blockers.append("allow_run_false")
    variant_to_prior = {
        "baseline_no_go2_velocity": None,
        "go2_velocity_direct_weak_diagnostic": velocity_prior_paths.get("direct"),
        "go2_velocity_frame_best_weak_diagnostic": velocity_prior_paths.get("weak"),
        "go2_velocity_contact_gated_diagnostic": velocity_prior_paths.get("contact_gated"),
        "go2_standing_zero_velocity_diagnostic": velocity_prior_paths.get("standing_zero"),
        "go2_yaw_rate_diagnostic": None,
    }
    baseline_rows: list[dict[str, float]] = []
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
            yaw_prior = yaw_rate_prior_path if variant_id == "go2_yaw_rate_diagnostic" else None
            config = _append_config(
                base_config=base_config,
                output_path=out / "runtime_configs" / f"{variant_id}.yaml",
                variant_id=variant_id,
                raw_doppler_factor_path=raw_doppler_factor_path,
                velocity_prior_path=prior,
                yaw_rate_prior_path=yaw_prior,
            )
            variant_dir = out / "variants" / variant_id
            run = _run_variant(exe, config, variant_dir)
            run["variant_id"] = variant_id
            runs.append(run)
            if variant_id == "baseline_no_go2_velocity":
                baseline_rows = _read_eval_nav(variant_dir / "EVAL_NAV.csv")
            manifest = run.get("manifest", {})
            state_delta = _state_delta_summary(variant_dir, baseline_rows) if variant_id != "baseline_no_go2_velocity" else {
                "count": len(baseline_rows),
                "evidence_status": "baseline",
                "state_delta_not_truth_error": True,
            }
            velocity_updates = int(manifest.get("go2_velocity_prior_update_count", 0) or 0)
            yaw_updates = int(manifest.get("go2_yaw_rate_prior_update_count", 0) or 0)
            run_status = "stable_no_reference_metric" if run["returncode"] == 0 else "diagnostic_activation_failed"
            label = "baseline"
            if variant_id != "baseline_no_go2_velocity":
                if run["returncode"] != 0:
                    label = "diagnostic_degradation"
                elif velocity_updates == 0 and yaw_updates == 0:
                    label = "diagnostic_no_effect_no_updates"
                else:
                    label = "diagnostic_stable_state_delta_only"
            summaries.append(
                {
                    "variant_id": variant_id,
                    "run_status": run_status,
                    "diagnostic_label": label,
                    "returncode": run["returncode"],
                    "manifest_path": str(variant_dir / "RUN_MANIFEST.json") if (variant_dir / "RUN_MANIFEST.json").exists() else "",
                    "go2_velocity_prior_diagnostic_enabled": bool(manifest.get("go2_velocity_prior_diagnostic_enabled", False)),
                    "go2_velocity_prior_update_count": velocity_updates,
                    "go2_velocity_prior_reject_count": int(manifest.get("go2_velocity_prior_reject_count", 0) or 0),
                    "go2_yaw_rate_prior_diagnostic_enabled": bool(manifest.get("go2_yaw_rate_prior_diagnostic_enabled", False)),
                    "go2_yaw_rate_prior_update_count": yaw_updates,
                    "go2_yaw_rate_activation_status": manifest.get("go2_yaw_rate_prior_activation_status", ""),
                    "measurement_update_count": int(manifest.get("measurement_update_count", 0) or 0),
                    "raw_doppler_update_count": int(manifest.get("raw_doppler_update_count", 0) or 0),
                    "state_delta_summary": state_delta,
                    "diagnostic_only": True,
                    "paper_performance_claim": False,
                    "go2_velocity_truth_claim": False,
                }
            )
    degraded = any(row.get("diagnostic_label") == "diagnostic_degradation" for row in summaries)
    stable_with_updates = [
        row["variant_id"]
        for row in summaries
        if row.get("diagnostic_label") == "diagnostic_stable_state_delta_only"
    ]
    activation_report = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "variants_requested": VARIANT_IDS,
        "variants_run": [row.get("variant_id") for row in summaries if row.get("run_status") != "blocked"],
        "variant_count": len(summaries),
        "stable_with_updates": stable_with_updates,
        "diagnostic_degradation_detected": degraded,
        "blocker_reasons": sorted(set(blockers)),
        "metric_namespace": "diagnostic_state_delta_not_paper_performance",
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }
    variant_summaries = {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "variants": summaries,
        "runs": runs,
        "diagnostic_only": True,
        "paper_performance_claim": False,
    }
    _write_json(out / "N7B3_DIAGNOSTIC_ACTIVATION_REPORT.json", activation_report)
    _write_json(out / "N7B3_DIAGNOSTIC_VARIANT_SUMMARIES.json", variant_summaries)
    return activation_report, variant_summaries
