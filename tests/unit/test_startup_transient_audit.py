"""中文说明：测试 startup transient 审计，不允许删 epoch 或裁剪指标。"""

import csv
import json
from pathlib import Path

from legsa_gins.visualization.startup_transient_audit import analyze_startup_transient


def _write_error_series(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "horizontal_error_m",
                "up_error_m",
                "yaw_error_deg",
                "roll_error_deg",
                "pitch_error_deg",
            ],
        )
        writer.writeheader()
        for index in range(20):
            writer.writerow(
                {
                    "timestamp": index,
                    "horizontal_error_m": 0.3,
                    "up_error_m": 2.0 if index <= 10 else 0.2,
                    "yaw_error_deg": 1.0,
                    "roll_error_deg": 3.1 if index <= 10 else 0.2,
                    "pitch_error_deg": 0.8,
                }
            )


def test_first_10s_bump_triggers_visible_and_within_gate(tmp_path):
    error = tmp_path / "err.csv"
    summary = tmp_path / "summary.json"
    _write_error_series(error)
    summary.write_text(json.dumps({"count": 20}), encoding="utf-8")
    report = analyze_startup_transient(error, summary)
    first_10 = report["windows"]["first_10s"]
    assert first_10["up_max_abs_m"] == 2.0
    assert first_10["roll_max_abs_deg"] == 3.1
    assert report["startup_transient_visible"]
    assert report["startup_transient_within_gate"]
    assert not report["deletion_or_crop_allowed"]
    assert not report["numerical_performance_claim"]
