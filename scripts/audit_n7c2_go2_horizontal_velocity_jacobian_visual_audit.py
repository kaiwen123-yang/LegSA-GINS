#!/usr/bin/env python3
"""Audit N7C2 Go2 horizontal velocity Jacobian and visual readability flow.

中文说明：该审计只跑 synthetic runtime 链路，验证 N7C2 输出和边界，不碰 solver。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_n7c1_go2_horizontal_velocity_visual_validation import _prepare_n7c_runtime


REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_n7c_visual_overlap_audit.py",
    "src/legsa_gins/go2_prior/go2_n7c_visual_readability_plots.py",
    "src/legsa_gins/go2_prior/go2_factor_jacobian_contract.py",
    "src/legsa_gins/go2_prior/go2_n7c2_decision.py",
    "scripts/experiments/run_n7c2_go2_horizontal_velocity_jacobian_visual_audit.py",
    "scripts/audit_factor_jacobian_contracts.py",
    "scripts/audit_n7c_visual_overlap_explained.py",
    "docs/experiments/n7c2_go2_horizontal_velocity_visual_readability.md",
    "docs/experiments/n7c2_factor_jacobian_contract.md",
    "docs/experiments/n7c2_decision.md",
    "docs/codex_prompts/N7C2_go2_horizontal_velocity_jacobian_visual_audit.md",
]

REQUIRED_OUTPUTS = [
    "N7C2_VISUAL_OVERLAP_AUDIT_REPORT.json",
    "N7C2_FACTOR_JACOBIAN_CONTRACT_REPORT.json",
    "N7C2_JACOBIAN_VISUAL_DECISION_REPORT.json",
    "N7C2_FIGURE_MANIFEST.json",
    "n7c2_jacobian_visual_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_HORIZONTAL_VELOCITY_PRIORS|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c2_go2_horizontal_velocity_jacobian_visual_audit failed: {message}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for token in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")


def _check_no_forbidden_tracked_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden runtime/figure artifact tracked: " + ", ".join(hits[:8]))


def _patch_matrix_with_raw_path(n7c: Path, n5b: Path) -> None:
    matrix_path = n7c / "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    raw_path = str(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    rows = matrix.get("matrix") or [{"variant_id": "toy"}]
    for row in rows:
        row["raw_doppler_factor_path"] = raw_path
    matrix["matrix"] = rows
    matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_n7c1_reports(n7c1: Path) -> None:
    n7c1.mkdir(parents=True, exist_ok=True)
    for name in [
        "N7C1_PLOT_DATA_COVERAGE_REPORT.json",
        "N7C1_FIGURE_MANIFEST.json",
        "N7C1_VISUAL_SANITY_REPORT.json",
    ]:
        (n7c1 / name).write_text(
            json.dumps({"stage": "N7C1_toy", "required_figures_nonempty": True, "visual_sanity_passed": True}, indent=2) + "\n",
            encoding="utf-8",
        )


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c2_visual_jacobian_") as tmp_value:
        tmp = Path(tmp_value)
        n7c, _n7b5, n5b, _n6b, _dual = _prepare_n7c_runtime(tmp)
        _patch_matrix_with_raw_path(n7c, n5b)
        n7c1 = tmp / "n7c1"
        _prepare_n7c1_reports(n7c1)
        out = tmp / "out"
        figs = tmp / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c2_go2_horizontal_velocity_jacobian_visual_audit.py"),
            "--n7c-root",
            str(n7c),
            "--n7c1-root",
            str(n7c1),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--allow-run",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            _fail(proc.stderr[-3000:] or proc.stdout[-3000:])
        for item in REQUIRED_OUTPUTS:
            if not (out / item).exists():
                _fail(f"missing output {item}")
        overlap = json.loads((out / "N7C2_VISUAL_OVERLAP_AUDIT_REPORT.json").read_text(encoding="utf-8"))
        figures = json.loads((out / "N7C2_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        jacobian = json.loads((out / "N7C2_FACTOR_JACOBIAN_CONTRACT_REPORT.json").read_text(encoding="utf-8"))
        decision = json.loads((out / "N7C2_JACOBIAN_VISUAL_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if not overlap.get("summary", {}).get("all_overlaps_explained"):
            _fail("overlap explanations missing")
        if figures.get("figure_count_total") != 10 or not figures.get("required_figures_nonempty"):
            _fail("readability figures missing or empty")
        if not jacobian.get("go2_horizontal_touches_only_horizontal_velocity"):
            _fail("Go2 horizontal Jacobian touched forbidden blocks")
        if not jacobian.get("go2_horizontal_vertical_derivative_zero"):
            _fail("Go2 horizontal vertical derivative is not zero")
        if jacobian.get("toy_finite_difference_status") != "toy_passed":
            _fail("toy finite-difference check failed")
        if decision.get("status") != "ready_to_merge_N7C_and_start_N8A":
            _fail(f"unexpected decision {decision.get('status')}")


def main() -> int:
    for item in REQUIRED_FILES:
        if not (ROOT / item).exists():
            _fail(f"missing file {item}")
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c2_go2_horizontal_velocity_jacobian_visual_audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
