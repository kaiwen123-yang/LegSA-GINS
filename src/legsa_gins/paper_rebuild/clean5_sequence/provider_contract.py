"""Frozen CLEAN5 provider parameters and input-derived time contracts."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from ..paths import load_yaml_mapping
from ..providers import status_time_sys


class SequenceProviderError(RuntimeError):
    """A sequence provider source, frozen parameter or output contract failed."""


def validate_frozen_parameters(contract, code_root):
    """Require complete BY2 source blocks; no per-sequence parameter defaults."""
    root = Path(code_root)
    parity = load_yaml_mapping(root / "configs/paper_rebuild/final_v23_parity_contract.yaml")
    protocol = load_yaml_mapping(root / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml")
    frozen = contract["frozen_parameters"]
    for name in ("imu_preprocessing", "dual_yaw_contract", "receiver_velocity_contract", "filter_contract"):
        if frozen.get(name) != parity[name]:
            raise SequenceProviderError(f"Frozen provider parameter block differs from BY2: {name}")
    for name in ("provider_generation", "solver_common"):
        if frozen.get(name) != protocol[name]:
            raise SequenceProviderError(f"Frozen provider parameter block differs from BY2: {name}")
    names = ("yaw_measurement_std_deg", "yaw_noise_injection_enabled", "yaw_noise_injection_std_deg", "yaw_noise_seed")
    if frozen.get("yaw_measurement") != {name: parity["profiles"]["clean_real_final_v23"][name] for name in names}:
        raise SequenceProviderError("Frozen clean-real yaw measurement/no-noise profile differs from BY2")
    return frozen["provider_generation"]


def validate_sequence_time(sequence, contract):
    """Validate R1 from the first position-valid source epoch, before providers."""
    with (sequence.fix_root / "gnss1-status.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        first = next((row for row in csv.DictReader(handle)
                      if str(row.get("pos_valid", "")).strip().lower() in {"true", "1"}), None)
    if first is None:
        raise SequenceProviderError("No position-valid GNSS1 status epoch for R1")
    timestamp = float(status_time_sys(first))
    if not math.isfinite(timestamp):
        raise SequenceProviderError("First position-valid GNSS1 sys_stamp is non-finite")
    base = math.floor(timestamp / 3600.0) * 3600.0
    midnight = math.floor(timestamp / 86400.0) * 86400.0
    offset = base - midnight
    expected = contract["time_contract"]
    values = {"base_time": base, "utc_day_midnight": midnight, "auxiliary_rebase_offset_seconds": offset}
    if any(float(expected[name]) != value for name, value in values.items()):
        raise SequenceProviderError(f"Source-derived R1/midnight/rebase differs from sequence contract: {values}")
    if sequence.dataset_id == "BY2" and base != 1772784000.0:
        raise SequenceProviderError("BY2 R1 does not reproduce the frozen 1772784000 origin")
    window = contract["window_contract"]
    start, end = float(window["t_start"]), float(window["t_end"])
    if not all(math.isfinite(t) for t in (start, end, offset)) or offset <= 0 or start >= end:
        raise SequenceProviderError("Sequence time/window contract is not finite and ordered")
    return {**values, "first_pos_valid_gnss1_sys_stamp": timestamp, "window": [start, end],
            "window_role": "frozen metadata only; providers retain their full input support",
            "time_or_window_search": False}
