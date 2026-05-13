#!/usr/bin/env python3
"""Audit N7C6A final review workflow with toy N7C6 outputs.

中文说明：用 toy runtime 产物验证 N7C6A runner，不提交图像或 runtime artifacts。
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
    "src/legsa_gins/go2_prior/go2_n7c6_final_visual_loader.py",
    "src/legsa_gins/go2_prior/go2_n7c6_metric_semantic_guard.py",
    "src/legsa_gins/go2_prior/go2_n7c6_plot_label_readability.py",
    "src/legsa_gins/go2_prior/go2_n7c6_final_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c6_final_decision.py",
    "scripts/experiments/run_n7c6a_go2_joint_factor_final_review.py",
    "scripts/audit_n7c6_metric_semantics.py",
    "scripts/audit_n7c6_plot_labels_readable.py",
    "scripts/audit_n7c6_ready_to_merge.py",
    "docs/experiments/n7c6a_go2_joint_factor_final_review.md",
    "docs/experiments/n7c6a_metric_semantics.md",
    "docs/experiments/n7c6a_plot_readability.md",
    "docs/experiments/n7c6a_decision.md",
    "docs/codex_prompts/N7C6A_go2_joint_factor_final_review.md",
]

REQUIRED_OUTPUTS = [
    "N7C6A_VISUAL_INPUT_MANIFEST.json",
    "N7C6A_METRIC_SEMANTIC_GUARD_REPORT.json",
    "N7C6A_PLOT_LABEL_READABILITY_REPORT.json",
    "N7C6A_FINAL_REVIEW_DECISION_REPORT.json",
    "N7C6A_FIGURE_MANIFEST.json",
    "n7c6a_final_review_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_PROPRIOCEPTIVE_FACTOR_PRIORS\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c6a_go2_joint_factor_final_review failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_eval_nav(path: Path, n: int = 12) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "vn", "yaw_deg", "roll_deg", "pitch_deg"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i in range(n):
            writer.writerow({"time": i * 0.1, "vn": 1.0 + i * 0.01, "yaw_deg": 0.1 * i, "roll_deg": 0.01 * i, "pitch_deg": -0.01 * i})


def _write_toy_n7c6(root: Path) -> None:
    variants = [
        "baseline_no_go2_proprioceptive",
        "horizontal_only_fixed_1p0",
        "rollpitch_only_5deg",
        "rollpitch_only_3deg",
        "rollpitch_only_1p6deg",
        "rollpitch_only_1deg",
        "joint_rp3deg_hv1p0",
        "joint_rp1p6deg_hv1p0",
        "joint_rp1deg_hv1p0",
        "joint_rp0p75_hv1p0_diagnostic",
        "joint_rp1p6deg_hv0p75_diagnostic",
        "joint_rp1p6deg_hv1p0_sourceaware_off",
        "receiver_velocity_stress_baseline",
        "receiver_velocity_stress_joint",
        "raw_doppler_stress_baseline",
        "raw_doppler_stress_joint",
    ]
    _write_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json", {"matrix": [{"variant_id": v} for v in variants], "required_variants_present": True, "go2_position_prior_enabled": False, "go2_yaw_prior_enabled": False, "go2_vertical_velocity_prior_enabled": False})
    _write_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_VARIANT_SUMMARIES.json", {"variants": [{"variant_id": v, "summary": {"roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1}, "manifest": {"go2_proprioceptive_joint_factor_update_count": 10}} for v in variants], "paper_performance_claim": False})
    _write_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_COMPARISON_REPORT.json", {"comparisons": {"joint_rp1deg_minus_horizontal_only": {"delta": {"horizontal_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}}, "receiver_velocity_stress_joint_minus_baseline": {"delta": {"horizontal_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}}, "raw_doppler_stress_joint_minus_baseline": {"delta": {"horizontal_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}}}, "paper_performance_claim": False})
    _write_json(root / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json", {"variants": {v: {"attitude": {"nis_proxy": {"p95": 1.0}, "residual_norm": {"p95": 0.1}}, "horizontal_velocity": {"nis_proxy": {"p95": 1.0}, "residual_norm": {"p95": 0.1}}, "joint_update_count_proxy": 10, "overconfidence_flag": False, "stuck_at_cap_flag": False} for v in variants}, "any_overconfidence": False, "any_stuck_at_cap": False, "paper_performance_claim": False})
    _write_json(root / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", {"status": "stronger_go2_proprioceptive_joint_factor_ready", "recommended_default": "joint_rp1deg_hv1p0", "paper_performance_claim": False})
    _write_json(root / "N7C6_FIGURE_MANIFEST.json", {"required_figures": ["clean_roll_pitch_error_baseline_vs_joint.png", "joint_minus_horizontal_only_delta.png"], "figure_count_total": 2, "required_figures_generated": True, "required_figures_nonempty": True})
    for variant in variants:
        _write_eval_nav(root / "variants" / variant / "EVAL_NAV.csv")


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


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"missing tracked file: {rel}")
    _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        n7c6 = Path(tmp) / "n7c6"
        out = Path(tmp) / "n7c6a"
        figs = Path(tmp) / "figs"
        _write_toy_n7c6(n7c6)
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n7c6a_go2_joint_factor_final_review.py"),
                "--n7c6-root",
                str(n7c6),
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
        decision = json.loads((out / "N7C6A_FINAL_REVIEW_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("status") != "ready_to_merge_PR38_and_start_N8A":
            _fail(f"unexpected decision: {decision.get('status')}")
        manifest = json.loads((out / "N7C6A_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if manifest.get("figure_count_total") != 12 or not manifest.get("required_figures_nonempty"):
            _fail("figure manifest failed")
    print("audit_n7c6a_go2_joint_factor_final_review passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
