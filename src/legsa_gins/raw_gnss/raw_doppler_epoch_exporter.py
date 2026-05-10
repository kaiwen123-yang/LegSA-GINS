"""Export raw-Doppler-derived velocity factors.

中文说明：只导出 provider-backed RAWX Doppler 速度因子 CSV，不生成 solver 假输入。
"""

from __future__ import annotations

import csv
from pathlib import Path

from .raw_doppler_types import DopplerVelocitySolution


def write_velocity_factors(solutions: list[DopplerVelocitySolution], output_csv: str | Path) -> None:
    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time",
                "vn",
                "ve",
                "vd",
                "std_vn",
                "std_ve",
                "std_vd",
                "sat_count",
                "gdop_like",
                "provider_status",
            ],
        )
        writer.writeheader()
        for sol in solutions:
            writer.writerow(
                {
                    "time": f"{sol.time:.9f}",
                    "vn": f"{sol.vn:.9f}",
                    "ve": f"{sol.ve:.9f}",
                    "vd": f"{sol.vd:.9f}",
                    "std_vn": f"{sol.std_vn:.9f}",
                    "std_ve": f"{sol.std_ve:.9f}",
                    "std_vd": f"{sol.std_vd:.9f}",
                    "sat_count": sol.sat_count,
                    "gdop_like": f"{sol.gdop_like:.9f}",
                    "provider_status": sol.provider_status,
                }
            )
