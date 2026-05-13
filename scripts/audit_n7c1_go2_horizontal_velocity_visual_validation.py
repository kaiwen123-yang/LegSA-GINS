#!/usr/bin/env python3
"""Audit N7C1 Go2 horizontal velocity visual validation.

中文说明：使用 synthetic runtime 数据验证 N7C1 loader、plot coverage、sanity、
decision 和 runner 链路；不读取真实 runtime 路径，不修改 solver。
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
    "src/legsa_gins/go2_prior/go2_n7c_visual_loader.py",
    "src/legsa_gins/go2_prior/go2_n7c_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c_plot_coverage.py",
    "src/legsa_gins/go2_prior/go2_n7c_visual_sanity.py",
    "src/legsa_gins/go2_prior/go2_n7c_visual_decision.py",
    "scripts/experiments/run_n7c1_go2_horizontal_velocity_visual_validation.py",
    "scripts/audit_n7c_required_figures_nonempty.py",
    "scripts/audit_n7c_vertical_disabled_visual_boundary.py",
    "docs/experiments/n7c1_go2_horizontal_velocity_visual_validation.md",
    "docs/experiments/n7c1_plot_catalog.md",
    "docs/experiments/n7c1_plot_data_coverage.md",
    "docs/experiments/n7c1_decision.md",
    "docs/codex_prompts/N7C1_go2_horizontal_velocity_visual_validation.md",
]

REQUIRED_OUTPUTS = [
    "N7C1_VISUAL_INPUT_MANIFEST.json",
    "N7C1_PLOT_DATA_COVERAGE_REPORT.json",
    "N7C1_VISUAL_SANITY_REPORT.json",
    "N7C1_GO2_HORIZONTAL_VELOCITY_VISUAL_DECISION_REPORT.json",
    "N7C1_VISUAL_VALIDATION_REPORT.json",
    "N7C1_FIGURE_MANIFEST.json",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_HORIZONTAL_VELOCITY_PRIORS|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c1_go2_horizontal_velocity_visual_validation failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


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
                    "vn": f"{1.0 + 0.01 * math.sin(index / 30.0):.6f}",
                    "ve": f"{0.2 + 0.01 * math.cos(index / 35.0):.6f}",
                    "vd": "-0.1",
                    "roll_deg": f"{0.03 * math.sin(index / 60.0) + offset * 1.0e4:.6f}",
                    "pitch_deg": f"{0.02 * math.cos(index / 70.0) + offset * 8.0e3:.6f}",
                    "yaw_deg": f"{1.0 + 0.04 * math.sin(index / 80.0) + offset * 2.0e4:.6f}",
                }
            )


def _write_prior_csv(path: Path, count: int = 1300) -> None:
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "source_status", "quality_flag", "contact_model", "contact_label", "frame_candidate", "prior_policy", "diagnostic_only", "go2_velocity_truth_claim"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            bucket = "high" if index % 30 == 0 else ("medium" if index % 2 == 0 else "low")
            writer.writerow(
                {
                    "time": f"{index * 0.25:.6f}",
                    "vn": f"{1.0 + 0.02 * math.sin(index / 40.0):.6f}",
                    "ve": f"{0.2 + 0.02 * math.cos(index / 45.0):.6f}",
                    "vd": "0.0",
                    "std_vn": "2.0",
                    "std_ve": "2.0",
                    "std_vd": "999.0",
                    "source_status": "active",
                    "quality_flag": f"n7c_horizontal_{bucket}_confidence",
                    "contact_model": "toy",
                    "contact_label": bucket,
                    "frame_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                    "prior_policy": "n7c_go2_horizontal_velocity_weak_prior",
                    "diagnostic_only": "False",
                    "go2_velocity_truth_claim": "False",
                }
            )


def _write_trace(path: Path, update_count: int = 30) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "update_index", "source_id", "policy_version", "mode", "lsim_score", "oim_score", "combined_R_scale", "residual_norm", "normalized_innovation", "used_innovation_covariance", "accepted", "rejected", "reason_codes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(update_count):
            writer.writerow(
                {
                    "time": f"{index * 8.0:.6f}",
                    "update_index": index + 1,
                    "source_id": "go2_horizontal_velocity",
                    "policy_version": "n6b_conservative_innovation_covariance",
                    "mode": "lsim_oim",
                    "lsim_score": "1.0",
                    "oim_score": "1.0",
                    "combined_R_scale": "2.0",
                    "residual_norm": f"{0.2 + 0.01 * math.sin(index):.6f}",
                    "normalized_innovation": "0.5",
                    "used_innovation_covariance": "1",
                    "accepted": "1",
                    "rejected": "0",
                    "reason_codes": "nominal",
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


def _variant_summary(variant_id: str, update_count: int, summary: dict) -> dict:
    return {
        "variant_id": variant_id,
        "summary": summary,
        "manifest": {
            "ablation_variant": variant_id,
            "go2_horizontal_velocity_prior_update_count": update_count,
            "go2_horizontal_velocity_prior_vertical_disabled": bool(update_count),
            "go2_position_prior_enabled": False,
            "go2_yaw_prior_enabled": False,
            "fgo": False,
            "paper_performance_claim": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        },
        "go2_horizontal_velocity_prior_update_count": update_count,
        "go2_horizontal_velocity_prior_reject_count": 0,
        "go2_horizontal_velocity_prior_vertical_disabled": bool(update_count),
        "go2_velocity_truth_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def _prepare_n7c_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    n7c = root / "n7c"
    n5b = root / "n5b"
    dual = root / "dual"
    _write_reference(dual / "KF_GINS_Navresult.nav")
    _write_prior_csv(n7c / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv")
    _write_prior_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    variants = [
        ("baseline_no_go2_horizontal_velocity", 0, 1.00e-8),
        ("go2_horizontal_velocity_weak_prior_main", 30, 1.01e-8),
        ("go2_horizontal_velocity_probability_weighted", 30, 1.01e-8),
        ("go2_horizontal_velocity_contact_weighted", 28, 1.01e-8),
        ("go2_horizontal_velocity_high_confidence_only", 5, 1.02e-8),
        ("receiver_velocity_stress_no_go2", 0, 1.30e-8),
        ("receiver_velocity_stress_plus_go2_horizontal", 30, 1.25e-8),
        ("raw_doppler_stress_no_go2", 0, 1.25e-8),
        ("raw_doppler_stress_plus_go2_horizontal", 30, 1.24e-8),
    ]
    summaries = []
    for variant_id, updates, offset in variants:
        _write_eval_nav(n7c / "variants" / variant_id / "EVAL_NAV.csv", offset=offset)
        if updates:
            _write_trace(n7c / "variants" / variant_id / "SOURCE_AWARE_WEIGHT_TRACE.csv", update_count=updates)
        else:
            _write_trace(n7c / "variants" / variant_id / "SOURCE_AWARE_WEIGHT_TRACE.csv", update_count=0)
        summaries.append(_variant_summary(variant_id, updates, _summary(0.06 + offset, 0.05, 0.4, 0.03, 0.03)))
    _write_json(
        n7c / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json",
        {
            "csv_generated": True,
            "epoch_count": 1300,
            "high_confidence_count": 44,
            "medium_confidence_count": 628,
            "low_confidence_count": 628,
            "vertical_velocity_disabled": True,
            "std_vd_disabled_threshold": 999.0,
            "go2_position_prior_enabled": False,
            "go2_yaw_prior_enabled": False,
            "paper_performance_claim": False,
            "go2_velocity_truth_claim": False,
            "no_outperform_final_v23_claim": True,
        },
    )
    _write_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json", {"required_variants_present": True, "paper_performance_claim": False})
    _write_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json", {"variants": summaries, "paper_performance_claim": False})
    comparisons = {
        "go2_horizontal_velocity_main_minus_baseline": {"delta": {"horizontal_rmse_m": 0.00001, "up_rmse_m": 0.0, "yaw_rmse_deg": 0.0001, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}, "paper_performance_claim": False},
        "receiver_velocity_stress_plus_go2_minus_no_go2": {"delta": {"horizontal_rmse_m": -0.00002, "yaw_rmse_deg": -0.0001}, "paper_performance_claim": False},
        "raw_doppler_stress_plus_go2_minus_no_go2": {"delta": {"horizontal_rmse_m": -0.00003, "yaw_rmse_deg": -0.0002}, "paper_performance_claim": False},
    }
    _write_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json", {"comparisons": comparisons, "paper_performance_claim": False})
    _write_json(
        n7c / "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json",
        {
            "status": "ready_with_weak_stress_evidence",
            "recommended_next_stage": "N8A_no_feedback_FGO_foundation",
            "update_count": 30,
            "reject_count": 0,
            "go2_vertical_velocity_prior_enabled": False,
            "go2_position_prior_enabled": False,
            "go2_yaw_prior_enabled": False,
            "paper_performance_claim": False,
            "go2_velocity_truth_claim": False,
            "no_outperform_final_v23_claim": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "fgo": False,
        },
    )
    _write_json(n7c / "N7C_FIGURE_MANIFEST.json", {"figure_count_total": 10, "required_figures_nonempty": True})
    return n7c, root / "n7b5", n5b, root / "n6b", dual


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c1_visual_") as tmp_value:
        tmp = Path(tmp_value)
        n7c, n7b5, n5b, n6b, dual = _prepare_n7c_runtime(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c1_go2_horizontal_velocity_visual_validation.py"),
            "--n7c-root",
            str(n7c),
            "--n7b5-root",
            str(n7b5),
            "--n5b-root",
            str(n5b),
            "--n6b-root",
            str(n6b),
            "--dual-root",
            str(dual),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--build-dir",
            str(tmp / "build"),
            "--exe",
            str(tmp / "not_used_demo"),
            "--allow-run",
            "--rerun-missing-timeseries",
            "true",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            _fail(proc.stderr[-3000:] or proc.stdout[-3000:])
        for item in REQUIRED_OUTPUTS:
            if not (out / item).exists():
                _fail(f"missing output {item}")
        if not (figs / "07_case_review" / "n7c1_visual_case_review.md").exists():
            _fail("missing case review markdown")
        coverage = json.loads((out / "N7C1_PLOT_DATA_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
        sanity = json.loads((out / "N7C1_VISUAL_SANITY_REPORT.json").read_text(encoding="utf-8"))
        decision = json.loads((out / "N7C1_GO2_HORIZONTAL_VELOCITY_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
        figure_manifest = json.loads((out / "N7C1_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if figure_manifest.get("figure_count_total") != 21:
            _fail("toy did not generate 21 figures")
        if not coverage.get("visual_validation_passed"):
            _fail("toy coverage did not pass")
        if not sanity.get("visual_sanity_passed"):
            _fail("toy sanity did not pass")
        if decision.get("status") != "visual_validation_passed_with_weak_stress_evidence":
            _fail(f"unexpected toy decision {decision.get('status')}")
        if decision.get("paper_performance_claim") or decision.get("go2_velocity_truth_claim"):
            _fail("forbidden claim flag true")


def main() -> int:
    for item in REQUIRED_FILES:
        if not (ROOT / item).exists():
            _fail(f"missing file {item}")
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c1_go2_horizontal_velocity_visual_validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
