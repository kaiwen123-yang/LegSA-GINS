import csv
from pathlib import Path

from legsa_gins.raw_gnss.raw_doppler_spike_audit import audit_raw_doppler_spikes


def test_raw_doppler_spike_audit_detects_two_spikes_without_rejection(tmp_path: Path):
    # 中文说明：spike 只报告不删除、不调 gate、不在 N5D1 中拒绝。
    factor = tmp_path / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    with factor.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for index in range(20):
            vn = 1.0
            if index == 10:
                vn = 8.0
            if index == 11:
                vn = 1.0
            writer.writerow({"time": index, "vn": vn, "ve": 0.2, "vd": -0.1, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 30, "provider_status": "available", "quality_flag": "ok"})
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("\n".join(f"{i} 0 0 0 0 0 0 1.0 0.2 -0.1 0 0 0 0 0" for i in range(20)) + "\n", encoding="utf-8")
    report = audit_raw_doppler_spikes(factor_csv=factor, receiver_velocity_path=gnss, update_manifest={"raw_doppler_update_count": 10, "raw_doppler_reject_count": 0})
    assert report["spike_count"] == 2
    assert report["spike_epochs_removed"] is False
    assert report["gate_tuned"] is False
    assert all(spike["rejected"] is False for spike in report["spike_epochs"])
    assert all("component_jumps" in spike for spike in report["spike_epochs"])
