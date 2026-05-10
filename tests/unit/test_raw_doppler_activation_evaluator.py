from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_activation_evaluator import find_clean_config, find_clean_gnss
from legsa_gins.raw_gnss.raw_doppler_n5b_decision import decide_n5b_activation


# 中文说明：activation decision 必须把 update_count=0 标成 blocker，而不是 completed。


def test_clean_root_discovery_and_decision(tmp_path: Path):
    root = tmp_path / "clean"
    root.mkdir()
    (root / "kf-gins-n4h2g-clean-replay.yaml").write_text("imupath: toy\n", encoding="utf-8")
    (root / "CLEAN_STATUS_YAW.gnss").write_text("1 30 120 10\n", encoding="utf-8")
    assert find_clean_config(root).name.endswith(".yaml")
    assert find_clean_gnss(root).name.endswith(".gnss")
    decision = decide_n5b_activation(
        {"helper_compile_status": "success", "blocker_reasons": []},
        {"factor_valid_epoch_count": 1, "covariance_available": True, "blocker_reasons": []},
        {"factor_csv_generated": True, "blocker_reasons": []},
        {"real_activation_status": "activation_failed_update_alignment_or_loader", "raw_doppler_update_count": 0, "blocker_reasons": []},
    )
    assert decision["recommended_next_stage"] == "N5B2_raw_doppler_time_alignment_fix"
