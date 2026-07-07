import math

from legsa_gins.da_repro.float_baseline_solver import float_baseline_summary, solve_float_baseline_epochs
from legsa_gins.da_repro.receiver_position import ReceiverApproxPosition


def test_float_baseline_projects_to_physical_length():
    receiver = ReceiverApproxPosition(
        receiver_id="gnss1",
        source="unit_test",
        x_ecef=6378137.0,
        y_ecef=0.0,
        z_ecef=0.0,
        lat_deg=0.0,
        lon_deg=0.0,
        height_m=0.0,
        time_span="static",
        source_allowed=True,
    )
    design = [
        {
            "rcv_tow": 1.0,
            "timestamp": 10.0,
            "num_dd": 3,
            "rank": 3,
            "condition_number": 1.0,
            "rows": [
                {"h_x": 1.0, "h_y": 0.0, "h_z": 0.0, "dd_code_m": 10.0, "dd_carrier_m": 10.0, "wavelength_m": 0.19, "weight": 1.0},
                {"h_x": 0.0, "h_y": 1.0, "h_z": 0.0, "dd_code_m": 1.0, "dd_carrier_m": 1.0, "wavelength_m": 0.19, "weight": 1.0},
                {"h_x": 0.0, "h_y": 0.0, "h_z": 1.0, "dd_code_m": 0.5, "dd_carrier_m": 0.5, "wavelength_m": 0.19, "weight": 1.0},
            ],
        }
    ]
    rows, ambiguity = solve_float_baseline_epochs(design, receiver1_position=receiver, nominal_length_m=0.355)
    assert len(rows) == 1
    assert math.isclose(rows[0]["baseline_length_m"], 0.355, rel_tol=0.0, abs_tol=1e-9)
    assert ambiguity[0]["integer_fix_attempted"] is True
    assert float_baseline_summary(rows)["physical_gate_pass"] is True
