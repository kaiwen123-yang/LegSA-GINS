import csv
from pathlib import Path
import struct

import pytest

from scripts.paper_rebuild import finalize_clean1r2_blocked as finalizer
from legsa_gins.paper_rebuild.ubx_nav_pvt import parse_ubx_nav_pvt_frame
from legsa_gins.paper_rebuild import providers


def test_receiver_velocity_offsets_and_std_addition_are_closed() -> None:
    contract = finalizer.load_contract()["receiver_velocity_contract"]
    assert contract["nav_pvt_full_message_offsets"]["vel_n"]["start"] == 54
    assert contract["nav_pvt_full_message_offsets"]["vel_d"]["end_exclusive"] == 66
    assert contract["nav_pvt_full_message_offsets"]["archived_sAcc_bug"] == {
        "start": 68,
        "end_exclusive": 72,
    }
    assert contract["nav_pvt_full_message_offsets"]["corrected_sAcc"]["start"] == 74
    assert contract["sAcc_used_by_archived_provider"] is False
    assert contract["provider_std_mps"] == [0.05, 0.05, 0.05]
    assert contract["solver_extra_std_addition_mps"] == [0.05, 0.05, 0.05]
    assert contract["solver_extra_std_is_floor"] is False
    assert contract["effective_pre_scale_std_mps"] == [0.1, 0.1, 0.1]


def test_blocked_report_records_active_clean_parser_repair() -> None:
    audit = finalizer.build_receiver_velocity_audit()
    assert audit["corrected_sAcc_offset_full_message"] == [74, 78]
    assert audit["active_clean_parser_fixed_by_this_stage"] is True


def test_active_clean_parser_reads_sacc_from_full_frame_74_to_78() -> None:
    frame = bytearray(100)
    frame[:4] = bytes([0xB5, 0x62, 0x01, 0x07])
    frame[54:58] = struct.pack("<i", 1_250)
    frame[58:62] = struct.pack("<i", -2_500)
    frame[62:66] = struct.pack("<i", 3_750)
    frame[68:72] = struct.pack("<I", 4_000_000_000)
    frame[74:78] = struct.pack("<I", 125)

    decoded = parse_ubx_nav_pvt_frame(frame)

    assert decoded["vn"] == 1.25
    assert decoded["ve"] == -2.5
    assert decoded["vd"] == 3.75
    assert decoded["sAcc"] == 0.125
    assert decoded["evidence_status"] == "decoded_ubx_nav_pvt_full_frame_offsets_v1"


def _write_raw_fixture(tmp_path: Path) -> Path:
    frame = bytearray(100)
    frame[:4] = bytes([0xB5, 0x62, 0x01, 0x07])
    frame[54:58] = struct.pack("<i", 1_000)
    frame[58:62] = struct.pack("<i", 2_000)
    frame[62:66] = struct.pack("<i", -3_000)
    frame[68:72] = struct.pack("<I", 3_000_000_000)
    frame[74:78] = struct.pack("<I", 250)
    path = tmp_path / "gnss1-raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["name", "stamp.secs", "stamp.nsecs", "data"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "name": "UBX-NAV-PVT",
                "stamp.secs": "100",
                "stamp.nsecs": "0",
                "data": repr(bytes(frame)),
            }
        )
    return path


def test_compat_builder_adapter_uses_active_parser_and_restores_on_success(
    tmp_path, monkeypatch
) -> None:
    raw = _write_raw_fixture(tmp_path)

    def fake_builder(*args, **kwargs):
        assert (
            providers._shared_process_data_compat.extract_pvt_velocity_rows
            is providers._active_clean_pvt_extractor
        )
        rows = providers._shared_process_data_compat.extract_pvt_velocity_rows(
            raw, base_time=0.0
        )
        return {"sAcc": rows[0]["sAcc"]}

    monkeypatch.setattr(
        providers._shared_process_data_compat,
        "generate_process_data_compat_inputs",
        fake_builder,
    )
    result = providers._generate_process_data_compat_with_active_pvt()

    assert result["sAcc"] == 0.25
    assert (
        providers._shared_process_data_compat.extract_pvt_velocity_rows
        is providers._expected_shared_pvt_extractor
    )


def test_compat_builder_adapter_restores_on_failure(monkeypatch) -> None:
    def failing_builder(*args, **kwargs):
        assert (
            providers._shared_process_data_compat.extract_pvt_velocity_rows
            is providers._active_clean_pvt_extractor
        )
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(
        providers._shared_process_data_compat,
        "generate_process_data_compat_inputs",
        failing_builder,
    )
    with pytest.raises(RuntimeError, match="fixture failure"):
        providers._generate_process_data_compat_with_active_pvt()
    assert (
        providers._shared_process_data_compat.extract_pvt_velocity_rows
        is providers._expected_shared_pvt_extractor
    )


def test_compat_builder_adapter_fails_closed_on_unexpected_shared_binding(
    monkeypatch,
) -> None:
    unexpected = lambda *args, **kwargs: []
    monkeypatch.setattr(
        providers._shared_process_data_compat,
        "extract_pvt_velocity_rows",
        unexpected,
    )
    with pytest.raises(providers.ProviderGenerationError, match="identity changed"):
        providers._generate_process_data_compat_with_active_pvt()
    assert providers._shared_process_data_compat.extract_pvt_velocity_rows is unexpected
