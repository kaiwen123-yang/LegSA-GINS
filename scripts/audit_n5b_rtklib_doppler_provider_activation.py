#!/usr/bin/env python3
"""Audit N5B RTKLIB Doppler provider activation path.

中文说明：检查 N5B provider 模块、文档、toy factor 构建、raw 数据提交边界和本机
路径泄漏；不运行真实数据，也不声明性能。
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.raw_gnss.raw_doppler_velocity_factor_builder import build_factor_file_from_provider


MODULES = [
    "src/legsa_gins/raw_gnss/rtklib_doppler_helper_builder.py",
    "src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py",
    "src/legsa_gins/raw_gnss/rtklib_solution_velocity_parser.py",
    "src/legsa_gins/raw_gnss/raw_doppler_velocity_factor_builder.py",
    "src/legsa_gins/raw_gnss/raw_doppler_activation_evaluator.py",
    "src/legsa_gins/raw_gnss/raw_doppler_n5b_decision.py",
    "scripts/experiments/run_n5b_rtklib_doppler_provider_activation.py",
]
DOCS = [
    "docs/experiments/n5b_rtklib_doppler_velocity_provider.md",
    "docs/experiments/n5b_rtklib_helper_build.md",
    "docs/experiments/n5b_raw_doppler_factor_activation_trial.md",
    "docs/experiments/n5b_raw_doppler_blocker_or_activation_decision.md",
    "docs/experiments/n5b_next_stage_plan.md",
    "docs/codex_prompts/N5B_rtklib_doppler_provider_activation.md",
]
FORBIDDEN_TRACKED = (
    "gnss1-raw.csv",
    "gnss2-raw.csv",
    "corr-raw.csv",
    ".ubx",
    ".obs",
    ".nav",
    ".sp3",
    ".clk",
    "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    ".png",
    ".pdf",
    ".jpg",
    ".jpeg",
)
LOCAL_PATH_TOKENS = (
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\\\Users",
    "/home/kaiwen" + "/legsa_n4h4",
    "/home/kaiwen" + "/legsa_external_artifacts",
)


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout.splitlines()


def _audit_toy_factor() -> None:
    tmp = Path("/tmp/legsa_n5b_provider_audit_toy")
    tmp.mkdir(parents=True, exist_ok=True)
    provider_csv = tmp / "provider.csv"
    with provider_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time",
                "vn",
                "ve",
                "vd",
                "std_vn",
                "std_ve",
                "std_vd",
                "sat_count",
                "doppler_obs_count",
                "gdop_like",
                "provider_status",
                "source_epoch_time",
                "quality_flag",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "time": "1.0",
                "vn": "0.1",
                "ve": "0.0",
                "vd": "0.0",
                "std_vn": "0.2",
                "std_ve": "0.2",
                "std_vd": "0.2",
                "sat_count": "8",
                "doppler_obs_count": "8",
                "gdop_like": "0.5",
                "provider_status": "available",
                "source_epoch_time": "1.0",
                "quality_flag": "toy",
            }
        )
    report = build_factor_file_from_provider(provider_csv, tmp)
    if not report.get("factor_csv_generated"):
        raise AssertionError(f"toy provider factor did not generate: {report}")


def audit_repository() -> None:
    for path in MODULES + DOCS:
        if not (ROOT / path).exists():
            raise AssertionError(f"missing N5B file: {path}")
    _audit_toy_factor()
    tracked = _git_lines(["git", "ls-files"])
    leaked_artifacts = [path for path in tracked if any(token in path for token in FORBIDDEN_TRACKED)]
    if leaked_artifacts:
        raise AssertionError(f"raw/generated artifacts are tracked: {leaked_artifacts[:10]}")
    for token in LOCAL_PATH_TOKENS:
        matches = _git_lines(["git", "grep", "-n", token, "--", "."])
        if matches:
            raise AssertionError(f"local path leak for {token}: {matches[:5]}")


def main() -> int:
    audit_repository()
    print("N5B RTKLIB Doppler provider activation audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
