from tests.paper10m1r2a_v2_common import EXPECTED_TYPE_IDS, read_csv, read_json


def test_effect_validation_rules_cover_all_60_types():
    rows = read_csv("05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv")
    assert len(rows) == 60
    assert [row["degradation_type_id"] for row in rows] == EXPECTED_TYPE_IDS
    assert [row["rule_id"] for row in rows] == [f"RULE_{type_id}" for type_id in EXPECTED_TYPE_IDS]


def test_effect_validation_rules_include_forbidden_source_checks():
    rows = read_csv("05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv")
    for row in rows:
        assert "trace must not be read" in row["trace_forbidden_check"]
        assert "final_v23/LegSA outputs must not be read" in row["final_v23_forbidden_check"]
        assert row["seed_reproducibility_check"]
        assert row["sha256_check"]
        assert row["timestamp_monotonic_check"]
        assert row["nan_inf_check"]
        assert row["physical_sanity_check"]


def test_effect_validation_schema_locks_rule_count():
    schema = read_json("05_EFFECT_VALIDATION/CANONICAL_BY2_EFFECT_VALIDATION_SCHEMA.json")
    assert schema["row_count"] == 60
    assert "rule_id" in schema["required_fields"]
    assert "final_v23_forbidden_check" in schema["required_fields"]
