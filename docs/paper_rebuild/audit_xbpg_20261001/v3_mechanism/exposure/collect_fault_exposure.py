#!/usr/bin/env python3
"""E01: intersect existing component metadata with registered evaluation windows.

Stdlib only. Reads the 24 explicit core CSVs and, for an unexecuted D39 proposal,
the existing dual_yaw FILE_CHECKS.csv. Does not open any source payload or run a
project module. Writes only FAULT_EXPOSURE_NOTES.csv and FAULT_EXPOSURE.md.
"""
import argparse
import collections
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


FAMILIES = (
    "gnss_outage", "gnss_sampling", "position_value", "position_std_status",
    "dual_yaw", "velocity_raw_doppler", "go2_prior_metadata", "multi_source_mixed",
)
METHODS = ("F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09")
AUDIT = Path("docs/paper_rebuild/audit_xbpg_20261001")


def load_json(value):
    return json.loads(value, parse_float=Decimal, parse_int=Decimal)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise ValueError("interval endpoint is not a JSON number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite endpoint")
    return result


def pair(value):
    if isinstance(value, dict):
        value = [value["start_s"], value["end_s"]]
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("expected endpoint pair or start_s/end_s dictionary")
    start, end = map(number, value)
    if end <= start:
        raise ValueError("empty or reversed source interval")
    return start, end


def classify(start, end, low, high):
    """Source [start,end), evaluator [low,high]; preserve end-point-only case."""
    if end <= low:
        return "OUTSIDE_BEFORE", "", "", "0", "EMPTY"
    if start > high:
        return "OUTSIDE_AFTER", "", "", "0", "EMPTY"
    if start == high:
        return "EVAL_END_POINT_ONLY", str(high), str(high), "0", "SINGLE_INCLUDED_POINT"
    left, right = max(start, low), min(end, high)
    endpoint = "RIGHT_OPEN" if end <= high else "RIGHT_CLOSED_BY_EVALUATION"
    label = "INSIDE_EVALUATION" if start >= low and end <= high else "PARTIAL_OVERLAP"
    return label, str(left), str(right), str(right - left), endpoint


def intervals(raw):
    """Do not infer an interval from anchor/duration/full_sequence labels."""
    details = load_json(raw)
    if not isinstance(details, dict):
        return [("", None, "UNPARSEABLE", "details is not an object")]
    found = []
    for key in ("interval", "intervals"):
        if key not in details:
            continue
        values = details[key] if key == "intervals" else [details[key]]
        if not isinstance(values, list) or not values:
            found.append(("/" + key, None, "UNPARSEABLE", "empty or non-list interval collection"))
            continue
        for index, value in enumerate(values):
            pointer = "/" + key + ("/" + str(index) if key == "intervals" else "")
            try:
                found.append((pointer, pair(value), "PARSED", ""))
            except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
                found.append((pointer, None, "UNPARSEABLE", str(exc)))
    if not found:
        unexpected = [key for key in details if "interval" in key or key in ("start_s", "end_s")]
        if unexpected:
            return [("", None, "UNPARSEABLE", "unrecognized interval keys: " + ";".join(unexpected))]
        return [("", None, "NO_EXPLICIT_INTERVAL", "No numeric local interval in this component; not evidence of no effect")]
    return found


def self_test():
    d = Decimal
    assert intervals('{"intervals":[{"start_s":82.204517,"end_s":84.204517}]}')[0][1] == (d("82.204517"), d("84.204517"))
    assert intervals('{"intervals":[[10,20],[30,40]]}')[1][1] == (d(30), d(40))
    assert intervals('{"interval":[2,1]}')[0][2] == "UNPARSEABLE"
    assert intervals('{"interval":["1",2]}')[0][2] == "UNPARSEABLE"
    assert intervals('{"target_rate_hz":1}')[0][2] == "NO_EXPLICIT_INTERVAL"
    assert classify(d(50), d(66), d(66), d(340))[0] == "OUTSIDE_BEFORE"
    assert classify(d(340), d(341), d(66), d(340))[0] == "EVAL_END_POINT_ONLY"
    assert classify(d(341), d(345), d(66), d(340))[0] == "OUTSIDE_AFTER"
    assert classify(d(65), d(70), d(66), d(340))[:4] == ("PARTIAL_OVERLAP", "66", "70", "4")
    assert classify(d(70), d(350), d(66), d(340))[4] == "RIGHT_CLOSED_BY_EVALUATION"
    assert classify(d(70), d(340), d(66), d(340))[4] == "RIGHT_OPEN"
    print("E01 parser/endpoint self-test: 11 assertions passed")


def collect(repo):
    core = repo / AUDIT / "v3_interpretation/core"
    output = repo / AUDIT / "v3_mechanism"
    policy_path = repo / AUDIT / "v3_interpretation/series_checks/SCHEMA_AND_TOLERANCE.md"
    assert "These use half-open `[start,end)`" in policy_path.read_text(encoding="utf-8")
    def portable(path):
        return "<CODE_ROOT>/" + path.relative_to(repo).as_posix()
    def read_csv(path):
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    cases, components, evidence, input_notes = {}, [], collections.defaultdict(list), []
    for family in FAMILIES:
        for name in ("INJECTION_CASES", "INJECTION_COMPONENTS", "ORIGINAL_RUN_VALUES"):
            path = core / family / (name + ".csv")
            rows = read_csv(path)
            input_notes.append((path, len(rows)))
            for row_number, row in enumerate(rows, 1):
                if name == "INJECTION_CASES":
                    assert row["case_id"] not in cases
                    cases[row["case_id"]] = (row, path, row_number)
                elif name == "INJECTION_COMPONENTS":
                    components.append((row, path, row_number))
                else:
                    evidence[row["case_id"]].append((row, path, row_number))
    assert len(cases) == 540 and len(components) == 657
    assert sum(map(len, evidence.values())) == 540 * 11 * 2
    assert {case.split("_")[0] for case in cases} == {f"D{i:02}" for i in range(1, 61)}
    assert all(len(value) == 22 for value in evidence.values())
    source_component_count = sum(len(load_json(row[0]["components_json"])) for row in cases.values())
    assert source_component_count == len(components)

    rows = []
    for component, component_path, component_row in components:
        case, case_path, case_row = cases[component["case_id"]]
        low, high = pair(load_json(case["evaluation_window"]))
        assert (low, high) == (Decimal(66), Decimal(340))
        index = int(component["source_row_key"].split("/")[-1])
        original_component = load_json(case["components_json"])[index]
        assert original_component["details"] == load_json(component["details"])
        assert str(original_component["affected_epoch_count"]) == component["affected_epoch_count"]
        assert original_component["component"] == component["component"]
        assert original_component["affected_source"] == component["affected_source"]
        eval_rows = evidence[case["case_id"]]
        completed = [entry for entry in eval_rows if entry[0]["evaluation_status"] == "COMPLETED"]
        for entry, _, _ in completed:
            assert Decimal(entry["sequence_window_start_s"]) == low
            assert Decimal(entry["sequence_window_end_s"]) == high
        support_refs = [{"row_key": entry["source_row_key"], "json_pointer": entry["source_json_pointer"],
                         "read_data_row": row_number, "status": entry["evaluation_status"]}
                        for entry, _, row_number in eval_rows]
        base = dict(
            case_id=case["case_id"], degradation_id=case["degradation_id"], family=case["family"],
            seed_index=case["seed_index"], seed_value=case["seed_value"],
            component=component["component"], affected_source=component["affected_source"],
            window_role="RECOVERY_METADATA" if component["component"] == "clean_recovery_interval" else "FAULT_COMPONENT_METADATA",
            component_status=component["status"], recorded_affected_epoch_count=component["affected_epoch_count"],
            affected_count_scope="WHOLE_PROVIDER_COMPONENT_NOT_EVALUATION_INTERSECTION_OR_ACCEPTED_UPDATES",
            data_mode=case["V3_data_mode"], synthetic_data_used="false", semisynthetic_data_used=case["V3_semisynthetic_data_used"],
            experiment_protocol="Protocol V3", bundle_protocol_id=case["bundle_protocol_id"],
            case_declared_duration=case["duration_s"],
            source_path=component["source_path"], source_row_key=component["source_row_key"], source_column="details",
            source_value=component["details"], source_recorded_sha256=case["recorded_sha256"],
            source_newly_verified_sha256="", original_bundle_opened_this_item="false",
            read_source_path=portable(component_path), read_source_row_key=f"data_row_1based:{component_row}", read_source_column="details",
            case_source_path=portable(case_path), case_source_row_key=f"data_row_1based:{case_row}",
            evaluation_window_source_column="evaluation_window", evaluation_window_source_value=case["evaluation_window"],
            evaluation_start_s=str(low), evaluation_end_s=str(high), evaluation_endpoint_policy="CLOSED",
            interval_endpoint_policy="LEFT_CLOSED_RIGHT_OPEN_EXISTING_PROVIDER_INTERPRETATION",
            interval_endpoint_policy_note="Existing interpretation policy; numeric component JSON alone does not encode brackets",
            interval_endpoint_policy_source=portable(policy_path),
            interval_endpoint_policy_source_lines="169-174",
            evaluation_records=len(eval_rows), completed_evaluation_records=len(completed),
            evaluation_status_counts=json.dumps(dict(collections.Counter(entry[0]["evaluation_status"] for entry in eval_rows)), sort_keys=True),
            evaluation_support_read_source=portable(eval_rows[0][1]),
            evaluation_support_original_source=eval_rows[0][0]["source_path"],
            evaluation_support_source_column="sequence_window_start_s;sequence_window_end_s;time_start;time_end;matched_epoch_count;evaluation_status",
            evaluation_support_row_keys=json.dumps(support_refs, separators=(",", ":")),
            observed_completed_time_envelopes=json.dumps(sorted({(entry[0]["time_start"], entry[0]["time_end"]) for entry in completed})),
            matched_epoch_count_values=json.dumps(sorted({entry[0]["matched_epoch_count"] for entry in completed})),
            actual_in_window_input_or_accepted_count="UNKNOWN_NOT_DERIVABLE_FROM_COMPONENT_METADATA",
            validation_calculation="METADATA_INTERVAL_INTERSECTION_ONLY", payload_opened_this_item="false",
        )
        for pointer, bounds, status, note in intervals(component["details"]):
            out = dict(base, interval_pointer=component["source_row_key"] + "/details" + pointer,
                       parse_status=status, parse_note=note)
            if bounds:
                start, end = bounds
                label, left, right, duration, endpoint = classify(start, end, low, high)
                out.update(interval_start_s=str(start), interval_end_s=str(end), interval_duration_s=str(end - start),
                           exposure_class=label, intersection_start_s=left, intersection_end_s=right,
                           intersection_duration_s=duration, intersection_right_endpoint=endpoint,
                           evaluation_intersection_conclusion="EMPTY_INTERSECTION" if label.startswith("OUTSIDE_") else
                           "POINT_ONLY_INTERSECTION_ACTUAL_SAMPLE_UNKNOWN" if label == "EVAL_END_POINT_ONLY" else
                           "NONEMPTY_TIME_INTERSECTION_ACTUAL_ACCEPTANCE_UNKNOWN")
            else:
                out.update(interval_start_s="", interval_end_s="", interval_duration_s="", exposure_class=status,
                           intersection_start_s="", intersection_end_s="", intersection_duration_s="", intersection_right_endpoint="UNKNOWN",
                           evaluation_intersection_conclusion="UNKNOWN_" + status)
            rows.append(out)
    rows.sort(key=lambda row: (row["degradation_id"], row["seed_index"], row["source_row_key"], row["interval_pointer"]))
    known = {(row["case_id"], row["interval_pointer"]): row for row in rows}
    for case_id, start, end in (("D22_seed_00", "348.205852", "352.205852"), ("D22_seed_06", "346.21325", "349.21325")):
        row = known[(case_id, "/components/0/details/intervals/0")]
        assert (row["interval_start_s"], row["interval_end_s"], row["exposure_class"]) == (start, end, "OUTSIDE_AFTER")
    d39 = [row for row in rows if row["case_id"] == "D39_seed_00"]
    assert [(row["interval_start_s"], row["interval_end_s"], row["exposure_class"]) for row in d39] == [
        ("82.204517", "84.204517", "INSIDE_EVALUATION"),
        ("182.204872", "184.204872", "INSIDE_EVALUATION"),
        ("349.204539", "352.204539", "OUTSIDE_AFTER"),
    ]
    assert len({(row["case_id"], row["source_row_key"]) for row in rows}) == 657
    output.mkdir(parents=True, exist_ok=True)
    with (output / "FAULT_EXPOSURE_NOTES.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    # Existing small read receipt only; these 22 gz files are not opened.
    d39_checks_path = repo / AUDIT / "v3_interpretation/series_checks/CORE_dual_yaw/FILE_CHECKS.csv"
    d39_files = [row for row in read_csv(d39_checks_path) if row["case_id"] == "D39_seed_00"]
    assert len(d39_files) == 22
    d39_file_map = {(row["method_id"], row["evaluator_version"]): row for row in d39_files}
    assert set(d39_file_map) == {(method, version) for method in METHODS for version in ("v3", "v2")}
    counts = collections.Counter(row["exposure_class"] for row in rows)
    explicit_cases = {row["case_id"] for row in rows if row["parse_status"] == "PARSED"}
    role_counts = collections.Counter((row["window_role"], row["exposure_class"]) for row in rows)
    outside = [row for row in rows if row["exposure_class"] in ("OUTSIDE_BEFORE", "OUTSIDE_AFTER", "PARTIAL_OVERLAP", "EVAL_END_POINT_ONLY", "UNPARSEABLE")]
    lines = ["# E01：已登记扰动区间与评价窗的交集", "",
        "本项只核对已有小型元数据的时间包络，没有重读 provider、error_series、NAV、STD、参考轨迹或任何 gzip。新输出不覆盖旧报告或源 CSV；未调用 solver、evaluator、provider generator、aggregate/controller，也未计算新性能指标。", "",
        f"实际读到八族 **540 个案例、657 个注入组件**，以及对应 **11,880 个评价终态行**（540×11×2）。展开显式多区间并保留无区间组件后，新表 {len(rows)} 行；这些是组件/区间条目，不是运行、独立实验或接受的更新次数。注册分母仍为 **540 个退化案例 + 1 个 clean = Canonical-541**，每例 11 个唯一方法；没有因窗口落在窗外删除注册案例。", "",
        "完整结果见 [FAULT_EXPOSURE_NOTES.csv](FAULT_EXPOSURE_NOTES.csv)，生成器见 [exposure/collect_fault_exposure.py](exposure/collect_fault_exposure.py)。表中 source_path/source_row_key/source_column/source_value 指向原 bundle 的组件 details；read_source_path/read_source_row_key 指向本轮实际读取的既有 CSV。原 details 字符串与原 hash pin 保留；newly_verified hash 留空，本项没有再次打开原 bundle。每个区间另给 interval_pointer。", "",
        "## 交集口径", "",
        "全部案例已有 evaluation_window 为 `[66.0,340.0]`。成功评价行的 sequence_window_start_s/end_s 逐条与之匹配；失败/未调用槽仍保留，不能伪造实际输出时间。观测首末匹配包络来自已有评价表，源行键及状态逐例保留在新表。", "",
        "沿既有 provider 解释使用注入半开 `[start,end)`、评价闭窗 `[66,340]`；半开规则来源为 [既有窗口定义](../v3_interpretation/series_checks/SCHEMA_AND_TOLERANCE.md) 第 169–174 行。原数值 JSON 自身不编码开闭括号，因此表中把解释政策与来源单列，不伪装成源字段。交集时长只做端点减法，不等于采样历元数或性能统计。精确落在 340 的起点保留为 EVAL_END_POINT_ONLY，不能仅因时长零就说没有端点；本批实际条目没有因此推造样本。", "",
        "| 分类 | 本批行数 | 含义 |", "| --- | ---: | --- |",
    ]
    meanings = {
        "INSIDE_EVALUATION": "显式区间完整位于评价时间包络内",
        "PARTIAL_OVERLAP": "显式区间跨评价边界，仅部分时间相交（含覆盖整个评价窗的情况）",
        "OUTSIDE_BEFORE": "半开区间在评价开始前结束，end=66 也不含该端点",
        "OUTSIDE_AFTER": "显式区间的 start>340，全部晚于评价窗",
        "EVAL_END_POINT_ONLY": "start=340，仅可能共享评价窗末端点，需样本才能判断实际暴露",
        "NO_EXPLICIT_INTERVAL": "组件未登记局部数字区间；不等于无扰动、未执行或未暴露",
        "UNPARSEABLE": "有区间字段但当前不能可靠解析，保留原字符串待核查",
    }
    for key, meaning in meanings.items():
        lines.append(f"| {key} | {counts[key]} | {meaning} |")
    lines += ["", f"显式区间共 {sum(row['parse_status'] == 'PARSED' for row in rows)} 条，属于 {len(explicit_cases)} 个案例；其余 {len(cases)-len(explicit_cases)} 个案例未在组件 details 中登记数字局部区间。窗内 {counts['INSIDE_EVALUATION']} 条中，{role_counts[('FAULT_COMPONENT_METADATA', 'INSIDE_EVALUATION')]} 条是故障组件区间、{role_counts[('RECOVERY_METADATA', 'INSIDE_EVALUATION')]} 条是已有 recovery 元数据；恢复条目不算第二次故障。多个组件可能共用同一时间窗，均保留各自来源，不按相同端点消掉组件身份。", "",
        "无显式区间条目中包含 full_sequence、随机逐点作用、audit-only/no_active_path 元数据和可能继承其他组件掩码的情况。本项不从 anchor/duration 猜出窗口，不把这些情况统称为无法解析，也不补成零交集。clean_recovery_interval 单列为 RECOVERY_METADATA，不能将恢复标记再次算成故障注入。", "",
        "## D22 与 D39 的直接核对", "",
        "| 案例 | 原组件子键 | 原区间 [start,end) s | 分类 | 与评价窗交集 s |", "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["case_id"] in ("D22_seed_00", "D22_seed_06", "D39_seed_00"):
            intersect = "空集" if not row["intersection_start_s"] else f"[{row['intersection_start_s']},{row['intersection_end_s']})"
            lines.append(f"| {row['case_id']} | {row['interval_pointer']} | [{row['interval_start_s']},{row['interval_end_s']}) | {row['exposure_class']} | {intersect} |")
    lines += ["", "D22_seed_00 与 seed_06 的既有成功评价首末匹配时刻均为 66.005054/339.997056 s；两个 burst 均在评价请求末端之后。其组件 affected_epoch_count 是 provider 全范围内记录的受影响条目，不能据正计数声称本评价窗受到位置脉冲。这里只证明已登记时间包络不交叠，不证明完整 NAV 字节身份或任意其他机制正确。", "",
        "D39_seed_00 的前两段各 2 s，在评价窗内；第三段 3 s 在窗外。原 details 还分别保存 frozen_affected_count=2/2/3、source_ids 和 count_to_duration_seconds；组件总 affected_epoch_count=7。保留字段里的计数不是本次 scalar R5 的真实接受数。既有扫描未提取 dict intervals 的缺口属于扫描窗口登记，不能据此判原数据错误或声称窗内两个区间没有发生。", "",
        "## 全部窗外、跨界或解析异常条目", "",
        "| 案例 | 组件/作用源 | role | 区间 s | 分类 | 原子键 |", "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in outside:
        lines.append(f"| {row['case_id']} | {row['component']} / {row['affected_source']} | {row['window_role']} | [{row['interval_start_s']},{row['interval_end_s']}) | {row['exposure_class']} | {row['interval_pointer']} |")
    lines += ["", "包络相交不证明输入恰有观测、观测通过有效性/时间匹配/门控，或求解器实际接受。窗外区间也不能解释为源文件没有被修改。失败槽有登记区间仍不意味着存在可评价输出；本表保留 completed_evaluation_records 和原状态，不替换原运行终态。", "",
        "## D39 可选局部核对清单：PROPOSED_NOT_EXECUTED", "",
        "若需补齐先前局部窗口缺口，可单独补充读取下表 22 个已保留文件，对固定 `[82.204517,84.204517)` 和 `[182.204872,184.204872)` 两窗只核对匹配历元数、首末时刻，以及沿既有定义的 H/yaw 误差摘要；每文件一次目标读取，44 个窗口条目。第三窗完全在评价窗外，只保留空交集，不伪造零 RMSE。本项尚未读任何 gzip，未执行这些统计；这仍不能恢复在线接受计数。", "",
        "清单仅从既有 `../v3_interpretation/series_checks/CORE_dual_yaw/FILE_CHECKS.csv` 的 case_id=D39_seed_00 行取得，逐行 recorded/newly_verified hash、EOF 与主扫描次数仍在该原回执中；下面路径使用 `<V3_ROOT>` 别名。", "",
        "| 方法 | run_id | v3 精确文件 | v2 精确文件 |", "| --- | --- | --- | --- |",
    ]
    for method in METHODS:
        a, b = d39_file_map[(method, "v3")], d39_file_map[(method, "v2")]
        assert a["run_id"] == b["run_id"]
        lines.append(f"| {method} | {a['run_id']} | `{a['source_path']}` | `{b['source_path']}` |")
    lines += ["", "## 本项实际读取的小型来源", "", "| 来源 | 数据行数 |", "| --- | ---: |"]
    for path, count in input_notes:
        relative = "../v3_interpretation/core/" + path.parent.name + "/" + path.name
        lines.append(f"| [{path.parent.name}/{path.name}]({relative}) | {count} |")
    lines += [f"| [D39 候选文件来源](../v3_interpretation/series_checks/CORE_dual_yaw/FILE_CHECKS.csv) | {len(read_csv(d39_checks_path))}（只选 22 行作提案） |", "",
        "复核：两种 interval 结构（pair 和 start_s/end_s 字典）均支持；540 案例/657 组件全覆盖，11,880 评价槽完整保留；源 components_json 与分表 details/计数/组件身份逐组件一致；新旧数据模式分开，V3 正式角色为 semisynthetic。另读上述既有窗口定义核实半开解释。没有读取旧工程或重新库存，脚本生成仅为本项 CSV/说明；脚本本体为新增小工具。运行 `python3 exposure/collect_fault_exposure.py --self-test` 可检查 11 个解析/边界断言，默认调用只读取上述明确小来源并重建本项说明，不调用科学流程。", "",
    ]
    (output / "FAULT_EXPOSURE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "components": len(components), "output_rows": len(rows),
                      "classification": dict(counts), "outside_case_ids": sorted({row["case_id"] for row in outside}),
                      "evaluation_rows_read": sum(map(len, evidence.values())), "payload_opens": 0}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        collect(args.repo_root.resolve())
