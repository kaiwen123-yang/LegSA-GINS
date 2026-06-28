from tests.paper10m1r2b_common import read_csv


def test_provider_ready_manifest_marks_all_cases_ready_and_forbidden_inputs_false():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_READY_MANIFEST.csv")
    assert len(rows) == 541
    assert {row["provider_ready"] for row in rows} == {"true"}
    assert {row["effect_validation_status"] for row in rows} == {"PASS"}
    assert {row["trace_used"] for row in rows} == {"false"}
    assert {row["final_v23_output_used"] for row in rows} == {"false"}
    assert {row["legsa_output_used"] for row in rows} == {"false"}
    assert {row["raw_data_modified"] for row in rows} == {"false"}
    assert {row["raw_data_overwritten"] for row in rows} == {"false"}


def test_provider_sha_manifest_is_complete():
    rows = read_csv("05_PROVIDER_READY/PAPER10M1R2B_PROVIDER_SHA256_MANIFEST.csv")
    assert len(rows) >= 541 * 5
    assert all(row["sha256"] for row in rows)
