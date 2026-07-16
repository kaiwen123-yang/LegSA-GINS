from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild import clean2_evaluator as evaluator
from legsa_gins.paper_rebuild.clean2_plots import _reasonable_x_range


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_runtime_and_seal(tmp_path: Path) -> tuple[Path, Path, dict]:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    registry = tmp_path / "registry.csv"
    registry.write_text("fixture\n", encoding="utf-8")
    runs = []
    for order in range(1, 111):
        run_id = f"R{order:03d}"
        attempt = runtime / run_id / "attempts/attempt_1"
        attempt.mkdir(parents=True)
        files = []
        for role, name, content in (
            ("exact_nav", "KF_GINS_Navresult.nav", f"2300 {65 + order / 1000:.3f} 0\n"),
            ("exact_std", "KF_GINS_STD.txt", "1 1\n"),
            ("gnss_action_trace", "PORT_GNSS_UPDATE_TRACE.csv", "gnss_time,yaw_update,yaw_mode\n66,0,NONE\n"),
        ):
            path = attempt / name
            path.write_text(content, encoding="utf-8")
            files.append({
                "role": role,
                "relative_path": f"{run_id}/attempts/attempt_1/{name}",
                "sha256": _sha(path),
                "size_bytes": path.stat().st_size,
            })
        runs.append({
            "run_id": run_id,
            "run_order": order,
            "feature_SA": False,
            "files": files,
        })
    seal = {
        "registry_sha256": _sha(registry),
        "unique_formal_run_count": 110,
        "runs": runs,
    }
    return runtime, registry, seal


def _write_complete_evaluation_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "offline"
    root.mkdir()
    results = []
    seal_hash = "2" * 64
    registry_hash = "7" * 64
    attempts_hash = "8" * 64
    attempts_audit_hash = "9" * 64
    for order in range(1, 111):
        run_id = f"R{order:03d}"
        run_root = root / run_id
        run_root.mkdir()
        row = {
            "time": "66.0",
            "err_n_m": "3.0",
            "err_e_m": "4.0",
            "err_u_m": "-2.0",
            "horizontal_err_m": "5.0",
            "roll_err_deg": "1.0",
            "pitch_err_deg": "-1.0",
            "yaw_err_deg": "2.0",
        }
        errors = run_root / "error_series.csv.gz"
        with gzip.open(errors, "wt", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        aggregate = evaluator.aggregate_exact_error_rows([row], output_epoch_count=1)
        exact_summary = {
            "meta": {"num_samples": 1},
            "position": {
                "north_rmse_m": 3.0,
                "east_rmse_m": 4.0,
                "up_rmse_m": 2.0,
                "horizontal_rmse_m": 5.0,
            },
            "attitude": {
                "roll_rmse_deg": 1.0,
                "pitch_rmse_deg": 1.0,
                "yaw_rmse_deg": 2.0,
            },
        }
        exact_summary_path = run_root / "exact_evaluator_summary.json"
        exact_summary_path.write_text(json.dumps(exact_summary), encoding="utf-8")
        summary = {
            "schema_version": "paper_rebuild.clean2_exact_summary.v2",
            "run_id": run_id,
            "trace_used_online": False,
            "all_outputs_sealed_before_trace": True,
            "no_offset_search": True,
            "no_alignment": True,
            "no_output_correction": True,
            "epoch_deleted_for_metric": False,
            "exact_evaluator_sha256": evaluator.EXACT_EVALUATOR_SHA256,
            "trace_sha256": evaluator.EXPECTED_TRACE_SHA256,
            **aggregate,
        }
        summary_path = run_root / "summary.json"
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        coverage = {
            "run_id": run_id,
            "output_epoch_count": 1,
            "matched_epoch_count": 1,
            "unmatched_epoch_count": 0,
            "coverage": 1.0,
            "exact_archived_evaluator_overlap_policy": True,
        }
        coverage_path = run_root / "coverage.json"
        coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
        manifest = {
            "schema_version": "paper_rebuild.clean2_exact_evaluator_manifest.v2",
            "run_id": run_id,
            "nav_sha256": "4" * 64,
            "std_sha256": "5" * 64,
            "trace_sha256": evaluator.EXPECTED_TRACE_SHA256,
            "exact_evaluator_sha256": evaluator.EXACT_EVALUATOR_SHA256,
            "execution_protocol_sha256": "6" * 64,
            "complete_output_seal_sha256": seal_hash,
            "registry_sha256": registry_hash,
            "run_attempts_sha256": attempts_hash,
            "run_attempts_audit_sha256": attempts_audit_hash,
            "exact_summary_sha256": _sha(exact_summary_path),
            "error_series_gzip_sha256": _sha(errors),
            "summary_sha256": _sha(summary_path),
            "coverage_sha256": _sha(coverage_path),
            "exact_summary_row_crosscheck": evaluator._assert_exact_summary(
                exact_summary, aggregate
            ),
            "aggregate_crosscheck": True,
            "trace_opened_offline_after_complete_110_seal": True,
            "passed": True,
        }
        manifest_path = run_root / "evaluator_manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        results.append({
            "run_id": run_id,
            "summary": summary,
            "error_series": str(errors),
            "summary_path": str(summary_path),
            "coverage_path": str(coverage_path),
            "exact_summary_path": str(exact_summary_path),
            "evaluator_manifest_path": str(manifest_path),
            "port_gnss_update_trace": "",
            "source_aware_weight_trace": "",
        })
    index = root / "CLEAN2_OFFLINE_EVALUATION_INDEX.json"
    index.write_text(
        json.dumps({
            "schema_version": "paper_rebuild.clean2_offline_evaluation_index.v2",
            "run_count": 110,
            "all_110_outputs_validated_before_trace": True,
            "all_outputs_sealed_before_trace": True,
            "trace_used_online": False,
            "exact_evaluator_sha256": evaluator.EXACT_EVALUATOR_SHA256,
            "trace_sha256": evaluator.EXPECTED_TRACE_SHA256,
            "solver_artifact_index_sha256": "3" * 64,
            "complete_output_seal_sha256": seal_hash,
            "registry_sha256": registry_hash,
            "run_attempts_sha256": attempts_hash,
            "run_attempts_audit_sha256": attempts_audit_hash,
            "all_110_attempt_histories_validated_before_trace": True,
            "terminal_attempt_audit_validated_before_trace": True,
            "results": results,
            "passed": True,
        }),
        encoding="utf-8",
    )
    return index


def test_structured_artifact_index_is_derived_from_seal_and_rehashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, registry, seal = _fake_runtime_and_seal(tmp_path)
    monkeypatch.setattr(evaluator, "validate_complete_output_seal", lambda *args, **kwargs: seal)
    seal_path = tmp_path / "seal.json"
    seal_path.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "index.json"
    payload = evaluator.build_solver_artifact_index(
        complete_output_seal_path=seal_path,
        runtime_root=runtime,
        registry_path=registry,
        output_path=output,
    )
    assert payload["run_count"] == 110
    loaded = evaluator.load_solver_artifact_index(output)
    validation = evaluator.validate_sealed_solver_artifact_index(
        artifact_index=loaded,
        complete_output_seal_path=seal_path,
        require_action_traces=True,
    )
    assert validation["nav_std_artifact_count"] == 220
    assert validation["action_artifact_count"] == 110


def test_structured_artifact_index_rejects_post_index_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, registry, seal = _fake_runtime_and_seal(tmp_path)
    monkeypatch.setattr(evaluator, "validate_complete_output_seal", lambda *args, **kwargs: seal)
    seal_path = tmp_path / "seal.json"
    seal_path.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "index.json"
    evaluator.build_solver_artifact_index(
        complete_output_seal_path=seal_path,
        runtime_root=runtime,
        registry_path=registry,
        output_path=output,
    )
    (runtime / "R001/attempts/attempt_1/KF_GINS_Navresult.nav").write_text(
        "tampered\n", encoding="utf-8"
    )
    with pytest.raises(Exception, match="hash changed"):
        evaluator.load_solver_artifact_index(output)


def test_plot_x_range_requires_frozen_time_window_or_contiguous_categories() -> None:
    assert _reasonable_x_range("time_series", [66.0, 100.0, 340.0])
    assert not _reasonable_x_range("time_series", [65.9, 100.0])
    assert not _reasonable_x_range("time_series", [66.0, 341.0])
    assert _reasonable_x_range("bar", [0.0, 1.0, 2.0])
    assert not _reasonable_x_range("bar", [0.0, 2.0])


def test_trace_hash_argument_cannot_select_a_different_reference(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="frozen CLEAN1 anchor"):
        evaluator._verify_offline_trace(tmp_path / "not-opened.trace", "0" * 64)


def test_offline_index_revalidates_all_110_artifact_sets(tmp_path: Path) -> None:
    index = _write_complete_evaluation_fixture(tmp_path)
    summaries, checks = evaluator.load_and_crosscheck_evaluation_index(index)
    assert len(summaries) == 110
    assert checks["independent_row_recomputation_count"] == 110
    assert checks["passed"] is True


def test_offline_index_rejects_post_manifest_coverage_mutation(tmp_path: Path) -> None:
    index = _write_complete_evaluation_fixture(tmp_path)
    coverage = index.parent / "R001/coverage.json"
    payload = json.loads(coverage.read_text(encoding="utf-8"))
    payload["coverage"] = 0.5
    coverage.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exception, match="AGGREGATE_CROSSCHECK"):
        evaluator.load_and_crosscheck_evaluation_index(index)
