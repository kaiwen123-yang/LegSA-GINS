from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


def test_fgo_state_vector_and_dataset_count() -> None:
    """中文说明：状态节点是离线诊断节点，不回写 EKF。"""
    dataset = FGOStateDataset([FGOState(index=0, time=1.0, vn_mps=2.0)])
    assert dataset.state_count == 1
    assert dataset.states[0].vector()[6] == 2.0
