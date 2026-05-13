#!/usr/bin/env python3
"""Audit N7B3 Go2 contact/velocity diagnostic activation workflow.

中文说明：本审计用合成数据验证 N7B3 runner、图表和 claim boundary；真实
runtime 路径仍只能来自命令行参数。
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
    "src/legsa_gins/go2_prior/go2_velocity_frame_review.py",
    "src/legsa_gins/go2_prior/go2_contact_model_candidates.py",
    "src/legsa_gins/go2_prior/go2_contact_model_comparison.py",
    "src/legsa_gins/go2_prior/go2_velocity_prior_diagnostic_builder.py",
    "src/legsa_gins/go2_prior/go2_yaw_rate_prior_diagnostic_builder.py",
    "src/legsa_gins/go2_prior/go2_diagnostic_activation_runner.py",
    "src/legsa_gins/go2_prior/go2_n7b3_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7b3_decision.py",
    "scripts/experiments/run_n7b3_go2_contact_velocity_diagnostic_activation.py",
    "docs/experiments/n7b3_go2_contact_velocity_diagnostic_activation.md",
    "docs/experiments/n7b3_go2_velocity_frame_review.md",
    "docs/experiments/n7b3_contact_model_candidates.md",
    "docs/experiments/n7b3_diagnostic_prior_boundary.md",
    "docs/experiments/n7b3_decision.md",
    "docs/codex_prompts/N7B3_go2_contact_velocity_diagnostic_activation.md",
]

REQUIRED_OUTPUTS = [
    "GO2_VELOCITY_FRAME_REVIEW_REPORT.json",
    "GO2_CONTACT_MODEL_CANDIDATES_REPORT.json",
    "GO2_CONTACT_MODEL_COMPARISON_REPORT.json",
    "GO2_VELOCITY_PRIOR_DIAGNOSTIC_BUILD_REPORT.json",
    "GO2_YAW_RATE_PRIOR_DIAGNOSTIC_BUILD_REPORT.json",
    "N7B3_DIAGNOSTIC_ACTIVATION_REPORT.json",
    "N7B3_DIAGNOSTIC_VARIANT_SUMMARIES.json",
    "N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json",
    "N7B3_FIGURE_MANIFEST.json",
    "n7b3_contact_velocity_diagnostic_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7b3_go2_contact_velocity_diagnostic_activation failed: {message}")


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
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        "mode",
        "gait_type",
        "body_height",
        *[f"foot_force_{foot}" for foot in range(4)],
        *[f"foot_speed_body_{idx}" for idx in range(12)],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(48):
            t = index * 0.1
            row = {
                "time": t,
                "aligned_time": t,
                "roll_rad": 0.01,
                "pitch_rad": -0.02,
                "yaw_rad": 0.30,
                "go2_velocity_0": 1.0 + 0.02 * index,
                "go2_velocity_1": 0.35,
                "go2_velocity_2": 0.10,
                "yaw_speed_radps": 0.04,
                "mode": "walk",
                "gait_type": "trot",
                "body_height": 0.32,
            }
            contact_pair = (0, 3) if index % 2 == 0 else (1, 2)
            for foot in range(4):
                row[f"foot_force_{foot}"] = 35.0 if foot in contact_pair else 3.0
                speed = 0.08 if foot in contact_pair else 1.2
                for axis in range(3):
                    row[f"foot_speed_body_{3 * foot + axis}"] = speed if axis == 0 else 0.0
            writer.writerow(row)


def _write_clean_gnss(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for index in range(48):
            t = index * 0.1
            vn = 1.0 + 0.02 * index
            handle.write(f"{t:.3f} 30.0 120.0 10.0 0.5 0.5 0.8 {vn:.6f} 0.35 0.10 0.1 0.1 0.1 5.0 1.0\n")


def _write_raw_factor(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"],
        )
        writer.writeheader()
        for index in range(48):
            t = index * 0.1
            writer.writerow(
                {
                    "time": t,
                    "vn": 1.0 + 0.02 * index,
                    "ve": 0.35,
                    "vd": 0.10,
                    "std_vn": 0.2,
                    "std_ve": 0.2,
                    "std_vd": 0.2,
                    "sat_count": 8,
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
yaw_enabled='enable_go2_yaw_rate_prior_diagnostic: true' in config
def path_after(key):
    for line in config.splitlines():
        if line.strip().startswith(key+':'):
            return line.split(':',1)[1].strip().strip('"')
    return ''
def count_rows(p):
    try:
        with open(p, newline='', encoding='utf-8-sig') as h:
            return max(0, sum(1 for _ in csv.DictReader(h)))
    except OSError:
        return 0
updates=count_rows(path_after('go2_velocity_prior_diagnostic_path')) if vel_enabled else 0
manifest={
 'ablation_variant': out.name,
 'paper_performance_claim': False,
 'diagnostic_only': True,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'go2_velocity_prior_diagnostic_enabled': vel_enabled,
 'go2_velocity_prior_update_count': updates,
 'go2_velocity_prior_reject_count': 0,
 'go2_yaw_rate_prior_diagnostic_enabled': yaw_enabled,
 'go2_yaw_rate_prior_update_count': 0,
 'go2_yaw_rate_prior_activation_status': 'yaw_rate_prior_not_activated_due_to_state_model' if yaw_enabled else '',
 'measurement_update_count': 48,
 'raw_doppler_update_count': 48,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    for i in range(48):
        w.writerow({'time':i*0.1,'lat_deg':30.0,'lon_deg':120.0,'height_m':10.0,'vn':1.0+0.02*i,'ve':0.35,'vd':0.10,'roll_deg':0,'pitch_deg':0,'yaw_deg':5})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path) -> None:
    _write_go2_csv(root / "n7a" / "GO2_BODY_STATE_STANDARDIZED.csv")
    _write_json(root / "n7b" / "N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json", {"status": "contact_not_ready"})
    _write_json(root / "n7b2" / "N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json", {"status": "contact_still_not_ready"})
    _write_json(root / "n7b2a" / "N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json", {"status": "contact_v2_not_ready"})
    _write_clean_gnss(root / "clean" / "CLEAN_STATUS_YAW.gnss")
    (root / "clean" / "kf-gins-n4h2g-clean-replay.yaml").write_text("imupath: input.imu\ngnsspath: CLEAN_STATUS_YAW.gnss\n", encoding="utf-8")
    _write_raw_factor(root / "n5b" / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_fake_exe(root / "fake_demo.py")


def _check_no_forbidden_artifacts() -> None:
    proc = _run(["git", "ls-files"])
    pattern_tokens = [
        "by2.txt",
        "GO2_BODY_STATE_STANDARDIZED.csv",
        "GO2_CONTACT_STATE_V2_TIMESERIES.csv",
        "GO2_VELOCITY_WEAK_PRIORS_DIAGNOSTIC.csv",
        "GO2_YAW_RATE_WEAK_PRIORS_DIAGNOSTIC.csv",
    ]
    for line in proc.stdout.splitlines():
        if any(token in line for token in pattern_tokens):
            _fail(f"forbidden tracked runtime artifact: {line}")
        if line.lower().endswith((".png", ".pdf", ".svg", ".jpg", ".jpeg")):
            _fail(f"forbidden tracked figure: {line}")


def main() -> int:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            _fail(f"required file missing: {rel}")
    text = "\n".join((ROOT / rel).read_text(encoding="utf-8", errors="ignore") for rel in REQUIRED_FILES)
    for token in [
        "diagnostic_only",
        "Go2 velocity is not truth",
        "cross-source consistency",
        "contact_model_ready",
        "paper_performance_claim",
        "final_v23_output_solver_input",
        "trace_solver_input",
        "fgo",
    ]:
        if token not in text:
            _fail(f"required N7B3 token missing: {token}")
    with tempfile.TemporaryDirectory(prefix="legsa_n7b3_toy_") as tmp:
        tmp_root = Path(tmp)
        _prepare_runtime(tmp_root)
        proc = _run(
            [
                sys.executable,
                "scripts/experiments/run_n7b3_go2_contact_velocity_diagnostic_activation.py",
                "--n7a-root",
                str(tmp_root / "n7a"),
                "--n7b-root",
                str(tmp_root / "n7b"),
                "--n7b2-root",
                str(tmp_root / "n7b2"),
                "--n7b2a-root",
                str(tmp_root / "n7b2a"),
                "--n5b-root",
                str(tmp_root / "n5b"),
                "--n6b-root",
                str(tmp_root / "n6b"),
                "--clean-root",
                str(tmp_root / "clean"),
                "--output-dir",
                str(tmp_root / "out"),
                "--figure-output-dir",
                str(tmp_root / "fig"),
                "--build-dir",
                str(tmp_root / "build"),
                "--exe",
                str(tmp_root / "fake_demo.py"),
                "--allow-run",
            ],
            timeout=90,
        )
        if proc.returncode != 0:
            _fail(proc.stdout + proc.stderr)
        for name in REQUIRED_OUTPUTS:
            if not (tmp_root / "out" / name).exists():
                _fail(f"runtime output missing: {name}")
        decision = json.loads((tmp_root / "out/N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("paper_performance_claim") or decision.get("fgo"):
            _fail("forbidden formal claim in decision")
        manifest = json.loads((tmp_root / "out/N7B3_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not manifest.get("required_figures_generated") or not manifest.get("required_figures_nonempty"):
            _fail("required figures missing/nonempty false")
    _check_no_forbidden_artifacts()
    print("audit_n7b3_go2_contact_velocity_diagnostic_activation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
