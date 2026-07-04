from legsa_gins.da_repro.csv_to_rinex_obs_writer import rebuild_ubx, run_convbin


def test_da3r2_rinex_bridge_exports_symbols():
    assert callable(rebuild_ubx)
    assert callable(run_convbin)
