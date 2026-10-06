#!/usr/bin/env python3
"""Append omitted config registries / patch artifacts; preserve every prior row."""
import csv
import subprocess
from pathlib import Path

BASE = "eb3cbed314693358c7c38442b6fbbb7afcf0342e"
ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs/paper_rebuild/audit_xbpg_20261001"


def main():
    destination = DOCS / "CODE_REVIEW_COVERAGE.csv"
    with destination.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        previous = list(reader)
    known = {row["path"] for row in previous}
    additions = []
    entries = subprocess.check_output(["git", "ls-tree", "-rz", BASE], cwd=ROOT).split(b"\0")
    for entry in entries:
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        _mode, kind, blob = metadata.decode().split()
        path = name.decode()
        selected = (path.startswith("configs/") and path.endswith(".csv")) or path.endswith((".diff", ".patch"))
        if kind != "blob" or path in known or not selected:
            continue
        payload = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)
        row = {key: "" for key in fields}
        row.update(path=path, tracking="TRACKED_BASE_SCOPE_ADDENDUM", identity=blob,
                   lines=str(len(payload.splitlines())), depth="UNREAD", semantic_lines="0",
                   relation="CONFIG_REGISTRY_OR_PATCH_NOT_AUTOMATIC_EXECUTION",
                   purpose="PENDING_SEMANTIC_REVIEW", entry_callers="PENDING_CALLGRAPH_REVIEW",
                   dependencies="PENDING_SEMANTIC_REVIEW", inputs_outputs="PENDING_SEMANTIC_REVIEW",
                   automation="IDENTITY_AND_LINE_COUNT_ONLY",
                   review_note="CODE_MAP.md;INVENTORY_SCOPE_ADDENDUM.csv")
        additions.append(row)
    if not additions:
        print("No additions; inventory was not rewritten")
        return
    with destination.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(previous)
        writer.writerows(additions)
    # Read-back verifies no previous row or review flag was altered.
    with destination.open(newline="") as stream:
        assert list(csv.DictReader(stream))[:len(previous)] == previous
    with (DOCS / "INVENTORY_SCOPE_ADDENDUM.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, ["path", "identity", "lines", "reason"], lineterminator="\n")
        writer.writeheader()
        for row in additions:
            writer.writerow({**{key: row[key] for key in ("path", "identity", "lines")},
                             "reason": "CSV configuration registries and project patch texts omitted by initial suffix selection; appended UNREAD"})
    print(f"Preserved {len(previous)} rows; appended {len(additions)} UNREAD files / {sum(int(r['lines']) for r in additions)} lines")


if __name__ == "__main__":
    main()
