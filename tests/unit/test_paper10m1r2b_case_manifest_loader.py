from collections import Counter

from tests.paper10m1r2b_common import EXPECTED_TYPES, read_csv


def test_m1r2b_provider_manifest_has_541_cases():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    assert len(rows) == 541
    assert sum(row["degradation_type_id"] == "CLEAN" for row in rows) == 1
    assert sum(row["degradation_type_id"] != "CLEAN" for row in rows) == 540


def test_m1r2b_provider_manifest_has_60_types_with_9_seeds():
    rows = [
        row
        for row in read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
        if row["degradation_type_id"] != "CLEAN"
    ]
    counts = Counter(row["degradation_type_id"] for row in rows)
    assert set(counts) == EXPECTED_TYPES
    assert set(counts.values()) == {9}
