from legsa_gins.da_repro.synthetic_clambda_validation import validate_synthetic_suite
from legsa_gins.da_repro.synthetic_dd_generator import generate_synthetic_suite


def test_synthetic_solver_validation_passes_exact_noise_free_cases():
    rows, summary = validate_synthetic_suite(generate_synthetic_suite(noise_levels_m=(0.0,)))
    assert rows
    assert summary["synthetic_validation_pass"] is True
    assert summary["max_length_error_m"] < 0.02
    assert summary["max_noise_free_direction_error_deg"] < 1.0
    assert summary["max_noise_free_yaw_abs_error_deg"] < 1.0
    assert summary["wrap_179_minus179_pass"] is True
    assert summary["swap_180_pass"] is True
    assert summary["lateral_plus90_pass"] is True
    assert summary["trace_used"] is False
