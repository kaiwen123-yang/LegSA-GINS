from legsa_gins.da_repro.method_liu_cwls import DA03_CLASSIC_CASES


def test_da03_classic_matrix_has_expected_18_cases():
    case_ids = [case.case_id for case in DA03_CLASSIC_CASES]
    assert len(case_ids) == 18
    assert case_ids[0] == "C00_clean_normal"
    assert case_ids[-1] == "C17_mixed_medium_seed2"
    assert len(set(case_ids)) == 18
