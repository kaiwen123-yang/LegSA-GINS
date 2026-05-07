"""中文说明：integration 测试验证输出链路和合同文件，不依赖真实 raw data，不代表性能评价。
"""

import json
import subprocess
import sys
from pathlib import Path


def test_standardize_final_v23_outputs(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = root / "baseline/final_v23_reproduction/scripts/standardize_final_v23_outputs.py"
    nav = tmp_path / "KF_GINS_Navresult.nav"
    std = tmp_path / "KF_GINS_STD.txt"
    imu = tmp_path / "KF_GINS_IMU_ERR.txt"
    output_dir = tmp_path / "out"

    nav.write_text(
        "\n".join(
            [
                "0 100.0 36.0 120.0 10.0 1.0 2.0 -0.1 0.5 -0.3 45.0",
                "0 101.0 36.00001 120.00001 10.2 1.1 2.1 -0.1 0.6 -0.2 45.5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    std.write_text(
        "\n".join(
            [
                "100.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
                "101.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    imu.write_text(
        "\n".join(
            [
                "100.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
                "101.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--nav",
            str(nav),
            "--std",
            str(std),
            "--imu-err",
            str(imu),
            "--output-dir",
            str(output_dir),
            "--dataset-name",
            "toy_dataset",
            "--source-root",
            "/tmp/external_kfgins",
        ],
        check=True,
    )

    for filename in [
        "FINAL_V23_NAV.csv",
        "FINAL_V23_STD.csv",
        "FINAL_V23_IMU_ERR.csv",
        "FINAL_V23_EVAL_NAV.csv",
        "RUN_MANIFEST.json",
    ]:
        assert (output_dir / filename).exists()

    manifest = json.loads((output_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["algorithm_role"] == "baseline"
    for flag in [
        "final_v23_is_proposed",
        "proposed_reads_final_v23_output",
        "final_v23_output_substitution",
        "trace_solver_input",
        "trace_used_for_tuning",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "raw_data_committed",
        "numerical_claim_without_oracle_pass",
    ]:
        assert manifest[flag] is False
