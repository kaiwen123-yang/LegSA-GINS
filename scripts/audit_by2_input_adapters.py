#!/usr/bin/env python3
"""Audit N4E BY2 input adapters and source-role manifest.

中文说明：本审计只使用 /tmp toy 数据验证 adapter、manifest 和边界字符串；不读取真实 BY2，不实现 raw Doppler 或 Go2 prior。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/legsa_gins/datasets/__init__.py",
    "src/legsa_gins/datasets/by2/__init__.py",
    "src/legsa_gins/datasets/by2/gnss_status_adapter.py",
    "src/legsa_gins/datasets/by2/gnss_raw_scanner.py",
    "src/legsa_gins/datasets/by2/trace_reference_adapter.py",
    "src/legsa_gins/datasets/by2/go2_body_state_parser.py",
    "src/legsa_gins/datasets/by2/input_manifest.py",
    "scripts/datasets/standardize_by2_inputs.py",
    "cpp/include/legsa_gins/readers/standard_receiver_measurement_reader.hpp",
    "cpp/src/readers/standard_receiver_measurement_reader.cpp",
    "docs/datasets/by2_input_adapter_contract.md",
    "docs/datasets/by2_receiver_native_status_contract.md",
    "docs/datasets/by2_go2_body_state_contract.md",
    "docs/codex_prompts/N4E_by2_input_adapters.md",
]

FORBIDDEN_PATH_SNIPPETS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "C:" + "\\Users\\ykw",
]

REQUIRED_DOC_STRINGS = [
    "trace_evaluation_only",
    "trace_solver_input: false",
    "receiver_imu_as_body_imu: false",
    "raw_doppler_extracted: false",
    "body_state_requires_frame_adapter",
]

EXPECTED_OUTPUTS = [
    "BY2_GNSS1_STATUS_STANDARD.csv",
    "BY2_GNSS2_STATUS_STANDARD.csv",
    "BY2_GNSS1_RAW_MESSAGE_SUMMARY.json",
    "BY2_GNSS2_RAW_MESSAGE_SUMMARY.json",
    "BY2_TRACE_REFERENCE_EVAL_ONLY.csv",
    "BY2_GO2_BODY_STATE_DIAGNOSTIC.csv",
    "BY2_INPUT_MANIFEST.json",
]

FORBIDDEN_FALSE_FLAGS = [
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "receiver_imu_as_body_imu",
    "final_v23_output_substitution",
    "raw_data_committed",
    "raw_doppler_extracted",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
]


def _write_toy_status(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Time,time_gps_wno,time_gps_tow,msg_valid,pos_lat,pos_lon,pos_height,pos_acc_h,pos_acc_v,pos_valid,fix_ok,fix_type,rel_pos_n,rel_pos_e,rel_pos_d,rel_acc_n,rel_acc_e,rel_acc_d,rel_valid,ant_valid",
                "1700000000,2400,100.0,1,30.0,120.0,10.0,0.5,0.8,1,1,3,1.0,1.0,0.0,0.1,0.1,0.2,1,1",
                "1700000001,2400,101.0,1,30.1,120.1,10.1,0.6,0.9,1,1,3,0.0,1.0,0.0,0.1,0.1,0.2,1,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_toy_raw(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Time,name,info,protocol,seq",
                "1700000000,UBX-NAV-PVT,nav pvt sample,UBX,1",
                "1700000001,UBX-NAV-HPPOSECEF,hp posecef sample,UBX,2",
                "1700000002,NMEA-GP-HDT,hdt sample,NMEA,3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_toy_trace(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "time,lat,lon,height,yaw,pitch,roll",
                "1700000000,30.0,120.0,10.0,90.0,1.0,2.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_toy_body(path: Path) -> None:
    path.write_text(
        """
stamp:
  sec: 1700000000
  nanosec: 100000000
error_code: 0
imu_state:
  quaternion:
  - 1.0
  - 0.0
  - 0.0
  - 0.0
  gyroscope:
  - 0.1
  - 0.2
  - 0.3
  accelerometer:
  - 1.0
  - 2.0
  - 3.0
  rpy:
  - 0.01
  - 0.02
  - 0.03
  temperature: 38.0
mode: 1
gait_type: 2
foot_raise_height: 0.05
position:
- 1.0
- 2.0
- 3.0
velocity:
- 0.1
- 0.2
- 0.3
yaw_speed: 0.4
foot_force:
- 10
- 20
- 30
- 40
foot_position_body:
- 0
- 1
- 2
- 3
- 4
- 5
- 6
- 7
- 8
- 9
- 10
- 11
foot_speed_body:
- 0.0
- 0.1
- 0.2
- 0.3
- 0.4
- 0.5
- 0.6
- 0.7
- 0.8
- 0.9
- 1.0
- 1.1
---
""".lstrip(),
        encoding="utf-8",
    )


def _check_required_files() -> list[str]:
    return [rel for rel in REQUIRED_FILES if not (REPO_ROOT / rel).exists()]


def _check_forbidden_paths() -> list[str]:
    violations: list[str] = []
    for dirname in ["docs", "configs"]:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if "configs" in path.parts and "local" in path.parts:
                continue
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(snippet in text for snippet in FORBIDDEN_PATH_SNIPPETS):
                violations.append(str(path.relative_to(REPO_ROOT)))
    return sorted(violations)


def _check_doc_strings() -> list[str]:
    docs_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (REPO_ROOT / "docs").rglob("*.md")
    )
    return [needle for needle in REQUIRED_DOC_STRINGS if needle not in docs_text]


def _make_toy_dataset(root: Path, body_path: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_toy_status(root / "gnss1-status.csv")
    _write_toy_status(root / "gnss2-status.csv")
    _write_toy_raw(root / "gnss1-raw.csv")
    _write_toy_raw(root / "gnss2-raw.csv")
    _write_toy_trace(root / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv")
    (root / "imu-data.csv").write_text("Time,acc_x\n1700000000,0.0\n", encoding="utf-8")
    _write_toy_body(body_path)


def _run_toy_standardizer() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="legsa_n4e_audit_", dir="/tmp") as tmp:
        tmp_path = Path(tmp)
        fix_root = tmp_path / "fix"
        body_path = tmp_path / "by2.txt"
        output_dir = tmp_path / "out"
        _make_toy_dataset(fix_root, body_path)
        subprocess.run(
            [
                sys.executable,
                "scripts/datasets/standardize_by2_inputs.py",
                "--fix-root",
                str(fix_root),
                "--body-imu",
                str(body_path),
                "--output-dir",
                str(output_dir),
                "--max-status-rows",
                "10",
                "--max-raw-rows",
                "10",
                "--max-body-messages",
                "10",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        missing = [name for name in EXPECTED_OUTPUTS if not (output_dir / name).exists()]
        manifest = json.loads((output_dir / "BY2_INPUT_MANIFEST.json").read_text(encoding="utf-8"))
        policy = manifest["solver_input_policy"]
        bad_flags = [flag for flag in FORBIDDEN_FALSE_FLAGS if policy.get(flag) is not False]
        if manifest["frame_policy"].get("body_state_requires_frame_adapter") is not True:
            bad_flags.append("body_state_requires_frame_adapter")
        return missing + bad_flags


def main() -> int:
    failures: list[str] = []
    failures.extend(f"missing_file:{path}" for path in _check_required_files())
    failures.extend(f"forbidden_path:{path}" for path in _check_forbidden_paths())
    failures.extend(f"missing_doc_string:{item}" for item in _check_doc_strings())
    failures.extend(f"toy_standardizer:{item}" for item in _run_toy_standardizer())

    if failures:
        print("BY2 input adapter audit failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("BY2 input adapter audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
