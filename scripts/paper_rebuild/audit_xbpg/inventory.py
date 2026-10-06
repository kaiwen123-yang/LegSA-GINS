#!/usr/bin/env python3
"""Enumerate the base tree; enumeration never upgrades semantic review depth."""
from __future__ import annotations

import argparse
import ast
import collections
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

BASE = "eb3cbed314693358c7c38442b6fbbb7afcf0342e"
SUFFIXES = {".py", ".pyi", ".cpp", ".cc", ".c", ".hpp", ".h", ".hh", ".m", ".sh", ".bash", ".ps1", ".bat", ".cmake", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".json", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".ipynb", ".R", ".rs"}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def selected(path):
    p = Path(path)
    # JSON reports are data, whereas configuration/schema JSON is executable input.
    if p.suffix == ".json":
        return path.startswith(("configs/", ".github/")) or "schema" in p.name.lower()
    return p.suffix in SUFFIXES or p.name in {"CMakeLists.txt", "Makefile", "Dockerfile"}


def relation(path):
    if path.startswith("cpp/legsa_v23_port_core/"):
        return "CURRENT_NATIVE_PORT_CORE"
    if path.startswith(("src/legsa_gins/paper_rebuild/", "scripts/paper_rebuild/", "configs/paper_rebuild/", "tests/paper_rebuild/")):
        return "CLEAN_NAMESPACE_CALL_RELATION_TO_REVIEW"
    if path.startswith("reference/"):
        return "EXTERNAL_REFERENCE"
    if path.startswith("cpp/"):
        return "OTHER_NATIVE_TARGET_OR_TEST"
    return "OTHER_OWNED_OR_SHARED_CALL_RELATION_TO_REVIEW"


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", type=Path, required=True)
    args = parser.parse_args()
    paths = yaml.safe_load(args.local.read_text())["paths"]
    root, original = Path(paths["code_root"]), Path(paths["audit_source_worktree"])
    doc = root / "docs/paper_rebuild/audit_xbpg_20261001"
    runtime = Path(paths["audit_root"])
    records, functions, modules = [], [], {}
    tracked = []
    submodules = []
    for item in git(root, "ls-tree", "-rz", BASE).split(b"\0"):
        if not item:
            continue
        meta, name = item.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        path = name.decode()
        if kind == "commit":
            submodules.append({"path": path, "commit": blob, "scope": "EXTERNAL_NOT_LINE_REVIEWED"})
        elif selected(path):
            tracked.append((path, blob, root, "TRACKED_BASE"))
    untracked = git(original, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    for path in sorted(p for p in untracked if p and selected(p)):
        # Identity only; source remains in the original worktree and is never copied.
        tracked.append((path, "sha256:" + hashlib.sha256((original / path).read_bytes()).hexdigest(), original, "UNTRACKED_ORIGINAL_PRESERVED"))
    for path, identity, location, tracking in tracked:
        payload = (location / path).read_text(encoding="utf-8", errors="replace")
        lines = len(payload.splitlines())
        deps, funcs, status = [], [], "NOT_APPLICABLE"
        if path.endswith(".py"):
            try:
                tree = ast.parse(payload, filename=path)
                deps = sorted({node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names})
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        funcs.append(node.name)
                        functions.append({"path": path, "tracking": tracking, "name": node.name, "kind": type(node).__name__, "start": node.lineno, "end": node.end_lineno, "depth": "UNREAD", "note": "AST enumeration only, not semantic review"})
                status = "AST_PARSED_NOT_REVIEWED"
            except SyntaxError as error:
                status = f"SYNTAX_ERROR_LINE_{error.lineno}"
            if path.startswith("src/"):
                modules[path[4:-3].replace("/", ".").removesuffix(".__init__")] = path
        records.append({"path": path, "tracking": tracking, "identity": identity, "lines": lines, "relation": relation(path), "purpose": "PENDING_SEMANTIC_REVIEW", "entry_callers": "PENDING_CALLGRAPH_REVIEW", "dependencies": ";".join(deps), "inputs_outputs": "PENDING_SEMANTIC_REVIEW", "depth": "UNREAD", "automation": status, "review_note": "", "finding_ids": ""})
    callers = collections.defaultdict(set)
    for row in records:
        for dep in row["dependencies"].split(";"):
            if dep in modules:
                callers[modules[dep]].add(row["path"])
    for row in records:
        if row["path"] in callers:
            row["entry_callers"] = "STATIC_IMPORT_ONLY:" + ";".join(sorted(callers[row["path"]]))
    write_csv(doc / "CODE_REVIEW_COVERAGE.csv", records, list(records[0]))
    write_csv(runtime / "FUNCTION_INVENTORY.csv", functions, ["path", "tracking", "name", "kind", "start", "end", "depth", "note"])
    duplicates = collections.defaultdict(list)
    for row in records:
        duplicates[row["identity"]].append(row["path"])
    summary = {"base_commit": BASE, "tracked_files": sum(x["tracking"] == "TRACKED_BASE" for x in records), "untracked_original_code_config_files": sum(x["tracking"] != "TRACKED_BASE" for x in records), "lines": sum(x["lines"] for x in records), "python_functions_classes_enumerated_not_reviewed": len(functions), "by_relation": dict(collections.Counter(x["relation"] for x in records)), "identical_blob_groups": [v for v in duplicates.values() if len(v) > 1], "submodules": submodules, "semantic_review_count_at_inventory": 0}
    (runtime / "INVENTORY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "identical_blob_groups"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
