import json
import zipfile

from scripts.paper10_da3_step0_da01_execute import export_clean


def test_export_clean_excludes_raw_runtime_payloads(tmp_path):
    stage = tmp_path / "stage"
    comp = tmp_path / "comparison"
    export = tmp_path / "export"
    (stage / "00_STAGE_REPORT").mkdir(parents=True)
    (stage / "01_LITERATURE").mkdir()
    (stage / "05_PROVIDER").mkdir()
    (stage / "09_MATRIX").mkdir()
    (stage / "10_EVALUATION").mkdir()
    (stage / "11_CLAIM_BOUNDARY").mkdir()
    (comp / "01_METHOD_DA01_TEUNISSEN_CLAMBDA").mkdir(parents=True)
    for path in [
        stage / "00_STAGE_REPORT/PAPER10_DA3_DA01_SUPERVISOR_FINAL_REPORT.md",
        stage / "00_STAGE_REPORT/PAPER10_DA3_DA01_REVIEWER_REPORT.md",
        stage / "01_LITERATURE/DA01_PAPER_SEARCH_REPORT.md",
        stage / "01_LITERATURE/DA01_PAPER_INVENTORY.csv",
        stage / "01_LITERATURE/DA01_PAPER_READING_NOTES_CN.md",
        stage / "05_PROVIDER/PROVIDER_CAPABILITY_MATRIX.csv",
        stage / "09_MATRIX/DA01_ROW_EXECUTION_STATUS.csv",
        stage / "10_EVALUATION/DA01_METHOD_LEVEL_SUMMARY.csv",
        stage / "10_EVALUATION/DA01_CASE_FAMILY_SUMMARY.csv",
        stage / "10_EVALUATION/DA01_FAILURE_ANALYSIS.md",
        stage / "11_CLAIM_BOUNDARY/DA01_CLAIM_BOUNDARY_FREEZE.md",
        comp / "01_METHOD_DA01_TEUNISSEN_CLAMBDA/README_SUMMARY_CN.md",
        comp / "01_METHOD_DA01_TEUNISSEN_CLAMBDA/CLAIM_BOUNDARY.md",
    ]:
        path.write_text("clean text\n", encoding="utf-8")
    result = export_clean(stage, comp, export, {str(tmp_path): "<TMP>"})
    assert result["passed"] is True
    scan = json.loads((export / "12_EXPORT_CLEAN_FOR_GPT/export_clean_path_scan.json").read_text(encoding="utf-8"))
    assert scan["forbidden_hits"] == []
    with zipfile.ZipFile(export / "12_EXPORT_CLEAN_FOR_GPT/paper10_da3_step0_da01_pack.zip") as zf:
        names = zf.namelist()
    assert all("epoch_output.csv" not in name for name in names)
    assert all(not name.endswith(".pdf") for name in names)
