from legsa_gins.external_dual.method_contracts import METHOD_CATALOG, ReproductionType, selected_methods


def test_a1_selects_three_faithful_methods():
    methods = selected_methods()
    assert len(methods) == 3
    assert all(method.reproduction_type == ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION for method in methods)
    assert all(method.backend_available for method in methods)


def test_a1_does_not_select_policy_baselines():
    assert all(method.reproduction_type != ReproductionType.PAPER_DERIVED_POLICY_BASELINE for method in selected_methods())
    assert any(method.reproduction_type == ReproductionType.BLOCKED_WITH_PROOF for method in METHOD_CATALOG)
