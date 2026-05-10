from pathlib import Path

from legsa_gins.raw_gnss.rtklib_discovery import discover_rtklib

# 中文说明：测试 RTKLIB discovery 的文件发现，不要求假 exe 真能运行。

def test_rtklib_discovery_finds_candidates(tmp_path: Path):
    root = tmp_path / "rtklib"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "convbin.exe").write_text("", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "pntpos.c").write_text("satposs(); eph2pos(); estvel();", encoding="utf-8")
    (root / "src" / "rtklib.h").write_text("int readrnx(void);", encoding="utf-8")
    report = discover_rtklib(root)
    assert report["rtklib_root_exists"] is True
    assert report["convbin_found"] is True
    assert report["source_tree_found"] is True
    assert report["candidate_source_files"]["pntpos.c"]
