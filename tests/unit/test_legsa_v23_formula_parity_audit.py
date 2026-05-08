"""中文说明：N4H4D2 formula parity audit 单元测试。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_formula_parity_audit import (
    audit_reference_formula_snippets,
    build_formula_parity_report,
)


def test_formula_audit_detects_toy_snippets_and_missing_evidence(tmp_path: Path):
    ref = tmp_path / "reference"
    ext = tmp_path / "external"
    repo = tmp_path / "repo"
    (ref / "src").mkdir(parents=True)
    ext.mkdir()
    (repo / "cpp/legsa_v23_core/src/updates").mkdir(parents=True)
    (repo / "cpp/legsa_v23_core/src/filter").mkdir(parents=True)
    (repo / "cpp/legsa_v23_core/src/common").mkdir(parents=True)
    (repo / "cpp/legsa_v23_core/src/mechanization").mkdir(parents=True)
    (ref / "src/formula.cpp").write_text("void EKFUpdate(){} // Joseph K\nH_gnsspos antlever\n", encoding="utf-8")
    for path in [
        "cpp/legsa_v23_core/src/common/earth.cpp",
        "cpp/legsa_v23_core/src/mechanization/ins_mechanization.cpp",
        "cpp/legsa_v23_core/src/updates/measurement_update.cpp",
        "cpp/legsa_v23_core/src/filter/ekf_update.cpp",
        "cpp/legsa_v23_core/src/filter/state_feedback.cpp",
    ]:
        (repo / path).write_text("", encoding="utf-8")
    snippets = audit_reference_formula_snippets(ref, ext)
    assert snippets["reference_formula_evidence"]["ekf_update"]["evidence_status"] == "found"
    report = build_formula_parity_report(ref, ext, repo)
    assert "earth_DRi_DR" in report["formula_mismatch_candidates"]
    assert report["diagnostic_only"] is True

