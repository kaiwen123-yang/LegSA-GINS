"""Executable counterexamples against actual project functions, not replacements.

Strict xfails describe verified defects/limitations, not a green implementation.
Synthetic byte frames never enter the real XBPG result tables.
"""
import struct

import pytest

from legsa_gins.input_generation import process_data_compat as compat
from legsa_gins.input_generation import status_yaw_builder as yaw
from legsa_gins.input_generation import ubx_nav_pvt as pvt
from legsa_gins.paper_rebuild.clean6_sensor_v21.providers import interpolate_a1


def frame():
    payload = bytearray(92)
    struct.pack_into("<iii", payload, 48, 1000, -2000, 3000)
    struct.pack_into("<i", payload, 60, 2236)
    struct.pack_into("<i", payload, 64, 1234567)
    struct.pack_into("<I", payload, 68, 50)
    content = b"\x01\x07\x5c\x00" + payload
    a = b = 0
    for c in content:
        a = (a + c) % 256
        b = (b + a) % 256
    return b"\xb5\x62" + content + bytes((a, b))


def test_nav_pvt_velocity_signed_and_scaled_correctly():
    result = pvt.parse_ubx_nav_pvt_payload(frame())
    assert [result[k] for k in ("vn", "ve", "vd")] == [1., -2., 3.]


@pytest.mark.xfail(strict=True, reason="P-IN-01: full-frame sAcc offset is 74, not 68")
def test_nav_pvt_sacc_protocol_offset():
    assert pvt.parse_ubx_nav_pvt_payload(frame())["sAcc"] == .05


@pytest.mark.xfail(strict=True, reason="P-IN-02: actual parser ignores UBX checksum")
def test_nav_pvt_bad_checksum_rejected():
    corrupted = frame()[:-1] + bytes([frame()[-1] ^ 1])
    with pytest.raises(ValueError):
        pvt.parse_ubx_nav_pvt_payload(corrupted)


@pytest.mark.xfail(strict=True, reason="P-IN-02: 92-byte truncated full frame accepted")
def test_nav_pvt_truncated_full_frame_rejected():
    with pytest.raises(ValueError):
        pvt.parse_ubx_nav_pvt_payload(frame()[:92])


@pytest.mark.xfail(strict=True, reason="P-IN-03: unlimited ffill+bfill erases missing support")
def test_missing_velocity_not_extended_one_hour():
    rows = [{"time": 0., "vn": 2.}, {"time": 3600., "vn": None}]
    compat._ffill_bfill(rows, ["vn"])
    assert rows[-1]["vn"] is None


@pytest.mark.xfail(strict=True, reason="P-IN-03: future nearest is legal without latency contract")
def test_online_nearest_must_not_read_future():
    assert compat._nearest([{"t": 1.05}], 1., key="t", tolerance=.1) is None


@pytest.mark.xfail(strict=True, reason="P-IN-04: old status interpolation has no gap limit")
def test_status_baseline_not_interpolated_across_hour():
    assert yaw._interp([{"t": 0., "n": 0.}, {"t": 3600., "n": 1.}], 1800., ["n"]) is None


def test_v21_a1_gap_rejects_interior_but_keeps_real_endpoints():
    _, valid = interpolate_a1([0., 1800., 3600.], [0., 3600.], [359., 1.])
    assert valid.tolist() == [True, False, True]


def test_v21_a1_wrap_uses_circle():
    import numpy as np
    values, valid = interpolate_a1([.5], [0., 1.], [359., 1.])
    assert valid.tolist() == [True]
    assert abs(np.rad2deg(values[0]) - 360.) < 1e-12


@pytest.mark.xfail(strict=True, reason="P-IN-05: malformed helper velocity silently becomes zero")
def test_nonfinite_doppler_velocity_not_coerced_to_zero(tmp_path):
    import math
    from legsa_gins.raw_gnss.rtklib_solution_velocity_parser import parse_helper_velocity_csv
    path = tmp_path / "helper.csv"
    path.write_text("time,vecef_x,vecef_y,vecef_z,std_vx,std_vy,std_vz,sat_count,provider_status\n1,nan,2,3,.2,.2,.2,7,available\n")
    rows = parse_helper_velocity_csv(path)
    assert not rows or not math.isfinite(rows[0]["vecef_x"])
