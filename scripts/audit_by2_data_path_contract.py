#!/usr/bin/env python3
"""Audit the Stage N3C BY2 data path and source-role contract.

中文说明：audit 脚本用于工程边界检查，不能通过删除测试或绕过 audit 让阶段过线。
"""

from __future__ import annotations

from pathlib import Path


REQUIRED_FILES = [
    "docs/datasets/by2_data_path_contract.md",
    "configs/datasets/by2_fixposition_dataset.example.yaml",
    "scripts/datasets/probe_by2_dataset_paths.py",
]

REQUIRED_DOC_STRINGS = [
    "trace_evaluation_only",
    "trace_solver_input: false",
    "receiver_imu_as_body_imu: false",
    "raw_data_committed: false",
]

FORBIDDEN_LOCAL_PATH_STRINGS = [
    "/mnt/c/Users" + "/ykw/Desktop",
    "C:" + "\\Users\\ykw",
]


def tracked_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if "configs" in path.parts and "local" in path.parts:
            continue
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".py", ".txt", ".json"}:
            files.append(path)
    return files


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        print("BY2 data path contract audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    contract_text = "\n".join((root / rel_path).read_text(encoding="utf-8") for rel_path in REQUIRED_FILES)
    missing_strings = [item for item in REQUIRED_DOC_STRINGS if item not in contract_text]
    if missing_strings:
        print("BY2 data path contract audit failed. Missing required strings:")
        for item in missing_strings:
            print(f"- {item}")
        return 1

    leaks: list[str] = []
    for path in tracked_text_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for forbidden in FORBIDDEN_LOCAL_PATH_STRINGS:
            if forbidden in text:
                leaks.append(str(path.relative_to(root)))
    if leaks:
        print("BY2 data path contract audit failed. Local absolute path leaks found:")
        for rel_path in sorted(set(leaks)):
            print(f"- {rel_path}")
        return 1

    print("BY2 data path contract audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
