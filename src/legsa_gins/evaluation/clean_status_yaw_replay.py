"""Clean status-yaw no-noise KF-GINS replay helpers for N4H2G.

中文说明：本模块只生成 clean status-yaw baseline replay 输入、调用外部
KF-GINS baseline、并对输出做 evaluation-only 评价；不修改 solver、不调参、
不使用 trace 作为 solver input。
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from legsa_gins.evaluation.fresh_replay_evaluator import _add_gate_booleans
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp, compute_errors, summary_metrics, write_error_series
from legsa_gins.input_generation.process_data_compat import generate_process_data_compat_inputs


DEFAULT_CLEAN_POLICY = {
    "yaw_source_mode": "status",
    "yaw_std_mode": "fixed_1p5",
    "yaw_noise_std_deg": 0.0,
    "outlier_mode": "none",
    "outlier_ratio": 0.0,
    "enable_outage": False,
    "status_yaw_scheme": "A1_dual_diff",
    "trace_yaw_for_solver": False,
    "output_only_correction": False,
    "bad_epoch_deletion_for_metric": False,
}


def _write_json(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _count_rows(path: str | Path) -> int:
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip())


def generate_clean_process_data_input(
    fix_root: str | Path,
    body_imu: str | Path,
    output_dir: str | Path,
    *,
    base_time: float = 1772784000.0,
) -> dict[str, Any]:
    """Generate clean/no-noise process_data-compatible `.gnss` and `.imu` files."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = generate_process_data_compat_inputs(
        fix_root,
        body_imu,
        out / "_generation",
        base_time=base_time,
        yaw_source_mode="status",
        yaw_std_mode="fixed_1p5",
        yaw_noise_std_deg=0.0,
        outlier_mode="none",
        enable_outage=False,
    )
    clean_gnss = out / "CLEAN_STATUS_YAW.gnss"
    clean_imu = out / "CLEAN_STATUS_YAW.imu"
    shutil.copyfile(generated["gnss_path"], clean_gnss)
    shutil.copyfile(generated["imu_path"], clean_imu)

    manifest = {
        "phase": "N4H2G",
        "clean_input_policy": dict(DEFAULT_CLEAN_POLICY),
        "yaw_source_mode": "status",
        "yaw_std_mode": "fixed_1p5",
        "yaw_noise_std_deg": 0.0,
        "outlier_mode": "none",
        "outlier_ratio": 0.0,
        "enable_outage": False,
        "trace_solver_input": False,
        "trace_yaw_for_solver": False,
        "clean_input_claim": "clean_status_yaw_no_synthetic_noise",
        "source_role": "process_data_compat_clean_variant",
        "clean_replay_is_historical_exact_artifact": False,
        "generated_files": {
            "gnss": clean_gnss.name,
            "imu": clean_imu.name,
            "source_generation_report": str(Path(generated["report_path"]).name),
        },
        "gnss_row_count": _count_rows(clean_gnss),
        "imu_row_count": _count_rows(clean_imu),
        "input_generation_report": generated.get("report", {}),
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
    _write_json(out / "CLEAN_INPUT_MANIFEST.json", manifest)
    return {
        "phase": "N4H2G",
        "clean_gnss_path": str(clean_gnss),
        "clean_imu_path": str(clean_imu),
        "manifest_path": str(out / "CLEAN_INPUT_MANIFEST.json"),
        "manifest": manifest,
        "generation": generated,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }


def _format_yaml_value(value: str | float | int) -> str:
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def _write_replay_config(
    *,
    template_config: str | Path,
    gnss: str | Path,
    imu: str | Path,
    replay_output_dir: str | Path,
    config_path: str | Path,
    starttime: float = 66.0,
    endtime: float = 340.0,
    imudatarate: int = 500,
) -> Path:
    """Patch top-level KF-GINS YAML IO/time keys using only standard library text handling."""

    replacements: dict[str, str | float | int] = {
        "imupath": str(Path(imu).resolve()),
        "gnsspath": str(Path(gnss).resolve()),
        "outputpath": str(Path(replay_output_dir).resolve()),
        "gnss_format": 0,
        "imudatalen": 7,
        "imudatarate": int(imudatarate),
        "imudataincremental": 1,
        "imudataformat": 0,
        "starttime": float(starttime),
        "endtime": float(endtime),
    }
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in Path(template_config).read_text(encoding="utf-8").splitlines():
        stripped = raw_line.lstrip()
        if stripped.startswith("#") or ":" not in raw_line:
            lines.append(raw_line)
            continue
        key = raw_line.split(":", 1)[0].strip()
        if key in replacements:
            lines.append(f"{key}: {_format_yaml_value(replacements[key])}")
            seen.add(key)
        else:
            lines.append(raw_line)
    for key, value in replacements.items():
        if key not in seen:
            lines.append(f"{key}: {_format_yaml_value(value)}")
    output = Path(config_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def run_external_kfgins_clean_replay(
    clean_input_dir: str | Path,
    external_source_root: str | Path,
    output_dir: str | Path,
    *,
    allow_build: bool = False,
    allow_run: bool = False,
    timeout_sec: int = 300,
    starttime: float = 66.0,
    endtime: float = 340.0,
    imudatarate: int = 500,
) -> dict[str, Any]:
    """Run external KF-GINS on clean inputs when explicitly allowed."""

    clean_dir = Path(clean_input_dir)
    source_root = Path(external_source_root)
    out = Path(output_dir)
    replay_dir = out / "kfgins_output"
    replay_dir.mkdir(parents=True, exist_ok=True)
    exe = source_root / "bin" / "KF-GINS"
    build_report: dict[str, Any] = {"allow_build": bool(allow_build), "build_attempted": False}
    if allow_build and not exe.exists():
        completed = subprocess.run(
            ["cmake", "--build", str(source_root / "build")],
            cwd=source_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        build_report.update(
            {
                "build_attempted": True,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            }
        )
    elif allow_build:
        build_report["build_skipped_reason"] = "executable_already_exists"

    config_path = out / "kf-gins-n4h2g-clean-replay.yaml"
    _write_replay_config(
        template_config=source_root / "config" / "kf-gins.yaml",
        gnss=clean_dir / "CLEAN_STATUS_YAW.gnss",
        imu=clean_dir / "CLEAN_STATUS_YAW.imu",
        replay_output_dir=replay_dir,
        config_path=config_path,
        starttime=starttime,
        endtime=endtime,
        imudatarate=imudatarate,
    )
    run_report: dict[str, Any] = {
        "phase": "N4H2G",
        "allow_run": bool(allow_run),
        "external_source_role": "EXTERNAL_KFGINS_ROOT",
        "config_path": str(config_path),
        "replay_output_role": "N4H2G_OUTPUT_ROOT/kfgins_output",
        "build_report": build_report,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "numerical_performance_claim": False,
    }
    if not allow_run:
        run_report.update({"replay_status": "not_run_allow_run_false", "completed": False})
        _write_json(out / "CLEAN_REPLAY_RUN_REPORT.json", run_report)
        return run_report
    if not exe.exists():
        run_report.update({"replay_status": "executable_missing", "completed": False})
        _write_json(out / "CLEAN_REPLAY_RUN_REPORT.json", run_report)
        return run_report
    completed = subprocess.run(
        [str(exe), str(config_path)],
        cwd=source_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    inventory = {}
    for name in ["KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt"]:
        path = replay_dir / name
        inventory[name] = {
            "exists": path.exists(),
            "row_count": _count_rows(path) if path.exists() else 0,
            "role": f"N4H2G_OUTPUT_ROOT/kfgins_output/{name}",
        }
    completed_ok = completed.returncode == 0 and all(item["exists"] and item["row_count"] > 0 for item in inventory.values())
    run_report.update(
        {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "output_inventory": inventory,
            "completed": completed_ok,
            "replay_status": "completed" if completed_ok else "failed",
            "nav_path": str(replay_dir / "KF_GINS_Navresult.nav"),
            "std_path": str(replay_dir / "KF_GINS_STD.txt"),
        }
    )
    _write_json(out / "CLEAN_REPLAY_RUN_REPORT.json", run_report)
    return run_report


def evaluate_clean_replay_against_dual_reference(
    clean_nav: str | Path,
    dual_reference: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate clean replay NAV against the selected dual official reference."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    clean_rows = parse_kfgins_nav(clean_nav)
    aligned = align_by_timestamp(clean_rows, dual_reference, max_dt=0.05)
    errors = compute_errors(aligned)
    summary = _add_gate_booleans(summary_metrics(errors))
    summary.update(
        {
            "phase": "N4H2G",
            "aligned_count": summary.get("count"),
            "reference_profile": "selected_dual_official_reference_direct_identity",
            "clean_input_role": "clean_status_yaw_no_synthetic_noise",
        }
    )
    report = {
        "phase": "N4H2G",
        "clean_replay_summary": summary,
        "count": summary.get("count"),
        "clean_nav_count": len(clean_rows),
        "official_reference_count": len(dual_reference),
        "replay_recomputed_under_dual_reference": True,
        "yaw_profile": "direct_identity",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    write_error_series(errors, out / "CLEAN_REPLAY_ERROR_SERIES.csv")
    _write_json(out / "CLEAN_REPLAY_SUMMARY.json", summary)
    _write_json(out / "CLEAN_REPLAY_EVALUATION_REPORT.json", report)
    return report
