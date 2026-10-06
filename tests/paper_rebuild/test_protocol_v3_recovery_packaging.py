"""Synthetic packaging tests; tmp_path must be registered scratch at invocation."""
from __future__ import annotations

import errno
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

import pytest

from legsa_gins.paper_rebuild.protocol_v3 import recovery_packaging as p
from legsa_gins.paper_rebuild.clean6_canonical_v2.archive_io import retry_io


FREEZE, REPAIR = "a" * 40, "b" * 40


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(p.encoded(value) if not isinstance(value, bytes) else value)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def closed(tmp_path, monkeypatch):
    root = tmp_path / "clean/stages/CLEAN8_PROTOCOL_V3"
    repo, handoff = tmp_path / "repo", tmp_path / "handoff"
    gates = write(root / "00_PREREQUISITES/GATES.json", dict(status="PASS", gates={
        name: dict(status="PASS", **({"phase": "COMPLETED_NATIVE_ADMISSION"} if name == "2c" else {}))
        for name in ("2a", "2b", "2c", "2d", "2e")}))
    audit_root = root / "00_CONTROL/AGGREGATE_RECOVERY"
    audit_rows = write(audit_root / "OPENAT_AUDIT_ROWS.csv", b"synthetic_fixture_only\n")
    pins = write(audit_root / "OPENAT_SOURCE_PINS.json", {"synthetic_fixture_only": True})
    audit = write(audit_root / "OPENAT_AUDIT_SUMMARY.json", dict(status="PASS", native_count=6468,
        evaluator_terminal_slots=12936, native_trace_open_count=0, evaluator_each_trace_exactly_one=True,
        evaluator_process_count=12370, native_calls=0, evaluator_calls=0, raw_trace_reads=0,
        completed_batches=279,
        counts=dict(evaluator_processes=12370, evaluator_skipped_slots=566),
        audit_rows_sha256=sha(audit_rows), source_pins_sha256=sha(pins)))
    table = write(root / "07_AGGREGATE/MAIN_TABLE_V3.csv", (
        "sequence_id,method_id,yaw_rmse_deg\nBY2,F04,1.886272\nBY2H,F04,1.933770\nBY2O,F04,2.433815\n"
        + "BY2,EXTERNAL,2.0\n" * 49).encode())
    reference = write(tmp_path / "clean/stages/REGISTERED_REFERENCE/SENSITIVITY.csv", b"variant\nB3\nR5SIGMA\nR5W\n")
    index = write(root / "07_AGGREGATE/REPORT_SOURCE_INDEX.json", {"sensitivity_summary": {
        "path": "<CLEAN_ROOT>/stages/REGISTERED_REFERENCE/SENSITIVITY.csv", "sha256": sha(reference)}})
    aggregate = write(root / "07_AGGREGATE/AGGREGATE_MANIFEST.json", dict(status="COMPLETE_V3_AGGREGATES",
        code_freeze=FREEZE, files_sha256={table.name: sha(table), index.name: sha(index)}))
    figures = []
    for name in sorted(p.FIGURES):
        outputs = {ext: write(root / "08_FIGURES" / name / (name + "." + ext), b"synthetic fixture: " + name.encode())
                   for ext in ("png", "pdf", "svg")}
        figures.append(dict(figure_id=name, status="RENDERED", qa=[dict(pass_=True)],
                            output_sha256={ext: sha(path) for ext, path in outputs.items()}))
        figures[-1]["qa"] = [{"pass": True}]
    render = write(root / "08_FIGURES/RENDER_MANIFEST.json", dict(status="COMPLETE", rendered_count=10,
        code_freeze=FREEZE, figures=figures))
    visual = write(root / "09_HANDOFF/VISUAL_REVIEW.json", dict(status="PASS", reviewed_figures=sorted(p.FIGURES),
        render_manifest_sha256=sha(render)))
    appendix_files = {}
    for name in ("FULL_ABLATION_TABLE_V3.csv", "FULL_ABLATION_TABLE_V2.csv", "CORE_541_V21_COMPARISON_V3.csv",
                 "CORE_541_V21_COMPARISON_V2.csv", "SUBSET61_V21_COMPARISON_V3.csv", "SUBSET61_V21_COMPARISON_V2.csv",
                 "FAILURE_FAMILY_CONFIG.csv", "MANUSCRIPT_FULL_ABLATION_AND_FAILURES.md"):
        appendix_files[name] = sha(write(root / "07C_FAILURE_FAMILY_CONFIG" / name, b"synthetic fixture only\n"))
    appendix = write(root / "07C_FAILURE_FAMILY_CONFIG/MANIFEST.json", dict(
        status="PASS_REPORT_ONLY_FULL_ABLATION_AND_FAILURE_FAMILY_CONFIG", science_freeze=FREEZE, repair_commit=REPAIR,
        v3_failures=283, v21_failures=177, f02_separate=True, full_ablation_rows_per_version=33,
        corrected_field_only="v21_failure", numeric_tokens_changed=0, original_files_changed=0, files_sha256=appendix_files))
    write(root / "00_CONTROL/DONE.json", dict(status="DONE_MATRIX_AGGREGATE_FIGURES_MACHINE_QA", science_freeze=FREEZE,
        aggregate_manifest_sha256=sha(aggregate), render_manifest_sha256=sha(render),
        full_ablation_failure_appendix_sha256=sha(appendix)))
    write(root / "00_CONTROL/SUMMARY.txt", b"DONE synthetic fixture only\n")
    write(root / "00_CONTROL/HARD_STOP.json", dict(status="HISTORICAL_HARD_STOP_PRESERVED"))
    for name in p.REQUIRED_DOCS:
        write(repo / "docs/paper_rebuild/v3" / name, b"synthetic packaging fixture\n")
    roots = dict(clean_root=str(tmp_path / "clean"), handoff_root=str(handoff))
    monkeypatch.setattr(p, "git_identity", lambda *args: args[1])
    monkeypatch.setattr(p, "verify_running_source", lambda *args: "c" * 64)
    monkeypatch.setattr(p, "require_g_roots", lambda *args: None)
    monkeypatch.setattr(p, "source_snapshot", lambda archive, repo, commit, prefix: [
        p.add_member(archive, io.BytesIO(commit.encode()), prefix + "/SOURCE_COMMIT.txt")])
    return dict(root=root, repo=repo, roots=roots, gate_path=gates, audit_path=audit,
                render=render, visual=visual, reference=reference, aggregate=aggregate, table=table)


def run(closed):
    return p.package(closed["roots"], closed["repo"], code_freeze=FREEZE, repair_commit=REPAIR,
                     gate_path=closed["gate_path"], audit_path=closed["audit_path"], package_name="fixture.zip")


def test_direct_handoff_contains_full_evidence_refs_source_docs_and_all_member_verification(closed):
    forbidden = write(closed["root"] / "03_NATIVE/UNRETAINED.NAV", b"must never read this")
    result = run(closed)
    destination = Path(result["destination"])
    assert destination.parent == Path(closed["roots"]["handoff_root"])
    assert not list(closed["root"].rglob("*.zip"))
    assert result["zip_sha256"] == sha(destination)
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        assert len(names) == result["zip_member_count"]
        assert "V3_RETAINED/00_CONTROL/HARD_STOP.json" in names
        assert "SCIENCE_SOURCE/SOURCE_COMMIT.txt" in names
        assert "REPAIR_SOURCE/SOURCE_COMMIT.txt" in names
        assert "CURRENT_REVIEW_DOCS/V3_01R_MANUSCRIPT_REPLACEMENT.md" in names
        assert any(name.endswith("REGISTERED_REFERENCE/SENSITIVITY.csv") for name in names)
        assert not any(name.endswith(".NAV") for name in names)
    receipt = p.read_json(destination.with_name("fixture_MANIFEST.json"))
    assert receipt["all_member_sha256_crc_size_verified"] is True
    assert receipt["wsl_archive_created"] is False
    assert receipt["native_calls"] == receipt["evaluator_calls"] == receipt["trace_open_count"] == 0
    assert len(receipt["members"]) == len(names)
    assert forbidden.read_bytes() == b"must never read this"
    with pytest.raises(FileExistsError, match="preserved"):
        run(closed)


@pytest.mark.parametrize("gate", ("native_trace", "evaluator_trace", "audit_conservation", "audit_pin", "visual", "visual_binding", "figure_qa", "f04", "failure_appendix"))
def test_complete_package_fails_closed_before_archive_on_required_gate(closed, gate):
    if gate in {"native_trace", "evaluator_trace"}:
        audit = p.read_json(closed["audit_path"])
        audit["native_trace_open_count" if gate == "native_trace" else "evaluator_each_trace_exactly_one"] = 1 if gate == "native_trace" else False
        write(closed["audit_path"], audit)
    elif gate == "audit_conservation":
        audit = p.read_json(closed["audit_path"])
        audit["counts"]["evaluator_skipped_slots"] = 0
        write(closed["audit_path"], audit)
    elif gate == "audit_pin":
        write(closed["audit_path"].parent / "OPENAT_AUDIT_ROWS.csv", b"changed\n")
    elif gate.startswith("visual"):
        visual = p.read_json(closed["visual"])
        visual["status" if gate == "visual" else "render_manifest_sha256"] = "FAIL"
        write(closed["visual"], visual)
    elif gate == "figure_qa":
        render = p.read_json(closed["render"])
        render["figures"][0]["qa"][0]["pass"] = False
        write(closed["render"], render)
        done = p.read_json(closed["root"] / "00_CONTROL/DONE.json")
        done["render_manifest_sha256"] = sha(closed["render"])
        write(closed["root"] / "00_CONTROL/DONE.json", done)
    elif gate == "failure_appendix":
        write(closed["root"] / "07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv", b"changed\n")
    else:
        table = closed["table"]
        write(table, table.read_bytes().replace(b"1.886272", b"1.886273"))
        aggregate = p.read_json(closed["aggregate"])
        aggregate["files_sha256"][table.name] = sha(table)
        write(closed["aggregate"], aggregate)
        done = p.read_json(closed["root"] / "00_CONTROL/DONE.json")
        done["aggregate_manifest_sha256"] = sha(closed["aggregate"])
        write(closed["root"] / "00_CONTROL/DONE.json", done)
    with pytest.raises(ValueError):
        run(closed)
    assert not list(Path(closed["roots"]["handoff_root"]).glob("*.zip"))


def test_external_reference_hash_mismatch_preserves_failed_unique_archive(closed):
    closed["reference"].write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="pin differs"):
        run(closed)
    failed = Path(closed["roots"]["handoff_root"]) / "fixture.zip"
    assert failed.is_file()
    assert not failed.with_name("fixture_MANIFEST.json").exists()
    with pytest.raises(FileExistsError, match="preserved"):
        run(closed)


def test_symlink_and_raw_external_path_rejected(tmp_path):
    actual = write(tmp_path / "actual", b"data")
    link = tmp_path / "link"
    link.symlink_to(actual)
    with pytest.raises(ValueError, match="symlinks"):
        p.walk_stage(tmp_path)
    for name in ("trace_reference.txt", "source.bag", "provider.imu"):
        with pytest.raises(ValueError, match="forbidden"):
            p.reference_files({"path": str(tmp_path / name), "sha256": "a" * 64}, {"clean_root": str(tmp_path)})


def test_non_g_destination_rejected(tmp_path):
    with pytest.raises(ValueError, match="mounted G volume"):
        p.require_g_roots(tmp_path / "stage", tmp_path / "handoff")


def test_zip_verification_checks_sha_even_when_zip_crc_is_self_consistent(tmp_path):
    path = tmp_path / "test.zip"
    manifest = b"manifest"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("x", b"wrong")
        archive.writestr("MEMBER_MANIFEST.json", manifest)
    expected = [dict(name="x", **p.digest_stream(io.BytesIO(b"right")))]
    with pytest.raises(ValueError, match="SHA256/CRC/size"):
        p.verify_zip(path, expected, manifest)


def test_fixed_offset_write_retry_does_not_duplicate_uncertain_partial_block(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "retry_io", lambda function, **kwargs: retry_io(function, **kwargs, sleep=lambda _: None))
    destination = tmp_path / "retry"
    with p.RetryFile(destination, "xb") as stream:
        underlying = stream.stream
        class Partial:
            attempts = 0
            def __getattr__(self, name):
                return getattr(underlying, name)
            def write(self, data):
                self.attempts += 1
                if self.attempts == 1:
                    underlying.write(data[:3])
                    raise OSError(errno.EIO, "uncertain partial write")
                return underlying.write(data)
        stream.stream = Partial()
        assert stream.write(b"abcdef") == 6
        stream.durable()
        assert len(stream.events) == 1
    assert destination.read_bytes() == b"abcdef"


def test_source_snapshot_streams_requested_commit_without_temporary_archive(tmp_path, monkeypatch):
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode="w") as archive:
        item = tarfile.TarInfo("src/legsa_gins/paper_rebuild/protocol_v3/trace_reference_adapter.py")
        data = b"scientific source"
        item.size = len(data)
        archive.addfile(item, io.BytesIO(data))
    class Process:
        stdout = io.BytesIO(tar.getvalue())
        stderr = io.BytesIO()
        def wait(self): return 0
        def poll(self): return 0
    commands = []
    monkeypatch.setattr(p.subprocess, "check_output", lambda *args, **kwargs: "src\n")
    def popen(command, **kwargs):
        commands.append(command)
        return Process()
    monkeypatch.setattr(p.subprocess, "Popen", popen)
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        members = p.source_snapshot(archive, tmp_path, FREEZE, "SCIENCE_SOURCE")
    assert len(members) == 1 and members[0]["sha256"] == hashlib.sha256(data).hexdigest()
    assert commands[0][3:6] == ["archive", "--format=tar", FREEZE]
    assert not list(tmp_path.iterdir())


def test_executing_packaging_source_must_match_frozen_repair_commit(monkeypatch):
    repo = Path(p.__file__).absolute().parents[4]
    monkeypatch.setattr(p.subprocess, "check_output", lambda *args, **kwargs: b"wrong committed source")
    with pytest.raises(ValueError, match="hash mismatch"):
        p.verify_running_source(repo, REPAIR)
