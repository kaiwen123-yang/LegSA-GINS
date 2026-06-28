from tests.paper10m1r2a_v2_common import read_csv


def test_module_disable_is_not_a_case_family_or_type():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    for row in rows:
        combined = f"{row['case_family']} {row['degradation_type_id']} {row['degradation_type_name']}".lower()
        assert "module_disable" not in combined


def test_internal_ablation_methods_are_separate_from_case_axis():
    rows = read_csv("06_QUEUE_DRAFT/PAPER10M1R2D_INTERNAL_ABLATION_QUEUE_DRAFT.csv")
    assert len(rows) == 4869
    assert any(row["ablation_method_id"] == "legsa_no_raw_doppler" for row in rows)
    for row in rows:
        assert "module_disable" not in row["case_id"].lower()
        assert "module_disable" not in row["degradation_type_id"].lower()
