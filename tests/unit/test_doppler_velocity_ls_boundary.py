import math

from legsa_gins.raw_gnss.doppler_velocity_ls import solve_raw_doppler_velocity
from legsa_gins.raw_gnss.raw_doppler_types import RawDopplerMeasurement, ReceiverApproxState, SatelliteState

# 中文说明：测试 provider-backed LS 和 provider_missing 边界。

class SyntheticProvider:
    def __init__(self, states):
        self.states = states

    def state_for(self, measurement):
        return self.states[(measurement.gnss_id, measurement.sv_id)]


def make_measurement(sv_id: int, los, sat_vel, receiver_vel=(10.0, -2.0, 1.0)):
    wavelength = 0.190293672798
    rr = sum(l * (rv - sv) for l, rv, sv in zip(los, receiver_vel, sat_vel))
    return RawDopplerMeasurement(
        time=1.0,
        rcv_tow=1.0,
        week=2408,
        gnss_id=0,
        sv_id=sv_id,
        sig_id=0,
        freq_id=0,
        pr_mes=2.1e7,
        cp_mes=0.0,
        do_mes_hz=-rr / wavelength,
        cno=45.0,
        do_stdev=1,
        trk_stat=7,
        wavelength_m=wavelength,
    )


def test_provider_missing_returns_none():
    receiver = ReceiverApproxState(0.0, 0.0, (0.0, 0.0, 0.0))
    assert solve_raw_doppler_velocity([], None, receiver) is None


def test_rawx_with_synthetic_satellite_states_solves_velocity():
    receiver = ReceiverApproxState(0.0, 0.0, (0.0, 0.0, 0.0))
    sat_positions = [
        (20_000_000.0, 0.0, 0.0),
        (0.0, 20_000_000.0, 0.0),
        (0.0, 0.0, 20_000_000.0),
        (14_000_000.0, 14_000_000.0, 0.0),
        (14_000_000.0, 0.0, 14_000_000.0),
    ]
    sat_vel = (0.0, 0.0, 0.0)
    measurements = []
    states = {}
    for index, pos in enumerate(sat_positions, start=1):
        norm = math.sqrt(sum(v * v for v in pos))
        los = tuple(v / norm for v in pos)
        measurements.append(make_measurement(index, los, sat_vel))
        states[(0, index)] = SatelliteState(1.0, 0, index, pos, sat_vel)
    solution = solve_raw_doppler_velocity(measurements, SyntheticProvider(states), receiver, min_sat=5)
    assert solution is not None
    assert solution.provider_status == "available"
    assert solution.sat_count == 5
