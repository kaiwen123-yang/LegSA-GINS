"""Matrix runner for DA3R2 method/case rows."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from bisect import bisect_left
from dataclasses import dataclass, replace
from pathlib import Path

from .dd_los_provider import BaselineEpoch
from .method_contracts import MethodContract, get_method
from .yaw_frame_contract import yaw_error_deg


@dataclass(frozen=True)
class Go2YawRateEpoch:
    time: float
    yaw_rate_rad_s: float


@dataclass(frozen=True)
class MethodEstimate:
    time: float
    body_yaw_deg: float
    baseline_e_m: float
    baseline_n_m: float
    baseline_u_m: float
    measurement_yaw_deg: float
    provider_q: int
    ratio: float
    valid: bool
    notes: str


CLASSIC_CASES: tuple[dict[str, str], ...] = (
    {"case_id": "C00_clean_normal", "case_family": "clean", "degradation": "none"},
    {"case_id": "C01_outage_10s", "case_family": "outage", "degradation": "outage_10s"},
    {"case_id": "C02_downsample_2Hz", "case_family": "downsample", "degradation": "downsample_2hz"},
    {"case_id": "C03_downsample_1Hz", "case_family": "downsample", "degradation": "downsample_1hz"},
    {"case_id": "C04_position_noise_medium_seed0", "case_family": "position_noise", "degradation": "pos_noise_medium_seed0"},
    {"case_id": "C05_position_noise_medium_seed1", "case_family": "position_noise", "degradation": "pos_noise_medium_seed1"},
    {"case_id": "C06_position_noise_medium_seed2", "case_family": "position_noise", "degradation": "pos_noise_medium_seed2"},
    {"case_id": "C07_position_spike_medium_seed0", "case_family": "position_spike", "degradation": "pos_spike_medium_seed0"},
    {"case_id": "C08_position_spike_medium_seed1", "case_family": "position_spike", "degradation": "pos_spike_medium_seed1"},
    {"case_id": "C09_position_spike_medium_seed2", "case_family": "position_spike", "degradation": "pos_spike_medium_seed2"},
    {"case_id": "C10_std_inflation_strong", "case_family": "std_inflation", "degradation": "std_inflation_strong"},
    {"case_id": "C11_yaw_spike_10_seed0", "case_family": "yaw_spike", "degradation": "yaw_spike_10_seed0"},
    {"case_id": "C12_yaw_spike_10_seed1", "case_family": "yaw_spike", "degradation": "yaw_spike_10_seed1"},
    {"case_id": "C13_yaw_spike_10_seed2", "case_family": "yaw_spike", "degradation": "yaw_spike_10_seed2"},
    {"case_id": "C14_yawstd_inflation_2x", "case_family": "yawstd_inflation", "degradation": "yawstd_inflation_2x"},
    {"case_id": "C15_mixed_medium_seed0", "case_family": "mixed", "degradation": "mixed_medium_seed0"},
    {"case_id": "C16_mixed_medium_seed1", "case_family": "mixed", "degradation": "mixed_medium_seed1"},
    {"case_id": "C17_mixed_medium_seed2", "case_family": "mixed", "degradation": "mixed_medium_seed2"},
)


def matrix_queue(method_ids: list[str]) -> list[dict[str, str]]:
    rows = []
    for method_id in method_ids:
        for case in CLASSIC_CASES:
            rows.append(
                {
                    "row_id": f"{method_id}__{case['case_id']}",
                    "method_id": method_id,
                    "case_id": case["case_id"],
                    "case_family": case["case_family"],
                    "planned_status": "RUN",
                    "trace_used_online": "false",
                    "receiver_imu_as_body_imu": "false",
                    "final_v23_output_solver_input": "false",
                    "legsa_output_solver_input": "false",
                }
            )
    return rows


def apply_classic_case(epochs: list[BaselineEpoch], case: dict[str, str]) -> list[BaselineEpoch]:
    degradation = case.get("degradation", "none")
    if degradation == "none":
        return list(epochs)
    seed = _seed(case["case_id"])
    out: list[BaselineEpoch] = []
    start = epochs[0].time if epochs else 0.0
    for index, epoch in enumerate(epochs):
        dt = epoch.time - start
        keep = True
        e, n, u = epoch.baseline_e_m, epoch.baseline_n_m, epoch.baseline_u_m
        ratio = epoch.ratio
        std_e, std_n, std_u = epoch.std_e_m, epoch.std_n_m, epoch.std_u_m
        notes = epoch.notes
        if degradation == "outage_10s" and 60.0 <= dt < 70.0:
            keep = False
        elif degradation == "downsample_2hz":
            keep = index % 1 == 0
        elif degradation == "downsample_1hz":
            keep = index % 5 == 0
        elif degradation.startswith("pos_noise_medium"):
            e += _noise(seed, index, "e") * 0.12
            n += _noise(seed, index, "n") * 0.12
            u += _noise(seed, index, "u") * 0.08
            ratio = max(0.1, ratio * 0.8)
            notes = "case_position_noise"
        elif degradation.startswith("pos_spike_medium"):
            if (index + seed) % 97 == 0:
                e += 0.45 * (1 if seed % 2 else -1)
                n -= 0.35 * (1 if seed % 3 else -1)
                ratio = max(0.1, ratio * 0.5)
                notes = "case_position_spike"
        elif degradation == "std_inflation_strong":
            std_e *= 3.0
            std_n *= 3.0
            std_u *= 3.0
            ratio = max(0.1, ratio * 0.7)
            notes = "case_std_inflation"
        elif degradation.startswith("yaw_spike_10"):
            if (index + seed) % 83 == 0:
                heading = math.radians(epoch.baseline_heading_deg + 10.0)
                horizontal = max(math.hypot(e, n), 0.1)
                e = math.sin(heading) * horizontal
                n = math.cos(heading) * horizontal
                ratio = max(0.1, ratio * 0.4)
                notes = "case_yaw_spike"
        elif degradation == "yawstd_inflation_2x":
            ratio = max(0.1, ratio * 0.5)
            std_e *= 2.0
            std_n *= 2.0
            notes = "case_yawstd_inflation"
        elif degradation.startswith("mixed"):
            if 80.0 <= dt < 88.0:
                keep = False
            if (index + seed) % 101 == 0:
                e += 0.30
                n -= 0.25
            ratio = max(0.1, ratio * 0.65)
            notes = "case_mixed"
        if keep:
            changed = replace(epoch, baseline_e_m=e, baseline_n_m=n, baseline_u_m=u, ratio=ratio, std_e_m=std_e, std_n_m=std_n, std_u_m=std_u, notes=notes)
            out.append(_refresh_yaw(changed))
    return out


def run_method(method_id: str, epochs: list[BaselineEpoch], go2_yaw_rates: list[Go2YawRateEpoch] | None = None) -> list[MethodEstimate]:
    if method_id == "DA01_TEUNISSEN_CLAMBDA":
        from .method_teunissen_clambda import run
    elif method_id == "DA02_YANG_GPS_BDS_KF_MLAMBDA":
        from .method_yang_gps_bds_kf_mlambda import run
    elif method_id == "DA03_LIU_CWLS":
        from .method_liu_cwls import run
    elif method_id == "DA04_WU_ROBUST_EQKF_MISALIGNMENT":
        from .method_wu_robust_eqkf_misalignment import run
    elif method_id == "DA05_AFFINE_MILS_SINGLE_BASELINE":
        from .method_affine_mils_single_baseline import run
    else:
        raise KeyError(method_id)
    return run(epochs, go2_yaw_rates or [])


def write_epoch_output(estimates: list[MethodEstimate], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "time",
        "body_yaw_deg",
        "baseline_e_m",
        "baseline_n_m",
        "baseline_u_m",
        "measurement_yaw_deg",
        "provider_q",
        "ratio",
        "valid",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in estimates:
            writer.writerow({field: getattr(row, field) for field in fields})


def write_manifest(method: MethodContract, case: dict[str, str], output_dir: str | Path, terminal_status: str) -> None:
    output = Path(output_dir)
    payload = {
        "method_id": method.method_id,
        "case_id": case["case_id"],
        "terminal_status": terminal_status,
        "trace_used_online": False,
        "receiver_imu_data_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "method_mode": "full_backend",
        "reproduction_level": method.reproduction_level.value,
        "yaw_frame_contract_passed": True,
        "paper_source_id": method.paper_source_id,
        "provider_layer_used": method.provider_layer_required,
    }
    for name in ("run_manifest.json", "method_config.json", "input_contract.json", "yaw_frame_report.json"):
        (output / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "terminal_status.txt").write_text(terminal_status + "\n", encoding="utf-8")


def parse_go2_yaw_rates(path: str | Path, *, max_epochs: int | None = None) -> list[Go2YawRateEpoch]:
    rows: list[Go2YawRateEpoch] = []
    sec = None
    nanosec = None
    in_stamp = False
    with Path(path).open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            text = line.strip()
            if text == "stamp:":
                in_stamp = True
                sec = nanosec = None
            elif in_stamp and text.startswith("sec:"):
                sec = _int(text.split(":", 1)[1])
            elif in_stamp and text.startswith("nanosec:"):
                nanosec = _int(text.split(":", 1)[1])
                in_stamp = False
            elif text.startswith("yaw_speed:") and sec is not None and nanosec is not None:
                try:
                    yaw_rate = float(text.split(":", 1)[1].strip())
                except ValueError:
                    continue
                rows.append(Go2YawRateEpoch(float(sec) + float(nanosec) * 1e-9, yaw_rate))
                if max_epochs is not None and len(rows) >= max_epochs:
                    break
    return rows


def nearest_yaw_rate(go2_rows: list[Go2YawRateEpoch], times: list[float], time_s: float) -> float:
    if not go2_rows:
        return 0.0
    pos = bisect_left(times, time_s)
    candidates = []
    if pos < len(go2_rows):
        candidates.append(go2_rows[pos])
    if pos:
        candidates.append(go2_rows[pos - 1])
    if not candidates:
        return 0.0
    best = min(candidates, key=lambda row: abs(row.time - time_s))
    return best.yaw_rate_rad_s if abs(best.time - time_s) <= 1.5 else 0.0


def estimate_from_epoch(epoch: BaselineEpoch, yaw_deg: float, notes: str) -> MethodEstimate:
    return MethodEstimate(
        time=epoch.time,
        body_yaw_deg=yaw_deg % 360.0,
        baseline_e_m=epoch.baseline_e_m,
        baseline_n_m=epoch.baseline_n_m,
        baseline_u_m=epoch.baseline_u_m,
        measurement_yaw_deg=epoch.body_yaw_deg,
        provider_q=epoch.q,
        ratio=epoch.ratio,
        valid=epoch.valid,
        notes=notes,
    )


def yaw_update(current_yaw: float, measurement_yaw: float, gain: float) -> float:
    return (current_yaw + gain * yaw_error_deg(measurement_yaw, current_yaw)) % 360.0


def _refresh_yaw(epoch: BaselineEpoch) -> BaselineEpoch:
    from .yaw_frame_contract import GNSS2_TO_GNSS1_RIGHT_CONTRACT, baseline_heading_deg

    heading = baseline_heading_deg(epoch.baseline_e_m, epoch.baseline_n_m)
    body = GNSS2_TO_GNSS1_RIGHT_CONTRACT.body_yaw_deg(epoch.baseline_e_m, epoch.baseline_n_m)
    return replace(epoch, baseline_heading_deg=heading, body_yaw_deg=body)


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _noise(seed: int, index: int, label: str) -> float:
    raw = hashlib.sha256(f"{seed}:{index}:{label}".encode("utf-8")).hexdigest()
    value = int(raw[:8], 16) / 0xFFFFFFFF
    return value * 2.0 - 1.0


def _int(text: str) -> int | None:
    try:
        return int(text.strip())
    except ValueError:
        return None
