from legsa_gins.external_literature.provider_factory import geodetic_to_enu


def test_da2r2_geodetic_to_enu_origin_is_zero():
    origin = (39.0, 116.0, 40.0)
    n, e, u = geodetic_to_enu(39.0, 116.0, 40.0, origin)
    assert abs(n) < 1e-6
    assert abs(e) < 1e-6
    assert abs(u) < 1e-6
