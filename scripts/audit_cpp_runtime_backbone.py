#!/usr/bin/env python3
"""Audit the N3A C++ runtime backbone scaffold and claim boundary."""

from pathlib import Path
import re
import sys


REQUIRED_FILES = [
    "cpp/CMakeLists.txt",
    "cpp/apps/legsa_gins.cpp",
    "cpp/include/legsa_gins/types/nav_types.hpp",
    "cpp/include/legsa_gins/engine/legsa_engine.hpp",
    "cpp/src/engine/legsa_engine.cpp",
    "cpp/include/legsa_gins/io/nav_writer.hpp",
    "cpp/src/io/nav_writer.cpp",
    "cpp/include/legsa_gins/io/std_writer.hpp",
    "cpp/src/io/std_writer.cpp",
    "cpp/include/legsa_gins/io/eval_nav_writer_bridge.hpp",
    "cpp/src/io/eval_nav_writer_bridge.cpp",
    "cpp/include/legsa_gins/io/run_manifest_writer.hpp",
    "cpp/src/io/run_manifest_writer.cpp",
    "cpp/include/legsa_gins/factors/factor_base.hpp",
    "cpp/include/legsa_gins/factors/factor_registry.hpp",
    "cpp/src/factors/factor_registry.cpp",
    "cpp/include/legsa_gins/config/runtime_config.hpp",
    "cpp/src/config/runtime_config.cpp",
    "configs/proposed/legsa_cpp_runtime.yaml",
]

REQUIRED_STRINGS = [
    "cpp_runtime_skeleton_only",
    "proposed_skeleton",
    "LegSA_NAV.nav",
    "LegSA_STD.csv",
    "EVAL_NAV.csv",
    "RUN_MANIFEST.json",
    "ReceiverPosition",
    "ReceiverVelocity",
    "ReceiverHeading",
    "RawDoppler",
    "Go2YawRatePrior",
    "Go2AttitudePrior",
    "SourceAwareWeighting",
    "FixedLagSmoother",
]

FORBIDDEN_CPP_PATTERNS = [
    r"RawDopplerResidual",
    r"raw_doppler_residual",
    r"computeRawDoppler",
    r"compute_raw_doppler",
    r"class\s+\w*Doppler\w*Factor",
    r"class\s+\w*FGO\w*",
    r"class\s+\w*Smoother\w*",
    r"optimizeFixedLag",
    r"factor_graph",
    r"final_v23_output_substitution",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cpp_runtime_text(root: Path) -> str:
    chunks: list[str] = []
    for directory in [root / "cpp", root / "configs/proposed"]:
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix in {".hpp", ".cpp", ".txt", ".yaml"}:
                chunks.append(_read_text(path))
    return "\n".join(chunks)


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    missing_files = [path for path in REQUIRED_FILES if not (root / path).exists()]
    if missing_files:
        print("C++ runtime backbone audit failed. Missing files:")
        for path in missing_files:
            print(f"- {path}")
        return 1

    text = _cpp_runtime_text(root)
    missing_strings = [item for item in REQUIRED_STRINGS if item not in text]
    if missing_strings:
        print("C++ runtime backbone audit failed. Missing required scaffold strings:")
        for item in missing_strings:
            print(f"- {item}")
        return 1

    forbidden_hits = []
    for pattern in FORBIDDEN_CPP_PATTERNS:
        if re.search(pattern, text):
            forbidden_hits.append(pattern)

    if forbidden_hits:
        print("C++ runtime backbone audit failed. Forbidden N3A implementation patterns:")
        for pattern in forbidden_hits:
            print(f"- {pattern}")
        return 1

    print("C++ runtime backbone audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
