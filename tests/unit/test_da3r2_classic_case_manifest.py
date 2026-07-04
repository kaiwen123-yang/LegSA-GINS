from legsa_gins.da_repro.method_runner import CLASSIC_CASES


def test_da3r2_classic_case_manifest_has_18_cases():
    assert len(CLASSIC_CASES) == 18
    assert CLASSIC_CASES[0]["case_id"] == "C00_clean_normal"
