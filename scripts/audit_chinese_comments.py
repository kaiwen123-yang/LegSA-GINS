#!/usr/bin/env python3
"""Audit Chinese readability comments across code modules.

中文说明：
本脚本只检查代码模块是否具备中文可读性说明，不修改任何文件。
它用于 N3D 注释审计，不能替代算法验证，也不能通过降低检查来让阶段过线。
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


TARGET_DIRS = ["cpp", "baseline", "src", "scripts", "tests"]
TARGET_SUFFIXES = {".py", ".cpp", ".hpp", ".h"}
SKIP_PARTS = {
    ".git",
    "build",
    "__pycache__",
    ".pytest_cache",
    "results",
    "paper_package",
    "external",
    "third_party",
    "vendor",
}
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def should_skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    if any(part in SKIP_PARTS for part in parts):
        return True
    return "configs" in parts and "local" in parts


def iter_code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirname in TARGET_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in TARGET_SUFFIXES and not should_skip(path, root):
                files.append(path)
    return sorted(files)


def py_has_chinese_comment_or_docstring(text: str) -> bool:
    in_docstring = False
    for line in text.splitlines():
        stripped = line.strip()
        triple_count = stripped.count('"""') + stripped.count("'''")
        if triple_count:
            if CHINESE_RE.search(line):
                return True
            if triple_count % 2 == 1:
                in_docstring = not in_docstring
            continue
        if CHINESE_RE.search(line) and (stripped.startswith("#") or in_docstring):
            return True
    return False


def cpp_has_chinese_comment(text: str) -> bool:
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if "/*" in stripped:
            in_block = True
        comment_line = stripped.startswith("//") or stripped.startswith("*") or in_block
        if comment_line and CHINESE_RE.search(line):
            return True
        if "*/" in stripped:
            in_block = False
    return False


def missing_chinese_comment(files: list[Path]) -> list[Path]:
    missing: list[Path] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix == ".py":
            ok = py_has_chinese_comment_or_docstring(text)
        else:
            ok = cpp_has_chinese_comment(text)
        if not ok:
            missing.append(path)
    return missing


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = iter_code_files(root)
    missing = missing_chinese_comment(files)
    if missing:
        print("Chinese comment audit failed. Missing Chinese comments:")
        for path in missing:
            print(f"- {path.relative_to(root)}")
        return 1
    print(f"Chinese comment audit passed. Checked {len(files)} code files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
