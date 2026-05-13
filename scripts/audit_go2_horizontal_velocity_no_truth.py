#!/usr/bin/env python3
"""Audit that N7C does not treat Go2 horizontal velocity as truth.

中文说明：该审计只检查 claim boundary，不使用运行指标反向调参。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_go2_horizontal_velocity_no_truth failed: {message}")


def main() -> int:
    paths = [
        ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_policy.py",
        ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_builder.py",
        ROOT / "src/legsa_gins/go2_prior/go2_horizontal_velocity_activation_runner.py",
        ROOT / "docs/experiments/n7c_go2_horizontal_velocity_weak_prior.md",
        ROOT / "CLAIM_BOUNDARY.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in [
        '"go2_velocity_truth_claim": False',
        "Go2 velocity is not truth",
        "no_outperform_final_v23_claim",
        "paper_performance_claim",
    ]:
        if token not in text:
            _fail(f"missing boundary token: {token}")
    proc = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "Go2 velocity is truth",
            "--",
            ".",
            ":(exclude)scripts/audit_go2_velocity_not_truth.py",
            ":(exclude)scripts/audit_go2_horizontal_velocity_no_truth.py",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode == 0:
        _fail("found forbidden Go2 velocity truth wording")
    print("audit_go2_horizontal_velocity_no_truth passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
