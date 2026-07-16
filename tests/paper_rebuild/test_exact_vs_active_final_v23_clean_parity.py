from __future__ import annotations

import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.final_v23_clean_parity import (
    FROZEN_TOLERANCES,
    FinalV23ParityError,
    active_runtime_config,
    compare_outputs,
    exact_runtime_yaml,
    parse_exact_modes,
)


def _write_outputs(root: Path) -> tuple[Path, Path, Path, Path]:
    exact_nav = root / "exact.nav"
    active_nav = root / "active.nav"
    exact_std = root / "exact.std"
    active_std = root / "active.std"
    exact_nav.write_text(
        "0 66.005 39.0 116.0 10.0 1.0 2.0 3.0 0.1 0.2 30.0\n"
        "0 66.007 39.0 116.0 10.0 1.0 2.0 3.0 0.1 0.2 30.0\n",
        encoding="utf-8",
    )
    active_nav.write_text(
        "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n"
        "66.005 39.0 116.0 10.001 1.0001 2.0 3.0 0.1005 0.1995 30.001\n"
        "66.007 39.0 116.0 10.001 1.0001 2.0 3.0 0.1005 0.1995 30.001\n",
        encoding="utf-8",
    )
    exact_std.write_text("66.005 " + " ".join(["1"] * 21) + "\n66.007 " + " ".join(["1"] * 21) + "\n", encoding="utf-8")
    active_std.write_text("row," + ",".join(f"s{i}" for i in range(21)) + "\n0," + ",".join(["1"] * 21) + "\n1," + ",".join(["1"] * 21) + "\n", encoding="utf-8")
    return exact_nav, active_nav, exact_std, active_std


def test_tolerances_are_frozen_before_runtime_outputs() -> None:
    assert FROZEN_TOLERANCES.timestamp_exact_abs_sec == 1.0e-9
    assert FROZEN_TOLERANCES.horizontal_rmse_m == 0.02
    assert FROZEN_TOLERANCES.velocity_3d_rmse_mps == 0.002
    assert FROZEN_TOLERANCES.yaw_rmse_deg == 0.002
    assert FROZEN_TOLERANCES.std_max_normalized_rmse == 0.01


def test_exact_and_active_writer_shapes_compare_pointwise(tmp_path: Path) -> None:
    exact_nav, active_nav, exact_std, active_std = _write_outputs(tmp_path)
    output = tmp_path / "pointwise.csv.gz"
    report = compare_outputs(exact_nav, active_nav, exact_std, active_std, output)
    assert report["row_count_exact"] is True
    assert report["timestamp_exact"] is True
    assert report["nav_aggregate_gate_passed"] is True
    assert report["velocity_and_std_gated"] is True
    assert output.is_file()


def test_active_exact_11_column_writer_shape_compares_pointwise(tmp_path: Path) -> None:
    exact_nav, active_nav, exact_std, active_std = _write_outputs(tmp_path)
    active_nav.write_text(exact_nav.read_text(encoding="utf-8"), encoding="utf-8")
    active_std.write_text(exact_std.read_text(encoding="utf-8"), encoding="utf-8")
    report = compare_outputs(
        exact_nav,
        active_nav,
        exact_std,
        active_std,
        tmp_path / "exact-writer.csv.gz",
    )
    assert report["row_count_exact"] is True
    assert report["timestamp_exact"] is True
    assert report["metrics"]["horizontal_rmse_m"] == 0.0


def test_runtime_adapters_use_same_inputs_and_no_trace_or_injection(tmp_path: Path) -> None:
    imu, gnss, output = tmp_path / "fresh.imu", tmp_path / "fresh.gnss", tmp_path / "out"
    exact = exact_runtime_yaml(imu, gnss, output)
    active = active_runtime_config(imu, gnss, output)
    assert str(imu) in exact and str(imu) in active
    assert str(gnss) in exact and str(gnss) in active
    assert "antlever: [0.03, 0.03, -0.30]" in exact
    assert "trace_used_online: false" in active
    assert "semisynthetic_data_used: false" in active
    assert "clean_final_v23_parity_mode: true" in active
    assert "algorithm_id: strong_dual_yaw_EKF" in active
    assert "yaw_noise" not in exact


def test_four_method_config_helper_is_fail_closed_for_auxiliary_paths(tmp_path: Path) -> None:
    with pytest.raises(FinalV23ParityError):
        active_runtime_config(tmp_path / "i", tmp_path / "g", tmp_path / "o", method_id="LegSA_Paper_V1")
    config = active_runtime_config(
        tmp_path / "i", tmp_path / "g", tmp_path / "o", method_id="LegSA_Paper_V1",
        auxiliary_paths={"raw_doppler": tmp_path / "r", "go2_roll_pitch": tmp_path / "a",
                         "go2_horizontal_velocity": tmp_path / "v"},
        extra_config={"raw_doppler_backend_id": "fresh_test_backend"},
    )
    assert "enable_raw_doppler: true" in config
    assert "enable_source_aware: true" in config
    assert "enable_go2_roll_pitch_prior: true" in config
    assert "enable_go2_horizontal_velocity_prior: true" in config


def test_exact_yaw_action_parser_preserves_sequence() -> None:
    log = "\r[YAW-NORMAL] x\r[YAW-DOWNWEIGHT] y\r[YAW-REJECT] z"
    assert parse_exact_modes(log) == ["NORMAL", "DOWNWEIGHT", "REJECT"]


def test_counter_contract_distinguishes_attempts_from_accepted_updates() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp"
    ).read_text(encoding="utf-8")
    assert r'\"dual_yaw_attempt_count\"' in source
    assert r'\"dual_yaw_accepted_count\"' in source


def test_parity_cli_bootstraps_repo_src_namespace() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts/paper_rebuild/run_final_v23_clean_parity.py"
    ).read_text(encoding="utf-8")
    assert 'SRC_ROOT = REPO_ROOT / "src"' in source
    assert "sys.path.insert(0, str(SRC_ROOT))" in source
