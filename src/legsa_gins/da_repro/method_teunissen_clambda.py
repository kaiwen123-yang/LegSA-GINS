"""DA01 Teunissen C-LAMBDA method implementation boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import percentile, wrap360
from .yaw_frame_contract import body_yaw_from_lateral_baseline


METHOD_ID = "DA01_TEUNISSEN_CLAMBDA"
METHOD_NAME = "Teunissen C-LAMBDA short-baseline GNSS compass"
FULL_REPRODUCTION_LEVEL = "FAITHFUL_NON_OFFICIAL_ALGORITHM"
DIAGNOSTIC_REPRODUCTION_LEVEL = "DIAGNOSTIC_STATUS_BASELINE_ONLY"


@dataclass(frozen=True)
class ClassicCase:
    case_id: str
    case_family: str
    policy: str
    seed: int | None = None


CLASSIC_CASES: tuple[ClassicCase, ...] = (
    ClassicCase("C00_clean_normal", "clean", "none"),
    ClassicCase("C01_outage_10s", "outage", "outage_10s"),
    ClassicCase("C02_downsample_2Hz", "downsample", "downsample_2hz"),
    ClassicCase("C03_downsample_1Hz", "downsample", "downsample_1hz"),
    ClassicCase("C04_position_noise_medium_seed0", "position_noise", "position_noise_medium", 0),
    ClassicCase("C05_position_noise_medium_seed1", "position_noise", "position_noise_medium", 1),
    ClassicCase("C06_position_noise_medium_seed2", "position_noise", "position_noise_medium", 2),
    ClassicCase("C07_position_spike_medium_seed0", "position_spike", "position_spike_medium", 0),
    ClassicCase("C08_position_spike_medium_seed1", "position_spike", "position_spike_medium", 1),
    ClassicCase("C09_position_spike_medium_seed2", "position_spike", "position_spike_medium", 2),
    ClassicCase("C10_std_inflation_strong", "std_inflation", "std_inflation_strong"),
    ClassicCase("C11_yaw_spike_10_seed0", "yaw_spike", "yaw_spike_10_deg", 0),
    ClassicCase("C12_yaw_spike_10_seed1", "yaw_spike", "yaw_spike_10_deg", 1),
    ClassicCase("C13_yaw_spike_10_seed2", "yaw_spike", "yaw_spike_10_deg", 2),
    ClassicCase("C14_yawstd_inflation_2x", "yawstd_inflation", "yawstd_inflation_2x"),
    ClassicCase("C15_mixed_medium_seed0", "mixed", "mixed_medium", 0),
    ClassicCase("C16_mixed_medium_seed1", "mixed", "mixed_medium", 1),
    ClassicCase("C17_mixed_medium_seed2", "mixed", "mixed_medium", 2),
)


def classic_case_manifest() -> list[dict[str, Any]]:
    return [case.__dict__ for case in CLASSIC_CASES]


def full_backend_ready(provider_capability: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for key, reason in (
        ("raw_ubx_rebuild_pass", "ubx_rebuild_not_closed"),
        ("rinex_conversion_pass", "rinex_conversion_not_closed"),
        ("common_epoch_satellite_pass", "common_epoch_satellite_not_closed"),
        ("los_provider_pass", "los_provider_not_closed"),
        ("dd_design_matrix_pass", "dd_design_matrix_not_closed"),
        ("ambiguity_provider_pass", "ambiguity_provider_not_closed"),
        ("physical_baseline_pass", "physical_baseline_not_closed"),
    ):
        if not provider_capability.get(key, False):
            blockers.append(reason)
    return not blockers, blockers


def blocked_full_backend_result(case_id: str, provider_capability: dict[str, Any]) -> dict[str, Any]:
    ready, blockers = full_backend_ready(provider_capability)
    if ready:
        raise ValueError("full backend is ready; blocked_full_backend_result is not applicable")
    return {
        "method_id": METHOD_ID,
        "case_id": case_id,
        "method_mode": "full_backend",
        "terminal_status": "BLOCKED_WITH_PROOF",
        "reproduction_level": "BLOCKED_WITH_PROOF",
        "provider_layer_used": "raw_carrier_dd_los_ambiguity_attempt",
        "blocker_reasons": blockers,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
    }


def _copy_series(series: list[dict[str, float]]) -> list[dict[str, float]]:
    return [dict(row) for row in series]


def _rng(seed: int | None) -> np.random.Generator:
    return np.random.default_rng(0 if seed is None else int(seed))


def _apply_vector_noise(rows: list[dict[str, float]], seed: int | None, sigma_m: float) -> None:
    rng = _rng(seed)
    for row in rows:
        row["east_m"] += float(rng.normal(0.0, sigma_m))
        row["north_m"] += float(rng.normal(0.0, sigma_m))
        row["up_m"] += float(rng.normal(0.0, sigma_m * 0.5))
        _refresh_geometry(row)


def _refresh_geometry(row: dict[str, float]) -> None:
    row["baseline_length_m"] = math.sqrt(row["east_m"] ** 2 + row["north_m"] ** 2 + row["up_m"] ** 2)
    row["baseline_heading_deg"] = wrap360(math.degrees(math.atan2(row["east_m"], row["north_m"])))


def _apply_spikes(rows: list[dict[str, float]], seed: int | None, magnitude_m: float, fraction: float = 0.05) -> None:
    if not rows:
        return
    rng = _rng(seed)
    count = max(1, int(len(rows) * fraction))
    for index in rng.choice(len(rows), size=count, replace=False):
        row = rows[int(index)]
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        row["east_m"] += magnitude_m * math.cos(angle)
        row["north_m"] += magnitude_m * math.sin(angle)
        _refresh_geometry(row)


def _apply_yaw_spikes(rows: list[dict[str, float]], seed: int | None, magnitude_deg: float, fraction: float = 0.05) -> set[int]:
    if not rows:
        return set()
    rng = _rng(seed)
    count = max(1, int(len(rows) * fraction))
    indices = {int(index) for index in rng.choice(len(rows), size=count, replace=False)}
    for index in indices:
        sign = -1.0 if rng.random() < 0.5 else 1.0
        rows[index]["diagnostic_yaw_offset_deg"] = sign * magnitude_deg
    return indices


def apply_case_policy(series: list[dict[str, float]], case: ClassicCase) -> tuple[list[dict[str, float]], dict[str, Any]]:
    rows = _copy_series(series)
    policy_report: dict[str, Any] = {"case_id": case.case_id, "policy": case.policy, "seed": case.seed, "input_rows": len(rows)}
    if case.policy == "outage_10s" and rows:
        midpoint = rows[len(rows) // 2]["time"]
        rows = [row for row in rows if not (midpoint <= row["time"] < midpoint + 10.0)]
        policy_report["source_measurement_withheld_rows"] = policy_report["input_rows"] - len(rows)
    elif case.policy == "downsample_2hz":
        # BY2 status is already about 1 Hz, so 2 Hz keeps all available samples.
        policy_report["downsample_note"] = "status cadence already <=2Hz; kept all rows"
    elif case.policy == "downsample_1hz":
        kept: list[dict[str, float]] = []
        last_time: float | None = None
        for row in rows:
            if last_time is None or row["time"] - last_time >= 0.95:
                kept.append(row)
                last_time = row["time"]
        rows = kept
        policy_report["source_measurement_withheld_rows"] = policy_report["input_rows"] - len(rows)
    elif case.policy == "position_noise_medium":
        _apply_vector_noise(rows, case.seed, sigma_m=0.05)
    elif case.policy == "position_spike_medium":
        _apply_spikes(rows, case.seed, magnitude_m=0.25)
    elif case.policy == "std_inflation_strong":
        policy_report["diagnostic_std_scale"] = 4.0
    elif case.policy == "yaw_spike_10_deg":
        indices = _apply_yaw_spikes(rows, case.seed, magnitude_deg=10.0)
        policy_report["yaw_spike_rows"] = len(indices)
    elif case.policy == "yawstd_inflation_2x":
        policy_report["diagnostic_yaw_std_scale"] = 2.0
    elif case.policy == "mixed_medium":
        _apply_vector_noise(rows, case.seed, sigma_m=0.03)
        _apply_spikes(rows, case.seed, magnitude_m=0.15, fraction=0.03)
        indices = _apply_yaw_spikes(rows, case.seed, magnitude_deg=6.0, fraction=0.03)
        policy_report["yaw_spike_rows"] = len(indices)
    policy_report["output_rows"] = len(rows)
    policy_report["epoch_deleted_for_metric"] = False
    return rows, policy_report


def run_status_diagnostic_case(
    status_series: list[dict[str, float]],
    case: ClassicCase,
    *,
    yaw_offset_deg: float = 90.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, policy = apply_case_policy(status_series, case)
    output_rows: list[dict[str, Any]] = []
    lengths: list[float] = []
    for row in rows:
        body_yaw = body_yaw_from_lateral_baseline(row["baseline_heading_deg"], offset_deg=yaw_offset_deg)
        body_yaw = wrap360(body_yaw + float(row.get("diagnostic_yaw_offset_deg", 0.0)))
        lengths.append(row["baseline_length_m"])
        output_rows.append(
            {
                "timestamp": row["time"],
                "method_id": METHOD_ID,
                "method_mode": "status_diagnostic",
                "case_id": case.case_id,
                "baseline_east_m": row["east_m"],
                "baseline_north_m": row["north_m"],
                "baseline_up_m": row["up_m"],
                "baseline_length_m": row["baseline_length_m"],
                "baseline_heading_deg": row["baseline_heading_deg"],
                "body_yaw_deg": body_yaw,
                "status_source": "gnss1_status_gnss2_status_absolute_position_difference",
                "trace_used_online": False,
                "full_backend_claim": False,
            }
        )
    manifest = {
        "method_id": METHOD_ID,
        "case_id": case.case_id,
        "method_mode": "status_diagnostic",
        "terminal_status": "COMPLETED_EVALUABLE_DIAGNOSTIC_FALLBACK" if output_rows else "FAILED_RUNTIME_WITH_LOG",
        "reproduction_level": DIAGNOSTIC_REPRODUCTION_LEVEL,
        "provider_layer_used": "gnss1_status_gnss2_status_absolute_position_difference",
        "row_count": len(output_rows),
        "median_baseline_length_m": percentile(lengths, 0.50),
        "yaw_frame_contract_passed": True,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "status_yaw_as_full_backend": False,
        "policy_report": policy,
    }
    return output_rows, manifest
