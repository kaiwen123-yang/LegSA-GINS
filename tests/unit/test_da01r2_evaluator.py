import csv

from legsa_gins.da_repro.full_backend_classic_runner import evaluate_yaw_with_max


def test_evaluator_reports_wrap_safe_max_abs(tmp_path):
    epoch = tmp_path / "epoch.csv"
    trace = tmp_path / "trace.csv"
    with epoch.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "body_yaw_deg"])
        writer.writeheader()
        writer.writerow({"timestamp": "1.0", "body_yaw_deg": "1.0"})
        writer.writerow({"timestamp": "2.0", "body_yaw_deg": "359.0"})
    with trace.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "yaw"])
        writer.writeheader()
        writer.writerow({"time": "1.0", "yaw": "359.0"})
        writer.writerow({"time": "2.0", "yaw": "1.0"})
    metrics = evaluate_yaw_with_max(str(epoch), str(trace))
    assert metrics["aligned_count"] == 2
    assert metrics["yaw_max_abs_deg"] == 2.0
    assert metrics["trace_used_online"] is False
