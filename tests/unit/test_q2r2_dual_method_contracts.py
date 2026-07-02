from legsa_gins.external_dual_methods.method_contracts import (
    ReproductionType,
    selected_methods,
)


def test_q2r2_selects_five_target_methods_with_faithful_targets():
    methods = selected_methods()
    assert len(methods) == 5
    assert all(method.target_reproduction_type == ReproductionType.FAITHFUL_ALGORITHM_REPRODUCTION for method in methods)
    assert all(method.required_inputs for method in methods)


def test_q2r2_contracts_forbid_exact_by_default():
    assert all(method.source_paper for method in selected_methods())
