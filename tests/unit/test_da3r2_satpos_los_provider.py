from pathlib import Path

from legsa_gins.da_repro.satpos_los_provider import rinex_satpos_los_summary


def test_da3r2_satpos_los_provider(tmp_path: Path):
    obs = tmp_path / "a.obs"
    nav = tmp_path / "a.nav"
    obs.write_text("obs", encoding="utf-8")
    nav.write_text("nav", encoding="utf-8")
    report = rinex_satpos_los_summary([obs], [nav], 3)
    assert report["satpos_los_ready"] is True
    assert report["direct_python_satpos_implemented"] is False
