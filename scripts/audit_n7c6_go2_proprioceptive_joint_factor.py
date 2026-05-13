#!/usr/bin/env python3
"""Audit N7C6 Go2 proprioceptive joint observation factor workflow.

中文说明：用 toy runtime 审计 N7C6 joint factor 的产物和边界。
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
    "src/legsa_gins/go2_prior/go2_attitude_strength_calibration.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_builder.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_policy.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_jacobian.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_ablation.py",
    "src/legsa_gins/go2_prior/go2_proprioceptive_joint_factor_nis.py",
    "src/legsa_gins/go2_prior/go2_n7c6_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c6_decision.py",
    "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py",
    "scripts/audit_go2_proprioceptive_joint_factor_no_truth.py",
    "scripts/audit_go2_proprioceptive_joint_factor_jacobian.py",
    "scripts/audit_go2_position_yaw_vertical_disabled.py",
    "scripts/audit_go2_proprioceptive_joint_no_trace_tuning.py",
    "docs/experiments/n7c6_go2_proprioceptive_joint_factor.md",
    "docs/experiments/n7c6_attitude_strength_calibration.md",
    "docs/experiments/n7c6_factor_jacobian_contract.md",
    "docs/experiments/n7c6_ablation_protocol.md",
    "docs/experiments/n7c6_decision.md",
    "docs/codex_prompts/N7C6_go2_proprioceptive_joint_factor.md",
]

REQUIRED_OUTPUTS = [
    "GO2_PROPRIOCEPTIVE_JOINT_FACTOR_PRIOR_BUILD_REPORT.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_VARIANT_SUMMARIES.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_COMPARISON_REPORT.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_NIS_REPORT.json",
    "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_JACOBIAN_REPORT.json",
    "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json",
    "N7C6_FIGURE_MANIFEST.json",
    "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_RUN_REPORT.json",
    "n7c6_go2_proprioceptive_joint_factor_case_review.md",
]

ARTIFACT_RE = re.compile(
    r"(by2\.txt|GO2_BODY_STATE_STANDARDIZED\.csv|GO2_PROPRIOCEPTIVE_FACTOR_PRIORS\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c6_go2_proprioceptive_joint_factor failed: {message}")


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


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_go2_body_state(path: Path, count: int = 80) -> None:
    rows = []
    for index in range(count):
        t = index * 0.1
        row = {
            "time": t,
            "aligned_time": t,
            "roll_rad": 0.01,
            "pitch_rad": -0.01,
            "yaw_rad": 0.02 * t,
            "mode": "walk",
            "gait_type": "trot",
            "body_height": 0.32,
            "not_truth": "true",
        }
        for foot in range(4):
            row[f"foot_force_{foot}"] = 80.0
        rows.append(row)
    _write_csv(path, rows)


def _write_horizontal_prior(path: Path, count: int = 80) -> None:
    rows = [
        {
            "time": index * 0.1,
            "vn": 1.0,
            "ve": 0.2,
            "vd": 0.0,
            "std_vn": 1.0,
            "std_ve": 1.0,
            "std_vd": 999.0,
            "confidence": 0.8,
            "confidence_level": "high",
            "update_flag": "true",
            "reason_codes": "toy",
            "source_status": "active",
            "quality_flag": "toy",
            "contact_model": "toy",
            "contact_label": "toy",
            "frame_candidate": "toy",
            "prior_policy": "fixed_1p0",
            "diagnostic_only": "false",
            "go2_velocity_truth_claim": "false",
        }
        for index in range(count)
    ]
    _write_csv(path, rows)


def _write_raw(path: Path, count: int = 80) -> None:
    rows = [
        {
            "time": index * 0.1,
            "vn": 1.0,
            "ve": 0.2,
            "vd": 0.0,
            "std_vn": 0.2,
            "std_ve": 0.2,
            "std_vd": 0.2,
            "sat_count": 8,
            "provider_status": "ok",
            "quality_flag": "toy",
        }
        for index in range(count)
    ]
    _write_csv(path, rows)


def _write_reference(path: Path, count: int = 80) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [f"0 {index * 0.1:.6f} {30 + index * 1e-9:.12f} {120 + index * 1e-9:.12f} 10 1 0.2 0 0 0 5" for index in range(count)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_fake_exe(path: Path, count: int = 80) -> None:
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
joint=after('enable_go2_proprioceptive_joint_factor').lower() == 'true'
att=after('enable_go2_attitude_weak_prior').lower() == 'true'
hv=after('enable_go2_horizontal_velocity_prior').lower() == 'true'
rp=float(after('go2_attitude_prior_std_roll_deg') or 5.0)
updates=80 if (joint or att or hv) else 0
manifest={
 'ablation_variant': variant,
 'phase': 'N7C6',
 'go2_proprioceptive_joint_factor_enabled': joint,
 'go2_proprioceptive_joint_factor_update_count': 80 if joint else 0,
 'go2_proprioceptive_joint_factor_reject_count': 0,
 'go2_proprioceptive_joint_factor_mode': after('go2_proprioceptive_joint_factor_mode'),
 'go2_proprioceptive_joint_factor_policy': after('go2_proprioceptive_joint_factor_policy'),
 'go2_proprioceptive_joint_factor_sequential_equivalent': joint,
 'go2_attitude_prior_update_count': 80 if att else 0,
 'go2_horizontal_velocity_prior_update_count': 80 if hv else 0,
 'go2_velocity_prior_update_count': 80 if hv else 0,
 'go2_velocity_prior_reject_count': 0,
 'go2_position_prior_enabled': False,
 'go2_yaw_prior_enabled': False,
 'go2_vertical_velocity_prior_enabled': False,
 'go2_velocity_truth_claim': False,
 'go2_roll_pitch_truth_claim': False,
 'paper_performance_claim': False,
 'no_outperform_final_v23_claim': True,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'fgo': False,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
offset={'joint_rp1p6deg_hv1p0': 1e-10, 'joint_rp1deg_hv1p0': 1e-10, 'horizontal_only_fixed_1p0': 1e-10}.get(variant, 0.0)
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    for i in range(80):
        w.writerow({'time':i*0.1,'lat_deg':30+i*1e-9+offset,'lon_deg':120+i*1e-9+offset,'height_m':10,'vn':1,'ve':0.2,'vd':0,'roll_deg':0.02 if att else 0.03,'pitch_deg':-0.02 if att else -0.03,'yaw_deg':5})
with (out/'SOURCE_AWARE_WEIGHT_TRACE.csv').open('w', encoding='utf-8', newline='') as h:
    fields=['time','update_index','source_id','policy_version','mode','combined_R_scale','residual_norm','normalized_innovation','accepted','rejected','reason_codes']
    w=csv.DictWriter(h, fieldnames=fields); w.writeheader()
    if att:
        for i in range(updates):
            w.writerow({'time':i*0.1,'update_index':i,'source_id':'go2_attitude_roll_pitch','policy_version':'n7c6','mode':'lsim_oim','combined_R_scale':1.0,'residual_norm':0.01,'normalized_innovation':0.8 if rp >= 1.0 else 1.4,'accepted':1,'rejected':0,'reason_codes':'toy'})
    if hv:
        for i in range(updates):
            w.writerow({'time':i*0.1,'update_index':i,'source_id':'go2_horizontal_velocity','policy_version':'n7c6','mode':'lsim_oim','combined_R_scale':1.0,'residual_norm':0.2,'normalized_innovation':0.9,'accepted':1,'rejected':0,'reason_codes':'toy'})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path):
    n7a = root / "n7a"
    n7c = root / "n7c"
    n7c2 = root / "n7c2"
    n7c4 = root / "n7c4"
    n7c5 = root / "n7c5"
    n7c5a = root / "n7c5a"
    n7b5 = root / "n7b5"
    n5b = root / "n5b"
    clean = root / "clean"
    dual = root / "dual"
    _write_go2_body_state(n7a / "GO2_BODY_STATE_STANDARDIZED.csv")
    _write_horizontal_prior(n7c4 / "GO2_HORIZONTAL_VELOCITY_STRENGTH_FIXED_1P0_PRIORS.csv")
    _write_raw(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    clean.mkdir(parents=True, exist_ok=True)
    (clean / "clean.yaml").write_text("imupath: input.imu\ngnsspath: input.gnss\n", encoding="utf-8")
    _write_reference(dual / "KF_GINS_Navresult.nav")
    _write_json(n7c5a / "N7C5A_VISUAL_DECISION_REPORT.json", {"status": "n7c5_visual_review_passed"})
    for path in [n7c, n7c2, n7c5, n7b5, root / "n6b"]:
        path.mkdir(parents=True, exist_ok=True)
    exe = root / "fake_demo.py"
    _write_fake_exe(exe)
    return n7a, n7c, n7c2, n7c4, n7c5, n7c5a, n7b5, n5b, root / "n6b", clean, dual, exe


def _toy_run() -> None:
    with tempfile.TemporaryDirectory(prefix="legsa_n7c6_joint_") as tmp_value:
        tmp = Path(tmp_value)
        n7a, n7c, n7c2, n7c4, n7c5, n7c5a, n7b5, n5b, n6b, clean, dual, exe = _prepare_runtime(tmp)
        out = tmp / "out"
        figs = tmp / "figs"
        proc = _run(
            [
                sys.executable,
                str(ROOT / "scripts/experiments/run_n7c6_go2_proprioceptive_joint_factor.py"),
                "--n7a-root",
                str(n7a),
                "--n7c-root",
                str(n7c),
                "--n7c2-root",
                str(n7c2),
                "--n7c4-root",
                str(n7c4),
                "--n7c5-root",
                str(n7c5),
                "--n7c5a-root",
                str(n7c5a),
                "--n7b5-root",
                str(n7b5),
                "--n5b-root",
                str(n5b),
                "--n6b-root",
                str(n6b),
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
                "--run-stress",
                "true",
            ]
        )
        if proc.returncode != 0:
            _fail(proc.stdout[-4000:] + proc.stderr[-4000:])
        for rel in REQUIRED_OUTPUTS:
            if not (out / rel).exists():
                _fail(f"missing output {rel}")
        decision = json.loads((out / "N7C6_GO2_PROPRIOCEPTIVE_JOINT_FACTOR_DECISION_REPORT.json").read_text(encoding="utf-8"))
        figures = json.loads((out / "N7C6_FIGURE_MANIFEST.json").read_text(encoding="utf-8"))
        jacobian = json.loads((out / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_JACOBIAN_REPORT.json").read_text(encoding="utf-8"))
        matrix = json.loads((out / "N7C6_PROPRIOCEPTIVE_JOINT_FACTOR_ABLATION_MATRIX.json").read_text(encoding="utf-8"))
        if not matrix.get("required_variants_present"):
            _fail("required variants missing")
        if jacobian.get("finite_difference_check_status") != "toy_passed":
            _fail("jacobian toy check did not pass")
        if decision.get("go2_position_prior_enabled") or decision.get("go2_yaw_prior_enabled") or decision.get("go2_vertical_velocity_prior_enabled"):
            _fail("forbidden Go2 prior enabled")
        if not decision.get("go2_not_truth") or decision.get("paper_performance_claim"):
            _fail("truth/claim boundary invalid")
        if figures.get("figure_count_total") != 12 or not figures.get("required_figures_nonempty"):
            _fail("required figures missing or empty")


def main() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))
    _check_no_local_path_leak()
    _check_no_forbidden_tracked_artifacts()
    _toy_run()
    print("audit_n7c6_go2_proprioceptive_joint_factor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
