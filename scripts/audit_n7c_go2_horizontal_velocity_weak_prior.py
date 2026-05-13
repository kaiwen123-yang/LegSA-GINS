#!/usr/bin/env python3
"""Audit N7C Go2 horizontal velocity weak-prior workflow.

中文说明：使用临时合成数据验证 runner、报告、图像和边界；不写入 Git。
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
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_builder.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_prior_policy.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_activation_runner.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_ablation.py",
    "src/legsa_gins/go2_prior/go2_horizontal_velocity_visual_plots.py",
    "src/legsa_gins/go2_prior/go2_n7c_decision.py",
    "scripts/experiments/run_n7c_go2_horizontal_velocity_weak_prior.py",
    "docs/experiments/n7c_go2_horizontal_velocity_weak_prior.md",
    "docs/experiments/n7c_horizontal_velocity_policy.md",
    "docs/experiments/n7c_ablation_protocol.md",
    "docs/experiments/n7c_decision.md",
    "docs/experiments/n7c_next_stage_plan.md",
    "docs/codex_prompts/N7C_go2_horizontal_velocity_weak_prior.md",
]

REQUIRED_OUTPUTS = [
    "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json",
    "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json",
    "N7C_FIGURE_MANIFEST.json",
    "n7c_go2_horizontal_velocity_case_review.md",
]


def _fail(message: str) -> None:
    raise SystemExit(f"audit_n7c_go2_horizontal_velocity_weak_prior failed: {message}")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_prior_csv(path: Path, count: int = 30) -> None:
    fields = [
        "time",
        "vn",
        "ve",
        "vd",
        "std_vn",
        "std_ve",
        "std_vd",
        "source_status",
        "quality_flag",
        "contact_model",
        "contact_label",
        "frame_candidate",
        "prior_policy",
        "diagnostic_only",
        "go2_velocity_truth_claim",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(count):
            bucket = "high" if index % 5 == 0 else ("medium" if index % 2 == 0 else "low")
            writer.writerow(
                {
                    "time": index * 0.1,
                    "vn": 1.0 + index * 0.01,
                    "ve": 0.2,
                    "vd": 0.0,
                    "std_vn": 2.0,
                    "std_ve": 2.0,
                    "std_vd": 999.0,
                    "source_status": "active",
                    "quality_flag": f"diagnostic_horizontal_{bucket}_confidence",
                    "contact_model": "toy",
                    "contact_label": bucket,
                    "frame_candidate": "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
                    "prior_policy": "best_frame_horizontal_only_diagnostic",
                    "diagnostic_only": True,
                    "go2_velocity_truth_claim": False,
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
def after(key):
    for line in config.splitlines():
        if line.strip().startswith(key+':'):
            return line.split(':',1)[1].strip().strip('"')
    return ''
enabled='enable_go2_horizontal_velocity_prior: true' in config
prior=after('go2_horizontal_velocity_prior_path')
rows=0
if enabled and prior:
    with open(prior, newline='', encoding='utf-8-sig') as h:
        rows=max(0, sum(1 for _ in csv.DictReader(h)))
manifest={
 'ablation_variant': out.name,
 'paper_performance_claim': False,
 'trace_solver_input': False,
 'final_v23_output_solver_input': False,
 'go2_horizontal_velocity_prior_enabled': enabled,
 'go2_velocity_prior_update_count': rows,
 'go2_velocity_prior_reject_count': 0,
 'go2_horizontal_velocity_prior_update_count': rows,
 'go2_horizontal_velocity_prior_vertical_disabled': True,
 'go2_position_prior_enabled': False,
 'go2_yaw_prior_enabled': False,
 'fgo_enabled': False,
 'measurement_update_count': 30,
 'raw_doppler_update_count': 30,
}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\\n', encoding='utf-8')
with (out/'EVAL_NAV.csv').open('w', encoding='utf-8', newline='') as h:
    w=csv.DictWriter(h, fieldnames=['time','lat_deg','lon_deg','height_m','vn','ve','vd','roll_deg','pitch_deg','yaw_deg'])
    w.writeheader()
    for i in range(30):
        w.writerow({'time':i*0.1,'lat_deg':30,'lon_deg':120,'height_m':10,'vn':1+i*0.01,'ve':0.2,'vd':0,'roll_deg':0,'pitch_deg':0,'yaw_deg':5})
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    n7b5 = root / "n7b5"
    _write_prior_csv(n7b5 / "GO2_HORIZONTAL_VELOCITY_PRIORS_DIAGNOSTIC.csv")
    _write_prior_csv(n7b5 / "GO2_HORIZONTAL_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv")
    _write_prior_csv(n7b5 / "GO2_HORIZONTAL_VELOCITY_CONTACT_WEIGHTED_PRIORS_DIAGNOSTIC.csv", count=18)
    _write_json(
        n7b5 / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json",
        {"std_policy": {"base_std_mps": 2.0}, "csv_generated": True, "epoch_count": 30},
    )
    clean = root / "clean"
    clean.mkdir(parents=True, exist_ok=True)
    (clean / "kf-gins-n4h2g-clean-replay.yaml").write_text("imupath: input.imu\ngnsspath: input.gnss\n", encoding="utf-8")
    (clean / "input.gnss").write_text("0 30 120 10 1 1 1 1 0.2 0 1 1 1 5 1\n", encoding="utf-8")
    n5b = root / "n5b"
    _write_prior_csv(n5b / "RAW_DOPPLER_VELOCITY_FACTORS.csv")
    exe = root / "fake_demo.py"
    _write_fake_exe(exe)
    return n7b5, root / "n7a", n5b, root / "n6b", clean


def main() -> int:
    for item in REQUIRED_FILES:
        if not (ROOT / item).exists():
            _fail(f"missing file {item}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        n7b5, n7a, n5b, n6b, clean = _prepare_runtime(work)
        out = work / "out"
        figs = work / "figs"
        cmd = [
            sys.executable,
            str(ROOT / "scripts/experiments/run_n7c_go2_horizontal_velocity_weak_prior.py"),
            "--n7b5-root",
            str(n7b5),
            "--n7a-root",
            str(n7a),
            "--n5b-root",
            str(n5b),
            "--n6b-root",
            str(n6b),
            "--clean-root",
            str(clean),
            "--dual-root",
            str(work / "dual"),
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--build-dir",
            str(work / "build"),
            "--exe",
            str(work / "fake_demo.py"),
            "--allow-run",
            "--run-stress",
            "true",
        ]
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            _fail(proc.stderr[-2000:] or proc.stdout[-2000:])
        for item in REQUIRED_OUTPUTS:
            if not (out / item).exists():
                _fail(f"missing output {item}")
        decision = json.loads((out / "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json").read_text(encoding="utf-8"))
        if decision.get("paper_performance_claim") or decision.get("go2_velocity_truth_claim"):
            _fail("forbidden claim flag true")
        if decision.get("update_count", 0) <= 0:
            _fail("N7C toy update_count did not activate")
    print("audit_n7c_go2_horizontal_velocity_weak_prior passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
