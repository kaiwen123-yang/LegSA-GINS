from pathlib import Path

from scripts.paper10q2r1_storage_slim import scan_for_export_leaks


def test_export_scan_rejects_runtime_payload_names(tmp_path: Path):
    (tmp_path / "bad.csv").write_text("epoch_output.csv\nqa_decisions_epoch.csv\neval_metrics.json\n", encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "FAIL"
    assert {finding["kind"] for finding in findings} == {"path_or_payload_leak"}


def test_export_scan_allows_placeholders(tmp_path: Path):
    (tmp_path / "ok.md").write_text("<PAPER10Q2R1_STAGE_ROOT>\n<TRACE_EVAL_REFERENCE_ONLY>\n", encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "PASS"
    assert findings == []
