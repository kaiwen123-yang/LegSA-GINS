"""中文说明：N4F toy integration 不依赖真实 BY2 路径。"""

import json
import subprocess
import sys


def test_by2_filter_trial_toy_generates_outputs(tmp_path):
    output_dir = tmp_path / "trial"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_by2_filter_core_trial.py",
            "--toy",
            "--output-dir",
            str(output_dir),
            "--max-filter-epochs",
            "140",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    for rel_path in [
        "run/LegSA_NAV.nav",
        "run/LegSA_STD.csv",
        "run/EVAL_NAV.csv",
        "run/RUN_MANIFEST.json",
        "evaluation/error_series.csv",
        "evaluation/summary.json",
        "case_review.md",
        "BY2_FILTER_TRIAL_MANIFEST.json",
    ]:
        assert (output_dir / rel_path).exists(), rel_path

    summary = json.loads((output_dir / "evaluation/summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output_dir / "BY2_FILTER_TRIAL_MANIFEST.json").read_text(encoding="utf-8")
    )
    run_manifest = json.loads(
        (output_dir / "run/RUN_MANIFEST.json").read_text(encoding="utf-8")
    )
    case_review = (output_dir / "case_review.md").read_text(encoding="utf-8")

    assert summary["count"] > 100
    assert manifest["trace_solver_input"] is False
    assert manifest["raw_doppler_claim"] is False
    assert manifest["numerical_performance_claim"] is False
    assert run_manifest["receiver_imu_as_body_imu"] is False
    assert run_manifest["go2_prior_claim"] is False
    assert "dual_final_v23 horizontal_rmse_m = 0.353" in case_review

