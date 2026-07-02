from pathlib import Path

from scripts.paper10q2r1_storage_slim import scan_for_export_leaks


def test_export_clean_scan_rejects_local_paths(tmp_path: Path):
    leak = "/home/" + "kaiwen/runtime"
    (tmp_path / "bad.md").write_text(leak, encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "FAIL"
    assert leak.startswith(findings[0]["token"])


def test_export_clean_scan_rejects_raw_filename(tmp_path: Path):
    (tmp_path / "bad.md").write_text("gnss1-raw.csv", encoding="utf-8")
    status, findings = scan_for_export_leaks(tmp_path)
    assert status == "FAIL"
    assert findings[0]["kind"] == "path_or_payload_leak"
