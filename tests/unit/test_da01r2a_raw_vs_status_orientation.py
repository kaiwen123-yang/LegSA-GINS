from legsa_gins.da_repro.orientation_audit import BaselineVector, compare_raw_to_status


def test_raw_vs_status_detects_unstable_direction():
    status = [
        BaselineVector(time=0.0, east_m=0.0, north_m=1.0, up_m=0.0, source="status"),
        BaselineVector(time=1.0, east_m=0.0, north_m=1.0, up_m=0.0, source="status"),
        BaselineVector(time=2.0, east_m=0.0, north_m=1.0, up_m=0.0, source="status"),
    ]
    raw = [
        BaselineVector(time=0.0, east_m=0.0, north_m=1.0, up_m=0.0, source="raw"),
        BaselineVector(time=1.0, east_m=1.0, north_m=0.0, up_m=0.0, source="raw"),
        BaselineVector(time=2.0, east_m=0.0, north_m=-1.0, up_m=0.0, source="raw"),
    ]
    rows, summary = compare_raw_to_status(raw, status)
    assert len(rows) == 3
    assert summary["direction_stable_against_status"] is False
    assert summary["p95_abs_heading_residual_deg"] >= 90.0
