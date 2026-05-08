#!/usr/bin/env python3
"""Audit N4H2E dual replay visual validation contract.

中文说明：audit 使用 toy 数据检查绘图合同，不提交生成图，不修改 solver。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legsa_gins.visualization.visual_sanity_checks import strict_yaw_gate_status  # noqa: E402


MODULES = [
    "src/legsa_gins/visualization/__init__.py",
    "src/legsa_gins/visualization/dual_replay_plot_loader.py",
    "src/legsa_gins/visualization/dual_replay_plots.py",
    "src/legsa_gins/visualization/visual_sanity_checks.py",
    "src/legsa_gins/visualization/plot_bundle_manifest.py",
    "scripts/experiments/run_dual_replay_visual_validation.py",
    "docs/experiments/dual_replay_visual_validation.md",
    "docs/experiments/dual_replay_visual_checklist.md",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _nav_line(time: float, lat: float, lon: float, height: float, yaw: float = 10.0) -> str:
    return f"2234 {time:.1f} {lat:.10f} {lon:.10f} {height:.4f} 0.1 0.0 0.0 0.5 -0.2 {yaw:.6f}\n"


def _std_line(time: float) -> str:
    values = [
        time,
        0.4,
        0.4,
        0.5,
        0.02,
        0.02,
        0.03,
        0.5,
        0.5,
        0.8,
        0.01,
        0.01,
        0.01,
        1.0,
        1.0,
        1.0,
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
    ]
    return " ".join(str(value) for value in values) + "\n"


def _gnss_line(time: float, lat: float, lon: float, height: float, yaw: float = 10.0) -> str:
    values = [
        time,
        lat,
        lon,
        height,
        0.4,
        0.4,
        0.5,
        0.1,
        0.0,
        0.0,
        0.02,
        0.02,
        0.03,
        yaw,
        1.0,
    ]
    return " ".join(str(value) for value in values) + "\n"


def _write_toy_artifacts(base: Path) -> tuple[Path, Path, Path]:
    dual = base / "dual"
    n4h2 = base / "n4h2"
    out = base / "out"
    lat0 = 30.0
    lon0 = 120.0
    nav_lines: list[str] = []
    replay_lines: list[str] = []
    gnss_lines: list[str] = []
    error_lines = ["timestamp,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"]
    for index in range(40):
        time = 100.0 + index
        lat = lat0 + index * 1.0e-6
        lon = lon0 + index * 1.0e-6
        height = 50.0 + 0.01 * index
        nav_lines.append(_nav_line(time, lat, lon, height, yaw=10.0))
        replay_lines.append(_nav_line(time, lat, lon, height, yaw=11.0))
        gnss_lines.append(_gnss_line(time, lat, lon, height, yaw=10.5))
        error_lines.append(f"{time:.1f},0.0,0.0,0.0,0.0,0.0,0.0,0.0\n")
    _write(dual / "KF_GINS_Navresult.nav", "".join(nav_lines))
    _write(dual / "KF_GINS_STD.txt", "".join(_std_line(100.0 + index) for index in range(40)))
    _write(dual / "input.gnss", "".join(gnss_lines))
    _write(dual / "error_series.csv", "".join(error_lines))
    _write(
        dual / "summary.json",
        json.dumps(
            {
                "count": 40,
                "horizontal_rmse_m": 0.0,
                "up_rmse_m": 0.0,
                "yaw_rmse_deg": 0.0,
                "roll_rmse_deg": 0.0,
                "pitch_rmse_deg": 0.0,
            }
        ),
    )
    _write(n4h2 / "replay" / "kfgins_output" / "KF_GINS_Navresult.nav", "".join(replay_lines))
    _write(n4h2 / "replay" / "kfgins_output" / "KF_GINS_STD.txt", "".join(_std_line(100.0 + index) for index in range(40)))
    _write(n4h2 / "inputs" / "BY2_PROCESS_DATA_COMPAT.gnss", "".join(gnss_lines))
    _write(n4h2 / "replay" / "evaluation" / "FINAL_V23_TRACE_EVAL_SUMMARY.json", json.dumps({"yaw_rmse_deg": 93.0}))
    return dual, n4h2, out


def _assert_no_generated_figures_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
    )
    forbidden = [line for line in result.stdout.splitlines() if line.endswith((".png", ".pdf", ".svg"))]
    if forbidden:
        raise AssertionError(f"generated figure files are tracked: {forbidden[:5]}")


def _assert_docs_no_local_paths() -> None:
    for path in [
        ROOT / "docs/experiments/dual_replay_visual_validation.md",
        ROOT / "docs/experiments/dual_replay_visual_checklist.md",
    ]:
        text = path.read_text(encoding="utf-8")
        needles = [
            "/mnt/c/Users" + "/ykw/Desktop",
            "/home/kaiwen/" + "legsa_n4h2_artifacts",
            "/home/kaiwen/" + "legsa_external_artifacts",
        ]
        for needle in needles:
            if needle in text:
                raise AssertionError(f"local path leaked in {path}")


def main() -> int:
    for module in MODULES:
        if not (ROOT / module).exists():
            raise AssertionError(f"missing required file: {module}")
    gate = strict_yaw_gate_status(2.06058)
    if gate["yaw_gate_pass"] or not gate["near_boundary_not_relaxed"]:
        raise AssertionError("yaw=2.06058 must be near-boundary, not pass")
    with tempfile.TemporaryDirectory(prefix="legsa_n4h2e_visual_") as temp:
        dual, n4h2, out = _write_toy_artifacts(Path(temp))
        command = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_dual_replay_visual_validation.py"),
            "--dual-root",
            str(dual),
            "--n4h2-artifacts-root",
            str(n4h2),
            "--output-dir",
            str(out),
            "--case-name",
            "toy",
            "--line-name",
            "dual_final_v23_replay",
        ]
        subprocess.run(command, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        required = [
            out / "01_trajectory/dual_replay_traj_truth_est.png",
            out / "02_position_errors/dual_replay_pos_horizontal.png",
            out / "04_attitude/dual_replay_yaw_error_deg.png",
            out / "08_summary_panels/dual_replay_summary_panel.png",
            out / "09_case_review/visual_case_review.md",
            out / "figure_manifest.json",
            out / "VISUAL_VALIDATION_REPORT.json",
        ]
        for path in required:
            if not path.exists():
                raise AssertionError(f"missing generated visual output: {path}")
        report = json.loads((out / "VISUAL_VALIDATION_REPORT.json").read_text(encoding="utf-8"))
        if not report["manual_visual_review_required"]:
            raise AssertionError("manual visual review flag missing")
        for flag in ["solver_output_changed", "trace_solver_input", "numerical_performance_claim", "output_only_correction"]:
            if report.get(flag):
                raise AssertionError(f"{flag} must be false")
        generated_names = "\n".join(str(path) for path in out.rglob("*"))
        for forbidden in ["pure_ins", "single_antenna", "compare"]:
            if forbidden in generated_names:
                raise AssertionError(f"forbidden visual role generated: {forbidden}")
    _assert_no_generated_figures_tracked()
    _assert_docs_no_local_paths()
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
