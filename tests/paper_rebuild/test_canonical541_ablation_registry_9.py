from legsa_gins.paper_rebuild.canonical541.ablation_registry import ABLATION_METHODS,validate_tracked_ablation_contract


def test_ablation_methods_exact_tracked_identity():
    assert [m.effective_profile for m in ABLATION_METHODS]==["AB1111","AB0000","AB0111","AB1011","AB1101","AB1110","AB1100","AB1000","AB0100"]
    validate_tracked_ablation_contract("configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml")
