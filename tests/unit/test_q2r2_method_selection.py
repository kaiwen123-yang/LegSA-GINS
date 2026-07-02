from legsa_gins.external_dual_methods.method_contracts import METHOD_CATALOG, selected_methods


def test_q2r2_candidate_pool_has_backup_but_only_five_selected():
    assert len(METHOD_CATALOG) >= 6
    assert len(selected_methods()) == 5


def test_q2r2_selected_methods_are_not_qa_methods():
    ids = {method.method_id for method in selected_methods()}
    assert not any("QA" in method_id for method_id in ids)
