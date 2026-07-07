import numpy as np

from legsa_gins.da_repro.synthetic_dd_generator import generate_synthetic_suite
from legsa_gins.da_repro.wrapped_ls_solver import solve_cwls_baseline, wrap_cycles


def test_wrap_cycles_half_down_interval():
    values = np.asarray([-0.51, -0.50, -0.49, 0.49, 0.50, 0.51])
    wrapped = wrap_cycles(values)
    assert np.all(wrapped > -0.500000001)
    assert np.all(wrapped <= 0.500000001)
    assert wrapped[1] == 0.5
    assert wrapped[4] == 0.5


def test_wrapped_ls_solver_recovers_noise_free_synthetic_baseline():
    case = generate_synthetic_suite(noise_levels_m=(0.0,))[0]
    rows = list(case.rows)
    solution = solve_cwls_baseline(
        h_rows=[[row["h_east"], row["h_north"], row["h_up"]] for row in rows],
        carrier_m=[row["dd_carrier_m"] for row in rows],
        code_m=[row["dd_code_m"] for row in rows],
        wavelengths_m=[row["wavelength_m"] for row in rows],
        weights=[row["weight"] for row in rows],
        baseline_length_m=0.355147,
        grid_count=64,
    )
    assert solution is not None
    assert solution.wrapped_phase_rms_cycles < 1.0e-9
    assert solution.code_residual_rms_m < 1.0e-9
    assert abs(solution.baseline_vector_m[0] + 0.355147) < 1.0e-6
