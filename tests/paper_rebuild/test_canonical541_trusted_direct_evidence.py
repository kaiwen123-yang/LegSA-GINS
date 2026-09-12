import csv
import gzip
import json
import zipfile
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541 import trusted_direct_evidence as direct
from legsa_gins.paper_rebuild.canonical541.evidence import sha256_file


def _csv(path: Path, rows, *, gz: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(rows)
    opener = gzip.open if gz else open
    with opener(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialized[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    stage = tmp_path / "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX" / ".attempt_test"
    export = tmp_path / "export"
    stage.mkdir(parents=True)
    export.mkdir()
    config = tmp_path / "local.yaml"
    config.write_text(f"paths:\n  runtime_root: {stage}\n  export_root: {export}\n", encoding="utf-8")

    terminal = "COMPLETED_EVALUABLE"
    unique = [{"run_id": f"R{i:05d}", "terminal_status": terminal} for i in range(5951)]
    logical = [{"logical_id": f"L{i:05d}", "run_id": f"R{i % 5951:05d}",
                "terminal_status": terminal} for i in range(7033)]
    _csv(stage / direct.REGISTRY_PATHS[0], ({"logical_id": f"F{i}"} for i in range(2164)))
    _csv(stage / direct.REGISTRY_PATHS[1], unique)
    _csv(stage / direct.REGISTRY_PATHS[2], ({"run_id": f"R{i:05d}"} for i in range(5951)))
    _json(stage / direct.REGISTRY_PATHS[3], {"method_bound_completed": 5951,
                                             "unique_runs_planned": 5951})
    _json(stage / direct.REGISTRY_PATHS[4], {
        "logical_row_count": 7033, "full_logical_row_count": 2164,
        "ablation_logical_row_count": 4869, "unique_run_count": 5951, "passed": True,
    })
    _csv(stage / direct.REGISTRY_PATHS[5], ({"logical_id": f"A{i}"} for i in range(4869)))

    seal = stage / "11_OUTPUT_SEAL"
    # This nonexistent runtime path is intentional: trusted-direct closure must
    # validate the generated seal registry without opening or rehashing NAV.
    _csv(seal / "OUTPUT_HASH_MANIFEST.csv", [{
        "run_id": "R00000", "run_root": str(tmp_path / "must_not_be_opened"),
        "relative_path": "outputs/result.nav", "terminal_status": terminal,
        "sealed_before_trace": "True", "size_bytes": "123", "sha256": "a" * 64,
    }])
    _csv(seal / "UNIQUE_RUN_TERMINAL_REGISTRY.csv", unique)
    _csv(seal / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv", logical)
    _csv(seal / "RUN_ATTEMPTS.csv", [{"attempt_id": "one"}])
    _json(seal / "OUTPUT_SEAL_JOURNAL.json", {
        "unique_run_count": 5951, "logical_result_count": 7033,
        "full_algorithm_logical_rows": 2164, "internal_ablation_logical_rows": 4869,
        "all_hashes_recorded": True, "all_logical_rows_terminal": True,
        "sealed_before_offline_trace": True, "trace_open_count_before_seal": 0,
        "manifest_sha256": sha256_file(seal / "OUTPUT_HASH_MANIFEST.csv"),
        "unique_registry_sha256": sha256_file(seal / "UNIQUE_RUN_TERMINAL_REGISTRY.csv"),
        "logical_registry_sha256": sha256_file(seal / "LOGICAL_RESULT_TERMINAL_REGISTRY.csv"),
        "run_attempts_sha256": sha256_file(seal / "RUN_ATTEMPTS.csv"),
        "run_attempt_count": 1, "file_count": 1, "passed": True,
    })

    full = ({"method_id": f"F{method:02d}",
             "case_id": "C00_clean_normal" if case == 0 else f"C{case:03d}",
             "logical_id": f"F{method:02d}_{case:03d}",
             "run_id": f"R{((method - 1) * 541 + case) % 5951:05d}",
             "terminal_status": terminal}
            for method in range(1, 5) for case in range(541))
    ablation = ({"method_id": f"A{method:02d}",
                 "case_id": "C00_clean_normal" if case == 0 else f"C{case:03d}",
                 "logical_id": f"A{method:02d}_{case:03d}",
                 "run_id": f"R{(2164 + (method - 1) * 541 + case) % 5951:05d}",
                 "terminal_status": terminal}
                for method in range(1, 10) for case in range(541))
    analysis = stage / "13_RESULT_ANALYSIS"
    _csv(analysis / direct.ANALYSIS_FILES["full_rows"], full, gz=True)
    _csv(analysis / direct.ANALYSIS_FILES["ablation_rows"], ablation, gz=True)
    for key, name in direct.ANALYSIS_FILES.items():
        if key not in {"full_rows", "ablation_rows"}:
            _csv(analysis / name, [{"value": "1"}], gz=name.endswith(".gz"))
    for name in direct.ANALYSIS_SUPPORT:
        if name.endswith(".json"):
            _json(analysis / name, {"passed": True})
        else:
            _csv(analysis / name, [{"value": "1"}])
    mechanism = stage / "14_MECHANISM_ANALYSIS"
    _csv(mechanism / direct.MECHANISM_FILES["source_aware_actions"], [{"value": "1"}], gz=True)
    _csv(mechanism / direct.MECHANISM_FILES["schemec_actions"], [{"value": "1"}])
    _csv(mechanism / "SOURCE_ISOLATION_AUDIT.csv", [{"passed": "True"}])
    _json(stage / "12_OFFLINE_EVALUATION/AGGREGATE_CROSSCHECK.json", {"passed": True})
    return stage, export, config


def _fake_figures(*, tables, output_root, table_hashes):
    output = Path(output_root)
    output.mkdir(parents=True)
    for stem, _ in direct.FIGURE_SPECS:
        (output / f"{stem}.png").write_bytes(b"png")
        (output / f"{stem}.pdf").write_bytes(b"%PDF")
    report = {"passed": True, "figure_count": 25}
    _json(output / "FIGURE_RENDER_QA.json", report)
    return report


def test_trusted_direct_packages_only_generated_artifacts_without_runtime_rehash(tmp_path, monkeypatch):
    stage, export, config = _fixture(tmp_path)
    monkeypatch.setattr(direct, "render_diagnostic_figures", _fake_figures)
    report = direct.package_trusted_direct(
        local_config=config, stage_root=stage, export_root=export,
        attempt_id="direct_1", timestamp="20260809T120000P0800",
    )
    assert report["passed"] is True
    closure = json.loads((stage / "DIRECT_EVIDENCE_CLOSURE.json").read_text(encoding="utf-8"))
    assert closure["terminal_registry_counts"]["unique_terminal_count"] == 5951
    assert closure["terminal_registry_counts"]["logical_terminal_count"] == 7033
    assert closure["runtime_output_payload_rehash_performed"] is False
    assert closure["raw_payload_rehash_performed"] is False
    with zipfile.ZipFile(report["archive"]["zip_path"]) as archive:
        names = set(archive.namelist())
    assert "EVIDENCE_MANIFEST.csv" in names and "EVIDENCE_MANIFEST.sha256" in names
    assert not any(name.startswith(("08_FULL_ALGORITHM_RUNS/", "10_INTERNAL_ABLATION_RUNS/")) for name in names)
    assert not any(Path(name).suffix.lower() in {".nav", ".std", ".imu", ".gnss"} for name in names)


def test_trusted_direct_rejects_unresolved_terminal_registry(tmp_path, monkeypatch):
    stage, export, config = _fixture(tmp_path)
    logical = stage / "11_OUTPUT_SEAL/LOGICAL_RESULT_TERMINAL_REGISTRY.csv"
    rows = direct._read_csv(logical)
    rows[0]["terminal_status"] = "PENDING"
    _csv(logical, rows)
    journal_path = stage / "11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["logical_registry_sha256"] = sha256_file(logical)
    _json(journal_path, journal)
    monkeypatch.setattr(direct, "render_diagnostic_figures", _fake_figures)
    with pytest.raises(direct.TrustedDirectEvidenceError, match="unresolved or duplicate"):
        direct.package_trusted_direct(local_config=config, stage_root=stage, export_root=export,
                                      attempt_id="direct_2", timestamp="20260809T120001P0800")
    assert not (stage / "17_FINAL_EVIDENCE").exists()
    assert not list(export.iterdir())
