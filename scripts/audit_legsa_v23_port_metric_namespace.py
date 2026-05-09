#!/usr/bin/env python3
"""Audit N4H4R3C metric namespace tooling and boundaries.

中文说明：该审计只检查 R3C 模块、runner、docs、toy 报告和边界旗标，
不读取或提交真实 runtime artifacts，也不做性能结论。
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.evaluation.legsa_v23_port_metric_namespace import MetricNamespace, classify_metric_namespace
from legsa_gins.evaluation.legsa_v23_port_parity_vs_absolute import compare_parity_and_absolute


TOY = Path("/tmp/legsa_n4h4r3c_metric_namespace_audit")
LOCAL_PATTERNS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "/mnt/c/Users" + "/86187/Desktop",
    "C:" + "\\Users",
    "/home/kaiwen" + "/legsa_n4h4r3c_metric_namespace",
    "/home/kaiwen" + "/legsa_n4h4r3b_overclose_audit",
    "/home/kaiwen" + "/legsa_n4h4r3a_update_timeline",
    "/home/kaiwen" + "/legsa_n4h4r3_port_clean_parity",
    "/home/kaiwen" + "/legsa_n4h2g_clean_replay",
    "/home/kaiwen" + "/legsa_external_artifacts",
]
ARTIFACT_RE = re.compile(
    r"(input\.gnss|\.imu$|KF_GINS_Navresult\.nav|KF_GINS_STD\.txt|summary\.json|"
    r"error_series\.csv|\.png$|\.pdf$|\.svg$)"
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
    print(f"N4H4R3C metric namespace audit failed: {message}")
    for detail in details or []:
        print(f"- {detail}")
    return 1


def _check_files() -> int:
    required = [
        "src/legsa_gins/evaluation/legsa_v23_port_metric_namespace.py",
        "src/legsa_gins/evaluation/legsa_v23_port_parity_vs_absolute.py",
        "src/legsa_gins/evaluation/legsa_v23_port_absolute_trace_eval.py",
        "src/legsa_gins/evaluation/legsa_v23_port_final_v23_parity_eval.py",
        "src/legsa_gins/evaluation/legsa_v23_port_metric_namespace_decision.py",
        "scripts/experiments/run_legsa_v23_port_metric_namespace_audit.py",
        "docs/experiments/n4h4r3c_metric_namespace.md",
        "docs/experiments/n4h4r3c_parity_vs_absolute_evaluation.md",
        "docs/experiments/n4h4r3c_trace_absolute_evaluation.md",
        "docs/experiments/n4h4r3c_decision.md",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    return _fail("missing required files", missing) if missing else 0


def _check_classifier_and_misuse() -> int:
    parity = classify_metric_namespace({"reference_path": "dual_final_v23/KF_GINS_Navresult.nav"})
    if parity["namespace"] != MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value:
        return _fail("parity namespace classification failed", [json.dumps(parity, sort_keys=True)])
    absolute = classify_metric_namespace({"solver_output_role": "port_nav", "reference_role": "trace/reference trajectory"})
    if absolute["namespace"] != MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value:
        return _fail("absolute namespace classification failed", [json.dumps(absolute, sort_keys=True)])
    comparison = compare_parity_and_absolute(
        {"namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value, "parity_small": True, "aligned_count": 5},
        {"namespace": MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value, "absolute_trace_evaluation_status": "evidence_missing"},
        {"namespace": MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value, "absolute_trace_evaluation_status": "evidence_missing"},
        {
            "namespace": MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value,
            "compared_metric_namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value,
        },
    )
    if not comparison["r3b_external_closeness_misuse_detected"]:
        return _fail("R3B misuse toy was not detected")
    if comparison["corrected_parity_status"] != "parity_to_finalv23_passed_absolute_missing":
        return _fail("absolute missing status mismatch", [comparison["corrected_parity_status"]])
    return 0


def _write_nav_csv(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "time,lat_deg,lon_deg,height_m,roll_deg,pitch_deg,yaw_deg\n"
    body = "".join(
        f"{row['time']:.3f},{row['lat_deg']:.10f},{row['lon_deg']:.10f},{row['height_m']:.4f},"
        f"{row['roll_deg']:.6f},{row['pitch_deg']:.6f},{row['yaw_deg']:.6f}\n"
        for row in rows
    )
    path.write_text(header + body, encoding="utf-8")


def _write_kfgins_nav(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"0 {row['time']:.3f} {row['lat_deg']:.10f} {row['lon_deg']:.10f} {row['height_m']:.4f} "
        f"0 0 0 {row['roll_deg']:.6f} {row['pitch_deg']:.6f} {row['yaw_deg']:.6f}\n"
        for row in rows
    ]
    path.write_text("".join(lines), encoding="utf-8")


def _make_rows(offset_h_m: float = 0.0, yaw_offset: float = 0.0) -> list[dict[str, float]]:
    rows = []
    lat_offset = offset_h_m / 6378137.0 * 180.0 / math.pi
    for index in range(120):
        time = index * 0.01
        rows.append(
            {
                "time": time,
                "lat_deg": 30.0 + lat_offset,
                "lon_deg": 120.0,
                "height_m": 10.0,
                "roll_deg": 1.0,
                "pitch_deg": 1.5,
                "yaw_deg": 5.0 + yaw_offset,
            }
        )
    return rows


def _run_toy() -> int:
    shutil.rmtree(TOY, ignore_errors=True)
    clean = TOY / "clean"
    dual = TOY / "dual"
    r3 = TOY / "r3"
    r3a = TOY / "r3a"
    r3b = TOY / "r3b"
    out = TOY / "out"
    trace = TOY / "trace.csv"
    for path in [clean, dual, r3, r3a, r3b]:
        path.mkdir(parents=True, exist_ok=True)
    trace_rows = _make_rows()
    final_rows = _make_rows(offset_h_m=0.35, yaw_offset=1.8)
    port_rows = _make_rows(offset_h_m=0.36, yaw_offset=1.85)
    _write_nav_csv(trace, trace_rows)
    _write_kfgins_nav(dual / "KF_GINS_Navresult.nav", final_rows)
    _write_nav_csv(r3b / "run" / "EVAL_NAV.csv", port_rows)
    (r3b / "PORT_OVERCLOSE_AUDIT_REPORT.json").write_text(
        json.dumps({"external_closeness_failed": True}, sort_keys=True),
        encoding="utf-8",
    )
    result = _run(
        [
            "python3",
            "scripts/experiments/run_legsa_v23_port_metric_namespace_audit.py",
            "--clean-root",
            str(clean),
            "--dual-root",
            str(dual),
            "--r3-root",
            str(r3),
            "--r3a-root",
            str(r3a),
            "--r3b-root",
            str(r3b),
            "--output-dir",
            str(out),
            "--trace-path",
            str(trace),
            "--allow-run",
        ]
    )
    if result.returncode != 0:
        return _fail("toy metric namespace runner failed", [result.stdout, result.stderr])
    required = [
        "PORT_VS_FINALV23_NAV_PARITY_REPORT.json",
        "FINALV23_VS_TRACE_ABSOLUTE_REPRO_REPORT.json",
        "PORT_VS_TRACE_ABSOLUTE_REPORT.json",
        "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json",
        "PORT_METRIC_NAMESPACE_DECISION_REPORT.json",
        "n4h4r3c_metric_namespace_audit.md",
    ]
    missing = [name for name in required if not (out / name).exists()]
    if missing:
        return _fail("toy report missing", missing)
    for name in required[:5]:
        data = json.loads((out / name).read_text(encoding="utf-8"))
        bad = [flag for flag in FALSE_FLAGS if data.get(flag) is not False]
        if bad:
            return _fail(f"{name} forbidden flags not false", bad)
        if data.get("no_outperform_final_v23_claim") is not True and name != "PORT_METRIC_NAMESPACE_DECISION_REPORT.json":
            return _fail(f"{name} missing no_outperform_final_v23_claim=true")
    comparison = json.loads((out / "PORT_PARITY_VS_ABSOLUTE_COMPARISON_REPORT.json").read_text(encoding="utf-8"))
    if not comparison.get("r3b_external_closeness_misuse_detected"):
        return _fail("toy comparison did not detect R3B misuse")
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
        return _fail("tracked artifact detected", artifact_hits)
    if path_hits:
        return _fail("local path leakage detected", path_hits)
    return 0


def main() -> int:
    for check in [_check_files, _check_classifier_and_misuse, _run_toy, _check_no_artifacts_or_paths]:
        result = check()
        if result:
            return result
    print("N4H4R3C metric namespace audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
