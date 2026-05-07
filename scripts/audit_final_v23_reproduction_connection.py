#!/usr/bin/env python3
"""Audit the Stage N3C final_v23 reproduction connection.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


REQUIRED_FILES = [
    "baseline/final_v23_reproduction/README.md",
    "baseline/final_v23_reproduction/scripts/probe_external_source.py",
    "baseline/final_v23_reproduction/scripts/build_external_final_v23.py",
    "baseline/final_v23_reproduction/scripts/run_external_final_v23.py",
    "baseline/final_v23_reproduction/scripts/parse_kfgins_nav.py",
    "baseline/final_v23_reproduction/scripts/parse_kfgins_std.py",
    "baseline/final_v23_reproduction/scripts/parse_kfgins_imu_err.py",
    "baseline/final_v23_reproduction/scripts/standardize_final_v23_outputs.py",
    "baseline/final_v23_reproduction/scripts/write_reproduction_manifest.py",
    "baseline/final_v23_reproduction/configs/final_v23_repro.local.example.yaml",
    "baseline/final_v23_reproduction/docs/kf_gins_output_mapping.md",
    "baseline/final_v23_reproduction/docs/reproduction_runner_contract.md",
    "baseline/final_v23_reproduction/manifests/final_v23_reproduction_manifest.schema.yaml",
]

REQUIRED_STRINGS = [
    "final_v23_is_proposed: false",
    "proposed_reads_final_v23_output: false",
    "final_v23_output_substitution: false",
    "output_only_correction: false",
    "numerical_claim_without_oracle_pass: false",
]

FORBIDDEN_VENDOR_DIRS = [
    "external/KF-GINS",
    "third_party/KF-GINS",
    "vendor/KF-GINS",
    "KF-GINS",
]

FORBIDDEN_FALSE_FLAGS = [
    "final_v23_is_proposed",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "trace_used_for_tuning",
    "output_only_correction",
    "bad_epoch_deletion_for_metric",
    "raw_data_committed",
    "numerical_claim_without_oracle_pass",
]


def write_toy_inputs(tmpdir: Path) -> tuple[Path, Path, Path]:
    nav = tmpdir / "KF_GINS_Navresult.nav"
    std = tmpdir / "KF_GINS_STD.txt"
    imu_err = tmpdir / "KF_GINS_IMU_ERR.txt"
    nav.write_text(
        "\n".join(
            [
                "0 100.0 36.0 120.0 10.0 1.0 2.0 -0.1 0.5 -0.3 45.0",
                "0 101.0 36.00001 120.00001 10.2 1.1 2.1 -0.1 0.6 -0.2 45.5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    std.write_text(
        "\n".join(
            [
                "100.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
                "101.0 1 1 2 0.1 0.1 0.2 0.5 0.5 1.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    imu_err.write_text(
        "\n".join(
            [
                "100.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
                "101.0 0.01 0.01 0.01 1 1 1 0.1 0.1 0.1 0.1 0.1 0.1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return nav, std, imu_err


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("N3C final_v23 audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    contract_text = "\n".join(
        (root / rel_path).read_text(encoding="utf-8")
        for rel_path in REQUIRED_FILES
        if rel_path.endswith((".md", ".yaml"))
    )
    missing_strings = [item for item in REQUIRED_STRINGS if item not in contract_text]
    if missing_strings:
        print("N3C final_v23 audit failed. Missing boundary strings:")
        for item in missing_strings:
            print(f"- {item}")
        return 1

    forbidden_present = [rel_path for rel_path in FORBIDDEN_VENDOR_DIRS if (root / rel_path).exists()]
    if forbidden_present:
        print("N3C final_v23 audit failed. Vendored source directories found:")
        for rel_path in forbidden_present:
            print(f"- {rel_path}")
        return 1

    with tempfile.TemporaryDirectory(prefix="legsa_n3c_audit_") as tmp:
        tmpdir = Path(tmp)
        nav, std, imu_err = write_toy_inputs(tmpdir)
        out_dir = tmpdir / "out"
        script = root / "baseline/final_v23_reproduction/scripts/standardize_final_v23_outputs.py"
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--nav",
                str(nav),
                "--std",
                str(std),
                "--imu-err",
                str(imu_err),
                "--output-dir",
                str(out_dir),
                "--dataset-name",
                "toy_dataset",
                "--source-root",
                "/tmp/external_kfgins",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        required_outputs = [
            out_dir / "FINAL_V23_EVAL_NAV.csv",
            out_dir / "RUN_MANIFEST.json",
        ]
        missing_outputs = [str(path) for path in required_outputs if not path.exists()]
        if missing_outputs:
            print("N3C final_v23 audit failed. Missing toy outputs:")
            for path in missing_outputs:
                print(f"- {path}")
            return 1
        manifest = json.loads((out_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        if manifest.get("algorithm_role") != "baseline":
            print("N3C final_v23 audit failed. algorithm_role is not baseline.")
            return 1
        bad_flags = [flag for flag in FORBIDDEN_FALSE_FLAGS if manifest.get(flag) is not False]
        if bad_flags:
            print("N3C final_v23 audit failed. Forbidden flags not false:")
            for flag in bad_flags:
                print(f"- {flag}")
            return 1

    print("N3C final_v23 reproduction connection audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
