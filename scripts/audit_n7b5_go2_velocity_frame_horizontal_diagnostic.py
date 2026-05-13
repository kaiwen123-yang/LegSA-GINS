#!/usr/bin/env python3
"""Audit N7B5 Go2 velocity frame horizontal diagnostic workflow.

中文说明：用合成数据验证 N7B5 runner、报告、图表和边界；审计输出只在
tempdir，不能进入 Git。
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_frame_equivalence_review.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_builder.py",
    "src/legsa_gins/go2_prior/go2_frame_sensitivity_runner.py",
    "src/legsa_gins/go2_prior/go2_horizontal_diagnostic_activation.py",
    "src/legsa_gins/go2_prior/go2_n7b5_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7b5_decision.py",
    "scripts/experiments/run_n7b5_go2_velocity_frame_horizontal_diagnostic.py",
    "docs/experiments/n7b5_go2_velocity_frame_horizontal_diagnostic.md",
    "docs/experiments/n7b5_frame_equivalence_review.md",
    "docs/experiments/n7b5_horizontal_prior_boundary.md",
    "docs/experiments/n7b5_decision.md",
    "docs/codex_prompts/N7B5_go2_velocity_frame_horizontal_diagnostic.md",
]

REQUIRED_OUTPUTS = [
    "GO2_FRAME_EQUIVALENCE_REVIEW_REPORT.json",
    "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json",
    "N7B5_FRAME_SENSITIVITY_REPORT.json",
    "N7B5_DIAGNOSTIC_VARIANT_SUMMARIES.json",
    "N7B5_GO2_VELOCITY_FRAME_HORIZONTAL_DECISION_REPORT.json",
    "N7B5_FIGURE_MANIFEST.json",
    "n7b5_velocity_frame_horizontal_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7b5_go2_velocity_frame_horizontal_diagnostic failed: {message}")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, **kwargs)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_go2_csv(path: Path) -> None:
    fields = [
        "time",
        "aligned_time",
        "roll_rad",
        "pitch_rad",
        "yaw_rad",
        "go2_position_0",
        "go2_position_1",
        "go2_position_2",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        "mode",
        "gait_type",
        "body_height",
        *[f"foot_force_{foot}" for foot in range(4)],
        *[f"foot_position_body_{idx}" for idx in range(12)],
        *[f"foot_speed_body_{idx}" for idx in range(12)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        x = 0.0
        y = 0.0
        for index in range(80):
            t = index * 0.1
            vx = 0.75 + 0.004 * index
            vy = 0.18
            yaw = 0.04 + 0.0015 * index
            x += vx * 0.1
            y += vy * 0.1
            row = {
                "time": t,
                "aligned_time": t,
                "roll_rad": 0.006,
                "pitch_rad": -0.006,
                "yaw_rad": yaw,
                "go2_position_0": x,
                "go2_position_1": y,
                "go2_position_2": 0.0,
                "go2_velocity_0": vx,
                "go2_velocity_1": vy,
                "go2_velocity_2": 0.0,
                "yaw_speed_radps": 0.015,
                "mode": "walk",
                "gait_type": "trot",
                "body_height": 0.32,
            }
            contact_pair = (0, 3) if index % 2 == 0 else (1, 2)
            for foot in range(4):
                row[f"foot_force_{foot}"] = 42.0 if foot in contact_pair else 3.0
                row[f"foot_position_body_{3 * foot + 0}"] = 0.25 if foot < 2 else -0.25
                row[f"foot_position_body_{3 * foot + 1}"] = 0.12 if foot % 2 == 0 else -0.12
                row[f"foot_position_body_{3 * foot + 2}"] = -0.30
                row[f"foot_speed_body_{3 * foot + 0}"] = 0.05 if foot in contact_pair else 1.0
                row[f"foot_speed_body_{3 * foot + 1}"] = 0.0
                row[f"foot_speed_body_{3 * foot + 2}"] = 0.0
            writer.writerow(row)


def _write_probability_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "model_id", "support_probability", "confidence_score", "uncertainty_probability"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(80):
            bucket = index % 4
            support = 0.70 if bucket == 0 else (0.48 if bucket in {1, 2} else 0.25)
            confidence = 0.55 if bucket == 0 else (0.35 if bucket in {1, 2} else 0.15)
            writer.writerow(
                {
                    "time": index * 0.1,
                    "model_id": "force_speed_fused_probability",
                    "support_probability": support,
                    "confidence_score": confidence,
                    "uncertainty_probability": 1.0 - confidence,
                }
            )


def _write_clean_gnss(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for index in range(80):
            t = index * 0.1
            vn = 0.75 + 0.004 * index
            handle.write(f"{t:.3f} 30.0 120.0 10.0 0.5 0.5 0.8 {vn:.6f} 0.18 0.0 0.1 0.1 0.1 5.0 1.0\n")


def _write_raw_factor(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"],
        )
        writer.writeheader()
        for index in range(80):
            t = index * 0.1
            writer.writerow(
                {
                    "time": t,
                    "vn": 0.75 + 0.004 * index,
                    "ve": 0.18,
                    "vd": 0.0,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 9,
                    "provider_status": "available",
                    "quality_flag": "nominal",
                }
            )


def _write_fake_exe(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import csv, json, sys
from pathlib import Path
args=sys.argv
out=Path(args[args.index('--output-dir')+1])
config=Path(args[args.index('--config')+1]).read_text(encoding='utf-8', errors='ignore')
out.mkdir(parents=True, exist_ok=True)
vel_enabled='enable_go2_velocity_prior_diagnostic: true' in config
def path_after(key):
    for line in config.splitlines():
        if line.strip().startswith(key+':'):
            return line.split(':',1)[1].strip().strip('"')
    return ''
prior=path_after('go2_velocity_prior_diagnostic_path')
def count_rows(p):
    try:
        with open(p, newline='', encoding='utf-8-sig') as h:
            return max(0, sum(1 for _ in csv.DictReader(h)))
    except OSError:
        return 0
def horizontal(p):
    try:
        with open(p, newline='', encoding='utf-8-sig') as h:
            return any(float(row.get('std_vd', 0) or 0) >= 999.0 for row in csv.DictReader(h))
    except OSError:
        return False
updates=count_rows(prior) if vel_enabled else 0
is_horizontal=horizontal(prior) if vel_enabled else False
manifest={
 'ablation_variant': out.name,
 'paper_performance_claim': False,
 'diagnostic_only': True,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'go2_velocity_prior_diagnostic_enabled': vel_enabled,
 'go2_velocity_prior_update_count': updates,
 'go2_velocity_prior_reject_count': 0,
 'go2_horizontal_velocity_prior_diagnostic_enabled': bool(is_horizontal and vel_enabled),
 'go2_horizontal_velocity_prior_update_count': updates if is_horizontal else 0,
 'go2_horizontal_velocity_prior_vertical_disabled': bool(is_horizontal),
 'formal_go2_velocity_prior': False,
 'measurement_update_count': 80,
 'raw_doppler_update_count': 80,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    for i in range(80):
        w.writerow({'time':i*0.1,'lat_deg':30.0,'lon_deg':120.0,'height_m':10.0,'vn':0.75+0.004*i,'ve':0.18,'vd':0.0,'roll_deg':0,'pitch_deg':0,'yaw_deg':5})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path) -> None:
    _write_go2_csv(root / "n7a" / "GO2_BODY_STATE_STANDARDIZED.csv")
    _write_clean_gnss(root / "clean" / "CLEAN_STATUS_YAW.gnss")
    (root / "clean" / "kf-gins-n4h2g-clean-replay.yaml").write_text("imupath: input.imu\ngnsspath: CLEAN_STATUS_YAW.gnss\n", encoding="utf-8")
    _write_raw_factor(root / "n5b" / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_probability_csv(root / "n7b4" / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    _write_json(
        root / "n7b4" / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json",
        {
            "selected_contact_probability_model": "force_speed_fused_probability",
            "contact_probability_model_ready": True,
            "diagnostic_only": True,
        },
    )
    best = "go2_velocity_as_body_flu_then_rotate_by_go2_attitude"
    yaw = "yaw_only_rotation_diagnostic_only"
    _write_json(
        root / "n7b4" / "GO2_VELOCITY_FRAME_SCORE_REPORT.json",
        {
            "best_candidate": best,
            "second_best": yaw,
            "top2_frame_for_diagnostic": yaw,
            "selected_frame_for_diagnostic": best,
            "frame_status": "ambiguous_but_testable",
            "margin": 0.0004,
            "candidates": {
                best: {"external": {"rmse_to_receiver": 1.2, "rmse_to_raw": 1.4}},
                yaw: {"external": {"rmse_to_receiver": 1.21, "rmse_to_raw": 1.41}},
            },
            "diagnostic_only": True,
            "no_truth_claim": True,
        },
    )
    _write_json(
        root / "n7b4" / "N7B4_GO2_LITERATURE_CONTACT_VELOCITY_DECISION_REPORT.json",
        {"status": "contact_ready_frame_ambiguous", "recommended_next_stage": "N7B5_frame_resolution_or_N8A"},
    )
    (root / "n6b").mkdir(parents=True, exist_ok=True)
    _write_fake_exe(root / "fake_demo.py")


def _check_no_forbidden_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    tokens = [
        "by2.txt",
        "GO2_BODY_STATE_STANDARDIZED.csv",
        "GO2_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv",
        "GO2_VELOCITY_PRIOR_FORCED_DIAGNOSTIC.csv",
        "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv",
        "summary.json",
        "error_series.csv",
    ]
    for line in proc.stdout.splitlines():
        if any(token in line for token in tokens):
            _fail(f"forbidden tracked runtime artifact: {line}")
        if line.lower().endswith((".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked figure: {line}")


def main() -> int:
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists():
            _fail(f"required file missing: {path}")
    _check_no_forbidden_artifacts()
    with tempfile.TemporaryDirectory(prefix="n7b5_audit_") as tmp:
        tmp_path = Path(tmp)
        _prepare_runtime(tmp_path)
        output = tmp_path / "out"
        figures = tmp_path / "figures"
        cmd = [
            sys.executable,
            "scripts/experiments/run_n7b5_go2_velocity_frame_horizontal_diagnostic.py",
            "--n7b4-root",
            str(tmp_path / "n7b4"),
            "--n7a-root",
            str(tmp_path / "n7a"),
            "--n5b-root",
            str(tmp_path / "n5b"),
            "--n6b-root",
            str(tmp_path / "n6b"),
            "--clean-root",
            str(tmp_path / "clean"),
            "--output-dir",
            str(output),
            "--figure-output-dir",
            str(figures),
            "--build-dir",
            str(tmp_path / "build"),
            "--exe",
            str(tmp_path / "fake_demo.py"),
            "--allow-run",
        ]
        proc = _run(cmd, timeout=120)
        if proc.returncode != 0:
            _fail(proc.stderr[-1200:] or proc.stdout[-1200:])
        for name in REQUIRED_OUTPUTS:
            if not (output / name).exists():
                _fail(f"required output missing: {name}")
        decision = json.loads((output / "N7B5_GO2_VELOCITY_FRAME_HORIZONTAL_DECISION_REPORT.json").read_text())
        if not decision.get("diagnostic_only") or decision.get("paper_performance_claim"):
            _fail("decision boundary flags invalid")
        if decision.get("formal_go2_velocity_prior") or decision.get("formal_go2_yaw_prior"):
            _fail("decision overclaims formal Go2 prior")
        prior = json.loads((output / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json").read_text())
        if not prior.get("vertical_velocity_disabled") or prior.get("formal_activation_allowed"):
            _fail("horizontal prior boundary invalid")
        activation = json.loads((output / "N7B5_FRAME_SENSITIVITY_REPORT.json").read_text())
        if activation.get("formal_go2_velocity_prior") or activation.get("fgo"):
            _fail("activation overclaims formal prior or FGO")
        manifest = json.loads((output / "N7B5_FIGURE_MANIFEST.json").read_text())
        if manifest.get("figure_count_total") != 8 or not manifest.get("required_figures_nonempty"):
            _fail("figures missing or empty")
    print("audit_n7b5_go2_velocity_frame_horizontal_diagnostic passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
