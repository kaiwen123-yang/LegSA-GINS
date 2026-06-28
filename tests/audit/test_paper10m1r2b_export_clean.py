from tests.paper10m1r2b_common import read_json


def test_export_clean_path_scan_passes():
    scan = read_json("11_EXPORT_CLEAN_FOR_GPT/export_clean_path_scan.json")
    assert scan["status"] == "PASS"
    assert scan["violations"] == []
