from pathlib import Path

from legsa_gins.da_repro.dd_los_provider import parse_rtklib_moving_base_pos, provider_summary


def test_da3r2_dd_los_provider(tmp_path: Path):
    pos = tmp_path / "mb.pos"
    pos.write_text(
        "% header\n"
        "2026/03/06 08:01:14.000,1.0,0.0,0.0,1,8,0.01,0.01,0.02,0,0,0,0,4.0\n",
        encoding="utf-8",
    )
    rows = parse_rtklib_moving_base_pos(pos)
    assert len(rows) == 1
    assert rows[0].provider_status == "fixed"
    assert provider_summary(rows)["dd_los_ready"] is True
