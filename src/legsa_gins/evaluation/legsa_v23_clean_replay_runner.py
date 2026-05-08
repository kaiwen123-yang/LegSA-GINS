"""Runner helpers for N4H4D LegSA-v23 clean replay.

中文说明：runner 只定位 runtime-only clean `.gnss/.imu`，生成临时 config，
调用 LegSA 自有 v23-core；不读取 trace，不读取 final_v23 output 作为 solver input。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REQUIRED_OUTPUTS = ["LegSA_V23_NAV.nav", "LegSA_V23_STD.csv", "EVAL_NAV.csv", "RUN_MANIFEST.json"]
CONFIG_KEYS = [
    "starttime",
    "endtime",
    "imudatalen",
    "imudatarate",
    "initpos",
    "initvel",
    "initatt",
    "initposstd",
    "initvelstd",
    "initattstd",
    "antlever",
]


def default_clean_root() -> Path:
    return Path.home() / "legsa_n4h2g_clean_replay"


def default_dual_root() -> Path:
    return Path.home() / "legsa_external_artifacts" / "dual_final_v23_nominal"


def default_output_root() -> Path:
    return Path.home() / "legsa_n4h4d_clean_parity"


def locate_clean_inputs(clean_root: str | Path) -> dict[str, Any]:
    """中文说明：定位 clean status-yaw `.gnss/.imu`；缺失时明确 clean_input_missing。"""

    root = Path(clean_root)
    gnss_candidates = [root / "CLEAN_STATUS_YAW.gnss", root / "_generation" / "BY2_PROCESS_DATA_COMPAT.gnss"]
    imu_candidates = [root / "CLEAN_STATUS_YAW.imu", root / "_generation" / "BY2_PROCESS_DATA_COMPAT.imu"]
    gnss = next((path for path in gnss_candidates if path.exists()), None)
    imu = next((path for path in imu_candidates if path.exists()), None)
    missing = []
    if gnss is None:
        missing.append("clean_gnss")
    if imu is None:
        missing.append("clean_imu")
    return {
        "clean_input_status": "clean_input_ready" if not missing else "clean_input_missing",
        "clean_root_role": "N4H2G_CLEAN_ROOT",
        "gnss_path": str(gnss) if gnss else None,
        "imu_path": str(imu) if imu else None,
        "missing": missing,
    }


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _parse_minimal_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        cleaned = _strip_comment(line)
        if not cleaned or (":" not in cleaned and "=" not in cleaned):
            continue
        sep = ":" if ":" in cleaned else "="
        key, value = cleaned.split(sep, 1)
        key = key.strip().lower()
        if key in CONFIG_KEYS:
            values[key] = value.strip().strip("\"'")
    return values


def _first_last_time(path: Path) -> tuple[float | None, float | None]:
    first: float | None = None
    last: float | None = None
    if not path.exists():
        return first, last
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                value = float(stripped.split()[0])
            except (ValueError, IndexError):
                continue
            if first is None:
                first = value
            last = value
    return first, last


def build_clean_replay_config(clean_root: str | Path, output_dir: str | Path, config_dir: str | Path | None = None) -> dict[str, Any]:
    """中文说明：生成 key-value config；绝对 runtime path 只写入 output-dir 下的非 tracked 文件。"""

    located = locate_clean_inputs(clean_root)
    if located["clean_input_status"] != "clean_input_ready":
        return {"config_status": "clean_input_missing", **located}

    root = Path(clean_root)
    out = Path(output_dir)
    cfg_dir = Path(config_dir) if config_dir else out / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    source_values = _parse_minimal_config(root / "kf-gins-n4h2g-clean-replay.yaml")
    imu_path = Path(str(located["imu_path"]))
    gnss_path = Path(str(located["gnss_path"]))
    imu_first, imu_last = _first_last_time(imu_path)
    gnss_first, gnss_last = _first_last_time(gnss_path)
    start_time = source_values.get("starttime") or str(max(value for value in [imu_first, gnss_first] if value is not None))
    end_time = source_values.get("endtime") or str(min(value for value in [imu_last, gnss_last] if value is not None))
    values = {
        "imupath": str(imu_path),
        "gnsspath": str(gnss_path),
        "outputpath": str(out),
        "starttime": start_time,
        "endtime": end_time,
        "imudatalen": source_values.get("imudatalen", "7"),
        "imudatarate": source_values.get("imudatarate", "500"),
        "initpos": source_values.get("initpos", "[39.98482973, 116.34312609, 41.80208107]"),
        "initvel": source_values.get("initvel", "[0.0, 0.0, 0.0]"),
        "initatt": source_values.get("initatt", "[0.0, 0.0, 0.688505]"),
        "initposstd": source_values.get("initposstd", "[10.0, 10.0, 10.0]"),
        "initvelstd": source_values.get("initvelstd", "[1.0, 1.0, 1.0]"),
        "initattstd": source_values.get("initattstd", "[2.0, 2.0, 2.0]"),
        "antlever": source_values.get("antlever", "[0.0, 0.0, -0.25]"),
        "clean_input_provenance_label": "clean_status_yaw_no_synthetic_noise",
    }
    config_path = cfg_dir / "legsa_v23_clean_replay.conf"
    lines = [
        "# N4H4D runtime-only config generated by runner; do not commit generated config.",
        *[f"{key}: {value}" for key, value in values.items()],
    ]
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "config_status": "config_written",
        "config_path": str(config_path),
        "config_role": "runtime_only_generated_config",
        "clean_input_status": located["clean_input_status"],
        "clean_root_role": located["clean_root_role"],
        "gnss_rows_approx": None,
        "imu_rows_approx": None,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
    }


def run_legsa_v23_core(exe: str | Path, config_path: str | Path, output_dir: str | Path, allow_run: bool) -> dict[str, Any]:
    """中文说明：执行 C++ demo；未传 allow_run 时只生成 dry report，不隐式跑 solver。"""

    if not allow_run:
        return {"run_status": "not_run_without_allow_run", "returncode": None}
    command = [str(exe), "--config", str(config_path), "--output-dir", str(output_dir)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return {
        "run_status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "command_role": "legsa_v23_core_demo_config_run",
    }


def check_runtime_outputs(output_dir: str | Path) -> dict[str, Any]:
    """中文说明：检查 NAV/STD/EVAL_NAV/RUN_MANIFEST 是否生成；不读取 final_v23 输出。"""

    out = Path(output_dir)
    missing = [name for name in REQUIRED_OUTPUTS if not (out / name).exists()]
    manifest: dict[str, Any] = {}
    manifest_path = out / "RUN_MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "runtime_output_status": "outputs_ready" if not missing else "outputs_missing",
        "missing_outputs": missing,
        "manifest": manifest,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
    }
