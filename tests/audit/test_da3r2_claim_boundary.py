from legsa_gins.da_repro.method_contracts import TARGET_METHODS


def test_da3r2_claim_boundary():
    assert all(not method.exact_claim_allowed for method in TARGET_METHODS)
