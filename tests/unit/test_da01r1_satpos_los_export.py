import math

from legsa_gins.da_repro.rinex_nav_satpos import GpsBroadcastEphemeris, choose_ephemeris, gps_satellite_position_ecef


def test_gps_broadcast_satpos_is_finite():
    eph = GpsBroadcastEphemeris(
        prn=3,
        toe=100000.0,
        sqrt_a=5153.7,
        eccentricity=0.01,
        delta_n=4.5e-9,
        m0=0.2,
        omega0=1.0,
        inclination0=0.96,
        argument_of_perigee=0.5,
        omega_dot=-8.0e-9,
        idot=0.0,
        cuc=1.0e-6,
        cus=2.0e-6,
        crc=200.0,
        crs=-80.0,
        cic=1.0e-7,
        cis=-1.0e-7,
    )
    selected = choose_ephemeris([eph], 3, 100030.0)
    assert selected is eph
    pos = gps_satellite_position_ecef(eph, 100030.0)
    assert all(math.isfinite(value) for value in pos)
    assert 20_000_000.0 < math.sqrt(sum(value * value for value in pos)) < 30_000_000.0
