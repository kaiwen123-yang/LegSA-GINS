"""Clean replay independence audit for N4H2G2.

中文说明：本模块强制重新生成 clean status-yaw 输入并重跑外部 KF-GINS，
用于排查 cache/stale summary 风险；不修改 solver，不调参，不删 epoch。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import time
from typing import Any

from legsa_gins.evaluation.clean_replay_fresh_summary_audit import recompute_clean_summary_from_nav
from legsa_gins.evaluation.clean_status_yaw_replay import (
    DEFAULT_CLEAN_POLICY,
    generate_clean_process_data_input,
    run_external_kfgins_clean_replay,
)
from legsa_gins.evaluation.error_series_parity import load_official_summary
from legsa_gins.evaluation.official_reference_reconstruction import (
    load_official_error_series,
    load_official_nav,
    select_reference_sign_by_summary,
)


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _load_dual_reference(dual_root: str | Path) -> dict[str, Any]:
    root = Path(dual_root)
    official_summary = load_official_summary(root / "summary.json")
    official_nav = load_official_nav(root / "KF_GINS_Navresult.nav")
    official_errors = load_official_error_series(root / "error_series.csv")
    reconstruction = select_reference_sign_by_summary(official_nav, official_errors, official_summary)
    selected = reconstruction.get("selected_reference_sign")
    reference = (reconstruction.get("reference_candidates") or {}).get(selected, [])
    return {
        "official_summary": official_summary,
        "reference_reconstruction": reconstruction,
        "selected_reference": reference,
        "selected_reference_sign": selected,
    }


def _manifest_valid(manifest: dict[str, Any], clean_policy: dict[str, Any]) -> bool:
    checks = {
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "trace_solver_input": False,
    }
    policy = manifest.get("clean_input_policy") or clean_policy
    for key, expected in checks.items():
        actual = manifest.get(key, policy.get(key))
        if actual != expected:
            return False
    return True


def _outputs_newer(paths: list[Path], run_start_time: float) -> tuple[bool, list[str]]:
    stale: list[str] = []
    for path in paths:
        if not path.exists() or path.stat().st_mtime < run_start_time:
            stale.append(path.name)
    return not stale, stale


def force_clean_replay_rerun(
    fix_root: str | Path,
    body_imu: str | Path,
    external_source_root: str | Path,
    output_root: str | Path,
    dual_root: str | Path,
    *,
    clean_policy: dict[str, Any] | None = None,
    base_time: float = 1772784000.0,
    allow_build: bool = False,
    allow_run: bool = False,
) -> dict[str, Any]:
    """Run a fresh clean replay in `output_root/rerun_clean` and audit freshness."""

    policy = dict(clean_policy or DEFAULT_CLEAN_POLICY)
    out = Path(output_root)
    rerun_dir = out / "rerun_clean"
    if rerun_dir.exists():
        shutil.rmtree(rerun_dir)
    rerun_dir.mkdir(parents=True, exist_ok=True)

    generation = generate_clean_process_data_input(fix_root, body_imu, rerun_dir, base_time=base_time)
    manifest = generation["manifest"]
    manifest_valid = _manifest_valid(manifest, policy)

    run_start_time = time.time()
    run_report = run_external_kfgins_clean_replay(
        rerun_dir,
        external_source_root,
        rerun_dir,
        allow_build=allow_build,
        allow_run=allow_run,
    )
    run_end_time = time.time()

    nav_path = rerun_dir / "kfgins_output" / "KF_GINS_Navresult.nav"
    std_path = rerun_dir / "kfgins_output" / "KF_GINS_STD.txt"
    imu_err_path = rerun_dir / "kfgins_output" / "KF_GINS_IMU_ERR.txt"
    output_newer, stale_files = _outputs_newer([nav_path, std_path, imu_err_path], run_start_time)

    reference_bundle = _load_dual_reference(dual_root)
    fresh_summary_audit: dict[str, Any]
    if run_report.get("completed") and reference_bundle["selected_reference"]:
        fresh_summary_audit = recompute_clean_summary_from_nav(
            nav_path,
            reference_bundle["selected_reference"],
            rerun_dir,
            old_clean_summary_path=None,
        )
    else:
        fresh_summary_audit = {
            "fresh_summary_computed": False,
            "fresh_summary": {},
            "evidence_status": "replay_not_completed",
            "old_clean_summary_used_as_input": False,
            "trace_solver_input": False,
            "output_only_correction": False,
            "solver_output_changed": False,
            "bad_epoch_deletion_for_metric": False,
            "numerical_performance_claim": False,
        }

    report = {
        "phase": "N4H2G2",
        "independent_rerun_completed": bool(run_report.get("completed")),
        "clean_input_manifest_valid": manifest_valid,
        "clean_output_files_newer_than_run_start": bool(output_newer),
        "stale_output_files": stale_files,
        "clean_output_dir_unique": True,
        "old_summary_used": False,
        "run_start_time": run_start_time,
        "run_end_time": run_end_time,
        "clean_policy": policy,
        "clean_input_manifest": manifest,
        "clean_generation_report": {
            "gnss_row_count": manifest.get("gnss_row_count"),
            "imu_row_count": manifest.get("imu_row_count"),
        },
        "clean_replay_run_report": run_report,
        "official_reference_reconstruction": {
            "selected_reference_sign": reference_bundle.get("selected_reference_sign"),
            "actual_dual_summary_reproduced": reference_bundle["reference_reconstruction"].get("actual_dual_summary_reproduced"),
            "summary_diff": reference_bundle["reference_reconstruction"].get("summary_diff"),
        },
        "fresh_summary_audit": fresh_summary_audit,
        "rerun_output_role": "N4H2G2_OUTPUT_ROOT/rerun_clean",
        "solver_output_changed": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "CLEAN_REPLAY_INDEPENDENCE_REPORT.json", report)
    return report | {
        "rerun_dir": str(rerun_dir),
        "nav_path": str(nav_path),
        "selected_reference": reference_bundle["selected_reference"],
    }
