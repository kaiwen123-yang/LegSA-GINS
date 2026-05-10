#!/usr/bin/env python3
"""Audit N5A raw Doppler factor activation path.

中文说明：检查 N5A 因子文件、默认关闭、toy update、路径泄漏和 raw 数据提交边界。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOY_DIR = Path("/tmp/legsa_n5a_raw_doppler_audit_toy")
EXE = ROOT / "build/cpp/legsa_v23_port_core_demo"


RAW_GNSS_MODULES = [
    "src/legsa_gins/raw_gnss/rtklib_discovery.py",
    "src/legsa_gins/raw_gnss/ephemeris_discovery.py",
    "src/legsa_gins/raw_gnss/rtklib_command_runner.py",
    "src/legsa_gins/raw_gnss/rtklib_doppler_provider.py",
    "src/legsa_gins/raw_gnss/ubx_raw_message_scanner.py",
    "src/legsa_gins/raw_gnss/ubx_raw_binary_rebuilder.py",
    "src/legsa_gins/raw_gnss/ubx_rawx_parser.py",
    "src/legsa_gins/raw_gnss/doppler_velocity_ls.py",
]
CXX_FILES = [
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/raw_doppler_types.hpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/raw_doppler_factor.hpp",
    "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/raw_doppler_factor_loader.hpp",
    "cpp/legsa_v23_port_core/src/factors/raw_doppler_factor_loader.cpp",
    "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/satellite_state_provider.hpp",
    "cpp/legsa_v23_port_core/src/factors/satellite_state_provider.cpp",
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


def _tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=True)
    return result.stdout.splitlines()


def _git_grep(token: str) -> str:
    result = subprocess.run(
        ["git", "grep", "-n", token, "--", "."],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout


def run_cpp_toy() -> dict:
    if not EXE.exists():
        raise AssertionError(f"C++ demo missing; run cmake build first: {EXE}")
    TOY_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(EXE), "--dry-run-raw-doppler-toy", "--output-dir", str(TOY_DIR)],
        cwd=ROOT,
        check=True,
    )
    manifest = json.loads((TOY_DIR / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    toy_trial = {
        "solver_enabled": True,
        "raw_doppler_update_count": manifest.get("raw_doppler_update_count", 0),
        "blocking_issue": "none",
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
    (TOY_DIR / "N5A_RAW_DOPPLER_FACTOR_TRIAL_REPORT.json").write_text(
        json.dumps(toy_trial, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def audit_repository(*, run_toy: bool = True) -> dict:
    for path in RAW_GNSS_MODULES + CXX_FILES:
        if not (ROOT / path).exists():
            raise AssertionError(f"missing N5A file: {path}")
    options = (ROOT / "cpp/legsa_v23_port_core/include/legsa_v23_port_core/factors/raw_doppler_types.hpp").read_text(
        encoding="utf-8"
    )
    if "bool enable_raw_doppler = false" not in options:
        raise AssertionError("raw Doppler must be disabled by default")
    tracked = _tracked_files()
    leaked_artifacts = [path for path in tracked if any(token in path for token in FORBIDDEN_TRACKED)]
    if leaked_artifacts:
        raise AssertionError(f"raw/generated artifacts are tracked: {leaked_artifacts[:10]}")
    for token in LOCAL_PATH_TOKENS:
        matches = _git_grep(token)
        if matches:
            raise AssertionError(f"local path leak for {token}: {matches[:500]}")
    manifest: dict = {}
    if run_toy:
        manifest = run_cpp_toy()
        if not manifest.get("raw_doppler_factor_code_present"):
            raise AssertionError("toy manifest missing raw_doppler_factor_code_present=true")
        if not manifest.get("raw_doppler_toy_factor_applied"):
            raise AssertionError("toy manifest missing raw_doppler_toy_factor_applied=true")
        if manifest.get("raw_doppler_update_count", 0) <= 0:
            raise AssertionError("toy raw_doppler_update_count must be > 0")
        if manifest.get("final_v23_output_solver_input") or manifest.get("trace_solver_input"):
            raise AssertionError("toy manifest leaked final_v23/trace solver input")
    return manifest


def main() -> int:
    audit_repository(run_toy=True)
    print("N5A raw Doppler factor activation audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
