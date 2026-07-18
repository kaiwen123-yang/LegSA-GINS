import zipfile
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2r2a_evidence import finalize_evidence_zip
from test_clean2r2a_manifest_sidecar import _approve_terminal, _minimal_stage


def test_final_zip_contains_manifest_and_sidecar_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _approve_terminal(monkeypatch)
    stage = _minimal_stage(tmp_path); export = tmp_path / "project" / "export"; export.mkdir()
    result = finalize_evidence_zip(
        stage_root=stage, export_root=export, timestamp="20260718T000001P0800",
        local_config=tmp_path / "local.yaml", exact_evaluator=tmp_path / "evaluator.py",
    )
    with zipfile.ZipFile(result["zip_path"], "r") as archive:
        assert archive.namelist().count("EVIDENCE_MANIFEST.csv") == 1
        assert archive.namelist().count("EVIDENCE_MANIFEST.sha256") == 1
    assert result["zip_manifest_closure"] is True
    assert result["zip_sidecar_check"] is True
