#!/usr/bin/env python3
"""Audit that trace remains evaluation-only and never becomes solver input.

中文说明：
本脚本扫描工程代码中的高风险 trace solver-input 字符串。
允许 trace_evaluation_only 说明；禁止把 trace_solver_input 打开为 true。
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


SCAN_DIRS = ["cpp", "baseline", "scripts", "src"]
SKIP_PARTS = {".git", "build", "__pycache__", ".pytest_cache", "results", "paper_package"}
FORBIDDEN_PATTERNS = [
    re.compile(r"trace_solver_input\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r"trace_.*(solver|proposed).*input\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r"(solver|proposed).*input.*trace\s*[:=]\s*true", re.IGNORECASE),
]


def should_skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part in SKIP_PARTS for part in parts)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for dirname in SCAN_DIRS:
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or should_skip(path, root):
                continue
            if path.suffix.lower() not in {".py", ".cpp", ".hpp", ".h", ".md", ".yaml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    violations.append(str(path.relative_to(root)))
                    break

    if violations:
        print("No-trace-solver-input audit failed. Violations:")
        for rel_path in sorted(set(violations)):
            print(f"- {rel_path}")
        return 1
    print("No-trace-solver-input audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
