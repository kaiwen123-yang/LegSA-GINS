"""Closeout gates with tiny metadata fixtures; no scientific execution."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def closeout():
    path = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/v3r_figure_closeout.py"
    spec = importlib.util.spec_from_file_location("v3r_figure_closeout_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_table_hash_change_and_root_escape_stop(closeout, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    table = root / "table.csv"
    table.write_bytes(b"fixed,table\n")
    pins = {"table.csv": hashlib.sha256(table.read_bytes()).hexdigest()}
    closeout.checked(root, pins)
    table.write_bytes(b"changed,table\n")
    with pytest.raises(RuntimeError, match="HASH_CHANGED"):
        closeout.checked(root, pins)
    with pytest.raises(ValueError):
        closeout.checked(root, {"../other.csv": "0" * 64})


def test_missing_or_failed_visual_review_cannot_write_done(closeout, tmp_path, monkeypatch):
    root = tmp_path / "root"
    control = root / closeout.CONTROL
    control.mkdir(parents=True)
    candidate = root / closeout.CANDIDATE
    candidate.mkdir(parents=True)
    render_path = candidate / "RENDER_MANIFEST.json"
    ids = [*(f"MFIG{i:02}" for i in range(7)), "SFIG01", "FIG02S", "FIG02S-b"]
    render_path.write_text(json.dumps({"figures": [{"figure_id": key} for key in ids]}))
    digest = hashlib.sha256(render_path.read_bytes()).hexdigest()
    (control / "BASELINE.json").write_text('{"files_sha256":{}}')
    (control / "MACHINE_QA_AND_TABLE_IDENTITY.json").write_text(json.dumps(
        {"figure_repair_commit": "a" * 40, "render_manifest_sha256": digest,
         "status": "PASS_TEN_FIGURES_MACHINE_QA_TABLES_UNCHANGED", "files_sha256": {},
         "baseline_sha256": hashlib.sha256((control / "BASELINE.json").read_bytes()).hexdigest()}))
    monkeypatch.setattr(closeout, "unchanged", lambda *_: {"files_sha256": {}})
    for status, results in (("FAIL", {}), ("PASS", {key: {"status": "PASS"} for key in ids[:-1]})):
        (control / "VISUAL_REVIEW.json").write_text(json.dumps(dict(status=status,
            actual_raster_review=True, reviewed_figures=ids, figure_results=results,
            render_manifest_sha256=digest)))
        with pytest.raises(RuntimeError, match="VISUAL_QA_REQUIRED"):
            closeout.complete({}, root, control, "a" * 40)
        assert not (root / "00_CONTROL/DONE.json").exists()


def test_persisted_stop_prevents_closeout(closeout, tmp_path):
    control = tmp_path / closeout.CONTROL
    control.mkdir(parents=True)
    (control / "HARD_STOP.json").write_text('{"status":"HARD_STOP"}')
    with pytest.raises(RuntimeError, match="existing stop"):
        closeout.complete({}, tmp_path, control, "a" * 40)
    assert not (tmp_path / "00_CONTROL/DONE.json").exists()
