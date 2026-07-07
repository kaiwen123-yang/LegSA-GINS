from legsa_gins.da_repro.orientation_audit import BaselineVector, baseline_summary, body_yaw_candidate


def test_status_baseline_heading_and_reverse_candidate():
    vector = BaselineVector(time=1.0, east_m=1.0, north_m=0.0, up_m=0.0, source="status_g2_g1")
    reverse = vector.reversed(source="status_g1_g2")
    assert vector.heading_enu_deg == 90.0
    assert reverse.heading_enu_deg == 270.0
    assert body_yaw_candidate(vector.east_m, vector.north_m, coordinate_variant="ENU", lateral_offset_deg=90.0) == 180.0
    summary = baseline_summary([vector, reverse], label="unit")
    assert summary["epoch_count"] == 2
    assert summary["median_length_m"] == 1.0
