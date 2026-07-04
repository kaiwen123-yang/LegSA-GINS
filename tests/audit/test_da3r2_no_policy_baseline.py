from legsa_gins.da_repro.method_contracts import TARGET_METHODS


def test_da3r2_no_policy_baseline():
    assert all("policy baseline" not in method.notes.lower() for method in TARGET_METHODS)
