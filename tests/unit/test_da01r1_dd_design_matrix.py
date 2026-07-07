from legsa_gins.da_repro.dd_design_matrix import build_dd_design_epochs, dd_design_summary


def _sat(key, sat_id, los, elevation):
    return {
        "satellite_key": key,
        "sat_id": sat_id,
        "constellation": "GPS",
        "frequency": "L1",
        "valid_flag": True,
        "elevation_deg": elevation,
        "cno_avg_dbhz": 45.0,
        "pr1_m": 20_000_000.0,
        "pr2_m": 20_000_000.4,
        "cp1_cycles": 100.0,
        "cp2_cycles": 101.0,
        "wavelength_m": 0.1902936728,
        "los1_x": los[0],
        "los1_y": los[1],
        "los1_z": los[2],
    }


def test_dd_design_matrix_has_rank_three():
    epoch = {
        "rcv_tow": 1.0,
        "timestamp": 10.0,
        "satellites": [
            _sat("0:1:0:0", "G01", (0.0, 0.0, 1.0), 80.0),
            _sat("0:2:0:0", "G02", (1.0, 0.0, 0.0), 20.0),
            _sat("0:3:0:0", "G03", (0.0, 1.0, 0.0), 25.0),
            _sat("0:4:0:0", "G04", (0.5, 0.5, 0.707), 30.0),
        ],
    }
    design = build_dd_design_epochs([epoch])
    assert design[0]["rank"] == 3
    assert design[0]["num_dd"] == 3
    assert design[0]["all_zero_h"] is False
    assert dd_design_summary(design)["usable_dd_epochs"] == 1
