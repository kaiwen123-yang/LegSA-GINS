from pathlib import Path

from scripts.paper10q2_horizontal_reconciliation import scan_for_export_leaks


def test_export_clean_scan_passes_placeholders(tmp_path: Path):
    (tmp_path / "ok.md").write_text("<PAPER10Q2_STAGE_ROOT>\n<TRACE_EVAL_REFERENCE_ONLY>\n", encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "PASS"
    assert findings == []


def test_export_clean_scan_rejects_local_path(tmp_path: Path):
    leak = "/home/" + "kaiwen/research/runtime"
    (tmp_path / "bad.md").write_text(leak, encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "FAIL"
    assert findings[0]["kind"] == "local_path_or_raw_leak"
