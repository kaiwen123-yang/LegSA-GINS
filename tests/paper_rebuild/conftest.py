from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_ablation import load_ablation_catalog
from legsa_gins.paper_rebuild.clean2_case_provider import (
    _read_dual_provider,
    _read_extended_gnss,
    align_gnss_with_dual_provider,
)
from legsa_gins.paper_rebuild.clean2_classic_cases import apply_classic_case, load_classic_case_catalog


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def ablation_catalog(repo_root: Path):
    return load_ablation_catalog(repo_root / "configs/paper_rebuild/clean2_ablation_2pow4.yaml")


@pytest.fixture(scope="session")
def classic_catalog(repo_root: Path):
    return load_classic_case_catalog(repo_root / "configs/paper_rebuild/clean2_classic18_active_mapping.yaml")


@pytest.fixture
def clean2_base_files(tmp_path: Path):
    gnss = tmp_path / "base.extended"
    dual = tmp_path / "dual.csv"
    gnss_lines = []
    dual_rows = []
    for index in range(40):
        time_value = index * 0.5
        heading = -20.0 + index * 0.2
        radians = math.radians(heading)
        north = 0.35 * math.cos(radians)
        east = 0.35 * math.sin(radians)
        yaw = (heading + 90.0) % 360.0
        fields = [
            f"{time_value:.6f}", "39.0", "116.0", "42.0", "0.1", "0.1", "0.2",
            "1.0", "2.0", "3.0", "0.05", "0.05", "0.05", f"{yaw:.6f}", "1.500000",
            "1", "1", "1",
        ]
        gnss_lines.append(" ".join(fields))
        dual_rows.append(
            {
                "time": f"{time_value:.6f}",
                "baseline_n_m": f"{north:.12f}",
                "baseline_e_m": f"{east:.12f}",
                "baseline_d_m": "0.000000000000",
                "baseline_length_m": "0.350000000000",
                "body_yaw_ned_deg": f"{yaw:.9f}",
                "yaw_std_deg": "1.500000",
                "physical_in_band": "True",
                "gnss_order": "GNSS2-GNSS1",
                "lateral_to_body_offset_deg": "90.0",
                "wrap_safe_residual": "True",
                "trace_sign_or_offset_selection": "False",
            }
        )
    gnss.write_text("\n".join(gnss_lines) + "\n", encoding="utf-8")
    with dual.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dual_rows[0]))
        writer.writeheader()
        writer.writerows(dual_rows)
    rows, payload = _read_extended_gnss(gnss)
    epochs = align_gnss_with_dual_provider(rows, _read_dual_provider(dual))
    return {"gnss": gnss, "dual": dual, "rows": rows, "payload": payload, "epochs": epochs}


@pytest.fixture
def apply_case(classic_catalog, clean2_base_files):
    def factory(case_id_or_code: str):
        return apply_classic_case(clean2_base_files["epochs"], classic_catalog.case(case_id_or_code))

    return factory
