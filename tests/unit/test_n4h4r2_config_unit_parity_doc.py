"""中文说明：检查 R2 config 单位文档覆盖关键 KF-GINS 转换。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_n4h4r2_config_unit_doc_terms():
    text = (ROOT / "docs/experiments/n4h4r2_config_unit_parity.md").read_text(encoding="utf-8")
    for term in ["deg/hour", "rad/second", "mGal", "ppm", "corrtime", "2 / corr_time"]:
        assert term in text
    assert "final_v23 outputs as solver input" in text
