from __future__ import annotations

import importlib.util
import json
import math
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO / "src/legsa_gins/paper_rebuild/horizontal_literature"


def _isolated_h6():
    package_name = "_test_hartley_h6_isolated"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5", "hartley_h6"):
        name = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / f"{basename}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h6"]


h6 = _isolated_h6()
CONTRACT = REPO / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6_EXECUTION_CONTRACT.yaml"


def _cache(masks: list[int], *, dt: float = 0.01) -> h6.CacheArrays:
    count = len(masks)
    timestamp = (np.arange(count) * round(dt * 1.0e9)).astype(np.int64)
    gyro = np.zeros((count, 3))
    gyro[:, 2] = np.linspace(0.0, 0.3, count)
    accel = np.tile([0.0, 0.0, 9.81], (count, 1))
    accel[:, 0] = np.linspace(0.0, 0.2, count)
    return h6.CacheArrays(
        timestamp, gyro, accel, np.zeros((count, 4)), np.zeros((count, 4, 3)),
        np.asarray(masks, dtype=np.uint8), np.zeros(count, dtype=np.uint8),
        np.zeros(count, dtype=np.uint8),
    )


def test_h6_frozen_identity_sign_and_prohibitions() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    assert contract["task_start_head"] == h6.TASK_START_HEAD
    assert contract["method_id"] == h6.METHOD_ID
    assert contract["backend_id"] == h6.BACKEND_ID
    assert contract["input_identity"]["state_rows"] == 63277
    assert contract["gauge_ensemble"]["initial_alpha_degrees"] == [-150, -100, -50, 0, 50, 100, 150]
    sign = contract["gauge_sign_and_multiplication"]
    assert sign["normalized_world_gravity_axis_e_g"] == [0.0, 0.0, -1.0]
    assert sign["mean_action"] == "LEFT_MULTIPLICATION"
    assert sign["expected_conventional_positive_Z_euler_yaw_offset_degrees"] == "NEGATIVE_ALPHA"
    assert sign["sign_selected_from_nonzero_results"] is False
    assert all(value == 0 for key, value in contract["forbidden_access_and_execution"].items() if key.endswith("_count"))
    assert contract["forbidden_access_and_execution"]["h7_executed"] is False


@pytest.mark.parametrize("alpha", [-150.0, -50.0, 0.0, 100.0, 150.0])
def test_q_alpha_is_about_normalized_negative_z_gravity(alpha: float) -> None:
    q = h6.rotation_z(alpha)
    signed_log_angle = -math.atan2(q[1, 0], q[0, 0])
    assert signed_log_angle == pytest.approx(math.radians(alpha), abs=2.0e-15)
    assert np.allclose(q.T @ q, np.eye(3), atol=2.0e-15)
    assert np.linalg.det(q) == pytest.approx(1.0, abs=2.0e-15)


def test_initial_state_contacts_bias_and_covariance_congruence() -> None:
    rotation = h6.rotation_z(-13.0)
    velocity = np.asarray([1.0, -2.0, 0.3])
    position = np.asarray([4.0, 5.0, -0.1])
    contacts = {0: np.asarray([3.8, 5.2, -0.4]), 3: np.asarray([4.2, 4.8, -0.4])}
    bg = np.asarray([0.01, -0.02, 0.03])
    ba = np.asarray([0.2, -0.1, 0.05])
    random = np.random.default_rng(42).normal(size=(21, 21))
    covariance = random @ random.T
    transformed = h6.gauge_transform_state(rotation, velocity, position, contacts, bg, ba, covariance, 50.0)
    q = h6.rotation_z(50.0)
    assert np.allclose(transformed[0], q @ rotation)
    assert np.allclose(transformed[1], q @ velocity)
    assert np.allclose(transformed[2], q @ position)
    assert all(np.allclose(transformed[3][key], q @ value) for key, value in contacts.items())
    assert np.array_equal(transformed[4], bg) and np.array_equal(transformed[5], ba)
    transform = np.eye(21)
    for offset in range(0, 15, 3):
        transform[offset:offset + 3, offset:offset + 3] = q
    assert np.allclose(transformed[6], transform @ covariance @ transform.T)


def test_zero_degree_python_transform_is_exact_noop() -> None:
    rotation = np.eye(3)
    zeros = np.zeros(3)
    contacts = {0: np.asarray([1.0, 2.0, 3.0])}
    covariance = np.diag(np.arange(1.0, 19.0))
    result = h6.gauge_transform_state(rotation, zeros, zeros, contacts, zeros, zeros, covariance, 0.0)
    assert np.array_equal(result[0], rotation)
    assert np.array_equal(result[1], zeros) and np.array_equal(result[2], zeros)
    assert np.array_equal(result[3][0], contacts[0])
    assert np.array_equal(result[6], covariance)


def test_inverse_gauge_state_alignment_relative_yaw_and_covariance() -> None:
    q = h6.rotation_z(-100.0)
    rotation = h6.rotation_z(27.0)
    vector = np.asarray([3.0, -4.0, 0.2])
    assert np.allclose(q.T @ (q @ rotation), rotation, atol=2.0e-15)
    assert np.allclose(q.T @ (q @ vector), vector, atol=2.0e-15)
    base_yaw = np.unwrap(np.asarray([0.1, 0.2, 0.4]))
    gauge_yaw = np.unwrap(base_yaw + math.atan2(q[1, 0], q[0, 0]))
    assert np.max(np.abs(h6.wrap_pi((gauge_yaw - gauge_yaw[0]) - (base_yaw - base_yaw[0])))) < 1.0e-15
    covariance = np.diag(np.linspace(0.1, 2.1, 21))
    transform = np.eye(21)
    for offset in range(0, 15, 3):
        transform[offset:offset + 3, offset:offset + 3] = q
    assert np.allclose(transform.T @ (transform @ covariance @ transform.T) @ transform, covariance, atol=2.0e-15)


def test_cached_epoch_aggregation_preserves_legacy_values_and_row_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(h6, "STATE_ROWS", 3)
    metric_map = {
        "orientation_geodesic_difference_rad": "orientation_geodesic_difference_rad",
        "velocity_difference_m_per_s": "velocity_difference_m_per_s",
        "position_difference_m": "position_difference_m",
        "maximum_matched_contact_position_difference_m": "contact_position_difference_m",
        "gyro_bias_difference_rad_per_s": "gyro_bias_difference_rad_per_s",
        "accelerometer_bias_difference_m_per_s2": "accelerometer_bias_difference_m_per_s2",
        "relative_yaw_increment_difference_rad": "relative_yaw_increment_difference_rad",
        "innovation_norm_difference": "innovation_norm_difference",
        "native_yaw_offset_residual_rad": "native_yaw_offset_residual_rad",
    }
    arrays = {"timestamp_ns": np.asarray([11, 12, 13], dtype=np.int64)}
    tolerances: dict[str, float] = {}
    for offset, (metric, tolerance) in enumerate(metric_map.items(), start=1):
        arrays[metric] = np.asarray([offset * 1.0e-7, offset * 2.0e-7, offset * 3.0e-7])
        tolerances[tolerance] = offset * 2.5e-7
    arrays["native_yaw_offset_rad"] = np.asarray([0.2, 0.2, 0.2])

    legacy_rows = []
    for index in range(3):
        passed = all(
            float(arrays[metric][index]) <= tolerances[tolerance]
            for metric, tolerance in metric_map.items()
        )
        legacy_rows.append({
            "run_id": "H6_YAW_P050", "initial_yaw_deg": 50.0, "row_index": index,
            **{name: arrays[name][index] for name in h6.EPOCH_METRIC_COLUMNS if name in arrays},
            "epoch_pass": passed,
        })

    cached_rows = list(h6._epoch_metric_rows_from_cached_arrays(
        "H6_YAW_P050", 50.0, arrays, tolerances, metric_map,
    ))
    assert [tuple(row) for row in cached_rows] == [tuple(row) for row in legacy_rows]
    assert cached_rows == legacy_rows


def test_maximal_constant_contact_segments_and_selection_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = _cache([15] * 25 + [3] * 30 + [0] * 22 + [1] * 25, dt=0.01)
    monkeypatch.setattr(h6, "STATE_ROWS", len(cache.timestamp_ns))
    segments = h6.enumerate_segments(cache)
    assert [(row.contact_mask, row.sample_count) for row in segments] == [(15, 25), (3, 30), (0, 22), (1, 25)]
    assert all(row.eligible for row in (segments[0], segments[1], segments[3]))
    assert segments[2].eligible is False
    monkeypatch.setattr(h6, "read_cache", lambda _path: cache)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    result = h6.freeze_window_selection(scratch, tmp_path / "cache.bin")
    assert result["svd_call_count_before_freeze"] == 0
    assert result["selection_forbidden_input_count"] == 0
    rows = h6._rows(scratch / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION/H6_OBSERVABILITY_WINDOW_SELECTION.csv")
    assert all(row["constant_contact_identity_set"] == "true" for row in rows)
    assert all(row["contact_boundary_inside_window"] == "false" for row in rows)


@pytest.mark.parametrize("contacts", [1, 2, 3, 4])
def test_ideal_four_dimensional_nullspace_and_rank_sensitivity(contacts: int) -> None:
    matrix = h6.ideal_observability(np.linspace(0.0, 0.4, 41), contacts)
    gauge = h6.gauge_basis(contacts, bias_augmented=False)
    rows, diagnostics, singular, complement = h6._observability_diagnostics(matrix, gauge, (0.1, 1.0, 10.0))
    assert all(row["rank"] == 5 + 3 * contacts and row["nullity"] == 4 for row in rows)
    assert diagnostics["o_times_g_normalized_residual"] < 1.0e-14
    assert diagnostics["smallest_non_gauge_singular_value"] > 0.0
    assert complement.shape == (9 + 3 * contacts, 5 + 3 * contacts)


def test_bias_augmented_phi_preserves_known_gauge_and_uses_correct_ordering() -> None:
    contacts = np.asarray([[1.0, 0.2, -0.4], [-0.3, 0.5, -0.4]])
    transition = h6.analytical_phi(
        h6.rotation_z(12.0), np.asarray([0.2, -0.1, 0.0]), np.asarray([1.0, 2.0, 0.1]),
        contacts, np.asarray([0.1, -0.04, 0.2]), np.asarray([0.3, -0.1, 9.2]), 0.004,
    )
    gauge = h6.gauge_basis(2, bias_augmented=True)
    measurement = h6.measurement_matrix(2, bias_augmented=True)
    assert transition.shape == (21, 21)
    assert np.linalg.norm(measurement @ transition @ gauge) < 1.0e-13
    assert np.count_nonzero(gauge[-6:]) == 0


def test_variable_dof_nis_and_zero_contact_exclusion() -> None:
    nis = np.asarray([0.0, 1.0, 2.0, 4.0])
    factorization = np.asarray([False, True, True, True])
    update = h6._nis_summary_row("CONTACT_COUNT", "CONTACT_COUNT_1", 1, np.asarray([1, 2]), nis, factorization)
    zero = h6._nis_summary_row("NO_CHI_SQUARE_UPDATE", "FLIGHT", 0, np.asarray([0]), nis, factorization)
    assert update["degrees_of_freedom"] == 3
    assert update["chi_square_updates_included"] is True
    assert 0.0 <= update["chi_square_central_95_coverage"] <= 1.0
    assert zero["chi_square_updates_included"] is False
    assert zero["chi_square_central_95_coverage"] == ""


def test_survivor_contact_set_differs_from_post_add_topology() -> None:
    current, added = 0b1111, 0b0100
    survivor = current & ~added
    assert h6.contact_set(survivor) == "FL+FR+RR"
    assert survivor.bit_count() == 3


def test_compact_artifact_schema_and_no_duplicate_payloads() -> None:
    assert "CONTACT_STATE.csv" not in h6.COMPACT_RUN_FILES
    assert "CONTACT_EVENT_LEDGER.csv" not in h6.COMPACT_RUN_FILES
    assert "KINEMATIC_INNOVATIONS.csv" not in h6.COMPACT_RUN_FILES
    assert "NIS_DIAGNOSTICS.csv" not in h6.COMPACT_RUN_FILES
    assert set(("NAV.csv", "COVARIANCE_CHECKPOINTS.npz", "NATIVE_CONFIG.yaml", "NATIVE_SUMMARY.json")) <= set(h6.COMPACT_RUN_FILES)


def test_no_reference_reader_or_h7_execution_interface() -> None:
    source = (PACKAGE_PATH / "hartley_h6.py").read_text()
    script = (REPO / "scripts/paper_rebuild/run_hartley_h6.py").read_text()
    assert "trace_path" not in source and "reference_path" not in source
    assert "run_h7" not in source + script and "EXT06" not in source + script
    assert "absolute_yaw_RMSE" in source and "absolute_position_RMSE" in source


def test_exclusive_copy_scratch_publication_parity(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(251)) * 40)
    destination = tmp_path / "published.bin"
    digest = h6.copy_exclusive(source, destination)
    assert destination.read_bytes() == source.read_bytes()
    assert digest == h6.sha256_file(source)
    with pytest.raises(FileExistsError):
        h6.copy_exclusive(source, destination)


def test_blocked_finalizer_and_guarded_publication_preserve_not_evaluated_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    repository = tmp_path / "repository"
    h5_anchor = tmp_path / "h5_anchor"
    stage = tmp_path / "stage"
    for path in (scratch / "00_ADMIN", repository / "contracts", h5_anchor, stage):
        path.mkdir(parents=True)
    contract = repository / "contracts/H6.yaml"
    contract.write_text("contract: frozen\n")
    for relative in (
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py",
        "scripts/paper_rebuild/run_hartley_h6.py",
        "tests/paper_rebuild/test_hartley_h6_contracts.py",
        "tests/paper_rebuild/test_hartley_h6_backend.py",
    ):
        source = repository / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"fixture: {relative}\n")
    (scratch / "00_ADMIN/H5_SCRATCH_CLEANUP_LEDGER.json").write_text(json.dumps({
        "deleted_root_count": 2, "bytes_reclaimed": 17,
        "accepted_v3_disposition": "RETAIN_WHILE_G_UNHEALTHY",
    }))
    (scratch / "00_ADMIN/H6_STORAGE_HEALTH_READ_ONLY.json").write_text(json.dumps({
        "HealthStatus": "Warning", "OperationalStatus": "Full Repair Needed",
        "repair_invoked": False,
    }))
    (scratch / "00_ADMIN/H6_TEST_RESULTS.json").write_text(json.dumps({"status": "PASS"}))
    runtime = [
        {
            "run_id": run_id, "initial_yaw_deg": yaw, "state_rows": h6.STATE_ROWS,
            "propagation_calls": h6.PROPAGATION_CALLS, "eq61_calls": h6.PROPAGATION_CALLS,
            "eq52_calls": 0, "threads_verified": True, "elapsed_seconds": 1.0,
        }
        for run_id, yaw, _ in h6.YAW_MEMBERS
    ]
    evidence = {
        "parity": {"parity_pass": True}, "parity_sha256": "a" * 64,
        "tolerance_registry_sha256": "b" * 64,
        "contact_failures": [{
            "run_id": run_id, "initial_yaw_deg": yaw,
            "maximum_matched_contact_position_difference_m": 0.0006,
            "frozen_tolerance_m": 0.0005,
        } for run_id, yaw, _ in h6.YAW_MEMBERS],
        "native_yaw_separation_max_residual_rad": 1.0e-9,
        "native_executable_sha256": "c" * 64,
        "native_scoped_source_manifest_sha256": "d" * 64,
        "equivalence_freeze_sha256": "e" * 64,
        "segment_count": 8, "zero_contact_segment_count": 2,
        "selection": {"selected_window_count_after_role_deduplication": 2},
        "selected_windows": [{
            "window_id": "W0", "start_row": "0", "end_row": "20",
            "contact_set": "FL+FR", "selection_roles": "earliest",
        }],
        "contract_path": contract, "contract_sha256": h6.sha256_file(contract),
        "runtime": runtime,
    }
    monkeypatch.setattr(h6, "_validate_blocked_prerequisites", lambda *_args: evidence)
    status = h6.finalize_blocked_h6(scratch, repository, h5_anchor)
    marker = h6.NOT_EVALUATED_AFTER_GAUGE_BLOCKER
    assert status["terminal_status"] == h6.BLOCKED_TERMINAL
    assert status["gauge_equivalence_pass"] is False
    assert status["ideal_observability_status"] == marker
    assert status["bias_augmented_observability_status"] == marker
    assert status["topology_conditioned_nis_status"] == marker
    assert status["h7_authorized"] is False and status["h7_executed"] is False
    assert status["observability_svd_call_count"] == 0

    report = scratch / "03_ANALYSIS/11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md"
    master = scratch / "H6_MASTER_FREEZE.json"
    monkeypatch.setattr(h6, "_blocked_publication_sources", lambda *_args: {
        "09_GAUGE_ENSEMBLE/00_CONTRACTS/H6.yaml": contract,
        "11_REPORT/LSE01_H6_GAUGE_AND_OBSERVABILITY_REPORT.md": report,
        "11_REPORT/H6_MASTER_FREEZE.json": master,
    })
    published = h6.publish_blocked_h6(scratch, repository, stage, h5_anchor)
    assert published["terminal_status"] == h6.BLOCKED_TERMINAL
    assert published["external_publication_all_bytes_equal"] is True
    parity = json.loads((scratch / "04_PUBLICATION/H6_EXTERNAL_PUBLICATION_PARITY.json").read_text())
    assert parity["all_published_bytes_equal"] is True
    assert (stage / "11_REPORT/LSE01_H6_STATUS.json").is_file()


def test_blocked_publication_excludes_unexecuted_observability_and_nis_products(tmp_path: Path) -> None:
    sources = h6._blocked_publication_sources(tmp_path / "scratch", tmp_path / "repository")
    assert not any("02_IDEAL_BIAS_FREE" in path for path in sources)
    assert not any("03_BIAS_AUGMENTED" in path for path in sources)
    assert not any("04_NIS_AND_COVARIANCE" in path for path in sources)
    assert "11_REPORT/H6_MASTER_FREEZE.json" in sources


def test_cpp_initial_gauge_helper_scope_and_zero_noop_branch() -> None:
    backend = (PACKAGE_PATH / "hartley_inekf/src/backend.cpp").read_text()
    runner = (PACKAGE_PATH / "hartley_inekf/tools/run_h5.cpp").read_text()
    assert "void HartleyInEkf::applyInitialGaugeTransform" in backend
    assert "contact.second = world_rotation * contact.second" in backend
    assert "transform * covariance_ * transform.transpose()" in backend
    assert "initial_gauge_yaw_deg != 0.0" in runner
    assert runner.index("initializeContactsEq32WithIndependentPrior") < runner.index("applyInitialGaugeTransform")
