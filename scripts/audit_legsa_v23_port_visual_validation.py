#!/usr/bin/env python3
"""Audit N4H4E source-backed port visual validation tooling.

中文说明：该审计只检查模块、docs、toy 图像输出和边界旗标；不读取真实大数据，
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
TOY = Path(tempfile.gettempdir()) / f"legsa_n4h4e_visual_validation_audit_{os.getpid()}"
LOCAL_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4e_visual_validation",
    "/home/kaiwen" + "/legsa_n4h4r3c_metric_namespace",
    "/home/kaiwen" + "/legsa_n4h4r3b_overclose_audit",
    "/home/kaiwen" + "/legsa_n4h4r3a_update_timeline",
    "/home/kaiwen" + "/legsa_n4h4r3_port_clean_parity",
    "/home/kaiwen" + "/legsa_n4h2g_clean_replay",
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
    print(f"N4H4E visual validation audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _check_files() -> int:
    required = [
        "src/legsa_gins/visualization/__init__.py",
        "src/legsa_gins/visualization/legsa_v23_port_visual_loader.py",
        "src/legsa_gins/visualization/legsa_v23_port_visual_plots.py",
        "src/legsa_gins/visualization/legsa_v23_port_visual_sanity.py",
        "src/legsa_gins/visualization/legsa_v23_port_visual_report.py",
        "scripts/experiments/run_legsa_v23_port_visual_validation.py",
        "docs/experiments/n4h4e_source_backed_port_visual_validation.md",
        "docs/experiments/n4h4e_visual_plot_catalog.md",
        "docs/experiments/n4h4e_visual_decision.md",
        "docs/codex_prompts/N4H4E_source_backed_port_visual_validation.md",
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


def _write_std(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", *[f"std_{index}" for index in range(21)]])
        for index in range(count):
            writer.writerow([index, 1, 1, 1, 0, 0, 0, 2, 2, 2, *([0] * 12)])


def _write_kfgins_std(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(f"{index*0.01:.3f} 1 1 1 0 0 0 2 2 2 0 0 0 0 0 0 0 0 0 0 0 0\n")
    path.write_text("".join(rows), encoding="utf-8")


def _write_r3c(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    reports = {
        "PORT_VS_FINALV23_NAV_PARITY_REPORT.json": {"parity_small": True, "horizontal_rmse_m": 0.05, "up_rmse_m": 0.05, "yaw_rmse_deg": 0.2, "roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.1, "paper_performance_claim": False},
        "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json": {"official_summary_reproduced": True, "horizontal_rmse_m": 0.35, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.8, "paper_performance_claim": False},
        "PORT_VS_TRACE_ABSOLUTE_REPORT.json": {"horizontal_rmse_m": 0.36, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.9, "paper_performance_claim": False},
        "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json": {"port_absolute_close_to_finalv23_absolute": True, "paper_performance_claim": False},
        "PORT_METRIC_NAMESPACE_DECISION_REPORT.json": {"engineering_backbone_candidate": True, "paper_performance_claim": False},
    }
    for name, data in reports.items():
        common = {
            "proposed_factor_claim": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "no_outperform_final_v23_claim": True,
        }
        (root / name).write_text(json.dumps({**data, **common}, indent=2) + "\n", encoding="utf-8")


def _make_toy() -> tuple[Path, Path, Path, Path, Path, Path]:
    shutil.rmtree(TOY, ignore_errors=True)
    r3 = TOY / "r3"
    r3a = TOY / "r3a"
    r3b = TOY / "r3b"
    r3c = TOY / "r3c"
    dual = TOY / "dual"
    trace = TOY / "trace.csv"
    port_rows = _rows(offset_h=0.03, yaw_offset=0.05)
    final_rows = _rows(offset_h=0.0, yaw_offset=0.0)
    trace_rows = _rows(offset_h=-0.3, yaw_offset=-1.8)
    _write_csv_nav(r3a / "run" / "EVAL_NAV.csv", port_rows)
    _write_kfgins_nav(r3a / "run" / "LegSA_PORT_NAV.nav", port_rows)
    _write_std(r3a / "run" / "LegSA_PORT_STD.csv", len(port_rows))
    _write_kfgins_nav(dual / "KF_GINS_Navresult.nav", final_rows)
    _write_kfgins_std(dual / "KF_GINS_STD.txt", len(final_rows))
    (dual / "summary.json").write_text("{}\n", encoding="utf-8")
    _write_csv_nav(trace, trace_rows)
    _write_r3c(r3c)
    with (r3a / "PORT_GNSS_UPDATE_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["update_index", "gnss_time", "position_update", "velocity_update", "yaw_update", "yaw_mode"])
        writer.writeheader()
        for index in range(20):
            writer.writerow({"update_index": index, "gnss_time": index * 0.1, "position_update": 1, "velocity_update": 1, "yaw_update": 1, "yaw_mode": "NORMAL"})
    r3b.mkdir(parents=True, exist_ok=True)
    with (r3b / "PORT_UPDATE_RESIDUAL_GAIN_TRACE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["update_index", "gnss_time", "yaw_residual_deg"])
        writer.writeheader()
        for index in range(20):
            writer.writerow({"update_index": index, "gnss_time": index * 0.1, "yaw_residual_deg": 0.1 * index})
    r3.mkdir(parents=True, exist_ok=True)
    return r3, r3a, r3b, r3c, dual, trace


def _run_toy() -> int:
    r3, r3a, r3b, r3c, dual, trace = _make_toy()
    out = TOY / "out"
    figs = TOY / "figs"
    result = _run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_visual_validation.py",
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
            "--output-dir",
            str(out),
            "--figure-output-dir",
            str(figs),
            "--trace-path",
            str(trace),
            "--allow-run",
        ]
    )
    if result.returncode != 0:
        return _fail("toy visual validation failed", [result.stdout, result.stderr])
    for name in ["VISUAL_INPUT_MANIFEST.json", "VISUAL_VALIDATION_REPORT.json", "VISUAL_SANITY_REPORT.json", "FIGURE_MANIFEST.json"]:
        if not (out / name).exists():
            return _fail("toy report missing", [name])
    data = json.loads((out / "VISUAL_VALIDATION_REPORT.json").read_text(encoding="utf-8"))
    bad = [flag for flag in FALSE_FLAGS if data.get(flag) is not False]
    if bad or data.get("no_outperform_final_v23_claim") is not True:
        return _fail("toy visual report boundary flags invalid", bad)
    figures = list(figs.rglob("*.png"))
    if len(figures) < 30:
        return _fail("toy figure count below 30", [str(len(figures))])
    pure_single = [str(path) for path in figures if "pure" in path.name.lower() or "single" in path.name.lower()]
    if pure_single:
        return _fail("pure/single figure generated", pure_single)
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
    print("N4H4E visual validation audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
