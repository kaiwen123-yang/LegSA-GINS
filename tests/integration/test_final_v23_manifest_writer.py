"""中文说明：integration 测试验证输出链路和合同文件，不依赖真实 raw data，不代表性能评价。
"""

import json
import subprocess
import sys
from pathlib import Path


def test_final_v23_manifest_writer_generates_required_fields(tmp_path):
    root = Path(__file__).resolve().parents[2]
    script = root / "baseline/final_v23_wrapper/scripts/write_final_v23_manifest.py"
    output_dir = tmp_path / "manifest"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output-dir",
            str(output_dir),
            "--dataset-name",
            "dummy_dataset",
            "--final-v23-root",
            "/tmp/nonexistent_final_v23",
            "--dry-run",
        ],
        check=True,
    )

    manifest = json.loads((output_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    required_fields = [
        "phase",
        "algorithm_role",
        "algorithm_name",
        "final_v23_is_proposed",
        "proposed_reads_final_v23_output",
        "final_v23_output_substitution",
        "trace_solver_input",
        "trace_used_for_tuning",
        "output_only_correction",
        "bad_epoch_deletion_for_metric",
        "raw_data_committed",
        "evidence_status",
    ]
    for field in required_fields:
        assert field in manifest
    assert manifest["algorithm_role"] == "baseline"
    assert manifest["evidence_status"] == "wrapper_only_until_real_final_v23_output_is_connected"
