from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS, validate_tracked_method_contract


def test_full_methods_exact_tracked_identity():
    assert [m.method_id for m in FULL_METHODS]==["F01","F02","F03","F04"]
    assert [m.flags["scheme_c"] for m in FULL_METHODS]==[False,False,True,True]
    validate_tracked_method_contract("configs/paper_rebuild/methods.yaml")
