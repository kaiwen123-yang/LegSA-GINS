#!/usr/bin/env python3
"""Audit N8E formal engineering ablation with caveat on toy runtime.

中文说明：用临时 runtime 验证 N8E 输出和边界，不读取真实路径。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OUTPUTS = [
    "N8E_INPUT_MANIFEST.json",
    "N8E_FINAL_ENGINEERING_ABLATION_MATRIX.json",
    "N8E_FINAL_ENGINEERING_ABLATION_TABLE.csv",
    "N8E_FINAL_ENGINEERING_ABLATION_SUMMARY.md",
    "N8E_MODULE_CONTRIBUTION_SUMMARY_REPORT.json",
    "N8E_CAVEAT_REPORT.json",
    "N8E_CLAIM_BOUNDARY_REVIEW_REPORT.json",
    "N8E_FORMAL_ABLATION_WITH_CAVEAT_DECISION_REPORT.json",
    "N8E_FIGURE_MANIFEST.json",
    "n8e_formal_ablation_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(FGO_SMOOTHED_NAV\.csv|FGO_FACTOR_TABLE\.csv|N8E_FINAL_ENGINEERING_ABLATION_TABLE\.csv|summary\.json|error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n8e_formal_ablation_with_caveat failed: {message}")


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _variant(name: str, *, diagnostic: bool = False, h: float = 0.1, yaw: float = 0.2) -> dict[str, Any]:
    return {
        "variant": name,
        "solve_status": "solved",
        "real_solver_rerun": True,
        "proxy_only": False,
        "finite_output": True,
        "diagnostic_only": diagnostic,
        "horizontal_delta_rmse_m": h,
        "up_delta_rmse_m": h / 10.0,
        "yaw_delta_wrapped_rmse_deg": yaw,
        "roll_delta_rmse_deg": 0.03,
        "pitch_delta_rmse_deg": 0.04,
        "raw_doppler_contribution_share": 0.01,
        "smoothness_contribution_share": 0.02,
        "no_feedback": True,
        "fgo_output_feedback_to_ekf": False,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    n5b = root / "N5B"
    n6b = root / "N6B"
    n7c6 = root / "N7C6"
    n8a2 = root / "N8A2"
    n8b = root / "N8B"
    n8c3 = root / "N8C3"
    n8d = root / "N8D"
    dual = root / "dual"
    variants = [
        "ekf_baseline_no_fgo_reference",
        "n8b_weak_yaw_default",
        "balanced_policy_A",
        "balanced_policy_B",
        "conservative_policy",
        "raw_receiver_balanced_best",
        "go2_joint_weight_best",
        "dual_yaw_weight_best",
        "split_smoothness_best",
        "candidate_stack_diagnostic",
        "no_raw_doppler_diagnostic",
        "no_go2_joint_diagnostic",
        "no_dual_yaw_diagnostic",
        "no_smoothness_diagnostic",
    ]
    _write_json(n5b / "N5B_RAW_DOPPLER_DECISION_REPORT.json", {"status": "raw_doppler_frontend_active"})
    _write_json(n5b / "N5B_RAW_DOPPLER_FACTOR_COMPARISON_REPORT.json", {"status": "available"})
    _write_json(n6b / "N6B_SOURCE_AWARE_DECISION_REPORT.json", {"status": "ready_with_weak_stress_evidence"})
    _write_json(n6b / "N6B_SOURCE_AWARE_ABLATION_MATRIX.json", {"status": "available"})
    _write_json(n7c6 / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json", {"status": "go2_joint_factor_review_passed"})
    _write_json(n7c6 / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json", {"status": "available"})
    _write_json(n8a2 / "N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json", {"status": "yaw_convention_fixed_foundation_ready"})
    _write_json(n8b / "N8B_FGO_FACTOR_GRAPH_POLICY_DECISION_REPORT.json", {"status": "weak_yaw_smoothness_ready"})
    _write_json(n8c3 / "N8C3_RAW_DOPPLER_FGO_FACTOR_FIX_DECISION_REPORT.json", {"status": "raw_doppler_active_consistent_or_dominated"})
    _write_json(
        n8d / "N8D_FGO_WEIGHT_POLICY_VARIANT_SUMMARIES.json",
        {
            "stage": "N8D_fgo_factor_weight_policy_review",
            "variant_count": len(variants),
            "variants": [_variant(name, diagnostic=("diagnostic" in name), h=0.02 + i * 0.01, yaw=0.05 + i * 0.02) for i, name in enumerate(variants)],
            "all_required_variants_run": True,
            "all_variants_real_solver_rerun": True,
        },
    )
    _write_json(
        n8d / "N8D_FORMAL_ENGINEERING_ABLATION_MATRIX.json",
        {
            "variant_count": len(variants),
            "required_variants": variants,
            "all_required_variants_run": True,
            "all_variants_real_solver_rerun": True,
            "best_solver_visible_balance_variant": "conservative_policy",
            "no_feedback": True,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8d / "N8D_FGO_WEIGHT_POLICY_DECISION_REPORT.json",
        {
            "status": "raw_doppler_active_but_low_fgo_marginal_value",
            "recommended_next_stage": "N8E_formal_ablation_with_caveat",
            "raw_doppler_remains_low_marginal_value": True,
            "no_feedback": True,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8d / "FGO_RAW_RECEIVER_WEIGHT_BALANCE_REPORT.json",
        {
            "best_solver_visible_raw_receiver_balance": "receiver_vel_x0p5_raw_x1",
            "raw_doppler_remains_low_marginal_value": True,
            "variants": [_variant("receiver_vel_x0p5_raw_x1", h=0.03, yaw=0.06)],
            "no_feedback": True,
        },
    )
    _write_json(
        n8d / "FGO_GO2_JOINT_WEIGHT_POLICY_REPORT.json",
        {
            "best_solver_visible_go2_joint_policy": "go2_joint_x2",
            "go2_joint_stable_low_marginal_value": False,
            "variants": [_variant("go2_joint_x2", h=0.04, yaw=0.08)],
            "no_feedback": True,
            "paper_performance_claim": False,
        },
    )
    _write_json(
        n8d / "FGO_DUAL_YAW_WEIGHT_POLICY_REPORT.json",
        {
            "best_solver_visible_dual_yaw_policy": "dual_yaw_x2",
            "variants": [_variant("dual_yaw_x2", h=0.05, yaw=0.04)],
            "no_feedback": True,
            "paper_performance_claim": False,
        },
    )
    _write_json(n8d / "FGO_PROCESS_FACTOR_POLICY_REVIEW_REPORT.json", {"decision": "keep_current_smoothness_for_N8D"})
    dual.mkdir(parents=True, exist_ok=True)
    return n5b, n6b, n7c6, n8a2, n8b, n8c3, n8d, dual


def _run_n8e(root: Path) -> Path:
    n5b, n6b, n7c6, n8a2, n8b, n8c3, n8d, dual = _prepare_runtime(root)
    out = root / "N8E"
    figs = root / "N8E_figs"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n8e_formal_ablation_with_caveat.py"),
            "--n5b-root",
            str(n5b),
            "--n6b-root",
            str(n6b),
            "--n7c6-root",
            str(n7c6),
            "--n8a2-root",
            str(n8a2),
            "--n8b-root",
            str(n8b),
            "--n8c3-root",
            str(n8c3),
            "--n8d-root",
            str(n8d),
            "--dual-root",
            str(dual),
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
        _fail(proc.stderr[-2600:] or proc.stdout[-2600:])
    return out


def _load(out: Path, name: str) -> dict[str, Any]:
    return json.loads((out / name).read_text(encoding="utf-8"))


def _check(out: Path, check: str) -> None:
    for name in REQUIRED_OUTPUTS:
        if not (out / name).exists():
            _fail(f"missing output: {name}")
    matrix = _load(out, "N8E_FINAL_ENGINEERING_ABLATION_MATRIX.json")
    modules = _load(out, "N8E_MODULE_CONTRIBUTION_SUMMARY_REPORT.json")
    caveats = _load(out, "N8E_CAVEAT_REPORT.json")
    claim = _load(out, "N8E_CLAIM_BOUNDARY_REVIEW_REPORT.json")
    decision = _load(out, "N8E_FORMAL_ABLATION_WITH_CAVEAT_DECISION_REPORT.json")
    figures = _load(out, "N8E_FIGURE_MANIFEST.json")
    if check == "all":
        if not matrix.get("matrix_complete") or matrix.get("row_count") != 22:
            _fail("matrix incomplete")
        if matrix.get("group_counts") != {
            "A_EKF_front_end_modules": 5,
            "B_no_feedback_FGO_modules": 7,
            "C_diagnostic_removals": 5,
            "D_candidate_factors": 5,
        }:
            _fail("unexpected group counts")
        if modules.get("module_count") != 8:
            _fail("module summary incomplete")
        if not caveats.get("all_required_caveats_present"):
            _fail("missing caveats")
        if figures.get("figure_count_total") != 10 or not figures.get("required_figures_nonempty"):
            _fail("figures missing or empty")
        if decision.get("status") != "formal_engineering_ablation_ready_with_caveats":
            _fail(f"unexpected decision: {decision.get('status')}")
    if check in {"all", "claim_boundary"}:
        if claim.get("forbidden_claim_count") != 0 or claim.get("decision") != "pass":
            _fail("claim boundary failed")
    if check in {"all", "no_performance_claim"}:
        if decision.get("paper_performance_claim") or not decision.get("no_outperform_final_v23_claim"):
            _fail("performance/outperform claim detected")
    if check in {"all", "no_trace_finalv23_tuning"}:
        if not matrix.get("no_trace_finalv23_solver_input_or_tuning"):
            _fail("trace/final_v23 tuning or solver input detected")
    if check in {"all", "no_feedback_substitution"}:
        if not matrix.get("no_fgo_feedback") or not matrix.get("no_fgo_output_substitution"):
            _fail("FGO feedback/substitution detected")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        choices=["all", "claim_boundary", "no_performance_claim", "no_trace_finalv23_tuning", "no_feedback_substitution"],
        default="all",
    )
    parser.add_argument("--skip-hygiene", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.skip_hygiene:
        _check_hygiene()
    with tempfile.TemporaryDirectory() as tmp:
        out = _run_n8e(Path(tmp))
        _check(out, args.check)
    print(f"audit_n8e_formal_ablation_with_caveat passed ({args.check})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
