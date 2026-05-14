#!/usr/bin/env python3
"""Audit N8C2 factor activation review on a toy runtime tree.

中文说明：使用临时目录生成 toy runtime，验证 N8C2 边界和报告完整性。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    "FGO_FACTOR_ACTIVATION_AUDIT_REPORT.json",
    "FGO_RESIDUAL_WHITENING_REVIEW_REPORT.json",
    "FGO_SMOOTHNESS_COMPONENT_REVIEW_REPORT.json",
    "FGO_RAW_DOPPLER_FACTOR_ACTIVATION_REVIEW.json",
    "FGO_RAW_DOPPLER_WEIGHT_SENSITIVITY_REPORT.json",
    "FGO_GO2_JOINT_FACTOR_ACTIVATION_REVIEW.json",
    "FGO_FACTOR_TOGGLE_INTEGRITY_REPORT.json",
    "FGO_CANDIDATE_FACTOR_REAL_CONTRIBUTION_REPORT.json",
    "N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json",
    "N8C2_FIGURE_MANIFEST.json",
    "n8c2_factor_activation_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8c2_fgo_factor_activation_review failed: {message}")


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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_ekf_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]
    yaws = [358.0, 359.5, 1.0, 2.5, 4.0, 5.0, 7.0, 8.0]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, yaw in enumerate(yaws):
            writer.writerow(
                {
                    "index": index,
                    "time": index * 10.0,
                    "lat_deg": 30.0 + index * 1e-6,
                    "lon_deg": 120.0 + index * 1.2e-6,
                    "height_m": 10.0 + 0.05 * index,
                    "roll_deg": 0.1 * index,
                    "pitch_deg": 0.04 * index,
                    "yaw_deg": yaw,
                    "vn_mps": 1.0 + 0.02 * index,
                    "ve_mps": 0.1 + 0.01 * index,
                    "vd_mps": -0.02,
                }
            )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        _fail(proc.stderr[-2000:] or proc.stdout[-2000:])


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    n8a = root / "N8A_no_feedback_fgo_foundation"
    n8a2 = root / "N8A2_fgo_yaw_convention_fix"
    n8b = root / "N8B_fgo_factor_graph_policy_review"
    n8c = root / "N8C_no_feedback_fgo_visual_validation"
    n5b = root / "N5B_rtklib_doppler_provider_activation"
    n7c6 = root / "N7C6_go2_proprioceptive_joint_factor"
    n7c5 = root / "N7C5_go2_full_proprioceptive_factor_mining"
    _write_ekf_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", {"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0})
    _write_json(n5b / "N5B_RAW_DOPPLER_PROVIDER_REPORT.json", {"raw_doppler_update_count": 8, "epoch_alignment_count": 8})
    n7c6.mkdir(parents=True, exist_ok=True)
    n7c5.mkdir(parents=True, exist_ok=True)
    _run(
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
            str(n8b),
            "--figure-output-dir",
            str(root / "n8b_figures"),
            "--allow-run",
        ]
    )
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8c_no_feedback_fgo_visual_validation.py"),
            "--n8b-root",
            str(n8b),
            "--n8a2-root",
            str(n8a2),
            "--output-dir",
            str(n8c),
            "--figure-output-dir",
            str(root / "n8c_figures"),
            "--allow-run",
            "--rerun-missing-timeseries",
            "true",
        ]
    )
    return n8c, n8b, n8a2, n5b, n7c6, n7c5, root


def _run_n8c2(root: Path) -> Path:
    n8c, n8b, n8a2, n5b, n7c6, n7c5, base = _prepare_runtime(root)
    out = base / "N8C2_fgo_factor_activation_review"
    figs = base / "N8C2_figures"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8c2_fgo_factor_activation_review.py"),
            "--n8c-root",
            str(n8c),
            "--n8b-root",
            str(n8b),
            "--n8a2-root",
            str(n8a2),
            "--n5b-root",
            str(n5b),
            "--n7c6-root",
            str(n7c6),
            "--n7c5-root",
            str(n7c5),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
            "--run-weight-sensitivity",
            "true",
        ]
    )
    return out


def _load(out: Path, name: str) -> dict:
    return json.loads((out / name).read_text(encoding="utf-8"))


def _check(out: Path, check: str) -> None:
    for name in REQUIRED_OUTPUTS:
        if not (out / name).exists():
            _fail(f"missing output: {name}")
    activation = _load(out, "FGO_FACTOR_ACTIVATION_AUDIT_REPORT.json")
    whitening = _load(out, "FGO_RESIDUAL_WHITENING_REVIEW_REPORT.json")
    smoothness = _load(out, "FGO_SMOOTHNESS_COMPONENT_REVIEW_REPORT.json")
    raw = _load(out, "FGO_RAW_DOPPLER_FACTOR_ACTIVATION_REVIEW.json")
    sensitivity = _load(out, "FGO_RAW_DOPPLER_WEIGHT_SENSITIVITY_REPORT.json")
    toggle = _load(out, "FGO_FACTOR_TOGGLE_INTEGRITY_REPORT.json")
    candidate = _load(out, "FGO_CANDIDATE_FACTOR_REAL_CONTRIBUTION_REPORT.json")
    decision = _load(out, "N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json")
    figures = _load(out, "N8C2_FIGURE_MANIFEST.json")
    if check in {"all", "activation"}:
        if activation.get("paper_performance_claim") or not activation.get("proxy_residuals_kept_separate"):
            _fail("activation boundary failed")
        if len(activation.get("factor_activation_rows", [])) != 6:
            _fail("active factor rows missing")
    if check in {"all", "raw"}:
        if raw.get("trace_weight_tuning") or raw.get("classification") not in {"activation_missing", "weight_too_weak", "dominated_by_receiver_velocity_smoothness", "consistent_no_large_delta", "review_logic_false_positive"}:
            _fail("raw doppler classification failed")
    if check in {"all", "toggle"}:
        if toggle.get("status") != "toggle_integrity_passed":
            _fail("toggle integrity failed")
    if check in {"all", "whitening"}:
        if not whitening.get("dimension_normalized_review_complete"):
            _fail("whitening review incomplete")
    if check in {"all", "smoothness"}:
        if not smoothness.get("smoothness_component_rows") or smoothness.get("smoothness_deleted_as_final_shortcut"):
            _fail("smoothness review failed")
    if check in {"all", "contribution"}:
        if candidate.get("formal_activation"):
            _fail("candidate factor was formalized")
    if check == "all":
        if not sensitivity.get("all_required_variants_run") or not sensitivity.get("all_variants_real_solver_rerun"):
            _fail("weight sensitivity did not run all real reruns")
        if decision.get("paper_performance_claim") or decision.get("output_substitution"):
            _fail("decision boundary failed")
        if figures.get("figure_count_total") != 14 or not figures.get("required_figures_nonempty"):
            _fail("figures missing or empty")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=["all", "activation", "raw", "toggle", "whitening", "smoothness", "contribution"], default="all")
    parser.add_argument("--skip-hygiene", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.skip_hygiene:
        _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        out = _run_n8c2(Path(tmp))
        _check(out, args.check)
    print(f"audit_n8c2_fgo_factor_activation_review passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
