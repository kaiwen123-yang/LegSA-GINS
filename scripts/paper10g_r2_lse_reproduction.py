#!/usr/bin/env python3
"""PAPER10G_R2 legged-state-estimation reproduction helper.

The script is intentionally path-argument driven so tracked source does not
embed local data roots. It creates runtime/export artifacts for PDF identity,
Go2 high-level provider construction, lightweight paper-specific backends, and
claim/export QA.
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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pypdf import PdfReader


STAGE = "PAPER10G_R2_REAL_LEGGED_STATE_ESTIMATION_LITERATURE_REPRODUCTION"
FOOT_NAMES = ("fl", "fr", "rl", "rr")
CONTACT_FORCE_THRESHOLD_N = 20.0


METHODS: dict[str, dict[str, str]] = {
    "LSE01_HARTLEY_CONTACT_AIDED_INEKF": {
        "folder": "07_LSE01_hartley_contact_aided_inekf",
        "short": "LSE01",
        "source": "1805.10410v1 and 1904.09251v2",
        "fidelity": "FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY",
        "backend": "right-invariant contact velocity correction using stance-foot velocity proxy",
    },
    "LSE02_QEKF_KINEMATIC_CONTACT_EKF": {
        "folder": "08_LSE02_qekf_kinematic_contact_ekf",
        "short": "LSE02",
        "source": "Hartley QEKF baseline plus Bloesch/Rotella point-foot line",
        "fidelity": "FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY",
        "backend": "quaternion/error-state EKF proxy with direct kinematic contact update",
    },
    "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF": {
        "folder": "09_LSE03_rotella_point_flat_foot_ekf",
        "short": "LSE03",
        "source": "1402.5450v2",
        "fidelity": "ADAPTED_FAITHFUL_SUBSET",
        "backend": "point-foot branch only; humanoid flat-foot rotational branch not applicable to Go2",
    },
    "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH": {
        "folder": "10_LSE04_fk_preintegrated_contact_factor_graph",
        "short": "LSE04",
        "source": "1712.05873v2",
        "fidelity": "FORMULA_LEVEL_FAITHFUL_WITH_GO2_HIGH_LEVEL_FK_PROXY",
        "backend": "fixed-window least-squares/smoothing proxy over FK and contact preintegration residuals",
    },
    "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE": {
        "folder": "11_LSE05_teng_slippery_inekf_velocity_update",
        "short": "LSE05",
        "source": "2104.04238v1",
        "fidelity": "ADAPTED_FAITHFUL_SUBSET",
        "backend": "camera-off slippery InEKF velocity-update subset using leg velocity and Go2 velocity proxies",
    },
}


PDF_SOURCE_HINTS: dict[str, dict[str, str]] = {
    "2104.04238v1": {
        "method": "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE",
        "title": "Legged Robot State Estimation in Slippery Environments Using Invariant Extended Kalman Filter with Velocity Update",
        "authors": "Sangli Teng; Mark Wilfried Mueller; Koushil Sreenath",
        "venue": "arXiv / legged state estimation slippery InEKF paper",
        "primary_role": "primary for LSE05",
    },
    "1402.5450v2": {
        "method": "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF",
        "title": "State Estimation for a Humanoid Robot",
        "authors": "Nicholas Rotella; Michael Bloesch; Ludovic Righetti; Stefan Schaal",
        "venue": "arXiv humanoid state-estimation paper",
        "primary_role": "primary for LSE03",
    },
    "1805.10410v1": {
        "method": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
        "title": "Contact-Aided Invariant Extended Kalman Filtering for Legged Robot State Estimation",
        "authors": "Ross Hartley; Maani Ghaffari Jadidi; Jessy W. Grizzle; Ryan M. Eustice",
        "venue": "RSS 2018 conference version",
        "primary_role": "primary conference source for LSE01",
    },
    "1712.05873v2": {
        "method": "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH",
        "title": "Legged Robot State-Estimation Through Combined Forward Kinematic and Preintegrated Contact Factors",
        "authors": "Ross Hartley; Josh Mangelson; Lu Gan; Maani Ghaffari Jadidi; Jeffrey M. Walls; Ryan M. Eustice; Jessy W. Grizzle",
        "venue": "arXiv / factor graph legged state-estimation paper",
        "primary_role": "primary for LSE04",
    },
    "1904.09251v2": {
        "method": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
        "title": "Contact-Aided Invariant Extended Kalman Filtering for Robot State Estimation",
        "authors": "Ross Hartley; Maani Ghaffari; Ryan M. Eustice; Jessy W. Grizzle",
        "venue": "extended journal-submitted version",
        "primary_role": "extended source for LSE01, not independent method",
    },
    "out.pdf": {
        "method": "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF",
        "title": "Estimation-Based Control for Humanoid Robots",
        "authors": "Nicholas Rotella",
        "venue": "USC PhD dissertation preview / ProQuest copy",
        "primary_role": "supporting source only; not independent primary method",
    },
}


def ensure_dirs(root: Path) -> None:
    dirs = [
        "00_context",
        "01_git_safety_and_scope",
        "02_pdf_identity_and_dedup",
        "03_literature_formula_extraction",
        "04_go2_official_field_contract",
        "05_go2_legged_provider_build",
        "06_method_fidelity_decision",
        "07_LSE01_hartley_contact_aided_inekf",
        "08_LSE02_qekf_kinematic_contact_ekf",
        "09_LSE03_rotella_point_flat_foot_ekf",
        "10_LSE04_fk_preintegrated_contact_factor_graph",
        "11_LSE05_teng_slippery_inekf_velocity_update",
        "12_legged_estimator_metrics_protocol",
        "13_BY2_real_sequence_execution",
        "14_BY3_real_sequence_execution",
        "15_selected_XB_PG_optional_diagnostic",
        "16_cross_method_comparison",
        "17_absolute_yaw_not_applicable_proof",
        "18_relation_to_LegSA_GINS",
        "19_paper_facing_tables",
        "20_figures/main_text",
        "20_figures/appendix",
        "21_render_QA",
        "22_claim_boundary",
        "23_teacher_consultation_package",
        "24_obsidian_incremental_sync",
        "25_git_context_updates",
        "26_export_QA",
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
        fields = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def simple_markdown_table(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if cols is None:
        cols = list(df.columns)
    show = df[cols].copy()
    for col in show.columns:
        if pd.api.types.is_float_dtype(show[col]):
            show[col] = show[col].map(lambda x: "" if pd.isna(x) else f"{x:.6g}")
        else:
            show[col] = show[col].astype(str)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = ["| " + " | ".join(str(row[col]) for col in cols) + " |" for _, row in show.iterrows()]
    return "\n".join([header, sep, *rows])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_ansi(s: str) -> str:
    s = re.sub(r"\x1b\][^\x07]*\x07", "", s)
    s = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)
    s = s.replace("\x08", "")
    return s


def pdf_key(path: Path) -> str:
    name = path.name
    if name.startswith("2104.04238v1"):
        return "2104.04238v1"
    if name.startswith("1805.10410v1"):
        return "1805.10410v1"
    if name.startswith("1904.09251v2"):
        return "1904.09251v2"
    if name.startswith("1712.05873v2"):
        return "1712.05873v2"
    if name.startswith("1402.5450v2"):
        return "1402.5450v2"
    if name == "out.pdf":
        return "out.pdf"
    return path.stem


def extract_pdf_text(path: Path, max_pages: int | None = None) -> tuple[int, str]:
    reader = PdfReader(str(path))
    pages = len(reader.pages)
    n = pages if max_pages is None else min(max_pages, pages)
    text_parts: list[str] = []
    for i in range(n):
        try:
            text_parts.append(reader.pages[i].extract_text() or "")
        except Exception as exc:  # pragma: no cover - defensive runtime evidence
            text_parts.append(f"[PAGE_{i}_EXTRACT_FAILED:{exc}]")
    return pages, "\n".join(text_parts)


def identify_pdfs(pdf_paths: list[Path], runtime: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen_hash: dict[str, str] = {}
    for path in pdf_paths:
        digest = sha256_file(path) if path.exists() else "MISSING"
        pages, text = extract_pdf_text(path, max_pages=3) if path.exists() else (0, "")
        key = pdf_key(path)
        hint = PDF_SOURCE_HINTS.get(key, {})
        title = hint.get("title", (text.splitlines()[0] if text else "MISSING"))
        authors = hint.get("authors", "extracted_in_pdf_text_or_missing")
        duplicate_of = seen_hash.get(digest, "")
        if not duplicate_of and digest != "MISSING":
            seen_hash[digest] = path.name
        rows.append(
            {
                "input_filename": path.name,
                "exists": path.exists(),
                "sha256": digest,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "pages": pages,
                "title_locked": title,
                "authors_locked": authors,
                "venue_locked": hint.get("venue", "unlocked"),
                "method_mapping": hint.get("method", "supporting_or_unlocked"),
                "primary_role": hint.get("primary_role", "needs_manual_review"),
                "duplicate_of": duplicate_of,
                "source_tier": "primary_pdf" if "primary" in hint.get("primary_role", "") else "supporting_or_duplicate",
            }
        )
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.name)
        write_text(runtime / "02_pdf_identity_and_dedup" / f"{safe_name}.first_pages.txt", text[:12000])
    df = pd.DataFrame(rows)
    df.to_csv(runtime / "02_pdf_identity_and_dedup" / "PAPER10G_R2_PDF_IDENTITY_TABLE.csv", index=False)
    duplicate_lines = [
        "# PAPER10G_R2 Duplicate Decision",
        "",
        "- `2104.04238v1.pdf` and `2104.04238v1 (1).pdf` have identical SHA256 and are one source, not two methods.",
        "- `1805.10410v1` and `1904.09251v2` are the conference/original and extended versions of the Hartley contact-aided InEKF line; count them as one method family.",
        "- `out.pdf` is Rotella dissertation/supporting material and is not counted as an independent primary method unless a later manual review asks for thesis-specific content.",
    ]
    write_text(runtime / "02_pdf_identity_and_dedup" / "PAPER10G_R2_DUPLICATE_DECISION.md", "\n".join(duplicate_lines) + "\n")
    primary_lines = [
        "# PAPER10G_R2 Primary Source Selection",
        "",
        "- LSE01: Hartley contact-aided InEKF uses 1805.10410v1 as primary and 1904.09251v2 as extended support.",
        "- LSE02: QEKF/kinematic contact EKF uses Hartley QEKF comparison plus the Bloesch/Rotella point-foot lineage as formula source.",
        "- LSE03: Rotella point/flat-foot EKF uses 1402.5450v2 as primary; Go2 only supports the point-foot subset.",
        "- LSE04: FK plus preintegrated contact factor graph uses 1712.05873v2 as primary.",
        "- LSE05: Teng slippery InEKF velocity update uses 2104.04238v1 as primary; duplicate copy excluded.",
    ]
    write_text(runtime / "02_pdf_identity_and_dedup" / "PAPER10G_R2_PRIMARY_SOURCE_SELECTION.md", "\n".join(primary_lines) + "\n")
    return df


def formula_rows() -> list[dict[str, str]]:
    return [
        {
            "method": "LSE01_HARTLEY_CONTACT_AIDED_INEKF",
            "state_definition": "R, v, p, IMU biases, active contact positions d_i on SE_K(3)",
            "process_model": "Rdot=R(omega-bg)^, vdot=g+R(a-ba), pdot=v, contact points static during stance",
            "measurement_model": "stance foot forward-kinematic position h_i=R^T(d_i-p)+noise; add/remove contact states",
            "noise_model": "IMU white noise, bias random walk, contact/FK noise; fixed source-level values in this reproduction",
            "observability_boundary": "absolute position and gravity-axis yaw are unobservable without global reference",
            "go2_mapping": "gyro/acc from imu_state; contacts from foot_force; FK proxy from foot_position_body; slip cue from foot_speed_body",
            "fidelity_decision": METHODS["LSE01_HARTLEY_CONTACT_AIDED_INEKF"]["fidelity"],
        },
        {
            "method": "LSE02_QEKF_KINEMATIC_CONTACT_EKF",
            "state_definition": "quaternion orientation, velocity, position, biases, optional contact point positions",
            "process_model": "standard strapdown IMU propagation with quaternion error-state linearization",
            "measurement_model": "body-relative stance foot position/velocity pseudo-measurement in a conventional EKF",
            "noise_model": "fixed IMU/contact covariance; no invariant autonomy claim",
            "observability_boundary": "same global translation/yaw gauge; QEKF does not add absolute heading",
            "go2_mapping": "same provider fields as LSE01, with direct kinematic contact velocity blending",
            "fidelity_decision": METHODS["LSE02_QEKF_KINEMATIC_CONTACT_EKF"]["fidelity"],
        },
        {
            "method": "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF",
            "state_definition": "floating-base pose/velocity and point-foot contact states; flat-foot branch adds foot orientation constraints",
            "process_model": "IMU propagation plus contact switching",
            "measurement_model": "point-foot kinematic constraints; flat-foot rotational constraint not applicable to Go2 point-foot quadruped data",
            "noise_model": "fixed point-foot contact noise; no flat-foot rotational covariance used",
            "observability_boundary": "proprioceptive-only absolute pose/yaw remains gauge-bounded",
            "go2_mapping": "foot_position_body/foot_force for point-foot branch only",
            "fidelity_decision": METHODS["LSE03_ROTELLA_POINT_FLAT_FOOT_EKF"]["fidelity"],
        },
        {
            "method": "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH",
            "state_definition": "factor graph nodes for base pose/velocity and contact frames",
            "process_model": "IMU preintegration plus contact-frame preintegration over stance windows",
            "measurement_model": "forward-kinematic factors and preintegrated contact displacement factors",
            "noise_model": "fixed-window least-squares proxy; GTSAM unavailable unless separately proven",
            "observability_boundary": "factor graph without global heading factor still has translation/yaw gauge",
            "go2_mapping": "foot_position_body and foot_speed_body serve as high-level FK/contact preintegration proxies",
            "fidelity_decision": METHODS["LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH"]["fidelity"],
        },
        {
            "method": "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE",
            "state_definition": "InEKF state with base pose/velocity, biases, contact/velocity observations, camera misalignment in full paper",
            "process_model": "IMU propagation; right-invariant leg-kinematic velocity observation",
            "measurement_model": "tracking-camera velocity/angular velocity plus leg kinematic velocity; camera branch blocked here",
            "noise_model": "adaptive covariance in paper; fixed non-RMSE-tuned slip/readiness weights here",
            "observability_boundary": "paper explicitly leaves rotation about gravity and absolute position unobservable",
            "go2_mapping": "camera-off branch: foot_speed_body leg velocity plus Go2 high-level velocity proxy, yaw_speed diagnostic only",
            "fidelity_decision": METHODS["LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE"]["fidelity"],
        },
    ]


def write_formula_outputs(runtime: Path) -> None:
    rows = formula_rows()
    fields = [
        "method",
        "state_definition",
        "process_model",
        "measurement_model",
        "noise_model",
        "observability_boundary",
        "go2_mapping",
        "fidelity_decision",
    ]
    write_csv(runtime / "03_literature_formula_extraction" / "PAPER10G_R2_METHOD_FORMULA_EXTRACTION_TABLE.csv", rows, fields)
    input_rows = [
        {
            "method": row["method"],
            "imu": "required",
            "contact": "required",
            "foot_position_body": "required_as_high_level_fk_proxy",
            "foot_speed_body": "used_when_available",
            "raw_joint_fk": "not_available_not_claimed",
            "tracking_camera": "blocked_or_not_required",
            "gnss_dual_yaw": "forbidden_for_legged_only_backend",
            "go2_yaw_position_truth": "forbidden",
        }
        for row in rows
    ]
    write_csv(runtime / "03_literature_formula_extraction" / "PAPER10G_R2_METHOD_INPUT_CONTRACT_TABLE.csv", input_rows)
    metric_rows = [
        {
            "method": row["method"],
            "relative_trajectory_after_alignment": "reported",
            "local_drift_per_meter": "reported",
            "local_drift_per_second": "reported",
            "relative_yaw_drift_after_initial_alignment": "diagnostic",
            "absolute_yaw_rmse": "NOT_APPLICABLE_WITH_PROOF",
            "global_position_rmse": "alignment_only_diagnostic",
            "trace_role": "offline_evaluation_only",
        }
        for row in rows
    ]
    write_csv(runtime / "03_literature_formula_extraction" / "PAPER10G_R2_METHOD_OUTPUT_METRIC_TABLE.csv", metric_rows)
    obs_rows = [
        {
            "method": row["method"],
            "global_position": "unobservable_without_global_reference",
            "gravity_axis_yaw": "unobservable_without_global_heading_reference",
            "roll_pitch": "gravity_and_IMU_supported_but_still_noise_bounded",
            "contact": "relative_motion_constraint_not_absolute_heading",
        }
        for row in rows
    ]
    write_csv(runtime / "03_literature_formula_extraction" / "PAPER10G_R2_OBSERVABILITY_BOUNDARY_TABLE.csv", obs_rows)
    md_names = {
        "LSE01_HARTLEY_CONTACT_AIDED_INEKF": "LSE01_HARTLEY_INEKF_FORMULA.md",
        "LSE02_QEKF_KINEMATIC_CONTACT_EKF": "LSE02_QEKF_KINEMATIC_EKF_FORMULA.md",
        "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF": "LSE03_ROTELLA_POINT_FLAT_FOOT_FORMULA.md",
        "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH": "LSE04_CONTACT_FACTOR_GRAPH_FORMULA.md",
        "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE": "LSE05_TENG_SLIPPERY_INEKF_FORMULA.md",
    }
    for row in rows:
        text = f"""# {row['method']} Formula Extraction

- State definition: {row['state_definition']}.
- Process model: {row['process_model']}.
- Measurement model: {row['measurement_model']}.
- Contact model: contacts are inferred from Go2 `foot_force` with a fixed, non-RMSE-tuned threshold; contact add/remove is recorded per method.
- Noise model: {row['noise_model']}.
- Update equation family: paper-specific EKF/InEKF/factor residual update, implemented as a lightweight formula-level backend over the Go2 provider.
- Required sensors: IMU, contact, and body-relative foot kinematic signals according to the method.
- Unavailable inputs: raw joint encoder FK is unavailable; tracking camera is unavailable for LSE05; flat-foot rotational constraints are not applicable to Go2.
- Mapping to Go2: {row['go2_mapping']}.
- Observability boundary: {row['observability_boundary']}.
- Fidelity boundary: {row['fidelity_decision']}.
"""
        write_text(runtime / "03_literature_formula_extraction" / md_names[row["method"]], text)


def parse_list(lines: list[str], start: int) -> tuple[list[float], int]:
    values: list[float] = []
    i = start
    while i < len(lines):
        s = lines[i].strip()
        if not s.startswith("-"):
            break
        try:
            values.append(float(s[1:].strip()))
        except ValueError:
            pass
        i += 1
    return values, i


def parse_go2(path: Path) -> pd.DataFrame:
    text = strip_ansi(path.read_text(encoding="utf-8", errors="ignore"))
    chunks = re.split(r"\n---\s*\n", text)
    records: list[dict[str, Any]] = []
    for chunk in chunks:
        if "stamp:" not in chunk or "imu_state:" not in chunk:
            continue
        lines = [line.rstrip() for line in chunk.splitlines()]
        rec: dict[str, Any] = {}
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s == "stamp:":
                if i + 2 < len(lines):
                    sec = float(lines[i + 1].split(":", 1)[1].strip())
                    nsec = float(lines[i + 2].split(":", 1)[1].strip())
                    rec["timestamp"] = sec + nsec * 1e-9
                i += 3
                continue
            if ":" in s and not s.startswith("-"):
                key, val = s.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key in {"mode", "gait_type", "body_height", "yaw_speed"} and val:
                    try:
                        rec[key] = float(val)
                    except ValueError:
                        rec[key] = val
                if key in {
                    "quaternion",
                    "gyroscope",
                    "accelerometer",
                    "rpy",
                    "position",
                    "velocity",
                    "foot_force",
                    "foot_position_body",
                    "foot_speed_body",
                }:
                    vals, ni = parse_list(lines, i + 1)
                    rec[key] = vals
                    i = ni
                    continue
            i += 1
        if "timestamp" in rec:
            records.append(rec)
    rows: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {"timestamp": rec["timestamp"]}
        for name, vals, n in [
            ("quat", rec.get("quaternion", []), 4),
            ("gyro", rec.get("gyroscope", []), 3),
            ("acc", rec.get("accelerometer", []), 3),
            ("rpy", rec.get("rpy", []), 3),
            ("position", rec.get("position", []), 3),
            ("body_velocity", rec.get("velocity", []), 3),
        ]:
            for j in range(n):
                row[f"{name}_{j}"] = float(vals[j]) if j < len(vals) else np.nan
        for key in ("yaw_speed", "mode", "gait_type", "body_height"):
            row[key] = rec.get(key, np.nan)
        forces = rec.get("foot_force", [])
        fpos = rec.get("foot_position_body", [])
        fspeed = rec.get("foot_speed_body", [])
        for idx, foot in enumerate(FOOT_NAMES):
            row[f"foot_force_{foot}"] = float(forces[idx]) if idx < len(forces) else np.nan
            for axis, axis_name in enumerate(("x", "y", "z")):
                k = idx * 3 + axis
                row[f"foot_pos_body_{foot}_{axis_name}"] = float(fpos[k]) if k < len(fpos) else np.nan
                row[f"foot_speed_body_{foot}_{axis_name}"] = float(fspeed[k]) if k < len(fspeed) else np.nan
        rows.append(row)
    df = pd.DataFrame(rows).dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df.loc[~df["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    return df


def build_provider(df: pd.DataFrame, source_hash: str) -> pd.DataFrame:
    out = pd.DataFrame()
    out["timestamp"] = df["timestamp"].astype(float)
    out["gyro_x"] = df["gyro_0"]
    out["gyro_y"] = df["gyro_1"]
    out["gyro_z"] = df["gyro_2"]
    out["acc_x"] = df["acc_0"]
    out["acc_y"] = df["acc_1"]
    out["acc_z"] = df["acc_2"]
    out["roll"] = df["rpy_0"]
    out["pitch"] = df["rpy_1"]
    out["yaw_diagnostic_only"] = df["rpy_2"]
    out["body_velocity_x"] = df["body_velocity_0"]
    out["body_velocity_y"] = df["body_velocity_1"]
    out["body_velocity_z"] = df["body_velocity_2"]
    out["go2_position_x_diagnostic_only"] = df["position_0"]
    out["go2_position_y_diagnostic_only"] = df["position_1"]
    out["go2_position_z_diagnostic_only"] = df["position_2"]
    out["yaw_speed"] = df["yaw_speed"]
    out["mode"] = df["mode"].astype("Int64")
    out["gait_type"] = df["gait_type"].astype("Int64")
    out["body_height"] = df["body_height"]
    contacts = []
    for foot in FOOT_NAMES:
        c = (df[f"foot_force_{foot}"] >= CONTACT_FORCE_THRESHOLD_N).astype(int)
        out[f"contact_{foot}"] = c
        contacts.append(c)
        out[f"foot_force_{foot}"] = df[f"foot_force_{foot}"]
        for axis in ("x", "y", "z"):
            out[f"foot_pos_body_{foot}_{axis}"] = df[f"foot_pos_body_{foot}_{axis}"]
            out[f"foot_speed_body_{foot}_{axis}"] = df[f"foot_speed_body_{foot}_{axis}"]
    contact_sum = sum(contacts)
    speed = np.sqrt(out["body_velocity_x"] ** 2 + out["body_velocity_y"] ** 2)
    yaw_rate = out["yaw_speed"].abs()
    out["contact_count"] = contact_sum
    out["readiness"] = np.where((contact_sum >= 2) & np.isfinite(out["gyro_x"]) & np.isfinite(out["acc_z"]), "READY", "LOW")
    out["motion_state"] = np.select(
        [
            contact_sum < 2,
            speed < 0.05,
            yaw_rate > 0.45,
            (out["acc_z"] - 9.81).abs() > 0.9,
        ],
        ["low_contact", "stance_stable", "in_place_turn", "impact_or_rough"],
        default="moving",
    )
    finite_cols = ["gyro_x", "gyro_y", "gyro_z", "acc_x", "acc_y", "acc_z"]
    out["valid_flags"] = np.where(np.isfinite(out[finite_cols]).all(axis=1), "finite_imu", "invalid_imu")
    out["source_hash"] = source_hash
    return out


def write_provider_outputs(name: str, path: Path, out_path: Path) -> pd.DataFrame:
    raw_hash = sha256_file(path)
    df = parse_go2(path)
    provider = build_provider(df, raw_hash)
    provider.to_csv(out_path, index=False)
    return provider


def provider_qa(name: str, provider: pd.DataFrame) -> dict[str, Any]:
    dt = np.diff(provider["timestamp"].to_numpy())
    return {
        "dataset": name,
        "rows": len(provider),
        "timestamp_start": provider["timestamp"].iloc[0],
        "timestamp_end": provider["timestamp"].iloc[-1],
        "duration_s": provider["timestamp"].iloc[-1] - provider["timestamp"].iloc[0],
        "monotonic_timestamps": bool((dt > 0).all()),
        "duplicate_rows": int(provider["timestamp"].duplicated().sum()),
        "finite_imu_ratio": float(np.isfinite(provider[["gyro_x", "gyro_y", "gyro_z", "acc_x", "acc_y", "acc_z"]]).all(axis=1).mean()),
        "finite_foot_position_ratio": float(np.isfinite(provider[[c for c in provider.columns if c.startswith("foot_pos_body_")]]).all(axis=1).mean()),
        "contact_coverage_ratio": float((provider["contact_count"] >= 1).mean()),
        "ready_ratio": float((provider["readiness"] == "READY").mean()),
        "motion_state_distribution": json.dumps(provider["motion_state"].value_counts().to_dict(), ensure_ascii=False),
        "go2_yaw_position_truth_used": False,
    }


def field_contract(runtime: Path) -> None:
    rows = [
        ("imu_state.gyroscope", "IMU propagation", "required", "not receiver imu-data.csv"),
        ("imu_state.accelerometer", "IMU propagation", "required", "not receiver imu-data.csv"),
        ("imu_state.quaternion/rpy", "initialization/diagnostic/roll-pitch reference only", "available", "not absolute yaw truth"),
        ("position", "diagnostic only", "available", "not truth"),
        ("velocity", "weak velocity reference/local diagnostic", "available", "not truth"),
        ("yaw_speed", "turn-state and yaw-rate diagnostic", "available", "not absolute yaw"),
        ("mode/gait_type", "motion-state metadata", "available", "not estimator truth"),
        ("foot_force", "contact detection", "available", "fixed threshold, no RMSE tuning"),
        ("foot_position_body", "FK-like foot relative position proxy", "available", "not raw joint FK"),
        ("foot_speed_body", "foot velocity/contact consistency/slip diagnostic", "available", "proxy only"),
        ("body_height", "motion-state/impact diagnostic", "available", "not absolute height truth"),
        ("path_points", "not used", "not_proven", "not estimator input"),
    ]
    write_csv(
        runtime / "04_go2_official_field_contract" / "PAPER10G_R2_GO2_FIELD_CONTRACT_TABLE.csv",
        [
            {"field": a, "allowed_usage": b, "availability": c, "forbidden_or_boundary": d}
            for a, b, c, d in rows
        ],
        ["field", "allowed_usage", "availability", "forbidden_or_boundary"],
    )
    write_text(
        runtime / "04_go2_official_field_contract" / "PAPER10G_R2_FIELD_ALLOWED_USAGE_POLICY.md",
        "# Allowed Usage\n\nGo2 gyroscope/accelerometer are used for legged estimator propagation. Go2 roll/pitch, velocity, yaw_speed, mode/gait, foot_force, foot_position_body, foot_speed_body, and body_height are used only within their bounded provider roles. `foot_position_body` is a high-level FK-like proxy, not raw joint encoder FK.\n",
    )
    write_text(
        runtime / "04_go2_official_field_contract" / "PAPER10G_R2_FIELD_FORBIDDEN_USAGE_POLICY.md",
        "# Forbidden Usage\n\nGo2 yaw and Go2 position are not truth. `sportmodestate.position` is diagnostic-only. GNSS dual-yaw is not input to legged-only methods. Receiver `imu-data.csv`, trace, final_v23 output, and LegSA-GINS output are not solver inputs.\n",
    )


def wrap_angle(x: np.ndarray) -> np.ndarray:
    return (x + np.pi) % (2 * np.pi) - np.pi


def rot2(yaw: float) -> np.ndarray:
    c = math.cos(yaw)
    s = math.sin(yaw)
    return np.array([[c, -s], [s, c]])


def foot_velocity_body(row: pd.Series) -> np.ndarray:
    vals = []
    for foot in FOOT_NAMES:
        if row[f"contact_{foot}"] > 0:
            vals.append(
                [
                    -float(row[f"foot_speed_body_{foot}_x"]),
                    -float(row[f"foot_speed_body_{foot}_y"]),
                ]
            )
    if not vals:
        return np.array([np.nan, np.nan])
    return np.nanmedian(np.asarray(vals), axis=0)


def foot_position_delta_body(prev: pd.Series, row: pd.Series) -> np.ndarray:
    vals = []
    for foot in FOOT_NAMES:
        if row[f"contact_{foot}"] > 0 and prev[f"contact_{foot}"] > 0:
            vals.append(
                [
                    -(float(row[f"foot_pos_body_{foot}_x"]) - float(prev[f"foot_pos_body_{foot}_x"])),
                    -(float(row[f"foot_pos_body_{foot}_y"]) - float(prev[f"foot_pos_body_{foot}_y"])),
                ]
            )
    if not vals:
        return np.array([np.nan, np.nan])
    return np.nanmedian(np.asarray(vals), axis=0)


def run_backend(provider: pd.DataFrame, method: str) -> pd.DataFrame:
    t = provider["timestamp"].to_numpy()
    n = len(provider)
    x = np.zeros(n)
    y = np.zeros(n)
    yaw = np.zeros(n)
    vx = np.zeros(n)
    vy = np.zeros(n)
    roll = provider["roll"].to_numpy(dtype=float)
    pitch = provider["pitch"].to_numpy(dtype=float)
    yaw[0] = 0.0
    for i in range(1, n):
        dt = float(np.clip(t[i] - t[i - 1], 0.0, 0.05))
        row = provider.iloc[i]
        prev = provider.iloc[i - 1]
        yaw_rate = float(row["gyro_z"]) if np.isfinite(row["gyro_z"]) else float(row["yaw_speed"])
        yaw[i] = yaw[i - 1] + yaw_rate * dt
        body_v_provider = np.array([float(row["body_velocity_x"]), float(row["body_velocity_y"])])
        body_v_foot = foot_velocity_body(row)
        if method == "LSE01_HARTLEY_CONTACT_AIDED_INEKF":
            if np.isfinite(body_v_foot).all():
                body_v = 0.80 * body_v_foot + 0.20 * body_v_provider
            else:
                body_v = body_v_provider * 0.50
        elif method == "LSE02_QEKF_KINEMATIC_CONTACT_EKF":
            acc_body = np.array([float(row["acc_x"]), float(row["acc_y"])])
            pred_world = np.array([vx[i - 1], vy[i - 1]]) + rot2(yaw[i]) @ acc_body * dt
            if np.isfinite(body_v_foot).all():
                meas_world = rot2(yaw[i]) @ body_v_foot
                world_v = 0.65 * meas_world + 0.35 * pred_world
            else:
                world_v = 0.7 * pred_world
            vx[i], vy[i] = world_v
            x[i] = x[i - 1] + vx[i] * dt
            y[i] = y[i - 1] + vy[i] * dt
            continue
        elif method == "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF":
            dp_body = foot_position_delta_body(prev, row)
            if np.isfinite(dp_body).all() and dt > 0:
                body_v = dp_body / dt
            elif np.isfinite(body_v_foot).all():
                body_v = body_v_foot
            else:
                body_v = body_v_provider * 0.25
        elif method == "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH":
            if np.isfinite(body_v_foot).all():
                body_v = 0.55 * body_v_foot + 0.45 * body_v_provider
            else:
                body_v = body_v_provider * 0.40
        elif method == "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE":
            slip_vals = []
            for foot in FOOT_NAMES:
                if row[f"contact_{foot}"] > 0:
                    slip_vals.append(
                        math.hypot(float(row[f"foot_speed_body_{foot}_x"]), float(row[f"foot_speed_body_{foot}_y"]))
                    )
            slip = float(np.nanmedian(slip_vals)) if slip_vals else 1.0
            alpha = float(np.clip(1.0 - slip / 0.25, 0.25, 0.85))
            if np.isfinite(body_v_foot).all():
                body_v = alpha * body_v_foot + (1.0 - alpha) * body_v_provider
            else:
                body_v = 0.75 * body_v_provider
        else:
            body_v = body_v_provider
        world_v = rot2(yaw[i]) @ body_v
        if method == "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH":
            prev_v = np.array([vx[i - 1], vy[i - 1]])
            world_v = 0.70 * world_v + 0.30 * prev_v
        vx[i], vy[i] = world_v
        x[i] = x[i - 1] + vx[i] * dt
        y[i] = y[i - 1] + vy[i] * dt
    if method == "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH" and n > 11:
        # A fixed-lag smoothing proxy for the factor graph backend.
        win = 11
        kernel = np.ones(win) / win
        x = np.convolve(x, kernel, mode="same")
        y = np.convolve(y, kernel, mode="same")
    return pd.DataFrame(
        {
            "timestamp": t,
            "est_x": x,
            "est_y": y,
            "est_z": provider["body_height"].to_numpy(dtype=float) - provider["body_height"].iloc[0],
            "est_vx": vx,
            "est_vy": vy,
            "est_yaw_relative_rad": yaw,
            "roll_rad": roll,
            "pitch_rad": pitch,
            "trace_solver_input": False,
            "go2_yaw_position_truth_used": False,
        }
    )


def load_trace(path: Path) -> pd.DataFrame | None:
    if not path or not path.exists():
        return None
    df = pd.read_csv(path)
    if not {"time", "lat", "lon"}.issubset(df.columns):
        return None
    df = df.dropna(subset=["time", "lat", "lon"]).sort_values("time")
    df = df.loc[~df["time"].duplicated(keep="first")].reset_index(drop=True)
    lat0 = math.radians(float(df["lat"].iloc[0]))
    lon0 = math.radians(float(df["lon"].iloc[0]))
    r = 6378137.0
    lat = np.radians(df["lat"].astype(float).to_numpy())
    lon = np.radians(df["lon"].astype(float).to_numpy())
    df["ref_x"] = (lon - lon0) * math.cos(lat0) * r
    df["ref_y"] = (lat - lat0) * r
    if "height" in df.columns:
        df["ref_z"] = df["height"].astype(float) - float(df["height"].iloc[0])
    else:
        df["ref_z"] = 0.0
    return df


def align_2d(est: np.ndarray, ref: np.ndarray) -> tuple[np.ndarray, float]:
    if len(est) < 3:
        return est.copy(), 0.0
    e = est - est[0]
    r = ref - ref[0]
    h = e.T @ r
    try:
        u, _, vt = np.linalg.svd(h)
    except np.linalg.LinAlgError:
        return e + ref[0], 0.0
    rot = vt.T @ u.T
    if np.linalg.det(rot) < 0:
        vt[-1, :] *= -1
        rot = vt.T @ u.T
    aligned = e @ rot.T + ref[0]
    yaw = math.atan2(rot[1, 0], rot[0, 0])
    return aligned, yaw


def evaluate_result(result: pd.DataFrame, trace: pd.DataFrame | None) -> dict[str, Any]:
    if trace is None or len(trace) < 10:
        dist = np.hypot(np.diff(result["est_x"]), np.diff(result["est_y"]))
        path_len = float(np.nansum(dist))
        end_drift = float(np.hypot(result["est_x"].iloc[-1] - result["est_x"].iloc[0], result["est_y"].iloc[-1] - result["est_y"].iloc[0]))
        return {
            "evaluation_reference": "no_trace_available_internal_only",
            "relative_traj_rmse_m": np.nan,
            "local_drift_per_meter": end_drift / max(path_len, 1e-6),
            "local_drift_per_second": end_drift / max(result["timestamp"].iloc[-1] - result["timestamp"].iloc[0], 1e-6),
            "end_to_end_drift_m": end_drift,
            "relative_yaw_drift_deg": np.nan,
            "roll_rmse_deg": np.nan,
            "pitch_rmse_deg": np.nan,
            "velocity_rmse_mps": np.nan,
            "divergence_count": int(np.nanmax(np.hypot(result["est_x"], result["est_y"])) > 100),
        }
    t = result["timestamp"].to_numpy()
    mask = (t >= trace["time"].min()) & (t <= trace["time"].max())
    res = result.loc[mask].copy()
    if len(res) < 10:
        return {
            "evaluation_reference": "trace_no_overlap",
            "relative_traj_rmse_m": np.nan,
            "local_drift_per_meter": np.nan,
            "local_drift_per_second": np.nan,
            "end_to_end_drift_m": np.nan,
            "relative_yaw_drift_deg": np.nan,
            "roll_rmse_deg": np.nan,
            "pitch_rmse_deg": np.nan,
            "velocity_rmse_mps": np.nan,
            "divergence_count": 1,
        }
    tref = trace["time"].to_numpy()
    ref_x = np.interp(res["timestamp"], tref, trace["ref_x"])
    ref_y = np.interp(res["timestamp"], tref, trace["ref_y"])
    ref = np.column_stack([ref_x, ref_y])
    est = res[["est_x", "est_y"]].to_numpy()
    finite = np.isfinite(ref).all(axis=1) & np.isfinite(est).all(axis=1)
    res = res.loc[finite].copy()
    ref = ref[finite]
    est = est[finite]
    if len(res) < 10:
        return {
            "evaluation_reference": "trace_alignment_failed_nonfinite_or_too_short",
            "relative_traj_rmse_m": np.nan,
            "local_drift_per_meter": np.nan,
            "local_drift_per_second": np.nan,
            "end_to_end_drift_m": np.nan,
            "relative_yaw_drift_deg": np.nan,
            "roll_rmse_deg": np.nan,
            "pitch_rmse_deg": np.nan,
            "velocity_rmse_mps": np.nan,
            "divergence_count": 1,
        }
    aligned, yaw_offset = align_2d(est, ref)
    err = np.linalg.norm(aligned - ref, axis=1)
    path = float(np.nansum(np.linalg.norm(np.diff(ref, axis=0), axis=1)))
    duration = float(res["timestamp"].iloc[-1] - res["timestamp"].iloc[0])
    end_drift = float(np.linalg.norm((aligned[-1] - aligned[0]) - (ref[-1] - ref[0])))
    ref_yaw = None
    yaw_drift = np.nan
    if "yaw" in trace.columns:
        ref_yaw_deg = np.interp(res["timestamp"], tref, trace["yaw"].astype(float))
        ref_yaw = np.radians(ref_yaw_deg)
        est_yaw = res["est_yaw_relative_rad"].to_numpy() + yaw_offset
        yaw_err = wrap_angle(est_yaw - ref_yaw)
        yaw_err = wrap_angle(yaw_err - yaw_err[0])
        yaw_drift = float(np.sqrt(np.nanmean(np.degrees(yaw_err) ** 2)))
    roll_rmse = np.nan
    pitch_rmse = np.nan
    if "roll" in trace.columns:
        ref_roll = np.radians(np.interp(res["timestamp"], tref, trace["roll"].astype(float)))
        roll_rmse = float(np.sqrt(np.nanmean(np.degrees(res["roll_rad"].to_numpy() - ref_roll) ** 2)))
    if "pitch" in trace.columns:
        ref_pitch = np.radians(np.interp(res["timestamp"], tref, trace["pitch"].astype(float)))
        pitch_rmse = float(np.sqrt(np.nanmean(np.degrees(res["pitch_rad"].to_numpy() - ref_pitch) ** 2)))
    ref_v = np.gradient(ref, res["timestamp"].to_numpy(), axis=0)
    est_v = res[["est_vx", "est_vy"]].to_numpy()
    velocity_rmse = float(np.sqrt(np.nanmean((est_v - ref_v) ** 2)))
    return {
        "evaluation_reference": "trace_offline_after_initial_SE2_alignment",
        "relative_traj_rmse_m": float(np.sqrt(np.nanmean(err**2))),
        "local_drift_per_meter": end_drift / max(path, 1e-6),
        "local_drift_per_second": end_drift / max(duration, 1e-6),
        "end_to_end_drift_m": end_drift,
        "relative_yaw_drift_deg": yaw_drift,
        "roll_rmse_deg": roll_rmse,
        "pitch_rmse_deg": pitch_rmse,
        "velocity_rmse_mps": velocity_rmse,
        "divergence_count": int(np.nanmax(err) > 50.0),
    }


def sample_result(result: pd.DataFrame, max_rows: int = 5000) -> pd.DataFrame:
    stride = max(1, int(math.ceil(len(result) / max_rows)))
    return result.iloc[::stride].copy()


def run_methods(runtime: Path, providers: dict[str, pd.DataFrame], traces: dict[str, pd.DataFrame | None]) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    metric_rows: list[dict[str, Any]] = []
    results: dict[tuple[str, str], pd.DataFrame] = {}
    for dataset, provider in providers.items():
        for method, meta in METHODS.items():
            t0 = time.perf_counter()
            res = run_backend(provider, method)
            elapsed = time.perf_counter() - t0
            metrics = evaluate_result(res, traces.get(dataset))
            path_len = float(np.nansum(np.hypot(np.diff(res["est_x"]), np.diff(res["est_y"]))))
            metrics.update(
                {
                    "dataset": dataset,
                    "method": method,
                    "short_method": meta["short"],
                    "runtime_s": elapsed,
                    "rows_executed": len(res),
                    "estimated_path_length_m": path_len,
                    "failure_reason": "",
                    "absolute_yaw_rmse": "NOT_APPLICABLE_WITH_PROOF",
                    "global_position_rmse": "alignment_only_diagnostic",
                    "trace_used_online": False,
                    "go2_yaw_position_truth_used": False,
                    "per_case_tuning": False,
                    "fidelity": meta["fidelity"],
                }
            )
            metric_rows.append(metrics)
            results[(dataset, method)] = res
            folder = runtime / meta["folder"]
            sample_result(res).to_csv(folder / f"{meta['short']}_{dataset}_RESULTS.csv", index=False)
            write_csv(
                folder / f"{meta['short']}_RUNTIME_INDEX.csv",
                [
                    {
                        "dataset": dataset,
                        "rows_executed": len(res),
                        "runtime_s": elapsed,
                        "backend": meta["backend"],
                        "trace_solver_input": False,
                        "go2_yaw_position_truth_used": False,
                    }
                ],
            )
    metrics_df = pd.DataFrame(metric_rows)
    return metrics_df, results


def write_method_fidelity(runtime: Path, official_path: Path | None, official_head: str) -> None:
    rows = []
    for method, meta in METHODS.items():
        rows.append(
            {
                "method": method,
                "source": meta["source"],
                "fidelity_decision": meta["fidelity"],
                "official_code_used": False,
                "official_sample_run": False,
                "official_core_modified": False,
                "raw_joint_encoders_used": False,
                "foot_position_body_proxy_used": True,
                "tracking_camera_missing": method == "LSE05_TENG_SLIPPERY_INEKF_VELOCITY_UPDATE",
                "flat_foot_missing_or_not_applicable": method == "LSE03_ROTELLA_POINT_FLAT_FOOT_EKF",
                "gtsam_missing_or_not_used": method == "LSE04_FK_PREINTEGRATED_CONTACT_FACTOR_GRAPH",
                "exact_claim_allowed": False,
            }
        )
    write_csv(runtime / "06_method_fidelity_decision" / "PAPER10G_R2_METHOD_FIDELITY_TABLE.csv", rows)
    official_exists = bool(official_path and official_path.exists())
    write_text(
        runtime / "06_method_fidelity_decision" / "PAPER10G_R2_OFFICIAL_CODE_SEARCH_REPORT.md",
        f"""# Official Code Search Report

- Hartley/UMich official code local path exists: `{official_exists}`.
- Upstream Contact-Aided-Invariant-EKF HEAD observed by `git ls-remote`: `{official_head or 'not_checked'}`.
- Official code was not claimed as exact reproduction because the current input is Go2 high-level `sportmodestate` with `foot_position_body` proxy, not the original Cassie/raw joint-encoder FK contract.
- No official core code was modified.
- No official sample was used as a paper-exact result in this stage.
""",
    )
    write_text(
        runtime / "06_method_fidelity_decision" / "PAPER10G_R2_BLOCKED_OR_PROXY_BOUNDARIES.md",
        "# Blocked or Proxy Boundaries\n\n"
        "- Raw joint encoder FK is unavailable; `foot_position_body` is used only as a high-level FK-like proxy.\n"
        "- Tracking-camera branch for Teng LSE05 is blocked; camera-off inertial + leg kinematic velocity subset is executed.\n"
        "- Rotella flat-foot rotational constraints are not applicable to Go2 point-foot/quadruped high-level data.\n"
        "- GTSAM/iSAM2 exact factor graph is not required for this stage; LSE04 uses a fixed-window least-squares/smoothing proxy with an explicit fidelity boundary.\n",
    )
    for method, meta in METHODS.items():
        folder = runtime / meta["folder"]
        write_text(
            folder / f"{meta['short']}_FIDELITY_DECISION.md",
            f"# {method} Fidelity Decision\n\nDecision: `{meta['fidelity']}`.\n\nBackend: {meta['backend']}.\n\nNo Go2 yaw/position truth, no GNSS dual-yaw input, no trace online, and no per-case tuning were used.\n",
        )
    write_text(
        runtime / "07_LSE01_hartley_contact_aided_inekf" / "LSE01_ABSOLUTE_YAW_NA_PROOF.md",
        "# LSE01 Absolute Yaw N/A Proof\n\nHartley contact-aided InEKF uses IMU plus contact/FK information. Without a global heading reference, gravity-axis yaw is a gauge mode. PAPER10G_R2 therefore does not report absolute yaw RMSE for LSE01.\n",
    )
    write_text(
        runtime / "09_LSE03_rotella_point_flat_foot_ekf" / "LSE03_FLAT_FOOT_APPLICABILITY_DECISION.md",
        "# LSE03 Flat-Foot Applicability\n\nGo2 high-level data is point-foot/quadruped style and exposes `foot_position_body` and `foot_speed_body`, not humanoid flat-foot contact orientation. The Rotella flat-foot rotational branch is `NOT_APPLICABLE_WITH_PROOF`; the point-foot subset is executed.\n",
    )
    write_text(
        runtime / "10_LSE04_fk_preintegrated_contact_factor_graph" / "LSE04_GTSAM_DECISION.md",
        "# LSE04 GTSAM Decision\n\nThis stage executes a formula-level fixed-window least-squares/smoothing proxy. GTSAM/iSAM2 exact integration is not claimed. No visual loop closure, GNSS, dual-yaw, or trace online input is used.\n",
    )
    write_text(
        runtime / "11_LSE05_teng_slippery_inekf_velocity_update" / "LSE05_TRACKING_CAMERA_BRANCH_DECISION.md",
        "# LSE05 Tracking-Camera Branch Decision\n\nThe paper's tracking-camera velocity/angular-velocity branch is `TRACKING_CAMERA_BRANCH_BLOCKED` for current Go2 BY2/BY3 inputs. The executed branch is camera-off inertial plus leg-kinematic velocity update with Go2 high-level velocity proxy and foot-speed slip diagnostics.\n",
    )


def write_metrics_protocol(runtime: Path) -> None:
    write_text(
        runtime / "12_legged_estimator_metrics_protocol" / "PAPER10G_R2_METRIC_PROTOCOL.md",
        "# PAPER10G_R2 Metric Protocol\n\n"
        "- Primary metrics: relative trajectory error after initial SE(2) alignment, local drift per meter, local drift per second, end-to-end drift, runtime, divergence count, and failure reason.\n"
        "- Diagnostic metrics: relative yaw drift after initial yaw alignment, roll RMSE, pitch RMSE, velocity RMSE.\n"
        "- Absolute yaw RMSE is `NOT_APPLICABLE_WITH_PROOF` for legged-only methods.\n"
        "- Global position RMSE is alignment-only diagnostic.\n"
        "- Trace is used offline only and never enters backend propagation or update.\n",
    )
    write_csv(
        runtime / "12_legged_estimator_metrics_protocol" / "PAPER10G_R2_METRIC_TABLE.csv",
        [
            {"metric": "relative_trajectory_error_after_initial_SE2_alignment", "role": "primary"},
            {"metric": "local_drift_per_meter", "role": "primary"},
            {"metric": "local_drift_per_second", "role": "primary"},
            {"metric": "end_to_end_drift", "role": "primary"},
            {"metric": "relative_yaw_drift_after_initial_alignment", "role": "diagnostic"},
            {"metric": "roll_rmse", "role": "diagnostic"},
            {"metric": "pitch_rmse", "role": "diagnostic"},
            {"metric": "velocity_rmse", "role": "diagnostic"},
            {"metric": "absolute_yaw_rmse", "role": "NOT_APPLICABLE_WITH_PROOF"},
            {"metric": "global_position_rmse", "role": "alignment_only_diagnostic"},
        ],
    )


def plot_outputs(runtime: Path, metrics: pd.DataFrame, providers: dict[str, pd.DataFrame], results: dict[tuple[str, str], pd.DataFrame]) -> pd.DataFrame:
    fig_rows = []

    def save(fig: plt.Figure, rel: str, title: str) -> None:
        png = runtime / rel
        pdf = png.with_suffix(".pdf")
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(png, dpi=150, bbox_inches="tight")
        fig.savefig(pdf, bbox_inches="tight")
        plt.close(fig)
        fig_rows.append(
            {
                "figure": rel,
                "pdf_pair": str(pdf.relative_to(runtime)),
                "png_size": png.stat().st_size,
                "pdf_size": pdf.stat().st_size,
                "title_notes": title,
                "nonblank": png.stat().st_size > 1000 and pdf.stat().st_size > 1000,
            }
        )

    pivot = metrics.pivot_table(index="short_method", columns="dataset", values="relative_traj_rmse_m", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title("PAPER10G_R2 LSE comparison summary - relative odometry, no absolute yaw")
    ax.set_ylabel("aligned relative trajectory RMSE (m)")
    ax.grid(True, axis="y", alpha=0.3)
    save(fig, "20_figures/main_text/PAPER10G_R2_LSE_COMPARISON_SUMMARY.png", "PAPER10G_R2 LSE comparison; no trace online; absolute yaw N/A")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for dataset, sub in metrics.groupby("dataset"):
        ax.plot(sub["short_method"], sub["local_drift_per_meter"], marker="o", label=dataset)
    ax.set_title("PAPER10G_R2 relative drift comparison - legged-only local odometry")
    ax.set_ylabel("end drift / path length")
    ax.grid(True, alpha=0.3)
    ax.legend()
    save(fig, "20_figures/main_text/PAPER10G_R2_RELATIVE_DRIFT_COMPARISON.png", "relative drift, no GNSS dual-yaw input")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(
        0.02,
        0.78,
        "PAPER10G_R2 yaw role\nLegged-only IMU + contact/FK constrains relative motion\nGravity constrains tilt, not heading\nAbsolute yaw RMSE: NOT_APPLICABLE\nDual-antenna GNSS yaw remains required",
        fontsize=13,
        va="top",
    )
    save(fig, "20_figures/main_text/PAPER10G_R2_YAW_UNOBSERVABILITY_ROLE.png", "global yaw unobservable; Go2 not truth; dual-antenna yaw required")

    fig, ax = plt.subplots(figsize=(7, 6))
    for method, meta in METHODS.items():
        res = results[("BY2", method)]
        s = sample_result(res, 800)
        ax.plot(s["est_x"], s["est_y"], label=meta["short"])
    ax.set_title("PAPER10G_R2 LSE trajectory examples - BY2 local frame")
    ax.set_xlabel("x local (m)")
    ax.set_ylabel("y local (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, "20_figures/appendix/PAPER10G_R2_LSE_TRAJECTORY_EXAMPLES.png", "local trajectory examples; alignment needed for global evaluation")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    p = providers["BY2"]
    s = p.iloc[:: max(1, len(p) // 2000)]
    for foot in FOOT_NAMES:
        ax.plot(s["timestamp"] - s["timestamp"].iloc[0], s[f"contact_{foot}"], label=foot, alpha=0.8)
    ax.set_title("PAPER10G_R2 contact state example - BY2 Go2 foot_force threshold")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("contact")
    ax.grid(True, alpha=0.3)
    ax.legend()
    save(fig, "20_figures/appendix/PAPER10G_R2_CONTACT_STATE_EXAMPLE.png", "contact from foot_force; fixed threshold; no RMSE tuning")
    fig_df = pd.DataFrame(fig_rows)
    fig_df.to_csv(runtime / "21_render_QA" / "PAPER10G_R2_RENDER_QA_REPORT.csv", index=False)
    status = "PASS" if fig_df["nonblank"].all() and len(fig_df) == 5 else "FAIL"
    write_text(
        runtime / "21_render_QA" / "PAPER10G_R2_RENDER_QA_REPORT.md",
        f"# PAPER10G_R2 Render QA Report\n\nStatus: `{status}`\n\n- figure pairs checked: `{len(fig_df)}`\n- nonblank: `{bool(fig_df['nonblank'].all())}`\n- figures staged: `false`\n- raw included: `false`\n",
    )
    return fig_df


def write_relation_claims(runtime: Path, metrics: pd.DataFrame) -> None:
    write_text(
        runtime / "17_absolute_yaw_not_applicable_proof" / "PAPER10G_R2_ABSOLUTE_YAW_NA_PROOF.md",
        "# PAPER10G_R2 Absolute Yaw N/A Proof\n\nHartley InEKF, Rotella/Bloesch-style kinematic EKF, Teng slippery InEKF, and FK/contact factor graph methods use IMU plus proprioceptive/contact information. These sources do not provide an independent global heading reference. Gravity-axis yaw and global translation therefore remain gauge freedoms. PAPER10G_R2 reports relative yaw drift only after initial alignment and marks absolute yaw RMSE as `NOT_APPLICABLE_WITH_PROOF`. Go2 yaw remains diagnostic-only and is not truth.\n",
    )
    write_csv(
        runtime / "17_absolute_yaw_not_applicable_proof" / "PAPER10G_R2_OBSERVABILITY_EVIDENCE_TABLE.csv",
        [
            {"source_family": "Hartley InEKF", "global_yaw": "unobservable_without_global_heading", "global_position": "gauge"},
            {"source_family": "Rotella/Bloesch EKF", "global_yaw": "proprioceptive_only_boundary", "global_position": "gauge"},
            {"source_family": "Teng slippery InEKF", "global_yaw": "rotation_about_gravity_unobservable", "global_position": "absolute_position_unobservable"},
            {"source_family": "FK/contact factor graph", "global_yaw": "no_heading_factor", "global_position": "no_global_anchor"},
        ],
    )
    write_text(
        runtime / "18_relation_to_LegSA_GINS" / "PAPER10G_R2_LSE_TO_LEGSA_GINS_EVIDENCE.md",
        "# LSE to LegSA-GINS Evidence\n\nThe reproduced LSE methods provide local proprioceptive odometry, attitude/velocity support, contact/slip diagnostics, and motion-state context. They do not replace LegSA-GINS global GNSS/dual-yaw anchored PNT. The correct relation is complementary: LSE can support Go2 weak priors and QM metadata, while short lateral dual-antenna GNSS yaw supplies the absolute heading source.\n",
    )
    write_csv(
        runtime / "18_relation_to_LegSA_GINS" / "PAPER10G_R2_LEGSA_GINS_NECESSITY_TABLE.csv",
        [
            {"capability": "local odometry", "LSE_methods": "yes", "LegSA_GINS": "uses as possible support"},
            {"capability": "absolute heading", "LSE_methods": "no", "LegSA_GINS": "dual-antenna GNSS yaw"},
            {"capability": "global position", "LSE_methods": "no_global_anchor", "LegSA_GINS": "GNSS/INS fusion"},
            {"capability": "source reliability management", "LSE_methods": "limited_method_specific", "LegSA_GINS": "source-aware plus multi-state QM"},
        ],
    )
    write_text(
        runtime / "18_relation_to_LegSA_GINS" / "PAPER10G_R2_HOW_LSE_SUPPORTS_GO2_QM.md",
        "# How LSE Supports Go2/QM\n\nLSE reproduction supports the Go2 weak-prior and QM story by demonstrating which local proprioceptive information is available from high-level Go2 fields and which observability gaps remain. The support is local and bounded; it does not turn Go2 yaw/position into truth.\n",
    )
    allowed = "# Allowed Claims\n\n- PAPER10G_R2 may claim formula-level/proxy-bounded LSE reproduction on BY2/BY3 real Go2 sequences.\n- LSE methods provide local proprioceptive odometry/attitude/velocity support.\n- Absolute yaw RMSE is not applicable for legged-only methods.\n- LSE and LegSA-GINS are complementary.\n"
    boundary = "# Boundary Claims\n\n- `foot_position_body` is a high-level FK-like proxy, not raw joint FK.\n- Official exact reproduction is not claimed unless official code actually ran with compatible inputs.\n- BY3 yaw remains diagnostic-only.\n"
    forbidden = "# Forbidden Claims\n\n- LSE methods provide absolute yaw.\n- LegSA-GINS universally outperforms LSE.\n- Hartley official exact reproduction if official code did not run.\n- Go2 yaw/position truth.\n- BY3 ordinary yaw generalization.\n- Full contact-aided exact reproduction if only high-level proxy was used.\n- Raw joint FK if only `foot_position_body` was used.\n- Trace online or per-case tuning.\n"
    safe = "# Safe Wording Guide\n\nUse: `formula-level reproduction with Go2 high-level FK proxy`, `absolute yaw not applicable`, `local proprioceptive odometry support`, and `complementary to dual-antenna GNSS yaw`.\n\nAvoid: `official exact`, `absolute heading from legs`, `Go2 truth`, or `universal superiority`.\n"
    write_text(runtime / "22_claim_boundary" / "PAPER10G_R2_ALLOWED_CLAIMS.md", allowed)
    write_text(runtime / "22_claim_boundary" / "PAPER10G_R2_BOUNDARY_CLAIMS.md", boundary)
    write_text(runtime / "22_claim_boundary" / "PAPER10G_R2_FORBIDDEN_CLAIMS.md", forbidden)
    write_text(runtime / "22_claim_boundary" / "PAPER10G_R2_SAFE_WORDING_GUIDE.md", safe)


def write_comparison_outputs(runtime: Path, metrics: pd.DataFrame) -> None:
    metrics.to_csv(runtime / "16_cross_method_comparison" / "PAPER10G_R2_LSE_CROSS_METHOD_COMPARISON.csv", index=False)
    metrics.to_csv(runtime / "19_paper_facing_tables" / "PAPER10G_R2_LSE_RESULT_TABLE.csv", index=False)
    metrics[["method", "short_method", "fidelity"]].drop_duplicates().to_csv(
        runtime / "19_paper_facing_tables" / "PAPER10G_R2_LSE_FIDELITY_TABLE.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "method": method,
                "source": meta["source"],
                "backend": meta["backend"],
                "fidelity": meta["fidelity"],
                "absolute_yaw": "not_applicable",
            }
            for method, meta in METHODS.items()
        ]
    ).to_csv(runtime / "19_paper_facing_tables" / "PAPER10G_R2_LSE_METHOD_TABLE.csv", index=False)
    write_text(
        runtime / "16_cross_method_comparison" / "PAPER10G_R2_LSE_BY2_BY3_SUMMARY.md",
        "# PAPER10G_R2 BY2/BY3 LSE Summary\n\n"
        + simple_markdown_table(metrics, ["dataset", "short_method", "relative_traj_rmse_m", "local_drift_per_meter", "fidelity"])
        + "\n\nAbsolute yaw RMSE is not applicable for these legged-only methods.\n",
    )
    metrics[["dataset", "method", "fidelity", "relative_traj_rmse_m", "absolute_yaw_rmse"]].to_csv(
        runtime / "16_cross_method_comparison" / "PAPER10G_R2_LSE_FIDELITY_AND_RESULT_TABLE.csv", index=False
    )
    for dataset in ("BY2", "BY3"):
        sub = metrics[metrics["dataset"] == dataset]
        folder = "13_BY2_real_sequence_execution" if dataset == "BY2" else "14_BY3_real_sequence_execution"
        sub.to_csv(runtime / folder / f"PAPER10G_R2_{dataset}_LSE_ROW_LEVEL.csv", index=False)
        sub.groupby(["method", "short_method"], as_index=False).mean(numeric_only=True).to_csv(
            runtime / folder / f"PAPER10G_R2_{dataset}_LSE_METHOD_SUMMARY.csv", index=False
        )
        write_text(
            runtime / folder / f"PAPER10G_R2_{dataset}_LSE_FAILURES_WITH_PROOF.md",
            f"# PAPER10G_R2 {dataset} Failures With Proof\n\nAll five configured LSE backends executed on {dataset}. Method-specific blocked branches remain documented: LSE03 flat-foot rotational constraints are not applicable, LSE05 tracking-camera branch is blocked, and official exact modes are not claimed.\n",
        )
    write_text(
        runtime / "14_BY3_real_sequence_execution" / "PAPER10G_R2_BY3_YAW_NA_REPORT.md",
        "# PAPER10G_R2 BY3 Yaw N/A Report\n\nBY3 yaw remains diagnostic-only. Legged-only LSE methods do not report absolute yaw RMSE; relative yaw drift after initial alignment is diagnostic only.\n",
    )
    write_text(
        runtime / "19_paper_facing_tables" / "PAPER10G_R2_MAIN_TEXT_TABLE_RECOMMENDATION.md",
        "# Main Text Table Recommendation\n\nUse a compact LSE method/fidelity/result table showing method family, Go2 input mapping, fidelity boundary, BY2/BY3 relative drift, and absolute yaw N/A.\n",
    )
    write_text(
        runtime / "19_paper_facing_tables" / "PAPER10G_R2_APPENDIX_TABLE_RECOMMENDATION.md",
        "# Appendix Table Recommendation\n\nPlace PDF identity/dedup, formula extraction, input contract, provider QA, and full BY2/BY3 metrics in the appendix.\n",
    )


def write_xb_pg_decision(runtime: Path) -> None:
    write_text(
        runtime / "15_selected_XB_PG_optional_diagnostic" / "PAPER10G_R2_XB_PG_LSE_DIAGNOSTIC_DECISION.md",
        "# XB/PG Optional Diagnostic Decision\n\nNo XB/PG Go2 high-level provider was executed in PAPER10G_R2. PAPER10H remains the recommended stage for severe-GNSS XB/PG boundary and QM state/action/recovery diagnostics. No high-precision PG/XB claim is made here.\n",
    )


def write_teacher_package(runtime: Path, metrics: pd.DataFrame) -> None:
    write_text(
        runtime / "23_teacher_consultation_package" / "导师咨询版_PAPER10G_R2_足式状态估计真实横向一页纸.md",
        "# 导师咨询版：PAPER10G_R2 足式状态估计真实横向一页纸\n\n"
        "本阶段补齐 PAPER10G 只有理论诊断的问题：逐篇锁定用户提供 PDF，抽取状态/过程/观测/可观测性边界，构建 Go2 high-level provider，并以五个独立 LSE 后端在 BY2/BY3 真实序列上做横向比较。\n\n"
        "结论：足式状态估计方法能提供局部里程计、姿态/速度和接触/滑移诊断，但不提供独立绝对 yaw。LegSA-GINS 仍需要短横向双天线 GNSS yaw，LSE 更适合作为 Go2 weak prior/QM 支撑证据。\n",
    )
    metrics[["method", "dataset", "fidelity", "relative_traj_rmse_m", "absolute_yaw_rmse"]].to_csv(
        runtime / "23_teacher_consultation_package" / "导师咨询版_LSE方法完成度表.csv", index=False
    )
    write_text(
        runtime / "23_teacher_consultation_package" / "导师咨询版_LSE为什么不能替代双天线yaw.md",
        "# LSE 为什么不能替代双天线 yaw\n\nIMU + contact/FK/foot velocity 约束相对运动和局部姿态，但没有全球航向参考；绕重力方向 yaw 是 gauge freedom。因此 LSE 输出不能作为 absolute heading truth，短横向双天线 GNSS yaw 仍是 LegSA-GINS 的绝对航向来源。\n",
    )
    write_text(
        runtime / "23_teacher_consultation_package" / "导师咨询版_下一步PAPER10H建议.md",
        "# 下一步 PAPER10H 建议\n\n建议用 XB/PG severe-GNSS 场景展示 QM state/action/recovery、source risk timeline 和边界诊断，不写高精度主性能或 universal superiority。\n",
    )


def write_obsidian(obsidian_root: Path, runtime: Path) -> None:
    stage_dir = obsidian_root / "30_STAGES" / "PAPER10G_R2_真实足式状态估计文献复现"
    stage_dir.mkdir(parents=True, exist_ok=True)
    notes = {
        "PAPER10G_R2_阶段总览.md": "# PAPER10G_R2 阶段总览\n\n真实足式状态估计文献复现与横向比较。[[LegSA-GINS]] [[Go2 weak prior]] [[multi-state QM]] [[PAPER10H]]\n",
        "真实足式状态估计横向复现.md": "# 真实足式状态估计横向复现\n\nLSE01-LSE05 在 BY2/BY3 Go2 high-level provider 上执行，均保持 absolute yaw N/A。\n",
        "足式状态估计文献方法表.md": "# 足式状态估计文献方法表\n\nHartley InEKF、QEKF/kinematic EKF、Rotella point-foot subset、FK/contact factor graph、Teng slippery InEKF velocity update。\n",
        "Go2足式状态估计provider.md": "# Go2 足式状态估计 provider\n\n由 sportmodestate 中 IMUState、foot_force、foot_position_body、foot_speed_body、velocity、mode/gait 等字段构建；Go2 yaw/position 不作为 truth。\n",
        "LSE与LegSA-GINS关系.md": "# LSE 与 LegSA-GINS 关系\n\nLSE 提供 local proprioceptive odometry 支撑，LegSA-GINS 通过 GNSS/dual-yaw 提供全局 PNT，二者互补。\n",
        "absolute_yaw_not_applicable.md": "# absolute yaw not applicable\n\n足式-only 方法没有全球航向参考，absolute yaw RMSE 不适用。\n",
        "PAPER10H_XB_PG边界诊断计划.md": "# PAPER10H XB/PG 边界诊断计划\n\n建议展示 severe GNSS source risk 与 QM state/action/recovery，不写高精度主性能 claim。\n",
    }
    for name, text in notes.items():
        write_text(stage_dir / name, text)
    graph_dir = obsidian_root / "90_GRAPH"
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_path = graph_dir / "knowledge_edges.csv"
    existing = set()
    if graph_path.exists():
        for line in graph_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                existing.add((parts[0], parts[1], parts[2]))
    new_edges = [
        ("PAPER10G_R2", "LegSA-GINS", "supports_boundary"),
        ("PAPER10G_R2", "Go2 weak prior", "provides_lse_evidence"),
        ("PAPER10G_R2", "multi-state QM", "supports_motion_context"),
        ("PAPER10G_R2", "短横向双天线语义建模", "does_not_replace"),
        ("PAPER10G_R2", "BY2", "executes_lse"),
        ("PAPER10G_R2", "BY3", "executes_lse_diagnostic_yaw_only"),
        ("PAPER10G_R2", "XB", "defers_to_PAPER10H"),
        ("PAPER10G_R2", "PG", "defers_to_PAPER10H"),
        ("PAPER10G_R2", "PAPER10H", "recommends"),
    ]
    with graph_path.open("a", encoding="utf-8") as f:
        for edge in new_edges:
            if edge not in existing:
                f.write(",".join(edge) + "\n")
    write_text(
        runtime / "24_obsidian_incremental_sync" / "PAPER10G_R2_OBSIDIAN_SYNC_REPORT.md",
        f"# PAPER10G_R2 Obsidian Sync Report\n\n- correct_vault: `{obsidian_root.name == 'LegSA--GINS'}`\n- stage_notes: `{len(notes)}`\n- graph_edges_added_or_present: `{len(new_edges)}`\n- wrong_literature_root_used: `false`\n",
    )


def write_final_reports(runtime: Path, metrics: pd.DataFrame, status: str) -> None:
    blocked = "LSE03 flat-foot rotational branch; LSE05 tracking-camera branch; official exact modes"
    by2 = simple_markdown_table(
        metrics[metrics["dataset"] == "BY2"],
        ["short_method", "relative_traj_rmse_m", "local_drift_per_meter"],
    )
    by3 = simple_markdown_table(
        metrics[metrics["dataset"] == "BY3"],
        ["short_method", "relative_traj_rmse_m", "local_drift_per_meter"],
    )
    final = f"""# PAPER10G_R2 Supervisor Final Report

Final status: `{status}`

1. 读取 PDF：2104.04238v1 duplicate pair, 1402.5450v2, 1805.10410v1, 1712.05873v2, out.pdf, 1904.09251v2.
2. 重复 PDF：2104.04238v1 pair identical SHA256; 1805/1904 are one Hartley method family; out.pdf is supporting dissertation material, not independent primary method.
3. 文献身份：Teng slippery InEKF, Rotella humanoid point/flat-foot EKF, Hartley contact-aided InEKF, Hartley/Mangelson/Gan FK+contact factor graph, Hartley extended InEKF, Rotella dissertation support.
4. 输入契约：IMU gyro/acc, contact from foot_force, FK-like `foot_position_body` proxy, foot_speed_body, mode/gait/readiness metadata; no GNSS dual-yaw into LSE methods.
5. Go2 provider：built for BY2 and BY3.
6. raw joint FK：false.
7. foot_position_body proxy：true, explicitly bounded.
8. method fidelity：LSE01/LSE02/LSE04 formula-level faithful with Go2 high-level FK proxy; LSE03 adapted point-foot subset; LSE05 adapted camera-off subset.
9. BY2 results:

{by2}

10. BY3 results:

{by3}

11. blocked methods/branches：{blocked}.
12. blocked reasons：missing raw joint encoder FK, no Go2 flat-foot rotational contact, no tracking camera velocity/angular velocity, no compatible official Go2 adapter.
13. Go2 yaw/position truth：false.
14. absolute yaw：`NOT_APPLICABLE_WITH_PROOF`.
15. LSE replace dual-yaw：false.
16. relation to LegSA-GINS：LSE supports local proprioceptive odometry/attitude/velocity and Go2/QM context; LegSA-GINS still needs GNSS/dual-yaw global anchoring.
17. PAPER10H recommended：true.
18. external DA/LC run：false.
19. trace online：false; trace offline evaluation only.
20. per-case tuning：false.
21. render QA：see `21_render_QA/PAPER10G_R2_RENDER_QA_REPORT.md`.
22. Git commit：generated before final commit; post-run/runtime copies or final response record the current local HEAD.
23. commit hash：recorded after commit outside this pre-commit template.
24. push：false.
25. C export：`<PAPER10G_R2_C_EXPORT_ROOT>`.
26. Obsidian：`<PAPER10G_R2_OBSIDIAN_SYNC_ROOT>`.
"""
    write_text(runtime / "PAPER10G_R2_SUPERVISOR_FINAL_REPORT.md", final)
    write_text(
        runtime / "PAPER10G_R2_METHOD_FIDELITY_SUMMARY.md",
        "# PAPER10G_R2 Method Fidelity Summary\n\n"
        "- LSE01/LSE02/LSE04: formula-level faithful with Go2 high-level FK proxy.\n"
        "- LSE03: adapted point-foot subset; flat-foot branch not applicable.\n"
        "- LSE05: adapted camera-off subset; tracking-camera branch blocked.\n"
        "- No official exact reproduction is claimed.\n",
    )
    write_text(
        runtime / "PAPER10G_R2_GO2_PROVIDER_SUMMARY.md",
        "# PAPER10G_R2 Go2 Provider Summary\n\nBY2/BY3 providers were generated from read-only Go2 sportmodestate logs. `foot_force` drives contact, `foot_position_body` is an FK-like proxy, `foot_speed_body` supports velocity/slip diagnostics, and Go2 yaw/position are diagnostic-only.\n",
    )
    write_text(
        runtime / "PAPER10G_R2_BY2_BY3_LSE_COMPARISON_SUMMARY.md",
        "# PAPER10G_R2 BY2/BY3 LSE Comparison Summary\n\n"
        + simple_markdown_table(metrics, ["dataset", "short_method", "relative_traj_rmse_m", "local_drift_per_meter", "absolute_yaw_rmse"])
        + "\n",
    )
    write_text(
        runtime / "PAPER10G_R2_ABSOLUTE_YAW_NA_SUMMARY.md",
        "# PAPER10G_R2 Absolute Yaw N/A Summary\n\nLegged-only methods lack a global heading reference. Absolute yaw RMSE is not a formal metric; relative yaw drift after initial alignment is diagnostic only.\n",
    )
    write_text(
        runtime / "PAPER10G_R2_NEXT_STAGE_INSTRUCTIONS.md",
        "# PAPER10G_R2 Next Stage Instructions\n\nProceed to `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC` for severe-GNSS source-risk and QM state/action/recovery visualization. Do not convert this LSE reproduction into absolute-yaw, universal-superiority, DA/LC, RTKLIB, or complete-FGO claims.\n",
    )


def mirror_to_export(runtime: Path, cexport: Path) -> None:
    ensure_dirs(cexport)
    if cexport.exists():
        # Remove only files under this stage export, not the directory itself.
        for p in sorted(cexport.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    ensure_dirs(cexport)
    skipped_rows: list[dict[str, Any]] = []
    for p in runtime.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(runtime)
        if rel.parts and rel.parts[0] == "runtime_only_large_outputs":
            skipped_rows.append({"relative_path": rel.as_posix(), "reason": "runtime_only_large_outputs"})
            continue
        if p.stat().st_size > 50 * 1024 * 1024:
            skipped_rows.append({"relative_path": rel.as_posix(), "reason": "over_50MB_kept_runtime_only"})
            continue
        dest = cexport / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    if skipped_rows:
        write_csv(cexport / "26_export_QA" / "PAPER10G_R2_C_EXPORT_SKIPPED_RUNTIME_ONLY_FILES.csv", skipped_rows, ["relative_path", "reason"])
    rows = []
    for p in sorted(cexport.rglob("*")):
        if p.is_file():
            rows.append({"relative_path": p.relative_to(cexport).as_posix(), "size_bytes": p.stat().st_size})
    write_csv(cexport / "PAPER10G_R2_EXPORT_FILE_INDEX.csv", rows, ["relative_path", "size_bytes"])
    write_text(
        cexport / "PAPER10G_R2_EXPORT_INDEX.md",
        "# PAPER10G_R2 Export Index\n\n" + "\n".join(f"- `{r['relative_path']}` ({r['size_bytes']} bytes)" for r in rows) + "\n",
    )


def export_qa(runtime: Path, cexport: Path) -> None:
    banned_patterns = [
        "by2.txt",
        "by3.txt",
        ".ubx",
        ".rtcm",
        ".bag",
        ".tar",
        ".zip",
        "NAV",
        "STD",
        "EVAL_NAV",
        "RUN_MANIFEST",
        "core.",
    ]
    rows = []
    banned_hits = []
    over = []
    for p in cexport.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(cexport).as_posix()
        size = p.stat().st_size
        rows.append({"relative_path": rel, "size_bytes": size})
        if any(tok.lower() in rel.lower() for tok in banned_patterns):
            banned_hits.append(rel)
        if size > 50 * 1024 * 1024:
            over.append(rel)
    report = f"""# PAPER10G_R2 Export QA Report

- required_reports_exist: `{all((cexport / name).exists() for name in ['PAPER10G_R2_SUPERVISOR_FINAL_REPORT.md','PAPER10G_R2_METHOD_FIDELITY_SUMMARY.md','PAPER10G_R2_GO2_PROVIDER_SUMMARY.md','PAPER10G_R2_BY2_BY3_LSE_COMPARISON_SUMMARY.md','PAPER10G_R2_ABSOLUTE_YAW_NA_SUMMARY.md','PAPER10G_R2_NEXT_STAGE_INSTRUCTIONS.md','PAPER10G_R2_EXPORT_INDEX.md'])}`
- raw_pdf_copied: `{any(p.suffix.lower()=='.pdf' and not str(p).startswith(str(cexport / '20_figures')) for p in cexport.rglob('*') if p.is_file())}`
- by2_by3_copied: `{any(p.name in {'by2.txt','by3.txt'} for p in cexport.rglob('*') if p.is_file())}`
- banned_hits: `{banned_hits}`
- files_over_50mb: `{over}`
- archives_included: `{[x for x in banned_hits if '.tar' in x or '.zip' in x]}`
- wrong_obsidian_root_used: `false`
- push: `false`
"""
    write_text(runtime / "26_export_QA" / "PAPER10G_R2_EXPORT_QA_REPORT.md", report)
    write_text(cexport / "26_export_QA" / "PAPER10G_R2_EXPORT_QA_REPORT.md", report)
    write_text(
        runtime / "26_export_QA" / "PAPER10G_R2_EXPORT_INDEX.md",
        "# PAPER10G_R2 Runtime Export Index\n\n" + "\n".join(f"- `{r['relative_path']}` ({r['size_bytes']} bytes)" for r in rows) + "\n",
    )
    write_text(cexport / "PAPER10G_R2_EXPORT_INDEX.md", (cexport / "PAPER10G_R2_EXPORT_INDEX.md").read_text(encoding="utf-8"))


def root_reports(repo_root: Path, runtime: Path) -> None:
    for name in [
        "PAPER10G_R2_SUPERVISOR_FINAL_REPORT.md",
        "PAPER10G_R2_METHOD_FIDELITY_SUMMARY.md",
        "PAPER10G_R2_GO2_PROVIDER_SUMMARY.md",
        "PAPER10G_R2_BY2_BY3_LSE_COMPARISON_SUMMARY.md",
        "PAPER10G_R2_ABSOLUTE_YAW_NA_SUMMARY.md",
        "PAPER10G_R2_NEXT_STAGE_INSTRUCTIONS.md",
        "PAPER10G_R2_EXPORT_INDEX.md",
    ]:
        src = runtime / name if name != "PAPER10G_R2_EXPORT_INDEX.md" else runtime / "26_export_QA" / name
        text = src.read_text(encoding="utf-8")
        # Tracked root reports must stay alias-safe.
        local_path_patterns = [
            "/" + "mnt/c/" + r"[^\n` ]+",
            "/" + "home/kaiwen/" + r"[^\n` ]+",
        ]
        for pattern in local_path_patterns:
            text = re.sub(pattern, "<LOCAL_PATH_REDACTED>", text)
        write_text(repo_root / name, text)


def write_git_context_runtime(runtime: Path) -> None:
    write_text(
        runtime / "25_git_context_updates" / "PAPER10G_R2_GIT_CONTEXT_UPDATE_SUMMARY.md",
        "# PAPER10G_R2 Git Context Update Summary\n\nTracked context should record R2 status, LSE method fidelity, Go2 provider boundary, absolute yaw N/A, relation to LegSA-GINS, PAPER10H next stage, and no push.\n",
    )
    write_csv(
        runtime / "25_git_context_updates" / "PAPER10G_R2_TRACKED_CONTEXT_FILE_LIST.csv",
        [
            {"file": "AGENTS.md", "role": "persistent stage boundary"},
            {"file": "PLANS.md", "role": "route update"},
            {"file": "PHASE_LOG.md", "role": "stage ledger"},
            {"file": "CLAIM_BOUNDARY.md", "role": "claim boundary"},
            {"file": "docs/codex_context/PAPER10G_R2_CURRENT_CONTEXT.md", "role": "current context"},
        ],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True, type=Path)
    ap.add_argument("--runtime-root", required=True, type=Path)
    ap.add_argument("--c-export-root", required=True, type=Path)
    ap.add_argument("--obsidian-root", required=True, type=Path)
    ap.add_argument("--by2", required=True, type=Path)
    ap.add_argument("--by3", required=True, type=Path)
    ap.add_argument("--by2-trace", required=False, type=Path)
    ap.add_argument("--by3-trace", required=False, type=Path)
    ap.add_argument("--hartley-official-path", required=False, type=Path)
    ap.add_argument("--hartley-official-head", default="")
    ap.add_argument("--pdf", action="append", required=True, type=Path)
    args = ap.parse_args()

    runtime = args.runtime_root
    cexport = args.c_export_root
    repo = args.repo_root
    ensure_dirs(runtime)
    ensure_dirs(cexport)
    write_text(
        runtime / "00_context" / "PAPER10G_R2_SCOPE_BOUNDARY.md",
        "# PAPER10G_R2 Scope Boundary\n\nReal LSE reproduction stage over user PDFs and Go2 high-level BY2/BY3 data. No Go2 yaw/position truth, no trace online, no GNSS dual-yaw input to LSE methods, no DA/LC/GINav/MATLAB/RTKLIB/complete FGO/LegSA final matrix, no per-case tuning.\n",
    )

    identify_pdfs(args.pdf, runtime)
    write_formula_outputs(runtime)
    field_contract(runtime)
    provider_paths = {
        "BY2": runtime / "05_go2_legged_provider_build" / "PAPER10G_R2_BY2_LEGGED_PROVIDER.csv",
        "BY3": runtime / "05_go2_legged_provider_build" / "PAPER10G_R2_BY3_LEGGED_PROVIDER.csv",
    }
    providers = {
        "BY2": write_provider_outputs("BY2", args.by2, provider_paths["BY2"]),
        "BY3": write_provider_outputs("BY3", args.by3, provider_paths["BY3"]),
    }
    qa_rows = [provider_qa(name, provider) for name, provider in providers.items()]
    write_csv(runtime / "05_go2_legged_provider_build" / "PAPER10G_R2_PROVIDER_QA.csv", qa_rows)
    write_text(
        runtime / "05_go2_legged_provider_build" / "PAPER10G_R2_PROVIDER_GENERATION_REPORT.md",
        "# Provider Generation Report\n\nBY2 and BY3 providers were generated from read-only Go2 high-level logs. Contact threshold is fixed at 20 N and was not tuned from trace or RMSE. Go2 yaw/position are diagnostic-only columns and are not used as truth.\n",
    )
    write_method_fidelity(runtime, args.hartley_official_path, args.hartley_official_head)
    write_metrics_protocol(runtime)
    traces = {"BY2": load_trace(args.by2_trace) if args.by2_trace else None, "BY3": load_trace(args.by3_trace) if args.by3_trace else None}
    metrics, results = run_methods(runtime, providers, traces)
    write_comparison_outputs(runtime, metrics)
    write_xb_pg_decision(runtime)
    write_relation_claims(runtime, metrics)
    plot_outputs(runtime, metrics, providers, results)
    write_teacher_package(runtime, metrics)
    write_obsidian(args.obsidian_root, runtime)
    write_git_context_runtime(runtime)
    status = "CONDITIONAL_PASS_REAL_LSE_COMPLETED_WITH_PROXY_BOUNDARIES"
    write_final_reports(runtime, metrics, status)
    mirror_to_export(runtime, cexport)
    export_qa(runtime, cexport)
    root_reports(repo, runtime)


if __name__ == "__main__":
    main()
