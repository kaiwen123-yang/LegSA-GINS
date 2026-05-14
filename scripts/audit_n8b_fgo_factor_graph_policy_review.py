#!/usr/bin/env python3
"""Audit N8B runner, real reruns, figures, and boundary flags.

中文说明：审计 N8B runner 的真实重跑、图像和 no-feedback 边界。
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
    "N8B_FGO_POLICY_GRID.json",
    "FGO_SMOOTHNESS_POLICY_REVIEW_REPORT.json",
    "FGO_FACTOR_WEIGHT_REVIEW_REPORT.json",
    "FGO_CANDIDATE_FACTOR_REVIEW_REPORT.json",
    "N8B_FGO_POLICY_ABLATION_SUMMARIES.json",
    "N8B_FGO_POLICY_COMPARISON_REPORT.json",
    "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json",
    "N8B_FIGURE_MANIFEST.json",
    "n8b_factor_graph_policy_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8b_fgo_factor_graph_policy_review failed: {message}")


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
            writer.writerow(
                {
                    "index": index,
                    "time": float(index),
                    "lat_deg": 30.0 + index * 1e-6,
                    "lon_deg": 120.0 + index * 1e-6,
                    "height_m": 10.0,
                    "roll_deg": 0.1 * index,
                    "pitch_deg": 0.05 * index,
                    "yaw_deg": yaw,
                    "vn_mps": 1.0,
                    "ve_mps": 0.2,
                    "vd_mps": 0.0,
                }
            )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        n8a = root / "n8a"
        n8a2 = root / "n8a2"
        n7c6 = root / "n7c6"
        n7c5 = root / "n7c5"
        out = root / "out"
        figs = root / "figs"
        n7c6.mkdir(parents=True)
        n7c5.mkdir(parents=True)
        _write_csv(n8a / "N8A_EKF_STATE_NODES.csv", [359.0, 1.0, 2.0, 3.0, 4.0, 5.0])
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
                str(n7c6),
                "--n7c5-root",
                str(n7c5),
                "--output-dir",
                str(out),
                "--figure-output-dir",
                str(figs),
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
        for name in REQUIRED_OUTPUTS:
            if not (out / name).exists():
                _fail(f"missing output: {name}")
        ablations = json.loads((out / "N8B_FGO_POLICY_ABLATION_SUMMARIES.json").read_text(encoding="utf-8"))
        if ablations.get("variant_count") != 13 or not ablations.get("all_variants_real_solver_rerun"):
            _fail("required real solver variants missing")
        if any(row.get("proxy_only") for row in ablations.get("variants", [])):
            _fail("proxy-only variant found")
        decision = json.loads((out / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("trace_solver_input") or decision.get("smoothness_deletion_final_shortcut"):
            _fail("boundary flags failed")
        manifest = json.loads((out / "N8B_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if manifest.get("figure_count_total") != 10 or not manifest.get("required_figures_nonempty"):
            _fail("figures missing or empty")
    print("audit_n8b_fgo_factor_graph_policy_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
