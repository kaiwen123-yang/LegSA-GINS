#!/usr/bin/env python3
"""E02: one supplemental read of exactly D39_seed_00's 22 retained error files.

Stdlib only. No hash calculation, project imports, original evaluator, reference,
provider or NAV/STD reads. Existing SUPPLEMENTAL_READS.csv prevents a second run.
"""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import json
import math
import os
from pathlib import Path

AUDIT = Path("docs/paper_rebuild/audit_xbpg_20261001")
METHODS = ("F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09")
SCHEMA = ("time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m", "position_3d_err_m",
          "roll_err_deg", "pitch_err_deg", "yaw_err_deg", "horizontal_3sigma_m",
          "roll_3sigma_deg", "pitch_3sigma_deg", "yaw_3sigma_deg")
WINDOWS = (("82.204517", "84.204517"), ("182.204872", "184.204872"), ("349.204539", "352.204539"))


def now():
    return datetime.now(timezone.utc).isoformat()


def selected(t, start, end):
    return 66.0 <= t <= 340.0 and start <= t < end


def percentile(values, q):
    if not values:
        return ""
    values = sorted(values)
    index = (len(values) - 1) * q
    low = math.floor(index)
    high = math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def summarize(rows):
    n = len(rows)
    output = {key: "" for key in (
        "first_matched_time_s", "last_matched_time_s", "selected_support_blocks",
        "first_source_data_row_1based", "last_source_data_row_1based",
        "minimum_positive_interval_s", "median_positive_interval_s", "maximum_positive_interval_s",
        "interval_over_0p01s_count", "interval_over_0p1s_count", "interval_over_1s_count",
        "horizontal_rmse_m", "horizontal_p95_absolute_m", "yaw_rmse_deg", "yaw_p95_absolute_deg",
    )}
    output["matched_epoch_count"] = n
    if n == 0:
        return output
    gaps = [b[1] - a[1] for a, b in zip(rows, rows[1:])]
    assert all(gap > 0 for gap in gaps)
    output.update(first_matched_time_s=rows[0][1], last_matched_time_s=rows[-1][1],
                  first_source_data_row_1based=rows[0][0] + 1,
                  last_source_data_row_1based=rows[-1][0] + 1,
                  selected_support_blocks=1 + sum(b[0] != a[0] + 1 for a, b in zip(rows, rows[1:])),
                  minimum_positive_interval_s=min(gaps) if gaps else "",
                  median_positive_interval_s=percentile(gaps, .5),
                  maximum_positive_interval_s=max(gaps) if gaps else "",
                  interval_over_0p01s_count=sum(gap > .01 for gap in gaps),
                  interval_over_0p1s_count=sum(gap > .1 for gap in gaps),
                  interval_over_1s_count=sum(gap > 1 for gap in gaps))
    for column, name, unit in ((2, "horizontal", "m"), (3, "yaw", "deg")):
        values = [row[column] for row in rows]
        output[f"{name}_rmse_{unit}"] = math.sqrt(math.fsum(value * value for value in values) / n)
        output[f"{name}_p95_absolute_{unit}"] = percentile([abs(value) for value in values], .95)
    return output


def self_test():
    assert selected(82.204517, 82.204517, 84.204517)
    assert not selected(84.204517, 82.204517, 84.204517)
    assert selected(66.0, 65.0, 70.0)
    assert selected(340.0, 339.0, 341.0)
    assert not any(selected(t, 349.204539, 352.204539) for t in (66, 339.99, 340, 349.204539))
    empty = summarize([])
    assert empty["matched_epoch_count"] == 0
    assert empty["horizontal_rmse_m"] == empty["yaw_p95_absolute_deg"] == ""
    sample = summarize([(1, 82.3, 3.0, -4.0), (2, 82.5, 4.0, 3.0)])
    assert sample["horizontal_rmse_m"] == math.sqrt(12.5)
    assert abs(sample["yaw_p95_absolute_deg"] - 3.95) < 1e-14
    assert sample["selected_support_blocks"] == 1
    assert abs(sample["maximum_positive_interval_s"] - .2) < 1e-12
    assert summarize([(1, 1, 0, 0)])["maximum_positive_interval_s"] == ""
    print("E02 fixed-window/empty/endpoint/statistic tests: 12 assertions passed")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())


def run(repo):
    output = repo / AUDIT / "v3_mechanism/exposure"
    source_dir = repo / AUDIT / "v3_interpretation/series_checks/CORE_dual_yaw"
    checks_path = source_dir / "FILE_CHECKS.csv"
    previous_receipt = source_dir / "RECEIPT.json"
    previous_receipt_bytes = previous_receipt.read_bytes()
    previous_checks_bytes = checks_path.read_bytes()
    alias_config = json.loads((repo / "configs/paper_rebuild/V3_RESULTS_ROOTS.local.json").read_text())["aliases"]
    cases = [row for row in read_csv(checks_path) if row["case_id"] == "D39_seed_00"]
    assert len(cases) == 22
    assert {(row["method_id"], row["evaluator_version"]) for row in cases} == {(m, v) for m in METHODS for v in ("v3", "v2")}
    assert len({row["source_path"] for row in cases}) == 22
    assert all(row["payload_kind"] == "error_series" and row["main_scan_count"] == "1" for row in cases)
    exposures = [row for row in read_csv(repo / AUDIT / "v3_mechanism/FAULT_EXPOSURE_NOTES.csv") if row["case_id"] == "D39_seed_00"]
    assert [(row["interval_start_s"], row["interval_end_s"]) for row in exposures] == list(WINDOWS)
    originals_path = repo / AUDIT / "v3_interpretation/core/dual_yaw/ORIGINAL_RUN_VALUES.csv"
    originals = {row["source_row_key"]: row for row in read_csv(originals_path) if row["case_id"] == "D39_seed_00"}
    assert len(originals) == 22
    reads_path = output / "SUPPLEMENTAL_READS.csv"
    # Exclusive guard: no automatic rerun or retry, even after an interrupted read.
    with reads_path.open("x", encoding="utf-8") as guard:
        guard.write("status\nSTARTED_NO_FILE_OPEN_YET\n")
        guard.flush()
        os.fsync(guard.fileno())
    started = now()
    read_rows, validation_rows = [], []
    for file in sorted(cases, key=lambda row: (METHODS.index(row["method_id"]), row["evaluator_version"])):
        source_alias = file["source_path"]
        assert source_alias.startswith("<V3_ROOT>/04_EVALUATION/V3R_CONTINUATION/")
        path = Path(alias_config["<V3_ROOT>"]) / source_alias[len("<V3_ROOT>/"):]
        assert path.name == "error_series.csv.gz"
        record = dict(file_id=file["file_id"], case_id="D39_seed_00", run_id=file["run_id"],
                      method_id=file["method_id"], evaluator_version=file["evaluator_version"], source_path=source_alias,
                      supplemental_read="true", supplemental_read_count=0, previous_main_scan_count=file["main_scan_count"],
                      status="STARTED", started_at_utc=now(), completed_at_utc="", read_depth="INDEXED_ONLY",
                      eof_crc_checked="false", rows_read=0, schema_columns_json="", first_time_s="", last_time_s="",
                      nonfinite_cells=0, duplicate_timestamps=0, backward_timestamps=0,
                      prior_recorded_uncompressed_sha256=file["recorded_uncompressed_sha256"],
                      prior_verified_uncompressed_sha256=file["newly_verified_uncompressed_sha256"],
                      newly_verified_uncompressed_sha256="", hash_status="NOT_REHASHED_PRIOR_HASH_RECORD_RETAINED",
                      expected_compressed_size=file["compressed_size_bytes"], compressed_size_before="", compressed_size_after="",
                      source_mtime_ns_before="", source_mtime_ns_after="",
                      source_metadata_unchanged="unknown", count_and_time_vs_previous="unknown", error="")
        read_rows.append(record)
        write_csv(reads_path, read_rows)
        buckets = [[] for _ in WINDOWS]
        try:
            before = path.stat()
            record["compressed_size_before"] = before.st_size
            record["source_mtime_ns_before"] = before.st_mtime_ns
            assert before.st_size == int(file["compressed_size_bytes"]), "compressed size differs from previous receipt"
            record["supplemental_read_count"] = 1
            write_csv(reads_path, read_rows)
            previous_time = None
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader)
                record["schema_columns_json"] = json.dumps(header, separators=(",", ":"))
                assert tuple(header) == SCHEMA, "unexpected error-series schema"
                record["read_depth"] = "HEADER_READ"
                for index, tokens in enumerate(reader):
                    assert len(tokens) == 13, "wrong field count"
                    values = list(map(float, tokens))
                    record["rows_read"] += 1
                    record["nonfinite_cells"] += sum(not math.isfinite(value) for value in values)
                    t = values[0]
                    if index == 0:
                        record["first_time_s"] = t
                    if previous_time is not None:
                        record["duplicate_timestamps"] += t == previous_time
                        record["backward_timestamps"] += t < previous_time
                    previous_time = t
                    record["last_time_s"] = t
                    for bucket, (start, end) in zip(buckets, WINDOWS):
                        if selected(t, float(start), float(end)):
                            bucket.append((index, t, values[4], values[8]))
            record["eof_crc_checked"] = "true"
            record["read_depth"] = "FULL_PAYLOAD_READ"
            after = path.stat()
            record["compressed_size_after"] = after.st_size
            record["source_mtime_ns_after"] = after.st_mtime_ns
            record["source_metadata_unchanged"] = str((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)).lower()
            assert record["source_metadata_unchanged"] == "true"
            assert not (record["nonfinite_cells"] or record["duplicate_timestamps"] or record["backward_timestamps"]), "invalid values or chronology; no epoch deletion"
            assert record["rows_read"] == int(file["row_count"])
            assert abs(record["first_time_s"] - float(file["time_start"])) <= 1e-9
            assert abs(record["last_time_s"] - float(file["time_end"])) <= 1e-9
            record["count_and_time_vs_previous"] = "MATCH"
            record["status"] = "COMPLETED_SUPPLEMENTAL_READ"
        except Exception as exc:
            record["status"] = "UNAVAILABLE_NO_AUTOMATIC_RETRY"
            record["error"] = type(exc).__name__ + ": " + str(exc).replace(str(path), source_alias)
        record["completed_at_utc"] = now()
        original = originals[file["run_id"] + "|" + file["evaluator_version"]]
        for index, ((start, end), bucket, exposure) in enumerate(zip(WINDOWS, buckets, exposures), 1):
            empty = exposure["evaluation_intersection_conclusion"] == "EMPTY_INTERSECTION"
            good = record["status"] == "COMPLETED_SUPPLEMENTAL_READ"
            summary = summarize(bucket) if good else summarize([])
            if not good:
                summary["matched_epoch_count"] = ""
            row = dict(file_id=file["file_id"], run_id=file["run_id"], method_id=file["method_id"],
                       effective_profile=file["effective_profile"], evaluator_version=file["evaluator_version"],
                       case_id="D39_seed_00", data_mode="semisynthetic", synthetic_data_used="false", semisynthetic_data_used="true",
                       validation_calculation="true", supplemental_read="true", source_path=source_alias,
                       source_columns="time;horizontal_err_m;yaw_err_deg", time_domain="original retained matched evaluation time in seconds; no time transformation",
                       schema_columns_json=json.dumps(SCHEMA, separators=(",", ":")),
                       window_id=f"D39_registered_fault_{index:02}", start_s=start, end_s=end, endpoint_policy="LEFT_CLOSED_RIGHT_OPEN",
                       full_support_start_s="66.0", full_support_end_s="340.0", full_support_endpoint_policy="CLOSED",
                       window_source_path=exposure["source_path"], window_source_pointer=exposure["interval_pointer"],
                       intersection_status="EMPTY_INTERSECTION" if empty else "NONEMPTY_INTERVAL_INTERSECTION",
                       status="EMPTY_INTERSECTION" if good and empty else "AVAILABLE" if good and bucket else "NO_MATCHED_SAMPLES" if good else "UNAVAILABLE_SOURCE_READ",
                       original_local_metric_target="NOT_PREVIOUSLY_REPORTED;NEW_FIXED_WINDOW_VALIDATION",
                       original_full_source_path=original["source_path"], original_full_source_row_key=original["source_row_key"],
                       original_full_source_json_pointer=original["source_json_pointer"],
                       original_full_horizontal_rmse_m=original["horizontal_rmse_m"], original_full_yaw_rmse_deg=original["yaw_rmse_deg"],
                       original_full_matched_epoch_count=original["matched_epoch_count"],
                       original_full_time_start=original["time_start"], original_full_time_end=original["time_end"],
                       actual_solver_accepted_count="UNKNOWN_NOT_IN_ERROR_SERIES", gap_interpolation="none", integrals="not calculated",
                       first_epoch_gap_from_intersection_start_s=(summary["first_matched_time_s"] - max(66.0, float(start))) if good and bucket else "",
                       last_epoch_gap_to_intersection_end_s=(min(340.0, float(end)) - summary["last_matched_time_s"]) if good and bucket else "",
                       **summary)
            validation_rows.append(row)
        write_csv(reads_path, read_rows)
        write_csv(output / "D39_WINDOW_VALIDATION.csv", validation_rows)
        print(file["file_id"], record["status"], [len(bucket) for bucket in buckets], flush=True)
    assert previous_receipt.read_bytes() == previous_receipt_bytes
    assert checks_path.read_bytes() == previous_checks_bytes
    failures = [row for row in read_rows if row["status"] != "COMPLETED_SUPPLEMENTAL_READ"]
    receipt = dict(stage="E02_D39_SEED00_SUPPLEMENTAL_WINDOWS", status="COMPLETE" if not failures else "PARTIAL_UNAVAILABLE_NO_RETRY",
                   started_at_utc=started, completed_at_utc=now(), selected_files=22, supplemental_read="true",
                   supplemental_payload_open_attempts=sum(row["supplemental_read_count"] for row in read_rows),
                   completed_files=22-len(failures), unavailable_files=len(failures), rows_read=sum(row["rows_read"] for row in read_rows),
                   window_rows=len(validation_rows), available_window_rows=sum(row["status"] == "AVAILABLE" for row in validation_rows),
                   empty_intersection_rows=sum(row["status"] == "EMPTY_INTERSECTION" for row in validation_rows),
                   full_source_hashes_recomputed=0, old_main_scan_receipt_unchanged=True, old_file_checks_unchanged=True,
                   original_main_scan_count_unchanged=1, new_read_kind="supplemental, one attempt per selected file; not another corpus scan",
                   fixed_windows=[list(window) for window in WINDOWS], full_support=[66,340],
                   data_mode="validation_of_existing_semisynthetic_results", synthetic_data_used=False, semisynthetic_data_used=True,
                   semisynthetic_data_generated=False, validation_calculation=True, solver_calls=0, provider_generator_calls=0,
                   original_evaluator_calls=0, controller_calls=0, bootstrap_calls=0, raw_reference_payload_opens=0,
                   nav_std_payload_opens=0, d22_payload_opens=0, other_error_series_payload_opens=0, source_writes=0)
    (output / "D39_WINDOW_VALIDATION_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    lines = ["# E02：D39 seed_00 三区间的补充读取验证", "",
        f"明确选中 11 方法×v3/v2 的 22 个既有 error_series；本项完成 {receipt['completed_files']} 个文件、{receipt['rows_read']:,} 数据行。每选中文件 supplemental_read_count=1，是旧主扫描之后的补充读取；旧 FILE_CHECKS/RECEIPT 字节未改，原 main_scan_count=1 保留。不读取 D22 或其余 error_series，不重算源 hash；recorded/prior verified hash 与本项 newly verified 空值分列。", "",
        "[D39_WINDOW_VALIDATION.csv](D39_WINDOW_VALIDATION.csv) 为 66 行（22×3）；[SUPPLEMENTAL_READS.csv](SUPPLEMENTAL_READS.csv) 为逐文件读取回执；[机器回执](D39_WINDOW_VALIDATION_RECEIPT.json)给出完成/空窗及零执行计数。来源原字段、时间域、窗口 JSON pointer 和原全窗值同行保留。", "",
        "固定窗为 `[82.204517,84.204517)`、`[182.204872,184.204872)`、`[349.204539,352.204539)`，与原闭评价窗 `[66,340]` 求交。第三窗为 EMPTY_INTERSECTION：matched_epoch_count=0，其 RMSE/P95/首末时刻/gap 为空，表示 NA 而非误差为零。首两窗按真实保留匹配历元统计，不能由窗口时长推定样本数。", "",
        "沿 [既有 schema](../../v3_interpretation/series_checks/SCHEMA_AND_TOLERANCE.md)：原 13 列按 binary64 读取，H 使用 horizontal_err_m，yaw 使用已有 signed yaw_err_deg；RMSE=sqrt(fsum(x²)/n)，绝对 P95 为排序后 (n−1)×0.95 处线性插值。gap 为原顺序相邻选中时刻差，不插值、不删异常历元、不计算积分；无样本/无相邻对时相应指标留 NA。所有导出列同时检查非有限数及时间单调性，异常文件不作有限值筛选，单列不可用且不自动重读。", "",
        "这里补齐的是此前 dict intervals 未入窗口表的局部 validation calculation，不是恢复原报告已经发表的局部数字，也不是重跑 solver/evaluator。原全窗 RMSE 与本项局部 RMSE 的支持不同，表中分别命名，不按二者大小判断优劣。误差样本数量及包络不等于 GNSS/RD/HV/RP 更新尝试或接受次数；真实接受计数仍 UNKNOWN。", "",
        "first_source_data_row_1based/last_source_data_row_1based 是源 CSV 去掉表头后的 1-based 数据行；首末边界 gap 分别为首样本减交集左端、交集右端减末样本，与相邻历元 gap 分开。它们只描述保留评价样本支持，不补齐窗口边界，也不替代传感器采样或因子接受计数。", "",
        "本项仅通过原 gzip EOF/CRC、文件大小/mtime 在读取前后不变及与旧回执的行数/首末时刻一致性检查；没有做新的完整字节哈希，因此不能把沿用的 hash 写成重新验证。", "",
        "## v3：全部 11 方法的两段局部值", "",
        "| 方法 | 窗1 n | 窗1 H RMSE (m) | 窗1 yaw RMSE (deg) | 窗2 n | 窗2 H RMSE (m) | 窗2 yaw RMSE (deg) |",
        "| --- | ---: | --- | --- | ---: | --- | --- |"]
    for method in METHODS:
        a,b = [row for row in validation_rows if row["method_id"]==method and row["evaluator_version"]=="v3"][:2]
        lines.append("| "+" | ".join(map(str,[method,a['matched_epoch_count'],a['horizontal_rmse_m'],a['yaw_rmse_deg'],b['matched_epoch_count'],b['horizontal_rmse_m'],b['yaw_rmse_deg']]))+" |")
    lines += ["", "v2、全部 P95、首末时刻和 gap 全量在 CSV；没有只保留上表的有利片段。脚本 [check_d39_windows.py](check_d39_windows.py) 的 --self-test 覆盖固定端点、空交集及统计定义。正式调用若 SUPPLEMENTAL_READS.csv 已存在即拒绝执行，以防误作第二次补读。", ""]
    (output / "D39_WINDOW_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[5])
    args = parser.parse_args()
    self_test() if args.self_test else run(args.repo_root.resolve())
