"""Double-difference observation equations for DA01R1."""

from __future__ import annotations

from typing import Any


def single_difference_receiver2_minus_receiver1(sat: dict[str, Any]) -> dict[str, float]:
    return {
        "code_m": float(sat["pr2_m"]) - float(sat["pr1_m"]),
        "carrier_m": (float(sat["cp2_cycles"]) - float(sat["cp1_cycles"])) * float(sat["wavelength_m"]),
    }


def double_difference_against_pivot(sat: dict[str, Any], pivot: dict[str, Any]) -> dict[str, float]:
    sd_sat = single_difference_receiver2_minus_receiver1(sat)
    sd_pivot = single_difference_receiver2_minus_receiver1(pivot)
    return {
        "dd_code_m": sd_sat["code_m"] - sd_pivot["code_m"],
        "dd_carrier_m": sd_sat["carrier_m"] - sd_pivot["carrier_m"],
    }


def baseline_design_row_ecef(sat: dict[str, Any], pivot: dict[str, Any]) -> tuple[float, float, float]:
    """Return H row for DD ~= H * baseline_ecef + lambda * ambiguity."""

    return (
        float(pivot["los1_x"]) - float(sat["los1_x"]),
        float(pivot["los1_y"]) - float(sat["los1_y"]),
        float(pivot["los1_z"]) - float(sat["los1_z"]),
    )
