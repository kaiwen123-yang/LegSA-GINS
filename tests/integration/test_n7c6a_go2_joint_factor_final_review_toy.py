import csv
import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    """中文说明：写 toy JSON，仅用于临时集成测试目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_eval(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "yaw_deg", "roll_deg", "pitch_deg"])
        writer.writeheader()
        for index in range(8):
            writer.writerow({"time": index, "vn": 1.0, "yaw_deg": index * 0.1, "roll_deg": 0.1, "pitch_deg": -0.1})


def test_n7c6a_runner_toy(tmp_path: Path) -> None:
    n7c6 = tmp_path / "n7c6"
    variants = ["baseline_no_go2_proprioceptive", "joint_rp1deg_hv1p0", "joint_rp1p6deg_hv1p0"]
    full_variants = variants + [
        "joint_rp3deg_hv1p0",
        "joint_rp0p75_hv1p0_diagnostic",
        "joint_rp1p6deg_hv0p75_diagnostic",
        "joint_rp1p6deg_hv1p0_sourceaware_off",
        "rollpitch_only_5deg",
        "rollpitch_only_3deg",
        "rollpitch_only_1p6deg",
        "rollpitch_only_1deg",
        "receiver_velocity_stress_baseline",
        "receiver_velocity_stress_joint",
        "raw_doppler_stress_baseline",
        "raw_doppler_stress_joint",
        "horizontal_only_fixed_1p0",
    ]
    _write_json(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json", {"matrix": [{"variant_id": v} for v in full_variants], "required_variants_present": True})
    _write_json(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_VARIANT_SUMMARIES.json", {"variants": [{"variant_id": v, "summary": {"roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1}, "manifest": {"go2_proprioceptive_joint_factor_update_count": 8}} for v in full_variants]})
    _write_json(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_COMPARISON_REPORT.json", {"comparisons": {"joint_rp1deg_minus_horizontal_only": {"delta": {}}, "receiver_velocity_stress_joint_minus_baseline": {"delta": {}}, "raw_doppler_stress_joint_minus_baseline": {"delta": {}}}})
    _write_json(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json", {"variants": {v: {"attitude": {"nis_proxy": {"p95": 1}, "residual_norm": {"p95": 0.1}}, "horizontal_velocity": {"nis_proxy": {"p95": 1}, "residual_norm": {"p95": 0.1}}, "overconfidence_flag": False, "stuck_at_cap_flag": False} for v in full_variants}, "any_overconfidence": False, "any_stuck_at_cap": False})
    _write_json(n7c6 / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", {"status": "stronger_go2_proprioceptive_joint_factor_ready", "recommended_default": "joint_rp1deg_hv1p0"})
    _write_json(n7c6 / "N7C6_FIGURE_MANIFEST.json", {"required_figures": ["clean_yaw_error_baseline_vs_joint.png"], "required_figures_generated": True, "required_figures_nonempty": True})
    for variant in full_variants:
        _write_eval(n7c6 / "variants" / variant / "EVAL_NAV.csv")
    out = tmp_path / "out"
    figs = tmp_path / "figs"
    subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_n7c6a_go2_joint_factor_final_review.py",
            "--n7c6-root",
            str(n7c6),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ],
        check=True,
    )
    decision = json.loads((out / "N7C6A_FINAL_REVIEW_DECISION_REPORT.json").read_text(encoding="utf-8"))
    assert decision["status"] == "ready_to_merge_PR38_and_start_N8A"
