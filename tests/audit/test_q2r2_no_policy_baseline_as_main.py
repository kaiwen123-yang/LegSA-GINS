from legsa_gins.external_dual_methods.method_contracts import ReproductionType, selected_methods


def test_q2r2_selected_methods_are_not_policy_baselines():
    assert all(method.target_reproduction_type != ReproductionType.PAPER_DERIVED_POLICY_BASELINE for method in selected_methods())
