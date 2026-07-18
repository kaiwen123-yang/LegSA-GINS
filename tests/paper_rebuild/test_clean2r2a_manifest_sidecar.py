from pathlib import Path

import pytest

import legsa_gins.paper_rebuild.clean2r2a_evidence as evidence_module
from legsa_gins.paper_rebuild.clean2r2a_evidence import finalize_evidence_zip
from legsa_gins.paper_rebuild.clean2r2a_evidence import STAGE_ID, TERMINAL_STATUS
from legsa_gins.paper_rebuild.manifest import sha256_file


def _minimal_stage(root: Path) -> Path:
    stage = root / "project" / "clean_rebuild_202607" / "stages" / STAGE_ID
    for name in ("00_AUTHORIZATION", "01_GIT_FREEZE", "02_PROTOCOLS", "03_RAW_AUDITS",
                 "04_BASE_PROVIDER", "05_RUN_REGISTRY", "06_FORMAL_RUNS", "07_OUTPUT_SEAL",
                 "08_OFFLINE_EVALUATION", "09_FACTORIAL_ANALYSIS", "10_DIAGNOSTIC_FIGURES",
                 "11_AUDITS", "12_FINAL_EVIDENCE"):
        (stage / name).mkdir(parents=True)
    for name in ("00_AUTHORIZATION", "01_GIT_FREEZE", "02_PROTOCOLS", "03_RAW_AUDITS",
                 "05_RUN_REGISTRY", "07_OUTPUT_SEAL", "09_FACTORIAL_ANALYSIS",
                 "10_DIAGNOSTIC_FIGURES", "11_AUDITS"):
        (stage / name / "proof.txt").write_text(name + "\n", encoding="utf-8")
    (stage / "04_BASE_PROVIDER/provider.json").write_text("{}\n", encoding="utf-8")
    (stage / "08_OFFLINE_EVALUATION/summary.json").write_text("{}\n", encoding="utf-8")
    return stage


def _approve_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        evidence_module,
        "audit_terminal_stage",
        lambda _stage, **_kwargs: {"terminal_status": TERMINAL_STATUS, "gates": {"test_gate": True}},
    )


def test_stage_manifest_and_sidecar_are_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _approve_terminal(monkeypatch)
    stage = _minimal_stage(tmp_path); export = tmp_path / "project" / "export"; export.mkdir()
    result = finalize_evidence_zip(
        stage_root=stage, export_root=export, timestamp="20260718T000000P0800",
        local_config=tmp_path / "local.yaml", exact_evaluator=tmp_path / "evaluator.py",
    )
    final = stage / "12_FINAL_EVIDENCE/FINALIZED"
    assert (final / "EVIDENCE_MANIFEST.sha256").read_text(encoding="utf-8") == (
        f"{sha256_file(final / 'EVIDENCE_MANIFEST.csv')}  EVIDENCE_MANIFEST.csv\n"
    )
    assert result["stage_sidecar_check"] is True


def test_finalizer_rejects_placeholder_stage(tmp_path: Path) -> None:
    stage = _minimal_stage(tmp_path); export = tmp_path / "project" / "export"; export.mkdir()
    with pytest.raises((OSError, ValueError)):
        finalize_evidence_zip(
            stage_root=stage, export_root=export, timestamp="20260718T000002P0800",
            local_config=tmp_path / "local.yaml", exact_evaluator=tmp_path / "evaluator.py",
        )
