"""Runtime runner for PAPER10B2 multi-state quality management closure.

The script is intentionally path-parameterized. It creates runtime-only configs,
solver outputs, evaluations, checkpoints, and summary tables under a caller
provided stage root. It does not modify raw data and does not use trace or
external baseline outputs as solver input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.reporting.by2_n9b1f_real_legsa_algorithm_runner import (  # noqa: E402
    _convert_eval_nav,
    _convert_std,
    _metrics_from_summary,
)


QM_MODES = [
    "QM00_OFF",
    "QM01_STATE_TRACE_ONLY",
    "QM02_DOWNWEIGHT_REJECT",
    "QM03_HOLD_RECOVERY",
    "QM04_FULL",
]

SOURCE_KEYS = [
    "receiver_position",
    "receiver_velocity",
    "dual_antenna_yaw",
    "raw_doppler_velocity",
    "go2_attitude_roll_pitch",
    "go2_horizontal_velocity",
]

RUNTIME_PATH_ALIASES: list[tuple[str, str]] = []

QM_PARAM_DEFAULTS: dict[str, Any] = {
    "qm_downweight_threshold": 4.0,
    "qm_reject_threshold": 12.0,
    "qm_hold_enter_count": 3,
    "qm_hold_length": 5,
    "qm_recovery_count": 3,
    "qm_fallback_enter_count": 2,
    "qm_fallback_exit_count": 3,
    "qm_fallback_max_duration": 10,
    "qm_timestamp_gap_hold_sec": 0.25,
    "qm_invalid_hold_enter_count": 2,
    "qm_source_cap": 25.0,
    "qm_global_cap": 25.0,
    "qm_go2_readiness_low_health": 0.35,
    "qm_min_stable_epochs": 3,
    "qm_go2_motion_state_influence": True,
    "qm_readiness_influence": True,
}


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    trace: Path
    base_time: float
    yaw_metric_status: str
    attitude_prior: Path
    velocity_prior: Path
    readiness_metadata: Path


@dataclass(frozen=True)
class RunCase:
    dataset: str
    case_id: str
    family: str
    seed: str
    template_config: Path
    provider_config: Path | None = None
    provider_gnss15: Path | None = None


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gb_free(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024**3)


def space_snapshot(e_probe: Path, wsl_probe: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "timestamp_unix": time.time(),
        "wsl_probe": str(wsl_probe),
        "wsl_free_gb": gb_free(wsl_probe),
        "e_probe": str(e_probe),
        "e_free_gb": "",
    }
    if e_probe.exists():
        row["e_free_gb"] = gb_free(e_probe)
    return row


def hard_stop_triggered(row: dict[str, Any], e_hard_stop_gb: float, wsl_hard_stop_gb: float) -> str:
    if row.get("wsl_free_gb", 0.0) <= wsl_hard_stop_gb:
        return "WSL_ROOT_HARD_STOP"
    e_free = row.get("e_free_gb", "")
    if e_free != "" and float(e_free) <= e_hard_stop_gb:
        return "E_DRIVE_HARD_STOP"
    return ""


def quote_yaml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if text.startswith("[") and text.endswith("]"):
        return text
    return json.dumps(text, ensure_ascii=False)


def update_flat_yaml_text(text: str, overrides: dict[str, Any]) -> str:
    out: list[str] = []
    key_re = re.compile(r"^([A-Za-z0-9_]+)\s*:")
    for line in text.splitlines():
        match = key_re.match(line)
        if match and match.group(1) in overrides:
            key = match.group(1)
            out.append(f"{key}: {quote_yaml(overrides[key])}")
        else:
            out.append(line)
    out.append("")
    out.append("# PAPER10B2 final multi-state quality management overrides. Last key wins.")
    for key, value in overrides.items():
        out.append(f"{key}: {quote_yaml(value)}")
    return "\n".join(out) + "\n"


def parse_simple_yaml_value(path: Path, key: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$")
    found = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            value = match.group(1).strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            found = value
    return found


def parse_float_yaml_value(path: Path, key: str, fallback: float) -> float:
    value = parse_simple_yaml_value(path, key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def resolve_runtime_path_alias(value: str) -> str:
    if not value:
        return value
    path = Path(value)
    if path.exists():
        return value
    for old, new in RUNTIME_PATH_ALIASES:
        if value.startswith(old):
            candidate = Path(new + value[len(old):])
            if candidate.exists():
                return str(candidate)
    return value


def parse_runtime_path_aliases(values: list[str]) -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    for item in values:
        if "=" not in item:
            raise ValueError(f"runtime path alias must be OLD=NEW, got {item!r}")
        old, new = item.split("=", 1)
        old = old.rstrip("/")
        new = new.rstrip("/")
        if not old or not new:
            raise ValueError(f"runtime path alias must have non-empty OLD and NEW, got {item!r}")
        aliases.append((old, new))
    return aliases


def family_from_case(case_id: str) -> str:
    if case_id in {"B0_normal_repeat_formal", "BY3_normal_000", "FULL_normal_repeat"} or "normal" in case_id:
        return "normal"
    if case_id.startswith("A_") or "_A_outage_" in case_id or "outage" in case_id:
        return "outage"
    if case_id.startswith("B_") or "downsample" in case_id:
        return "downsample"
    if case_id.startswith("C_") or "position_noise" in case_id:
        return "position_noise"
    if case_id.startswith("D_") or "position_spike" in case_id:
        return "position_spike"
    if "E_position_std" in case_id:
        return "position_std"
    if "E_yaw_std" in case_id:
        return "yaw_std"
    if case_id.startswith("H_") or "dual_yaw_noise" in case_id:
        return "yaw_noise"
    if case_id.startswith("M_") or "mixed" in case_id:
        return "mixed"
    return "unknown"


def canonical_case_id(row: dict[str, str]) -> tuple[str, str]:
    case_id = row["case_id"]
    seed_raw = row.get("seed", "")
    if seed_raw in {"", "nan", "NaN"}:
        return case_id, ""
    try:
        seed = str(int(float(seed_raw)))
    except ValueError:
        seed = seed_raw
    return case_id, seed


def build_by2_case_map(manifest_path: Path, by2_config_roots: list[Path]) -> list[RunCase]:
    paths: list[Path] = []
    for root in by2_config_roots:
        if root.exists():
            paths.extend(root.glob("**/source_aware_EKF.runtime_config.yaml"))
    cases: list[RunCase] = []
    missing: list[str] = []
    for row in read_csv_dicts(manifest_path):
        case_id, seed = canonical_case_id(row)
        candidates = []
        for path in paths:
            parts = set(path.parts)
            if case_id not in parts:
                continue
            if seed and f"seed_{seed}" not in parts:
                continue
            candidates.append(path)
        if not candidates:
            missing.append(f"{case_id}:{seed}")
            continue
        cases.append(
            RunCase(
                dataset="BY2",
                case_id=case_id,
                family=row.get("family") or family_from_case(case_id),
                seed=seed,
                template_config=sorted(candidates)[0],
            )
        )
    if missing:
        raise RuntimeError("missing BY2 source-aware configs: " + ", ".join(missing[:20]))
    return cases


def build_by3_case_map(by3_sa04_root: Path, by3_provider_root: Path) -> list[RunCase]:
    templates = sorted(by3_sa04_root.glob("*/config/runtime_config.yaml"))
    cases: list[RunCase] = []
    missing: list[str] = []
    for template in templates:
        case_id = template.parent.parent.name
        provider = by3_provider_root / "06_KF_GINS_source_exact_BY3_120_smoke_full" / "runs" / case_id / "config.yaml"
        gnss15 = by3_provider_root / "04_BY3_degradation_input_generation" / "cases" / case_id / "final_v23_15col_input.csv"
        if not provider.exists():
            missing.append(case_id)
            continue
        if not gnss15.exists():
            missing.append(f"{case_id}:final_v23_15col_input.csv")
            continue
        cases.append(
            RunCase(
                dataset="BY3",
                case_id=case_id,
                family=family_from_case(case_id),
                seed=seed_from_case(case_id),
                template_config=template,
                provider_config=provider,
                provider_gnss15=gnss15,
            )
        )
    if missing:
        raise RuntimeError("missing BY3 provider configs: " + ", ".join(missing[:20]))
    return cases


def seed_from_case(case_id: str) -> str:
    match = re.search(r"_(\d{3})$", case_id)
    if match:
        return str(int(match.group(1)))
    match = re.search(r"_seed(\d+)$", case_id)
    if match:
        return match.group(1)
    return ""


def run_key(case: RunCase) -> str:
    if case.seed:
        return f"{case.case_id}__seed_{case.seed}"
    return case.case_id


def generate_readiness_metadata(velocity_prior: Path, output: Path, dataset: str) -> dict[str, Any]:
    rows = read_csv_dicts(velocity_prior)
    out_rows: list[dict[str, Any]] = []
    last_time: float | None = None
    last_speed: float | None = None
    for row in rows:
        try:
            t = float(row.get("time", "nan"))
            vn = float(row.get("vn", "nan"))
            ve = float(row.get("ve", "nan"))
        except ValueError:
            continue
        if not math.isfinite(t) or not math.isfinite(vn) or not math.isfinite(ve):
            continue
        speed = math.hypot(vn, ve)
        gap = 0.0 if last_time is None else max(0.0, t - last_time)
        accel = 0.0
        if last_time is not None and gap > 1.0e-6 and last_speed is not None:
            accel = abs(speed - last_speed) / gap
        update_flag = str(row.get("update_flag", "true")).lower() in {"true", "1", "yes"}
        valid = update_flag and gap <= 0.25
        stance_stable = valid and speed < 0.03
        impact_or_rough = (not valid) or accel > 3.0
        in_place_turn = False
        if impact_or_rough:
            motion_state = "impact_or_rough"
        elif stance_stable:
            motion_state = "stance_stable"
        else:
            motion_state = "normal_motion"
        readiness_score = 0.2 if impact_or_rough else (0.8 if stance_stable else 0.95)
        readiness_low = readiness_score < 0.35 or not valid
        out_rows.append(
            {
                "time": f"{t:.9f}",
                "source_status": "active" if valid else "degraded_or_gap",
                "source_valid": valid,
                "motion_state": motion_state,
                "contact_label": row.get("contact_label", "not_used_as_truth") or "not_used_as_truth",
                "readiness_score": f"{readiness_score:.3f}",
                "readiness_flag": not readiness_low,
                "stance_stable": stance_stable,
                "in_place_turn": in_place_turn,
                "impact_or_rough": impact_or_rough,
                "readiness_low": readiness_low,
                "reason_code": "timestamp_gap_or_speed_jump" if impact_or_rough else "engineering_go2_velocity_metadata",
                "dataset": dataset,
                "trace_used_online": False,
                "go2_position_as_truth": False,
                "go2_yaw_as_truth": False,
            }
        )
        last_time = t
        last_speed = speed
    write_csv(output, out_rows)
    return {
        "dataset": dataset,
        "source": str(velocity_prior),
        "output": str(output),
        "rows": len(out_rows),
        "impact_or_rough_rows": sum(str(r["impact_or_rough"]).lower() == "true" for r in out_rows),
        "readiness_low_rows": sum(str(r["readiness_low"]).lower() == "true" for r in out_rows),
        "trace_used_online": False,
        "go2_position_as_truth": False,
        "go2_yaw_as_truth": False,
    }


def time_align_prior_to_solver_axis(src: Path, output: Path, target_starttime: float, dataset: str) -> dict[str, Any]:
    rows = read_csv_dicts(src)
    first_time = ""
    first_finite: float | None = None
    for row in rows:
        try:
            value = float(row.get("time", "nan"))
        except ValueError:
            continue
        if math.isfinite(value):
            first_finite = value
            first_time = f"{value:.9f}"
            break
    shift = 0.0
    if first_finite is not None and abs(first_finite - target_starttime) > 1000.0:
        shift = first_finite - target_starttime
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        new_row = dict(row)
        if shift:
            try:
                t = float(new_row.get("time", "nan"))
                if math.isfinite(t):
                    new_row["time"] = f"{t - shift:.9f}"
            except ValueError:
                pass
        out_rows.append(new_row)
    output.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        write_csv(output, out_rows, fieldnames=list(rows[0].keys()))
    else:
        write_csv(output, out_rows)
    first_after = ""
    if out_rows:
        first_after = str(out_rows[0].get("time", ""))
    return {
        "dataset": dataset,
        "source": str(src),
        "output": str(output),
        "rows": len(out_rows),
        "target_starttime": f"{target_starttime:.9f}",
        "first_time_before": first_time,
        "time_shift_sec": f"{shift:.9f}",
        "first_time_after": first_after,
        "trace_used_online": False,
        "go2_position_as_truth": False,
        "go2_yaw_as_truth": False,
    }


def materialize_provider_15col_gnss(src: Path, output: Path, case_id: str) -> dict[str, Any]:
    rows = read_csv_dicts(src)
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            try:
                t = float(row["gps_tow"])
                lat = float(row["lat_deg"])
                lon = float(row["lon_deg"])
                height = float(row["height_m"])
                std_n = float(row["std_n_m"])
                std_e = float(row["std_e_m"])
                std_d = float(row["std_d_m"])
                ve = float(row["vel_e_mps"])
                vn = float(row["vel_n_mps"])
                vu = float(row["vel_u_mps"])
                yaw = float(row["yaw_deg"])
                yaw_std = float(row["yaw_std_deg"])
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            values = [
                t,
                lat,
                lon,
                height,
                std_n,
                std_e,
                std_d,
                vn,
                ve,
                -vu,
                0.05,
                0.05,
                0.05,
                yaw,
                max(yaw_std, 0.001),
            ]
            handle.write(" ".join(f"{value:.12g}" for value in values) + "\n")
            written += 1
    audit = {
        "case_id": case_id,
        "source_csv": str(src),
        "runtime_gnss15": str(output),
        "source_csv_hash": sha256_file(src),
        "runtime_gnss15_hash": sha256_file(output),
        "source_rows_read": len(rows),
        "runtime_rows_written": written,
        "skipped_rows": skipped,
        "velocity_std_policy": "fixed_0p05_observed_in_uploaded_code",
        "velocity_axis_mapping": "vn=vel_n_mps;ve=vel_e_mps;vd=-vel_u_mps",
        "trace_used_online": False,
        "final_v23_output_solver_input": False,
        "legsa_output_solver_input": False,
        "per_case_tuning": False,
    }
    write_json(output.with_suffix(".audit.json"), audit)
    return audit


def mode_overrides(mode: str) -> dict[str, Any]:
    overrides: dict[str, Any] = {
        "enable_multi_state_qm": mode != "QM00_OFF",
        "multi_state_qm": mode != "QM00_OFF",
        "multi_state_qm_mode": mode,
        "multi_state_qm_trace_enabled": mode != "QM00_OFF",
        "source_aware_policy_version": "n6b_conservative_innovation_covariance",
        "source_aware_mode": "lsim_oim",
        "enable_source_aware_weighting": True,
        "source_aware_trace_enabled": True,
        "source_aware_no_R_shrink": True,
        "source_aware_reject_extreme": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "legsa_output_solver_input": False,
        "per_case_tuning": False,
        "trace_tuning": False,
        "final_v23_tuning": False,
    }
    overrides.update(QM_PARAM_DEFAULTS)
    return overrides


def go2_overrides(spec: DatasetSpec) -> dict[str, Any]:
    return {
        "enable_go2_attitude_weak_prior": True,
        "go2_attitude_prior_path": str(spec.attitude_prior),
        "go2_attitude_prior_time_tolerance_sec": 0.05,
        "go2_attitude_prior_std_roll_deg": 1.6,
        "go2_attitude_prior_std_pitch_deg": 1.6,
        "go2_attitude_prior_sourceaware": True,
        "go2_attitude_prior_diagnostic_only": False,
        "enable_go2_horizontal_velocity_prior": True,
        "go2_horizontal_velocity_prior_path": str(spec.velocity_prior),
        "go2_velocity_prior_time_tolerance_sec": 0.05,
        "go2_horizontal_velocity_prior_vertical_disabled": True,
        "go2_horizontal_velocity_prior_std_scale": 1.0,
        "go2_horizontal_velocity_prior_source_aware_enabled": True,
        "go2_horizontal_velocity_prior_mode": "horizontal_2d",
        "enable_go2_readiness_lsim_metadata": True,
        "go2_readiness_lsim_metadata_path": str(spec.readiness_metadata),
        "go2_readiness_lsim_time_tolerance_sec": 0.05,
        "go2_readiness_lsim_default_closed": False,
        "source_aware_go2_readiness_lsim_enabled": True,
        "source_aware_go2_readiness_low_scale": 2.0,
        "source_aware_go2_attitude_roll_pitch_enabled": True,
        "source_aware_go2_attitude_roll_pitch_lsim_enabled": True,
        "source_aware_go2_attitude_roll_pitch_oim_enabled": True,
        "source_aware_go2_horizontal_velocity_enabled": True,
        "source_aware_go2_horizontal_velocity_lsim_enabled": True,
        "source_aware_go2_horizontal_velocity_oim_enabled": True,
        "go2_position_prior_enabled": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "enable_go2_yaw_rate_prior_diagnostic": False,
    }


def materialize_config(case: RunCase, mode: str, spec: DatasetSpec, output_dir: Path) -> Path:
    text = case.template_config.read_text(encoding="utf-8", errors="replace")
    key = run_key(case)
    overrides = {
        "run_label": f"PAPER10B2_{case.dataset}_{mode}_{key}",
        "algorithm_id": "LegSA_full_EKF_multi_state_QM",
        "ablation_variant": mode,
        "outputpath": str(output_dir),
        "source_aware_policy": "SA04_N6B",
        "go2_policy": "G05_FULL_AUX",
        "paper_performance_claim": False,
        "bad_epoch_deletion_for_metric": False,
        "output_only_correction": False,
        "enable_fgo_feedback": False,
        "fgo_feedback_output_substitution": False,
        "fgo_feedback_direct_nav_override": False,
        "receiver_imu_data_as_body_imu": False,
    }
    if case.dataset == "BY2":
        imu_path = resolve_runtime_path_alias(parse_simple_yaml_value(case.template_config, "imupath"))
        gnss_path = resolve_runtime_path_alias(parse_simple_yaml_value(case.template_config, "gnsspath"))
        if imu_path:
            overrides["imupath"] = imu_path
        if gnss_path:
            overrides["gnsspath"] = gnss_path
    if case.dataset == "BY3" and case.provider_config is not None:
        overrides["imupath"] = resolve_runtime_path_alias(parse_simple_yaml_value(case.provider_config, "imupath"))
        if case.provider_gnss15 is not None:
            runtime_gnss15 = output_dir / "config" / "paper10b2_provider_15col.gnss"
            materialize_provider_15col_gnss(case.provider_gnss15, runtime_gnss15, case.case_id)
            overrides["gnsspath"] = str(runtime_gnss15)
        else:
            overrides["gnsspath"] = parse_simple_yaml_value(case.provider_config, "gnsspath")
        overrides["by3_yaw_metric_status"] = "diagnostic_only"
        overrides["by3_dataset_role"] = "poor_heading_stress_position_up_generalization"
    overrides.update(go2_overrides(spec))
    overrides.update(mode_overrides(mode))
    config_text = update_flat_yaml_text(text, overrides)
    config_path = output_dir / "config" / "runtime_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def run_solver(repo: Path, executable: Path, config: Path, output_dir: Path, timeout: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [str(executable), "--config", str(config), "--output-dir", str(output_dir)]
    write_json(output_dir / "solver_command.json", {"command": command, "trace_solver_input": False})
    try:
        completed = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=timeout, check=False)
        (output_dir / "logs").mkdir(exist_ok=True)
        (output_dir / "logs" / "stdout.txt").write_text(completed.stdout, encoding="utf-8", errors="replace")
        (output_dir / "logs" / "stderr.txt").write_text(completed.stderr, encoding="utf-8", errors="replace")
        return {
            "run_status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "solver_command": " ".join(command),
        }
    except subprocess.TimeoutExpired as exc:
        return {"run_status": "failed", "returncode": "", "blocked_reason": f"solver timeout after {exc.timeout}s"}


def run_eval(eval_script: Path, spec: DatasetSpec, solver_output: Path, eval_dir: Path, timeout: int) -> dict[str, Any]:
    eval_dir.mkdir(parents=True, exist_ok=True)
    nav_src = solver_output / "EVAL_NAV.csv"
    std_src = solver_output / "LegSA_PORT_STD.csv"
    if not nav_src.exists() or not std_src.exists():
        return {"official_eval_status": "blocked", "blocked_reason": "EVAL_NAV.csv or LegSA_PORT_STD.csv missing"}
    nav_dst = eval_dir / "converted_eval_nav_official.nav"
    std_dst = eval_dir / "converted_std_official.txt"
    try:
        nav_meta = _convert_eval_nav(nav_src, nav_dst)
        std_meta = _convert_std(std_src, nav_src, std_dst)
    except Exception as exc:
        return {"official_eval_status": "blocked", "blocked_reason": f"conversion failed: {exc!r}"}
    command = [
        "python3",
        str(eval_script),
        "--trace",
        str(spec.trace),
        "--nav",
        str(nav_dst),
        "--std",
        str(std_dst),
        "--outdir",
        str(eval_dir),
        "--base_time",
        f"{spec.base_time:.6f}",
        "--yaw_truth_mode",
        "enu",
    ]
    write_json(
        eval_dir / "command.json",
        {
            "command": command,
            "trace_is_evaluation_only": True,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
        },
    )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        (eval_dir / "run_stdout.txt").write_text(completed.stdout, encoding="utf-8", errors="replace")
        (eval_dir / "run_stderr.txt").write_text(completed.stderr, encoding="utf-8", errors="replace")
        summary = read_json(eval_dir / "summary.json", {}) or {}
        metrics = _metrics_from_summary(summary)
        if completed.returncode == 0 and not (eval_dir / "EVAL_NAV.csv").exists():
            shutil.copy2(nav_src, eval_dir / "EVAL_NAV.csv")
        return {
            "official_eval_status": "completed" if completed.returncode == 0 else "failed",
            "eval_returncode": completed.returncode,
            "metrics": metrics,
            "summary": summary,
            "nav_conversion": nav_meta,
            "std_conversion": std_meta,
        }
    except subprocess.TimeoutExpired as exc:
        return {"official_eval_status": "failed", "blocked_reason": f"eval timeout after {exc.timeout}s"}


def parse_qm_trace_counts(trace_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "state_trace_rows": 0,
        "state_transition_count": 0,
        "normal_count": 0,
        "downweight_count": 0,
        "reject_count": 0,
        "hold_count": 0,
        "recovery_count": 0,
        "fallback_count": 0,
        "source_action_count_by_source": "{}",
    }
    if not trace_path.exists():
        return out
    counts = {source: 0 for source in SOURCE_KEYS}
    prev_by_source: dict[str, str] = {}
    with trace_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            out["state_trace_rows"] += 1
            source = row.get("source") or row.get("source_id", "")
            state = row.get("state", "")
            if source in counts:
                counts[source] += 1
            if source and state and prev_by_source.get(source) not in {None, state}:
                out["state_transition_count"] += 1
            if source and state:
                prev_by_source[source] = state
            key = state.lower() + "_count"
            if key in out:
                out[key] += 1
    out["source_action_count_by_source"] = json.dumps(counts, ensure_ascii=False, sort_keys=True)
    return out


def metric_value(metrics: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metrics:
            return metrics[key]
    return ""


def row_from_result(case: RunCase,
                    mode: str,
                    spec: DatasetSpec,
                    output_dir: Path,
                    eval_dir: Path,
                    config_path: Path,
                    solver: dict[str, Any],
                    evaluator: dict[str, Any]) -> dict[str, Any]:
    metrics = evaluator.get("metrics") or {}
    trace_counts = parse_qm_trace_counts(output_dir / "QM_STATE_ACTION_TRACE.csv")
    row_status = "completed" if solver.get("run_status") == "completed" and evaluator.get("official_eval_status") == "completed" else "failed"
    if solver.get("run_status") != "completed":
        row_status = "solver_failed"
    elif evaluator.get("official_eval_status") != "completed":
        row_status = "eval_failed"
    manifest = read_json(output_dir / "RUN_MANIFEST.json", {}) or {}
    row: dict[str, Any] = {
        "dataset": case.dataset,
        "case_id": case.case_id,
        "run_key": run_key(case),
        "family": case.family,
        "seed": case.seed,
        "qm_mode": mode,
        "source_aware_policy": "SA04_N6B",
        "go2_policy": "G05_FULL_AUX",
        "row_status": row_status,
        "runtime_attempted": True,
        "solver_status": solver.get("run_status", ""),
        "official_eval_status": evaluator.get("official_eval_status", ""),
        "position_rmse_h": metric_value(metrics, "horizontal_rmse_m"),
        "position_rmse_3d": metric_value(metrics, "position_3d_rmse_m"),
        "up_rmse": metric_value(metrics, "up_rmse_m"),
        "velocity_rmse": metric_value(metrics, "velocity_rmse_m"),
        "roll_rmse": metric_value(metrics, "roll_rmse_deg"),
        "pitch_rmse": metric_value(metrics, "pitch_rmse_deg"),
        "yaw_rmse": metric_value(metrics, "yaw_rmse_deg"),
        "yaw_rmse_diagnostic": metric_value(metrics, "yaw_rmse_deg") if case.dataset == "BY3" else "",
        "yaw_metric_status": spec.yaw_metric_status,
        "trace_used_online": False,
        "go2_position_as_truth": False,
        "go2_yaw_as_truth": False,
        "final_v23_output_solver_input": False,
        "legsa_output_solver_input": False,
        "no_per_case_tuning": True,
        "config_hash": sha256_file(config_path),
        "input_hash": input_hash_for_config(config_path),
        "output_hash": sha256_file(output_dir / "EVAL_NAV.csv"),
        "output_dir": str(output_dir),
        "official_eval_dir": str(eval_dir),
        "go2_readiness_lsim_metadata_enabled": manifest.get("go2_readiness_lsim_metadata_enabled", ""),
        "go2_readiness_first_class_lsim": manifest.get("go2_readiness_first_class_lsim", ""),
    }
    row.update(trace_counts)
    return row


def input_hash_for_config(config: Path) -> str:
    pieces = []
    for key in ("imupath", "gnsspath", "go2_attitude_prior_path", "go2_horizontal_velocity_prior_path", "go2_readiness_lsim_metadata_path"):
        value = parse_simple_yaml_value(config, key)
        if value:
            pieces.append(sha256_file(Path(value)))
    if not pieces:
        return ""
    h = hashlib.sha256()
    for piece in pieces:
        h.update(piece.encode("ascii"))
    return h.hexdigest()


def run_one(job: dict[str, Any]) -> dict[str, Any]:
    case: RunCase = job["case"]
    mode: str = job["mode"]
    spec: DatasetSpec = job["spec"]
    args = job["args"]
    output_dir: Path = job["output_dir"]
    eval_dir: Path = job["eval_dir"]
    config_path = materialize_config(case, mode, spec, output_dir)
    solver = run_solver(args.repo, args.executable, config_path, output_dir, args.solver_timeout_sec)
    evaluator: dict[str, Any]
    if solver.get("run_status") == "completed":
        evaluator = run_eval(args.eval_script, spec, output_dir, eval_dir, args.eval_timeout_sec)
    else:
        evaluator = {"official_eval_status": "skipped", "blocked_reason": solver.get("blocked_reason", "solver failed")}
    return row_from_result(case, mode, spec, output_dir, eval_dir, config_path, solver, evaluator)


def write_checkpoint(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows)
    write_json(path.with_suffix(".json"), rows)


def run_jobs(jobs: list[dict[str, Any]], args: argparse.Namespace, space_csv: Path, checkpoint_csv: Path) -> tuple[list[dict[str, Any]], str]:
    completed: list[dict[str, Any]] = []
    space_rows: list[dict[str, Any]] = []
    stop_reason = ""
    last_checkpoint = time.time()
    job_iter = iter(jobs)
    submitted = 0
    futures: set[Any] = set()

    def submit_next(pool: ThreadPoolExecutor) -> bool:
        nonlocal stop_reason, submitted
        try:
            job = next(job_iter)
        except StopIteration:
            return False
        snap = space_snapshot(args.e_drive_probe, args.wsl_root_probe)
        snap["event"] = "pre_submit"
        snap["case_id"] = job["case"].case_id
        snap["qm_mode"] = job["mode"]
        space_rows.append(snap)
        stop_reason = hard_stop_triggered(snap, args.e_drive_hard_stop_gb, args.wsl_root_hard_stop_gb)
        if stop_reason:
            return False
        futures.add(pool.submit(run_one, job))
        submitted += 1
        return True

    pool = ThreadPoolExecutor(max_workers=args.jobs)
    try:
        for _ in range(max(1, args.jobs)):
            if not submit_next(pool):
                break
        while futures:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                row = future.result()
                completed.append(row)
                snap = space_snapshot(args.e_drive_probe, args.wsl_root_probe)
                snap["event"] = "post_complete"
                snap["case_id"] = row.get("case_id", "")
                snap["qm_mode"] = row.get("qm_mode", "")
                space_rows.append(snap)
                if len(completed) % 20 == 0 or time.time() - last_checkpoint > 600:
                    write_checkpoint(checkpoint_csv, completed)
                    write_csv(space_csv, space_rows)
                    last_checkpoint = time.time()
                stop_reason = hard_stop_triggered(snap, args.e_drive_hard_stop_gb, args.wsl_root_hard_stop_gb)
                if stop_reason:
                    break
            if stop_reason:
                break
            while len(futures) < max(1, args.jobs) and submitted < len(jobs):
                if not submit_next(pool):
                    break
            if stop_reason:
                break
    finally:
        if stop_reason:
            for future in futures:
                future.cancel()
        pool.shutdown(wait=not stop_reason, cancel_futures=bool(stop_reason))
    write_checkpoint(checkpoint_csv, completed)
    write_csv(space_csv, space_rows)
    return completed, stop_reason


def build_run_jobs(cases: list[RunCase], spec: DatasetSpec, modes: list[str], root: Path, section: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    jobs = []
    for case in cases:
        key = run_key(case)
        for mode in modes:
            output_dir = root / section / "solver_outputs" / case.dataset / mode / key
            eval_dir = root / section / "official_eval" / case.dataset / mode / key
            jobs.append({"case": case, "mode": mode, "spec": spec, "args": args, "output_dir": output_dir, "eval_dir": eval_dir})
    return jobs


def aggregate_by_case(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows


def aggregate_by_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["dataset"], row["family"], row["qm_mode"]), []).append(row)
    out = []
    for (dataset, family, mode), items in sorted(groups.items()):
        completed = [r for r in items if r.get("row_status") == "completed"]
        def mean(key: str) -> Any:
            vals = [float(r[key]) for r in completed if str(r.get(key, "")) not in {"", "nan"}]
            return sum(vals) / len(vals) if vals else ""
        out.append(
            {
                "dataset": dataset,
                "family": family,
                "qm_mode": mode,
                "planned_rows": len(items),
                "completed_rows": len(completed),
                "position_rmse_h_mean": mean("position_rmse_h"),
                "position_rmse_3d_mean": mean("position_rmse_3d"),
                "up_rmse_mean": mean("up_rmse"),
                "yaw_rmse_mean": mean("yaw_rmse"),
                "state_trace_rows_sum": sum(int(r.get("state_trace_rows") or 0) for r in completed),
                "downweight_count_sum": sum(int(r.get("downweight_count") or 0) for r in completed),
                "reject_count_sum": sum(int(r.get("reject_count") or 0) for r in completed),
                "hold_count_sum": sum(int(r.get("hold_count") or 0) for r in completed),
                "recovery_count_sum": sum(int(r.get("recovery_count") or 0) for r in completed),
                "fallback_count_sum": sum(int(r.get("fallback_count") or 0) for r in completed),
            }
        )
    return out


def delta_vs_qm00(family_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = {(r["dataset"], r["family"]): r for r in family_rows if r["qm_mode"] == "QM00_OFF"}
    out = []
    for row in family_rows:
        key = (row["dataset"], row["family"])
        b = base.get(key)
        if not b or row["qm_mode"] == "QM00_OFF":
            continue
        def delta(metric: str) -> Any:
            a_val, b_val = row.get(metric, ""), b.get(metric, "")
            if a_val == "" or b_val == "":
                return ""
            return float(a_val) - float(b_val)
        out.append(
            {
                "dataset": row["dataset"],
                "family": row["family"],
                "qm_mode": row["qm_mode"],
                "delta_position_rmse_h_mean": delta("position_rmse_h_mean"),
                "delta_up_rmse_mean": delta("up_rmse_mean"),
                "delta_yaw_rmse_mean": delta("yaw_rmse_mean"),
            }
        )
    return out


def method_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["dataset"], row["qm_mode"]), []).append(row)
    out = []
    for (dataset, mode), items in sorted(groups.items()):
        completed = [r for r in items if r.get("row_status") == "completed"]
        def mean(key: str) -> Any:
            vals = [float(r[key]) for r in completed if str(r.get(key, "")) not in {"", "nan"}]
            return sum(vals) / len(vals) if vals else ""
        out.append(
            {
                "dataset": dataset,
                "qm_mode": mode,
                "planned_rows": len(items),
                "completed_rows": len(completed),
                "position_rmse_h_mean": mean("position_rmse_h"),
                "up_rmse_mean": mean("up_rmse"),
                "yaw_metric_status": "diagnostic_only" if dataset == "BY3" else "ordinary_evaluation",
                "trace_rows_sum": sum(int(r.get("state_trace_rows") or 0) for r in completed),
                "fallback_count_sum": sum(int(r.get("fallback_count") or 0) for r in completed),
            }
        )
    return out


def write_matrix_outputs(stage_root: Path, dataset: str, rows: list[dict[str, Any]]) -> None:
    if dataset == "BY2":
        eval_dir = stage_root / "10_BY2_120_qm_ablation_evaluation"
        prefix = "PAPER10B2_BY2_120_QM"
    else:
        eval_dir = stage_root / "14_BY3_120_qm_ablation_evaluation"
        prefix = "PAPER10B2_BY3_120_QM"
    write_csv(eval_dir / f"{prefix}_ROW_LEVEL_MASTER_TABLE.csv", rows)
    write_csv(eval_dir / f"{prefix}_METRICS_BY_CASE.csv", aggregate_by_case(rows))
    family = aggregate_by_family(rows)
    write_csv(eval_dir / f"{prefix}_METRICS_BY_FAMILY.csv", family)
    write_csv(eval_dir / f"{prefix}_METHOD_SUMMARY.csv", method_summary(rows))
    write_csv(eval_dir / f"{prefix}_DELTA_VS_QM00_BY_FAMILY.csv", delta_vs_qm00(family))
    if dataset == "BY2":
        write_csv(eval_dir / f"{prefix}_WIN_LOSS_TIE_TABLE.csv", win_loss_tie(rows))
    else:
        (eval_dir / f"{prefix}_YAW_DIAGNOSTIC_ONLY_REPORT.md").write_text(
            "# PAPER10B2 BY3 QM Yaw Diagnostic-Only Report\n\n"
            "BY3 yaw remains diagnostic-only / poor-heading stress. PAPER10B2 does not convert BY3 into ordinary yaw generalization.\n",
            encoding="utf-8",
        )


def win_loss_tie(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_case: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault((row["dataset"], row.get("run_key") or row["case_id"]), {})[row["qm_mode"]] = row
    out = []
    for mode in QM_MODES:
        if mode == "QM00_OFF":
            continue
        wins = losses = ties = comparable = 0
        for items in by_case.values():
            base = items.get("QM00_OFF")
            other = items.get(mode)
            if not base or not other:
                continue
            try:
                b = float(base["position_rmse_h"])
                o = float(other["position_rmse_h"])
            except Exception:
                continue
            comparable += 1
            if o < b * 0.99:
                wins += 1
            elif o > b * 1.01:
                losses += 1
            else:
                ties += 1
        out.append({"qm_mode": mode, "comparable_rows": comparable, "wins": wins, "losses": losses, "ties": ties})
    return out


def make_manifest_rows(cases: list[RunCase], modes: list[str]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        for mode in modes:
            rows.append(
                {
                    "dataset": case.dataset,
                    "case_id": case.case_id,
                    "run_key": run_key(case),
                    "family": case.family,
                    "seed": case.seed,
                    "qm_mode": mode,
                    "source_aware_policy": "SA04_N6B",
                    "go2_policy": "G05_FULL_AUX",
                    "template_config": str(case.template_config),
                    "provider_config": str(case.provider_config or ""),
                    "trace_solver_input": False,
                    "final_v23_output_solver_input": False,
                    "legsa_output_solver_input": False,
                    "no_per_case_tuning": True,
                }
            )
    return rows


def run_stage(args: argparse.Namespace) -> dict[str, Any]:
    args.repo = args.repo.resolve()
    args.stage_root.mkdir(parents=True, exist_ok=True)
    by2_cases = build_by2_case_map(args.by2_case_manifest, args.by2_config_roots)
    by3_cases = build_by3_case_map(args.by3_sa04_root, args.by3_provider_root)

    by2_normal = [case for case in by2_cases if case.family == "normal"]
    by3_normal = [case for case in by3_cases if case.family == "normal"]
    by2_starttime = parse_float_yaml_value(by2_normal[0].template_config, "starttime", 66.0) if by2_normal else 66.0
    by3_start_source = (by3_normal[0].provider_config or by3_normal[0].template_config) if by3_normal else None
    by3_starttime = parse_float_yaml_value(by3_start_source, "starttime", 461217.499847) if by3_start_source else 461217.499847
    aligned_root = args.stage_root / "runtime_only_large_outputs" / "go2_prior_time_aligned"
    prior_alignment_reports = [
        time_align_prior_to_solver_axis(
            args.by2_go2_attitude_prior,
            aligned_root / "BY2_GO2_ATTITUDE_WEAK_PRIORS_QM_TIME_ALIGNED.csv",
            by2_starttime,
            "BY2",
        ),
        time_align_prior_to_solver_axis(
            args.by2_go2_velocity_prior,
            aligned_root / "BY2_GO2_HORIZONTAL_VELOCITY_PRIORS_QM_TIME_ALIGNED.csv",
            by2_starttime,
            "BY2",
        ),
        time_align_prior_to_solver_axis(
            args.by3_go2_attitude_prior,
            aligned_root / "BY3_GO2_ATTITUDE_WEAK_PRIORS_QM_TIME_ALIGNED.csv",
            by3_starttime,
            "BY3",
        ),
        time_align_prior_to_solver_axis(
            args.by3_go2_velocity_prior,
            aligned_root / "BY3_GO2_HORIZONTAL_VELOCITY_PRIORS_QM_TIME_ALIGNED.csv",
            by3_starttime,
            "BY3",
        ),
    ]
    specs = {
        "BY2": DatasetSpec(
            name="BY2",
            trace=args.by2_trace,
            base_time=args.by2_base_time,
            yaw_metric_status="ordinary_evaluation",
            attitude_prior=aligned_root / "BY2_GO2_ATTITUDE_WEAK_PRIORS_QM_TIME_ALIGNED.csv",
            velocity_prior=aligned_root / "BY2_GO2_HORIZONTAL_VELOCITY_PRIORS_QM_TIME_ALIGNED.csv",
            readiness_metadata=args.stage_root / "runtime_only_large_outputs" / "BY2_GO2_READINESS_LSIM_METADATA.csv",
        ),
        "BY3": DatasetSpec(
            name="BY3",
            trace=args.by3_trace,
            base_time=args.by3_base_time,
            yaw_metric_status="diagnostic_only",
            attitude_prior=aligned_root / "BY3_GO2_ATTITUDE_WEAK_PRIORS_QM_TIME_ALIGNED.csv",
            velocity_prior=aligned_root / "BY3_GO2_HORIZONTAL_VELOCITY_PRIORS_QM_TIME_ALIGNED.csv",
            readiness_metadata=args.stage_root / "runtime_only_large_outputs" / "BY3_GO2_READINESS_LSIM_METADATA.csv",
        ),
    }
    readiness_reports = [
        generate_readiness_metadata(specs["BY2"].velocity_prior, specs["BY2"].readiness_metadata, "BY2"),
        generate_readiness_metadata(specs["BY3"].velocity_prior, specs["BY3"].readiness_metadata, "BY3"),
    ]
    write_json(
        args.stage_root / "06_qm_config_freeze" / "PAPER10B2_GO2_READINESS_METADATA_GENERATION.json",
        {
            "prior_alignment_reports": prior_alignment_reports,
            "readiness_reports": readiness_reports,
            "trace_used_online": False,
            "go2_position_as_truth": False,
            "go2_yaw_as_truth": False,
        },
    )
    write_csv(args.stage_root / "08_BY2_120_qm_ablation_manifest" / "PAPER10B2_BY2_120_QM_RUN_MATRIX.csv", make_manifest_rows(by2_cases, QM_MODES))
    write_csv(args.stage_root / "08_BY2_120_qm_ablation_manifest" / "PAPER10B2_BY2_120_QM_CASE_MANIFEST.csv", make_manifest_rows(by2_cases, ["QM04_FULL"]))
    write_csv(args.stage_root / "12_BY3_120_qm_ablation_manifest" / "PAPER10B2_BY3_120_QM_RUN_MATRIX.csv", make_manifest_rows(by3_cases, QM_MODES))
    write_csv(args.stage_root / "12_BY3_120_qm_ablation_manifest" / "PAPER10B2_BY3_120_QM_CASE_MANIFEST.csv", make_manifest_rows(by3_cases, ["QM04_FULL"]))

    result: dict[str, Any] = {
        "readiness_reports": readiness_reports,
        "by2_case_count": len(by2_cases),
        "by3_case_count": len(by3_cases),
    }
    if args.manifest_only:
        result["status"] = "manifest_only"
        return result

    smoke_jobs = build_run_jobs(by2_normal, specs["BY2"], QM_MODES, args.stage_root, "07_QM_normal_smoke_BY2_BY3", args)
    smoke_jobs += build_run_jobs(by3_normal, specs["BY3"], QM_MODES, args.stage_root, "07_QM_normal_smoke_BY2_BY3", args)
    smoke_rows, smoke_stop = run_jobs(
        smoke_jobs,
        args,
        args.stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_NORMAL_QM_SPACE_MONITOR.csv",
        args.stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_NORMAL_QM_CHECKPOINT.csv",
    )
    write_csv(args.stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_BY2_NORMAL_QM_SMOKE.csv", [r for r in smoke_rows if r["dataset"] == "BY2"])
    write_csv(args.stage_root / "07_QM_normal_smoke_BY2_BY3" / "PAPER10B2_BY3_NORMAL_QM_SMOKE.csv", [r for r in smoke_rows if r["dataset"] == "BY3"])
    result["smoke_rows"] = len(smoke_rows)
    result["smoke_stop_reason"] = smoke_stop
    if smoke_stop or args.smoke_only:
        result["status"] = "smoke_only" if args.smoke_only else "stopped_after_smoke"
        return result

    by2_jobs = build_run_jobs(by2_cases, specs["BY2"], QM_MODES, args.stage_root, "09_BY2_120_qm_ablation_execution", args)
    by2_rows, by2_stop = run_jobs(
        by2_jobs,
        args,
        args.stage_root / "09_BY2_120_qm_ablation_execution" / "PAPER10B2_BY2_120_QM_SPACE_MONITOR.csv",
        args.stage_root / "09_BY2_120_qm_ablation_execution" / "PAPER10B2_BY2_120_QM_RUNTIME_INDEX.csv",
    )
    write_csv(args.stage_root / "09_BY2_120_qm_ablation_execution" / "PAPER10B2_BY2_120_QM_RUNTIME_PROOF.csv", by2_rows)
    write_matrix_outputs(args.stage_root, "BY2", by2_rows)
    result["by2_rows"] = len(by2_rows)
    result["by2_stop_reason"] = by2_stop
    if by2_stop:
        result["status"] = "stopped_after_by2"
        return result

    by3_jobs = build_run_jobs(by3_cases, specs["BY3"], QM_MODES, args.stage_root, "13_BY3_120_qm_ablation_execution", args)
    by3_rows, by3_stop = run_jobs(
        by3_jobs,
        args,
        args.stage_root / "13_BY3_120_qm_ablation_execution" / "PAPER10B2_BY3_120_QM_SPACE_MONITOR.csv",
        args.stage_root / "13_BY3_120_qm_ablation_execution" / "PAPER10B2_BY3_120_QM_RUNTIME_INDEX.csv",
    )
    write_csv(args.stage_root / "13_BY3_120_qm_ablation_execution" / "PAPER10B2_BY3_120_QM_RUNTIME_PROOF.csv", by3_rows)
    write_matrix_outputs(args.stage_root, "BY3", by3_rows)
    result["by3_rows"] = len(by3_rows)
    result["by3_stop_reason"] = by3_stop
    result["status"] = "completed" if not by3_stop else "stopped_after_by3"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--eval-script", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--e-drive-hard-stop-gb", type=float, default=10.0)
    parser.add_argument("--wsl-root-hard-stop-gb", type=float, default=30.0)
    parser.add_argument("--e-drive-probe", type=Path, required=True)
    parser.add_argument("--wsl-root-probe", type=Path, required=True)
    parser.add_argument("--runtime-path-alias", action="append", default=[], help="Runtime-only OLD=NEW path remap for migrated evidence roots.")
    parser.add_argument("--solver-timeout-sec", type=int, default=1800)
    parser.add_argument("--eval-timeout-sec", type=int, default=900)
    parser.add_argument("--by2-case-manifest", type=Path, required=True)
    parser.add_argument("--by2-config-roots", type=Path, nargs="+", required=True)
    parser.add_argument("--by3-sa04-root", type=Path, required=True)
    parser.add_argument("--by3-provider-root", type=Path, required=True)
    parser.add_argument("--by2-trace", type=Path, required=True)
    parser.add_argument("--by3-trace", type=Path, required=True)
    parser.add_argument("--by2-base-time", type=float, default=1772784000.0)
    parser.add_argument("--by3-base-time", type=float, default=1772323182.0)
    parser.add_argument("--by2-go2-attitude-prior", type=Path, required=True)
    parser.add_argument("--by2-go2-velocity-prior", type=Path, required=True)
    parser.add_argument("--by3-go2-attitude-prior", type=Path, required=True)
    parser.add_argument("--by3-go2-velocity-prior", type=Path, required=True)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--smoke-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global RUNTIME_PATH_ALIASES
    RUNTIME_PATH_ALIASES = parse_runtime_path_aliases(args.runtime_path_alias)
    result = run_stage(args)
    write_json(args.stage_root / "logs" / "PAPER10B2_RUNNER_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"completed", "smoke_only", "manifest_only"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
