"""H-EXT-04L manuscript amendment over sealed scalar tables; no evaluation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from .aggregate import METRIC_FIELDS, H03_PRIMARY_STARTS, pinned_payload

PINS = {
    "v3": "8c0535273809777ccb873ded828a5e8f4c2ef4d80ac4b244f1c8ce4f71647348",
    "v2": "ae8e49a224c56a3ebf224ab32ef0b8843d6522f00aec2cd41edd25e10e7251fd",
}
REASON = "预注册规则按 BY2 航向选出 S，三序列结果显示 S 对基线并非一致有利（BY2O 航向 4.016 对 2.454，三序列 roll/pitch 均差），改用发表配置"
LC01_DESCRIPTION = "IMU 过程噪声取自原文实验设定，未针对本 IMU 标定"


def amend_rows(rows):
    result = []
    for original in rows:
        row = dict(original)
        internal = row["method_id"] in ("F01", "F02", "F03", "A04", "F04")
        external = (row["method_id"] == "LC01"
                    and row["start_convention"] == H03_PRIMARY_STARTS[row["sequence_id"]])
        row["main_row"] = internal or external
        row["manuscript_row"] = row["main_row"] and row["method_id"] not in ("F01", "F03")
        result.append(row)
    return result


def scoreboards(rows):
    """Per-metric minima are a sensitivity envelope, never a new method row."""
    literature, favorable = [], []
    for sequence, start in H03_PRIMARY_STARTS.items():
        def one(method):
            matches = [r for r in rows if r["sequence_id"] == sequence and r["method_id"] == method
                       and (method == "F04" or r["start_convention"] == start)]
            if len(matches) != 1:
                raise ValueError("Scoreboard identity absent or duplicated")
            return matches[0]
        full, lit, shared = (one(m) for m in ("F04", "LC01", "LC01-S"))
        for metric in METRIC_FIELDS:
            f, l, s = (float(r[metric]) for r in (full, lit, shared))
            for output, value, comparator in (
                    (literature, l, "LC01"),
                    (favorable, min(l, s), "LC01" if l <= s else "LC01-S")):
                output.append(dict(sequence_id=sequence, metric=metric, f04=f,
                    comparator_method=comparator, comparator=value, delta_f04_minus_comparator=f-value,
                    lower="F04" if f < value else comparator if f > value else "TIE",
                    start_convention=start, geometric_audit_status=lit["geometric_audit_status"]))
    return literature, favorable


def write_csv(path, rows):
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(stage_root, *, code_commit, config_hash):
    stage_root = Path(stage_root)
    output = stage_root / "11_READONLY_CLOSEOUT_H_EXT_04L"
    output.mkdir(parents=True, exist_ok=True)
    source_hashes, all_rows = {}, {}
    for version, pin in PINS.items():
        filename = "HORIZONTAL_TABLE_" + version.upper() + "_THREE_SEQUENCES.csv"
        payload = pinned_payload(stage_root / "08_AGGREGATE" / filename, pin)
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        if len(rows) != 52:
            raise ValueError("Frozen table cardinality changed")
        all_rows[version] = amend_rows(rows)
        write_csv(output / ("MAIN_TABLE_" + version.upper() + ".csv"), all_rows[version])
        source_hashes["<HEXT_ROOT>/08_AGGREGATE/" + filename] = pin
    lit, favorable = scoreboards(all_rows["v3"])
    write_csv(output / "SCOREBOARD_LITERATURE_V3.csv", lit)
    write_csv(output / "SCOREBOARD_FAVORABLE_PER_METRIC_V3.csv", favorable)
    write_csv(output / "LC01_BOTH_CONFIGURATIONS_ALL_METRICS.csv",
              [r for rows in all_rows.values() for r in rows if r["method_id"] in ("LC01", "LC01-S")])
    summary = dict(schema_version="hext.readonly.manuscript.v1.2", task="H-EXT-04L",
        status="MANUSCRIPT_ROWS_AMENDED_READ_ONLY", code_commit=code_commit,
        code_commit_role="BASE_COMMIT_WITH_IMPLEMENTATION_SHA256", config_hash=config_hash,
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        data_mode="frozen_real_result_read_only", synthetic_data_used=False, semisynthetic_data_used=False,
        native_invocation_count=0, evaluator_invocation_count=0, trace_open_count=0,
        source_hashes=source_hashes,
        selection=dict(selected_config="LIT", selected_method_id="LC01",
            paper_primary_starts=H03_PRIMARY_STARTS, amended_after_results_seen=True,
            prior_selected_method_id="LC01-S", reason=REASON, lc01_description=LC01_DESCRIPTION,
            supplemental_method_id="LC01-S"),
        favorable_scoreboard_definition="Per sequence/metric min(LC01, LC01-S) at fixed manuscript start; not an executable method",
        files_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.csv")
                      if p.name.startswith(("MAIN_TABLE_", "SCOREBOARD_", "LC01_BOTH_"))})
    with (output / "FINAL_SUMMARY.json").open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return summary
