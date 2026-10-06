#!/usr/bin/env python3
"""Read completed saved frontend/tracking/serial artifacts only; no solver imports.

All cases, including failures, are retained in the output CSV. SCRATCH is a
caller-supplied artifact root. The script never opens raw data, epoch models,
reference trajectories, navigation results, or a sphere/ILS library.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value, *, positive=False):
    require(isinstance(value, (float, int)) and not isinstance(value, bool), "non-numeric time")
    value = float(value)
    require(math.isfinite(value) and (value > 0 if positive else value >= 0), "invalid time")
    return value


def stats(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    def q(p):
        x = (len(values) - 1) * p
        i = math.floor(x)
        return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (x - i)
    out = {"count": len(values), "min_s": values[0], "median_s": q(.5),
           "p90_s": q(.9), "p95_s": q(.95), "p99_s": q(.99), "max_s": values[-1],
           "mean_s": sum(values) / len(values), "sum_s": sum(values)}
    for threshold in (.2, 1, 2):
        count = sum(v > threshold for v in values)
        out[f"gt_{threshold:g}s_count"] = count
        out[f"gt_{threshold:g}s_fraction"] = count / len(values)
    return out


def service_cost(case):
    cert = case.get("search", {}).get("certificate")
    valid = case.get("measurement", {}).get("valid", False)
    if cert is not None:
        require(case.get("search_called") is True, "certificate without attempt")
        require(not valid or cert.get("global_optimum_certified") is True, "valid without global certificate")
        return finite(cert.get("elapsed_s")), "CERTIFICATE_ELAPSED"
    require(not valid, "valid output without certificate")
    if case.get("search_called") is True:
        return finite(case.get("search_attempt_elapsed_s"), positive=True), "FAILED_SEARCH_ATTEMPT_TIMER"
    require(case.get("search_called") is False and case.get("presearch_unavailable") is True,
            "unrecorded no-search service cost")
    return 0., "NO_CILS_PRESELECTION_UNAVAILABLE"


def stream(path, expected_valid):
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    times = [float(r["measurement_time"]) for r in rows]
    require(all(math.isfinite(t) for t in times), "nonfinite stream time")
    require(all(a < b for a, b in zip(times, times[1:])), "duplicate/unordered stream")
    require(all(float(r["decision_available_time"]) == t for r, t in zip(rows, times)), "backdated output")
    require(all(r["valid"] in ("0", "1") for r in rows), "nonbinary valid")
    valid_times = [t for r, t in zip(rows, times) if r["valid"] == "1"]
    require(len(valid_times) == expected_valid, "stream/summary valid count mismatch")
    return {"rows": len(rows), "valid": len(valid_times), "invalid": len(rows) - len(valid_times),
            "valid_fraction": len(valid_times) / len(rows) if rows else None,
            "first_time_s": times[0] if times else None, "last_time_s": times[-1] if times else None,
            "first_valid_s": valid_times[0] if valid_times else None,
            "last_valid_s": valid_times[-1] if valid_times else None,
            "sha256": sha(path)}, valid_times


def read_arm(root, prefix):
    complete_path = root / (prefix + "_COMPLETE.json")
    complete = load(complete_path)
    require(complete.get("status") == "COMPLETE", prefix + " incomplete")
    require(len(complete.get("phases", [])) == 3 and
            all(x.get("returncode") == 0 for x in complete["phases"]), "not all phases completed")
    front = root / (prefix + "_FRONTEND")
    tracking = root / (prefix + "_TRACKING")
    serial = root / (prefix + "_SERIAL")
    fp, tp, sp = front / "SUMMARY_0001.json", tracking / "SUMMARY.json", serial / "SUMMARY.json"
    fs, ts, ss = map(load, (fp, tp, sp))
    contract_path = front / "INPUT_CONTRACT.json"
    contract = load(contract_path)
    f, t, s = (v["modes"]["partial"] for v in (fs, ts, ss))
    require(ts["acquisition_summary_sha256"] == sha(fp) == ss["acquisition_summary_sha256"], "summary pin mismatch")
    require(ss["original_tracking_summary_sha256"] == sha(tp), "tracking summary pin mismatch")
    require(ts["prepared_plan_sha256"] == ss["prepared_plan_sha256"] == contract["model_plan_sha256"], "plan pin mismatch")
    case_paths = sorted((front / "cases").glob("partial_*.json"))
    require(len(case_paths) == f["cases"], "case coverage mismatch")
    require(set(fs["attempted_case_ids"]) == {p.stem for p in case_paths}, "attempted ID coverage mismatch")
    saved_pins = s["original_case_pins"]
    require(set(saved_pins) == {p.stem for p in case_paths}, "serial case pin coverage mismatch")
    with (serial / "PARTIAL_SCHEDULE.jsonl").open() as handle:
        schedule = [json.loads(line) for line in handle if line.strip()]
    offers = {r["case_id"]: r for r in schedule if r["action"] != "RESULT_ARRIVAL"}
    require(len(offers) == len(case_paths), "offer coverage mismatch")
    actions = Counter(r["action"] for r in offers.values())
    require(dict(actions) == s["service_actions"], "schedule action count mismatch")
    arrivals = [r for r in schedule if r["action"] == "RESULT_ARRIVAL"]
    case_rows, cert_times, attempt_times, whole_times = [], [], [], []
    statuses, cert_reasons, dimensions, backends, cost_sources = (Counter() for _ in range(5))
    checked_pins = {}
    for path in case_paths:
        digest = sha(path)
        require(digest == saved_pins[path.stem], "case pin mismatch: " + path.stem)
        checked_pins[path.stem] = digest
        c = load(path)
        require(c["case_id"] == path.stem and c["execution_commit"] == fs["execution_commit"], "case identity mismatch")
        cert = c.get("search", {}).get("certificate")
        elapsed, source = service_cost(c)
        dim = len(c.get("search", {}).get("all_labels", [])) if cert is not None else None
        if dim is not None:
            require(dim > 0, "nonpositive integer dimension")
            if c["search"].get("best") is not None:
                require(len(c["search"]["best"]["ambiguity"]) == dim, "candidate integer dimension mismatch")
            require(len(c["subset_selection"]["selected_labels"]) == dim, "selected likelihood dimension mismatch")
            cert_times.append(elapsed)
            dimensions[str(dim)] += 1
            cert_reasons[cert["termination_reason"]] += 1
            backends[cert["sphere_backend"]] += 1
        if c.get("search_attempt_elapsed_s") is not None:
            attempt_times.append(finite(c["search_attempt_elapsed_s"], positive=True))
        if c.get("elapsed_s") is not None:
            whole_times.append(finite(c["elapsed_s"]))
        statuses[c["status"]] += 1
        cost_sources[source] += 1
        offer = offers[c["case_id"]]
        require(float(offer["recorded_cils_elapsed_s"]) == elapsed, "schedule service time mismatch")
        require(offer.get("cost_source", "CERTIFICATE_ELAPSED") == source, "schedule cost source mismatch")
        case_rows.append({"trial": prefix, "case_id": c["case_id"], "case_sha256": digest,
             "window_start_s": c["window_start_s"], "selected_at_s": offer["selection_ready_s"],
             "status": c["status"], "search_called": c["search_called"],
             "presearch_unavailable": c.get("presearch_unavailable", False),
             "certificate_present": cert is not None,
             "global_optimum_certified": cert.get("global_optimum_certified", False) if cert else False,
             "termination_reason": cert["termination_reason"] if cert else "NO_CERTIFICATE",
             "integer_dimension": dim, "sphere_backend": cert["sphere_backend"] if cert else "",
             "cost_source": source, "recorded_service_elapsed_s": elapsed,
             "certificate_elapsed_s": elapsed if cert else None,
             "search_attempt_elapsed_s": c.get("search_attempt_elapsed_s"),
             "whole_case_elapsed_s": c.get("elapsed_s"),
             "initial_measurement_time_s": c.get("measurement", {}).get("measurement_time"),
             "initial_valid": c.get("measurement", {}).get("valid", False),
             "serial_offer_action": offer["action"]})
    require(dict(statuses) == f["statuses"], "case status count mismatch")
    require(sum(r["search_called"] for r in case_rows) == f["search_calls"] == fs["new_search_calls"] == complete["new_search_calls"], "search count mismatch")
    require(sum(r["initial_valid"] for r in case_rows) == f["valid_experimental_measurements"], "initial valid mismatch")
    all_streams, valid_times = {}, {}
    for kind, summary, folder in (("acquisition", f, front), ("tracking", t, tracking), ("serial", s, serial)):
        # Resolve the artifact basename against the caller's root for relocation.
        path = folder / Path(summary["csv"]).name
        all_streams[kind], valid_times[kind] = stream(path, summary["valid_experimental_measurements"])
        require(all_streams[kind]["rows"] == (f["cases"] if kind == "acquisition" else summary["epochs"]), "stream coverage mismatch")
        if kind != "acquisition":
            require(valid_times[kind] == summary["valid_times_s"], "saved valid times mismatch")
            events_path = folder / "PARTIAL_EVENTS.jsonl"
            with events_path.open() as handle:
                events = [json.loads(line) for line in handle if line.strip()]
            event_counts = Counter(e["event"] for e in events)
            require(dict(event_counts) == {k:v for k,v in summary["events"].items() if k != "suppressed_valid_origins"}, "event count mismatch")
            require(len(events) == summary["epochs"], "event row coverage mismatch")
            releases = Counter(e["measurement"]["status"] for e in events if e["event"] == "TRACK_RELEASED")
            require(dict(releases) == summary["release_statuses"], "release count mismatch")
            require([e["time_s"] for e in events if e["measurement"]["valid"]] == valid_times[kind], "events/CSV valid mismatch")
            require(len(summary["origins"]) == event_counts["TRACK_STARTED"], "owner count mismatch")
    require(valid_times["acquisition"] == sorted(r["initial_measurement_time_s"] for r in case_rows if r["initial_valid"]), "case/CSV initial valid times mismatch")
    times = sorted(r["selected_at_s"] for r in case_rows)
    spacing = [b-a for a,b in zip(times,times[1:])]
    require(all(v > 0 for v in spacing), "opportunity time collision")
    nominal = round(stats(spacing).get("median_s", 0), 6)
    registered_costs = ss.get("registered_cost_sources_by_mode", {}).get("partial")
    require(registered_costs is None or registered_costs == dict(cost_sources), "registered cost-source mismatch")
    serviced_costs = Counter(r["cost_source"] for r in case_rows if r["serial_offer_action"] == "SEARCH_LAUNCHED")
    if "serviced_cost_sources" in s:
        require(dict(serviced_costs) == s["serviced_cost_sources"], "serviced cost-source mismatch")
    def lifecycle(summary):
        return {"owners": len(summary["origins"]), "releases": summary["events"].get("TRACK_RELEASED", 0),
                "events": summary["events"], "release_statuses": summary["release_statuses"],
                "active_at_end": summary.get("active_at_end", summary.get("active_owner_at_end"))}
    total = len(case_rows)
    result = {"execution_commit": fs["execution_commit"], "likelihood": contract["likelihood"],
      "sphere_backend": contract["sphere_backend"], "opportunities": total,
      "nominal_opportunity_spacing_s": nominal, "actual_spacing_s": stats(spacing),
      "actual_search_attempts": sum(r["search_called"] for r in case_rows),
      "presearch_unavailable": sum(r["presearch_unavailable"] for r in case_rows),
      "certificates_present": sum(r["certificate_present"] for r in case_rows),
      "global_certificates": sum(r["global_optimum_certified"] for r in case_rows),
      "timeouts": sum(v for k,v in cert_reasons.items() if "TIMEOUT" in k.upper()),
      "termination_reasons": dict(cert_reasons), "positive_integer_dimension_cases": sum(dimensions.values()),
      "integer_dimension_counts": dict(dimensions), "certificate_backend_counts": dict(backends),
      "initial_valid": f["valid_experimental_measurements"], "initial_valid_fraction": f["valid_experimental_measurements"] / total,
      "initial_status_counts": dict(statuses), "registered_cost_sources": dict(cost_sources),
      "certificate_time_s": stats(cert_times), "whole_search_attempt_time_s": stats(attempt_times),
      "whole_case_time_s": stats(whole_times), "streams": all_streams,
      "tracking": lifecycle(t), "serial": {**lifecycle(s), "service_actions": dict(actions),
       "serviced_cost_sources": dict(serviced_costs), "arrival_actions": s["arrival_actions"],
       "arrivals": len(arrivals), "pending_at_end": s["pending_at_end"],
       "simulated_cils_attempts_started": actions.get("SEARCH_LAUNCHED", 0),
       "presearch_unavailable_no_cils": actions.get("PRESEARCH_UNAVAILABLE_NO_CILS", 0),
       "dropped_initially_valid_cases": sum(r["initial_valid"] and r["serial_offer_action"] == "BUSY_DROP_NO_QUEUE" for r in case_rows)},
      "tracking_and_serial_csv_byte_equal": all_streams["tracking"]["sha256"] == all_streams["serial"]["sha256"],
      "tracking_and_serial_valid_times_equal": valid_times["tracking"] == valid_times["serial"],
      "case_pins_checked": len(checked_pins),
      "ordered_case_pin_map_sha256": hashlib.sha256(json.dumps(checked_pins,sort_keys=True,separators=(",", ":")).encode()).hexdigest(),
      "input_hashes": {str(p.relative_to(root)):sha(p) for p in (complete_path,fp,tp,sp,contract_path,serial/"PARTIAL_SCHEDULE.jsonl",tracking/"PARTIAL_EVENTS.jsonl",serial/"PARTIAL_EVENTS.jsonl")},
      "zero_cost_components": ss["zero_cost_components"],
      "real_time_implementation": ss["real_time_implementation"],
      "wall_clock_realtime_validated": ss["wall_clock_realtime_validated"],
      "integer_truth_available": ss["integer_truth_available"],
      "lifetime_false_fix_probability": ss["lifetime_false_fix_probability"]}
    return result, case_rows


def report(dense, prior):
    arms = [("旧 120 窗 / Python", prior), ("新 1191 窗 / native", dense)]
    lines = ["# Dense selected-observation frontend readout", "",
      "完整驱动 COMPLETE 后在 Ubuntu 22.04 WSL 只读汇总。新增 CILS、模型重验收、导航、参考/trace 读取均为 0；全部 case 保留。",
      "", "| 项目 | 旧 120 窗 / Python | 新 1191 窗 / native |", "|---|---:|---:|"]
    fields = [("机会 / 实际搜索",lambda a:f"{a['opportunities']} / {a['actual_search_attempts']}"),
      ("机会间隔 s",lambda a:a['nominal_opportunity_spacing_s']),
      ("预选不可用 / 超时",lambda a:f"{a['presearch_unavailable']} / {a['timeouts']}"),
      ("全局证书",lambda a:a['global_certificates']),
      ("初始合格候选",lambda a:f"{a['initial_valid']} ({a['initial_valid_fraction']:.2%})"),
      ("普通跟踪有效 / 总历元",lambda a:f"{a['streams']['tracking']['valid']} / {a['streams']['tracking']['rows']}"),
      ("串行有效 / 总历元",lambda a:f"{a['streams']['serial']['valid']} / {a['streams']['serial']['rows']}"),
      ("普通与串行 owner / release",lambda a:f"{a['tracking']['owners']} / {a['tracking']['releases']} ; {a['serial']['owners']} / {a['serial']['releases']}"),
      ("串行启动 / 忙丢弃 / 末尾待处理",lambda a:f"{a['serial']['simulated_cils_attempts_started']} / {a['serial']['service_actions'].get('BUSY_DROP_NO_QUEUE',0)} / {len(a['serial']['pending_at_end'])}"),
      ("CILS 中位 / P95 / 最大 s",lambda a:' / '.join(f"{a['certificate_time_s'][k]:.6f}" for k in ['median_s','p95_s','max_s'])),
      ("CILS >0.2 / >1 / >2 s 个数",lambda a:' / '.join(str(a['certificate_time_s'][f'gt_{v}s_count']) for v in ['0.2','1','2']))]
    for label,fn in fields:
        lines.append(f"| {label} | {fn(prior)} | {fn(dense)} |")
    lines += ["", f"本轮冻结 `{dense['execution_commit']}`；对照冻结 `{prior['execution_commit']}`。",
      "整数维数指搜索未知整数的数量，不是正号整数值的个数。新/旧分布分别为 " + str(dense['integer_dimension_counts']) + " / " + str(prior['integer_dimension_counts']) + "。证书证明登记的新预选观测似然下的全局候选搜索完成，不能证明物理整数正确。",
      "", "## 保留的初始结果", "", "| 状态 | 旧 120 | 新 1191 |", "|---|---:|---:|"]
    for status in sorted(set(dense['initial_status_counts']) | set(prior['initial_status_counts'])):
        lines.append(f"| {status} | {prior['initial_status_counts'].get(status,0)} | {dense['initial_status_counts'].get(status,0)} |")
    lines += ["", "## 跟踪、串行与时间边界", "",
      f"新普通与串行测量 CSV 逐字节一致：{dense['tracking_and_serial_csv_byte_equal']}；旧轮一致：{prior['tracking_and_serial_csv_byte_equal']}。新串行被丢弃机会中原初始合格候选为 {dense['serial']['dropped_initially_valid_cases']} 个。owner 竞争、释放与无效历元仍保留，不能把初始候选数量直接当作独立有效测量数量。",
      "", "新普通跟踪事件：`" + json.dumps(dense['tracking']['events'],sort_keys=True) + "`。",
      "", "新串行到达结果（包括无效候选）：`" + json.dumps(dense['serial']['arrival_actions'],sort_keys=True) + "`。",
      "", "新释放原因（普通与串行分别保存在 JSON）：`" + json.dumps(dense['serial']['release_statuses'],sort_keys=True) + "`。",
      "", "新登记服务成本来源：`" + json.dumps(dense['registered_cost_sources'],sort_keys=True) + "`；实际被串行模拟服务的来源：`" + json.dumps(dense['serial']['serviced_cost_sources'],sort_keys=True) + "`。",
      "", "正常搜索服务成本严格取 certificate.elapsed_s；无证书失败才取显式 whole-attempt timer，明确未搜索的预选失败计 0 CILS。后两类本轮均为 0。总 case 时间与 whole-attempt 时间另存在 JSON/逐例 CSV，未替换 CILS 成本。分位数使用排序样本的线性插值，保留超时与失败，不只统计合格结果。",
      "", "串行结果仍是 idealized recorded CILS service cost 回放：单 worker、忙则丢弃、无队列；准备、模型读取、验证、诊断、catchup、跟踪、导出、I/O 与资源争用开销均未计。完成后且原五历元验收齐备才允许当前历元输出；不是实际 wall-clock 实时测量，也不是部署实时性证明。",
      "", "## 比较允许的结论", "",
      "相比旧轮，本轮同时把 Python 球面核改为 native，并把 2 s 获取机会改为每个 0.2 s RAWX 历元；两次执行负载与时段也不同。因此这些整轮差异不是孤立调度消融，不能把耗时变化或可用量变化全部归因于 cadence。共用 120 窗的独立等价复核由 DENSE_SELECTED_EQUIVALENCE 报告承担，本脚本不重做候选搜索或等价审计。",
      "", "重叠选择/未来窗口与同一 owner 的持续输出存在依赖，116 个初始合格、157 个有效历元均不是独立成功试验。无真实整数标签，lifetime false-fix probability 未校准；没有以参考精度删窗或改门。这里只报告前端支持与记录成本，不作航向/位置精度判断。",
      "", "## 复现", "", "从仓库根目录在 Ubuntu 22.04 WSL 执行（只读已有产物）：", "", "```bash",
      "python3 scripts/paper_rebuild/carrier_phase/summarize_dense_selected_frontend.py --scratch-root <CARRIER_INTEGRATION_ROOT> --output-dir <REPORT_DIRECTORY>",
      "```", "", "脚本要求两轮 COMPLETE 和三阶段成功，核验 summary/case pins、CSV/event 数量、时间顺序与逐行有效状态；保存所有 1311 个 case 的状态/维度/耗时/串行动作及 SHA。运行目录以调用参数传入，报告不保存机器绝对路径。"]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    driver_path = args.scratch_root / "DENSE_SELECTED_DRIVER/COMPLETE.json"
    driver = load(driver_path)
    require(driver.get("status") == "COMPLETE" and driver.get("completed_phases") == 3, "dense driver incomplete")
    dense, dense_rows = read_arm(args.scratch_root, "DENSE_SELECTED")
    prior, prior_rows = read_arm(args.scratch_root, "SELECTED_LIKELIHOOD")
    require(dense["opportunities"] == 1191 and prior["opportunities"] == 120, "registered opportunity count mismatch")
    result = {"schema": "DENSE_SELECTED_FRONTEND_READOUT_V1", "operation": "READ_ONLY_COMPLETED_ARTIFACT_AGGREGATION",
      "new_solver_calls": 0, "reference_reads": 0, "epoch_model_reads": 0, "gate_revalidation_calls": 0,
      "comparison": "native backend and acquisition cadence changed together; not an isolated scheduling ablation",
      "quantile_method": "linear interpolation at (n-1)*p", "driver_complete_sha256": sha(driver_path),
      "summary_script_sha256": sha(Path(__file__)), "dense": dense, "prior_selected_python": prior}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / "DENSE_SELECTED_FRONTEND"
    stem.with_name(stem.name + "_SUMMARY.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    with stem.with_name(stem.name + "_RESULTS.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(dense_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(dense_rows + prior_rows)
    stem.with_name(stem.name + "_READOUT.md").write_text(report(dense, prior), encoding="utf-8")
    print(json.dumps({"status": "PASS", "case_rows": len(dense_rows) + len(prior_rows), "dense": {k:dense[k] for k in ['opportunities','actual_search_attempts','global_certificates','initial_valid','certificate_time_s']}, "output_dir": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
