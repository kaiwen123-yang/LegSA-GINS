#!/usr/bin/env python3
"""Audit N4H4E1 STD unit and plot semantics fix tooling.

中文说明：该审计只运行 toy 数据和 tracked 文件检查；不读取真实大数据，
不提交图像，不做 paper performance claim。
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOY = Path(tempfile.gettempdir()) / f"legsa_n4h4e1_visual_fix_audit_{os.getpid()}"
LOCAL_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4e_visual_validation",
    "/home/kaiwen" + "/legsa_n4h4r3c_metric_namespace",
    "/home/kaiwen" + "/legsa_external_artifacts",
]
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$|\.jpg$|\.jpeg$)"
)
FALSE_FLAGS = [
    "paper_performance_claim",
    "proposed_factor_claim",
    "trace_solver_input",
    "final_v23_output_solver_input",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)


def _fail(message: str, details: list[str] | None = None) -> int:
    print(f"N4H4E1 visual fix audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _check_files() -> int:
    required = [
        "src/legsa_gins/visualization/legsa_v23_port_std_unit_audit.py",
        "src/legsa_gins/visualization/legsa_v23_port_plot_semantics_fix.py",
        "src/legsa_gins/visualization/legsa_v23_port_visual_e1_report.py",
        "scripts/experiments/run_legsa_v23_port_visual_e1_fix.py",
        "scripts/audit_legsa_v23_port_visual_e1_fix.py",
        "docs/experiments/n4h4e1_std_unit_consistency.md",
        "docs/experiments/n4h4e1_plot_semantics_fix.md",
        "docs/experiments/n4h4e1_visual_decision.md",
        "docs/codex_prompts/N4H4E1_std_unit_plot_semantics_fix.md",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    return _fail("missing required files", missing) if missing else 0


def _rows(offset_h: float = 0.0, yaw_offset: float = 0.0) -> list[dict[str, float]]:
    lat_offset = offset_h / 6378137.0 * 180.0 / math.pi
    rows = []
    for index in range(160):
        rows.append(
            {
                "time": index * 0.01,
                "lat_deg": 30.0 + lat_offset + index * 1.0e-7,
                "lon_deg": 120.0 + index * 1.0e-7,
                "height_m": 10.0 + 0.01 * math.sin(index / 10.0),
                "roll_deg": 0.1 * math.sin(index / 20.0),
                "pitch_deg": 0.1 * math.cos(index / 22.0),
                "yaw_deg": 5.0 + yaw_offset + 0.1 * math.sin(index / 18.0),
            }
        )
    return rows


def _write_csv_nav(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_kfgins_nav(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            f"0 {row['time']:.3f} {row['lat_deg']:.10f} {row['lon_deg']:.10f} {row['height_m']:.4f} "
            f"0 0 0 {row['roll_deg']:.6f} {row['pitch_deg']:.6f} {row['yaw_deg']:.6f}\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _write_port_std_rad(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", *[f"std_{index}" for index in range(21)]])
        for index in range(count):
            attitude = math.radians(2.0 if index == 0 else 0.2)
            writer.writerow([index, 1, 1, 1, 0.1, 0.1, 0.1, attitude, attitude, attitude, *([0] * 12)])


def _write_kfgins_std(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(f"{index*0.01:.3f} 1 1 1 0.1 0.1 0.1 2 2 2 0 0 0 0 0 0 0 0 0 0 0 0\n")
    path.write_text("".join(rows), encoding="utf-8")


def _write_r3c(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    reports = {
        "PORT_VS_FINALV23_NAV_PARITY_REPORT.json": {"parity_small": True, "horizontal_rmse_m": 0.05, "up_rmse_m": 0.05, "yaw_rmse_deg": 0.2, "roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1},
        "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json": {"official_summary_reproduced": True, "horizontal_rmse_m": 0.35, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.8},
        "PORT_VS_TRACE_ABSOLUTE_REPORT.json": {"horizontal_rmse_m": 0.36, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.9},
        "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json": {"port_absolute_close_to_finalv23_absolute": True},
        "PORT_METRIC_NAMESPACE_DECISION_REPORT.json": {"engineering_backbone_candidate": True},
    }
    common = {
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    for name, data in reports.items():
        (root / name).write_text(json.dumps({**data, **common}, indent=2) + "\n", encoding="utf-8")


def _make_toy() -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    shutil.rmtree(TOY, ignore_errors=True)
    r3 = TOY / "r3"
    r3a = TOY / "r3a"
    r3b = TOY / "r3b"
    r3c = TOY / "r3c"
    n4h4e = TOY / "n4h4e"
    dual = TOY / "dual"
    trace = TOY / "trace.csv"
    port_rows = _rows(offset_h=0.03, yaw_offset=0.05)
    final_rows = _rows(offset_h=0.0, yaw_offset=0.0)
    trace_rows = _rows(offset_h=-0.3, yaw_offset=-1.8)
    _write_csv_nav(r3a / "run" / "EVAL_NAV.csv", port_rows)
    _write_port_std_rad(r3a / "run" / "LegSA_PORT_STD.csv", len(port_rows))
    _write_kfgins_nav(dual / "KF_GINS_Navresult.nav", final_rows)
    _write_kfgins_std(dual / "KF_GINS_STD.txt", len(final_rows))
    _write_csv_nav(trace, trace_rows)
    _write_r3c(r3c)
    r3.mkdir(parents=True, exist_ok=True)
    r3b.mkdir(parents=True, exist_ok=True)
    n4h4e.mkdir(parents=True, exist_ok=True)
    (n4h4e / "FIGURE_MANIFEST.json").write_text(
        json.dumps({"figure_paths": ["01_trajectory/trajectory_xy_error_to_reference.png", "01_trajectory/trajectory_xy_port_minus_finalv23_zoom.png"]}) + "\n",
        encoding="utf-8",
    )
    return r3, r3a, r3b, r3c, n4h4e, dual, trace


def _run_toy() -> int:
    r3, r3a, r3b, r3c, n4h4e, dual, trace = _make_toy()
    out = TOY / "reports"
    figs = TOY / "figs"
    result = _run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_visual_e1_fix.py",
            "--n4h4e-root",
            str(n4h4e),
            "--r3-root",
            str(r3),
            "--r3a-root",
            str(r3a),
            "--r3b-root",
            str(r3b),
            "--r3c-root",
            str(r3c),
            "--dual-root",
            str(dual),
            "--report-output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--trace-path",
            str(trace),
            "--allow-run",
        ]
    )
    if result.returncode != 0:
        return _fail("toy E1 visual fix failed", [result.stdout, result.stderr])
    for name in ["STD_UNIT_AUDIT_REPORT.json", "PLOT_SEMANTICS_FIX_REPORT.json", "VISUAL_VALIDATION_E1_REPORT.json", "VISUAL_SANITY_E1_REPORT.json", "FIGURE_MANIFEST_E1.json"]:
        if not (out / name).exists():
            return _fail("toy report missing", [name])
    std = json.loads((out / "STD_UNIT_AUDIT_REPORT.json").read_text(encoding="utf-8"))
    plot = json.loads((out / "PLOT_SEMANTICS_FIX_REPORT.json").read_text(encoding="utf-8"))
    visual = json.loads((out / "VISUAL_VALIDATION_E1_REPORT.json").read_text(encoding="utf-8"))
    for data in [std, plot, visual]:
        bad = [flag for flag in FALSE_FLAGS if data.get(flag) is not False]
        if bad or data.get("no_outperform_final_v23_claim") is not True:
            return _fail("toy boundary flags invalid", bad)
    if std["port_attitude_std_unit"] != "rad" or std["finalv23_attitude_std_unit"] != "deg":
        return _fail("toy STD unit inference failed", [json.dumps(std, indent=2)])
    if not plot["vector_xy_line_removed"] or not plot["vector_cloud_scatter_created"]:
        return _fail("toy plot semantics not fixed", [json.dumps(plot, indent=2)])
    figures = list(figs.rglob("*.png"))
    if len(figures) < 10:
        return _fail("toy corrected figure count below expected", [str(len(figures))])
    pure_single = [str(path) for path in figures if "pure" in path.name.lower() or "single" in path.name.lower()]
    if pure_single:
        return _fail("pure/single figure generated", pure_single)
    if not (figs / "09_case_review" / "visual_case_review_e1.md").exists():
        return _fail("toy case review missing")
    return 0


def _tracked_files() -> list[str]:
    result = _run(["git", "ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _check_no_artifacts_or_paths() -> int:
    artifact_hits: list[str] = []
    path_hits: list[str] = []
    for rel in _tracked_files():
        if rel == "reference/final_v23_repo" or rel.startswith("reference/final_v23_repo/"):
            continue
        if ARTIFACT_RE.search(rel):
            artifact_hits.append(rel)
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in LOCAL_PATTERNS:
            if pattern in text:
                path_hits.append(f"{rel}: {pattern}")
    if artifact_hits:
        return _fail("tracked artifact or figure detected", artifact_hits)
    if path_hits:
        return _fail("local path leakage detected", path_hits)
    return 0


def main() -> int:
    for check in [_check_files, _run_toy, _check_no_artifacts_or_paths]:
        result = check()
        if result:
            return result
    print("N4H4E1 visual fix audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
