#!/usr/bin/env python3
"""Audit N4H4R3A update timeline and overlap parity tooling.

中文说明：审计模块、文档、C++ debug flags 和 toy timeline run；只检查边界，
不提交 runtime artifacts。
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


TOY = Path("/tmp/legsa_n4h4r3a_timeline_audit")
LOCAL_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4r3a_update_timeline",
    "/home/kaiwen" + "/legsa_n4h4r3_port_clean_parity",
    "/home/kaiwen" + "/legsa_n4h2g_clean_replay",
    "/home/kaiwen" + "/legsa_external_artifacts",
]
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
)
FALSE_FLAGS = [
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
    print(f"N4H4R3A update timeline audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _write_toy_dual(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(160):
        time = i * 0.01
        lines.append(f"0 {time:.2f} 30.0 120.0 10.0 0 0 0 0 0 5.0\n")
    (root / "KF_GINS_Navresult.nav").write_text("".join(lines), encoding="utf-8")


def _check_files() -> int:
    required = [
        "src/legsa_gins/evaluation/legsa_v23_port_update_timeline.py",
        "src/legsa_gins/evaluation/legsa_v23_port_overlap_expectation.py",
        "src/legsa_gins/evaluation/legsa_v23_port_config_parity.py",
        "src/legsa_gins/evaluation/legsa_v23_port_runtime_loop_fix_decision.py",
        "scripts/experiments/run_legsa_v23_port_update_timeline_audit.py",
        "docs/experiments/n4h4r3a_update_timeline_audit.md",
        "docs/experiments/n4h4r3a_config_overlap_parity.md",
        "docs/experiments/n4h4r3a_runtime_loop_fix_decision.md",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        return _fail("missing required files", missing)
    demo = (ROOT / "cpp/legsa_v23_port_core/src/demo/port_demo.cpp").read_text(encoding="utf-8")
    for flag in ["--debug-update-timeline", "--debug-output-dir", "--debug-max-rows"]:
        if flag not in demo:
            return _fail("missing C++ debug flag", [flag])
    return 0


def _run_toy() -> int:
    shutil.rmtree(TOY, ignore_errors=True)
    clean = TOY / "clean"
    dual = TOY / "dual"
    r3 = TOY / "r3"
    out = TOY / "out"
    copy_toy_inputs(clean)
    _write_toy_dual(dual)
    r3.mkdir(parents=True)
    command = [
        "python3",
        "scripts/experiments/run_legsa_v23_port_update_timeline_audit.py",
        "--clean-root",
        str(clean),
        "--dual-root",
        str(dual),
        "--r3-root",
        str(r3),
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
        return _fail("toy timeline run failed", [result.stdout, result.stderr])
    for name in [
        "PORT_INPUT_TIMELINE_SNAPSHOT.json",
        "PORT_OVERLAP_EXPECTATION_REPORT.json",
        "PORT_RUNTIME_LOOP_TRACE_REPORT.json",
        "PORT_CLEAN_CONFIG_PARITY_REPORT.json",
        "PORT_RUNTIME_LOOP_FIX_DECISION_REPORT.json",
    ]:
        if not (out / name).exists():
            return _fail("toy report missing", [name])
    decision = json.loads((out / "PORT_RUNTIME_LOOP_FIX_DECISION_REPORT.json").read_text(encoding="utf-8"))
    bad = [flag for flag in FALSE_FLAGS if decision.get(flag) is not False]
    if bad:
        return _fail("decision forbidden flags not false", bad)
    return 0


def _check_docs() -> int:
    joined = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for rel in [
            "docs/experiments/n4h4r3a_update_timeline_audit.md",
            "docs/experiments/n4h4r3a_config_overlap_parity.md",
            "docs/experiments/n4h4r3a_runtime_loop_fix_decision.md",
        ]
    )
    for term in ["overlap", "no performance claim", "no output-only correction", "source-backed"]:
        if term not in joined:
            return _fail("docs missing boundary term", [term])
    return 0


def _tracked_files() -> list[str]:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [line for line in result.stdout.splitlines() if line.strip()]


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
        return _fail("tracked artifact detected", artifact_hits)
    if path_hits:
        return _fail("local path leakage detected", path_hits)
    return 0


def main() -> int:
    for check in [_check_files, _check_docs, _run_toy, _check_no_artifacts_or_paths]:
        result = check()
        if result:
            return result
    print("N4H4R3A update timeline audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
