from pathlib import Path

from legsa_gins.raw_gnss.rtklib_doppler_helper_builder import (
    build_rtklib_doppler_helper,
    discover_rtklib_source_layout,
)


# 中文说明：helper builder 必须报告源码函数证据，并在缺文件时给出具体 blocker。


def test_discover_rtklib_source_layout_finds_functions(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    for name in ["rtklib.h", "pntpos.c", "rtkcmn.c", "ephemeris.c", "rinex.c", "preceph.c", "options.c", "solution.c", "geoid.c", "lambda.c", "sbas.c", "ionex.c"]:
        (src / name).write_text("pntpos estvel resdop satposs eph2pos geph2pos seleph readrnx\n", encoding="utf-8")
    report = discover_rtklib_source_layout(tmp_path)
    assert report["missing_source_files"] == []
    assert report["rtklib_source_functions_found"]["estvel"]


def test_helper_build_missing_sources_classified(tmp_path: Path):
    report = build_rtklib_doppler_helper(tmp_path / "missing", tmp_path / "build", tmp_path / "out")
    assert report["helper_compile_status"] == "failed"
    assert "missing_source_files" in report["blocker_reasons"]
