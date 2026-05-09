#!/usr/bin/env python3
"""Audit N4H4R3 source-backed port clean replay parity plumbing.

中文说明：审计只使用 toy runtime dirs，验证报告边界旗标；不提交 runtime artifacts。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_port_clean_replay_runner import copy_toy_inputs


TOY_ROOT = Path("/tmp/legsa_n4h4r3_audit_toy")
LOCAL_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4r3_port_clean_parity",
    "/home/kaiwen" + "/legsa_n4h4d",
    "/home/kaiwen" + "/legsa_external_artifacts",
    "/home/kaiwen" + "/legsa_n4h2g_clean_replay",
]
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
)
REPORT_FALSE_FLAGS = [
    "paper_performance_claim",
    "proposed_factor_claim",
    "trace_solver_input",
    "final_v23_output_solver_input",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4R3 port clean replay parity audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _tracked_files() -> list[str]:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _check_files() -> int:
    required = [
        "src/legsa_gins/evaluation/legsa_v23_port_clean_replay_runner.py",
        "src/legsa_gins/evaluation/legsa_v23_port_clean_replay_evaluator.py",
        "src/legsa_gins/evaluation/legsa_v23_port_gap_screen.py",
        "src/legsa_gins/evaluation/legsa_v23_port_parity_decision.py",
        "scripts/experiments/run_legsa_v23_port_clean_replay_parity.py",
        "docs/experiments/n4h4r3_port_clean_replay_parity.md",
        "docs/experiments/n4h4r3_port_gap_screen.md",
        "docs/experiments/n4h4r3_parity_decision.md",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        return _fail("missing required R3 files", missing)
    demo = (ROOT / "cpp/legsa_v23_port_core/src/demo/port_demo.cpp").read_text(encoding="utf-8")
    if "--config" not in demo or "--output-dir" not in demo:
        return _fail("port demo lacks --config/--output-dir")
    return 0


def _write_toy_dual(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(0, 160):
        time = i * 0.01
        lines.append(f"0 {time:.2f} 30.0 120.0 10.0 0 0 0 0 0 5.0\n")
    (root / "KF_GINS_Navresult.nav").write_text("".join(lines), encoding="utf-8")


def _run_toy_pipeline() -> int:
    shutil.rmtree(TOY_ROOT, ignore_errors=True)
    clean = TOY_ROOT / "clean"
    dual = TOY_ROOT / "dual"
    out = TOY_ROOT / "out"
    copy_toy_inputs(clean)
    _write_toy_dual(dual)
    command = [
        "python3",
        "scripts/experiments/run_legsa_v23_port_clean_replay_parity.py",
        "--clean-root",
        str(clean),
        "--dual-root",
        str(dual),
        "--output-dir",
        str(out),
        "--build-dir",
        "build/cpp",
        "--exe",
        "./build/cpp/legsa_v23_port_core_demo",
        "--allow-run",
    ]
    result = _run(command)
    if result.returncode != 0:
        return _fail("toy pipeline failed", [result.stdout, result.stderr])
    for name in [
        "LEGSA_PORT_CLEAN_REPLAY_SUMMARY.json",
        "LEGSA_PORT_CLEAN_REPLAY_REPORT.json",
        "LEGSA_PORT_CLEAN_REPLAY_GAP_SCREEN.json",
        "LEGSA_PORT_CLEAN_REPLAY_DECISION.json",
    ]:
        if not (out / name).exists():
            return _fail("toy report missing", [name])
    decision = json.loads((out / "LEGSA_PORT_CLEAN_REPLAY_DECISION.json").read_text(encoding="utf-8"))
    if decision.get("engineering_backbone_parity_only") is not True:
        return _fail("engineering_backbone_parity_only must be true")
    bad = [flag for flag in REPORT_FALSE_FLAGS if decision.get(flag) is not False]
    if bad:
        return _fail("decision forbidden flags not false", bad)
    return 0


def _check_docs() -> int:
    joined = "\n".join((ROOT / path).read_text(encoding="utf-8", errors="ignore") for path in [
        "docs/experiments/n4h4r3_port_clean_replay_parity.md",
        "docs/experiments/n4h4r3_port_gap_screen.md",
        "docs/experiments/n4h4r3_parity_decision.md",
    ])
    required = [
        "engineering backbone parity",
        "not paper performance",
        "not factor",
        "final_v23 output",
        "trace evaluation-only",
    ]
    missing = [term for term in required if term not in joined]
    if missing:
        return _fail("docs missing required boundary terms", missing)
    return 0


def _check_no_artifacts_or_paths() -> int:
    path_hits: list[str] = []
    artifact_hits: list[str] = []
    for rel in _tracked_files():
        if rel == "reference/final_v23_repo" or rel.startswith("reference/final_v23_repo/"):
            continue
        if ARTIFACT_RE.search(rel):
            artifact_hits.append(rel)
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LOCAL_PATTERNS:
            if pattern in text:
                path_hits.append(f"{rel}: {pattern}")
    if artifact_hits:
        return _fail("tracked runtime/raw artifact detected", artifact_hits)
    if path_hits:
        return _fail("local path leakage detected", path_hits)
    return 0


def main() -> int:
    for check in [_check_files, _check_docs, _run_toy_pipeline, _check_no_artifacts_or_paths]:
        result = check()
        if result:
            return result
    print("N4H4R3 port clean replay parity audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
