from legsa_gins.da_repro.orientation_audit import BaselineVector, transform_candidate_rows


def test_transform_candidates_are_deterministic_and_not_trace_selected():
    raw = [BaselineVector(time=1.0, east_m=1.0, north_m=0.0, up_m=0.0, source="raw")]
    status = [BaselineVector(time=1.0, east_m=1.0, north_m=0.0, up_m=0.0, source="status")]
    rows = transform_candidate_rows(raw, status)
    assert len(rows) == 32
    assert {row["vector_order"] for row in rows} == {"GNSS2-GNSS1", "GNSS1-GNSS2"}
    assert {row["lateral_offset_deg"] for row in rows} == {90.0, -90.0, 0.0, 180.0}
    assert all(row["trace_used_for_selection"] is False for row in rows)
