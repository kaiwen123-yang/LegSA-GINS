"""H-EXT-02 source-interval and initialization tests, synthetic data only."""
from __future__ import annotations

import csv
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.hext import ext05_sequence_runner as run
from legsa_gins.paper_rebuild.hext.parameters import H02_GAP_POLICY, load_h02_parameters, load_parameters
from legsa_gins.paper_rebuild.horizontal_literature import phase5_runner as phase5
from legsa_gins.paper_rebuild.horizontal_literature.ext05_provider import (
    ImuSample, calibrate_static_imu, sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]
PHASE5 = ROOT / "configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml"
SENSOR = ROOT / "configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml"


def _cache(tmp_path, *, times=None, solution_times=None, static_pass=True, invalid_baseline_index=None):
    cache = tmp_path / "cache"
    cache.mkdir()
    times = np.asarray(times if times is not None else [999.99, 1000.0, 1000.02, 1000.20, 1000.205, 1000.21])
    solution_times = np.asarray(solution_times if solution_times is not None else [1000.0, 1000.05, 1000.10, 1000.15, 1000.209])
    n = len(solution_times)
    p1 = np.repeat(np.array([[0.03, 0.03, -0.30]]), n, axis=0)
    p1[:, 0] += np.arange(n) * 0.02
    accel = np.repeat(np.array([[0.0, 0.0, -9.8]]), len(times), axis=0)
    accel[:, 0] = np.arange(len(times)) + 1.0
    # Distinguish an invalid endpoint from the retained pre-gap and resume force.
    if len(times) > 3:
        accel[3, 0] = 77.0
    arrays = {
        "solution_times": solution_times, "solution_itow": np.arange(n) * 200,
        "p1": p1, "p2": p1 + np.array([0.0, -0.35, 0.0]),
        "pacc1": np.full(n, 0.01), "pacc2": np.full(n, 0.01),
        "valid1": np.ones(n, dtype=np.bool_), "valid2": np.ones(n, dtype=np.bool_),
        "imu_times": times, "gyro": np.zeros((len(times), 3)), "accel": accel,
    }
    if invalid_baseline_index is not None:
        arrays["valid2"][invalid_baseline_index] = False
    hashes = {}
    for name, array in arrays.items():
        path = cache / (name + ".npy")
        np.save(path, array, allow_pickle=False)
        hashes[path.name] = sha256_file(path)
    manifest = {
        "array_hashes": hashes,
        "origin_ecef_m": [-2171613.3982, 4385611.7675, 4076721.9435],
        "ecef_to_ned": np.eye(3).tolist(),
        "first_five_seconds_static_audit": {"passed": static_pass},
        "calibration": {
            "start_time_unix_seconds": 995.0, "end_time_unix_seconds": 1000.0,
            "sample_count": 501, "used_preregistered_initial_interval": True,
            "gyro_bias_frd_radps": [0.0, 0.0, 0.0],
            "mean_specific_force_frd_mps2": [0.0, 0.0, -9.8],
            "gyro_norm_median_radps": 0.0, "acceleration_norm_median_mps2": 9.8,
            "local_gravity_mps2": 9.8, "max_internal_gap_seconds": 0.01,
        },
    }
    (cache / "CACHE_MANIFEST.json").write_text(json.dumps(manifest))
    return cache, arrays, manifest


def _capture_propagations(monkeypatch):
    calls = []
    original = run.PavlasekIEKF

    class CapturingFilter(original):
        def propagate(self, gyro, force, dt):
            calls.append({"dt": dt, "force": force.copy(), "gyro": gyro.copy()})
            return super().propagate(gyro, force, dt)

    monkeypatch.setattr(run, "PavlasekIEKF", CapturingFilter)
    return calls


def _execute(cache, output, *, start="FILE_START", window=(0.0, 0.21)):
    return run._run_h02_filter_sequence(
        cache, output, configuration_id="LC01", start_mode=start, base_time=1000.0,
        window=window, parameters=load_h02_parameters(PHASE5),
    )


def test_d1_classifies_raw_gap_before_short_gnss_splits_and_keeps_updates(monkeypatch, tmp_path):
    cache, arrays, _ = _cache(tmp_path)
    calls = _capture_propagations(monkeypatch)
    result = _execute(cache, tmp_path / "native")
    gap = result["gaps"][0]
    assert gap["duration_s"] == pytest.approx(0.18)
    assert gap["gnss_updates_in_gap"] == 3
    assert gap["gnss_update_indices"] == [1, 2, 3]
    assert gap["propagation_count"] == 0
    assert gap["invalid_endpoint_assimilated"] is False
    assert np.linalg.norm(gap["position_delta_ned_m"]) > 0.0
    # All inertial calls exclude the .18-second gap even though three GNSS
    # events would split it into individually admissible <=.1-second spans.
    assert sum(c["dt"] for c in calls) == pytest.approx(0.03)
    assert calls[1]["dt"] == pytest.approx(arrays["imu_times"][4] - arrays["imu_times"][3])
    np.testing.assert_array_equal(calls[1]["force"], arrays["accel"][2])
    for call in calls[2:]:
        np.testing.assert_array_equal(call["force"], arrays["accel"][4])
    assert all(c["force"][0] != 77.0 for c in calls)
    assert (tmp_path / "native/GAP_EVENTS.json").is_file()


def test_d1_duplicate_endpoint_dropped_resume_uses_own_dt(monkeypatch, tmp_path):
    times = [999.99, 1000.0, 1000.02, 1000.02, 1000.025, 1000.03]
    cache, arrays, _ = _cache(tmp_path, times=times, solution_times=[1000.0, 1000.029])
    calls = _capture_propagations(monkeypatch)
    result = _execute(cache, tmp_path / "native", window=(0.0, 0.03))
    gap = result["gaps"][0]
    assert gap["classification"] == "DROPPED_NONPOSITIVE_DT"
    assert gap["duration_s"] == 0.0
    assert gap["processed_after_initialization"] is True
    assert gap["position_delta_ned_m"] == [0.0, 0.0, 0.0]
    assert gap["propagation_count"] == 0
    np.testing.assert_array_equal(calls[1]["force"], arrays["accel"][2])
    assert calls[1]["dt"] == pytest.approx(0.005)
    assert all(c["force"][0] != 77.0 for c in calls)


def test_backwards_stamp_drop_is_logged_before_overlap_failure(tmp_path):
    cache, _, _ = _cache(tmp_path, times=[999.99, 1000.0, 1000.02, 1000.01, 1000.025],
                         solution_times=[1000.0, 1000.024])
    with pytest.raises(run.SourceChronologyFailure, match="overlaps") as error:
        _execute(cache, tmp_path / "native")
    assert error.value.gap_records[0]["classification"] == "DROPPED_NONPOSITIVE_DT"
    assert error.value.gap_records[0]["invalid_endpoint_assimilated"] is False


def test_d2_contract_start_position_epoch_separate_from_subsequent_valid_yaw(tmp_path):
    cache, arrays, manifest = _cache(tmp_path, static_pass=False, invalid_baseline_index=2)
    origin_before = list(manifest["origin_ecef_m"])
    selected, attitude, position = run.select_h02_initialization(
        arrays, manifest, start_mode="CONTRACT_START", base_time=1000.0, window=(0.10, 0.21),
    )
    assert selected["initial_solution_index"] == 2
    assert selected["initial_time_unix_seconds"] == 1000.10
    assert selected["initial_yaw_source_index"] == 3
    np.testing.assert_array_equal(position, arrays["p1"][2] - attitude @ run.LEVER_IMU_TO_RECEIVER1_FRD_M)
    assert manifest["origin_ecef_m"] == origin_before
    assert selected["initial_velocity_ned_mps"] == [0.0, 0.0, 0.0]
    assert selected["static_admissibility_waived"] is True
    assert selected["calibration_interval_unchanged"] is True
    with pytest.raises(run.FileStartStaticFailure):
        run.select_h02_initialization(arrays, manifest, start_mode="FILE_START", base_time=1000.0, window=(0.10, 0.21))
    result = _execute(cache, tmp_path / "contract", start="CONTRACT_START", window=(0.10, 0.21))
    assert result["summary"]["first_valid_interval_after_initialization"]["source_right_index"] == 4
    assert result["summary"]["first_valid_interval_after_initialization"]["held_sample_index"] == 2
    with (tmp_path / "contract/INNOVATION.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert all(float(row["absolute_time_unix_seconds"]) >= 1000.10 for row in rows)


def test_first_file_calibration_exact_frozen_statistics_and_no_fallback():
    samples = tuple(ImuSample(995.0 + .01 * i, np.array([.001, .002, .003]),
                              np.array([0.0, 0.0, -9.8])) for i in range(600))
    frozen = calibrate_static_imu(samples, latitude_deg=40.0, height_m=30.0)
    actual, audit = run._first_file_calibration(samples, 40.0, 30.0)
    for key, value in asdict(frozen).items():
        if isinstance(value, np.ndarray):
            np.testing.assert_array_equal(getattr(actual, key), value)
        else:
            assert getattr(actual, key) == value
    assert audit["passed"] is True
    moving = tuple(ImuSample(s.absolute_time_unix_seconds, np.array([1.0, 0.0, 0.0]), s.specific_force_frd_mps2)
                   for s in samples)
    actual, audit = run._first_file_calibration(moving, 40.0, 30.0)
    assert audit["passed"] is False
    assert actual.start_time_unix_seconds == 995.0
    assert audit["fallback_window_search_used"] is False


@pytest.mark.parametrize("two_receiver,configuration", [(True, "LC01"), (False, "EXT05C")])
def test_h02_no_gap_file_start_native_bytes_equal_frozen_phase5(tmp_path, two_receiver, configuration):
    test_path = ROOT / "tests/paper_rebuild/test_horizontal_phase5_c00.py"
    spec = importlib.util.spec_from_file_location("hext02_original_fixture", test_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    cache = fixture._write_synthetic_cache(tmp_path)
    manifest_path = cache / "CACHE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["first_five_seconds_static_audit"] = {"passed": True}
    manifest_path.write_text(json.dumps(manifest))
    phase5._run_filter_sequence(str(cache), two_receiver=two_receiver, output_root_text=str(tmp_path / "frozen"))
    result = run._run_h02_filter_sequence(
        cache, tmp_path / "h02", configuration_id=configuration, start_mode="FILE_START",
        base_time=phase5.BASE_TIME, window=(66.0, 340.0), parameters=load_h02_parameters(PHASE5),
    )
    assert result["gaps"] == []
    for filename in ("NAV.csv", "INNOVATION.csv", "NIS.csv"):
        assert (tmp_path / "h02" / filename).read_bytes() == (tmp_path / "frozen" / filename).read_bytes()


def test_h02_parameters_only_authorized_common_policy_and_variant_fields():
    original = load_parameters(PHASE5)
    literature = load_h02_parameters(PHASE5)
    assert replace(literature, imu_gap_policy="frozen_filter_raise") == original
    variant = load_h02_parameters(PHASE5, variant_enabled=True, sensor_model_path=SENSOR)
    assert variant.gyro_psd_rad2_s == (8.209651003126647e-08,) * 3
    assert variant.accel_scale == 1.0308398903907543
    assert variant.phase5_parameter_blocks == literature.phase5_parameter_blocks
    assert variant.imu_gap_policy == literature.imu_gap_policy == H02_GAP_POLICY
