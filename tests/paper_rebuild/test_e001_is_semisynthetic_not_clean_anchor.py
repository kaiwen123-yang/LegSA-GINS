from pathlib import Path

from legsa_gins.paper_rebuild.final_v23_clean_input import load_contract


CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "configs/paper_rebuild/final_v23_parity_contract.yaml"
)


def test_e001_is_semisynthetic_diagnostic_not_clean_anchor() -> None:
    contract = load_contract(CONTRACT)
    e001 = contract["profiles"]["archived_E001_semisynthetic"]
    correction = contract["profile_identity_correction"]

    assert e001["role"] == "ARCHIVED_SEMISYNTHETIC_DIAGNOSTIC_REFERENCE_ONLY"
    assert e001["data_mode"] == "semisynthetic"
    assert e001["yaw_noise_injection_enabled"] is True
    assert e001["yaw_noise_injection_std_deg"] == 1.5
    assert e001["yaw_noise_seed"] == 42
    assert e001["trace_used_during_input_generation"] is True
    assert e001["clean_solver_input_eligible"] is False
    assert e001["strict_clean_input_parity_target"] is False
    assert correction["E001_selected_as_clean_input_anchor"] is False
    assert correction["E001_selected_as_static_runtime_field_source"] is True
    assert correction["E001_old_input_used_by_solver"] is False
    assert correction["nominal_none_does_not_mean_clean_real_input"] is True
