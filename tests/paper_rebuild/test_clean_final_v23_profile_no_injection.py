from pathlib import Path

from legsa_gins.paper_rebuild.final_v23_clean_input import (
    PROFILE_ID,
    load_contract,
    validate_clean_profile,
)


CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "configs/paper_rebuild/final_v23_parity_contract.yaml"
)


def test_clean_profile_keeps_measurement_std_separate_from_injection() -> None:
    contract = load_contract(CONTRACT)
    profile = contract["profiles"][PROFILE_ID]
    validate_clean_profile(profile)

    assert profile["yaw_measurement_std_deg"] == 1.5
    assert profile["yaw_noise_injection_enabled"] is False
    assert profile["yaw_noise_injection_std_deg"] == 0.0
    assert profile["yaw_noise_seed"] is None
    assert profile["data_mode"] == "real_by2_raw"
    assert profile["clean_solver_input_eligible"] is True
    assert profile["E001_old_input_used_by_solver"] is False
