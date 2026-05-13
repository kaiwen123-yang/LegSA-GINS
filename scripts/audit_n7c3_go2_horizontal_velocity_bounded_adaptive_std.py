#!/usr/bin/env python3
"""Audit N7C3 bounded adaptive Go2 horizontal velocity std workflow.

中文说明：本审计覆盖 N7C3 有界自适应水平速度先验的策略、输出和边界声明。
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_confidence.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_bounded_adaptive_std.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_soft_gating.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_adaptive_ablation.py",
    "src/legsa_gins/go2_prior/go2_n7c3_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c3_decision.py",
    "scripts/experiments/run_n7c3_go2_horizontal_velocity_bounded_adaptive_std.py",
    "scripts/audit_go2_adaptive_std_no_trace_tuning.py",
    "scripts/audit_go2_adaptive_std_physical_bounds.py",
    "scripts/audit_go2_adaptive_std_vertical_disabled.py",
    "docs/experiments/n7c3_go2_horizontal_velocity_bounded_adaptive_std.md",
    "docs/experiments/n7c3_literature_informed_policy.md",
    "docs/experiments/n7c3_confidence_policy.md",
    "docs/experiments/n7c3_soft_gating_policy.md",
    "docs/experiments/n7c3_decision.md",
    "docs/codex_prompts/N7C3_go2_horizontal_velocity_bounded_adaptive_std.md",
]

REQUIRED_OUTPUTS = [
    "GO2_HORIZONTAL_VELOCITY_CONFIDENCE_REPORT.json",
    "GO2_HORIZONTAL_VELOCITY_CONFIDENCE_TIMESERIES.csv",
    "GO2_HORIZONTAL_VELOCITY_BOUNDED_ADAPTIVE_PRIORS.csv",
    "GO2_HORIZONTAL_VELOCITY_BOUNDED_ADAPTIVE_STD_REPORT.json",
    "GO2_HORIZONTAL_VELOCITY_SOFT_GATING_REPORT.json",
    "N7C3_BOUNDED_ADAPTIVE_STD_VARIANT_SUMMARIES.json",
    "N7C3_BOUNDED_ADAPTIVE_STD_COMPARISON_REPORT.json",
    "N7C3_BOUNDED_ADAPTIVE_STD_DECISION_REPORT.json",
    "N7C3_FIGURE_MANIFEST.json",
    "n7c3_bounded_adaptive_std_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_HORIZONTAL_VELOCITY_PRIORS\.csv|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c3_go2_horizontal_velocity_bounded_adaptive_std failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for token in [
        "/mnt/c/" + "Users/ykw/Desktop",
        "/mnt/c/" + "Users/86187/Desktop",
        "C:" + "\\\\Users",
        "/home/kaiwen/" + "legsa_n4h4",
        "/home/kaiwen/" + "legsa_external_artifacts",
    ]:
        if _git_lines(["grep", "-n", token, "--", "."]):
            _fail(f"local path leak: {token}")


def _check_no_forbidden_tracked_artifacts() -> None:
    hits = [line for line in _git_lines(["ls-files"]) if ARTIFACT_RE.search(line)]
    if hits:
        _fail("forbidden runtime/figure artifact tracked: " + ", ".join(hits[:8]))


def _write_prior_csv(path: Path, count: int = 80) -> None:
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "source_status", "quality_flag", "contact_model", "contact_label", "frame_candidate", "prior_policy", "diagnostic_only", "go2_velocity_truth_claim"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            bucket = "high" if index % 11 == 0 else ("medium" if index % 3 == 0 else "low")
            writer.writerow(
                {
                    "time": f"{index * 0.1:.6f}",
                    "vn": f"{0.8 + 0.01 * index:.6f}",
                    "ve": "0.2",
                    "vd": "0.0",
                    "std_vn": "2.0",
                    "std_ve": "2.0",
                    "std_vd": "999.0",
                    "source_status": "active",
                    "quality_flag": f"n7c_horizontal_{bucket}_confidence",
                    "contact_model": "toy",
                    "contact_label": bucket,
                    "frame_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                    "prior_policy": "n7c_go2_horizontal_velocity_weak_prior",
                    "diagnostic_only": "False",
                    "go2_velocity_truth_claim": "False",
                }
            )


def _write_contact_probability(path: Path, count: int = 80) -> None:
    fields = ["time", "model_id", "foot_0_contact_probability", "foot_1_contact_probability", "foot_2_contact_probability", "foot_3_contact_probability", "support_probability", "swing_probability", "uncertainty_probability", "confidence_score", "hard_contact_count", "alternating_contact_hint", "all_contact_penalty", "all_uncertain_penalty", "mode", "gait_type", "body_velocity_norm", "trace_solver_input", "final_v23_output_solver_input", "diagnostic_only"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            support = 0.90 if index % 11 == 0 else (0.72 if index % 3 == 0 else 0.45)
            confidence = 0.90 if index % 11 == 0 else (0.70 if index % 3 == 0 else 0.50)
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
                    "uncertainty_probability": 0.10,
                    "confidence_score": confidence,
                    "hard_contact_count": 3,
                    "alternating_contact_hint": 1,
                    "all_contact_penalty": 0,
                    "all_uncertain_penalty": 0,
                    "mode": "walk",
                    "gait_type": "trot",
                    "body_velocity_norm": 0.6,
                    "trace_solver_input": False,
                    "final_v23_output_solver_input": False,
                    "diagnostic_only": True,
                }
            )


def _write_frame_equivalence(path: Path, count: int = 80) -> None:
    fields = ["time", "primary_frame", "secondary_frame", "primary_vn", "primary_ve", "primary_vd", "secondary_vn", "secondary_ve", "secondary_vd", "horizontal_difference_mps", "vertical_difference_mps", "horizontal_angle_difference_deg", "segment_labels", "diagnostic_only", "go2_velocity_truth_claim"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow(
                {
                    "time": f"{index * 0.1:.6f}",
                    "primary_frame": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                    "secondary_frame": "yaw_only_rotation_diagnostic_only",
                    "primary_vn": 1.0,
                    "primary_ve": 0.2,
                    "primary_vd": 0,
                    "secondary_vn": 1.0,
                    "secondary_ve": 0.2,
                    "secondary_vd": 0,
                    "horizontal_difference_mps": 0.05,
                    "vertical_difference_mps": 0.0,
                    "horizontal_angle_difference_deg": 2.0,
                    "segment_labels": "toy",
                    "diagnostic_only": True,
                    "go2_velocity_truth_claim": False,
                }
            )


def _write_raw_or_gnss_csv(path: Path, count: int = 80) -> None:
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow({"time": f"{index * 0.1:.6f}", "vn": f"{0.8 + 0.01 * index:.6f}", "ve": "0.2", "vd": "0", "std_vn": "0.2", "std_ve": "0.2", "std_vd": "0.2", "sat_count": 8, "provider_status": "ok", "quality_flag": "usable"})


def _write_clean_gnss(path: Path, count: int = 80) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(f"{index * 0.1:.6f} 30 120 10 1 1 1 {0.8 + 0.01 * index:.6f} 0.2 0 1 1 1 5 1")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_reference(path: Path, count: int = 80) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(f"0 {index * 0.1:.6f} {30 + index * 1e-9:.12f} {120 + index * 1e-9:.12f} 10 1 0.2 0 0 0 5")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_fake_exe(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import csv, json, sys
from pathlib import Path
args=sys.argv
out=Path(args[args.index('--output-dir')+1])
config=Path(args[args.index('--config')+1]).read_text(encoding='utf-8', errors='ignore')
out.mkdir(parents=True, exist_ok=True)
def after(key):
    for line in config.splitlines():
        if line.strip().startswith(key+':'):
            return line.split(':',1)[1].strip().strip('"')
    return ''
variant=after('ablation_variant') or out.name
enabled='enable_go2_horizontal_velocity_prior: true' in config
prior=after('go2_horizontal_velocity_prior_path')
updates=0
skips=0
stds=[]
if enabled and prior:
    with open(prior, newline='', encoding='utf-8-sig') as h:
        for row in csv.DictReader(h):
            update=str(row.get('update_flag','true')).lower() in {'true','1','yes'} and row.get('source_status','active')=='active'
            updates += int(update)
            skips += int(not update)
            if update:
                stds.append(float(row.get('std_vn') or 0))
manifest={
 'ablation_variant': variant,
 'phase': 'N7C3',
 'go2_horizontal_velocity_adaptive_std_enabled': True,
 'go2_horizontal_velocity_bounded_std_policy': after('go2_horizontal_velocity_bounded_std_policy'),
 'paper_performance_claim': False,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'go2_horizontal_velocity_prior_enabled': enabled,
 'go2_velocity_prior_update_count': updates,
 'go2_velocity_prior_reject_count': 0,
 'go2_horizontal_velocity_prior_update_count': updates,
 'go2_horizontal_velocity_prior_skip_count': skips,
 'go2_horizontal_velocity_prior_vertical_disabled': True,
 'go2_horizontal_velocity_prior_std_vn_p50': sorted(stds)[len(stds)//2] if stds else 0,
 'go2_horizontal_velocity_prior_std_vn_p95': sorted(stds)[int(0.95*(len(stds)-1))] if stds else 0,
 'go2_horizontal_velocity_prior_std_vn_max': max(stds) if stds else 0,
 'go2_horizontal_velocity_prior_max_std_le_5': max(stds or [0]) <= 5,
 'go2_position_prior_enabled': False,
 'go2_yaw_prior_enabled': False,
 'fgo_enabled': False,
 'measurement_update_count': 80,
 'raw_doppler_update_count': 80,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    offset=0.0 if 'adaptive' in variant else 1e-9
    for i in range(80):
        w.writerow({'time':i*0.1,'lat_deg':30+i*1e-9+offset,'lon_deg':120+i*1e-9+offset,'height_m':10,'vn':1,'ve':0.2,'vd':0,'roll_deg':0,'pitch_deg':0,'yaw_deg':5+offset*1e6})
with (out/'SOURCE_AWARE_WEIGHT_TRACE.csv').open('w', encoding='utf-8', newline='') as h:
    fields=['time','update_index','source_id','policy_version','mode','lsim_score','oim_score','combined_R_scale','residual_norm','normalized_innovation','used_innovation_covariance','accepted','rejected','reason_codes']
    w=csv.DictWriter(h, fieldnames=fields); w.writeheader()
    for i in range(max(1, min(updates, 20))):
        w.writerow({'time':i*0.2,'update_index':i,'source_id':'go2_horizontal_velocity','policy_version':'n7c3','mode':'lsim_oim','lsim_score':1,'oim_score':1,'combined_R_scale':1,'residual_norm':0.2,'normalized_innovation':0.5,'used_innovation_covariance':1,'accepted':1,'rejected':0,'reason_codes':'toy'})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    n7c = root / "n7c"
    n7b4 = root / "n7b4"
    n7b5 = root / "n7b5"
    n5b = root / "n5b"
    clean = root / "clean"
    dual = root / "dual"
    _write_prior_csv(n7c / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv")
    _write_prior_csv(n7c / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_N7C.csv")
    _write_contact_probability(n7b4 / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    _write_json(n7b4 / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json", {"selected_contact_probability_model": "ensemble_probability", "contact_probability_model_ready": True})
    _write_frame_equivalence(n7b5 / "GO2_FRAME_EQUIVALENCE_TIMESERIES.csv")
    _write_json(n7b5 / "GO2_FRAME_EQUIVALENCE_REVIEW_REPORT.json", {"frame_equivalent_for_horizontal_only": True})
    _write_prior_csv(n7b5 / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    _write_raw_or_gnss_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    clean.mkdir(parents=True, exist_ok=True)
    _write_clean_gnss(clean / "input.gnss")
    (clean / "clean.yaml").write_text("imupath: input.imu\ngnsspath: input.gnss\n", encoding="utf-8")
    _write_reference(dual / "KF_GINS_Navresult.nav")
    exe = root / "fake_demo.py"
    _write_fake_exe(exe)
    return n7c, root / "n7c1", root / "n7c2", n7b5, n7b4, n5b, clean, dual, exe


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c3_bounded_") as tmp_value:
        tmp = Path(tmp_value)
        n7c, n7c1, n7c2, n7b5, n7b4, n5b, clean, dual, exe = _prepare_runtime(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c3_go2_horizontal_velocity_bounded_adaptive_std.py"),
            "--n7c-root",
            str(n7c),
            "--n7c1-root",
            str(n7c1),
            "--n7c2-root",
            str(n7c2),
            "--n7b5-root",
            str(n7b5),
            "--n7b4-root",
            str(n7b4),
            "--n5b-root",
            str(n5b),
            "--n6b-root",
            str(tmp / "n6b"),
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--build-dir",
            str(tmp / "build"),
            "--exe",
            str(exe),
            "--allow-run",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            _fail(proc.stderr[-4000:] or proc.stdout[-4000:])
        for item in REQUIRED_OUTPUTS:
            if not (out / item).exists():
                _fail(f"missing output {item}")
        std_report = json.loads((out / "GO2_HORIZONTAL_VELOCITY_BOUNDED_ADAPTIVE_STD_REPORT.json").read_text(encoding="utf-8"))
        decision = json.loads((out / "N7C3_BOUNDED_ADAPTIVE_STD_DECISION_REPORT.json").read_text(encoding="utf-8"))
        figures = json.loads((out / "N7C3_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if not std_report.get("max_std_le_5") or std_report.get("contains_8_or_10_mps_std"):
            _fail("bounded std physical bound failed")
        if decision.get("update_count", 0) <= 0:
            _fail("adaptive update count is zero")
        if decision.get("go2_velocity_truth_claim") or decision.get("paper_performance_claim"):
            _fail("forbidden claim flag true")
        if decision.get("go2_vertical_velocity_prior_enabled") or decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled"):
            _fail("forbidden Go2 prior enabled")
        if figures.get("figure_count_total") != 10 or not figures.get("required_figures_nonempty"):
            _fail("required figures missing or empty")


def main() -> int:
    for item in REQUIRED_FILES:
        if not (ROOT / item).exists():
            _fail(f"missing file {item}")
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c3_go2_horizontal_velocity_bounded_adaptive_std passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
