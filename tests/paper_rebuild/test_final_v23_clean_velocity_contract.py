import struct

from legsa_gins.paper_rebuild.final_v23_clean_input import (
    RECEIVER_VELOCITY_CONTRACT,
)
from legsa_gins.paper_rebuild.ubx_nav_pvt import parse_ubx_nav_pvt_frame


def test_clean_velocity_uses_correct_full_frame_offsets_and_fixed_std() -> None:
    frame = bytearray(100)
    frame[:4] = bytes([0xB5, 0x62, 0x01, 0x07])
    frame[54:58] = struct.pack("<i", 1250)
    frame[58:62] = struct.pack("<i", -2500)
    frame[62:66] = struct.pack("<i", 3750)
    frame[68:72] = struct.pack("<I", 4_000_000_000)
    frame[74:78] = struct.pack("<I", 125)

    decoded = parse_ubx_nav_pvt_frame(frame)

    assert RECEIVER_VELOCITY_CONTRACT["vel_n_full_frame"] == [54, 58]
    assert RECEIVER_VELOCITY_CONTRACT["vel_e_full_frame"] == [58, 62]
    assert RECEIVER_VELOCITY_CONTRACT["vel_d_full_frame"] == [62, 66]
    assert RECEIVER_VELOCITY_CONTRACT["sAcc_full_frame"] == [74, 78]
    assert decoded["vn"] == 1.25
    assert decoded["ve"] == -2.5
    assert decoded["vd"] == 3.75
    assert decoded["sAcc"] == 0.125
    assert RECEIVER_VELOCITY_CONTRACT["provider_std_mps"] == [0.05, 0.05, 0.05]
    assert RECEIVER_VELOCITY_CONTRACT["sAcc_used_for_provider_std"] is False
