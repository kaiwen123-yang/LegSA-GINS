from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from legsa_gins.paper_rebuild.horizontal_literature import phase5_runner as phase5
from legsa_gins.paper_rebuild.horizontal_literature.ext05_pavlasek import (
    METHOD_IEKF,
    METHOD_SINGLE,
)
from legsa_gins.paper_rebuild.horizontal_literature.ext05_provider import (
    BASELINE_BODY_FRD_M,
    LEVER_IMU_TO_RECEIVER1_FRD_M,
    sha256_file,
)


def _write_synthetic_cache(root: Path) -> Path:
    cache = root / "cache"
    cache.mkdir()
    within_support = 1000.0 + 0.1 * np.arange(8)
    beyond_support = 1001.1 + 0.1 * np.arange(38)
    solution_times = np.concatenate((within_support, beyond_support))
    count = len(solution_times)
    p1 = np.repeat(LEVER_IMU_TO_RECEIVER1_FRD_M[None, :], count, axis=0)
    p2 = p1 + BASELINE_BODY_FRD_M
    imu_times = 999.99 + 0.01 * np.arange(92)
    arrays = {
        "solution_times": solution_times,
        "solution_itow": np.arange(count, dtype=np.int64) * 100,
        "p1": p1,
        "p2": p2,
        "pacc1": np.full(count, 0.01),
        "pacc2": np.full(count, 0.01),
        "valid1": np.ones(count, dtype=np.bool_),
        "valid2": np.ones(count, dtype=np.bool_),
        "imu_times": imu_times,
        "gyro": np.zeros((len(imu_times), 3)),
        "accel": np.repeat(np.array([[0.0, 0.0, -9.8]]), len(imu_times), axis=0),
    }
    hashes: dict[str, str] = {}
    for name, array in arrays.items():
        path = cache / f"{name}.npy"
        np.save(path, array, allow_pickle=False)
        hashes[path.name] = sha256_file(path)
    (cache / "CACHE_MANIFEST.json").write_text(json.dumps({
        "array_hashes": hashes,
        "calibration": {
            "start_time_unix_seconds": 995.0,
            "end_time_unix_seconds": 1000.0,
            "sample_count": 501,
            "used_preregistered_initial_interval": True,
            "gyro_bias_frd_radps": [0.0, 0.0, 0.0],
            "mean_specific_force_frd_mps2": [0.0, 0.0, -9.8],
            "gyro_norm_median_radps": 0.0,
            "acceleration_norm_median_mps2": 9.8,
            "local_gravity_mps2": 9.8,
            "max_internal_gap_seconds": 0.01,
        },
    }, sort_keys=True), encoding="utf-8")
    return cache


def test_native_required_artifact_contract_includes_explicit_mekf_waiver() -> None:
    assert phase5.NATIVE_NAMES == (
        "EXT05A_C00_IEKF_NAV.csv",
        "EXT05A_C00_INNOVATION_DIAGNOSTICS.csv",
        "EXT05A_C00_NIS_DIAGNOSTICS.csv",
        "EXT05A_C00_PROVIDER_DIAGNOSTICS.csv",
        "EXT05A_C00_RUNTIME.csv",
        "EXT05A_C00_NATIVE_SUMMARY.json",
        "EXT05C_C00_SINGLE_RECEIVER_IEKF_NAV.csv",
        "EXT05C_C00_SINGLE_RECEIVER_IEKF_INNOVATION_DIAGNOSTICS.csv",
        "EXT05C_C00_SINGLE_RECEIVER_IEKF_NIS_DIAGNOSTICS.csv",
        "EXT05B_C00_MEKF_NOT_IMPLEMENTED.json",
    )
    assert phase5.NATIVE_FREEZE_NAME == "EXT05A_C00_NATIVE_FREEZE.json"


def test_synthetic_native_sequences_are_chronological_and_worker_deterministic(
    tmp_path: Path,
) -> None:
    cache = _write_synthetic_cache(tmp_path)
    workers1 = phase5._run_method_set(cache, tmp_path / "workers1", 1)
    workers16 = phase5._run_method_set(cache, tmp_path / "workers16", 16)
    for name, method in (("dual", METHOD_IEKF), ("single", METHOD_SINGLE)):
        assert workers1[name]["method_id"] == method
        assert workers1[name]["scientific_hash"] == workers16[name]["scientific_hash"]
        assert workers16[name]["summary"]["recursive_epochs_chronological"] is True
        assert workers16[name]["summary"]["provider_epochs_beyond_imu_support"] == 38
        assert workers16[name]["summary"]["final_snapshot"]["finite"] is True
        with (Path(workers16[name]["output_root"]) / "NAV.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            first = next(csv.DictReader(handle))
        assert first["covariance_coordinate"] == "LEFT_INVARIANT_BODY_TANGENT"
        assert first["covariance_state_order"].startswith("dtheta_x_body,dtheta_y_body")
        assert "std_roll_deg" not in first
        assert len([field for field in first if field.startswith("P_left_")]) == 45
        covariance = np.zeros((9, 9))
        for row in range(9):
            for column in range(row, 9):
                covariance[row, column] = float(first[f"P_left_{row}_{column}"])
                covariance[column, row] = covariance[row, column]
        assert np.min(np.linalg.eigvalsh(covariance)) >= -1.0e-10


def test_geometric_yaw_uses_fixed_p2_minus_p1_body_transform() -> None:
    source = []
    for index, yaw in enumerate((359.0, 0.5, 1.0)):
        source.append({
            "method_id": METHOD_IEKF,
            "provider_epoch_index": str(index),
            "absolute_time_unix_seconds": str(1005.0 + index),
            "yaw_ned_deg": str(yaw),
            "measured_baseline_n": "0.0",
            "measured_baseline_e": "-0.35",
            "measured_baseline_d": "0.0",
            "estimated_baseline_n": "0.0",
            "estimated_baseline_e": "-0.35",
            "estimated_baseline_d": "0.0",
            "receiver1_residual_n": "0.0",
            "receiver1_residual_e": "0.0",
            "receiver1_residual_d": "0.0",
            "relative_residual_n": "0.0",
            "relative_residual_e": "0.0",
            "relative_residual_d": "0.0",
        })
    rows = phase5._geometric_audit_rows(source, initial_time=1000.0)
    assert [row["direct_geometric_yaw_ned_deg"] for row in rows] == pytest.approx([0.0] * 3)
    assert [row["filter_minus_geometric_wrapsafe_deg"] for row in rows] == pytest.approx(
        [-1.0, 0.5, 1.0]
    )
    assert [row["measured_estimated_direction_angle_deg"] for row in rows] == pytest.approx(
        [0.0] * 3
    )


def test_native_code_has_no_trace_or_historical_matrix_dependency() -> None:
    native_source = inspect.getsource(phase5.run_native)
    cache_source = inspect.getsource(phase5._build_cache)
    module_source = Path(phase5.__file__).read_text(encoding="utf-8").lower()
    assert "paths.trace" not in native_source
    assert "trace.open" not in cache_source
    assert "classic_case_spec" not in module_source
    assert "canonical541" not in module_source
    assert "by2_algorithm_runner" not in module_source


def test_thread_environment_is_pinned_to_one() -> None:
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        assert phase5.os.environ[name] == "1"


def test_dirty_untracked_source_snapshot_is_hash_complete_and_explicit() -> None:
    snapshot = phase5._source_snapshot()
    assert snapshot["file_count"] == 15
    roles = [row["source_role"] for row in snapshot["files"].values()]
    assert roles.count("DIRECT_EXT05_RUNTIME") == 6
    assert roles.count("MAINTAINED_SHARED_RUNTIME") == 7
    assert roles.count("FOCUSED_TEST") == 2
    assert len([row for row in snapshot["files"].values() if row["runtime_bearing"]]) == 13
    assert snapshot["dirty_or_untracked_snapshot_recorded"] is True
    assert snapshot["git_head_alone_identifies_ext05_implementation"] is False
    for evidence in snapshot["files"].values():
        assert len(evidence["sha256"]) == 64
        assert evidence["size_bytes"] > 0
    phase5._revalidate_source_snapshot(snapshot)


def _lla_to_ecef(latitude_deg: float, longitude_deg: float, height_m: float) -> np.ndarray:
    latitude, longitude = np.radians([latitude_deg, longitude_deg])
    semi_major = 6_378_137.0
    eccentricity_sq = 6.6943799901413165e-3
    sin_lat = np.sin(latitude)
    radius = semi_major / np.sqrt(1.0 - eccentricity_sq * sin_lat * sin_lat)
    return np.array([
        (radius + height_m) * np.cos(latitude) * np.cos(longitude),
        (radius + height_m) * np.cos(latitude) * np.sin(longitude),
        (radius * (1.0 - eccentricity_sq) + height_m) * sin_lat,
    ])


def test_exact_evaluator_nav_adapter_uses_fixed_frame_and_closed_window(tmp_path: Path) -> None:
    origin = np.array([-2171613.3982, 4385611.7675, 4076721.9435])
    rotation = np.array([
        [0.28514433788619087, -0.5758540469064211, 0.7662146065123943],
        [-0.8961526644772995, -0.44374587541771776, 0.0],
        [0.34000457132468453, -0.6866452611875077, -0.6425847623209383],
    ])
    native = tmp_path / "native.csv"
    fields = (
        "time_seconds", "north_m", "east_m", "down_m", "vn_mps", "ve_mps",
        "vd_mps", "roll_deg", "pitch_deg", "yaw_ned_deg",
    )
    rows = []
    for time_seconds, ned in (
        (65.9, [9.0, 9.0, 9.0]),
        (66.0, [0.0, 0.0, 0.0]),
        (100.0, [1.0, 2.0, 3.0]),
        (340.0, [-2.0, 1.0, -0.5]),
        (340.1, [9.0, 9.0, 9.0]),
    ):
        rows.append({
            "time_seconds": time_seconds,
            "north_m": ned[0], "east_m": ned[1], "down_m": ned[2],
            "vn_mps": 0.1, "ve_mps": 0.2, "vd_mps": 0.3,
            "roll_deg": 1.0, "pitch_deg": 2.0, "yaw_ned_deg": 3.0,
        })
    phase5._write_csv(native, fields, rows)
    adapted = tmp_path / "adapted.nav"
    report = phase5._materialize_exact_evaluator_nav(
        native, adapted, origin_ecef_m=origin, ecef_to_ned=rotation
    )
    numeric = [
        line.split() for line in adapted.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("%")
    ]
    assert report["output_epoch_count"] == 3
    assert [float(row[1]) for row in numeric] == pytest.approx([66.0, 100.0, 340.0])
    expected_ned = ([0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [-2.0, 1.0, -0.5])
    for row, expected in zip(numeric, expected_ned):
        reconstructed_ecef = _lla_to_ecef(float(row[2]), float(row[3]), float(row[4]))
        assert rotation @ (reconstructed_ecef - origin) == pytest.approx(expected, abs=2.0e-6)


def test_supplemental_trace_metrics_add_p99_and_crosscheck_exact_rmse(tmp_path: Path) -> None:
    columns = {
        "time": [66.0, 67.0, 68.0],
        "err_n_m": [1.0, -2.0, 3.0],
        "err_e_m": [0.5, -0.25, 0.75],
        "err_u_m": [-1.0, 0.0, 1.0],
        "horizontal_err_m": [1.11803398875, 2.01556443707, 3.09232921921],
        "position_3d_err_m": [1.5, 2.01556443707, 3.25],
        "roll_err_deg": [0.1, -0.2, 0.3],
        "pitch_err_deg": [-0.4, 0.5, -0.6],
        "yaw_err_deg": [1.0, -2.0, 3.0],
    }
    errors = tmp_path / "errors.csv"
    phase5._write_csv(
        errors, tuple(columns),
        ({name: values[index] for name, values in columns.items()} for index in range(3)),
    )
    distributions = {
        name: phase5._metric_distribution(columns[column])
        for name, column in {
            "north_m": "err_n_m", "east_m": "err_e_m", "up_m": "err_u_m",
            "horizontal_m": "horizontal_err_m", "position_3d_m": "position_3d_err_m",
            "roll_deg": "roll_err_deg", "pitch_deg": "pitch_err_deg", "yaw_deg": "yaw_err_deg",
        }.items()
    }
    exact = {
        "position": {
            "north_rmse_m": distributions["north_m"]["rmse"],
            "east_rmse_m": distributions["east_m"]["rmse"],
            "up_rmse_m": distributions["up_m"]["rmse"],
            "horizontal_rmse_m": distributions["horizontal_m"]["rmse"],
            "position_3d_rmse_m": distributions["position_3d_m"]["rmse"],
        },
        "attitude": {
            "roll_rmse_deg": distributions["roll_deg"]["rmse"],
            "pitch_rmse_deg": distributions["pitch_deg"]["rmse"],
            "yaw_rmse_deg": distributions["yaw_deg"]["rmse"],
        },
    }
    result = phase5._supplement_exact_metrics(
        method_id=METHOD_IEKF,
        evaluator_result={"errors_path": errors, "summary": exact, "runtime_seconds": 0.2},
        adapter={"output_epoch_count": 3, "strictly_chronological": True},
        nis={"row_count": 3, "degrees_of_freedom": 6},
        native_runtime_seconds=1.0,
    )
    assert result["coverage"] == 1.0
    assert result["metrics"]["yaw_deg"]["p99_absolute"] == pytest.approx(2.98)
    assert max(result["exact_evaluator_crosscheck_absolute_differences"].values()) <= 1e-10


def test_exact_evaluator_and_trace_hash_constants_are_frozen() -> None:
    assert phase5.EXACT_EVALUATOR_SHA256 == "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"
    assert phase5.FROZEN_TRACE_SHA256 == "ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c"


def test_trace_evaluation_resume_revalidates_payload_report_and_native_freeze(
    tmp_path: Path,
) -> None:
    c00 = tmp_path / "stage/06/C00"
    c00.mkdir(parents=True)
    native_files = {}
    for name in phase5.NATIVE_NAMES:
        path = c00 / name
        path.write_text(name, encoding="utf-8")
        native_files[name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    phase5._write_json(c00 / phase5.NATIVE_FREEZE_NAME, {
        "terminal_status": phase5.PASS_NATIVE,
        "files": native_files,
        "trace_open_count": 0,
    })
    native_freeze_hash = sha256_file(c00 / phase5.NATIVE_FREEZE_NAME)
    evaluation = c00 / phase5.TRACE_EVALUATION_RELATIVE
    evaluation.mkdir()
    summary = evaluation / "EXT05A_C00_TRACE_EVALUATION_SUMMARY.json"
    phase5._write_json(summary, {"terminal_status": phase5.PASS_C00})
    report_root = tmp_path / "stage/11_REPORT"
    report_root.mkdir()
    report = report_root / "EXT05A_C00_VALIDITY_REPORT.md"
    report.write_text("frozen report\n", encoding="utf-8")
    phase5._write_json(evaluation / "EXT05A_C00_TRACE_EVALUATION_FREEZE.json", {
        "terminal_status": phase5.PASS_C00,
        "trace_used_online": False,
        "exact_evaluator_sha256": phase5.EXACT_EVALUATOR_SHA256,
        "files": {
            summary.name: {"sha256": sha256_file(summary), "size_bytes": summary.stat().st_size},
        },
        "report": {"sha256": sha256_file(report), "size_bytes": report.stat().st_size},
        "native_freeze_sha256": native_freeze_hash,
    })
    paths = phase5.Phase5Paths(
        config_path=tmp_path / "paths.yaml", code_root=tmp_path, raw_root=tmp_path,
        by2_fix_root=tmp_path, go2_body=tmp_path / "go2", clean_root=tmp_path,
        by2_hash_lock=tmp_path / "by2.lock", full_hash_lock=tmp_path / "all.lock",
        gnss1_raw=tmp_path / "g1", gnss2_raw=tmp_path / "g2", trace=tmp_path / "trace",
        stage_root=tmp_path / "stage", ext05_root=c00.parent, c00_root=c00,
        report_root=report_root,
    )
    assert phase5._validate_trace_evaluation_freeze(paths)["terminal_status"] == phase5.PASS_C00
    summary.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(phase5.Phase5RunnerError, match="payload drifted"):
        phase5._validate_trace_evaluation_freeze(paths)
