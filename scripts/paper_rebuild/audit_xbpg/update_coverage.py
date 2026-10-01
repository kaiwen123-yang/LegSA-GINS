#!/usr/bin/env python3
"""Merge explicit semantic receipts into the inventory, never recreate it."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=Path, default=Path("docs/paper_rebuild/audit_xbpg_20261001"))
    docs = ap.parse_args().docs
    path = docs / "CODE_REVIEW_COVERAGE.csv"
    rows = read(path)
    by_path = {r["path"]: r for r in rows}
    for name in ("REVIEW_RECEIPTS.csv", "NATIVE_COVERAGE.csv", "RAW_GNSS_COVERAGE.csv", "NATIVE_OTHER_COVERAGE.csv"):
        receipt = docs / name
        if not receipt.exists():
            continue
        for item in read(receipt):
            if item["path"] not in by_path:
                raise ValueError(f"Receipt outside baseline inventory: {item['path']}")
            row = by_path[item["path"]]
            if item.get("git_blob") and item["git_blob"] != row["identity"]:
                raise ValueError(f"Identity mismatch: {item['path']}")
            depth = item.get("depth", "")
            complete = depth in {"已完成语义审查", "已动态测试", "SEMANTIC_REVIEW_COMPLETE", "SEMANTIC_REVIEWED", "DYNAMIC_TESTED"}
            if depth == "PARTIAL_SEMANTIC" and row["depth"].startswith("SEMANTIC_REVIEW_COMPLETE"):
                continue
            row["depth"] = "SEMANTIC_REVIEW_COMPLETE" if complete else depth
            row["semantic_lines"] = row["lines"] if complete else item.get("semantic_lines", "PARTIAL_UNQUANTIFIED")
            for key, targets in {
                "purpose": ("purpose",), "entry_callers": ("entry_or_callers", "entry_callers", "callers"),
                "dependencies": ("dependencies",), "inputs_outputs": ("input_output", "inputs_outputs"),
                "relation": ("formal_relation", "relation"), "review_note": ("explanation", "review_note", "review_reference"),
                "finding_ids": ("findings", "finding_ids"), "dynamic_evidence": ("dynamic_test", "dynamic_evidence"),
            }.items():
                value = next((item[k] for k in targets if item.get(k)), None)
                if value:
                    row[key] = value
            row["review_receipt"] = name
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    counts = Counter(row["depth"] for row in rows)
    complete = [row for row in rows if row["depth"] == "SEMANTIC_REVIEW_COMPLETE"]
    summary = dict(baseline_files=len(rows), baseline_lines=sum(int(r["lines"]) for r in rows),
                   complete_semantic_files=len(complete), complete_semantic_lines=sum(int(r["lines"]) for r in complete),
                   depth_counts=dict(counts), inventory_recreated=False, new_audit_code_separate=True,
                   note="Complete semantic read does not mean all branches dynamically tested; external frozen evaluator excluded from baseline denominator")
    (docs / "COVERAGE_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    remaining = [row for row in rows if row["depth"] != "SEMANTIC_REVIEW_COMPLETE"]
    groups = Counter()
    lines = Counter()
    for row in remaining:
        parts = row["path"].split("/")
        key = "/".join(parts[:4] if row["path"].startswith("src/legsa_gins/paper_rebuild/") else parts[:3])
        groups[key] += 1; lines[key] += int(row["lines"])
    with (docs/"REMAINING_REVIEW_QUEUE.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream,["module","not_complete_files","file_lines","status"],lineterminator="\n")
        writer.writeheader(); writer.writerows(dict(module=k,not_complete_files=groups[k],file_lines=lines[k],status="NOT_SEMANTIC_COMPLETE") for k in sorted(groups))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
