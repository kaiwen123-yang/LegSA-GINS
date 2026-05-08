"""中文说明：UBX-NAV-PVT 单元测试只覆盖 process_data parity 字段，不解析 raw Doppler。"""

import struct

import pytest

from legsa_gins.input_generation.ubx_nav_pvt import parse_ubx_nav_pvt_payload


def _frame(vn, ve, vd, sacc):
    frame = bytearray(100)
    frame[:6] = bytes([0xB5, 0x62, 0x01, 0x07, 0x5C, 0x00])
    frame[54:58] = struct.pack("<i", vn)
    frame[58:62] = struct.pack("<i", ve)
    frame[62:66] = struct.pack("<i", vd)
    frame[68:72] = struct.pack("<I", sacc)
    return bytes(frame)


def test_parse_ubx_nav_pvt_payload_from_bytes_repr_and_list_repr():
    frame = _frame(1234, -5678, 90, 321)

    parsed = parse_ubx_nav_pvt_payload(repr(frame))
    assert parsed["vn"] == 1.234
    assert parsed["ve"] == -5.678
    assert parsed["vd"] == 0.09
    assert parsed["sAcc"] == 0.321

    parsed_list = parse_ubx_nav_pvt_payload(repr(list(frame)))
    assert parsed_list["vn"] == 1.234
    assert parsed_list["evidence_status"] == "decoded_ubx_nav_pvt_process_data_offsets"


def test_parse_ubx_nav_pvt_payload_rejects_non_pvt():
    frame = bytearray(_frame(1, 2, 3, 4))
    frame[3] = 0x08
    with pytest.raises(ValueError, match="UBX-NAV-PVT"):
        parse_ubx_nav_pvt_payload(repr(bytes(frame)))
