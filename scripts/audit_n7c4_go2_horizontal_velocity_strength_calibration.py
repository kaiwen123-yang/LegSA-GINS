#!/usr/bin/env python3
"""Audit N7C4 Go2 horizontal velocity strength calibration workflow.

中文说明：本审计生成 toy runtime，检查 N7C4 confidence、prior strength、
ablation、NIS、图像和决策报告都满足边界。
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
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_calibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_confidence_recalibration.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_nis_diagnostics.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_strength_ablation.py",
    "src/legsa_gins/go2_prior/go2_n7c4_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c4_decision.py",
    "scripts/experiments/run_n7c4_go2_horizontal_velocity_strength_calibration.py",
    "scripts/audit_go2_prior_strength_no_trace_tuning.py",
    "scripts/audit_go2_prior_strength_vertical_disabled.py",
    "scripts/audit_go2_prior_strength_no_truth_claim.py",
    "docs/experiments/n7c4_go2_horizontal_velocity_strength_calibration.md",
    "docs/experiments/n7c4_confidence_recalibration.md",
    "docs/experiments/n7c4_prior_strength_ablation.md",
    "docs/experiments/n7c4_decision.md",
    "docs/codex_prompts/N7C4_go2_horizontal_velocity_strength_calibration.md",
]

REQUIRED_OUTPUTS = [
    "GO2_HORIZONTAL_VELOCITY_RECALIBRATED_CONFIDENCE_REPORT.json",
    "GO2_HORIZONTAL_VELOCITY_RECALIBRATED_CONFIDENCE_TIMESERIES.csv",
    "GO2_HORIZONTAL_VELOCITY_STRENGTH_PRIOR_BUILD_REPORT.json",
    "GO2_HORIZONTAL_VELOCITY_NIS_DIAGNOSTICS_REPORT.json",
    "N7C4_STRENGTH_ABLATION_MATRIX.json",
    "N7C4_STRENGTH_VARIANT_SUMMARIES.json",
    "N7C4_STRENGTH_COMPARISON_REPORT.json",
    "N7C4_STRENGTH_CALIBRATION_DECISION_REPORT.json",
    "N7C4_FIGURE_MANIFEST.json",
    "n7c4_strength_calibration_case_review.md",
]

ARTIFACT_RE = re.compile(r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|summary\.json|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)")


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c4_go2_horizontal_velocity_strength_calibration failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git_lines(args: list[str]) -> list[str]:
    proc = _run(["git", *args])
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _check_no_local_path_leak() -> None:
    for token in ["/mnt/c/" + "Users/ykw/Desktop", "/mnt/c/" + "Users/86187/Desktop", "C:" + "\\\\Users", "/home/kaiwen/" + "legsa_external_artifacts"]:
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
                    "quality_flag": "toy",
                    "contact_model": "toy",
                    "contact_label": "toy",
                    "frame_candidate": "toy_horizontal_equivalent",
                    "prior_policy": "n7c_go2_horizontal_velocity_weak_prior",
                    "diagnostic_only": "false",
                    "go2_velocity_truth_claim": "false",
                }
            )


def _write_contact_probability(path: Path, count: int = 80) -> None:
    fields = ["time", "model_id", "support_probability", "swing_probability", "uncertainty_probability", "confidence_score", "mode", "gait_type"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            support = 0.90 if index % 5 else 0.50
            writer.writerow({"time": f"{index * 0.1:.6f}", "model_id": "ensemble_probability", "support_probability": support, "swing_probability": 1 - support, "uncertainty_probability": 0.10, "confidence_score": 0.85, "mode": "walk", "gait_type": "trot"})


def _write_frame_equivalence(path: Path, count: int = 80) -> None:
    fields = ["time", "horizontal_difference_mps", "horizontal_angle_difference_deg", "diagnostic_only", "go2_velocity_truth_claim"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow({"time": f"{index * 0.1:.6f}", "horizontal_difference_mps": 0.04, "horizontal_angle_difference_deg": 2.0, "diagnostic_only": True, "go2_velocity_truth_claim": False})


def _write_velocity_csv(path: Path, count: int = 80) -> None:
    fields = ["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status", "quality_flag"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            writer.writerow({"time": f"{index * 0.1:.6f}", "vn": f"{0.82 + 0.01 * index:.6f}", "ve": "0.22", "vd": "0", "std_vn": "0.2", "std_ve": "0.2", "std_vd": "0.2", "sat_count": 8, "provider_status": "ok", "quality_flag": "usable"})


def _write_clean_gnss(path: Path, count: int = 80) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [f"{index * 0.1:.6f} 30 120 10 1 1 1 {0.82 + 0.01 * index:.6f} 0.22 0 1 1 1 5 1" for index in range(count)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_reference(path: Path, count: int = 80) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [f"0 {index * 0.1:.6f} {30 + index * 1e-9:.12f} {120 + index * 1e-9:.12f} 10 1 0.2 0 0 0 5" for index in range(count)]
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
updates=0; skips=0; stds=[]
if enabled and prior:
    with open(prior, newline='', encoding='utf-8-sig') as h:
        for row in csv.DictReader(h):
            update=str(row.get('update_flag','true')).lower() in {'true','1','yes'} and row.get('source_status','active')=='active'
            updates += int(update); skips += int(not update)
            if update: stds.append(float(row.get('std_vn') or 0))
std=min(stds or [2.0])
manifest={
 'ablation_variant': variant,
 'phase': 'N7C4',
 'go2_horizontal_velocity_strength_policy': after('go2_horizontal_velocity_strength_policy'),
 'go2_horizontal_velocity_prior_enabled': enabled,
 'go2_horizontal_velocity_prior_update_count': updates,
 'go2_velocity_prior_update_count': updates,
 'go2_velocity_prior_reject_count': 0,
 'go2_horizontal_velocity_prior_skip_count': skips,
 'go2_horizontal_velocity_prior_vertical_disabled': True,
 'go2_horizontal_velocity_prior_std_vn_p50': sorted(stds)[len(stds)//2] if stds else 0,
 'go2_horizontal_velocity_prior_std_vn_p95': sorted(stds)[int(0.95*(len(stds)-1))] if stds else 0,
 'go2_horizontal_velocity_prior_std_vn_max': max(stds) if stds else 0,
 'go2_position_prior_enabled': False,
 'go2_yaw_prior_enabled': False,
 'go2_velocity_truth_claim': False,
 'paper_performance_claim': False,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'fgo': False,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
offset={'fixed_1p0': 1e-10, 'fixed_1p5': 2e-10, 'fixed_0p75_aggressive': 5e-10, 'recalibrated_adaptive': 1e-10}.get(variant, 0.0)
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    for i in range(80):
        w.writerow({'time':i*0.1,'lat_deg':30+i*1e-9+offset,'lon_deg':120+i*1e-9+offset,'height_m':10,'vn':1,'ve':0.2,'vd':0,'roll_deg':0,'pitch_deg':0,'yaw_deg':5+offset*1e6})
with (out/'SOURCE_AWARE_WEIGHT_TRACE.csv').open('w', encoding='utf-8', newline='') as h:
    fields=['time','update_index','source_id','policy_version','mode','combined_R_scale','residual_norm','normalized_innovation','accepted','rejected','reason_codes']
    w=csv.DictWriter(h, fieldnames=fields); w.writeheader()
    normalized=0.7 if std >= 1.0 else 1.4
    for i in range(max(1, min(updates, 20))):
        w.writerow({'time':i*0.2,'update_index':i,'source_id':'go2_horizontal_velocity','policy_version':'n7c4','mode':'lsim_oim','combined_R_scale':1.0,'residual_norm':0.25,'normalized_innovation':normalized,'accepted':1,'rejected':0,'reason_codes':'toy'})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path):
    n7c = root / "n7c"
    n7b4 = root / "n7b4"
    n7b5 = root / "n7b5"
    n5b = root / "n5b"
    clean = root / "clean"
    dual = root / "dual"
    _write_prior_csv(n7c / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv")
    _write_contact_probability(n7b4 / "GO2_CONTACT_PROBABILITY_TIMESERIES.csv")
    _write_json(n7b4 / "GO2_CONTACT_PROBABILITY_MODEL_REPORT.json", {"selected_contact_probability_model": "ensemble_probability"})
    _write_frame_equivalence(n7b5 / "GO2_FRAME_EQUIVALENCE_TIMESERIES.csv")
    _write_json(n7b5 / "GO2_FRAME_EQUIVALENCE_REVIEW_REPORT.json", {"frame_equivalent_for_horizontal_only": True})
    _write_velocity_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    _write_clean_gnss(clean / "input.gnss")
    (clean / "clean.yaml").write_text("imupath: input.imu\ngnsspath: input.gnss\n", encoding="utf-8")
    _write_reference(dual / "KF_GINS_Navresult.nav")
    exe = root / "fake_demo.py"
    _write_fake_exe(exe)
    return n7c, root / "n7c1", root / "n7c2", root / "n7c3", n7b5, n7b4, n5b, clean, dual, exe


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c4_strength_") as tmp_value:
        tmp = Path(tmp_value)
        n7c, n7c1, n7c2, n7c3, n7b5, n7b4, n5b, clean, dual, exe = _prepare_runtime(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c4_go2_horizontal_velocity_strength_calibration.py"),
            "--n7c-root", str(n7c),
            "--n7c1-root", str(n7c1),
            "--n7c2-root", str(n7c2),
            "--n7c3-root", str(n7c3),
            "--n7b5-root", str(n7b5),
            "--n7b4-root", str(n7b4),
            "--n5b-root", str(n5b),
            "--n6b-root", str(tmp / "n6b"),
            "--clean-root", str(clean),
            "--dual-root", str(dual),
            "--output-dir", str(out),
            "--figure-output-dir", str(figs),
            "--build-dir", str(tmp / "build"),
            "--exe", str(exe),
            "--allow-run",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            _fail(proc.stderr[-4000:] or proc.stdout[-4000:])
        for item in REQUIRED_OUTPUTS:
            if not (out / item).exists():
                _fail(f"missing output {item}")
        decision = json.loads((out / "N7C4_STRENGTH_CALIBRATION_DECISION_REPORT.json").read_text(encoding="utf-8"))
        confidence = json.loads((out / "GO2_HORIZONTAL_VELOCITY_RECALIBRATED_CONFIDENCE_REPORT.json").read_text(encoding="utf-8"))
        figures = json.loads((out / "N7C4_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        if sum(confidence.get("confidence_counts", {}).values()) <= 0:
            _fail("confidence counts missing")
        if not decision.get("recommended_default_policy"):
            _fail("recommended default policy missing")
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
    print("audit_n7c4_go2_horizontal_velocity_strength_calibration passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
