#!/usr/bin/env python3
"""Audit N8A2 runner, outputs, and boundary flags with toy N8A data.

中文说明：toy 审计覆盖 N8A2 报告、图像和 no-feedback 边界。
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
    "FGO_YAW_RESIDUAL_CONTRACT_REPORT.json",
    "FGO_YAW_FACTOR_REGRESSION_REPORT.json",
    "N8A2_FGO_RERUN_VARIANT_SUMMARIES.json",
    "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json",
    "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json",
    "N8A2_FIGURE_MANIFEST.json",
    "n8a2_yaw_convention_fix_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8a2_fgo_yaw_convention_fix failed: {message}")


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


def _write_csv(path: Path, yaws: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate(yaws):
            writer.writerow({"index": index, "time": float(index), "lat_deg": 30, "lon_deg": 120, "height_m": 10, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": yaw, "vn_mps": 1, "ve_mps": 0, "vd_mps": 0})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        n8a = root / "n8a"
        out = root / "out"
        figs = root / "figs"
        _write_csv(n8a / "N8A_EKF_STATE_NODES.csv", [359.0, 1.0, 2.0, 3.0, 4.0])
        _write_csv(n8a / "N8A_FGO_DIAGNOSTIC_STATES.csv", [180.0, 120.0, 2.0, 3.0, 4.0])
        _write_json(n8a / "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json", {"solve_status": "solved", "finite_output": True, "residual_proxy_p95": 100.0})
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n8a2_fgo_yaw_convention_fix.py"),
                "--n8a-root",
                str(n8a),
                "--output-dir",
                str(out),
                "--figure-output-dir",
                str(figs),
                "--allow-run",
                "--run-rerun",
                "true",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            _fail(proc.stderr[-1200:])
        for name in REQUIRED_OUTPUTS:
            if not (out / name).exists():
                _fail(f"missing output: {name}")
        decision = json.loads((out / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") == "yaw_wrap_fix_failed":
            _fail("yaw wrap fix failed")
        if decision.get("output_only_yaw_correction") or decision.get("fgo_output_feedback_to_ekf"):
            _fail("boundary flags failed")
        variants = json.loads((out / "N8A2_FGO_RERUN_VARIANT_SUMMARIES.json").read_text(encoding="utf-8"))
        fixed = next(row for row in variants["variants"] if row["variant"] == "yaw_wrap_fixed_default_active_stack")
        if not fixed.get("real_solver_rerun"):
            _fail("fixed variant was not a real rerun")
        manifest = json.loads((out / "N8A2_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("required_figures_nonempty"):
            _fail("figures missing or empty")
    print("audit_n8a2_fgo_yaw_convention_fix passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
