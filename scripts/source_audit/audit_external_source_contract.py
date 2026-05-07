#!/usr/bin/env python3
"""Audit the N3B external source audit and reproduction contract.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from pathlib import Path
import sys


REQUIRED_FILES = [
    "docs/source_audit/final_v23_source_map.md",
    "docs/source_audit/kf_gins_runtime_flow.md",
    "docs/source_audit/final_v23_evidence_missing.md",
    "docs/reproduction/final_v23_reproduction_contract.md",
    "configs/baselines/final_v23_reproduction/final_v23_repro.local.example.yaml",
]

REQUIRED_STRINGS = [
    "final_v23_is_proposed: false",
    "proposed_reads_final_v23_output: false",
    "final_v23_output_substitution: false",
    "evidence_missing",
    "Do not modify final_v23 source",
    "Do not commit raw data",
]

FORBIDDEN_VENDOR_DIRS = [
    "external/KF-GINS",
    "third_party/KF-GINS",
    "vendor/KF-GINS",
    "KF-GINS",
]

SOURCE_MAP_REQUIRED_STRINGS = [
    "/home/kaiwen/KF-GINS",
    "kaiwen123-yang/KF-GINS-graduation-design",
]


def _read_all_contract_text(root: Path) -> str:
    chunks: list[str] = []
    for rel_path in REQUIRED_FILES:
        chunks.append((root / rel_path).read_text(encoding="utf-8"))
    return "\n".join(chunks)


def main() -> int:
    root = Path(__file__).resolve().parents[2]

    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("External source contract audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    text = _read_all_contract_text(root)
    missing_strings = [item for item in REQUIRED_STRINGS if item not in text]
    if missing_strings:
        print("External source contract audit failed. Missing required strings:")
        for item in missing_strings:
            print(f"- {item}")
        return 1

    forbidden_present = []
    for rel_path in FORBIDDEN_VENDOR_DIRS:
        path = root / rel_path
        if path.exists():
            forbidden_present.append(rel_path)
    if forbidden_present:
        print("External source contract audit failed. Vendored source directories found:")
        for rel_path in forbidden_present:
            print(f"- {rel_path}")
        return 1

    source_map = (root / "docs/source_audit/final_v23_source_map.md").read_text(
        encoding="utf-8"
    )
    source_map_missing = [
        item for item in SOURCE_MAP_REQUIRED_STRINGS if item not in source_map
    ]
    if source_map_missing:
        print("External source contract audit failed. Source map missing:")
        for item in source_map_missing:
            print(f"- {item}")
        return 1

    print("External source contract audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
