from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# 中文说明：测试文档和 C++ loader 都禁止 PVT/.gnss 冒充 raw Doppler。

def test_docs_and_scanner_guard_nav_pvt_not_raw_doppler():
    doc = (ROOT / "docs/experiments/n5a_raw_gnss_message_scan.md").read_text(encoding="utf-8")
    scanner = (ROOT / "src/legsa_gins/raw_gnss/ubx_raw_message_scanner.py").read_text(encoding="utf-8")
    loader = (ROOT / "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp").read_text(encoding="utf-8")
    assert "NAV-PVT velocity is not raw Doppler" in doc
    assert ".gnss vn/ve/vd" in doc
    assert "pvt_velocity_not_raw_doppler" in scanner
    assert "不能读取 NAV-PVT 或 .gnss" in loader
