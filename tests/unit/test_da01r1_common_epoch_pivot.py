from legsa_gins.da_repro.pivot_satellite_selector import build_pivot_selection_rows, select_pivot_satellite


def test_pivot_selects_highest_elevation_without_trace():
    sats = [
        {"sat_id": "G03", "elevation_deg": 20.0, "cno_avg_dbhz": 45.0, "valid_flag": True},
        {"sat_id": "G11", "elevation_deg": 70.0, "cno_avg_dbhz": 35.0, "valid_flag": True},
        {"sat_id": "G22", "elevation_deg": 65.0, "cno_avg_dbhz": 50.0, "valid_flag": True},
        {"sat_id": "G19", "elevation_deg": 10.0, "cno_avg_dbhz": 40.0, "valid_flag": True},
    ]
    assert select_pivot_satellite(sats)["sat_id"] == "G11"
    rows = build_pivot_selection_rows([{"rcv_tow": 1.0, "timestamp": 10.0, "satellites": sats}])
    assert rows[0]["pivot_selected"] is True
    assert rows[0]["trace_used_for_selection"] is False
