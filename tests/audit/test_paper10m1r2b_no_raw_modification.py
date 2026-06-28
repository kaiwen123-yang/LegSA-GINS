from tests.paper10m1r2b_common import read_csv


def test_raw_data_immutability_audit_passes():
    rows = read_csv("07_GUARDS/PAPER10M1R2B_RAW_DATA_IMMUTABILITY_AUDIT.csv")
    assert rows
    assert {row["status"] for row in rows} == {"UNCHANGED"}


def test_provider_manifest_confirms_no_raw_modification_or_overwrite():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    assert {row["raw_data_modified"] for row in rows} == {"false"}
    assert {row["raw_data_overwritten"] for row in rows} == {"false"}
