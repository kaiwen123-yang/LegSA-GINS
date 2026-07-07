from legsa_gins.da_repro.method_liu_cwls import METHOD_ID, solve_cwls_design_epochs
from legsa_gins.da_repro.receiver_position import ReceiverApproxPosition
from legsa_gins.da_repro.synthetic_dd_generator import GPS_L1_WAVELENGTH_M


def test_da03_clean_full_backend_toy_epoch_outputs_required_fields():
    true_baseline = [-0.355147, 0.0, 0.0]
    h_rows = [
        [0.9, -0.2, 0.1],
        [-0.4, 0.8, 0.2],
        [0.2, 0.1, 0.9],
        [-0.7, -0.3, 0.4],
    ]
    rows = []
    for index, h in enumerate(h_rows):
        geom = sum(a * b for a, b in zip(h, true_baseline))
        rows.append(
            {
                "h_x": h[0],
                "h_y": h[1],
                "h_z": h[2],
                "dd_code_m": geom,
                "dd_carrier_m": geom + GPS_L1_WAVELENGTH_M * (index - 2),
                "wavelength_m": GPS_L1_WAVELENGTH_M,
                "weight": 1.0,
            }
        )
    receiver = ReceiverApproxPosition("gnss1", "test", 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, "test", True)
    outputs, ambiguity = solve_cwls_design_epochs(
        [{"timestamp": 1.0, "rcv_tow": 1.0, "rank": 3, "num_dd": len(rows), "condition_number": 2.0, "rows": rows}],
        receiver1_position=receiver,
        nominal_length_m=0.355147,
        grid_count=64,
    )
    assert len(outputs) == 1
    assert ambiguity
    assert outputs[0]["method_id"] == METHOD_ID
    assert outputs[0]["method_mode"] == "full_backend"
    assert outputs[0]["trace_used_online"] is False
    assert outputs[0]["status_diagnostic_used_as_full_backend"] is False
