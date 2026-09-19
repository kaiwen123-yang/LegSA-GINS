from __future__ import annotations

import csv
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
CONTRACT = REPO / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/HARTLEY_H6R_EXECUTION_CONTRACT.yaml"


def _isolated_h6r():
    package_name = "_test_hartley_h6r_contracts_isolated"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5", "hartley_h6", "hartley_h6r"):
        name = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / f"{basename}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h6r"], sys.modules[f"{package_name}.hartley_h6"]


h6r, h6 = _isolated_h6r()


def _write_old_contacts(path: Path, timestamps: np.ndarray, active: np.ndarray,
                        xyz: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("timestamp_ns", "row_index", "leg_id", "leg", "active",
                         "contact_x", "contact_y", "contact_z"))
        for row in range(len(timestamps)):
            for leg in range(4):
                values = xyz[row, leg] if active[row, leg] else ("", "", "")
                writer.writerow((timestamps[row], row, leg, h6r.LEGS[leg], int(active[row, leg]), *values))


def _write_npz(path: Path, timestamps: np.ndarray, active: np.ndarray, xyz: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path, timestamp_ns=timestamps.astype(np.int64),
        row_index=np.arange(len(timestamps), dtype=np.int64),
        active_mask=active.astype(np.bool_), contact_xyz=xyz.astype(np.float64),
        leg_ids=np.arange(4, dtype=np.int32), leg_names=np.asarray(h6r.LEGS, dtype="S2"),
    )


def _populate_core_outputs(scratch: Path) -> None:
    analysis = h6r._analysis_root(scratch)
    for relative in h6r.CORE_OUTPUT_RELATIVES:
        path = analysis / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            path.write_text("{}\n")
        elif path.suffix == ".md":
            path.write_text("# fixture\n")
        else:
            path.write_text("field\nvalue\n")


def test_frozen_identity_tolerance_hash_old_maxima_and_order_contract() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    assert contract["task_start_head"] == h6r.TASK_START_HEAD
    assert contract["method_id"] == h6r.METHOD_ID
    assert contract["backend_id"] == h6r.BACKEND_ID
    assert contract["process_profile"] == h6r.PROCESS_PROFILE
    original = contract["original_h6"]
    assert original["status"] == "BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE"
    assert original["immutable"] is True and original["outputs_overwritten_or_deleted"] is False
    assert original["contact_position_tolerance_m"] == h6r.CONTACT_TOLERANCE_M == 0.0005
    assert original["tolerance_registry_sha256"] == h6r.TOLERANCE_REGISTRY_SHA256
    assert original["tolerance_changed"] is False
    reproduction = contract["old_format_reproduction"]
    assert reproduction["comparison_order"] == "FREEZE_BEFORE_OPENING_FULL_PRECISION_NPZ"
    assert reproduction["tolerance_m"] == h6r.OLD_REPRODUCTION_TOLERANCE_M
    assert reproduction["changes_scientific_tolerance"] is False
    assert reproduction["frozen_maxima_m"] == h6r.EXPECTED_OLD_MAXIMA
    assert list(reproduction["frozen_maxima_m"]) == [
        "H6R_YAW_M150", "H6R_YAW_M100", "H6R_YAW_M050",
        "H6R_YAW_P050", "H6R_YAW_P100", "H6R_YAW_P150",
    ]


def test_full_precision_inverse_gauge_checks_every_epoch_and_active_identity() -> None:
    base_active = np.asarray([
        [True, False, True, False], [False, True, False, True], [False] * 4,
    ])
    base = np.full((3, 4, 3), np.nan)
    base[0, 0], base[0, 2] = [100.0, 2.0, -0.4], [99.5, 2.5, -0.4]
    base[1, 1], base[1, 3] = [101.0, -2.0, -0.4], [100.5, -2.5, -0.4]
    yaw = 50.0
    member = np.einsum("ij,nlj->nli", h6.rotation_z(yaw), base)
    epoch_max, coordinate = h6r._inverse_gauge_epoch_max(
        base_active, base, base_active.copy(), member, yaw,
    )
    assert epoch_max.shape == (3,) and coordinate.shape == (3, 4, 3)
    assert epoch_max[2] == 0.0
    assert np.nanmax(epoch_max) < 3.0e-14
    changed = base_active.copy(); changed[1, 3] = False
    with pytest.raises(h6r.HartleyH6RError, match="contact identity mismatch"):
        h6r._inverse_gauge_epoch_max(base_active, base, changed, member, yaw)


def test_old_blocker_is_frozen_before_authoritative_npz_and_fp_max_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(h6r, "STATE_ROWS", 3)
    scratch = tmp_path / "scratch"
    timestamps = np.asarray([10, 20, 30], dtype=np.int64)
    active = np.asarray([[True, True, False, False]] * 3, dtype=np.bool_)
    base = np.full((3, 4, 3), np.nan, dtype=np.float64)
    base[:, 0] = [[100.0, 1.0, -0.4], [100.1, 1.1, -0.4], [100.2, 1.2, -0.4]]
    base[:, 1] = [[100.0, -1.0, -0.4], [100.1, -1.1, -0.4], [100.2, -1.2, -0.4]]
    zero = h6r._member_root(scratch, "H6R_YAW_000")
    _write_old_contacts(zero / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv", timestamps, active, base)
    _write_npz(zero / "CONTACT_STATE_FLOAT64.npz", timestamps, active, base)
    expected: dict[str, float] = {}
    for offset, (run_id, yaw, _directory) in enumerate(h6r.YAW_MEMBERS):
        if yaw == 0.0:
            continue
        member_root = h6r._member_root(scratch, run_id)
        delta = (offset + 1) * 1.0e-4
        old_aligned = base.copy(); old_aligned[active] += np.asarray([delta, 0.0, 0.0])
        old_member = np.einsum("ij,nlj->nli", h6.rotation_z(yaw), old_aligned)
        _write_old_contacts(member_root / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv",
                            timestamps, active, old_member)
        parsed_base = h6r._old_contacts(zero / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv")
        parsed_member = h6r._old_contacts(member_root / "CONTACT_STATE_OLD_FORMAT_COMPAT.csv")
        expected[run_id] = float(np.max(h6r._inverse_gauge_epoch_max(
            parsed_base[1], parsed_base[2], parsed_member[1], parsed_member[2], yaw,
        )[0]))
        full_member = np.einsum("ij,nlj->nli", h6.rotation_z(yaw), base)
        _write_npz(member_root / "CONTACT_STATE_FLOAT64.npz", timestamps, active, full_member)
    for run_id, _yaw, _directory in h6r.YAW_MEMBERS:
        payload = {"non_contact_frozen_metric_parity_pass": True}
        if run_id == "H6R_YAW_000":
            payload["zero_degree_parity"] = {"old_format_contact_csv_byte_identical": True}
        (h6r._member_root(scratch, run_id) / "MEMBER_FREEZE.json").write_text(json.dumps(payload))
    monkeypatch.setattr(h6r, "EXPECTED_OLD_MAXIMA", expected)
    (scratch / "00_ADMIN").mkdir(parents=True)
    recovery_root = h6r._gauge_root(scratch) / "08_PRECISION_RECOVERY"
    recovery_root.mkdir(parents=True)
    (recovery_root / "H6R_CONTACT_SERIALIZATION_FORENSIC.json").write_text("{}\n")
    original_reader = h6r.read_contact_npz
    npz_opened = []

    def guarded_reader(path: Path):
        freeze = h6r._gauge_root(scratch) / "08_PRECISION_RECOVERY/OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"
        assert freeze.is_file(), "authoritative NPZ opened before old-format reproduction freeze"
        npz_opened.append(path)
        return original_reader(path)

    monkeypatch.setattr(h6r, "read_contact_npz", guarded_reader)
    result = h6r.aggregate_contact_recovery(scratch)
    assert result["old_format_blocker_reproduced"] is True
    assert result["full_precision_contact_gate_pass"] is True
    assert result["contact_tolerance_m"] == 0.0005
    assert len(npz_opened) == 7
    recovery = h6r._gauge_root(scratch) / "08_PRECISION_RECOVERY"
    old_rows = list(csv.DictReader((recovery / "OLD_FORMAT_QUANTIZATION_REPRODUCTION.csv").open()))
    full_rows = list(csv.DictReader((recovery / "FULL_PRECISION_CONTACT_EQUIVALENCE_SUMMARY.csv").open()))
    assert [row["run_id"] for row in old_rows] == list(expected)
    assert len(full_rows) == 6 and all(row["pass"] == "true" for row in full_rows)
    assert all(float(row["maximum_contact_vector_difference_m"]) <= 0.0005 for row in full_rows)
    ledger = [json.loads(line) for line in (
        scratch / "00_ADMIN/H6R_CONTACT_NPZ_ACCESS_LEDGER.jsonl"
    ).read_text().splitlines()]
    assert len(ledger) == 7
    assert all(row["old_format_freeze_sha256"] == h6r.sha256_file(
        recovery / "OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"
    ) for row in ledger)
    assert all(len(row["npz_sha256_after_old_format_freeze"]) == 64 for row in ledger)


def test_npz_is_not_read_or_hashed_before_old_format_freeze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(h6r, "STATE_ROWS", 1)
    scratch = tmp_path / "scratch"
    (scratch / "00_ADMIN").mkdir(parents=True)
    member = h6r._member_root(scratch, "H6R_YAW_000")
    member.mkdir(parents=True)
    raw = member / "CONTACT_STATE_FLOAT64.raw"
    raw.write_bytes(h6r.RAW_HEADER.pack(
        h6r.RAW_MAGIC, 1, h6r.RAW_HEADER.size, h6r.RAW_RECORD.size, 1, 0, 1, 2, 3,
    ) + h6r.RAW_RECORD.pack(
        1, 0, True, False, False, False, 1.0, 2.0, 3.0, *([float("nan")] * 9),
    ))
    npz = member / "CONTACT_STATE_FLOAT64.npz"
    original_load, original_hash = h6r.np.load, h6r.sha256_file
    loads = []
    hashes = []
    monkeypatch.setattr(h6r.np, "load", lambda *args, **kwargs: loads.append(args[0]))

    def guarded_hash(path: Path) -> str:
        hashes.append(Path(path))
        if Path(path).suffix == ".npz":
            raise AssertionError("NPZ hashed before old-format freeze")
        return original_hash(Path(path))

    monkeypatch.setattr(h6r, "sha256_file", guarded_hash)
    schema = h6r.convert_contact_raw(raw, npz)
    assert schema["npz_sha256"] == "DEFERRED_UNTIL_AFTER_OLD_FORMAT_REPRODUCTION_FREEZE"
    assert loads == [] and not [path for path in hashes if path.suffix == ".npz"]
    with pytest.raises(h6r.HartleyH6RError, match="old-format reproduction PASS marker absent"):
        h6r.read_contact_npz(npz)
    assert loads == [] and not [path for path in hashes if path.suffix == ".npz"]
    monkeypatch.setattr(h6r.np, "load", original_load)
    monkeypatch.setattr(h6r, "sha256_file", original_hash)
    freeze = h6r._gauge_root(scratch) / "08_PRECISION_RECOVERY/OLD_FORMAT_QUANTIZATION_REPRODUCTION_FREEZE.json"
    freeze.parent.mkdir(parents=True)
    freeze.write_text(json.dumps({"old_format_blocker_reproduced": True}))
    h6r.read_contact_npz(npz)
    record = json.loads((scratch / "00_ADMIN/H6R_CONTACT_NPZ_ACCESS_LEDGER.jsonl").read_text())
    assert record["role"].endswith("CONTACT_STATE_FLOAT64.npz")
    assert record["npz_sha256_after_old_format_freeze"] == h6r.sha256_file(npz)


def test_non_contact_frozen_metric_parity_excludes_only_contact_metric() -> None:
    source = (PACKAGE_PATH / "hartley_h6r.py").read_text()
    assert 'if key != "maximum_matched_contact_position_difference_m"' in source
    required = (
        '"NAV.csv"', '"non_contact_epoch_metric_arrays"', '"covariance_checkpoint_metrics"',
        '"CONTACT_EVENT_LEDGER.csv"', '"KINEMATIC_INNOVATIONS.csv"',
        '"NIS_DIAGNOSTICS.csv"', '"COVARIANCE_CHECKPOINTS.bin"',
    )
    assert all(token in source for token in required)
    assert '"non_contact_frozen_metric_parity_pass": parity' in source
    assert "if not parity:" in source


def test_exact_frozen_window_reuse_without_reselection_or_prefreeze_svd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    source = original / "03_ANALYSIS/10_OBSERVABILITY/01_WINDOW_SELECTION"
    source.mkdir(parents=True)
    csv_bytes = (
        "window_id,start_row,end_row,contact_set\n" +
        "".join(f"WIN{i:03d},{i * 10},{i * 10 + 9},FL+FR\n" for i in range(5))
    ).encode()
    freeze_bytes = json.dumps({"svd_call_count_before_freeze": 0}, sort_keys=True).encode()
    (source / "H6_OBSERVABILITY_WINDOW_SELECTION.csv").write_bytes(csv_bytes)
    (source / "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json").write_bytes(freeze_bytes)
    monkeypatch.setattr(h6r, "WINDOW_SELECTION_SHA256", h6r.sha256_file(
        source / "H6_OBSERVABILITY_WINDOW_SELECTION.csv"
    ))
    monkeypatch.setattr(h6r, "WINDOW_FREEZE_SHA256", h6r.sha256_file(
        source / "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"
    ))
    scratch = tmp_path / "scratch"
    (scratch / "00_ADMIN").mkdir(parents=True)
    (scratch / "00_ADMIN/H6R_GAUGE_EQUIVALENCE_PASS.json").write_text(
        json.dumps({"gauge_equivalence_pass": True})
    )
    result = h6r.reuse_frozen_windows(original, scratch)
    destination = h6r._observability_root(scratch) / "00_WINDOW_REUSE"
    assert result["selected_windows"] == [f"WIN{i:03d}" for i in range(5)]
    assert result["segment_count"] == 3358
    assert result["selection_recomputed"] is False
    assert result["svd_call_count_before_original_selection_freeze"] == 0
    assert result["one_contact_eligible_window"] == "UNAVAILABLE"
    assert result["three_contact_eligible_window"] == "UNAVAILABLE"
    assert (destination / "H6_OBSERVABILITY_WINDOW_SELECTION.csv").read_bytes() == csv_bytes
    assert (destination / "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json").read_bytes() == freeze_bytes


def test_observability_failure_preserves_all_transient_evidence_and_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    admin = scratch / "00_ADMIN"
    admin.mkdir(parents=True)
    (admin / "H6R_WINDOW_REUSE_PASS.json").write_text(json.dumps({"window_reuse_pass": True}))
    reuse = h6r._observability_root(scratch) / "00_WINDOW_REUSE"
    reuse.mkdir(parents=True)
    for name in ("H6_OBSERVABILITY_WINDOW_SELECTION.csv", "H6_OBSERVABILITY_WINDOW_SELECTION_FREEZE.json"):
        (reuse / name).write_text("fixture\n")

    def failing_analysis(temp: Path, _cache: Path, _anchor: Path):
        root = temp / "03_ANALYSIS/10_OBSERVABILITY"
        evidence = {
            "02_IDEAL_BIAS_FREE/OBSERVABILITY_SINGULAR_VALUES.csv": "svd\n",
            "02_IDEAL_BIAS_FREE/OBSERVABILITY_RANK_SENSITIVITY.csv": "rank\n",
            "02_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY.json": "{}\n",
            "03_BIAS_AUGMENTED/BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY.csv": "bias\n",
        }
        for relative, content in evidence.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        raise h6.HartleyH6Error("BLOCKED_LSE01_H6_IDEAL_NULLSPACE_FAILURE")

    monkeypatch.setattr(h6, "analyze_observability", failing_analysis)
    with pytest.raises(h6r.HartleyH6RError, match=h6r.BLOCKERS["ideal"]):
        h6r.analyze_observability_r1(scratch, tmp_path / "cache", tmp_path / "anchor")
    temp = admin / "H6R_ANALYSIS_COMPAT_TMP"
    assert temp.is_dir()
    manifest_path = (h6r._observability_root(scratch) / "FAILURE_EVIDENCE" /
                     h6r.BLOCKERS["ideal"] / "OBSERVABILITY_FAILURE_EVIDENCE_MANIFEST.json")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["transient_evidence_retained"] is True
    assert manifest["file_count"] == 6
    expected_suffixes = {
        "OBSERVABILITY_SINGULAR_VALUES.csv", "OBSERVABILITY_RANK_SENSITIVITY.csv",
        "OBSERVABILITY_NULLSPACE_SUMMARY.json", "BIAS_AUGMENTED_WEAK_DIRECTION_SUMMARY.csv",
    }
    assert expected_suffixes <= {Path(relative).name for relative in manifest["files"]}
    assert all(not Path(relative).is_absolute() for relative in manifest["files"])
    for relative, identity in manifest["files"].items():
        copied = manifest_path.parent / relative
        assert identity == {"sha256": h6r.sha256_file(copied), "size": copied.stat().st_size}


def test_principal_angle_csv_has_four_angles_per_model_window_tolerance(tmp_path: Path) -> None:
    rows = []
    for model in ("IDEAL_BIAS_FREE", "BIAS_AUGMENTED_REAL_TRAJECTORY"):
        for window in ("WIN000", "WIN001", "WIN002", "WIN003", "WIN004"):
            matrix = h6.ideal_observability(np.linspace(0.0, 0.4, 41), 2)
            rows.extend(h6r._principal_angle_rows(matrix, h6.gauge_basis(2, bias_augmented=False),
                                                  model, window))
    path = tmp_path / "OBSERVABILITY_PRINCIPAL_ANGLES_R1.csv"
    h6r.exclusive_csv(path, rows, tuple(rows[0]))
    parsed = list(csv.DictReader(path.open()))
    groups: dict[tuple[str, str, str], list[int]] = {}
    for row in parsed:
        key = (row["model"], row["window_id"], row["tolerance_multiplier"])
        groups.setdefault(key, []).append(int(row["principal_angle_index"]))
    assert len(groups) == 2 * 5 * 3
    assert all(sorted(indices) == [0, 1, 2, 3] for indices in groups.values())
    assert len(parsed) == 120


@pytest.mark.parametrize("contacts", [2, 4])
def test_ideal_bias_free_nullity_is_exactly_four(contacts: int) -> None:
    matrix = h6.ideal_observability(np.linspace(0.0, 0.4, 41), contacts)
    gauge = h6.gauge_basis(contacts, bias_augmented=False)
    rank_rows, diagnostics, singular, _complement = h6._observability_diagnostics(
        matrix, gauge, (0.1, 1.0, 10.0),
    )
    assert all(row["nullity"] == 4 for row in rank_rows)
    assert all(row["rank"] == 5 + 3 * contacts for row in rank_rows)
    assert gauge.shape[1] == 4 and singular.size == min(matrix.shape)
    assert diagnostics["o_times_g_normalized_residual"] < 1.0e-14
    assert all(row["gauge_to_numerical_nullspace_residual"] < 1.0e-14 for row in rank_rows)


def test_bias_augmented_known_gauge_is_preserved_not_relabelled() -> None:
    contacts = np.asarray([[1.0, 0.2, -0.4], [-0.3, 0.5, -0.4]])
    transition = h6.analytical_phi(
        h6.rotation_z(12.0), np.asarray([0.2, -0.1, 0.0]),
        np.asarray([1.0, 2.0, 0.1]), contacts,
        np.asarray([0.1, -0.04, 0.2]), np.asarray([0.3, -0.1, 9.2]), 0.004,
    )
    gauge = h6.gauge_basis(2, bias_augmented=True)
    measurement = h6.measurement_matrix(2, bias_augmented=True)
    assert gauge.shape == (21, 4)
    assert np.linalg.norm(measurement @ transition @ gauge) < 1.0e-13
    assert np.count_nonzero(gauge[-6:]) == 0
    contract = yaml.safe_load(CONTRACT.read_text())
    assert contract["observability"]["additional_bias_augmented_small_singular_values_are_structural_gauges"] is False


def test_variable_dof_nis_tail_fields_and_zero_contact_exclusion() -> None:
    nis = np.asarray([0.0, 0.1, 1.0, 2.0, 4.0, 8.0])
    factorization = np.asarray([False, True, True, True, True, True])
    update = h6._nis_summary_row(
        "CONTACT_COUNT", "CONTACT_COUNT_2", 2, np.asarray([1, 2, 3, 4, 5]), nis, factorization,
    )
    zero = h6._nis_summary_row(
        "NO_CHI_SQUARE_UPDATE", "FLIGHT", 0, np.asarray([0]), nis, factorization,
    )
    assert update["degrees_of_freedom"] == 6
    assert update["chi_square_updates_included"] is True
    assert 0.0 <= update["chi_square_central_95_coverage"] <= 1.0
    assert update["chi_square_pvalue_p01"] <= update["chi_square_pvalue_p99"]
    assert zero["degrees_of_freedom"] == ""
    assert zero["chi_square_updates_included"] is False
    assert zero["chi_square_central_95_coverage"] == ""
    source = (PACKAGE_PATH / "hartley_h6r.py").read_text()
    assert 'row["lower_tail_rate"]' in source and 'row["upper_tail_rate"]' in source
    assert '"RECOMPUTED_FROM_FROZEN_GROUP"' not in source


def test_no_reference_h7_ext_or_other_method_interface() -> None:
    source = (PACKAGE_PATH / "hartley_h6r.py").read_text()
    lower = source.lower()
    forbidden_interfaces = (
        "trace_path", "reference_path", "run_h7", "run_ext06", "absolute_yaw_rmse(",
        "absolute_position_rmse(", "relative_pose_error(", "gnss_path", "legsa_output_path",
    )
    assert not [token for token in forbidden_interfaces if token in lower]
    status = h6r.status_template(h6r.PASS_TERMINAL)
    for field in (
        "reference_open_count", "trace_open_count", "GNSS_input_count",
        "Go2_onboard_pose_or_yaw_input_count", "LegSA_output_input_count", "EXT_output_input_count",
    ):
        assert status[field] == 0
    assert status["h7_executed"] is False and status["ext06_executed"] is False


def test_exclusive_compact_publication_preserves_original_h6_root(tmp_path: Path) -> None:
    scratch, stage = tmp_path / "scratch", tmp_path / "stage"
    analysis = scratch / "03_ANALYSIS"
    (scratch / "00_ADMIN").mkdir(parents=True)
    (scratch / "00_ADMIN/ORIGINAL_H6_PRE_RECOVERY_PRESERVATION.json").write_text(
        json.dumps({"files": {}})
    )
    (scratch / "00_ADMIN/H6R_LOCAL_PATH_BINDINGS.json").write_text(json.dumps({
        "external_stage": str(stage),
    }))
    (analysis / "11_REPORT").mkdir(parents=True)
    (scratch / "04_PUBLICATION").mkdir(parents=True)
    _populate_core_outputs(scratch)
    (analysis / "11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md").write_text("H6R\n")
    status_path = analysis / "11_REPORT/LSE01_H6R_STATUS.json"
    report_path = analysis / "11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md"
    status_path.write_text(json.dumps({"terminal_status": h6r.PASS_TERMINAL}) + "\n")
    complete_core = h6r._core_output_identities(scratch, include_reports=True)
    core_freeze = analysis / "11_REPORT/H6R_CORE_OUTPUT_FREEZE.json"
    core_freeze.write_text(json.dumps({
        "all_mandatory_core_outputs_present": True, "files": complete_core,
    }, sort_keys=True))
    (scratch / "00_ADMIN/H6R_FINALIZED_PASS.json").write_text(json.dumps({
        "finalized_pass": True, "terminal_status": h6r.PASS_TERMINAL,
        "status_sha256": h6r.sha256_file(status_path),
        "report_sha256": h6r.sha256_file(report_path),
        "core_output_freeze_sha256": h6r.sha256_file(core_freeze),
    }))
    original = stage / "09_GAUGE_ENSEMBLE/original-blocked.txt"
    original.parent.mkdir(parents=True)
    original.write_text("immutable blocked H6\n")
    (scratch / "00_ADMIN/ORIGINAL_H6_PRE_RECOVERY_PRESERVATION.json").write_text(json.dumps({
        "files": {str(original): {"sha256": h6r.sha256_file(original), "size": original.stat().st_size}},
    }))
    wrong_stage = tmp_path / "wrong-stage"
    with pytest.raises(h6r.HartleyH6RError, match="stage root identity mismatch"):
        h6r.publish_exclusive(scratch, wrong_stage)
    assert not wrong_stage.exists()
    result = h6r.publish_exclusive(scratch, stage)
    assert result["all_published_bytes_equal"] is True
    assert result["original_h6_publication_paths_touched"] is False
    assert result["local_preflight_complete_before_first_write"] is True
    assert result["manifest_published_bytes_equal"] is True
    assert result["parity_file_published_bytes_equal"] is True
    assert result["preservation_proof_published_bytes_equal"] is True
    assert result["original_h6_post_publication_preserved"] is True
    assert original.read_text() == "immutable blocked H6\n"
    assert all(not relative.startswith("09_GAUGE_ENSEMBLE/") for relative in h6r.publication_sources(scratch))
    local_prefix = str(tmp_path)
    for path in stage.rglob("*.json"):
        assert local_prefix not in path.read_text(), path
    with pytest.raises(FileExistsError):
        h6r.publish_exclusive(scratch, stage)


def test_core_outputs_are_hash_bound_and_missing_file_blocks_finalize_and_publish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    _populate_core_outputs(scratch)
    identities = h6r._core_output_identities(scratch)
    assert set(identities) == set(h6r.CORE_OUTPUT_RELATIVES)
    assert all(len(identity["sha256"]) == 64 and identity["size"] > 0
               for identity in identities.values())
    missing_relative = h6r.CORE_OUTPUT_RELATIVES[-1]
    (h6r._analysis_root(scratch) / missing_relative).unlink()
    with pytest.raises(h6r.HartleyH6RError, match="mandatory H6R core output absent"):
        h6r._core_output_identities(scratch)

    admin = scratch / "00_ADMIN"
    admin.mkdir(parents=True)
    (admin / "H6R_NIS_COVARIANCE_PASS.json").write_text(json.dumps({"nis_covariance_pass": True}))
    evidence = {
        h6r._gauge_root(scratch) / "08_PRECISION_RECOVERY/CONTACT_PRECISION_RECOVERY_FREEZE.json": {
            "full_precision_contact_gate_pass": True,
        },
        h6r._gauge_root(scratch) / "09_EQUIVALENCE/H6R_GAUGE_EQUIVALENCE_FREEZE.json": {
            "gauge_equivalence_pass": True,
        },
        h6r._observability_root(scratch) / "02_BIAS_AUGMENTED/OBSERVABILITY_ANALYSIS_FREEZE_R1.json": {
            "ideal_rank_nullity_pass": True, "bias_augmented_known_gauge_confirmed": True,
        },
        h6r._observability_root(scratch) / "03_NIS_AND_COVARIANCE/NIS_AND_COVARIANCE_FREEZE_R1.json": {},
    }
    for path, payload in evidence.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    monkeypatch.setattr(h6r, "verify_original_h6_post", lambda *_args, **_kwargs: {
        "all_original_h6_bytes_preserved": True,
    })
    with pytest.raises(h6r.HartleyH6RError, match="mandatory H6R core output absent"):
        h6r.finalize(scratch, tmp_path / "original-h6")

    stage = tmp_path / "stage"
    report_root = h6r._analysis_root(scratch) / "11_REPORT"
    report_root.mkdir(parents=True)
    status = report_root / "LSE01_H6R_STATUS.json"
    report = report_root / "LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md"
    status.write_text(json.dumps({"terminal_status": h6r.PASS_TERMINAL}))
    report.write_text("H6R\n")
    core_freeze = report_root / "H6R_CORE_OUTPUT_FREEZE.json"
    core_freeze.write_text(json.dumps({"all_mandatory_core_outputs_present": True, "files": identities}))
    (admin / "H6R_FINALIZED_PASS.json").write_text(json.dumps({
        "finalized_pass": True, "terminal_status": h6r.PASS_TERMINAL,
        "status_sha256": h6r.sha256_file(status), "report_sha256": h6r.sha256_file(report),
        "core_output_freeze_sha256": h6r.sha256_file(core_freeze),
    }))
    (admin / "H6R_LOCAL_PATH_BINDINGS.json").write_text(json.dumps({"external_stage": str(stage)}))
    with pytest.raises(h6r.HartleyH6RError, match="mandatory H6R core output absent"):
        h6r.publish_exclusive(scratch, stage)
    assert not stage.exists()


def test_exact_blocked_finalization_is_fail_closed_and_idempotent(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    terminal = h6r.BLOCKERS["contact"]
    raw = scratch / "01_NATIVE_RAW_H6R/H6R_YAW_M050"
    raw.mkdir(parents=True)
    (raw / "CONTACT_STATE_FLOAT64.raw").write_bytes(b"packed failure evidence")
    (raw / "CONTACT_STATE_FLOAT64.npz").write_bytes(b"unopened NPZ evidence")
    first = h6r.finalize_blocked(scratch, terminal, "full precision maximum exceeded")
    status_path = h6r._analysis_root(scratch) / "11_REPORT/LSE01_H6R_STATUS.json"
    first_bytes = status_path.read_bytes()
    second = h6r.finalize_blocked(scratch, terminal, "later text must not overwrite")
    assert first["terminal_status"] == second["terminal_status"] == terminal
    assert first["authoritative_blocker"] == terminal
    assert first["later_gates_executed"] is False
    assert first["raw_failure_evidence_retained"] is True
    npz_identity = first["retained_failure_evidence"][
        "01_NATIVE_RAW_H6R/H6R_YAW_M050/CONTACT_STATE_FLOAT64.npz"
    ]
    assert npz_identity["sha256"] == "NOT_OPENED_OR_HASHED_BEFORE_OLD_FORMAT_FREEZE"
    assert first["h7_executed"] is False and first["ext06_executed"] is False
    assert status_path.read_bytes() == first_bytes
    with pytest.raises(h6r.HartleyH6RError, match="invalid H6R blocker terminal"):
        h6r.finalize_blocked(scratch, "BLOCKED_UNREGISTERED", "invalid")


def test_ext4_guard_accepts_only_linux_local_filesystems(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class Completed:
        def __init__(self, filesystem: str):
            self.stdout = filesystem + "\n"
            self.returncode = 0

    monkeypatch.setattr(h6r.subprocess, "run", lambda *_args, **_kwargs: Completed("ext4"))
    h6r._require_ext4(tmp_path)
    monkeypatch.setattr(h6r.subprocess, "run", lambda *_args, **_kwargs: Completed("9p"))
    with pytest.raises(h6r.HartleyH6RError, match=h6r.BLOCKERS["storage"]):
        h6r._require_ext4(tmp_path)


def test_scoped_source_manifest_requires_clean_head_blobs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    scoped_paths = set(h6r.APPROVED_CHANGED_PATHS) | {
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h6.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/CMakeLists.txt",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp",
        "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp",
    }
    for relative in scoped_paths:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((relative + "\n").encode())

    class Completed:
        def __init__(self, stdout: bytes | str = b"", returncode: int = 0):
            self.stdout = stdout
            self.stderr = b""
            self.returncode = returncode

    def clean_git(command, **_kwargs):
        if command[1:3] == ["rev-parse", "HEAD"]:
            return Completed(h6r.TASK_START_HEAD + "\n")
        if command[1:3] == ["merge-base", "--is-ancestor"]:
            return Completed(returncode=0)
        if command[1] == "show":
            relative = command[2].split("HEAD:", 1)[1]
            return Completed((repository / relative).read_bytes())
        if command[1:3] == ["status", "--porcelain=v1"]:
            return Completed("" if _kwargs.get("text") else b"")
        raise AssertionError(command)

    monkeypatch.setattr(h6r.subprocess, "run", clean_git)
    digest, commit, identities = h6r._scoped_source_manifest(repository)
    assert len(digest) == 64 and commit == h6r.TASK_START_HEAD
    assert set(identities) == scoped_paths

    original_run = clean_git
    dirty = h6r.APPROVED_CHANGED_PATHS[0]

    def stale_blob(command, **kwargs):
        if command[1] == "show" and command[2] == f"HEAD:{dirty}":
            return Completed(b"stale committed blob\n")
        return original_run(command, **kwargs)

    monkeypatch.setattr(h6r.subprocess, "run", stale_blob)
    with pytest.raises(h6r.HartleyH6RError, match="not byte-identical to HEAD"):
        h6r._scoped_source_manifest(repository)


def test_required_terminal_statuses_and_pass_status_fields_are_exact() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    assert contract["terminal_statuses"]["pass"] == h6r.PASS_TERMINAL
    assert set(contract["terminal_statuses"]["blockers"]) == set(h6r.BLOCKERS.values())
    assert len(h6r.BLOCKERS) == 6
    status = h6r.status_template(h6r.PASS_TERMINAL)
    required = {
        "original_h6_status_preserved": True,
        "original_tolerance_changed": False,
        "old_format_blocker_reproduced": True,
        "full_precision_contact_gate_pass": True,
        "gauge_equivalence_pass": True,
        "ideal_observability_gauge_dimension": 4,
        "bias_augmented_known_gauge_confirmed": True,
        "reference_open_count": 0,
        "trace_open_count": 0,
        "h7_authorized": True,
    }
    assert {key: status[key] for key in required} == required
    assert status["h7_executed"] is False


def test_storage_and_cleanup_authority_preserve_both_transactions() -> None:
    contract = yaml.safe_load(CONTRACT.read_text())
    storage = contract["storage"]
    assert storage["execution_filesystem"] == "LINUX_LOCAL_EXT4_SCRATCH"
    assert storage["external_health_query_read_only"] is True
    assert storage["repair_authorized"] is False
    assert storage["publication"] == "EXCLUSIVE_CREATE_WITH_HASH_PARITY"
    assert storage["cleanup_authority"] == "SUPERVISOR_ONLY_AFTER_FINAL_PROOF"
    assert storage["worker_deletes_original_h6_scratch"] is False
    assert storage["retain_h6r_scratch_while_external_storage_unhealthy"] is True
