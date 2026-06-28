from collections import Counter

from tests.paper10m1r2a_v2_common import EXPECTED_TYPE_IDS, read_csv, read_json


def test_case_manifest_has_541_rows_with_clean_and_540_degraded():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    assert len(rows) == 541
    assert sum(row["degradation_type_id"] == "CLEAN" for row in rows) == 1
    assert sum(row["degradation_type_id"] != "CLEAN" for row in rows) == 540


def test_each_degradation_type_has_9_seed_cases():
    rows = [
        row
        for row in read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
        if row["degradation_type_id"] != "CLEAN"
    ]
    counts = Counter(row["degradation_type_id"] for row in rows)
    assert sorted(counts) == EXPECTED_TYPE_IDS
    assert set(counts.values()) == {9}


def test_case_manifest_safety_fields_are_locked():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    allowed_claim_levels = {"main_candidate", "appendix_candidate", "diagnostic_only"}
    for row in rows:
        assert row["dataset"] == "BY2"
        assert row["trace_eval_only"] == "true"
        assert row["final_v23_output_solver_input_allowed"] == "false"
        assert row["legsa_output_solver_input_allowed"] == "false"
        assert row["go2_truth_claim_allowed"] == "false"
        assert row["claim_level"] in allowed_claim_levels


def test_case_spec_schema_locks_expected_row_count():
    schema = read_json("04_CASE_MANIFEST/CANONICAL_BY2_CASE_SPEC_SCHEMA.json")
    assert schema["row_count"] == 541
    assert schema["degraded_case_count"] == 540
    assert schema["clean_case_count"] == 1
