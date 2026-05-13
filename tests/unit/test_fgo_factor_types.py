from legsa_gins.fgo.fgo_factor_types import FGOFactorContract


def test_factor_contract_truth_flags_false() -> None:
    """中文说明：factor 合同默认不声明 truth。"""
    factor = FGOFactorContract("Toy", "toy", True, False, 1, ("velocity",), "toy", "diag")
    assert factor.truth_claim is False
    assert factor.to_dict()["trace_input"] is False
