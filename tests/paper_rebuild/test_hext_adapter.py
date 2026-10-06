"""Synthetic/unit-only adapter validation; no raw data or trace is opened."""
from __future__ import annotations

from dataclasses import replace
import csv
import importlib.util
import inspect
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import ext05_provider as provider
from legsa_gins.paper_rebuild.horizontal_literature import phase5_runner as phase5
from legsa_gins.paper_rebuild.hext import ext05_sequence_runner as adapter
from legsa_gins.paper_rebuild.hext.parameters import (
    literature_parameters, load_parameters, require_implemented_gap_policy,
    scaled_frd_specific_force,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml"
SENSOR = ROOT / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml"


def test_provider_defaults_are_original_by2_guards() -> None:
    position = inspect.signature(provider.build_solution_position_provider).parameters
    imu = inspect.signature(provider.build_imu_only_provider).parameters
    assert position["expected_position_epochs"].default == provider.EXPECTED_POSITION_EPOCHS == 1510
    assert position["expected_rawx_epochs"].default == provider.EXPECTED_RAWX_EPOCHS == 1509
    assert position["expected_gps_week"].default == provider.EXPECTED_GPS_WEEK == 2408
    assert position["expected_leap_seconds"].default == provider.EXPECTED_LEAP_SECONDS == 18
    assert imu["expected_imu_samples"].default == provider.EXPECTED_IMU_SAMPLES == 63278
    assert position["hash_lock"].default is None
    assert imu["hash_lock"].default is None


def test_disabled_parameters_equal_literature_field_for_field(tmp_path: Path) -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    expected = literature_parameters(contract)
    actual = load_parameters(CONTRACT, variant_enabled=False, sensor_model_path=tmp_path / "must_not_open")
    assert actual == expected
    assert actual.phase5_parameter_blocks == contract
    assert actual.gyro_psd_rad2_s == (4e-4, 4e-4, 3.24e-4)
    assert actual.accel_psd_m2_s3 == (0.0289, 0.0225, 0.0576)
    assert actual.accel_scale == 1.0
    assert actual.imu_gap_policy == "frozen_filter_raise"


def test_shared_psd_conversions_and_q_crosscheck(tmp_path: Path) -> None:
    values = load_parameters(CONTRACT, variant_enabled=True, sensor_model_path=SENSOR)
    model = yaml.safe_load(SENSOR.read_text())
    expected = (0.985 * math.pi / 180.0 / 60.0) ** 2
    assert values.gyro_psd_rad2_s == (expected,) * 3
    assert values.accel_psd_m2_s3 == tuple(model["q"])
    assert values.accel_psd_m2_s3 == pytest.approx(tuple((v / 60.0) ** 2 for v in model["vrw"]), rel=1e-13)
    assert values.accel_scale == 1.0308398903907543
    assert values.phase5_parameter_blocks == load_parameters(CONTRACT).phase5_parameter_blocks
    model["q"][1] *= 1.001
    bad = tmp_path / "bad_sensor.yaml"
    bad.write_text(yaml.safe_dump(model))
    with pytest.raises(ValueError, match="q disagrees"):
        load_parameters(CONTRACT, variant_enabled=True, sensor_model_path=bad)


def test_scale_is_three_axis_post_transform_preintegration_and_default_noop() -> None:
    force_flu = np.array([0.31, -0.83, 9.58])
    transformed = provider.euler_rpy_deg_to_matrix(-1, 0, 0) @ np.diag([1.0, -1.0, -1.0]) @ force_flu
    assert scaled_frd_specific_force(transformed, 1.0) is transformed
    scale, dt = 1.0308398903907543, 0.00417
    scaled = scaled_frd_specific_force(transformed, scale)
    np.testing.assert_array_equal(scaled, transformed * scale)
    np.testing.assert_array_equal(scaled * dt, (transformed * scale) * dt)


def test_unimplemented_gap_policy_stops_before_cache_access(tmp_path: Path) -> None:
    params = replace(load_parameters(CONTRACT), imu_gap_policy="mirror_legsa_drop")
    with pytest.raises(NotImplementedError, match="H-EXT-02"):
        require_implemented_gap_policy(params)
    with pytest.raises(NotImplementedError, match="H-EXT-02"):
        adapter._run_filter_sequence(
            str(tmp_path / "absent_cache"), two_receiver=True,
            output_root_text=str(tmp_path / "must_not_exist"), base_time=0.0, parameters=params,
        )
    assert not (tmp_path / "must_not_exist").exists()


def _synthetic_cache(tmp_path: Path) -> Path:
    # Reuse the existing short synthetic fixture with its frozen 38 support-tail rows.
    path = ROOT / "tests/paper_rebuild/test_horizontal_phase5_c00.py"
    spec = importlib.util.spec_from_file_location("hext_phase5_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._write_synthetic_cache(tmp_path)


@pytest.mark.parametrize("two_receiver", [True, False])
def test_default_recursive_loop_exact_synthetic_native_bytes(tmp_path: Path, two_receiver: bool) -> None:
    cache = _synthetic_cache(tmp_path)
    phase5._run_filter_sequence(str(cache), two_receiver=two_receiver, output_root_text=str(tmp_path / "frozen"))
    adapter._run_filter_sequence(
        str(cache), two_receiver=two_receiver, output_root_text=str(tmp_path / "adapter"),
        base_time=phase5.BASE_TIME, parameters=load_parameters(CONTRACT),
    )
    for filename in ("NAV.csv", "INNOVATION.csv", "NIS.csv", "SCIENTIFIC_SUMMARY.json"):
        assert (tmp_path / "adapter" / filename).read_bytes() == (tmp_path / "frozen" / filename).read_bytes()


def _native_rows(path: Path, *, base_time: float, times: list[float]) -> None:
    fields = ("absolute_time_unix_seconds", "time_seconds", "north_m", "east_m", "down_m", "vn_mps", "ve_mps", "vd_mps", "roll_deg", "pitch_deg", "yaw_ned_deg")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for t in times:
            row = {key: 0.0 for key in fields}
            row.update(absolute_time_unix_seconds=base_time + t, time_seconds=t)
            writer.writerow(row)


def test_closed_window_and_sequence_base_time_and_frozen_nav_serialization(tmp_path: Path) -> None:
    origin = np.array([-2171613.3982, 4385611.7675, 4076721.9435])
    rotation = provider.fixed_ecef_to_ned_rotation(origin)
    native = tmp_path / "native.csv"
    _native_rows(native, base_time=phase5.BASE_TIME, times=[65.0, 66.0, 100.0, 340.0, 341.0])
    kwargs = {"origin_ecef_m": origin, "ecef_to_ned": rotation}
    phase5._materialize_exact_evaluator_nav(native, tmp_path / "frozen.nav", **kwargs)
    report = adapter.materialize_exact_evaluator_nav(
        native, tmp_path / "adapter.nav", **kwargs, base_time=phase5.BASE_TIME, window=(66.0, 340.0),
    )
    assert (tmp_path / "adapter.nav").read_bytes() == (tmp_path / "frozen.nav").read_bytes()
    assert report["output_epoch_count"] == 3
    other = tmp_path / "other.csv"
    _native_rows(other, base_time=1772780400.0, times=[3185.0, 3186.0, 3500.0, 3563.0, 3564.0])
    report = adapter.materialize_exact_evaluator_nav(
        other, tmp_path / "other.nav", **kwargs, base_time=1772780400.0, window=(3186.0, 3563.0),
    )
    table = np.loadtxt(tmp_path / "other.nav", comments="%")
    assert table.shape == (3, 11)  # frozen index/time/LLA/velocity/RPY columns
    assert table[:, 0].tolist() == [1, 2, 3]  # pre-crop row index retained
    assert table[:, 1].tolist() == [3186.0, 3500.0, 3563.0]
    assert report["window_seconds"] == [3186.0, 3563.0]
    with pytest.raises(phase5.Phase5RunnerError, match="base_time"):
        adapter.materialize_exact_evaluator_nav(
            other, tmp_path / "wrong.nav", **kwargs, base_time=phase5.BASE_TIME, window=(3186.0, 3563.0),
        )


@pytest.mark.parametrize("sequence_id,variant", [("BY2H", False), ("BY2O", False), ("BY2", True)])
def test_h_ext_01_rejects_unauthorized_native_launch_before_io(tmp_path: Path, sequence_id: str, variant: bool) -> None:
    with pytest.raises(PermissionError, match="only default BY2"):
        adapter.run_native_sequence(
            SimpleNamespace(sequence_id=sequence_id), tmp_path / "never_created",
            phase5_contract_path=tmp_path / "never_read", code_commit="unit_test",
            variant_enabled=variant,
        )
    assert not (tmp_path / "never_created").exists()


@pytest.mark.parametrize("leading_count", [0, 1])
def test_expected_count_guard_preserves_exact_plus_two_relation(monkeypatch, tmp_path: Path, leading_count: int) -> None:
    hp = [SimpleNamespace(itow_ms=1002 + 200 * i,
                          position_ecef_m=np.array([-2171613.3982, 4385611.7675, 4076721.9435]),
                          position_accuracy_m=0.01) for i in range(3)]
    rawx = [SimpleNamespace(gps_tow_seconds=(e.itow_ms - 2) / 1000.0,
                            gps_week=2408, leap_seconds=18) for e in hp[leading_count:]]
    stream = SimpleNamespace(nav_hpposecef_epochs=hp, rawx_epochs=rawx)
    monkeypatch.setattr(provider, "reconstruct_ubx_stream", lambda *args, **kwargs: stream)
    monkeypatch.setattr(provider, "verify_hash_locked_file", lambda *args, **kwargs: {"synthetic_fixture": True})
    result = provider.build_solution_position_provider(
        tmp_path / "gnss1", tmp_path / "gnss2", raw_root=tmp_path,
        hash_lock=tmp_path / "synthetic_lock", expected_position_epochs=3,
        expected_rawx_epochs=3-leading_count,
    )
    assert result.diagnostics["leading_hpposecef_without_rawx_count"] == leading_count
    assert result.diagnostics["hpposecef_equals_rawx_plus_ms"] == 2
    assert result.epochs[0].absolute_time_unix_seconds == 315964800.0 + 2408 * 604800.0 + 1.002 - 18
