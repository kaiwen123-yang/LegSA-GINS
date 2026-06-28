from tests.paper10m1r2a_v2_common import (
    EXPECTED_DEGRADATION_NAMES,
    EXPECTED_TYPE_IDS,
    read_csv,
)


def test_registry_has_exact_fixed_60_types():
    rows = read_csv("02_MATRIX_DESIGN/CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv")
    assert len(rows) == 60
    assert [row["degradation_type_id"] for row in rows] == EXPECTED_TYPE_IDS
    assert [row["degradation_type_name"] for row in rows] == EXPECTED_DEGRADATION_NAMES


def test_registry_has_no_module_disable_axis():
    rows = read_csv("02_MATRIX_DESIGN/CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv")
    assert {row["module_disable_axis"] for row in rows} == {"false"}
    joined = "\n".join(
        f"{row['case_family']} {row['degradation_type_id']} {row['degradation_type_name']}"
        for row in rows
    ).lower()
    assert "module_disable" not in joined
