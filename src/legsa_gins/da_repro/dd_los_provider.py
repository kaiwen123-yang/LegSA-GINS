"""DD/LOS backend evidence derived from RTKLIB relative carrier processing."""

from __future__ import annotations

import csv
import datetime as dt
import math
from dataclasses import dataclass, replace
from pathlib import Path

from .yaw_frame_contract import GNSS2_TO_GNSS1_RIGHT_CONTRACT, baseline_heading_deg


@dataclass(frozen=True)
class BaselineEpoch:
    time: float
    baseline_e_m: float
    baseline_n_m: float
    baseline_u_m: float
    q: int
    satellite_count: int
    std_e_m: float
    std_n_m: float
    std_u_m: float
    ratio: float
    baseline_heading_deg: float
    body_yaw_deg: float
    provider_status: str
    valid: bool = True
    notes: str = ""

    @property
    def baseline_length_m(self) -> float:
        return math.sqrt(self.baseline_e_m**2 + self.baseline_n_m**2 + self.baseline_u_m**2)


def parse_rtklib_moving_base_pos(path: str | Path) -> list[BaselineEpoch]:
    path = Path(path)
    epochs: list[BaselineEpoch] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(line for line in handle if not line.startswith("%"))
        for row in reader:
            if len(row) < 14:
                continue
            try:
                unix_time = _parse_time(row[0].strip())
                e = float(row[1])
                n = float(row[2])
                u = float(row[3])
                q = int(row[4])
                ns = int(row[5])
                sde = float(row[6])
                sdn = float(row[7])
                sdu = float(row[8])
                ratio = float(row[13])
            except (ValueError, IndexError):
                continue
            heading = baseline_heading_deg(e, n)
            body_yaw = GNSS2_TO_GNSS1_RIGHT_CONTRACT.body_yaw_deg(e, n)
            valid = q in {1, 2, 5} and ns >= 4 and math.isfinite(ratio)
            status = "fixed" if q == 1 else "float" if q == 2 else "single" if q == 5 else "invalid"
            epochs.append(BaselineEpoch(unix_time, e, n, u, q, ns, sde, sdn, sdu, ratio, heading, body_yaw, status, valid))
    return epochs


def provider_summary(epochs: list[BaselineEpoch]) -> dict[str, object]:
    fixed = [row for row in epochs if row.q == 1]
    usable = [row for row in epochs if row.valid]
    ratios = [row.ratio for row in usable if math.isfinite(row.ratio)]
    lengths = [row.baseline_length_m for row in usable]
    return {
        "rtklib_relative_epoch_count": len(epochs),
        "usable_epoch_count": len(usable),
        "fixed_epoch_count": len(fixed),
        "float_epoch_count": sum(1 for row in epochs if row.q == 2),
        "single_epoch_count": sum(1 for row in epochs if row.q == 5),
        "median_ratio": _median(ratios),
        "median_baseline_length_m": _median(lengths),
        "dd_los_ready": bool(usable),
        "ambiguity_evidence_ready": bool(fixed or ratios),
        "provider_layer_used": "raw_carrier_rinex_rtklib_dd_ambiguity",
        "status_yaw_used_as_solver_input": False,
    }


def with_body_yaw(epoch: BaselineEpoch, body_yaw_deg_value: float, note: str) -> BaselineEpoch:
    return replace(epoch, body_yaw_deg=body_yaw_deg_value, notes=note)


def _parse_time(text: str) -> float:
    value = dt.datetime.strptime(text, "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=dt.timezone.utc)
    return value.timestamp()


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return 0.5 * (clean[mid - 1] + clean[mid])
