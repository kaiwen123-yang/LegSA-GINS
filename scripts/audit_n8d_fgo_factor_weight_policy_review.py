#!/usr/bin/env python3
"""Audit N8D FGO factor weight policy review on toy runtime.

中文说明：用临时 runtime 验证 N8D 权重审查真实重跑且不越过 claim 边界。
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
    "N8D_FGO_WEIGHT_POLICY_GRID.json",
    "FGO_WHITENED_BALANCE_POLICY_REPORT.json",
    "FGO_SMOOTHNESS_WEIGHT_POLICY_REPORT.json",
    "FGO_RAW_RECEIVER_WEIGHT_BALANCE_REPORT.json",
    "FGO_GO2_JOINT_WEIGHT_POLICY_REPORT.json",
    "FGO_DUAL_YAW_WEIGHT_POLICY_REPORT.json",
    "FGO_PROCESS_FACTOR_POLICY_REVIEW_REPORT.json",
    "N8D_FORMAL_ENGINEERING_ABLATION_MATRIX.json",
    "N8D_FGO_WEIGHT_POLICY_VARIANT_SUMMARIES.json",
    "N8D_FGO_WEIGHT_POLICY_COMPARISON_REPORT.json",
    "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json",
    "N8D_FIGURE_MANIFEST.json",
    "n8d_factor_weight_policy_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8d_fgo_factor_weight_policy_review failed: {message}")


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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(14):
            writer.writerow(
                {
                    "index": index,
                    "time": index * 0.2,
                    "lat_deg": 30.0 + index * 1.0e-6,
                    "lon_deg": 120.0 + index * 1.1e-6,
                    "height_m": 10.0 + index * 0.01,
                    "roll_deg": 0.05 * index,
                    "pitch_deg": 0.02 * index,
                    "yaw_deg": float(index),
                    "vn_mps": 1.0 + index * 0.03,
                    "ve_mps": 0.1 + index * 0.005,
                    "vd_mps": 0.01,
                }
            )


def _write_raw_doppler_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "doppler_obs_count", "provider_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(14):
            writer.writerow(
                {
                    "time": index * 0.2,
                    "vn": 0.62 + index * 0.015,
                    "ve": 0.02 + index * 0.002,
                    "vd": 0.0,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 18,
                    "doppler_obs_count": 28,
                    "provider_status": "available",
                }
            )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        _fail(proc.stderr[-2600:] or proc.stdout[-2600:])


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    n8a = root / "N8A_no_feedback_fgo_foundation"
    n8a2 = root / "N8A2_fgo_yaw_convention_fix"
    n8b = root / "N8B_fgo_factor_graph_policy_review"
    n8c = root / "N8C_no_feedback_fgo_visual_validation"
    n8c2 = root / "N8C2_fgo_factor_activation_review"
    n8c3 = root / "N8C3_raw_doppler_fgo_factor_fix"
    n5b = root / "N5B_rtklib_doppler_provider_activation"
    n7c6 = root / "N7C6_go2_proprioceptive_joint_factor"
    _write_ekf_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_raw_doppler_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", {"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0})
    _write_json(n8c / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json", {"status": "factor_contribution_needs_review"})
    _write_json(
        n8c2 / "FGO_SMOOTHNESS_COMPONENT_REVIEW_REPORT.json",
        {
            "stage": "N8C2_fgo_factor_activation_review",
            "component_causing_spikes": "yaw_smoothness",
            "yaw_smoothness_still_dominates": True,
        },
    )
    _write_json(n8c3 / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json", {"status": "raw_doppler_active_consistent_or_dominated"})
    _write_json(n7c6 / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", {"status": "go2_joint_factor_review_passed"})
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
            str(root / "n7c5"),
            "--output-dir",
            str(n8b),
            "--figure-output-dir",
            str(root / "n8b_figs"),
            "--allow-run",
        ]
    )
    return n8c3, n8c2, n8c, n8b, n8a2, n5b, n7c6, root


def _run_n8d(root: Path) -> Path:
    n8c3, n8c2, n8c, n8b, n8a2, n5b, n7c6, runtime = _prepare_runtime(root)
    out = runtime / "N8D_fgo_factor_weight_policy_review"
    figs = runtime / "N8D_figs"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8d_fgo_factor_weight_policy_review.py"),
            "--n8c3-root",
            str(n8c3),
            "--n8c2-root",
            str(n8c2),
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
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ]
    )
    return out


def _load(out: Path, name: str) -> dict:
    return json.loads((out / name).read_text(encoding="utf-8"))


def _check(out: Path, check: str) -> None:
    for name in REQUIRED_OUTPUTS:
        if not (out / name).exists():
            _fail(f"missing output: {name}")
    grid = _load(out, "N8D_FGO_WEIGHT_POLICY_GRID.json")
    balance = _load(out, "FGO_WHITENED_BALANCE_POLICY_REPORT.json")
    smoothness = _load(out, "FGO_SMOOTHNESS_WEIGHT_POLICY_REPORT.json")
    formal = _load(out, "N8D_FORMAL_ENGINEERING_ABLATION_MATRIX.json")
    variants = _load(out, "N8D_FGO_WEIGHT_POLICY_VARIANT_SUMMARIES.json")
    decision = _load(out, "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json")
    figures = _load(out, "N8D_FIGURE_MANIFEST.json")
    if check == "all":
        if len(grid.get("formal_ablation_variants", [])) != 14:
            _fail("policy grid missing formal variants")
        if not formal.get("all_required_variants_run") or not formal.get("all_variants_real_solver_rerun"):
            _fail("formal matrix did not run real solver variants")
        if variants.get("variant_count") != 14:
            _fail("unexpected formal variant count")
        if figures.get("figure_count_total") != 12 or not figures.get("required_figures_nonempty"):
            _fail("figures missing or empty")
    if check in {"all", "no_trace"}:
        if balance.get("trace_weight_tuning") or decision.get("trace_weight_tuning"):
            _fail("trace tuning flag set")
        if any(row.get("trace_weight_tuning") or row.get("trace_solver_input") for row in variants.get("variants", [])):
            _fail("variant uses trace")
    if check in {"all", "no_finalv23"}:
        if balance.get("final_v23_weight_tuning") or decision.get("final_v23_weight_tuning"):
            _fail("final_v23 tuning flag set")
        if any(row.get("final_v23_weight_tuning") or row.get("final_v23_output_solver_input") for row in variants.get("variants", [])):
            _fail("variant uses final_v23")
    if check in {"all", "no_smoothness_deletion"}:
        if decision.get("smoothness_factor_deleted_for_metric") or not decision.get("no_smoothness_final_shortcut"):
            _fail("smoothness deletion shortcut detected")
        if not smoothness.get("no_smoothness_final_shortcut"):
            _fail("smoothness report allows deletion shortcut")
    if check in {"all", "no_paper_claim"}:
        if decision.get("paper_performance_claim") or not decision.get("no_paper_performance_claim"):
            _fail("paper performance claim detected")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=["all", "no_trace", "no_finalv23", "no_smoothness_deletion", "no_paper_claim"], default="all")
    parser.add_argument("--skip-hygiene", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.skip_hygiene:
        _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        out = _run_n8d(Path(tmp))
        _check(out, args.check)
    print(f"audit_n8d_fgo_factor_weight_policy_review passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
