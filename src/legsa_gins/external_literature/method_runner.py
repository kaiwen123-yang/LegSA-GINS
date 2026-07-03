"""DA2R2 method dispatch and runtime writing helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .method_contracts import MethodContract
from .method_outputs import EpochOutput
from .provider_factory import ProviderEpoch


def run_method_contract(method: MethodContract, epochs: list[ProviderEpoch]) -> list[EpochOutput]:
    if method.method_id == "DA2R2_A_TWO_RECEIVER_IEKF":
        from .method_da2r2_a_two_receiver_iekf import run_method
    elif method.method_id == "DA2R2_B_DUAL_HEADING_AIDED_EKF":
        from .method_da2r2_b_dual_heading_aided_ekf import run_method
    elif method.method_id == "DA2R2_C_CONSTRAINED_BASELINE_WLS":
        from .method_da2r2_c_constrained_baseline_wls import run_method
    else:
        raise KeyError(method.method_id)
    return run_method(epochs)


def write_epoch_output(path: Path, outputs: list[EpochOutput]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time", "body_yaw_deg", "pos_n_m", "pos_e_m", "pos_u_m", "valid_measurement", "update_used"],
        )
        writer.writeheader()
        for item in outputs:
            writer.writerow(
                {
                    "time": f"{item.time:.9f}",
                    "body_yaw_deg": "" if item.yaw_deg is None else f"{item.yaw_deg:.9f}",
                    "pos_n_m": "" if item.pos_n_m is None else f"{item.pos_n_m:.9f}",
                    "pos_e_m": "" if item.pos_e_m is None else f"{item.pos_e_m:.9f}",
                    "pos_u_m": "" if item.pos_u_m is None else f"{item.pos_u_m:.9f}",
                    "valid_measurement": str(item.valid_measurement).lower(),
                    "update_used": item.update_used,
                }
            )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
