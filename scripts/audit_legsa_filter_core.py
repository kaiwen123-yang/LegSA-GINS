#!/usr/bin/env python3
"""Audit the Stage N4 LegSA-GINS C++ filter core.

中文说明：
本脚本只检查 N4 filter core 的文件、边界字符串和 toy manifest 合同。
它不运行真实数据，不读取 trace，不读取 final_v23 output，也不做性能评价。
"""

from __future__ import annotations

from pathlib import Path
import sys


REQUIRED_FILES = [
    "cpp/include/legsa_gins/math/constants.hpp",
    "cpp/include/legsa_gins/math/angle.hpp",
    "cpp/include/legsa_gins/math/vec3.hpp",
    "cpp/include/legsa_gins/math/quaternion.hpp",
    "cpp/include/legsa_gins/math/earth.hpp",
    "cpp/include/legsa_gins/math/rotation.hpp",
    "cpp/include/legsa_gins/types/filter_types.hpp",
    "cpp/include/legsa_gins/types/imu_types.hpp",
    "cpp/include/legsa_gins/filter/diag_covariance.hpp",
    "cpp/include/legsa_gins/filter/legsa_filter.hpp",
    "cpp/src/filter/diag_covariance.cpp",
    "cpp/src/filter/legsa_filter.cpp",
    "cpp/include/legsa_gins/mechanization/ins_mechanization.hpp",
    "cpp/src/mechanization/ins_mechanization.cpp",
    "cpp/include/legsa_gins/updates/receiver_position_update.hpp",
    "cpp/src/updates/receiver_position_update.cpp",
    "cpp/include/legsa_gins/updates/receiver_velocity_update.hpp",
    "cpp/src/updates/receiver_velocity_update.cpp",
    "cpp/include/legsa_gins/updates/receiver_heading_update.hpp",
    "cpp/src/updates/receiver_heading_update.cpp",
    "cpp/include/legsa_gins/readers/toy_csv_reader.hpp",
    "cpp/src/readers/toy_csv_reader.cpp",
    "docs/legsa_filter_core_design.md",
    "docs/mechanization_foundation.md",
    "docs/receiver_native_update_contract.md",
]

REQUIRED_TEXT = [
    "kErrorStateSize = 21",
    "P_ID = 0",
    "V_ID = 3",
    "PHI_ID = 6",
    "BG_ID = 9",
    "BA_ID = 12",
    "SG_ID = 15",
    "SA_ID = 18",
    "filter_core_toy_only_no_performance_claim",
    "proposed_reads_final_v23_output",
    "final_v23_output_substitution",
    "trace_solver_input",
    "raw_doppler_claim",
    "go2_prior_claim",
    "source_aware_weighting_claim",
    "fgo_smoother_claim",
    "numerical_performance_claim",
]

FORBIDDEN_IN_N4_CPP = [
    "RawDopplerResidual",
    "raw_doppler_residual",
    "computeRawDoppler",
    "Go2YawRatePriorUpdate",
    "Go2AttitudePriorUpdate",
    "SourceAwareWeightingUpdate",
    "FgoSmoother",
    "FixedLagSmootherImplementation",
    "KF_GINS_Navresult.nav",
    "FINAL_V23_NAV.csv",
]


def collect_text(root: Path, rel_paths: list[str]) -> str:
    return "\n".join((root / rel_path).read_text(encoding="utf-8") for rel_path in rel_paths)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("LegSA filter core audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    text = collect_text(root, REQUIRED_FILES + [
        "cpp/src/io/run_manifest_writer.cpp",
        "cpp/apps/legsa_gins.cpp",
    ])
    missing_text = [item for item in REQUIRED_TEXT if item not in text]
    if missing_text:
        print("LegSA filter core audit failed. Missing required text:")
        for item in missing_text:
            print(f"- {item}")
        return 1

    for flag in [
        "proposed_reads_final_v23_output",
        "final_v23_output_substitution",
        "trace_solver_input",
        "raw_doppler_claim",
        "go2_prior_claim",
        "source_aware_weighting_claim",
        "fgo_smoother_claim",
        "numerical_performance_claim",
    ]:
        # C++ writer 中的 JSON 字段必须静态写成 false，toy dry-run 测试会再验证运行产物。
        # The C++ writer must keep these JSON fields false; runtime tests verify output too.
        if f'\\"{flag}\\": false' not in text:
            print(f"LegSA filter core audit failed. Flag is not statically false: {flag}")
            return 1

    n4_cpp_files = [
        path
        for path in (root / "cpp").rglob("*")
        if path.is_file()
        and path.suffix in {".cpp", ".hpp", ".h"}
        and any(part in {"filter", "mechanization", "updates", "readers", "math"} for part in path.parts)
    ]
    n4_cpp_text = "\n".join(path.read_text(encoding="utf-8") for path in n4_cpp_files)
    forbidden = [item for item in FORBIDDEN_IN_N4_CPP if item in n4_cpp_text]
    if forbidden:
        print("LegSA filter core audit failed. Forbidden implementation markers found:")
        for item in forbidden:
            print(f"- {item}")
        return 1

    print("LegSA filter core audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
