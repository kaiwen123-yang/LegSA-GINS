#!/usr/bin/env python3
"""Audit that N7A Go2 weak prior is not framed as truth.

中文说明：Go2 body-state position/velocity/rpy 均不是 global truth；N7A 不用
trace/final_v23 output 构造 prior，不做 paper claim。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_weak_prior_not_truth failed: {message}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def main() -> int:
    doc_paths = [
        ROOT / "docs/experiments/n7a_go2_body_state_weak_prior.md",
        ROOT / "docs/experiments/n7a_go2_source_contract.md",
        ROOT / "docs/experiments/n7a_go2_attitude_prior_model.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in doc_paths if path.exists())
    required = [
        "Go2 body-state is not truth",
        "Go2 position and velocity priors are disabled by default in N7A",
        "Go2 yaw prior is disabled in N7A",
        "No trace/final_v23 output is used for Go2 prior construction",
        "No paper performance claim",
    ]
    for token in required:
        if token not in text:
            _fail(f"required boundary text missing: {token}")
    code = (
        (ROOT / "src/legsa_gins/go2_state/go2_weak_prior_builder.py").read_text(encoding="utf-8")
        + (ROOT / "scripts/experiments/run_n7a_go2_body_state_weak_prior.py").read_text(encoding="utf-8")
        + (ROOT / "cpp/legsa_v23_port_core/src/fileio/file_saver.cpp").read_text(encoding="utf-8")
    )
    for token in [
        '"position_prior_enabled": False',
        '"velocity_prior_enabled": False',
        '"yaw_prior_enabled": False',
        '"trace_solver_input": False',
        '"final_v23_output_solver_input": False',
        '"paper_performance_claim": False',
        '"output_only_correction": False',
    ]:
        if token not in code:
            _fail(f"boundary token missing in code: {token}")
    grep = _run(["git", "grep", "-n", "Go2 position as truth", "--", "."])
    if grep.returncode == 0:
        _fail("forbidden truth wording found")
    print("audit_go2_weak_prior_not_truth passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
