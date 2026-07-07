import csv

from legsa_gins.da_repro.rinex_bridge import summarize_rinex_obs
from legsa_gins.da_repro.ubx_rebuilder import rebuild_receiver_ubx
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import ubx_checksum


def _frame(payload: bytes = b"abc") -> bytes:
    body = b"\x02\x15" + len(payload).to_bytes(2, "little") + payload
    ck_a, ck_b = ubx_checksum(body)
    return b"\xb5\x62" + body + bytes([ck_a, ck_b])


def _write_raw(path):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "protocol", "data", "name", "seq", "info"])
        writer.writeheader()
        writer.writerow({"Time": "1", "protocol": "4", "data": repr(_frame()), "name": "UBX-RXM-RAWX", "seq": "1", "info": ""})


def test_rebuild_receiver_ubx_and_summarize_rinex(tmp_path):
    _write_raw(tmp_path / "gnss1-raw.csv")
    _write_raw(tmp_path / "gnss2-raw.csv")
    report = rebuild_receiver_ubx(tmp_path, tmp_path / "ubx")
    assert report["rebuilt_ubx_available"] is True
    assert (tmp_path / "ubx" / "gnss1.ubx").exists()

    obs = tmp_path / "toy.obs"
    obs.write_text(
        "     3.04           OBSERVATION DATA    M                   RINEX VERSION / TYPE\n"
        "                                                            END OF HEADER\n"
        "> 2026 03 06 00 00 00.0000000  0  2\n"
        "G01  1.0  2.0\n"
        "C02  1.0  2.0\n",
        encoding="utf-8",
    )
    summary = summarize_rinex_obs(obs)
    assert summary["epoch_count"] == 1
    assert summary["satellite_observation_count"] == 2
    assert summary["systems"] == {"C": 1, "G": 1}
