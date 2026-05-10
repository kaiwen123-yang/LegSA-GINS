"""Discover local RTKLIB executables and source evidence.

中文说明：搜索结果只进入 runtime report；tracked docs/config/scripts 不硬编码本机路径。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .rtklib_command_runner import run_command


EXECUTABLE_NAMES = {
    "convbin": ["convbin", "convbin.exe"],
    "rnx2rtkp": ["rnx2rtkp", "rnx2rtkp.exe"],
    "rtksvr": ["rtksvr", "rtksvr.exe"],
    "str2str": ["str2str", "str2str.exe"],
}
PREFERRED_RELATIVE = [
    "app/convbin/gcc/convbin",
    "app/rnx2rtkp/gcc/rnx2rtkp",
    "app/convbin/Debug/convbin.exe",
    "app/rnx2rtkp/Debug/rnx2rtkp.exe",
    "bin/convbin.exe",
    "bin/rnx2rtkp.exe",
]
SOURCE_FILES = ["pntpos.c", "rtkpos.c", "ephemeris.c", "rinex.c", "rtklib.h"]


def _find_first(root: Path, names: list[str]) -> Path | None:
    for rel in PREFERRED_RELATIVE:
        candidate = root / rel
        if candidate.name.lower() in {name.lower() for name in names} and candidate.exists():
            return candidate
    lower = {name.lower() for name in names}
    for current, _, files in os.walk(root):
        for file_name in files:
            if file_name.lower() in lower:
                return Path(current) / file_name
    return None


def _find_sources(root: Path) -> dict[str, str | None]:
    found: dict[str, str | None] = {name: None for name in SOURCE_FILES}
    remaining = {name.lower(): name for name in SOURCE_FILES}
    for current, _, files in os.walk(root):
        for file_name in files:
            key = file_name.lower()
            if key in remaining and found[remaining[key]] is None:
                found[remaining[key]] = str(Path(current) / file_name)
        if all(found.values()):
            break
    return found


def discover_rtklib(rtklib_root: str | Path) -> dict[str, Any]:
    root = Path(rtklib_root).expanduser()
    report: dict[str, Any] = {
        "rtklib_root_exists": root.exists(),
        "convbin_found": False,
        "convbin_path": "",
        "rnx2rtkp_found": False,
        "rnx2rtkp_path": "",
        "source_tree_found": False,
        "candidate_source_files": {},
        "executable_invocation_mode": "missing",
        "version_output": "",
        "can_run_help": False,
        "rtklib_provider_available": False,
        "blocker_reasons": [],
    }
    if not root.exists():
        report["blocker_reasons"].append("rtklib_root_missing")
        return report
    convbin = _find_first(root, EXECUTABLE_NAMES["convbin"])
    rnx2rtkp = _find_first(root, EXECUTABLE_NAMES["rnx2rtkp"])
    sources = _find_sources(root)
    report["convbin_found"] = convbin is not None
    report["convbin_path"] = str(convbin) if convbin else ""
    report["rnx2rtkp_found"] = rnx2rtkp is not None
    report["rnx2rtkp_path"] = str(rnx2rtkp) if rnx2rtkp else ""
    report["candidate_source_files"] = sources
    report["source_tree_found"] = any(sources.values())
    exe = convbin or rnx2rtkp
    if exe:
        help_result = run_command(exe, ["-h"], timeout=10.0)
        report["executable_invocation_mode"] = help_result.invocation_mode
        report["version_output"] = (help_result.stdout + help_result.stderr)[-2000:]
        report["can_run_help"] = help_result.returncode in (0, 1, 2)
    else:
        report["blocker_reasons"].append("rtklib_executable_missing")
    report["rtklib_provider_available"] = bool(report["can_run_help"] and (convbin or rnx2rtkp))
    if not report["rtklib_provider_available"]:
        report["blocker_reasons"].append("rtklib_provider_not_runnable")
    return report


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtklib-root", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)
    write_report(discover_rtklib(args.rtklib_root), args.output_json)
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
