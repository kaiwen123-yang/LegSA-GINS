#!/usr/bin/env python3
"""Audit N5D1 visual data coverage and spike-audit protocol.

中文说明：该审计使用 synthetic toy 数据，验证 clean ablation 修复、coverage gate、
spike audit、plot semantics 和边界旗标；不读取真实数据、不提交生成图像。
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
sys.path.insert(0, str(ROOT / "src"))


ARTIFACT_RE = re.compile(
    r"(gnss1-raw\.csv|gnss2-raw\.csv|corr-raw\.csv|\.ubx$|\.obs$|\.nav$|\.sp3$|\.clk$|"
    r"input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|RAW_DOPPLER_VELOCITY_FACTORS\.csv|"
    r"summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"FAILED: {message}")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for pattern in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", pattern, "--", "."]):
            _fail(f"local path leak: {pattern}")


def _check_no_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("generated/raw artifact tracked: " + ", ".join(hits[:8]))


def _must_exist(paths: list[str]) -> None:
    missing = [path for path in paths if not (ROOT / path).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))


def _write_factor(path: Path, count: int = 1200) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"])
        writer.writeheader()
        for index in range(count):
            time = index * 0.25
            vn = 1.0 + 0.02 * math.sin(index / 30.0)
            if index == 400:
                vn = 8.0
            if index == 401:
                vn = 1.0
            writer.writerow(
                {
                    "time": time,
                    "vn": vn,
                    "ve": 0.2,
                    "vd": -0.1,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 28 + index % 4,
                    "provider_status": "available",
                    "quality_flag": "ok",
                }
            )


def _write_clean_gnss(path: Path, count: int = 1200) -> None:
    lines = []
    for index in range(count):
        time = index * 0.25
        lines.append(f"{time:.6f} 0 0 0 0 0 0 1.0 0.2 -0.1 0 0 0 0 0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_navs(root: Path, dual_root: Path, count: int = 1200) -> None:
    dual_lines = []
    for index in range(count):
        time = index * 0.25
        lat = 39.0 + index * 1e-9
        lon = 116.0 + index * 1e-9
        height = 40.0 + 0.001 * math.sin(index / 50.0)
        roll = 0.01 * math.sin(index / 40.0)
        pitch = 0.02 * math.cos(index / 45.0)
        yaw = 1.0 + 0.03 * math.sin(index / 60.0)
        dual_lines.append(f"0 {time:.6f} {lat:.12f} {lon:.12f} {height:.6f} 1.0 0.2 -0.1 {roll:.6f} {pitch:.6f} {yaw:.6f}")
    dual_root.mkdir(parents=True, exist_ok=True)
    (dual_root / "KF_GINS_Navresult.nav").write_text("\n".join(dual_lines) + "\n", encoding="utf-8")
    for variant_id, offset in [("baseline_full", 1.0e-8), ("baseline_plus_raw_doppler_r1", 0.8e-8)]:
        variant_dir = root / "variants" / variant_id
        variant_dir.mkdir(parents=True, exist_ok=True)
        with (variant_dir / "EVAL_NAV.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"])
            writer.writeheader()
            for index in range(count):
                time = index * 0.25
                writer.writerow(
                    {
                        "time": f"{time:.6f}",
                        "lat_deg": f"{39.0 + index * 1e-9 + offset:.12f}",
                        "lon_deg": f"{116.0 + index * 1e-9 + offset:.12f}",
                        "height_m": f"{40.0 + offset * 1e6:.6f}",
                        "vn": "1.0",
                        "ve": "0.2",
                        "vd": "-0.1",
                        "roll_deg": "0.01",
                        "pitch_deg": "0.02",
                        "yaw_deg": f"{1.0 + (0.02 if 'plus' in variant_id else 0.03):.6f}",
                    }
                )
        (variant_dir / "RUN_MANIFEST.json").write_text(
            json.dumps({"raw_doppler_update_count": 274 if "plus" in variant_id else 0, "raw_doppler_reject_count": 0}, indent=2) + "\n",
            encoding="utf-8",
        )


def _summary(h: float, up: float, yaw: float) -> dict[str, float]:
    return {"horizontal_rmse_m": h, "up_rmse_m": up, "yaw_rmse_deg": yaw, "roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1}


def _write_stress_summary(path: Path) -> None:
    variants = [
        ("baseline_full", _summary(1.0, 1.0, 1.0), False),
        ("baseline_plus_raw_doppler_r1", _summary(0.98, 0.99, 0.9), True),
        ("position_yaw_only", _summary(2.0, 1.3, 1.6), False),
        ("position_yaw_plus_raw_doppler_r1", _summary(1.7, 1.1, 1.1), True),
        ("receiver_velocity_disabled_no_raw", _summary(2.0, 1.3, 1.6), False),
        ("receiver_velocity_disabled_plus_raw", _summary(1.7, 1.1, 1.1), True),
        ("receiver_velocity_std_scale_5_no_raw", _summary(1.6, 1.2, 1.4), False),
        ("receiver_velocity_std_scale_5_plus_raw", _summary(1.3, 1.0, 1.1), True),
        ("receiver_velocity_outage_30s_no_raw", _summary(2.1, 1.4, 1.5), False),
        ("receiver_velocity_outage_30s_plus_raw", _summary(1.8, 1.2, 1.2), True),
        ("receiver_velocity_noise_0p5_no_raw", _summary(1.8, 1.2, 1.5), False),
        ("receiver_velocity_noise_0p5_plus_raw", _summary(1.5, 1.1, 1.2), True),
    ]
    rows = []
    for variant_id, summary, raw_enabled in variants:
        rows.append(
            {
                "variant_id": variant_id,
                "summary": summary,
                "parity_metrics": summary,
                "enable_raw_doppler": raw_enabled,
                "raw_doppler_solver_enabled": raw_enabled,
                "raw_doppler_update_count": 274 if raw_enabled else 0,
                "raw_doppler_reject_count": 0,
                "diagnostic_only": variant_id not in {"baseline_full", "baseline_plus_raw_doppler_r1"},
                "paper_performance_claim": False,
                "proposed_factor_claim": False,
                "no_outperform_final_v23_claim": True,
            }
        )
    path.write_text(json.dumps({"variants": rows, "paper_performance_claim": False}, indent=2) + "\n", encoding="utf-8")


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n5d1_toy_") as tmp_value:
        tmp = Path(tmp_value)
        n5b = tmp / "n5b"
        n5c = tmp / "n5c"
        n5d = tmp / "n5d"
        clean = tmp / "clean"
        dual = tmp / "dual"
        out = tmp / "out"
        figs = tmp / "figs"
        for path in [n5b, n5c, n5d, clean]:
            path.mkdir(parents=True)
        _write_factor(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
        _write_clean_gnss(clean / "clean.gnss")
        _write_navs(n5c, dual)
        _write_stress_summary(n5d / "N5D_STRESS_VARIANT_SUMMARIES.json")
        (n5d / "N5D_FIGURE_MANIFEST.json").write_text(json.dumps({"figure_paths": ["01_clean_ablation/clean_horizontal_error_baseline_vs_raw.png"]}), encoding="utf-8")
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n5d1_visual_data_coverage_spike_audit.py"),
            "--n5b-root",
            str(n5b),
            "--n5c-root",
            str(n5c),
            "--n5d-root",
            str(n5d),
            "--clean-root",
            str(clean),
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
            "--rerun-clean-variants-if-needed",
            "true",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
        if proc.returncode != 0:
            _fail("toy N5D1 runner failed:\n" + proc.stdout + proc.stderr)
        for name in [
            "N5D_PLOT_DATA_COVERAGE_REPORT.json",
            "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json",
            "N5D_PLOT_SEMANTICS_FIX_REPORT.json",
            "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json",
            "N5D1_FIGURE_MANIFEST.json",
        ]:
            if not (out / name).exists():
                _fail(f"toy missing report {name}")
        coverage = json.loads((out / "N5D_PLOT_DATA_COVERAGE_REPORT.json").read_text(encoding="utf-8"))
        if not coverage.get("mandatory_coverage_passed"):
            _fail("toy mandatory coverage did not pass")
        if coverage.get("empty_plot_suspect_count") != 0:
            _fail("toy repaired figures still empty")
        spike = json.loads((out / "RAW_DOPPLER_SPIKE_AUDIT_REPORT.json").read_text(encoding="utf-8"))
        if spike.get("spike_count") != 2 or spike.get("spike_epochs_removed"):
            _fail("toy spike audit did not detect two non-deleted spikes")
        semantics = json.loads((out / "N5D_PLOT_SEMANTICS_FIX_REPORT.json").read_text(encoding="utf-8"))
        if not semantics.get("velocity_3sigma_semantics_fixed") or not semantics.get("long_labels_fixed"):
            _fail("toy plot semantics fix missing")
        decision = json.loads((out / "N5D1_VISUAL_DATA_COVERAGE_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("paper_performance_claim") is not False or decision.get("proposed_factor_claim") is not False:
            _fail("decision boundary flags invalid")
        if not (figs / "05_case_review" / "n5d1_visual_case_review.md").exists():
            _fail("toy case review missing")


def main() -> int:
    _must_exist(
        [
            "src/legsa_gins/raw_gnss/raw_doppler_plot_data_coverage.py",
            "src/legsa_gins/raw_gnss/raw_doppler_clean_ablation_plot_fix.py",
            "src/legsa_gins/raw_gnss/raw_doppler_spike_audit.py",
            "src/legsa_gins/raw_gnss/raw_doppler_plot_semantics_audit.py",
            "src/legsa_gins/raw_gnss/raw_doppler_n5d1_decision.py",
            "scripts/experiments/run_n5d1_visual_data_coverage_spike_audit.py",
            "scripts/audit_n5d_required_figures_nonempty.py",
            "docs/experiments/n5d1_visual_data_coverage_spike_audit.md",
            "docs/experiments/n5d1_clean_ablation_plot_fix.md",
            "docs/experiments/n5d1_raw_doppler_spike_audit.md",
            "docs/experiments/n5d1_plot_semantics_fix.md",
            "docs/experiments/n5d1_decision.md",
            "docs/codex_prompts/N5D1_visual_data_coverage_spike_audit.md",
        ]
    )
    _toy_run()
    _check_no_artifacts()
    _check_no_local_path_leak()
    print("audit_n5d1_visual_data_coverage_spike_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
