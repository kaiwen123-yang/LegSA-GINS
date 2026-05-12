#!/usr/bin/env python3
"""Audit N6B1 source-aware visual validation.

中文说明：审计使用 synthetic toy 数据验证 N6B1 图像、coverage、sanity、decision
链路；不读取真实 runtime 路径，不修改 solver，不提交图像。
"""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "src/legsa_gins/source_aware/source_aware_n6b_visual_loader.py",
    "src/legsa_gins/source_aware/source_aware_n6b_visual_plots.py",
    "src/legsa_gins/source_aware/source_aware_n6b_visual_sanity.py",
    "src/legsa_gins/source_aware/source_aware_n6b_plot_coverage.py",
    "src/legsa_gins/source_aware/source_aware_n6b_visual_decision.py",
    "scripts/experiments/run_n6b1_source_aware_visual_validation.py",
    "scripts/audit_n6b1_required_figures_nonempty.py",
    "docs/experiments/n6b1_source_aware_visual_validation.md",
    "docs/experiments/n6b1_plot_catalog.md",
    "docs/experiments/n6b1_plot_data_coverage.md",
    "docs/experiments/n6b1_decision.md",
    "docs/codex_prompts/N6B1_source_aware_visual_validation.md",
]

ARTIFACT_RE = re.compile(
    r"(SOURCE_AWARE_WEIGHT_TRACE\.csv|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n6b1_source_aware_visual_validation failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for token in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")


def _check_no_forbidden_tracked_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden runtime/figure artifact tracked: " + ", ".join(hits[:8]))


def _write_reference(path: Path, count: int = 1300) -> None:
    lines = []
    for index in range(count):
        time = index * 0.25
        lat = 39.0 + index * 1.0e-9
        lon = 116.0 + index * 1.0e-9
        height = 40.0 + 0.002 * math.sin(index / 50.0)
        roll = 0.03 * math.sin(index / 60.0)
        pitch = 0.02 * math.cos(index / 70.0)
        yaw = 1.0 + 0.04 * math.sin(index / 80.0)
        lines.append(f"0 {time:.6f} {lat:.12f} {lon:.12f} {height:.6f} 1.0 0.2 -0.1 {roll:.6f} {pitch:.6f} {yaw:.6f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_eval_nav(path: Path, *, offset: float, count: int = 1300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"])
        writer.writeheader()
        for index in range(count):
            time = index * 0.25
            writer.writerow(
                {
                    "time": f"{time:.6f}",
                    "lat_deg": f"{39.0 + index * 1.0e-9 + offset:.12f}",
                    "lon_deg": f"{116.0 + index * 1.0e-9 + offset:.12f}",
                    "height_m": f"{40.0 + offset * 1.0e5 + 0.002 * math.sin(index / 50.0):.6f}",
                    "vn": "1.0",
                    "ve": "0.2",
                    "vd": "-0.1",
                    "roll_deg": f"{0.03 * math.sin(index / 60.0) + offset * 1.0e4:.6f}",
                    "pitch_deg": f"{0.02 * math.cos(index / 70.0) + offset * 8.0e3:.6f}",
                    "yaw_deg": f"{1.0 + 0.04 * math.sin(index / 80.0) + offset * 2.0e4:.6f}",
                }
            )


def _summary(h: float, up: float, yaw: float, roll: float, pitch: float) -> dict[str, float | bool | int | str]:
    return {
        "count": 1300,
        "aligned_count": 1300,
        "evidence_status": "diagnostic_aligned",
        "horizontal_rmse_m": h,
        "up_rmse_m": up,
        "yaw_rmse_deg": yaw,
        "roll_rmse_deg": roll,
        "pitch_rmse_deg": pitch,
        "paper_performance_claim": False,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def _write_trace(path: Path, *, policy: str, scale_boost: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sources = ["receiver_position", "receiver_velocity", "dual_antenna_yaw", "raw_doppler_velocity"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "time",
            "update_index",
            "source_id",
            "policy_version",
            "mode",
            "lsim_score",
            "oim_score",
            "lsim_R_scale",
            "oim_R_scale",
            "combined_R_scale",
            "residual_norm",
            "normalized_innovation",
            "nis",
            "dof",
            "innovation_cov_trace",
            "used_innovation_covariance",
            "source_cap",
            "accepted",
            "rejected",
            "reason_codes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(1300):
            for source in sources:
                time = index * 0.25
                normalized = 1.0 + 0.2 * math.sin(index / 30.0)
                scale = 1.0 + scale_boost * abs(math.sin(index / 22.0))
                if source == "raw_doppler_velocity" and abs(time - 96.25) < 0.13:
                    normalized = 2.6
                    scale = 1.55
                writer.writerow(
                    {
                        "time": f"{time:.6f}",
                        "update_index": index + 1,
                        "source_id": source,
                        "policy_version": policy,
                        "mode": "lsim_oim",
                        "lsim_score": "1.0",
                        "oim_score": f"{1.0 / scale:.6f}",
                        "lsim_R_scale": "1.0",
                        "oim_R_scale": f"{scale:.6f}",
                        "combined_R_scale": f"{scale:.6f}",
                        "residual_norm": f"{0.4 + normalized * 0.1:.6f}",
                        "normalized_innovation": f"{normalized:.6f}",
                        "nis": f"{normalized * normalized:.6f}",
                        "dof": "3",
                        "innovation_cov_trace": "1.0",
                        "used_innovation_covariance": "1",
                        "source_cap": "15" if source == "raw_doppler_velocity" else "5",
                        "accepted": "1",
                        "rejected": "0",
                        "reason_codes": "nominal",
                    }
                )


def _write_reports(n6b: Path) -> None:
    variants = [
        ("baseline_plus_raw_no_sourceaware", _summary(0.057, 0.050, 0.376, 0.039, 0.041)),
        ("n6a_lsim_oim_original_policy", _summary(0.070, 0.080, 0.700, 0.050, 0.060)),
        ("n6b_lsim_only", _summary(0.058, 0.055, 0.430, 0.041, 0.038)),
        ("n6b_oim_only", _summary(0.058, 0.058, 0.450, 0.042, 0.036)),
        ("n6b_lsim_oim", _summary(0.058, 0.062, 0.504, 0.043, 0.031)),
    ]
    for variant, _ in variants:
        _write_eval_nav(n6b / "variants" / variant / "EVAL_NAV.csv", offset=1.0e-8 if "no_sourceaware" in variant else 1.1e-8)
        (n6b / "variants" / variant / "RUN_MANIFEST.json").write_text(json.dumps({"paper_performance_claim": False}), encoding="utf-8")
    for variant in [
        "receiver_velocity_disabled_plus_raw_no_sourceaware",
        "receiver_velocity_std_scale_5_plus_raw_no_sourceaware",
        "receiver_velocity_outage_30s_plus_raw_no_sourceaware",
        "receiver_velocity_noise_0p5_plus_raw_no_sourceaware",
    ]:
        _write_eval_nav(n6b / "variants" / variant / "EVAL_NAV.csv", offset=1.4e-8)
    for variant in [
        "receiver_velocity_disabled_plus_raw_n6b_lsim_oim",
        "receiver_velocity_std_scale_5_plus_raw_n6b_lsim_oim",
        "receiver_velocity_outage_30s_plus_raw_n6b_lsim_oim",
        "receiver_velocity_noise_0p5_plus_raw_n6b_lsim_oim",
    ]:
        _write_eval_nav(n6b / "variants" / variant / "EVAL_NAV.csv", offset=1.35e-8)
    _write_trace(n6b / "variants" / "n6a_lsim_oim_original_policy" / "SOURCE_AWARE_WEIGHT_TRACE.csv", policy="n6a_original_policy", scale_boost=1.5)
    _write_trace(n6b / "variants" / "n6b_lsim_oim" / "SOURCE_AWARE_WEIGHT_TRACE.csv", policy="n6b_conservative_innovation_covariance", scale_boost=0.6)
    (n6b / "N6B_SOURCE_AWARE_VARIANT_SUMMARIES.json").write_text(json.dumps({"variants": [{"variant_id": v, "summary": s} for v, s in variants], "paper_performance_claim": False}, indent=2), encoding="utf-8")
    stats = {
        "trace_row_count": 5200,
        "sources_covered": ["dual_antenna_yaw", "raw_doppler_velocity", "receiver_position", "receiver_velocity"],
        "stats_by_source": {
            "receiver_position": {"R_scale_p50": 1.02, "R_scale_p95": 1.16, "R_scale_max": 1.38, "reject_count": 0, "update_count": 1300},
            "receiver_velocity": {"R_scale_p50": 1.08, "R_scale_p95": 2.03, "R_scale_max": 4.9, "reject_count": 0, "update_count": 1300},
            "dual_antenna_yaw": {"R_scale_p50": 1.01, "R_scale_p95": 1.20, "R_scale_max": 1.9, "reject_count": 0, "update_count": 1300},
            "raw_doppler_velocity": {"R_scale_p50": 1.08, "R_scale_p95": 5.1, "R_scale_max": 15.0, "reject_count": 0, "update_count": 1300},
        },
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    (n6b / "N6B_SOURCE_AWARE_WEIGHT_STATS.json").write_text(json.dumps({"main_variant_stats": stats, "paper_performance_claim": False, "trace_solver_input": False, "final_v23_output_solver_input": False}, indent=2), encoding="utf-8")
    comparison = {
        "baseline_plus_raw_no_sourceaware": variants[0][1],
        "n6b_lsim_oim": variants[4][1],
        "comparisons": {
            "n6b_lsim_oim_minus_no_sourceaware": {"delta": {"horizontal_rmse_m": 0.001, "up_rmse_m": 0.012, "yaw_rmse_deg": 0.128, "roll_rmse_deg": 0.004, "pitch_rmse_deg": -0.010}},
            "n6b_lsim_oim_minus_n6a_original_policy": {"delta": {"horizontal_rmse_m": -0.012, "up_rmse_m": -0.018, "yaw_rmse_deg": -0.196, "roll_rmse_deg": -0.007, "pitch_rmse_deg": -0.029}},
        },
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }
    for key in ["receiver_velocity_disabled", "receiver_velocity_std_scale_5", "receiver_velocity_outage_30s", "receiver_velocity_noise_0p5"]:
        comparison["comparisons"][f"{key}_n6b_lsim_oim_minus_no_sourceaware"] = {"delta": {"horizontal_rmse_m": -0.002, "up_rmse_m": 0.0, "yaw_rmse_deg": -0.01, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}}
    (n6b / "N6B_SOURCE_AWARE_COMPARISON_REPORT.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    diagnostics = {
        "clean_neutrality_gate": {"pass": True},
        "R_scale_gate": {"pass": True},
        "spike_response_status": "increased_mildly",
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_prior": False,
        "fgo": False,
    }
    (n6b / "N6B_SOURCE_AWARE_POLICY_DIAGNOSTICS.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    spike = {
        "spike_report_found": True,
        "response_status": "increased_mildly",
        "responses": [
            {"spike_time": 96.4067945, "nearest_time": 96.25, "raw_doppler_combined_R_scale": 1.55, "raw_doppler_normal_median_scale": 1.08, "oim_normalized_at_spike": 2.6},
            {"spike_time": 97.0067945, "nearest_time": 97.00, "raw_doppler_combined_R_scale": 1.0, "raw_doppler_normal_median_scale": 1.08, "oim_normalized_at_spike": 1.1},
        ],
        "paper_performance_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    (n6b / "N6B_SPIKE_RESPONSE_REPORT.json").write_text(json.dumps(spike, indent=2), encoding="utf-8")


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n6b1_toy_") as tmp_value:
        tmp = Path(tmp_value)
        n6b = tmp / "n6b"
        n5d1 = tmp / "n5d1"
        dual = tmp / "dual"
        out = tmp / "out"
        figs = tmp / "figs"
        n6b.mkdir(parents=True)
        n5d1.mkdir(parents=True)
        _write_reference(dual / "KF_GINS_Navresult.nav")
        _write_reports(n6b)
        (n5d1 / "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
        (n5d1 / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json").write_text(json.dumps({"spike_count": 2}), encoding="utf-8")
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n6b1_source_aware_visual_validation.py"),
            "--n6b-root",
            str(n6b),
            "--n5d1-root",
            str(n5d1),
            "--dual-root",
            str(dual),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--build-dir",
            str(tmp / "build"),
            "--exe",
            str(tmp / "demo"),
            "--allow-run",
            "--rerun-missing-timeseries",
            "true",
        ]
        proc = _run(cmd, timeout=180)
        if proc.returncode != 0:
            _fail("toy N6B1 runner failed:\n" + proc.stdout + proc.stderr)
        for name in [
            "N6B1_VISUAL_INPUT_MANIFEST.json",
            "N6B1_PLOT_DATA_COVERAGE_REPORT.json",
            "N6B1_VISUAL_SANITY_REPORT.json",
            "N6B1_VISUAL_VALIDATION_DECISION_REPORT.json",
            "N6B1_VISUAL_VALIDATION_REPORT.json",
            "N6B1_FIGURE_MANIFEST.json",
        ]:
            if not (out / name).exists():
                _fail(f"toy missing report {name}")
        if not (figs / "07_case_review" / "n6b1_visual_case_review.md").exists():
            _fail("toy case review missing")
        coverage = json.loads((out / "N6B1_PLOT_DATA_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
        if not coverage.get("visual_validation_passed"):
            _fail("toy coverage did not pass")
        if coverage.get("figure_count") != 23 or not coverage.get("required_figures_nonempty"):
            _fail("toy required figure coverage invalid")
        sanity = json.loads((out / "N6B1_VISUAL_SANITY_REPORT.json").read_text(encoding="utf-8"))
        for key in [
            "clean_no_gross_degradation_visual",
            "receiver_position_not_slammed_to_cap",
            "receiver_velocity_not_slammed_to_cap",
            "raw_doppler_spike_response_visible",
            "stress_variants_visualized",
        ]:
            if not sanity.get(key):
                _fail(f"toy sanity flag failed: {key}")
        decision = json.loads((out / "N6B1_VISUAL_VALIDATION_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") != "visual_validation_passed":
            _fail("toy decision did not pass")
        for report in [coverage, sanity, decision]:
            if report.get("paper_performance_claim") is not False:
                _fail("paper claim flag invalid")
            if report.get("final_v23_output_solver_input") is not False or report.get("trace_solver_input") is not False:
                _fail("solver-input boundary flag invalid")
            if report.get("output_only_correction") is not False or report.get("bad_epoch_deletion_for_metric") is not False:
                _fail("output correction or epoch deletion boundary invalid")


def main() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))
    _toy_run()
    _check_no_forbidden_tracked_artifacts()
    _check_no_local_path_leak()
    print("audit_n6b1_source_aware_visual_validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
