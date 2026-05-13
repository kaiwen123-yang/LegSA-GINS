#!/usr/bin/env python3
"""Audit N8A no-feedback FGO foundation with toy runtime data.

中文说明：toy 审计只验证 no-feedback FGO foundation 合同，不做性能 claim。
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

REQUIRED_FILES = [
    "src/legsa_gins/fgo/__init__.py",
    "src/legsa_gins/fgo/fgo_backend_discovery.py",
    "src/legsa_gins/fgo/fgo_state_types.py",
    "src/legsa_gins/fgo/fgo_factor_types.py",
    "src/legsa_gins/fgo/fgo_factor_registry.py",
    "src/legsa_gins/fgo/fgo_dataset_builder.py",
    "src/legsa_gins/fgo/fgo_linear_solver.py",
    "src/legsa_gins/fgo/fgo_no_feedback_smoother.py",
    "src/legsa_gins/fgo/fgo_evaluator.py",
    "src/legsa_gins/fgo/fgo_visual_plots.py",
    "src/legsa_gins/fgo/fgo_decision.py",
    "scripts/experiments/run_n8a_no_feedback_fgo_foundation.py",
]

REQUIRED_OUTPUTS = [
    "N8A_BACKEND_DISCOVERY_REPORT.json",
    "N8A_FACTOR_REGISTRY_REPORT.json",
    "N8A_DATASET_REPORT.json",
    "N8A_NO_FEEDBACK_SMOOTHER_REPORT.json",
    "N8A_EVALUATION_REPORT.json",
    "N8A_FIGURE_MANIFEST.json",
    "N8A_NO_FEEDBACK_FGO_DECISION_REPORT.json",
    "n8a_no_feedback_fgo_case_review.md",
]

ARTIFACT_RE = re.compile(r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_PROPRIOCEPTIVE_FACTOR_PRIORS\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8a_no_feedback_fgo_foundation failed: {message}")


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_hygiene() -> None:
    for token in ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users", "/home/kaiwen/" + "legsa_external_artifacts"]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden tracked artifact: " + ", ".join(hits[:6]))


def _write_eval(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn", "ve", "vd"])
        writer.writeheader()
        for index in range(20):
            writer.writerow({"time": index * 0.1, "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 10.0, "roll_deg": 0.1, "pitch_deg": -0.1, "yaw_deg": index * 0.2, "vn": 1.0, "ve": 0.1, "vd": 0.0})


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"missing file: {rel}")
    _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        n7c6 = root / "n7c6"
        _write_eval(n7c6 / "variants" / "joint_rp1deg_hv1p0" / "EVAL_NAV.csv")
        out = root / "out"
        figs = root / "figs"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n8a_no_feedback_fgo_foundation.py"),
                "--clean-root",
                str(root / "clean"),
                "--n5b-root",
                str(root / "n5b"),
                "--n6b-root",
                str(root / "n6b"),
                "--n7a-root",
                str(root / "n7a"),
                "--n7b4-root",
                str(root / "n7b4"),
                "--n7c-root",
                str(root / "n7c"),
                "--n7c5-root",
                str(root / "n7c5"),
                "--n7c6-root",
                str(n7c6),
                "--dual-root",
                str(root / "dual"),
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
            _fail(proc.stderr[-1000:])
        for name in REQUIRED_OUTPUTS:
            if not (out / name).exists():
                _fail(f"missing output: {name}")
        decision = json.loads((out / "N8A_NO_FEEDBACK_FGO_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") != "n8a_no_feedback_fgo_foundation_ready":
            _fail(f"unexpected decision {decision.get('status')}")
        if decision.get("fgo_output_feedback_to_ekf") or decision.get("paper_performance_claim"):
            _fail("boundary failed")
    print("audit_n8a_no_feedback_fgo_foundation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
