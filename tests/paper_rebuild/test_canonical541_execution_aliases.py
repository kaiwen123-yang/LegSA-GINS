from legsa_gins.paper_rebuild.canonical541.ablation_registry import FULL_ALIAS


def test_only_exact_full_profile_aliases_are_prefrozen():
    assert FULL_ALIAS=={"A01":"F04","A02":"F03"}
