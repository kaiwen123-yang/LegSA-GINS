#!/usr/bin/env python3
"""Audit N8C3 Raw Doppler FGO factor fix on toy runtime.

中文说明：用临时 runtime 验证 Raw Doppler residual/Jacobian 不再是 proxy-only。
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
    "FGO_RAW_DOPPLER_FACTOR_CONTRACT_REPORT.json",
    "FGO_RAW_DOPPLER_DATASET_LINK_REPORT.json",
    "FGO_RAW_DOPPLER_SOLVER_INJECTION_REPORT.json",
    "FGO_RAW_DOPPLER_TOGGLE_REGRESSION_REPORT.json",
    "N8C3_RAW_DOPPLER_RERUN_VARIANT_SUMMARIES.json",
    "N8C3_RAW_DOPPLER_FIX_COMPARISON_REPORT.json",
    "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json",
    "N8C3_FIGURE_MANIFEST.json",
    "n8c3_raw_doppler_factor_fix_case_review.md",
]

ARTIFACT_RE = re.compile(r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8c3_raw_doppler_fgo_factor_fix failed: {message}")


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
        for index in range(12):
            writer.writerow(
                {
                    "index": index,
                    "time": index * 0.2,
                    "lat_deg": 30.0 + index * 1e-6,
                    "lon_deg": 120.0 + index * 1.1e-6,
                    "height_m": 10.0,
                    "roll_deg": 0.1 * index,
                    "pitch_deg": 0.03 * index,
                    "yaw_deg": float(index),
                    "vn_mps": 1.0 + index * 0.02,
                    "ve_mps": 0.1,
                    "vd_mps": 0.0,
                }
            )


def _write_raw_doppler_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "doppler_obs_count", "provider_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(12):
            writer.writerow(
                {
                    "time": index * 0.2,
                    "vn": 0.45 + index * 0.01,
                    "ve": -0.02,
                    "vd": 0.03,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 20,
                    "doppler_obs_count": 30,
                    "provider_status": "available",
                }
            )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        _fail(proc.stderr[-2400:] or proc.stdout[-2400:])


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    n8a = root / "N8A_no_feedback_fgo_foundation"
    n8a2 = root / "N8A2_fgo_yaw_convention_fix"
    n8b = root / "N8B_fgo_factor_graph_policy_review"
    n8c = root / "N8C_no_feedback_fgo_visual_validation"
    n8c2 = root / "N8C2_fgo_factor_activation_review"
    n5b = root / "N5B_rtklib_doppler_provider_activation"
    _write_ekf_csv(n8a / "N8A_EKF_STATE_NODES.csv")
    _write_raw_doppler_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8a2 / "N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json", {"n8a2_default_yaw_delta_wrapped_rmse_deg": 1.0})
    _write_json(n8c / "N8C_NO_FEEDBACK_FGO_VISUAL_DECISION_REPORT.json", {"status": "factor_contribution_needs_review"})
    _write_json(n8c2 / "N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json", {"status": "raw_doppler_activation_missing"})
    _run(
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
        ]
    )
    return n8c2, n8c, n8b, n8a2, n5b


def _run_n8c3(root: Path) -> Path:
    n8c2, n8c, n8b, n8a2, n5b = _prepare_runtime(root)
    out = root / "N8C3_raw_doppler_fgo_factor_fix"
    figs = root / "N8C3_figs"
    _run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8c3_raw_doppler_fgo_factor_fix.py"),
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
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
            "--run-rerun",
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
    contract = _load(out, "FGO_RAW_DOPPLER_FACTOR_CONTRACT_REPORT.json")
    link = _load(out, "FGO_RAW_DOPPLER_DATASET_LINK_REPORT.json")
    injection = _load(out, "FGO_RAW_DOPPLER_SOLVER_INJECTION_REPORT.json")
    toggle = _load(out, "FGO_RAW_DOPPLER_TOGGLE_REGRESSION_REPORT.json")
    variants = _load(out, "N8C3_RAW_DOPPLER_RERUN_VARIANT_SUMMARIES.json")
    decision = _load(out, "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json")
    figures = _load(out, "N8C3_FIGURE_MANIFEST.json")
    if check in {"all", "jacobian"}:
        if not contract.get("toy_passed") or contract.get("touches_yaw"):
            _fail("contract jacobian failed")
    if check in {"all", "solver"}:
        if not injection.get("appears_in_solver_residual_vector") or injection.get("residual_row_count", 0) <= 0:
            _fail("raw doppler not in solver residual")
        if injection.get("jacobian_nonzero_count", 0) <= 0:
            _fail("raw doppler jacobian missing")
    if check in {"all", "toggle"}:
        if not toggle.get("toggle_regression_passed") or injection.get("dim_delta", 0) <= 0:
            _fail("raw doppler toggle not real")
    if check in {"all", "no_proxy"}:
        if not variants.get("raw_doppler_direct_equation_available"):
            _fail("raw doppler still proxy-only")
    if check == "all":
        if link.get("aligned_factor_count", 0) <= 0 or link.get("factor_table_rows", 0) <= 0:
            _fail("dataset link did not create rows")
        if not variants.get("all_required_variants_run") or not variants.get("all_variants_real_solver_rerun"):
            _fail("variants did not rerun")
        if decision.get("paper_performance_claim") or decision.get("output_substitution") or decision.get("trace_solver_input"):
            _fail("decision boundary failed")
        if figures.get("figure_count_total") != 10 or not figures.get("required_figures_nonempty"):
            _fail("figures missing or empty")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=["all", "solver", "jacobian", "toggle", "no_proxy"], default="all")
    parser.add_argument("--skip-hygiene", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.skip_hygiene:
        _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        out = _run_n8c3(Path(tmp))
        _check(out, args.check)
    print(f"audit_n8c3_raw_doppler_fgo_factor_fix passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
