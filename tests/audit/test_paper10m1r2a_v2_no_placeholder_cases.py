import json

from tests.paper10m1r2a_v2_common import read_csv


def test_no_placeholder_case_ids_or_names_remain():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    forbidden = ["placeholder", "mixed_00", "dummy", "todo", "tbd"]
    for row in rows:
        haystack = " ".join(
            [row["case_id"], row["case_family"], row["degradation_type_id"], row["degradation_type_name"]]
        ).lower()
        assert not any(token in haystack for token in forbidden)


def test_mixed_cases_have_explicit_component_lists():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    mixed = [row for row in rows if row["case_family"] == "multi_source_mixed"]
    assert {row["degradation_type_id"] for row in mixed} == {"D57", "D58", "D59", "D60"}
    for row in mixed:
        params = json.loads(row["degradation_parameters_json"])
        assert params["components"]
        assert isinstance(params["components"], list)
