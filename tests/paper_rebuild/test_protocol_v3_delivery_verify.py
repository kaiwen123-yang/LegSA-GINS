"""Tiny synthetic receipts; no scientific code or output generation is invoked."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/v3r_delivery_verify.py"
SPEC = importlib.util.spec_from_file_location("v3r_delivery_verify_test", SCRIPT)
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return verify.digest(path)


@pytest.fixture
def delivery(tmp_path):
    tables = {f"07_AGGREGATE/table_{i:02}.csv": write(tmp_path, f"07_AGGREGATE/table_{i:02}.csv", [i])
        for i in range(59)}
    for name in ("07_AGGREGATE/AGGREGATE_MANIFEST.json", "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json",
                 "07D_CLASSIFICATION_PROVENANCE/MANIFEST.json", "07_AGGREGATE/REPORT_SOURCE_INDEX.json",
                 "07_AGGREGATE/MANUSCRIPT_REPLACEMENT_TEXT.md", "07C_FAILURE_FAMILY_CONFIG/MANUSCRIPT.md"):
        tables[name] = write(tmp_path, name, {})
    baseline = dict(status="PASS_REVIEWED_TABLE_BASELINE", csv_count=59, files_sha256=tables, science_freeze="f" * 40)
    baseline_sha = write(tmp_path, verify.BASELINE, baseline)
    entries, outputs = [], {}
    for index, name in enumerate(sorted(verify.FIGURES)):
        hashes = {ext: write(tmp_path, f"08_FIGURES/{name}/{name}.{ext}", dict(synthetic_test=name, format=ext))
            for ext in ("png", "pdf", "svg")}
        outputs[name] = hashes
        entries.append(dict(figure_id=name, status="RENDERED", output_sha256=hashes,
            qa=[dict(figure_id=name, check=str(n), **{"pass": True}) for n in range(15 if index == 0 else 6)]))
    render_sha = write(tmp_path, verify.RENDER, dict(status="COMPLETE", requested_count=10, rendered_count=10,
        code_freeze="f" * 40, figures=entries))
    visual_sha = write(tmp_path, verify.VISUAL, dict(status="PASS", actual_raster_review=True,
        reviewed_figures=sorted(verify.FIGURES), render_manifest_sha256=render_sha,
        figure_results={name: dict(status="PASS") for name in verify.FIGURES}, figure_output_sha256=outputs))
    zero_calls = dict(native_calls=0, evaluator_calls=0, aggregate_calls=0)
    machine_sha = write(tmp_path, verify.MACHINE, dict(status="PASS_TEN_FIGURES_MACHINE_QA_TABLES_UNCHANGED",
        baseline_sha256=baseline_sha, render_manifest_sha256=render_sha, files_sha256=tables,
        csv_count=59, qa_checks=69, exports=30, figure_repair_commit="r" * 40, **zero_calls))
    write(tmp_path, verify.DONE, dict(status="DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA", utc="synthetic-test",
        render_manifest_sha256=render_sha, visual_review_sha256=visual_sha, table_identity_receipt_sha256=machine_sha,
        visual_review_status="PASS", table_hashes_unchanged=True, csv_count=59, figure_repair_commit="r" * 40,
        aggregate_manifest_sha256=tables["07_AGGREGATE/AGGREGATE_MANIFEST.json"],
        full_ablation_failure_appendix_sha256=tables["07C_FAILURE_FAMILY_CONFIG/MANIFEST.json"],
        science_freeze="f" * 40, **zero_calls))
    for name in verify.REQUIRED - {verify.BASELINE, verify.RENDER, verify.VISUAL, verify.MACHINE, verify.DONE}:
        write(tmp_path, name, dict(synthetic_test=True))
    write(tmp_path, verify.DISPOSITION, dict(status="SKIPPED_BY_USER", explicit_user_decision=True, zip_required=False,
        files_sha256={name: verify.digest(tmp_path / name) for name in verify.REQUIRED}))
    return tmp_path


def test_explicit_skip_accepts_absent_zip_and_only_reads_existing_files(delivery, monkeypatch):
    original = Path.open
    reads = []

    def read_only(path, mode="r", *args, **kwargs):
        assert mode in ("r", "rb")
        assert path.suffix != ".zip"
        reads.append(path)
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", read_only)
    result = verify.verify(delivery)
    assert result["status"] == "PASS_V3R_FINAL_DELIVERY_PACKAGE_SKIPPED_BY_USER"
    assert (result["unchanged_files"], result["unchanged_csv"], result["figures"],
        result["recorded_machine_checks"], result["verified_exports"]) == (65, 59, 10, 69, 30)
    assert result["zip_reads"] == result["figure_qa_calls"] == result["native_calls"] == result["evaluator_calls"] == 0
    assert reads


@pytest.mark.parametrize("field,value", [("explicit_user_decision", False), ("explicit_user_decision", "true"),
    ("status", "PENDING"), ("zip_required", True)])
def test_missing_explicit_package_waiver_is_rejected(delivery, field, value):
    decision = json.loads((delivery / verify.DISPOSITION).read_text())
    decision[field] = value
    write(delivery, verify.DISPOSITION, decision)
    with pytest.raises(ValueError, match="EXPLICIT_PACKAGE_DECISION"):
        verify.verify(delivery)


@pytest.mark.parametrize("name", [verify.DONE, "07_AGGREGATE/table_00.csv", "08_FIGURES/MFIG00/MFIG00.png"])
def test_changed_receipt_table_or_export_hash_is_rejected(delivery, name):
    (delivery / name).write_text("changed")
    with pytest.raises(ValueError, match="HASH"):
        verify.verify(delivery)


def test_rebound_done_with_wrong_cross_receipt_hash_is_rejected(delivery):
    done = json.loads((delivery / verify.DONE).read_text())
    done["render_manifest_sha256"] = "0" * 64
    digest = write(delivery, verify.DONE, done)
    decision = json.loads((delivery / verify.DISPOSITION).read_text())
    decision["files_sha256"][verify.DONE] = digest
    write(delivery, verify.DISPOSITION, decision)
    with pytest.raises(ValueError, match="DONE_BINDING"):
        verify.verify(delivery)
