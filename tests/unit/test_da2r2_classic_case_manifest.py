from legsa_gins.external_literature.by2_classic_case_manifest import classic_case_manifest


def test_da2r2_classic_case_manifest_has_locked_18_cases():
    cases = classic_case_manifest()
    assert len(cases) == 18
    assert cases[0]["case_id"] == "C00_clean_normal"
    assert cases[-1]["case_id"] == "C17_mixed_medium_seed2"
    assert len({case["case_id"] for case in cases}) == 18
