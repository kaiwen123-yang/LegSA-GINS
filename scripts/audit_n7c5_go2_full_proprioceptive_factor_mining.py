#!/usr/bin/env python3
"""Audit N7C5 Go2 full proprioceptive factor mining workflow.

中文说明：本审计使用 toy runtime 运行 N7C5 runner，检查字段盘点、contact
概率审查、foot kinematic 候选、phase/yawrate/relative odometry、ranking、
图像和 decision 报告都满足“不激活新正式因子、不把 Go2 当 truth”的边界。
"""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_full_field_inventory.py",
    "src/legsa_gins/go2_prior/go2_contact_probability_factor_review.py",
    "src/legsa_gins/go2_prior/go2_foot_kinematic_velocity_candidate.py",
    "src/legsa_gins/go2_prior/go2_mode_gait_phase_model.py",
    "src/legsa_gins/go2_prior/go2_yawrate_consistency_candidate.py",
    "src/legsa_gins/go2_prior/go2_relative_odometry_candidate.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_factor_ranking.py",
    "src/legsa_gins/go2_prior/go2_n7c5_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c5_decision.py",
    "scripts/experiments/run_n7c5_go2_full_proprioceptive_factor_mining.py",
    "scripts/audit_go2_foot_kinematic_factor_boundary.py",
    "scripts/audit_go2_proprioceptive_no_trace_tuning.py",
    "scripts/audit_go2_full_field_not_truth.py",
    "docs/experiments/n7c5_go2_full_proprioceptive_factor_mining.md",
    "docs/experiments/n7c5_foot_kinematic_velocity_candidate.md",
    "docs/experiments/n7c5_contact_probability_factor_review.md",
    "docs/experiments/n7c5_factor_ranking.md",
    "docs/experiments/n7c5_decision.md",
    "docs/codex_prompts/N7C5_go2_full_proprioceptive_factor_mining.md",
]

REQUIRED_OUTPUTS = [
    "GO2_FULL_FIELD_INVENTORY_REPORT.json",
    "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json",
    "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json",
    "GO2_FOOT_KINEMATIC_VELOCITY_TIMESERIES.csv",
    "GO2_MODE_GAIT_PHASE_MODEL_REPORT.json",
    "GO2_MODE_GAIT_PHASE_TIMESERIES.csv",
    "GO2_YAWRATE_CONSISTENCY_CANDIDATE_REPORT.json",
    "GO2_RELATIVE_ODOMETRY_CANDIDATE_REPORT.json",
    "GO2_PROPRIOCEPTIVE_FACTOR_RANKING_REPORT.json",
    "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_DECISION_REPORT.json",
    "N7C5_FIGURE_MANIFEST.json",
    "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_RUN_REPORT.json",
    "n7c5_go2_full_proprioceptive_factor_case_review.md",
]

ARTIFACT_RE = re.compile(r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_.*\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c5_go2_full_proprioceptive_factor_mining failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    tokens = ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users", "/home/kaiwen/" + "legsa_external_artifacts"]
    for token in tokens:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")


def _check_no_forbidden_tracked_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden runtime/figure artifact tracked: " + ", ".join(hits[:8]))


def _write_go2_body_state(path: Path, count: int = 90) -> None:
    fields = [
        "time",
        "aligned_time",
        "quat_w",
        "quat_x",
        "quat_y",
        "quat_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "roll_rad",
        "pitch_rad",
        "yaw_rad",
        "mode",
        "gait_type",
        "go2_position_0",
        "go2_position_1",
        "go2_position_2",
        "body_height",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{i}" for i in range(4)],
        *[f"foot_position_body_{i}" for i in range(12)],
        *[f"foot_speed_body_{i}" for i in range(12)],
        "not_truth",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            t = index * 0.1
            yaw = 0.02 * t
            row = {
                "time": f"{t:.6f}",
                "aligned_time": f"{t:.6f}",
                "quat_w": 1.0,
                "quat_x": 0.0,
                "quat_y": 0.0,
                "quat_z": 0.0,
                "gyro_x": 0.0,
                "gyro_y": 0.0,
                "gyro_z": 0.02,
                "acc_x": 0.0,
                "acc_y": 0.0,
                "acc_z": 9.8,
                "roll_rad": 0.01,
                "pitch_rad": -0.01,
                "yaw_rad": f"{yaw:.9f}",
                "mode": "walk",
                "gait_type": "trot",
                "go2_position_0": f"{1.0 * t:.6f}",
                "go2_position_1": f"{0.2 * t:.6f}",
                "go2_position_2": "0.0",
                "body_height": "0.32",
                "go2_velocity_0": "1.0",
                "go2_velocity_1": "0.2",
                "go2_velocity_2": "0.0",
                "yaw_speed_radps": "0.02",
                "not_truth": "true",
            }
            for foot in range(4):
                row[f"foot_force_{foot}"] = "80.0"
                row[f"foot_position_body_{3 * foot + 0}"] = f"{0.25 if foot < 2 else -0.25:.6f}"
                row[f"foot_position_body_{3 * foot + 1}"] = f"{0.12 if foot % 2 == 0 else -0.12:.6f}"
                row[f"foot_position_body_{3 * foot + 2}"] = "-0.30"
                row[f"foot_speed_body_{3 * foot + 0}"] = "-1.0"
                row[f"foot_speed_body_{3 * foot + 1}"] = "-0.2"
                row[f"foot_speed_body_{3 * foot + 2}"] = "0.0"
            writer.writerow(row)


def _write_contact(path: Path, count: int = 90) -> None:
    fields = [
        "time",
        "model_id",
        "foot_0_contact_probability",
        "foot_1_contact_probability",
        "foot_2_contact_probability",
        "foot_3_contact_probability",
        "support_probability",
        "swing_probability",
        "uncertainty_probability",
        "hard_contact_count",
        "alternating_contact_hint",
        "mode",
        "gait_type",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            support = 0.82 if index % 7 else 0.62
            writer.writerow(
                {
                    "time": f"{index * 0.1:.6f}",
                    "model_id": "ensemble_probability",
                    "foot_0_contact_probability": support,
                    "foot_1_contact_probability": support,
                    "foot_2_contact_probability": support,
                    "foot_3_contact_probability": support,
                    "support_probability": support,
                    "swing_probability": 1.0 - support,
                    "uncertainty_probability": 0.12,
                    "hard_contact_count": 4,
                    "alternating_contact_hint": 0.8,
                    "mode": "walk",
                    "gait_type": "trot",
                }
            )


def _write_velocity_csv(path: Path, count: int = 90) -> None:
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "source_status", "go2_velocity_truth_claim"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow({"time": f"{index * 0.1:.6f}", "vn": "1.0", "ve": "0.2", "vd": "0.0", "std_vn": "1.0", "std_ve": "1.0", "std_vd": "999.0", "source_status": "active", "go2_velocity_truth_claim": "false"})


def _write_clean_gnss(path: Path, count: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [f"{index * 0.1:.6f} 30 120 10 1 1 1 1.0 0.2 0 1 1 1 5 1" for index in range(count)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_eval_nav(path: Path, count: int = 90) -> None:
    fields = ["time", "lat_deg", "lon_deg", "height_m", "vn", "ve", "vd", "roll_deg", "pitch_deg", "yaw_deg"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow({"time": index * 0.1, "lat_deg": 30 + index * 1e-8, "lon_deg": 120 + index * 2e-9, "height_m": 10, "vn": 1.0, "ve": 0.2, "vd": 0.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 0.0})


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path, Path]:
    n7a = root / "n7a"
    n7b4 = root / "n7b4"
    n7b5 = root / "n7b5"
    n7c = root / "n7c"
    n7c4 = root / "n7c4"
    n5b = root / "n5b"
    clean = root / "clean"
    dual = root / "dual"
    _write_go2_body_state(n7a / "GO2_BODY_STATE_STANDARDIZED.csv")
    _write_contact(n7b4 / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    _write_json(n7b4 / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json", {"selected_contact_probability_model": "ensemble_probability"})
    _write_velocity_csv(n7b5 / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    _write_velocity_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_clean_gnss(clean / "input.gnss")
    _write_json(n7c4 / "N7C4_STRENGTH_CALIBRATION_DECISION_REPORT.json", {"recommended_default_policy": "fixed_1p0", "status": "stronger_policy_ready"})
    _write_eval_nav(n7c4 / "variants" / "fixed_1p0" / "EVAL_NAV.csv")
    dual.mkdir(parents=True, exist_ok=True)
    n7c.mkdir(parents=True, exist_ok=True)
    return n7a, n7b4, n7b5, n7c, n7c4, n5b, root / "n6b", clean, dual


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c5_full_") as tmp_value:
        tmp = Path(tmp_value)
        n7a, n7b4, n7b5, n7c, n7c4, n5b, n6b, clean, dual = _prepare_runtime(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c5_go2_full_proprioceptive_factor_mining.py"),
            "--n7a-root", str(n7a),
            "--n7b4-root", str(n7b4),
            "--n7b5-root", str(n7b5),
            "--n7c-root", str(n7c),
            "--n7c4-root", str(n7c4),
            "--n5b-root", str(n5b),
            "--n6b-root", str(n6b),
            "--clean-root", str(clean),
            "--dual-root", str(dual),
            "--output-dir", str(out),
            "--figure-output-dir", str(figs),
            "--allow-run",
        ]
        proc = _run(cmd)
        if proc.returncode != 0:
            _fail(proc.stdout + proc.stderr)
        for rel in REQUIRED_OUTPUTS:
            if not (out / rel).exists():
                _fail(f"missing runtime output {rel}")
        inventory = _load(out / "GO2_FULL_FIELD_INVENTORY_REPORT.json")
        contact = _load(out / "GO2_CONTACT_PROBABILITY_FACTOR_REVIEW.json")
        foot = _load(out / "GO2_FOOT_KINEMATIC_VELOCITY_CANDIDATE_REPORT.json")
        decision = _load(out / "N7C5_GO2_FULL_PROPRIOCEPTIVE_FACTOR_DECISION_REPORT.json")
        figures = _load(out / "N7C5_FIGURE_MANIFEST.json")
        if not inventory.get("all_required_groups_available"):
            _fail("inventory did not find all required Go2 field groups")
        if not contact.get("usable_as_weight"):
            _fail("contact probability not usable as weight in toy run")
        if foot.get("activation_candidate") != "ready_for_N7C6":
            _fail("toy foot kinematic candidate should be ready_for_N7C6")
        if decision.get("formal_activation_in_n7c5"):
            _fail("N7C5 must not formally activate a new factor")
        if decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_vertical_velocity_prior_enabled"):
            _fail("forbidden Go2 prior enabled in decision")
        if not figures.get("required_figures_generated") or not figures.get("required_figures_nonempty"):
            _fail("required N7C5 figures missing or empty")


def main() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c5_go2_full_proprioceptive_factor_mining passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
