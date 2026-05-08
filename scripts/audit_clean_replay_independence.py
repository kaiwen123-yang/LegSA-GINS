#!/usr/bin/env python3
"""Audit N4H2G2 clean replay independence tooling with toy artifacts.

中文说明：本审计只用 toy 文件验证 hash/stale/fresh-summary/yaw-probe 合同，
不运行外部 KF-GINS，不读取真实 raw data。
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.evaluation.clean_replay_fresh_summary_audit import recompute_clean_summary_from_nav  # noqa: E402
from legsa_gins.evaluation.replay_artifact_hash_audit import compare_artifact_hashes, hash_replay_artifacts  # noqa: E402
from legsa_gins.evaluation.yaw_input_sensitivity_probe import (  # noqa: E402
    classify_yaw_sensitivity,
    create_yaw_shifted_gnss,
)


REQUIRED_FILES = [
    "src/legsa_gins/evaluation/clean_replay_independence_audit.py",
    "src/legsa_gins/evaluation/replay_artifact_hash_audit.py",
    "src/legsa_gins/evaluation/yaw_input_sensitivity_probe.py",
    "src/legsa_gins/evaluation/clean_replay_fresh_summary_audit.py",
    "scripts/experiments/run_clean_replay_independence_audit.py",
    "docs/experiments/clean_replay_independence_audit.md",
    "docs/experiments/yaw_input_sensitivity_probe.md",
    "docs/experiments/n4h2g2_clean_replay_independence_decision.md",
    "docs/codex_prompts/N4H2G2_clean_replay_independence_audit.md",
]


def _write_gnss(path: Path, yaw: float) -> None:
    path.write_text(f"0 40 116 10 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 {yaw} 1.5\n", encoding="utf-8")


def _write_nav(path: Path, yaw: float) -> None:
    path.write_text("0 0 40 116 10 0 0 0 0 0 " + str(yaw) + "\n", encoding="utf-8")


def _assert_boundary(report: dict, name: str) -> None:
    for key in ["trace_solver_input", "output_only_correction", "solver_output_changed", "numerical_performance_claim"]:
        if report.get(key) is not False:
            raise AssertionError(f"{name} {key} must be false")


def _toy_hash_audit(tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    noisy = tmp / "noisy"
    clean = tmp / "clean"
    noisy.mkdir()
    clean.mkdir()
    _write_gnss(noisy / "input.gnss", 10.0)
    _write_gnss(clean / "CLEAN_STATUS_YAW.gnss", 40.0)
    _write_nav(noisy / "KF_GINS_Navresult.nav", 10.0)
    _write_nav(clean / "KF_GINS_Navresult.nav", 10.0)
    (noisy / "summary.json").write_text('{"yaw_rmse_deg": 93.0}\n', encoding="utf-8")
    (clean / "CLEAN_REPLAY_SUMMARY.json").write_text('{"yaw_rmse_deg": 2.0}\n', encoding="utf-8")
    clean_hash = hash_replay_artifacts(clean, "clean")
    noisy_hash = hash_replay_artifacts(noisy, "noisy")
    comparison = compare_artifact_hashes(clean_hash, noisy_hash)
    if comparison["clean_input_differs_from_noisy_input"] is not True:
        raise AssertionError("toy clean/noisy input hash should differ")
    if comparison["clean_nav_differs_from_noisy_nav"] is not False:
        raise AssertionError("toy nav hash should be identical")
    if comparison["possible_yaw_input_ignored_or_output_reused"] is not True:
        raise AssertionError("identical NAV with differing input should flag reused/ignored risk")
    _assert_boundary(comparison, "hash comparison")

    run_start = clean.stat().st_mtime + 1000.0
    stale = compare_artifact_hashes(clean_hash, noisy_hash, clean_run_start_time=run_start)
    if stale["stale_output"] is not True:
        raise AssertionError("stale output should be detected from mtime")


def _toy_fresh_summary(tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    nav = tmp / "fresh.nav"
    nav.write_text("0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n", encoding="utf-8")
    reference = [
        {"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
        {"timestamp": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
    ]
    old = tmp / "CLEAN_REPLAY_SUMMARY.json"
    old.write_text('{"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}\n', encoding="utf-8")
    report = recompute_clean_summary_from_nav(nav, reference, tmp / "fresh_out", old_clean_summary_path=old)
    if report["fresh_summary_computed"] is not True:
        raise AssertionError("fresh summary should be computed")
    if report["old_clean_summary_used_as_input"] is not False:
        raise AssertionError("old summary must not be used as input")
    _assert_boundary(report, "fresh summary")


def _toy_yaw_shift(tmp: Path) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    clean = tmp / "clean.gnss"
    shifted = tmp / "shifted.gnss"
    _write_gnss(clean, 10.0)
    report = create_yaw_shifted_gnss(clean, shifted, yaw_shift_deg=30.0)
    if report["formal_allowed"] is not False:
        raise AssertionError("yaw shift must remain diagnostic only")
    text = shifted.read_text(encoding="utf-8").strip().split()
    if abs(float(text[13]) - 40.0) > 1.0e-9:
        raise AssertionError("yaw column was not shifted")
    if classify_yaw_sensitivity(0.1)["yaw_input_has_low_runtime_effect_or_update_rejected"] is not True:
        raise AssertionError("low NAV yaw diff should classify as low runtime effect")
    if classify_yaw_sensitivity(6.0)["yaw_input_affects_runtime"] is not True:
        raise AssertionError("large NAV yaw diff should classify as runtime affected")
    _assert_boundary(report, "yaw shift")


def audit(root: Path) -> None:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing:
        raise AssertionError(f"missing required files: {missing}")
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        _toy_hash_audit(tmp / "hash")
        _toy_fresh_summary(tmp / "fresh")
        _toy_yaw_shift(tmp / "shift")

    docs = [root / path for path in REQUIRED_FILES if path.startswith("docs/")]
    forbidden = [str(Path("/home") / "kaiwen") + "/", str(Path("/mnt") / "c" / "Users") + "/", "C:" + "\\Users"]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                raise AssertionError(f"tracked doc contains local absolute path: {doc}")


def main() -> int:
    try:
        audit(REPO_ROOT)
    except AssertionError as exc:
        print(f"N4H2G2 clean replay independence audit failed: {exc}")
        return 1
    print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
