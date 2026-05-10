"""Discover BY2-date ephemeris files for N5A.

中文说明：搜索根目录来自 runtime 参数或环境变量；报告可记录本机路径，但 tracked
文件不得硬编码这些路径。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DATE_PATTERNS = [
    "2026065",
    "2026_065",
    "2026-03-06",
    "0650",
    "brdc065",
    "BRDC00",
    "BRDM",
    "MGEX",
    "IGS",
    "GFZ",
    "COD",
    "WUM",
    "CLK",
    "SP3",
]
EXTENSIONS = (
    ".nav",
    ".rnx",
    ".rnx.gz",
    ".sp3",
    ".sp3.gz",
    ".clk",
    ".clk.gz",
    ".eph",
)


def role_for_path(path: Path) -> str:
    name = path.name.lower()
    if name.endswith((".sp3", ".sp3.gz")):
        return "precise_sp3"
    if name.endswith((".clk", ".clk.gz")):
        return "clock_clk"
    if name.endswith((".nav", ".n", ".g")) or "brdc" in name or "brdm" in name:
        return "broadcast_nav"
    if name.endswith((".obs", ".o", ".rnx")) and "brd" not in name:
        return "rinex_obs"
    return "unknown"


def _candidate(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if any(lower.endswith(ext) for ext in EXTENSIONS):
        return True
    if any(token.lower() in lower for token in ("brdc", "brdm")):
        return True
    if lower.endswith((".b", ".n", ".p", ".g", ".l")):
        return True
    return False


def _score(path: Path, role: str) -> int:
    name = path.name
    lower = name.lower()
    score = 0
    for pattern in DATE_PATTERNS:
        if pattern.lower() in lower:
            score += 5
    if role == "broadcast_nav":
        score += 4
    if role == "precise_sp3":
        score += 3
    if role == "clock_clk":
        score += 2
    if "2026065" in lower or "0650" in lower:
        score += 4
    if "brdc" in lower or "brdm" in lower:
        score += 3
    return score


def discover_ephemeris(search_roots: list[str | Path]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for raw_root in search_roots:
        if not raw_root:
            continue
        root = Path(raw_root).expanduser()
        if not root.exists():
            continue
        for current, _, files in os.walk(root):
            for file_name in files:
                path = Path(current) / file_name
                if not _candidate(path):
                    continue
                role = role_for_path(path)
                score = _score(path, role)
                candidates.append(
                    {
                        "path": str(path),
                        "role": role,
                        "date_score": score,
                        "by2_date_match": score > 0,
                    }
                )
    candidates.sort(key=lambda item: (item["date_score"], item["role"] == "broadcast_nav"), reverse=True)

    def best(role: str) -> str:
        for item in candidates:
            if item["role"] == role and item["by2_date_match"]:
                return item["path"]
        for item in candidates:
            if item["role"] == role:
                return item["path"]
        return ""

    best_nav = best("broadcast_nav")
    best_sp3 = best("precise_sp3")
    best_clk = best("clock_clk")
    available = bool(best_nav or best_sp3)
    return {
        "candidate_count": len(candidates),
        "candidate_files": candidates[:500],
        "best_broadcast_nav_candidate": best_nav,
        "best_sp3_candidate": best_sp3,
        "best_clk_candidate": best_clk,
        "by2_date_match": any(item["by2_date_match"] for item in candidates),
        "ephemeris_available": available,
        "blocker_reasons": [] if available else ["ephemeris_missing"],
    }


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)
    roots = args.search_root or [value for value in (os.environ.get("RTKLIB_ROOT"), os.environ.get("LOCAL_OUTPUT_ROOT")) if value]
    write_report(discover_ephemeris(roots), args.output_json)
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
