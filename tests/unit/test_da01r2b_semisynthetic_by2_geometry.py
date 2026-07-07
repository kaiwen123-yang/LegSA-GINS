from legsa_gins.da_repro.orientation_audit import BaselineVector
from legsa_gins.da_repro.semisynthetic_by2_geometry_validation import run_semisynthetic_validation


def _toy_design_epochs(count=600):
    h_enu_rows = [
        (0.9, -0.2, 0.1),
        (-0.4, 0.8, 0.2),
        (0.2, 0.1, 0.9),
        (-0.7, -0.3, 0.4),
    ]
    epochs = []
    for index in range(count):
        rows = []
        for row_index, (east, north, up) in enumerate(h_enu_rows):
            # For lat=0/lon=0, ecef_delta_to_enu(dx,dy,dz) = (dy,dz,dx).
            rows.append(
                {
                    "h_x": up,
                    "h_y": east,
                    "h_z": north,
                    "weight": 1.0,
                    "satellite": f"G{row_index + 1:02d}",
                }
            )
        epochs.append(
            {
                "timestamp": float(index) * 0.2,
                "rcv_tow": float(index) * 0.2,
                "rank": 3,
                "num_dd": len(rows),
                "rows": rows,
            }
        )
    return epochs


def test_semisynthetic_geometry_recovers_status_baseline():
    status = [
        BaselineVector(time=float(index) * 0.2, east_m=-0.355147, north_m=0.0, up_m=0.0, source="status")
        for index in range(600)
    ]
    rows, summary = run_semisynthetic_validation(
        design_epochs=_toy_design_epochs(),
        status_vectors=status,
        receiver_lat_deg=0.0,
        receiver_lon_deg=0.0,
    )
    assert len(rows) == 600
    assert summary["semisynthetic_validation_pass"] is True
    assert 0.20 <= summary["median_recovered_baseline_length_m"] <= 0.60
    assert summary["median_baseline_vs_status_angle_deg"] < 2.0
    assert summary["body_yaw_vs_status_rmse_deg"] < 2.0
    assert summary["trace_used"] is False
    assert summary["per_case_offset"] is False
    assert summary["status_used_as_real_full_backend_output"] is False
