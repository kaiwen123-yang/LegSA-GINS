import math

from legsa_gins.da_repro.orientation_audit import BaselineVector
from legsa_gins.da_repro.synthetic_dd_generator import GPS_L1_WAVELENGTH_M
from legsa_gins.da_repro.wrapped_ls_solver import solve_cwls_baseline
from legsa_gins.da_repro.yaw_frame_contract import baseline_heading_from_enu, body_yaw_from_lateral_baseline, yaw_residual_deg


def test_da03_semisynthetic_toy_geometry_recovers_status_yaw():
    status = BaselineVector(time=0.0, east_m=-0.355147, north_m=0.0, up_m=0.0, source="status")
    h_rows = [
        [0.9, -0.2, 0.1],
        [-0.4, 0.8, 0.2],
        [0.2, 0.1, 0.9],
        [-0.7, -0.3, 0.4],
    ]
    carrier = []
    code = []
    for index, h in enumerate(h_rows):
        geom = h[0] * status.east_m + h[1] * status.north_m + h[2] * status.up_m
        code.append(geom)
        carrier.append(geom + GPS_L1_WAVELENGTH_M * (index - 2))
    solution = solve_cwls_baseline(
        h_rows=h_rows,
        carrier_m=carrier,
        code_m=code,
        wavelengths_m=[GPS_L1_WAVELENGTH_M] * len(h_rows),
        baseline_length_m=status.length_m,
        grid_count=64,
    )
    assert solution is not None
    east, north, _up = solution.baseline_vector_m
    yaw = body_yaw_from_lateral_baseline(baseline_heading_from_enu(east, north), offset_deg=90.0)
    status_yaw = body_yaw_from_lateral_baseline(status.heading_enu_deg, offset_deg=90.0)
    assert abs(yaw_residual_deg(yaw, status_yaw)) < 1.0
    assert math.isfinite(solution.objective)
