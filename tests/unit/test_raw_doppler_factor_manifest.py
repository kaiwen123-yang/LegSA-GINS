from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：测试 C++ manifest 暴露 raw Doppler 计数且默认关闭。

def test_raw_doppler_default_disabled_and_manifest_fields_present():
    types = (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/raw_doppler_types.hpp").read_text(
        encoding="utf-8"
    )
    manifest_writer = (ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp").read_text(encoding="utf-8")
    assert "bool enable_raw_doppler = false" in types
    assert "raw_doppler_update_count" in manifest_writer
    assert "raw_doppler_solver_enabled" in manifest_writer
