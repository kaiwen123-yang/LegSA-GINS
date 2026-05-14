#!/usr/bin/env python3
"""Audit N8C no-feedback FGO visual validation runner.

中文说明：用 toy runtime 目录审计 N8C 报告、图像和 no-feedback 边界。
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    "N8C_VISUAL_INPUT_MANIFEST.json",
    "N8C_PLOT_DATA_COVERAGE_REPORT.json",
    "N8C_FACTOR_CONTRIBUTION_REVIEW_REPORT.json",
    "N8C_VISUAL_SANITY_REPORT.json",
    "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json",
    "N8C_FIGURE_MANIFEST.json",
    "n8c_visual_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8c_no_feedback_fgo_visual_validation failed: {message}")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_hygiene() -> None:
    for token in ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users"]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden tracked artifact: " + ", ".join(hits[:6]))


def _write_ekf_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    yaws = [359.0, 1.0, 2.0, 4.0, 5.0, 6.0, 8.0]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate(yaws):
            writer.writerow({"index": index, "time": index * 60.0, "lat_deg": 30.0 + index * 1e-6, "lon_deg": 120.0 + index * 1e-6, "height_m": 10.0, "roll_deg": 0.1 * index, "pitch_deg": 0.05 * index, "yaw_deg": yaw, "vn_mps": 1.0, "ve_mps": 0.1, "vd_mps": 0.0})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_n8b(root: Path) -> tuple[Path, Path]:
    n8a = root / "N8A_no_feedback_fgo_foundation"
    n8a2 = root / "N8A2_fgo_yaw_convention_fix"
    n8b = root / "N8B_fgo_factor_graph_policy_review"
    _write_ekf_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", {"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0})
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8b_fgo_factor_graph_policy_review.py"),
            "--n8a2-root",
            str(n8a2),
            "--n8a-root",
            str(n8a),
            "--n7c6-root",
            str(root / "n7c6"),
            "--n7c5-root",
            str(root / "n7c5"),
            "--output-dir",
            str(n8b),
            "--figure-output-dir",
            str(root / "n8b_figs"),
            "--allow-run",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _fail(proc.stderr[-1600:])
    return n8b, n8a2


def main() -> int:
    _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        n8b, n8a2 = _prepare_n8b(root)
        out = root / "N8C_no_feedback_fgo_visual_validation"
        figs = root / "n8c_figs"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n8c_no_feedback_fgo_visual_validation.py"),
                "--n8b-root",
                str(n8b),
                "--n8a2-root",
                str(n8a2),
                "--output-dir",
                str(out),
                "--figure-output-dir",
                str(figs),
                "--allow-run",
                "--rerun-missing-timeseries",
                "true",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            _fail(proc.stderr[-1600:])
        for name in REQUIRED_OUTPUTS:
            if not (out / name).exists():
                _fail(f"missing output: {name}")
        manifest = json.loads((out / "N8C_VISUAL_INPUT_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("weak_yaw_variant_found") or manifest.get("trace_solver_input"):
            _fail("manifest boundary failed")
        decision = json.loads((out / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("paper_performance_claim") or decision.get("output_substitution"):
            _fail("decision boundary failed")
        figures = json.loads((out / "N8C_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if figures.get("figure_count_total") != 22 or not figures.get("required_figures_nonempty"):
            _fail("figures missing or empty")
    print("audit_n8c_no_feedback_fgo_visual_validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
