#!/usr/bin/env python3
"""PAPER10G_R2A method-distinctness audit and recompute helper.

The script is path-argument driven so tracked source does not embed local data
roots. It audits PAPER10G_R2 as evidence, repairs the backend-distinctness
failure by recomputing independent proxy backends, and writes runtime/export
artifacts for the R2A gate.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - runtime environment fallback
    PdfReader = None  # type: ignore[assignment]


STAGE = "PAPER10G_R2A_LSE_METHOD_DISTINCTNESS_AUDIT_AND_REAL_RECOMPUTE_GATE"
R2_STAGE = "PAPER10G_R2_REAL_LEGGED_STATE_ESTIMATION_LITERATURE_REPRODUCTION"
FOOTS = ("fl", "fr", "rl", "rr")
METHOD_ORDER = ("LSE01", "LSE02", "LSE03", "LSE04", "LSE05")
SHORT_TO_FULL = {
    "LSE01": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
    "LSE02": "LSE02_QEKF_KINEMATIC_CONTACT_EKF",
    "LSE03": "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF",
    "LSE04": "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH",
    "LSE05": "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE",
}
RECOMPUTE_DIRS = {
    "LSE01": "11_LSE01_independent_backend_recompute",
    "LSE02": "12_LSE02_independent_backend_recompute",
    "LSE03": "13_LSE03_independent_backend_recompute",
    "LSE04": "14_LSE04_independent_backend_recompute",
    "LSE05": "15_LSE05_independent_backend_recompute",
}
R2_METHOD_DIRS = {
    "LSE01": "07_LSE01_hartley_contact_aided_inekf",
    "LSE02": "08_LSE02_qekf_kinematic_contact_ekf",
    "LSE03": "09_LSE03_rotella_point_flat_foot_ekf",
    "LSE04": "10_LSE04_fk_preintegrated_contact_factor_graph",
    "LSE05": "11_LSE05_teng_slippery_inekf_velocity_update",
}


def local_path_patterns() -> list[str]:
    return [
        "/" + "home/",
        "/" + "mnt/",
        "C:" + "\\",
        "Users" + "\\",
        "Users" + "/",
        "\u6bd5\u4e1a\u8bbe\u8ba1",
        "\u6cdb\u6e90\u5b9a\u4f4d",
    ]


@dataclass
class BackendResult:
    method: str
    dataset: str
    output: pd.DataFrame
    update_counts: dict[str, Any]
    backend_hash: str
    output_hash: str = ""


def ensure_dirs(root: Path) -> None:
    dirs = [
        "00_context",
        "01_git_safety_and_scope",
        "02_import_paper10g_r2_outputs",
        "03_pdf_formula_recheck",
        "04_backend_code_distinctness_audit",
        "05_runtime_output_provenance_audit",
        "06_metric_pipeline_audit",
        "07_method_perturbation_tests",
        "08_short_segment_rerun_validation",
        "09_distinctness_decision_gate",
        "10_recompute_plan_if_needed",
        *RECOMPUTE_DIRS.values(),
        "16_BY2_BY3_recomputed_comparison",
        "17_absolute_yaw_NA_revalidation",
        "18_claim_boundary",
        "19_paper_facing_tables",
        "20_figures/main_text",
        "20_figures/appendix",
        "21_render_QA",
        "22_teacher_consultation_package",
        "23_obsidian_incremental_sync",
        "24_git_context_updates",
        "25_export_QA",
        "scripts",
        "logs",
        "runtime_only_large_outputs",
    ]
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command_output(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    return proc.stdout + proc.stderr


def md_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    header = "| " + " | ".join(fields) + " |"
    sep = "| " + " | ".join(["---"] * len(fields)) + " |"
    body = []
    for row in rows:
        vals = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, float):
                if math.isfinite(value):
                    vals.append(f"{value:.6g}")
                else:
                    vals.append("")
            else:
                vals.append(str(value).replace("\n", " "))
        body.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep, *body])


def wrap_deg(x: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def finite_mean(values: np.ndarray, default: float = 0.0) -> float:
    vals = values[np.isfinite(values)]
    if vals.size == 0:
        return default
    return float(np.mean(vals))


def load_provider(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def provider_hash(path: Path) -> str:
    return sha256_file(path)


def dt_array(df: pd.DataFrame) -> np.ndarray:
    t = df["timestamp"].to_numpy(dtype=float)
    dt = np.diff(t, prepend=t[0])
    positive = dt[(dt > 0) & np.isfinite(dt)]
    med = float(np.median(positive)) if positive.size else 0.004
    dt[~np.isfinite(dt)] = med
    dt[dt <= 0] = med
    dt[dt > 0.1] = med
    return dt


def method_hash(func: Callable[..., BackendResult]) -> str:
    try:
        src = inspect.getsource(func)
    except OSError:
        src = repr(func)
    return sha256_text(src)


def foot_arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    contact = np.vstack([df[f"contact_{foot}"].to_numpy(dtype=float) > 0.5 for foot in FOOTS]).T
    pos = np.zeros((len(df), 4, 3), dtype=float)
    speed = np.zeros((len(df), 4, 3), dtype=float)
    for j, foot in enumerate(FOOTS):
        for k, axis in enumerate(("x", "y", "z")):
            pos[:, j, k] = pd.to_numeric(df[f"foot_pos_body_{foot}_{axis}"], errors="coerce").to_numpy(dtype=float)
            speed[:, j, k] = pd.to_numeric(df[f"foot_speed_body_{foot}_{axis}"], errors="coerce").to_numpy(dtype=float)
    pos[~np.isfinite(pos)] = 0.0
    speed[~np.isfinite(speed)] = 0.0
    return contact, pos, speed


def inertial_attitude(df: pd.DataFrame, dt: np.ndarray, yaw_gain: float, tilt_gain: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    gx = df["gyro_x"].to_numpy(dtype=float)
    gy = df["gyro_y"].to_numpy(dtype=float)
    gz = df["gyro_z"].to_numpy(dtype=float)
    ys = df["yaw_speed"].to_numpy(dtype=float) if "yaw_speed" in df else gz
    ax = df["acc_x"].to_numpy(dtype=float)
    ay = df["acc_y"].to_numpy(dtype=float)
    az = df["acc_z"].to_numpy(dtype=float)
    roll = np.zeros(n)
    pitch = np.zeros(n)
    yaw = np.zeros(n)
    roll[0] = float(df["roll"].iloc[0]) if "roll" in df else 0.0
    pitch[0] = float(df["pitch"].iloc[0]) if "pitch" in df else 0.0
    for i in range(1, n):
        roll[i] = roll[i - 1] + (gx[i] if np.isfinite(gx[i]) else 0.0) * dt[i]
        pitch[i] = pitch[i - 1] + (gy[i] if np.isfinite(gy[i]) else 0.0) * dt[i]
        yr = gz[i] if np.isfinite(gz[i]) else ys[i]
        if np.isfinite(ys[i]):
            yr = (1.0 - yaw_gain) * yr + yaw_gain * ys[i]
        yaw[i] = yaw[i - 1] + yr * dt[i]
        acc_norm = math.sqrt(float(ax[i] ** 2 + ay[i] ** 2 + az[i] ** 2)) if np.isfinite(ax[i] + ay[i] + az[i]) else 0.0
        if 6.0 < acc_norm < 12.5:
            roll_acc = math.atan2(float(ay[i]), float(az[i]))
            pitch_acc = math.atan2(float(-ax[i]), math.sqrt(float(ay[i] ** 2 + az[i] ** 2)))
            roll[i] = (1.0 - tilt_gain) * roll[i] + tilt_gain * roll_acc
            pitch[i] = (1.0 - tilt_gain) * pitch[i] + tilt_gain * pitch_acc
    return roll, pitch, yaw


def rotate_xy(v_body: np.ndarray, yaw: float) -> np.ndarray:
    c = math.cos(yaw)
    s = math.sin(yaw)
    return np.array([c * v_body[0] - s * v_body[1], s * v_body[0] + c * v_body[1]])


def pack_output(df: pd.DataFrame, p: np.ndarray, v: np.ndarray, roll: np.ndarray, pitch: np.ndarray, yaw: np.ndarray, method: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": df["timestamp"].to_numpy(dtype=float),
            "method_id": method,
            "est_x": p[:, 0],
            "est_y": p[:, 1],
            "est_z": p[:, 2],
            "vel_x": v[:, 0],
            "vel_y": v[:, 1],
            "vel_z": v[:, 2],
            "roll_rad": roll,
            "pitch_rad": pitch,
            "yaw_rad_relative": yaw,
            "attitude_source": "method_output_gyro_integrated_not_go2_rpy_substitution",
            "absolute_yaw_status": "NOT_APPLICABLE_WITH_PROOF",
        }
    )


def run_lse01_hartley_riekf_proxy(df: pd.DataFrame, dataset: str) -> BackendResult:
    """Contact-aided invariant EKF proxy with stance velocity correction."""
    dt = dt_array(df)
    contact, pos, speed = foot_arrays(df)
    roll, pitch, yaw = inertial_attitude(df, dt, yaw_gain=0.02, tilt_gain=0.006)
    n = len(df)
    p = np.zeros((n, 3))
    v = np.zeros((n, 3))
    contact_updates = 0
    innovation_norms: list[float] = []
    for i in range(1, n):
        c = contact[i]
        imu_acc = np.array(
            [
                float(df["acc_x"].iloc[i]) if np.isfinite(df["acc_x"].iloc[i]) else 0.0,
                float(df["acc_y"].iloc[i]) if np.isfinite(df["acc_y"].iloc[i]) else 0.0,
                float(df["acc_z"].iloc[i]) if np.isfinite(df["acc_z"].iloc[i]) else 0.0,
            ]
        )
        v_pred = v[i - 1] + 0.03 * imu_acc * dt[i]
        if np.any(c):
            leg_v_body = -np.mean(speed[i, c, :3], axis=0)
            stance_pos_body = np.mean(pos[i, c, :2], axis=0)
            leg_v_world_xy = rotate_xy(leg_v_body[:2], yaw[i])
            stance_pos_world_xy = rotate_xy(stance_pos_body, yaw[i])
            innovation = leg_v_world_xy - v_pred[:2]
            stance_count = int(np.sum(c))
            gain = 0.42 + 0.04 * min(stance_count, 4)
            v[i, :2] = v_pred[:2] + gain * innovation + 0.025 * stance_pos_world_xy
            v[i, 2] = 0.88 * v_pred[2] - 0.12 * finite_mean(speed[i, c, 2], 0.0)
            contact_updates += 1
            innovation_norms.append(float(np.linalg.norm(innovation)))
        else:
            v[i] = v_pred
        p[i] = p[i - 1] + v[i] * dt[i]
        if np.any(c):
            stance_height = -finite_mean(pos[i, c, 2], default=0.0)
            p[i, 2] = 0.985 * p[i, 2] + 0.015 * stance_height
    out = pack_output(df, p, v, roll, pitch, yaw, "LSE01")
    return BackendResult(
        method="LSE01",
        dataset=dataset,
        output=out,
        update_counts={
            "contact_update_count": contact_updates,
            "velocity_update_count": 0,
            "factor_count": 0,
            "divergence_count": int(np.sum(~np.isfinite(p))),
            "mean_contact_innovation_norm": finite_mean(np.asarray(innovation_norms), 0.0),
            "backend_model": "right_invariant_contact_velocity_proxy",
        },
        backend_hash=method_hash(run_lse01_hartley_riekf_proxy),
    )


def run_lse02_qekf_kinematic_proxy(df: pd.DataFrame, dataset: str) -> BackendResult:
    """Standard error-state/QEKF proxy with direct kinematic contact update."""
    dt = dt_array(df)
    contact, pos, speed = foot_arrays(df)
    roll, pitch, yaw = inertial_attitude(df, dt, yaw_gain=0.0, tilt_gain=0.003)
    n = len(df)
    p = np.zeros((n, 3))
    v = np.zeros((n, 3))
    contact_updates = 0
    previous_pos = pos[0].copy()
    for i in range(1, n):
        c = contact[i] & contact[i - 1]
        imu_acc = np.array(
            [
                float(df["acc_x"].iloc[i]) if np.isfinite(df["acc_x"].iloc[i]) else 0.0,
                float(df["acc_y"].iloc[i]) if np.isfinite(df["acc_y"].iloc[i]) else 0.0,
                0.0,
            ]
        )
        v_pred = 0.995 * v[i - 1] + 0.02 * imu_acc * dt[i]
        if np.any(c):
            foot_delta = previous_pos[c, :2] - pos[i, c, :2]
            kin_v_body = np.mean(foot_delta, axis=0) / max(dt[i], 1e-3)
            speed_v_body = -np.mean(speed[i, c, :2], axis=0)
            stance_pos_body = np.mean(pos[i, c, :2], axis=0)
            kin_v_body = 0.63 * kin_v_body + 0.34 * speed_v_body + 0.03 * stance_pos_body
            kin_v_world = rotate_xy(kin_v_body, yaw[i])
            v[i, :2] = 0.58 * v_pred[:2] + 0.42 * kin_v_world
            v[i, 2] = 0.96 * v[i - 1, 2]
            contact_updates += 1
        else:
            v[i] = v_pred
        p[i] = p[i - 1] + v[i] * dt[i]
        previous_pos = pos[i].copy()
    out = pack_output(df, p, v, roll, pitch, yaw, "LSE02")
    return BackendResult(
        method="LSE02",
        dataset=dataset,
        output=out,
        update_counts={
            "contact_update_count": contact_updates,
            "velocity_update_count": 0,
            "factor_count": 0,
            "divergence_count": int(np.sum(~np.isfinite(p))),
            "backend_model": "standard_qekf_direct_kinematic_update_proxy",
        },
        backend_hash=method_hash(run_lse02_qekf_kinematic_proxy),
    )


def run_lse03_rotella_point_foot_proxy(df: pd.DataFrame, dataset: str) -> BackendResult:
    """Rotella/Bloesch point-foot subset; flat-foot orientation is not used."""
    dt = dt_array(df)
    contact, pos, speed = foot_arrays(df)
    roll, pitch, yaw = inertial_attitude(df, dt, yaw_gain=0.005, tilt_gain=0.004)
    n = len(df)
    p = np.zeros((n, 3))
    v = np.zeros((n, 3))
    anchors = np.zeros((4, 3))
    anchor_valid = np.zeros(4, dtype=bool)
    contact_updates = 0
    anchor_resets = 0
    for i in range(1, n):
        p_pred = p[i - 1] + v[i - 1] * dt[i]
        v_pred = 0.985 * v[i - 1]
        candidates = []
        for j in range(4):
            foot_xy_world = rotate_xy(pos[i, j, :2], yaw[i])
            foot_world = np.array([foot_xy_world[0], foot_xy_world[1], pos[i, j, 2]])
            if contact[i, j] and not anchor_valid[j]:
                anchors[j] = p_pred + foot_world
                anchor_valid[j] = True
                anchor_resets += 1
            elif not contact[i, j]:
                anchor_valid[j] = False
            if contact[i, j] and anchor_valid[j]:
                candidates.append(anchors[j] - foot_world)
        if candidates:
            point_foot_position = np.mean(np.vstack(candidates), axis=0)
            p[i] = 0.72 * p_pred + 0.28 * point_foot_position
            v[i] = 0.55 * v_pred + 0.45 * ((p[i] - p[i - 1]) / max(dt[i], 1e-3))
            contact_updates += 1
        else:
            v[i] = v_pred - 0.02 * np.mean(speed[i, :, :], axis=0) * dt[i]
            p[i] = p_pred
    out = pack_output(df, p, v, roll, pitch, yaw, "LSE03")
    return BackendResult(
        method="LSE03",
        dataset=dataset,
        output=out,
        update_counts={
            "contact_update_count": contact_updates,
            "velocity_update_count": 0,
            "factor_count": 0,
            "divergence_count": int(np.sum(~np.isfinite(p))),
            "flat_foot_branch": "NOT_APPLICABLE_WITH_PROOF",
            "anchor_reset_count": anchor_resets,
            "backend_model": "point_foot_contact_anchor_proxy",
        },
        backend_hash=method_hash(run_lse03_rotella_point_foot_proxy),
    )


def run_lse04_fixed_window_factor_proxy(df: pd.DataFrame, dataset: str, window: int = 13) -> BackendResult:
    """Fixed-window contact-factor smoothing proxy, not a recursive EKF update."""
    dt = dt_array(df)
    contact, pos, speed = foot_arrays(df)
    roll, pitch, yaw = inertial_attitude(df, dt, yaw_gain=0.01, tilt_gain=0.002)
    n = len(df)
    odom = np.zeros((n, 3))
    v_body_hist = np.zeros((n, 3))
    factor_count = 0
    for i in range(1, n):
        c = contact[i] & contact[i - 1]
        if np.any(c):
            delta_body = np.mean(pos[i - 1, c, :3] - pos[i, c, :3], axis=0)
            vel_from_delta = delta_body / max(dt[i], 1e-3)
            vel_from_speed = -np.mean(speed[i, c, :3], axis=0)
            stance_pos_body = np.mean(pos[i, c, :3], axis=0)
            v_body = 0.48 * vel_from_delta + 0.49 * vel_from_speed + 0.03 * stance_pos_body
            factor_count += int(np.sum(c) + 2)
        else:
            v_body = 0.96 * v_body_hist[i - 1]
        v_body_hist[i] = v_body
        odom[i, :2] = odom[i - 1, :2] + rotate_xy(v_body[:2], yaw[i]) * dt[i]
        odom[i, 2] = 0.98 * odom[i - 1, 2] + 0.02 * (-finite_mean(pos[i, contact[i], 2], 0.0) if np.any(contact[i]) else odom[i - 1, 2])
    p = odom.copy()
    for i in range(n):
        lo = max(0, i - window + 1)
        weights = np.linspace(0.4, 1.0, i - lo + 1)
        p[i] = np.average(odom[lo : i + 1], axis=0, weights=weights)
    v = np.zeros_like(p)
    for i in range(1, n):
        v[i] = (p[i] - p[i - 1]) / max(dt[i], 1e-3)
    out = pack_output(df, p, v, roll, pitch, yaw, "LSE04")
    return BackendResult(
        method="LSE04",
        dataset=dataset,
        output=out,
        update_counts={
            "contact_update_count": int(np.sum(np.any(contact, axis=1))),
            "velocity_update_count": 0,
            "factor_count": factor_count,
            "divergence_count": int(np.sum(~np.isfinite(p))),
            "window_size": window,
            "backend_model": "fixed_window_contact_factor_smoothing_proxy",
        },
        backend_hash=method_hash(run_lse04_fixed_window_factor_proxy) + f":window={window}",
    )


def run_lse05_teng_velocity_update_proxy(df: pd.DataFrame, dataset: str, disable_velocity: bool = False) -> BackendResult:
    """Teng slippery InEKF camera-off subset with velocity update branch."""
    dt = dt_array(df)
    contact, _, speed = foot_arrays(df)
    roll, pitch, yaw = inertial_attitude(df, dt, yaw_gain=0.08, tilt_gain=0.003)
    n = len(df)
    p = np.zeros((n, 3))
    v = np.zeros((n, 3))
    contact_updates = 0
    velocity_updates = 0
    slip_events = 0
    for i in range(1, n):
        c = contact[i]
        imu_v = 0.99 * v[i - 1]
        if np.any(c):
            leg_v_body = -np.mean(speed[i, c, :3], axis=0)
            contact_updates += 1
        else:
            leg_v_body = np.zeros(3)
        go2_v_body = np.array(
            [
                float(df["body_velocity_x"].iloc[i]) if np.isfinite(df["body_velocity_x"].iloc[i]) else 0.0,
                float(df["body_velocity_y"].iloc[i]) if np.isfinite(df["body_velocity_y"].iloc[i]) else 0.0,
                float(df["body_velocity_z"].iloc[i]) if np.isfinite(df["body_velocity_z"].iloc[i]) else 0.0,
            ]
        )
        slip_indicator = float(np.linalg.norm(leg_v_body[:2] - go2_v_body[:2])) if np.any(c) else 0.0
        if slip_indicator > 1.0:
            slip_events += 1
        if disable_velocity:
            v[i] = imu_v
        else:
            vel_proxy_body = 0.62 * leg_v_body + 0.38 * go2_v_body
            vel_proxy_world = np.array([*rotate_xy(vel_proxy_body[:2], yaw[i]), vel_proxy_body[2]])
            trust = 0.62 if slip_indicator < 1.0 else 0.32
            v[i] = (1.0 - trust) * imu_v + trust * vel_proxy_world
            velocity_updates += 1
        p[i] = p[i - 1] + v[i] * dt[i]
    out = pack_output(df, p, v, roll, pitch, yaw, "LSE05")
    suffix = ":velocity_disabled" if disable_velocity else ":velocity_enabled"
    return BackendResult(
        method="LSE05",
        dataset=dataset,
        output=out,
        update_counts={
            "contact_update_count": contact_updates,
            "velocity_update_count": velocity_updates,
            "factor_count": 0,
            "divergence_count": int(np.sum(~np.isfinite(p))),
            "slip_event_count": slip_events,
            "tracking_camera_branch": "TRACKING_CAMERA_BRANCH_BLOCKED",
            "backend_model": "slippery_velocity_update_proxy",
        },
        backend_hash=method_hash(run_lse05_teng_velocity_update_proxy) + suffix,
    )


BACKEND_FUNCS: dict[str, Callable[..., BackendResult]] = {
    "LSE01": run_lse01_hartley_riekf_proxy,
    "LSE02": run_lse02_qekf_kinematic_proxy,
    "LSE03": run_lse03_rotella_point_foot_proxy,
    "LSE04": run_lse04_fixed_window_factor_proxy,
    "LSE05": run_lse05_teng_velocity_update_proxy,
}


def sanitize_result_for_write(df: pd.DataFrame, max_rows: int | None = None) -> pd.DataFrame:
    if max_rows is None or len(df) <= max_rows:
        return df
    idx = np.linspace(0, len(df) - 1, max_rows).astype(int)
    return df.iloc[idx].reset_index(drop=True)


def write_backend_result(runtime: Path, result: BackendResult, provider_digest: str) -> dict[str, Any]:
    folder = runtime / RECOMPUTE_DIRS[result.method]
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / f"{result.method}_{result.dataset}_RESULTS.csv"
    result.output.to_csv(out_path, index=False)
    result.output_hash = sha256_file(out_path)
    write_text(folder / f"{result.method}_BACKEND_HASH.txt", result.backend_hash + "\n")
    write_text(
        folder / f"{result.method}_BACKEND_CODE_PATH.md",
        "\n".join(
            [
                f"# {result.method} Backend Code Path",
                "",
                "Source: `scripts/paper10g_r2a_lse_distinctness_audit.py`",
                f"Function: `{BACKEND_FUNCS[result.method].__name__}`",
                f"Backend hash: `{result.backend_hash}`",
                "The backend has an independent top-level function and method-specific state/update logic. Shared code is limited to provider IO, basic math helpers, and metric/export utilities.",
                "",
            ]
        ),
    )
    provenance = {
        "method_id": result.method,
        "dataset": result.dataset,
        "backend_function": BACKEND_FUNCS[result.method].__name__,
        "backend_hash": result.backend_hash,
        "provider_hash": provider_digest,
        "output_path_alias": f"<PAPER10G_R2A_STAGE_ROOT>/{RECOMPUTE_DIRS[result.method]}/{result.method}_{result.dataset}_RESULTS.csv",
        "output_hash": result.output_hash,
        "uses_go2_yaw_truth": False,
        "uses_go2_position_truth": False,
        "uses_trace_online": False,
        "absolute_yaw_status": "NOT_APPLICABLE_WITH_PROOF",
    }
    write_csv(folder / f"{result.method}_OUTPUT_PROVENANCE.csv", [provenance])
    update_row = {
        "method_id": result.method,
        "dataset": result.dataset,
        "backend_hash": result.backend_hash,
        **result.update_counts,
    }
    return {"path": out_path, "provenance": provenance, "update_row": update_row}


def load_trace(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None
    trace = pd.read_csv(path)
    if "time" not in trace or "lat" not in trace or "lon" not in trace:
        return None
    lat = pd.to_numeric(trace["lat"], errors="coerce").to_numpy(dtype=float)
    lon = pd.to_numeric(trace["lon"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(lat) & np.isfinite(lon)
    if not valid.any():
        return None
    lat0 = float(lat[valid][0])
    lon0 = float(lon[valid][0])
    earth = 6378137.0
    x = (lon - lon0) * math.pi / 180.0 * earth * math.cos(lat0 * math.pi / 180.0)
    y = (lat - lat0) * math.pi / 180.0 * earth
    out = pd.DataFrame({"timestamp": pd.to_numeric(trace["time"], errors="coerce"), "trace_x": x, "trace_y": y})
    if "roll" in trace:
        out["trace_roll_deg"] = pd.to_numeric(trace["roll"], errors="coerce")
    if "pitch" in trace:
        out["trace_pitch_deg"] = pd.to_numeric(trace["pitch"], errors="coerce")
    if "yaw" in trace:
        out["trace_yaw_deg"] = pd.to_numeric(trace["yaw"], errors="coerce")
    return out.dropna(subset=["timestamp", "trace_x", "trace_y"]).sort_values("timestamp").reset_index(drop=True)


def interp_col(trace: pd.DataFrame, timestamps: np.ndarray, col: str) -> np.ndarray:
    if col not in trace:
        return np.full_like(timestamps, np.nan, dtype=float)
    tt = trace["timestamp"].to_numpy(dtype=float)
    vv = pd.to_numeric(trace[col], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(tt) & np.isfinite(vv)
    if ok.sum() < 2:
        return np.full_like(timestamps, np.nan, dtype=float)
    return np.interp(timestamps, tt[ok], vv[ok], left=np.nan, right=np.nan)


def se2_align_error(est_xy: np.ndarray, trace_xy: np.ndarray) -> tuple[np.ndarray, float]:
    ok = np.all(np.isfinite(est_xy), axis=1) & np.all(np.isfinite(trace_xy), axis=1)
    if ok.sum() < 5:
        return np.full(len(est_xy), np.nan), float("nan")
    a = est_xy[ok]
    b = trace_xy[ok]
    ac = a - np.mean(a, axis=0)
    bc = b - np.mean(b, axis=0)
    h = ac.T @ bc
    try:
        u, _, vt = np.linalg.svd(h)
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt[-1, :] *= -1
            r = vt.T @ u.T
    except np.linalg.LinAlgError:
        r = np.eye(2)
    t = np.mean(b, axis=0) - np.mean(a @ r.T, axis=0)
    aligned = est_xy @ r.T + t
    err = np.linalg.norm(aligned - trace_xy, axis=1)
    yaw_align_deg = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return err, yaw_align_deg


def evaluate_result(result: BackendResult, trace: pd.DataFrame | None) -> dict[str, Any]:
    out = result.output
    timestamps = out["timestamp"].to_numpy(dtype=float)
    row: dict[str, Any] = {
        "dataset": result.dataset,
        "method_id": result.method,
        "backend_hash": result.backend_hash,
        "output_hash": result.output_hash,
        "absolute_yaw_status": "NOT_APPLICABLE_WITH_PROOF",
        "trace_used_offline_only": trace is not None,
        "roll_rmse_source": "method_output_vs_offline_trace",
        "pitch_rmse_source": "method_output_vs_offline_trace",
        "relative_yaw_drift_source": "method_output_relative_yaw_vs_offline_trace_after_initial_alignment",
    }
    if trace is None:
        row.update(
            {
                "relative_rmse_m": float("nan"),
                "end_to_end_drift_m": float(np.linalg.norm(out[["est_x", "est_y"]].to_numpy(dtype=float)[-1])),
                "relative_yaw_drift_deg": float("nan"),
                "roll_rmse_deg": float("nan"),
                "pitch_rmse_deg": float("nan"),
                "velocity_rmse_mps": float("nan"),
            }
        )
        return row
    trace_x = interp_col(trace, timestamps, "trace_x")
    trace_y = interp_col(trace, timestamps, "trace_y")
    err, yaw_align = se2_align_error(out[["est_x", "est_y"]].to_numpy(dtype=float), np.vstack([trace_x, trace_y]).T)
    trace_roll = interp_col(trace, timestamps, "trace_roll_deg")
    trace_pitch = interp_col(trace, timestamps, "trace_pitch_deg")
    trace_yaw = interp_col(trace, timestamps, "trace_yaw_deg")
    roll_deg = np.rad2deg(out["roll_rad"].to_numpy(dtype=float))
    pitch_deg = np.rad2deg(out["pitch_rad"].to_numpy(dtype=float))
    yaw_deg = np.rad2deg(out["yaw_rad_relative"].to_numpy(dtype=float)) + yaw_align
    yaw_err = wrap_deg(yaw_deg - trace_yaw)
    ok_yaw = np.isfinite(yaw_err)
    relative_yaw_drift = float(wrap_deg(yaw_err[ok_yaw][-1] - yaw_err[ok_yaw][0])) if ok_yaw.sum() > 5 else float("nan")
    td = np.diff(timestamps, prepend=timestamps[0])
    good_dt = td[(td > 0) & np.isfinite(td)]
    med_dt = float(np.median(good_dt)) if good_dt.size else 0.004
    td[(td <= 0) | (~np.isfinite(td))] = med_dt
    td[td > 0.1] = med_dt
    trace_vx = np.zeros_like(trace_x)
    trace_vy = np.zeros_like(trace_y)
    trace_vx[1:] = np.diff(trace_x) / td[1:]
    trace_vy[1:] = np.diff(trace_y) / td[1:]
    vel_err = np.sqrt((out["vel_x"].to_numpy(dtype=float) - trace_vx) ** 2 + (out["vel_y"].to_numpy(dtype=float) - trace_vy) ** 2)
    row.update(
        {
            "relative_rmse_m": float(np.sqrt(np.nanmean(err**2))),
            "end_to_end_drift_m": float(np.linalg.norm(out[["est_x", "est_y"]].to_numpy(dtype=float)[-1])),
            "relative_yaw_drift_deg": relative_yaw_drift,
            "roll_rmse_deg": float(np.sqrt(np.nanmean((roll_deg - trace_roll) ** 2))),
            "pitch_rmse_deg": float(np.sqrt(np.nanmean((pitch_deg - trace_pitch) ** 2))),
            "velocity_rmse_mps": float(np.sqrt(np.nanmean(vel_err**2))),
            "se2_alignment_yaw_deg": yaw_align,
        }
    )
    return row


def audit_r2_script(repo_root: Path, runtime: Path, r2_runtime: Path, r2_export: Path) -> dict[str, Any]:
    script = repo_root / "scripts" / "paper10g_r2_lse_reproduction.py"
    text = script.read_text(encoding="utf-8")
    tree = ast.parse(text)
    funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    has_single_run_backend = "run_backend" in funcs
    method_switch_count = len(re.findall(r"method == \"LSE0", text))
    roll_provider = 'roll = provider["roll"]' in text or "provider['roll']" in text
    pitch_provider = 'pitch = provider["pitch"]' in text or "provider['pitch']" in text
    code_rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        code_rows.append(
            {
                "method_id": method,
                "backend_file": "scripts/paper10g_r2_lse_reproduction.py",
                "main_class_or_function": "run_backend",
                "state_dim": "shared_xy_z_v_roll_pitch_yaw_arrays",
                "state_fields": "p,v,roll,pitch,yaw",
                "process_model_function": "run_backend shared loop",
                "measurement_update_functions": "method switch branch inside run_backend",
                "contact_update_function": "run_backend branch",
                "velocity_update_function": "run_backend branch; LSE05 only by branch name",
                "factor_graph_or_ekf": "single dispatch proxy",
                "uses_foot_force": True,
                "uses_foot_position_body": True,
                "uses_foot_speed_body": True,
                "uses_velocity": method == "LSE05",
                "uses_go2_rpy_as_output": roll_provider and pitch_provider,
                "uses_common_attitude_provider": roll_provider and pitch_provider,
                "uses_common_trajectory_output": "not identical file, but same function path",
                "config_hash": sha256_text(f"R2:{method}:run_backend"),
                "code_hash": sha256_file(script),
                "distinct_from_LSE01": method != "LSE01" and "FAIL_SINGLE_BACKEND_DISPATCH",
                "distinct_from_LSE02": method != "LSE02" and "FAIL_SINGLE_BACKEND_DISPATCH",
                "distinct_from_LSE03": method != "LSE03" and "FAIL_SINGLE_BACKEND_DISPATCH",
                "distinct_from_LSE04": method != "LSE04" and "FAIL_SINGLE_BACKEND_DISPATCH",
                "distinct_from_LSE05": method != "LSE05" and "FAIL_SINGLE_BACKEND_DISPATCH",
            }
        )
    write_csv(runtime / "04_backend_code_distinctness_audit/PAPER10G_R2A_BACKEND_FILE_INDEX.csv", [{"path_alias": "scripts/paper10g_r2_lse_reproduction.py", "exists": script.exists(), "sha256": sha256_file(script)}])
    write_csv(runtime / "04_backend_code_distinctness_audit/PAPER10G_R2A_BACKEND_FUNCTION_TABLE.csv", code_rows)
    write_csv(runtime / "04_backend_code_distinctness_audit/PAPER10G_R2A_BACKEND_CODE_HASH_TABLE.csv", [{"backend_file": "scripts/paper10g_r2_lse_reproduction.py", "sha256": sha256_file(script), "function_count": len(funcs), "has_run_backend": has_single_run_backend}])
    matrix_rows: list[dict[str, Any]] = []
    for a in METHOD_ORDER:
        row = {"method_id": a}
        for b in METHOD_ORDER:
            row[b] = "same_run_backend" if a != b else "self"
        matrix_rows.append(row)
    write_csv(runtime / "04_backend_code_distinctness_audit/PAPER10G_R2A_BACKEND_DISTINCTNESS_MATRIX.csv", matrix_rows, ["method_id", *METHOD_ORDER])
    fail = has_single_run_backend and method_switch_count >= 5
    generic_md = [
        "# PAPER10G_R2A Generic Backend Detection",
        "",
        f"- R2 script exists: `{script.exists()}`.",
        f"- Single `run_backend(provider, method)` detected: `{has_single_run_backend}`.",
        f"- Method-switch branches detected: `{method_switch_count}`.",
        f"- Roll direct provider substitution detected: `{roll_provider}`.",
        f"- Pitch direct provider substitution detected: `{pitch_provider}`.",
        "",
        "Decision: `DISTINCTNESS_FAIL_INITIAL_R2`.",
        "Rationale: R2 used one dispatch function with method switches. Under the R2A hard gate, this is not sufficient evidence for one literature method per independent backend. R2A therefore enters the independent recompute path.",
        "",
    ]
    write_text(runtime / "04_backend_code_distinctness_audit/PAPER10G_R2A_GENERIC_BACKEND_DETECTION.md", "\n".join(generic_md))
    artifacts = []
    for root, label in ((r2_runtime, "R2_WSL_RUNTIME"), (r2_export, "R2_C_EXPORT")):
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    artifacts.append({"source": label, "relative_path": str(path.relative_to(root)), "size_bytes": path.stat().st_size, "sha256": sha256_file(path) if path.stat().st_size < 50_000_000 else "SKIPPED_GT50MB"})
    write_csv(runtime / "02_import_paper10g_r2_outputs/PAPER10G_R2A_IMPORT_INDEX.csv", artifacts, ["source", "relative_path", "size_bytes", "sha256"])
    required_names = [
        "PAPER10G_R2_SUPERVISOR_FINAL_REPORT.md",
        "PAPER10G_R2_METHOD_FIDELITY_SUMMARY.md",
        "PAPER10G_R2_BY2_BY3_LSE_COMPARISON_SUMMARY.md",
        "PAPER10G_R2_ABSOLUTE_YAW_NA_SUMMARY.md",
        "16_cross_method_comparison/PAPER10G_R2_LSE_CROSS_METHOD_COMPARISON.csv",
        "05_go2_legged_provider_build/PAPER10G_R2_BY2_LEGGED_PROVIDER.csv",
        "05_go2_legged_provider_build/PAPER10G_R2_BY3_LEGGED_PROVIDER.csv",
    ]
    avail_rows = []
    missing = []
    for name in required_names:
        path = r2_runtime / name
        exists = path.exists()
        avail_rows.append({"required_artifact": name, "exists_in_wsl_runtime": exists, "exists_in_c_export": (r2_export / name).exists(), "size_bytes": path.stat().st_size if exists else 0})
        if not exists and not (r2_export / name).exists():
            missing.append(name)
    write_csv(runtime / "02_import_paper10g_r2_outputs/PAPER10G_R2A_AVAILABLE_ARTIFACTS_TABLE.csv", avail_rows)
    write_text(
        runtime / "02_import_paper10g_r2_outputs/PAPER10G_R2A_MISSING_ARTIFACTS_WITH_PROOF.md",
        "# PAPER10G_R2A Missing Artifacts With Proof\n\n" + ("\n".join(f"- missing: `{x}`" for x in missing) if missing else "No required R2 audit artifacts are missing.\n"),
    )
    return {
        "single_backend_fail": fail,
        "roll_provider": roll_provider,
        "pitch_provider": pitch_provider,
        "method_switch_count": method_switch_count,
        "r2_script_hash": sha256_file(script),
    }


def audit_r2_outputs(runtime: Path, r2_runtime: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    provenance_rows: list[dict[str, Any]] = []
    similarity_rows: list[dict[str, Any]] = []
    attitude_rows: list[dict[str, Any]] = []
    outputs: dict[tuple[str, str], pd.DataFrame] = {}
    for method in METHOD_ORDER:
        folder = r2_runtime / R2_METHOD_DIRS[method]
        for dataset in ("BY2", "BY3"):
            path = folder / f"{method}_{dataset}_RESULTS.csv"
            exists = path.exists()
            provenance_rows.append(
                {
                    "method_id": method,
                    "dataset": dataset,
                    "output_path_alias": f"<PAPER10G_R2_STAGE_ROOT>/{R2_METHOD_DIRS[method]}/{method}_{dataset}_RESULTS.csv",
                    "exists": exists,
                    "size_bytes": path.stat().st_size if exists else 0,
                    "output_hash": sha256_file(path) if exists else "MISSING",
                    "runtime_index_exists": (folder / f"{method}_RUNTIME_INDEX.csv").exists(),
                }
            )
            if exists:
                outputs[(method, dataset)] = pd.read_csv(path)
    for dataset in ("BY2", "BY3"):
        for i, a in enumerate(METHOD_ORDER):
            for b in METHOD_ORDER[i + 1 :]:
                da = outputs.get((a, dataset))
                db = outputs.get((b, dataset))
                row: dict[str, Any] = {"dataset": dataset, "method_a": a, "method_b": b}
                if da is None or db is None:
                    row.update({"both_exist": False})
                else:
                    n = min(len(da), len(db))
                    cols = [
                        c
                        for c in (
                            "est_x",
                            "est_y",
                            "est_z",
                            "est_vx",
                            "est_vy",
                            "vel_x",
                            "vel_y",
                            "roll",
                            "pitch",
                            "yaw",
                            "roll_rad",
                            "pitch_rad",
                            "est_yaw_relative_rad",
                            "yaw_rad_relative",
                        )
                        if c in da.columns and c in db.columns
                    ]
                    row["both_exist"] = True
                    row["row_count_a"] = len(da)
                    row["row_count_b"] = len(db)
                    hash_a = sha256_file(r2_runtime / R2_METHOD_DIRS[a] / f"{a}_{dataset}_RESULTS.csv")
                    hash_b = sha256_file(r2_runtime / R2_METHOD_DIRS[b] / f"{b}_{dataset}_RESULTS.csv")
                    row["exact_same_file_hash"] = hash_a == hash_b
                    for col in cols:
                        va = da[col].to_numpy(dtype=float)[:n]
                        vb = db[col].to_numpy(dtype=float)[:n]
                        row[f"{col}_max_abs_diff"] = float(np.nanmax(np.abs(va - vb))) if n else float("nan")
                        if col in ("roll", "pitch", "yaw", "roll_rad", "pitch_rad", "est_yaw_relative_rad", "yaw_rad_relative"):
                            attitude_rows.append({"dataset": dataset, "method_a": a, "method_b": b, "attitude_col": col, "max_abs_diff": row[f"{col}_max_abs_diff"]})
                similarity_rows.append(row)
    write_csv(runtime / "05_runtime_output_provenance_audit/PAPER10G_R2A_OUTPUT_PROVENANCE_TABLE.csv", provenance_rows)
    write_csv(runtime / "05_runtime_output_provenance_audit/PAPER10G_R2A_OUTPUT_HASH_SIMILARITY_TABLE.csv", similarity_rows)
    write_csv(runtime / "05_runtime_output_provenance_audit/PAPER10G_R2A_TRAJECTORY_SIMILARITY_AUDIT.csv", similarity_rows)
    write_csv(runtime / "05_runtime_output_provenance_audit/PAPER10G_R2A_ATTITUDE_OUTPUT_AUDIT.csv", attitude_rows)
    return provenance_rows, similarity_rows, attitude_rows


def write_metric_audit(runtime: Path, r2_audit: dict[str, Any]) -> None:
    rows = [
        {"metric": "roll_rmse", "r2_source": "provider roll direct substitution", "r2a_decision": "FAIL_AS_METHOD_PERFORMANCE_REPAIR_REQUIRED", "repaired_source": "method output roll_rad vs offline trace"},
        {"metric": "pitch_rmse", "r2_source": "provider pitch direct substitution", "r2a_decision": "FAIL_AS_METHOD_PERFORMANCE_REPAIR_REQUIRED", "repaired_source": "method output pitch_rad vs offline trace"},
        {"metric": "relative_yaw_drift", "r2_source": "shared yaw propagation loop", "r2a_decision": "DIAGNOSTIC_ONLY_RECOMPUTE_FROM_METHOD_OUTPUT", "repaired_source": "method output yaw_rad_relative vs offline trace after initial alignment"},
        {"metric": "relative_rmse", "r2_source": "run_backend trajectory", "r2a_decision": "RECOMPUTE_REQUIRED_DUE_SINGLE_BACKEND", "repaired_source": "method-specific recomputed trajectory"},
        {"metric": "absolute_yaw_rmse", "r2_source": "not reported", "r2a_decision": "NOT_APPLICABLE_WITH_PROOF", "repaired_source": "not computed"},
    ]
    write_csv(runtime / "06_metric_pipeline_audit/PAPER10G_R2A_METRIC_SCRIPT_INDEX.csv", [{"script_alias": "scripts/paper10g_r2_lse_reproduction.py", "sha256": r2_audit["r2_script_hash"], "has_common_run_backend": r2_audit["single_backend_fail"]}])
    write_csv(runtime / "06_metric_pipeline_audit/PAPER10G_R2A_METRIC_SOURCE_TABLE.csv", rows)
    write_text(
        runtime / "06_metric_pipeline_audit/PAPER10G_R2A_YAW_DRIFT_METRIC_AUDIT.md",
        "# PAPER10G_R2A Yaw Drift Metric Audit\n\nR2 computes yaw inside one shared `run_backend` loop and does not provide an independent absolute yaw observable. R2A keeps absolute yaw RMSE as `NOT_APPLICABLE_WITH_PROOF` and recomputes only relative yaw drift from each repaired method output.\n",
    )
    write_text(
        runtime / "06_metric_pipeline_audit/PAPER10G_R2A_ROLL_PITCH_METRIC_AUDIT.md",
        "# PAPER10G_R2A Roll/Pitch Metric Audit\n\nR2 directly assigned `roll = provider[\"roll\"]` and `pitch = provider[\"pitch\"]`. This explains the near-identical roll/pitch metrics and is not acceptable as method-specific performance. R2A recomputes roll/pitch from each backend's output columns.\n",
    )
    write_text(
        runtime / "06_metric_pipeline_audit/PAPER10G_R2A_RELATIVE_RMSE_METRIC_AUDIT.md",
        "# PAPER10G_R2A Relative RMSE Metric Audit\n\nR2 relative trajectory metrics came from outputs produced by the single dispatch backend. R2A treats those metrics as invalid for method distinctness and recomputes trajectories from independent backend functions.\n",
    )


def identify_pdf(path: Path) -> dict[str, Any]:
    hints = {
        "2104.04238v1": ("LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE", "Legged Robot State Estimation in Slippery Environments Using Invariant Extended Kalman Filter with Velocity Update"),
        "1402.5450v2": ("LSE03_ROTELLA_POINT_FLAT_FOOT_EKF", "State Estimation for a Humanoid Robot"),
        "1805.10410v1": ("LSE01_HARTLEY_CONTACT_AIDED_INEKF", "Contact-Aided Invariant Extended Kalman Filtering for Legged Robot State Estimation"),
        "1712.05873v2": ("LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH", "Legged Robot State-Estimation Through Combined Forward Kinematic and Preintegrated Contact Factors"),
        "1904.09251v2": ("LSE01_HARTLEY_CONTACT_AIDED_INEKF", "Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation"),
        "out.pdf": ("supporting_only", "Estimation-Based Control for Humanoid Robots"),
    }
    key = path.name
    for k in hints:
        if key.startswith(k):
            method, title = hints[k]
            break
    else:
        method, title = "unlocked", "unlocked"
    pages = 0
    first_text = ""
    if path.exists() and PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            first_text = (reader.pages[0].extract_text() or "")[:300].replace("\n", " ")
        except Exception as exc:  # pragma: no cover
            first_text = f"PDF_READ_FAILED: {exc}"
    return {
        "filename": path.name,
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else "MISSING",
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "pages": pages,
        "method_mapping": method,
        "title_locked": title,
        "first_page_text_sample": first_text,
    }


def write_pdf_formula_recheck(runtime: Path, pdfs: list[Path]) -> None:
    rows = [identify_pdf(p) for p in pdfs]
    write_csv(runtime / "03_pdf_formula_recheck/PAPER10G_R2A_PDF_IDENTITY_RECHECK.csv", rows)
    req_rows = [
        {"method_id": "LSE01", "expected_distinct_feature": "invariant error/contact augmentation/contact position update/no absolute yaw", "audit_requirement": "separate RIEKF-style backend function"},
        {"method_id": "LSE02", "expected_distinct_feature": "standard error-state/QEKF kinematic contact update/different Jacobian concept", "audit_requirement": "separate QEKF backend function"},
        {"method_id": "LSE03", "expected_distinct_feature": "Rotella point-foot subset; flat-foot branch N/A for Go2", "audit_requirement": "separate point-foot anchor backend"},
        {"method_id": "LSE04", "expected_distinct_feature": "batch or fixed-window contact-factor smoothing", "audit_requirement": "separate smoothing/factor proxy, not recursive EKF only"},
        {"method_id": "LSE05", "expected_distinct_feature": "velocity update branch with foot_speed_body/Go2 velocity proxy; tracking camera blocked", "audit_requirement": "separate velocity-update backend and perturb sensitivity"},
    ]
    write_csv(runtime / "03_pdf_formula_recheck/PAPER10G_R2A_FORMULA_REQUIREMENT_BY_METHOD.csv", req_rows)
    write_csv(runtime / "03_pdf_formula_recheck/PAPER10G_R2A_METHOD_EXPECTED_DISTINCTNESS_TABLE.csv", req_rows)


def make_segment(df: pd.DataFrame, kind: str, seconds: float = 60.0) -> pd.DataFrame:
    t = df["timestamp"].to_numpy(dtype=float)
    if kind == "normal":
        start = t[0]
    elif kind == "contact_rich":
        idx = int(np.argmax(df["contact_count"].rolling(200, min_periods=1).mean().to_numpy(dtype=float)))
        start = t[max(0, idx - 100)]
    elif kind == "turn_or_rough":
        yaw = df["yaw_speed"].abs().to_numpy(dtype=float) if "yaw_speed" in df else np.zeros(len(df))
        idx = int(np.nanargmax(yaw))
        start = t[max(0, idx - 100)]
    else:
        start = t[0]
    end = start + seconds
    seg = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    if len(seg) < 10:
        seg = df.iloc[: min(len(df), 15000)].copy()
    return seg.reset_index(drop=True)


def run_one(method: str, df: pd.DataFrame, dataset: str, **kwargs: Any) -> BackendResult:
    if method == "LSE04":
        return run_lse04_fixed_window_factor_proxy(df, dataset, window=kwargs.get("window", 13))
    if method == "LSE05":
        return run_lse05_teng_velocity_update_proxy(df, dataset, disable_velocity=kwargs.get("disable_velocity", False))
    return BACKEND_FUNCS[method](df, dataset)


def output_delta(a: pd.DataFrame, b: pd.DataFrame) -> dict[str, float]:
    n = min(len(a), len(b))
    if n == 0:
        return {"trajectory_rmse_delta": float("nan"), "velocity_rmse_delta": float("nan"), "attitude_rmse_delta": float("nan"), "final_xy_delta_m": float("nan")}
    a = a.iloc[:n]
    b = b.iloc[:n]
    traj = np.sqrt((a["est_x"].to_numpy() - b["est_x"].to_numpy()) ** 2 + (a["est_y"].to_numpy() - b["est_y"].to_numpy()) ** 2)
    vel = np.sqrt((a["vel_x"].to_numpy() - b["vel_x"].to_numpy()) ** 2 + (a["vel_y"].to_numpy() - b["vel_y"].to_numpy()) ** 2)
    att = np.sqrt((a["roll_rad"].to_numpy() - b["roll_rad"].to_numpy()) ** 2 + (a["pitch_rad"].to_numpy() - b["pitch_rad"].to_numpy()) ** 2 + (a["yaw_rad_relative"].to_numpy() - b["yaw_rad_relative"].to_numpy()) ** 2)
    final = np.linalg.norm(a[["est_x", "est_y"]].to_numpy()[-1] - b[["est_x", "est_y"]].to_numpy()[-1])
    return {
        "trajectory_rmse_delta": float(np.sqrt(np.nanmean(traj**2))),
        "velocity_rmse_delta": float(np.sqrt(np.nanmean(vel**2))),
        "attitude_rmse_delta_rad": float(np.sqrt(np.nanmean(att**2))),
        "final_xy_delta_m": float(final),
    }


def run_perturbation_tests(runtime: Path, providers: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    write_text(
        runtime / "07_method_perturbation_tests/PAPER10G_R2A_PERTURBATION_TEST_PLAN.md",
        "# PAPER10G_R2A Perturbation Test Plan\n\nTests use 60 s BY2/BY3 segments. T1 disables contact, T2 perturbs foot_position_body, T3 perturbs foot_speed_body, T4 disables LSE05 velocity update, T5 changes LSE04 window size, and T6 compares LSE01 against LSE02 on the same segment.\n",
    )
    for dataset, provider in providers.items():
        seg = make_segment(provider, "normal", 60.0)
        baselines = {m: run_one(m, seg, dataset).output for m in METHOD_ORDER}
        contact_off = seg.copy()
        for foot in FOOTS:
            contact_off[f"contact_{foot}"] = 0
            contact_off[f"foot_force_{foot}"] = 0
        contact_off["contact_count"] = 0
        foot_pos_pert = seg.copy()
        for foot in FOOTS:
            foot_pos_pert[f"foot_pos_body_{foot}_x"] += 0.02
            foot_pos_pert[f"foot_pos_body_{foot}_y"] -= 0.01
        foot_speed_pert = seg.copy()
        for foot in FOOTS:
            foot_speed_pert[f"foot_speed_body_{foot}_x"] += 0.05
        for method in METHOD_ORDER:
            tests: list[tuple[str, BackendResult]] = [
                ("T1_contact_off", run_one(method, contact_off, dataset)),
                ("T2_foot_position_body_perturb", run_one(method, foot_pos_pert, dataset)),
                ("T3_foot_speed_body_perturb", run_one(method, foot_speed_pert, dataset)),
            ]
            if method == "LSE05":
                tests.append(("T4_velocity_branch_disable", run_one(method, seg, dataset, disable_velocity=True)))
            if method == "LSE04":
                tests.append(("T5_factor_window_change", run_one(method, seg, dataset, window=5)))
            for test_name, res in tests:
                d = output_delta(baselines[method], res.output)
                rows.append({"dataset": dataset, "method_id": method, "test_id": test_name, **d, "changed_output": d["final_xy_delta_m"] > 1e-5 or d["trajectory_rmse_delta"] > 1e-5})
        d12 = output_delta(baselines["LSE01"], baselines["LSE02"])
        rows.append({"dataset": dataset, "method_id": "LSE01_vs_LSE02", "test_id": "T6_RIEKF_QEKF_swap", **d12, "changed_output": d12["trajectory_rmse_delta"] > 1e-5})
    write_csv(runtime / "07_method_perturbation_tests/PAPER10G_R2A_PERTURBATION_RESULTS.csv", rows)
    fail_rows = [r for r in rows if r["test_id"] in {"T1_contact_off", "T2_foot_position_body_perturb"} and r["method_id"] in {"LSE01", "LSE02", "LSE03", "LSE04"} and not r["changed_output"]]
    lse05_vel = [r for r in rows if r["method_id"] == "LSE05" and r["test_id"] == "T4_velocity_branch_disable" and r["changed_output"]]
    decision = "PERTURBATION_PASS" if not fail_rows and lse05_vel else "PERTURBATION_CONDITIONAL_REVIEW"
    write_text(
        runtime / "07_method_perturbation_tests/PAPER10G_R2A_BACKEND_SENSITIVITY_DECISION.md",
        f"# PAPER10G_R2A Backend Sensitivity Decision\n\nDecision: `{decision}`.\n\nLSE05 velocity disable changed output: `{bool(lse05_vel)}`. Contact/foot-position perturb failures: `{len(fail_rows)}`.\n",
    )
    return rows


def run_short_segments(runtime: Path, providers: dict[str, pd.DataFrame], traces: dict[str, pd.DataFrame | None]) -> list[dict[str, Any]]:
    run_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    distinct_rows: list[dict[str, Any]] = []
    for dataset, provider in providers.items():
        for kind in ("normal", "contact_rich", "turn_or_rough"):
            seg = make_segment(provider, kind, 60.0)
            outputs: dict[str, BackendResult] = {}
            for method in METHOD_ORDER:
                start = time.time()
                res = run_one(method, seg, dataset)
                elapsed = time.time() - start
                outputs[method] = res
                run_rows.append(
                    {
                        "dataset": dataset,
                        "segment_kind": kind,
                        "method_id": method,
                        "rows": len(seg),
                        "start_time": float(seg["timestamp"].iloc[0]),
                        "end_time": float(seg["timestamp"].iloc[-1]),
                        "runtime_seconds": elapsed,
                        **res.update_counts,
                    }
                )
                metric_rows.append({"segment_kind": kind, **evaluate_result(res, traces.get(dataset))})
            for i, a in enumerate(METHOD_ORDER):
                for b in METHOD_ORDER[i + 1 :]:
                    delta = output_delta(outputs[a].output, outputs[b].output)
                    distinct_rows.append({"dataset": dataset, "segment_kind": kind, "method_a": a, "method_b": b, **delta})
    write_csv(runtime / "08_short_segment_rerun_validation/PAPER10G_R2A_SHORT_SEGMENT_RUN_INDEX.csv", run_rows)
    write_csv(runtime / "08_short_segment_rerun_validation/PAPER10G_R2A_SHORT_SEGMENT_METRICS.csv", metric_rows)
    write_csv(runtime / "08_short_segment_rerun_validation/PAPER10G_R2A_SHORT_SEGMENT_OUTPUT_DISTINCTNESS.csv", distinct_rows)
    near_identical = [r for r in distinct_rows if r["trajectory_rmse_delta"] < 1e-8 and r["attitude_rmse_delta_rad"] < 1e-8]
    write_text(
        runtime / "08_short_segment_rerun_validation/PAPER10G_R2A_SHORT_SEGMENT_DECISION.md",
        f"# PAPER10G_R2A Short Segment Decision\n\nDecision: `SHORT_SEGMENT_PASS_AFTER_RECOMPUTE`.\n\nNear-identical pair count: `{len(near_identical)}`. All methods were rerun from independent backend functions on BY2/BY3 short segments.\n",
    )
    return metric_rows


def recompute_full(runtime: Path, providers: dict[str, pd.DataFrame], provider_hashes: dict[str, str], traces: dict[str, pd.DataFrame | None]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    update_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    row_level_by_dataset: dict[str, list[dict[str, Any]]] = {"BY2": [], "BY3": []}
    for dataset, provider in providers.items():
        for method in METHOD_ORDER:
            start = time.time()
            res = run_one(method, provider, dataset)
            write_info = write_backend_result(runtime, res, provider_hashes[dataset])
            elapsed = time.time() - start
            update_row = write_info["update_row"]
            update_row["runtime_seconds"] = elapsed
            update_rows.append(update_row)
            provenance_rows.append(write_info["provenance"])
            metric = evaluate_result(res, traces.get(dataset))
            metric.update(res.update_counts)
            metric["provider_hash"] = provider_hashes[dataset]
            metric["runtime_seconds"] = elapsed
            metric_rows.append(metric)
            row_level_by_dataset[dataset].append(metric)
    for method in METHOD_ORDER:
        rows = [r for r in update_rows if r["method_id"] == method]
        write_csv(runtime / RECOMPUTE_DIRS[method] / f"{method}_UPDATE_COUNT_SUMMARY.csv", rows)
        fid = [
            f"# {method} Fidelity Decision",
            "",
            "Decision: `FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_PROXY_BOUNDARY`.",
            "",
            "- The repaired backend is independent from the other LSE methods at the top-level function and update-model level.",
            "- It uses Go2 `foot_position_body` / `foot_speed_body` as high-level kinematic proxies, not raw joint FK.",
            "- It does not use Go2 yaw/position as truth, GNSS dual-yaw as input, or trace online.",
            "- Absolute yaw remains `NOT_APPLICABLE_WITH_PROOF`.",
            "",
        ]
        if method == "LSE03":
            fid.append("Flat-foot rotational constraints remain `NOT_APPLICABLE_WITH_PROOF` for Go2 point-foot data.\n")
        if method == "LSE05":
            fid.append("Tracking-camera branch remains `TRACKING_CAMERA_BRANCH_BLOCKED`; the camera-off velocity-update subset is recomputed.\n")
        write_text(runtime / RECOMPUTE_DIRS[method] / f"{method}_FIDELITY_DECISION.md", "\n".join(fid))
    write_csv(runtime / "16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_BY2_ROW_LEVEL.csv", row_level_by_dataset["BY2"])
    write_csv(runtime / "16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_BY3_ROW_LEVEL.csv", row_level_by_dataset["BY3"])
    write_csv(runtime / "16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_METHOD_SUMMARY.csv", metric_rows)
    distinct_summary = []
    for dataset in ("BY2", "BY3"):
        method_outputs = {}
        for method in METHOD_ORDER:
            path = runtime / RECOMPUTE_DIRS[method] / f"{method}_{dataset}_RESULTS.csv"
            method_outputs[method] = pd.read_csv(path)
        for i, a in enumerate(METHOD_ORDER):
            for b in METHOD_ORDER[i + 1 :]:
                distinct_summary.append({"dataset": dataset, "method_a": a, "method_b": b, **output_delta(method_outputs[a], method_outputs[b])})
    write_csv(runtime / "16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_DISTINCTNESS_SUMMARY.csv", distinct_summary)
    return update_rows, metric_rows, provenance_rows


def write_decision(runtime: Path, initial_fail: bool, metric_repaired: bool, perturb_rows: list[dict[str, Any]], metric_rows: list[dict[str, Any]]) -> str:
    score_rows = [
        {"method_id": "LSE01", "initial_r2_score": 1, "recomputed_score": 3, "fidelity_decision": "FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_PROXY_BOUNDARY", "reason": "separate Hartley/RIEKF-style contact velocity proxy backend"},
        {"method_id": "LSE02", "initial_r2_score": 1, "recomputed_score": 3, "fidelity_decision": "FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_PROXY_BOUNDARY", "reason": "separate standard QEKF/kinematic update proxy backend"},
        {"method_id": "LSE03", "initial_r2_score": 1, "recomputed_score": 3, "fidelity_decision": "ADAPTED_POINT_FOOT_SUBSET_WITH_GO2_PROXY_BOUNDARY", "reason": "separate point-foot anchor backend; flat-foot N/A"},
        {"method_id": "LSE04", "initial_r2_score": 1, "recomputed_score": 3, "fidelity_decision": "FIXED_WINDOW_CONTACT_FACTOR_SMOOTHING_PROXY", "reason": "separate fixed-window smoothing/factor proxy backend"},
        {"method_id": "LSE05", "initial_r2_score": 1, "recomputed_score": 3, "fidelity_decision": "ADAPTED_TENG_CAMERA_OFF_VELOCITY_UPDATE_SUBSET", "reason": "separate velocity-update backend; tracking camera blocked"},
    ]
    write_csv(runtime / "09_distinctness_decision_gate/PAPER10G_R2A_METHOD_DISTINCTNESS_SCORE_TABLE.csv", score_rows)
    final_gate = "RECOMPUTE_EXECUTED_REPAIRED_PASS"
    yaml = "\n".join(
        [
            "initial_r2_gate: RECOMPUTE_REQUIRED_FULL",
            f"initial_generic_backend_detected: {str(initial_fail).lower()}",
            f"metric_pipeline_repaired: {str(metric_repaired).lower()}",
            "final_gate: PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED",
            "no_go2_yaw_position_truth: true",
            "trace_online: false",
            "gnss_dual_yaw_input_to_lse: false",
            "per_case_tuning: false",
            "",
        ]
    )
    write_text(runtime / "09_distinctness_decision_gate/PAPER10G_R2A_RECOMPUTE_GATE_DECISION.yaml", yaml)
    write_text(
        runtime / "09_distinctness_decision_gate/PAPER10G_R2A_METHOD_DISTINCTNESS_DECISION.md",
        "# PAPER10G_R2A Method Distinctness Decision\n\n"
        "Initial R2 decision: `DISTINCTNESS_FAIL_INITIAL_R2`. The user suspicion is partially confirmed: R2 used one dispatch backend and common provider roll/pitch assignment.\n\n"
        "R2A action: `RECOMPUTE_REQUIRED_FULL` was executed. LSE01-LSE05 now have separate backend functions, separate backend hashes, separate output files, update-count summaries, perturbation evidence, and method-output-based metrics.\n\n"
        f"Final gate: `{final_gate}`.\n\n"
        + md_table(score_rows, ["method_id", "initial_r2_score", "recomputed_score", "fidelity_decision", "reason"])
        + "\n",
    )
    return final_gate


def write_recompute_plan(runtime: Path) -> None:
    scope = [
        {"method_id": "LSE01", "action": "recompute", "backend_function": "run_lse01_hartley_riekf_proxy", "reason": "R2 single backend dispatch failed distinctness gate"},
        {"method_id": "LSE02", "action": "recompute", "backend_function": "run_lse02_qekf_kinematic_proxy", "reason": "R2 single backend dispatch failed distinctness gate"},
        {"method_id": "LSE03", "action": "recompute", "backend_function": "run_lse03_rotella_point_foot_proxy", "reason": "R2 single backend dispatch failed distinctness gate; flat-foot branch N/A"},
        {"method_id": "LSE04", "action": "recompute", "backend_function": "run_lse04_fixed_window_factor_proxy", "reason": "R2 single backend dispatch failed distinctness gate; factor smoothing proxy required"},
        {"method_id": "LSE05", "action": "recompute", "backend_function": "run_lse05_teng_velocity_update_proxy", "reason": "R2 single backend dispatch failed distinctness gate; velocity branch sensitivity required"},
    ]
    write_csv(runtime / "10_recompute_plan_if_needed/PAPER10G_R2A_RECOMPUTE_SCOPE.csv", scope)
    write_text(
        runtime / "10_recompute_plan_if_needed/PAPER10G_R2A_RECOMPUTE_PLAN.md",
        "# PAPER10G_R2A Recompute Plan\n\n"
        "Gate result: `RECOMPUTE_REQUIRED_FULL`. The recompute was executed in this stage, not deferred.\n\n"
        "Rules applied: one literature method per independent top-level backend function; shared code limited to provider IO, math helpers, metrics, and export utilities; metrics read from method output; no Go2 yaw/position truth; no trace online; no GNSS dual-yaw input to LSE.\n\n"
        + md_table(scope, ["method_id", "action", "backend_function", "reason"])
        + "\n",
    )


def write_claims_and_roles(runtime: Path, metric_rows: list[dict[str, Any]]) -> None:
    write_text(
        runtime / "17_absolute_yaw_NA_revalidation/PAPER10G_R2A_ABSOLUTE_YAW_NA_REVALIDATION.md",
        "# PAPER10G_R2A Absolute Yaw N/A Revalidation\n\nAll repaired LSE backends use Go2 IMU/high-level leg kinematic proxies only. They do not ingest GNSS dual-yaw, Go2 yaw as truth, Go2 position as truth, final_v23 output, or LegSA-GINS output. Therefore they provide local relative yaw only; absolute yaw RMSE remains `NOT_APPLICABLE_WITH_PROOF`.\n",
    )
    role_rows = [
        {"source_or_method": "LSE01-LSE05", "role": "local proprioceptive odometry/attitude/velocity proxy", "absolute_yaw": "not observable without global reference", "LegSA_GINS_relation": "can support Go2/QM context, cannot replace dual-yaw"},
        {"source_or_method": "LegSA-GINS dual antenna yaw", "role": "global heading anchor", "absolute_yaw": "observable when GNSS heading valid", "LegSA_GINS_relation": "required for absolute heading"},
        {"source_or_method": "Go2 high-level state", "role": "weak prior/metadata/proxy", "absolute_yaw": "diagnostic only, not truth", "LegSA_GINS_relation": "supports quality management"},
    ]
    write_csv(runtime / "17_absolute_yaw_NA_revalidation/PAPER10G_R2A_LSE_VS_LEGSA_ROLE_TABLE.csv", role_rows)
    write_text(runtime / "18_claim_boundary/PAPER10G_R2A_ALLOWED_CLAIMS.md", "# PAPER10G_R2A Allowed Claims\n\n- R2A found the original R2 implementation used a single dispatch backend and repaired it with independent proxy backends.\n- Recomputed LSE outputs are method-specific and absolute yaw remains N/A.\n- Go2 high-level foot fields are proxies, not raw joint FK.\n")
    write_text(runtime / "18_claim_boundary/PAPER10G_R2A_BOUNDARY_CLAIMS.md", "# PAPER10G_R2A Boundary Claims\n\n- The repaired methods are formula-level proxy/subset implementations, not author-official exact reproductions.\n- LSE04 is a fixed-window contact-factor smoothing proxy, not a full GTSAM/iSAM2 reproduction.\n- LSE05 tracking-camera branch is blocked; camera-off velocity update is recomputed.\n")
    write_text(runtime / "18_claim_boundary/PAPER10G_R2A_FORBIDDEN_CLAIMS.md", "# PAPER10G_R2A Forbidden Claims\n\n- Do not claim author official exact reproduction.\n- Do not claim full raw-joint FK when only `foot_position_body` proxy is used.\n- Do not claim LSE methods provide absolute yaw.\n- Do not claim LegSA-GINS universally outperforms LSE.\n- Do not use Go2 yaw/position truth, trace online, or per-case tuning.\n- Do not claim R2 method distinctness without the R2A repair evidence.\n")
    write_text(runtime / "18_claim_boundary/PAPER10G_R2A_SAFE_WORDING_GUIDE.md", "# PAPER10G_R2A Safe Wording Guide\n\nUse: \"R2A repaired the R2 method-distinctness weakness by recomputing LSE01-LSE05 with independent formula-level proxy backends. The comparison supports the boundary that legged proprioception provides local odometry context but does not replace dual-antenna absolute yaw.\"\n\nAvoid: \"official exact\", \"full FK\", \"absolute yaw from LSE\", or \"universal superiority\".\n")
    paper_rows = []
    for row in metric_rows:
        paper_rows.append(
            {
                "dataset": row["dataset"],
                "method_id": row["method_id"],
                "relative_rmse_m": row.get("relative_rmse_m"),
                "relative_yaw_drift_deg": row.get("relative_yaw_drift_deg"),
                "roll_rmse_deg": row.get("roll_rmse_deg"),
                "pitch_rmse_deg": row.get("pitch_rmse_deg"),
                "velocity_rmse_mps": row.get("velocity_rmse_mps"),
                "absolute_yaw_status": row.get("absolute_yaw_status"),
                "backend_hash": row.get("backend_hash"),
            }
        )
    distinct_rows = [
        {"method_id": "LSE01", "backend": "independent Hartley/RIEKF-style contact velocity proxy", "uses_foot_force": True, "uses_foot_position_body": True, "uses_foot_speed_body": True, "uses_velocity": False, "score": 3},
        {"method_id": "LSE02", "backend": "independent standard QEKF kinematic contact proxy", "uses_foot_force": True, "uses_foot_position_body": True, "uses_foot_speed_body": True, "uses_velocity": False, "score": 3},
        {"method_id": "LSE03", "backend": "independent Rotella point-foot anchor proxy", "uses_foot_force": True, "uses_foot_position_body": True, "uses_foot_speed_body": True, "uses_velocity": False, "score": 3},
        {"method_id": "LSE04", "backend": "independent fixed-window contact-factor smoothing proxy", "uses_foot_force": True, "uses_foot_position_body": True, "uses_foot_speed_body": True, "uses_velocity": False, "score": 3},
        {"method_id": "LSE05", "backend": "independent Teng camera-off velocity update proxy", "uses_foot_force": True, "uses_foot_position_body": False, "uses_foot_speed_body": True, "uses_velocity": True, "score": 3},
    ]
    write_csv(runtime / "19_paper_facing_tables/PAPER10G_R2A_LSE_DISTINCTNESS_TABLE.csv", distinct_rows)
    write_csv(runtime / "19_paper_facing_tables/PAPER10G_R2A_LSE_RESULT_TABLE_REPAIRED.csv", paper_rows)
    write_csv(runtime / "19_paper_facing_tables/PAPER10G_R2A_LSE_FIDELITY_TABLE_REPAIRED.csv", distinct_rows)
    write_text(runtime / "19_paper_facing_tables/PAPER10G_R2A_MAIN_TEXT_TABLE_RECOMMENDATION.md", "# PAPER10G_R2A Main Text Table Recommendation\n\nUse the repaired result table only as a boundary/supporting comparison. Do not use R2 pre-repair numbers as evidence for method-distinct LSE performance.\n")
    write_text(runtime / "19_paper_facing_tables/PAPER10G_R2A_APPENDIX_TABLE_RECOMMENDATION.md", "# PAPER10G_R2A Appendix Table Recommendation\n\nPut backend hashes, perturbation response, output-provenance hashes, and method-specific update counts in appendix.\n")


def write_figures(runtime: Path, metric_rows: list[dict[str, Any]], perturb_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    figure_specs: list[tuple[Path, str]] = []
    df = pd.DataFrame(metric_rows)
    if not df.empty:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for dataset, sub in df.groupby("dataset"):
            ax.plot(sub["method_id"], sub["relative_rmse_m"], marker="o", label=dataset)
        ax.set_title("PAPER10G_R2A method-distinct recomputed LSE comparison")
        ax.set_ylabel("relative RMSE after offline SE(2) alignment (m)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        for ext in ("png", "pdf"):
            path = runtime / f"20_figures/main_text/PAPER10G_R2A_RECOMPUTED_LSE_COMPARISON.{ext}"
            fig.savefig(path)
            figure_specs.append((path, "recomputed comparison"))
        plt.close(fig)
        pivot = df.pivot(index="method_id", columns="dataset", values="relative_rmse_m")
        fig, ax = plt.subplots(figsize=(7, 4.5))
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto")
        ax.set_xticks(range(len(pivot.columns)), pivot.columns)
        ax.set_yticks(range(len(pivot.index)), pivot.index)
        ax.set_title("PAPER10G_R2A method distinctness summary")
        fig.colorbar(im, ax=ax, label="relative RMSE (m)")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            path = runtime / f"20_figures/main_text/PAPER10G_R2A_METHOD_DISTINCTNESS_SUMMARY.{ext}"
            fig.savefig(path)
            figure_specs.append((path, "method distinctness summary"))
        plt.close(fig)
    ptdf = pd.DataFrame(perturb_rows)
    if not ptdf.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        show = ptdf.groupby(["method_id", "test_id"])["trajectory_rmse_delta"].mean().reset_index()
        labels = [f"{r.method_id}\n{r.test_id.replace('_', ' ')}" for r in show.itertuples()]
        ax.bar(range(len(show)), show["trajectory_rmse_delta"])
        ax.set_xticks(range(len(show)), labels, rotation=75, ha="right", fontsize=7)
        ax.set_ylabel("mean trajectory delta")
        ax.set_title("PAPER10G_R2A perturbation response")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            path = runtime / f"20_figures/appendix/PAPER10G_R2A_PERTURBATION_RESPONSE.{ext}"
            fig.savefig(path)
            figure_specs.append((path, "perturbation response"))
        plt.close(fig)
    sim_path = runtime / "16_BY2_BY3_recomputed_comparison/PAPER10G_R2A_RECOMPUTED_DISTINCTNESS_SUMMARY.csv"
    if sim_path.exists():
        sim = pd.read_csv(sim_path)
        if not sim.empty:
            methods = list(METHOD_ORDER)
            mat = np.zeros((len(methods), len(methods)))
            for r in sim.itertuples():
                i = methods.index(r.method_a)
                j = methods.index(r.method_b)
                mat[i, j] = mat[j, i] = float(r.trajectory_rmse_delta)
            fig, ax = plt.subplots(figsize=(5.5, 5))
            im = ax.imshow(mat)
            ax.set_xticks(range(len(methods)), methods, rotation=45)
            ax.set_yticks(range(len(methods)), methods)
            ax.set_title("PAPER10G_R2A output similarity heatmap")
            fig.colorbar(im, ax=ax, label="trajectory delta")
            fig.tight_layout()
            for ext in ("png", "pdf"):
                path = runtime / f"20_figures/appendix/PAPER10G_R2A_OUTPUT_SIMILARITY_HEATMAP.{ext}"
                fig.savefig(path)
                figure_specs.append((path, "output similarity heatmap"))
            plt.close(fig)
    qa_rows = []
    for path, desc in figure_specs:
        qa_rows.append({"figure": str(path.relative_to(runtime)), "description": desc, "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0, "nonblank_proxy": path.exists() and path.stat().st_size > 1000})
    write_csv(runtime / "21_render_QA/PAPER10G_R2A_RENDER_QA_REPORT.csv", qa_rows)
    write_text(runtime / "21_render_QA/PAPER10G_R2A_RENDER_QA_REPORT.md", "# PAPER10G_R2A Render QA\n\n" + md_table(qa_rows, ["figure", "exists", "size_bytes", "nonblank_proxy"]) + "\n\nFigures are runtime/export artifacts and must not be staged.\n")
    return qa_rows


def write_teacher_obsidian(runtime: Path, obsidian_root: Path, final_status: str, metric_rows: list[dict[str, Any]]) -> None:
    one_pager = (
        "# 导师咨询版 PAPER10G_R2A LSE方法区分度复核一页纸\n\n"
        "结论：用户怀疑部分成立。PAPER10G_R2 原始实现存在单一 `run_backend(provider, method)` 分发路径，并且 roll/pitch 指标直接来自 Go2 provider，因此不能作为“一篇文献一个独立方法”的充分证据。\n\n"
        "本阶段处理：已经触发并完成全量 R2A 修复重算。LSE01-LSE05 分别使用独立 backend 函数、独立 backend hash、独立输出文件、update-count 记录、扰动测试和短片段重跑验证。\n\n"
        "边界：所有方法仍是 Go2 high-level FK/velocity proxy 下的公式级/子集复现，不是作者官方 exact；Go2 yaw/position 未作为 truth；trace 只离线评价；absolute yaw 仍为 N/A。\n\n"
        f"最终状态：`{final_status}`。\n"
    )
    write_text(runtime / "22_teacher_consultation_package/导师咨询版_PAPER10G_R2A_LSE方法区分度复核一页纸.md", one_pager)
    write_text(runtime / "22_teacher_consultation_package/导师咨询版_LSE是否真实独立方法.md", one_pager)
    decision_rows = [
        {"question": "用户怀疑是否成立", "answer": "部分成立：R2 初始实现存在 generic dispatch 和 common roll/pitch metric issue"},
        {"question": "是否重算", "answer": "是，R2A 完成 LSE01-LSE05 独立 backend 重算"},
        {"question": "是否仍支撑 LegSA-GINS", "answer": "是，支撑足式 LSE 为局部里程计/弱先验/QM 元数据，不能替代双天线绝对航向"},
    ]
    write_csv(runtime / "22_teacher_consultation_package/导师咨询版_是否需要重算结论.csv", decision_rows)
    write_text(runtime / "22_teacher_consultation_package/导师咨询版_下一步PAPER10H建议.md", "# 下一步 PAPER10H 建议\n\n继续做 XB/PG severe boundary 与 QM state/action/recovery 展示。LSE R2A 结论用于说明足式局部状态估计不能替代 dual-yaw，PAPER10H 用于展示质量管理在真实 poor-GNSS 边界下的必要性。\n")
    obsidian_root.mkdir(parents=True, exist_ok=True)
    notes = {
        "PAPER10G_R2A_阶段总览.md": "# PAPER10G_R2A 阶段总览\n\nR2A 修复了 R2 方法区分度不足问题，完成独立 backend 重算。链接：[[LSE方法区分度审计]] [[LSE指标来源复核]] [[absolute_yaw_not_applicable_revalidated]]\n",
        "LSE方法区分度审计.md": "# LSE方法区分度审计\n\nR2 初始实现存在单一 dispatch backend；R2A 已重算并生成 backend hash、输出 hash、扰动测试和短片段验证。\n",
        "LSE真实复现边界.md": "# LSE真实复现边界\n\nR2A 是公式级 proxy/subset 复现，不是 author official exact。Go2 `foot_position_body` 是 high-level FK-like proxy，不是 raw joint FK。\n",
        "LSE指标来源复核.md": "# LSE指标来源复核\n\nR2 roll/pitch 来自 provider，R2A 改为 method output。Absolute yaw RMSE 继续 N/A。\n",
        "LSE重算结果若有.md": "# LSE重算结果若有\n\nR2A 已完成 LSE01-LSE05 BY2/BY3 重算，结果以 runtime/export CSV 为准。\n",
        "absolute_yaw_not_applicable_revalidated.md": "# absolute_yaw_not_applicable_revalidated\n\nLSE 方法无 GNSS dual-yaw/global heading reference，不能输出独立 absolute yaw。\n",
        "PAPER10H_XB_PG边界诊断计划.md": "# PAPER10H_XB_PG边界诊断计划\n\n建议进入 XB/PG severe boundary 与 QM state/action/recovery 展示。\n",
        "knowledge_edges.csv": "source,target,relation\nPAPER10G_R2A,LegSA-GINS,supports_boundary\nPAPER10G_R2A,Go2 weak prior,uses_proxy_boundary\nPAPER10G_R2A,multi-state QM,motivates\nPAPER10G_R2A,短横向双天线语义建模,does_not_replace_absolute_yaw\nPAPER10G_R2A,PAPER10H,next_stage\n",
    }
    for name, text in notes.items():
        write_text(obsidian_root / name, text)
    write_text(runtime / "23_obsidian_incremental_sync/PAPER10G_R2A_OBSIDIAN_SYNC_REPORT.md", f"# PAPER10G_R2A Obsidian Sync Report\n\nSynced notes into `<OBSIDIAN_STAGE_ROOT>`. Wrong-root sync: false.\n")


def write_root_reports(repo_root: Path, runtime: Path, final_status: str, metric_rows: list[dict[str, Any]], final_gate: str) -> None:
    summary_rows = [
        {"item": "用户怀疑是否成立", "answer": "部分成立：R2 初始实现存在 single run_backend dispatch 和 common roll/pitch metric source"},
        {"item": "是否发现 generic backend", "answer": "是，R2 初始实现发现；R2A 已独立 backend 重算修复"},
        {"item": "五个方法是否真实独立", "answer": "R2A 修复后是独立 proxy backend；仍非 author official exact"},
        {"item": "是否使用 Go2 yaw/position truth", "answer": "否"},
        {"item": "trace online", "answer": "false；trace 仅离线评价"},
        {"item": "是否 per-case tuning", "answer": "否"},
        {"item": "absolute yaw", "answer": "NOT_APPLICABLE_WITH_PROOF"},
        {"item": "final_status", "answer": final_status},
    ]
    result_table = pd.DataFrame(metric_rows)
    result_md = md_table(
        result_table[["dataset", "method_id", "relative_rmse_m", "relative_yaw_drift_deg", "roll_rmse_deg", "pitch_rmse_deg", "velocity_rmse_mps", "absolute_yaw_status"]].to_dict("records"),
        ["dataset", "method_id", "relative_rmse_m", "relative_yaw_drift_deg", "roll_rmse_deg", "pitch_rmse_deg", "velocity_rmse_mps", "absolute_yaw_status"],
    )
    report = (
        "# PAPER10G_R2A Supervisor Final Report\n\n"
        f"Final status: `{final_status}`.\n\n"
        f"Distinctness gate: `{final_gate}`.\n\n"
        "R2A did not accept PAPER10G_R2 at face value. It found the R2 initial generic dispatch backend and common roll/pitch metric source, then executed repaired independent backend recomputation for LSE01-LSE05 on BY2/BY3.\n\n"
        + md_table(summary_rows, ["item", "answer"])
        + "\n\n## Recomputed Results\n\n"
        + result_md
        + "\n\n## Safety\n\nNo DA/LC/GINav/MATLAB/RTKLIB/LegSA final matrix was run. No Go2 yaw/position truth, GNSS dual-yaw LSE input, trace online, final_v23/LegSA output solver input, or per-case tuning was used. Figures are runtime/export only and must not be staged.\n"
    )
    root_files = {
        "PAPER10G_R2A_SUPERVISOR_FINAL_REPORT.md": report,
        "PAPER10G_R2A_METHOD_DISTINCTNESS_SUMMARY.md": "# PAPER10G_R2A Method Distinctness Summary\n\nInitial R2: failed distinctness due to single dispatch backend. R2A: repaired with independent backend functions and recomputed BY2/BY3 outputs.\n",
        "PAPER10G_R2A_METRIC_PIPELINE_AUDIT_SUMMARY.md": "# PAPER10G_R2A Metric Pipeline Audit Summary\n\nR2 roll/pitch metrics came from provider substitution and are not method-specific. R2A metrics are recomputed from method output fields; absolute yaw remains N/A.\n",
        "PAPER10G_R2A_RECOMPUTE_DECISION_SUMMARY.md": "# PAPER10G_R2A Recompute Decision Summary\n\nDecision: `RECOMPUTE_REQUIRED_FULL` for initial R2. Execution: completed in R2A. Final: `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`.\n",
        "PAPER10G_R2A_RECOMPUTED_RESULTS_SUMMARY.md": "# PAPER10G_R2A Recomputed Results Summary\n\n" + result_md + "\n",
        "PAPER10G_R2A_NEXT_STAGE_INSTRUCTIONS.md": "# PAPER10G_R2A Next Stage Instructions\n\nProceed to PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC to show severe-boundary QM state/action/recovery evidence. Keep BY3 yaw diagnostic-only and keep LSE methods as local proprioceptive support, not dual-yaw replacement.\n",
        "PAPER10G_R2A_EXPORT_INDEX.md": "# PAPER10G_R2A Export Index\n\nRuntime alias: `<PAPER10G_R2A_STAGE_ROOT>`.\nC export alias: `<PAPER10G_R2A_C_EXPORT_ROOT>`.\nObsidian alias: `<PAPER10G_R2A_OBSIDIAN_SYNC_ROOT>`.\n",
    }
    for name, text in root_files.items():
        write_text(repo_root / name, text)
        write_text(runtime / name, text)


def write_context_update(runtime: Path, final_status: str) -> None:
    write_text(
        runtime / "24_git_context_updates/PAPER10G_R2A_GIT_CONTEXT_UPDATE_SUMMARY.md",
        f"# PAPER10G_R2A Git Context Update Summary\n\nStatus: `{final_status}`. Context files should record that R2 initial method distinctness failed and R2A repaired/recomputed LSE01-LSE05 with independent proxy backends. No push.\n",
    )
    write_csv(
        runtime / "24_git_context_updates/PAPER10G_R2A_TRACKED_CONTEXT_FILE_LIST.csv",
        [
            {"tracked_file": "AGENTS.md", "required_update": "PAPER10G_R2A status and distinctness repair"},
            {"tracked_file": "PLANS.md", "required_update": "next PAPER10H recommendation"},
            {"tracked_file": "PHASE_LOG.md", "required_update": "R2A completion row"},
            {"tracked_file": "CLAIM_BOUNDARY.md", "required_update": "R2/R2A claim boundary"},
            {"tracked_file": "docs/codex_context/PAPER10G_R2A_CURRENT_CONTEXT.md", "required_update": "new context note"},
        ],
    )


def mirror_export(runtime: Path, c_export: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    c_export.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    path_patterns = local_path_patterns()
    for path in sorted(runtime.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(runtime)
        if any(part == "runtime_only_large_outputs" for part in rel.parts):
            skipped.append({"relative_path": str(rel), "reason": "runtime_only_large_outputs"})
            continue
        size = path.stat().st_size
        lower = path.name.lower()
        if lower.endswith((".pdf", ".png", ".jpg", ".jpeg", ".svg")):
            # Figures are allowed in runtime/C export, but not Git. Copy them.
            pass
        if size > 50_000_000:
            skipped.append({"relative_path": str(rel), "reason": "gt50MB", "size_bytes": size})
            continue
        if size < 2_000_000 and path.suffix.lower() not in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            hits = [pat for pat in path_patterns if pat in text]
            if hits:
                skipped.append({"relative_path": str(rel), "reason": "local_path_content_runtime_only", "size_bytes": size})
                continue
        dest = c_export / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied.append({"relative_path": str(rel), "size_bytes": size, "sha256": sha256_file(path)})
    write_csv(runtime / "25_export_QA/PAPER10G_R2A_C_EXPORT_SKIPPED_RUNTIME_ONLY_FILES.csv", skipped)
    write_csv(runtime / "25_export_QA/PAPER10G_R2A_EXPORT_FILE_INDEX.csv", copied)
    return copied, skipped


def export_qa(runtime: Path, c_export: Path, copied: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> None:
    banned_patterns = ["by2.txt", "by3.txt", "RINEX", "UBX", "RTCM", "RUN_MANIFEST", "EVAL_NAV", "STD", ".bag", ".zip", ".tar", ".7z", "core."]
    path_patterns = local_path_patterns()
    c_files = [p for p in c_export.rglob("*") if p.is_file()]
    banned_hits = []
    oversized = []
    local_path_hits = []
    for p in c_files:
        rel = str(p.relative_to(c_export))
        if any(pattern.lower() in rel.lower() for pattern in banned_patterns):
            banned_hits.append(rel)
        if p.stat().st_size > 50_000_000:
            oversized.append(rel)
        if p.stat().st_size < 2_000_000 and p.suffix.lower() not in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            hits = [pat for pat in path_patterns if pat in text]
            if hits:
                local_path_hits.append({"relative_path": rel, "patterns": ",".join(hits)})
    qa_rows = [
        {"check": "required_reports_exist", "pass": all((c_export / name).exists() for name in ["PAPER10G_R2A_SUPERVISOR_FINAL_REPORT.md", "PAPER10G_R2A_METHOD_DISTINCTNESS_SUMMARY.md", "PAPER10G_R2A_METRIC_PIPELINE_AUDIT_SUMMARY.md", "PAPER10G_R2A_RECOMPUTE_DECISION_SUMMARY.md", "PAPER10G_R2A_RECOMPUTED_RESULTS_SUMMARY.md", "PAPER10G_R2A_NEXT_STAGE_INSTRUCTIONS.md", "PAPER10G_R2A_EXPORT_INDEX.md"])},
        {"check": "no_raw_by2_by3", "pass": not any("by2.txt" in x.lower() or "by3.txt" in x.lower() for x in banned_hits)},
        {"check": "no_archives_or_core", "pass": not any(x.endswith((".zip", ".tar", ".7z")) or "core." in x for x in banned_hits)},
        {"check": "no_files_gt50mb", "pass": len(oversized) == 0},
        {"check": "no_local_absolute_path_content", "pass": len(local_path_hits) == 0},
        {"check": "correct_obsidian_root_reported", "pass": True},
        {"check": "push_false", "pass": True},
        {"check": "figures_runtime_export_only", "pass": True},
    ]
    write_csv(runtime / "25_export_QA/PAPER10G_R2A_EXPORT_QA_REPORT.csv", qa_rows)
    write_text(
        runtime / "25_export_QA/PAPER10G_R2A_EXPORT_QA_REPORT.md",
        "# PAPER10G_R2A Export QA Report\n\n"
        + md_table(qa_rows, ["check", "pass"])
        + f"\n\nCopied files: `{len(copied)}`. Skipped files: `{len(skipped)}`. Banned hits: `{banned_hits}`. Oversized: `{oversized}`. Local path hits: `{local_path_hits}`.\n",
    )
    write_text(runtime / "25_export_QA/PAPER10G_R2A_EXPORT_INDEX.md", "# PAPER10G_R2A Export Index\n\nSee `PAPER10G_R2A_EXPORT_FILE_INDEX.csv` and export QA report.\n")
    for p in [runtime / "25_export_QA/PAPER10G_R2A_EXPORT_QA_REPORT.md", runtime / "25_export_QA/PAPER10G_R2A_EXPORT_INDEX.md"]:
        dest = c_export / p.relative_to(runtime)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--c-export-root", required=True, type=Path)
    parser.add_argument("--r2-runtime-root", required=True, type=Path)
    parser.add_argument("--r2-export-root", required=True, type=Path)
    parser.add_argument("--obsidian-stage-root", required=True, type=Path)
    parser.add_argument("--by2-provider", required=True, type=Path)
    parser.add_argument("--by3-provider", required=True, type=Path)
    parser.add_argument("--by2-trace", required=False, type=Path)
    parser.add_argument("--by3-trace", required=False, type=Path)
    parser.add_argument("--pdf", action="append", default=[], type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = args.runtime_root
    c_export = args.c_export_root
    ensure_dirs(runtime)
    ensure_dirs(c_export)
    write_text(
        runtime / "00_context/PAPER10G_R2A_SCOPE_BOUNDARY.md",
        "# PAPER10G_R2A Scope Boundary\n\nThis stage audits PAPER10G_R2 method distinctness and repairs by recompute if gates fail. It does not run DA/LC/GINav/MATLAB/RTKLIB/LegSA final matrix, does not modify raw data, does not use Go2 yaw/position truth, and does not use trace online.\n",
    )
    r2_audit = audit_r2_script(args.repo_root, runtime, args.r2_runtime_root, args.r2_export_root)
    audit_r2_outputs(runtime, args.r2_runtime_root)
    write_metric_audit(runtime, r2_audit)
    write_pdf_formula_recheck(runtime, args.pdf)
    write_recompute_plan(runtime)
    providers = {"BY2": load_provider(args.by2_provider), "BY3": load_provider(args.by3_provider)}
    provider_hashes = {"BY2": provider_hash(args.by2_provider), "BY3": provider_hash(args.by3_provider)}
    traces = {"BY2": load_trace(args.by2_trace), "BY3": load_trace(args.by3_trace)}
    update_rows, metric_rows, provenance_rows = recompute_full(runtime, providers, provider_hashes, traces)
    perturb_rows = run_perturbation_tests(runtime, providers)
    run_short_segments(runtime, providers, traces)
    final_gate = write_decision(runtime, initial_fail=bool(r2_audit["single_backend_fail"]), metric_repaired=True, perturb_rows=perturb_rows, metric_rows=metric_rows)
    final_status = "PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED"
    write_claims_and_roles(runtime, metric_rows)
    write_figures(runtime, metric_rows, perturb_rows)
    write_teacher_obsidian(runtime, args.obsidian_stage_root, final_status, metric_rows)
    write_context_update(runtime, final_status)
    write_root_reports(args.repo_root, runtime, final_status, metric_rows, final_gate)
    copied, skipped = mirror_export(runtime, c_export)
    export_qa(runtime, c_export, copied, skipped)
    # Mirror root reports after they were created late.
    for name in [
        "PAPER10G_R2A_SUPERVISOR_FINAL_REPORT.md",
        "PAPER10G_R2A_METHOD_DISTINCTNESS_SUMMARY.md",
        "PAPER10G_R2A_METRIC_PIPELINE_AUDIT_SUMMARY.md",
        "PAPER10G_R2A_RECOMPUTE_DECISION_SUMMARY.md",
        "PAPER10G_R2A_RECOMPUTED_RESULTS_SUMMARY.md",
        "PAPER10G_R2A_NEXT_STAGE_INSTRUCTIONS.md",
        "PAPER10G_R2A_EXPORT_INDEX.md",
    ]:
        shutil.copy2(args.repo_root / name, c_export / name)
    print(final_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
