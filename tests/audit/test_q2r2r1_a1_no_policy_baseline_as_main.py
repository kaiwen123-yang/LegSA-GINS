from legsa_gins.external_dual.method_contracts import ReproductionType, selected_methods


def test_a1_selected_methods_are_not_policy_baselines():
    assert all(method.reproduction_type != ReproductionType.PAPER_DERIVED_POLICY_BASELINE for method in selected_methods())
    assert all(method.claim_level != "main_text_candidate" for method in selected_methods())
