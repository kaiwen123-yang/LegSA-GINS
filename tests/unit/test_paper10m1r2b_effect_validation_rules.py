from tests.paper10m1r2b_common import EXPECTED_TYPES, read_csv


def test_effect_validation_passes_all_541_cases():
    rows = read_csv("04_EFFECT_VALIDATION/PAPER10M1R2B_EFFECT_VALIDATION_RESULT_TABLE.csv")
    assert len(rows) == 541
    assert {row["effect_validation_status"] for row in rows} == {"PASS"}


def test_effect_validation_covers_all_degradation_types():
    rows = read_csv("04_EFFECT_VALIDATION/PAPER10M1R2B_EFFECT_VALIDATION_RESULT_TABLE.csv")
    types = {row["degradation_type_id"] for row in rows if row["degradation_type_id"] != "CLEAN"}
    assert types == EXPECTED_TYPES
    failures = read_csv("04_EFFECT_VALIDATION/PAPER10M1R2B_EFFECT_VALIDATION_FAILURES.csv")
    assert failures == [{"case_id": "NONE", "effect_validation_status": "PASS", "issues": "none"}]
