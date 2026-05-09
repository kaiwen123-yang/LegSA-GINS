"""Runner helpers for N4H4R3 source-backed port clean replay.

中文说明：config 写入 runtime-only output dir；clean input 是 solver input，
dual_final_v23 official reference 只在 evaluation 阶段读取。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "imudatalen": "7",
    "imudatarate": "500",
    "starttime": "66.0",
    "endtime": "340.0",
    "initpos": "[39.98482973, 116.34312609, 41.80208107]",
    "initvel": "[0.0, 0.0, 0.0]",
    "initatt": "[0.0, 0.0, 0.688505]",
    "initgyrbias": "[0.0, 0.0, 0.0]",
    "initaccbias": "[0.0, 0.0, 0.0]",
    "initgyrscale": "[0.0, 0.0, 0.0]",
    "initaccscale": "[0.0, 0.0, 0.0]",
    "initposstd": "[10.0, 10.0, 10.0]",
    "initvelstd": "[1.0, 1.0, 1.0]",
    "initattstd": "[2.0, 2.0, 2.0]",
    "arw": "[0.985, 0.985, 0.985]",
    "vrw": "[0.077, 0.077, 0.077]",
    "gbstd": "[9.38, 9.38, 9.38]",
    "abstd": "[77.8, 77.8, 77.8]",
    "gsstd": "[0.0, 0.0, 0.0]",
    "asstd": "[0.0, 0.0, 0.0]",
    "corrtime": "1.0",
    "antlever": "[0.0, 0.0, -0.25]",
}


def _normalize_line(line: str) -> str:
    line = line.split("#", 1)[0].strip()
    return line


def _read_yaml_like_config(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = _normalize_line(raw)
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            data[key] = value
    return data


def _first_last_time(path: Path | None) -> tuple[float | None, float | None]:
    if not path or not path.exists():
        return None, None
    first: float | None = None
    last: float | None = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            time = float(stripped.replace(",", " ").split()[0])
        except (IndexError, ValueError):
            continue
        if first is None:
            first = time
        last = time
    return first, last


def locate_clean_inputs(clean_root: str | Path) -> dict[str, Any]:
    root = Path(clean_root)
    imu_candidates = [root / "CLEAN_STATUS_YAW.imu", *root.glob("**/CLEAN_STATUS_YAW.imu")]
    gnss_candidates = [root / "CLEAN_STATUS_YAW.gnss", *root.glob("**/CLEAN_STATUS_YAW.gnss")]
    imu = next((path for path in imu_candidates if path.exists()), None)
    gnss = next((path for path in gnss_candidates if path.exists()), None)
    gnss_count = 0
    if gnss:
        gnss_count = sum(
            1
            for line in gnss.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    imu_count = 0
    if imu:
        imu_count = sum(
            1
            for line in imu.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    first_imu, last_imu = _first_last_time(imu)
    first_gnss, last_gnss = _first_last_time(gnss)
    return {
        "clean_root": str(root),
        "imu_path": str(imu) if imu else None,
        "gnss_path": str(gnss) if gnss else None,
        "clean_imu_row_count": imu_count,
        "clean_gnss_row_count": gnss_count,
        "first_imu_time": first_imu,
        "last_imu_time": last_imu,
        "first_gnss_time": first_gnss,
        "last_gnss_time": last_gnss,
        "clean_input_missing": imu is None or gnss is None,
        "clean_input_provenance_label": "clean_status_yaw_no_synthetic_noise",
    }


def write_port_clean_config(clean_inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    config_dir = out / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "legsa_v23_port_clean_replay.conf"
    clean_root = Path(clean_inputs.get("clean_root", ""))
    source_policy = _read_yaml_like_config(clean_root / "kf-gins-n4h2g-clean-replay.yaml")
    values = dict(DEFAULT_CONFIG)
    for key in values:
        if key in source_policy:
            values[key] = source_policy[key]
    if not source_policy:
        first_imu = clean_inputs.get("first_imu_time")
        last_imu = clean_inputs.get("last_imu_time")
        first_gnss = clean_inputs.get("first_gnss_time")
        last_gnss = clean_inputs.get("last_gnss_time")
        if isinstance(first_imu, (int, float)) and isinstance(first_gnss, (int, float)):
            values["starttime"] = str(max(float(first_imu), float(first_gnss)) - 0.01)
        if isinstance(last_imu, (int, float)) and isinstance(last_gnss, (int, float)):
            values["endtime"] = str(min(float(last_imu), float(last_gnss)) + 0.01)
    config_policy_evidence_status = (
        "n4h2g_clean_config_policy_found" if source_policy else "config_policy_evidence_missing_source_backed_default"
    )
    imu_path = clean_inputs.get("imu_path")
    gnss_path = clean_inputs.get("gnss_path")
    lines = [
        "run_label: N4H4R3_clean_replay",
        f"imupath: {imu_path or ''}",
        f"gnsspath: {gnss_path or ''}",
        f"outputpath: {out / 'run'}",
        "clean_input_provenance_label: clean_status_yaw_no_synthetic_noise",
        f"config_policy_evidence_status: {config_policy_evidence_status}",
    ]
    for key in [
        "imudatalen",
        "imudatarate",
        "starttime",
        "endtime",
        "initpos",
        "initvel",
        "initatt",
        "initgyrbias",
        "initaccbias",
        "initgyrscale",
        "initaccscale",
        "initposstd",
        "initvelstd",
        "initattstd",
        "arw",
        "vrw",
        "gbstd",
        "abstd",
        "gsstd",
        "asstd",
        "corrtime",
        "antlever",
    ]:
        lines.append(f"{key}: {values[key]}")
    lines.extend(
        [
            f"initbgstd: {values['gbstd']}",
            f"initbastd: {values['abstd']}",
            f"initsgstd: {values['gsstd']}",
            f"initsastd: {values['asstd']}",
        ]
    )
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "config_path": str(config_path),
        "config_generated": True,
        "config_policy_evidence_status": config_policy_evidence_status,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def run_port_core(
    exe: str | Path,
    config_path: str | Path,
    run_dir: str | Path,
    *,
    allow_run: bool,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    if not allow_run:
        return {"port_core_run_status": "skipped", "returncode": None}
    command = [str(exe), "--config", str(config_path), "--output-dir", str(run_path)]
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    manifest_path = run_path / "RUN_MANIFEST.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "port_core_run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "run_dir": str(run_path),
        "manifest": manifest,
        "outputs": {
            name: str(run_path / name)
            for name in ["LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
            if (run_path / name).exists()
        },
    }


def copy_toy_inputs(clean_root: Path) -> None:
    """Create a tiny deterministic clean input for audit/integration tests."""

    clean_root.mkdir(parents=True, exist_ok=True)
    imu_lines = []
    for i in range(0, 160):
        time = i * 0.01
        imu_lines.append(f"{time:.2f} 0 0 0 0 0 -0.0980665\n")
    (clean_root / "CLEAN_STATUS_YAW.imu").write_text("".join(imu_lines), encoding="utf-8")
    gnss_lines = []
    for time in [0.5, 1.0, 1.5]:
        gnss_lines.append(f"{time:.2f} 30.0 120.0 10.0 0.5 0.5 0.8 0 0 0 0.1 0.1 0.1 5.0 1.0\n")
    (clean_root / "CLEAN_STATUS_YAW.gnss").write_text("".join(gnss_lines), encoding="utf-8")
    shutil.copyfile(clean_root / "CLEAN_STATUS_YAW.gnss", clean_root / "input.gnss")
