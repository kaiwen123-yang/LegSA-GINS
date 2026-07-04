from legsa_gins.da_repro.method_contracts import TARGET_METHODS


def test_da3r2_no_summary_reconstruction():
    assert all("SUMMARY_RECONSTRUCTED" not in method.notes for method in TARGET_METHODS)
