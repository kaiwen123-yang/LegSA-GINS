#!/usr/bin/env python3
"""Engineering derivation from sealed BODY_PROXY_AUDIT outputs; no raw replay."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

CODE = Path(__file__).resolve().parents[3]
DOCS = CODE / "docs/paper_rebuild/TRUSTED_HEADING_20261006"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stats(values):
    a = np.asarray(values, dtype=float)
    return {"n": len(values), "min": float(a.min()), "median": float(np.median(a)),
            "p99": float(np.quantile(a, .99)), "max": float(a.max())} if len(a) else {"n": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-paths", type=Path, required=True)
    parser.add_argument("--stage-alias", required=True)
    args = parser.parse_args()
    aliases = json.loads(args.local_paths.read_text())["aliases"]
    token = "<SCRATCH_ROOT>"
    if not args.stage_alias.startswith(token + "/"):
        raise ValueError("stage must use scratch alias")
    stage = Path(aliases[token]) / args.stage_alias[len(token) + 1:]
    seal = json.loads((stage / "COMPLETE.json").read_text())
    for filename, expected in seal["files"].items():
        if sha(stage / filename) != expected:
            raise ValueError("sealed file changed: " + filename)
    source = json.loads((stage / "SUMMARY.json").read_text())
    output = {"source_stage_alias": args.stage_alias,
              "scope": "read-only saved grid/event derivation; raw/body/GNSS/reference payload reads 0",
              "complete_sha256": sha(stage / "COMPLETE.json"),
              "rows_verified": 0, "sequences": {}, "raw_replay": False}
    copied = {}
    archive = DOCS / "body_proxy_audit"
    archive.mkdir(exist_ok=True)
    for summary in source["sequence_summaries"]:
        name = summary["sequence"]
        with (stage / (name + "_GRID.csv")).open() as handle:
            rows = list(csv.DictReader(handle))
        expected = [round(summary["full_window_s"][0] * 1e9) + k * 100_000_000
                    for k in range(summary["registered_grid_denominator"])]
        actual = [round(float(v["grid_time_s"]) * 1e9) for v in rows]
        assert actual == expected
        output["rows_verified"] += len(rows)
        arity = Counter(int(v["usable_foot_count"]) for v in rows)
        combinations = Counter(v["usable_feet"] for v in rows if int(v["rank"]) > 0)
        instant = Counter(sum(value == "STANCE" for value in json.loads(v["support_states"]).values())
                          for v in rows if v["support_states"])
        by_rank, z_projector = defaultdict(list), []
        orthogonality_max = 0.
        for row in rows:
            if row["current_source_time_s"]:
                assert float(row["current_source_time_s"]) <= float(row["grid_time_s"]) + 1e-12
            rank = int(row["rank"])
            if not rank:
                continue
            assert 0.1 - 1e-12 <= float(row["actual_dt_s"]) <= .15 + 1e-12
            assert 0 <= float(row["source_age_s"]) <= .05 + 1e-12
            assert float(row["previous_source_time_s"]) >= summary["full_window_s"][0]
            assert float(row["current_source_time_s"]) <= summary["full_window_s"][1]
            basis = np.asarray(json.loads(row["observable_basis_frd_json"]))
            null = np.asarray(json.loads(row["nullspace_frd_json"]))
            orthogonality_max = max(orthogonality_max,
                float(np.max(np.abs(basis.T @ basis - np.eye(rank)))))
            if 3-rank:
                orthogonality_max = max(orthogonality_max, float(np.max(np.abs(basis.T @ null))))
            assert orthogonality_max < 1e-12
            assert row["gyro_status"] == "INTERNAL_CONSISTENCY_ONLY"
            by_rank[str(rank)].append(float(row["observable_cayley_difference_norm_rad_s"]))
            if rank == 2:
                z_projector.append(float(np.sum(basis[2, :] ** 2)))
        with (stage / (name + "_SUPPORT_EVENTS.csv")).open() as handle:
            events = list(csv.DictReader(handle))
        with (stage / (name + "_FAULTS.csv")).open() as handle:
            faults = list(csv.DictReader(handle))
        gap_events = sorted({float(v["source_time_s"]) for v in events if "SOURCE_GAP" in v["reasons"]})
        transitions_by_foot = Counter(v["foot"] for v in events if v["state_before"] != v["state_after"])
        result = {
            "grid_rows": len(rows), "usable_foot_count_full_grid": dict(arity),
            "valid_geometry_foot_combinations": dict(combinations),
            "instant_stance_count_at_selected_grid_sample": dict(instant),
            "source_fault_ledger_rows": len(faults),
            "saved_support_transitions_by_foot": dict(transitions_by_foot),
            "source_gap_with_recorded_support_transition_times_s": gap_events,
            "source_gap_count_limit": "Only times carrying SOURCE_GAP in saved support-transition events; not asserted to count every source-message gap.",
            "observable_cayley_difference_rad_s_by_rank": {k: stats(v) for k, v in by_rank.items()},
            "rank2_body_frd_z_projector_diagonal": stats(z_projector),
            "z_projection_limit": "Geometry alignment only. Values near one do not make global yaw or body-z rotation exactly identifiable; nonzero null-axis z component remains.",
            "basis_orthogonality_max_abs": orthogonality_max,
            "all_grid_timekeys_and_causality_checked": True,
            "full_rank_unavailable_reason": ("No >=3 feet retain a common eligible contact episode across selected full intervals."
                if summary["grid_rank_counts"]["3"] == 0 else
                "Rank-3 records consist of three/four common continuous SDK-support proxies, not independently certified no-slip contacts."),
        }
        output["sequences"][name] = result
        for suffix in ("GRID", "FAULTS", "SUPPORT_EVENTS"):
            filename = name + "_" + suffix + ".csv"
            data = (stage / filename).read_bytes()
            compressed = gzip.compress(data, mtime=0)
            destination = archive / (filename + ".gz")
            destination.write_bytes(compressed)
            assert gzip.decompress(destination.read_bytes()) == data
            copied[str(destination.relative_to(DOCS))] = {
                "compressed_sha256": sha(destination),
                "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                "source_filename": filename, "uncompressed_size": len(data)}
    assert output["rows_verified"] == 9213
    output["copies"] = copied
    (DOCS / "BODY_PROXY_AUDIT_DERIVED.json").write_text(
        json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf8")
    lines = [
        "# 三全窗机体输入与接触旋转代理：工程运行记录", "",
        "本次一次执行完成，耗时 {:.3f} s。保留 9213 个固定 10 Hz 网格点、191781 条窗内机体源记录，以及 24360 条仅用于因果支撑历史的前缀记录。Python 文件打开审计只允许三个锁定 body 文件；GNSS、参考、导航解算、整数搜索和评价器均为 0。原始文件只核锁定 size，继承原登记 SHA，不重哈希。".format(source["elapsed_s"]),
        "", "| 序列 | 完整网格 | rank 0 / 2 / 3 | 几何可用比例 | 最长 rank-0 网格覆盖 |",
        "|---|---:|---|---:|---:|"]
    for summary in source["sequence_summaries"]:
        rank = summary["grid_rank_counts"]
        lines.append("| {} | {} | {} / {} / {} | {:.2%} | {:.1f} s |".format(
            summary["sequence"], summary["registered_grid_denominator"], rank["0"], rank["2"], rank["3"],
            summary["rank_positive_fraction_full_grid"], summary["max_rank0_grid_coverage_s"]))
    lines += ["", "三窗 rank 1 均为 0。几何可用比例不是航向准入率。最长空窗按连续 rank-0 点数乘 0.1 s 的网格覆盖计算，含初始端点不足，不能称物理传感器失效时长。",
        "", "## BY2 / BY2H 为什么没有 rank 3",
        "", "BY2 的 1357 个可用区间全部恰好保留两个连续共同支撑足：FR/RL 666 次，FL/RR 691 次。BY2H 的 1326 个可用区间同样只有两足：634 / 692 次。瞬时消息虽然曾显示三足或四足支撑，但第三足没有在所选约 0.1 s 区间两端与完整中间历史中保持同一有效 episode。不能仅取端点 stance 交集来补成三维观测。",
        "", "因此这里的 rank 2 是实际输入和连续支撑资格共同决定的几何不可观方向，不是 SVD 求解失败。两足连线方向必须保留为 nullspace。BY2O 的 898 个 rank-3 区间来自 37 个三足和 861 个四足连续共同支撑区间；这是不同支撑场景，不能拿它与两足子集比较后宣称算法精度提高。",
        "", "## 与机体陀螺的内部一致性",
        "", "| 序列 / 秩 | 样本 | 可观 Cayley 率差中位数 (rad/s) | P99 | 最大值 |",
        "|---|---:|---:|---:|---:|"]
    for name, result in output["sequences"].items():
        for rank, value in result["observable_cayley_difference_rad_s_by_rank"].items():
            lines.append("| {} / {} | {} | {:.6f} | {:.6f} | {:.6f} |".format(
                name, rank, value["n"], value["median"], value["p99"], value["max"]))
    lines += ["", "比较使用完整同区间原始 gyro 左保持 SO(3) 积分，再转为同一 Cayley 参数。沿用 H5 的传感器到 body-FLU 的 Rx(-1°)，再做 FLU→FRD；没有估计偏置、拟合时间偏移、读取 SDK 姿态或补地球/运输项。差值仅投影至接触可观子空间，不是真实姿态误差，也不证明两路独立。",
        "", "rank-2 可观投影对 body-FRD z 轴的覆盖在本批几何中接近 1，派生 JSON 保留完整最小/中位/最大统计。这只是几何方向关系；剩余 nullspace 的 z 分量通常并非严格为零，更不能将 body-z 旋转直接改称全局航向完全可观。",
        "", "## 源字段、时序与故障",
        "", "| 序列 | 窗内记录 / error_code=0 | 足点精确重复比例 | gyro 精确重复比例 | 足力精确重复比例 | 最大源间隔 (s) |",
        "|---|---:|---:|---:|---:|---:|"]
    for summary in source["sequence_summaries"]:
        counts = summary["counts"]
        repeat = summary["exact_adjacent_field_repeats_window"]
        lines.append("| {} | {} / {} | {:.2%} | {:.2%} | {:.2%} | {:.6f} |".format(
            summary["sequence"], counts["source_records_window"], summary["source_error_code_counts_window"]["0"],
            repeat["feet"]["fraction"], repeat["gyro"]["fraction"], repeat["force"]["fraction"],
            summary["source_step_s"]["max"]))
    lines += ["", "三个源故障表均为 0 行：本次读取范围内没有允许字段解析失败、非单调 timestamp 或非零/缺失 error_code。该结果不证明没有滑移、硬件误差或 SDK 内部共享依赖。精确重复率按相邻可解码字段组计数；gyro 重复检查作用于固定安装/坐标变换后的三个值。",
        "", "源时间断点仍真实存在，不能因 error_code=0 忽略。保存的支撑转移事件中，带 SOURCE_GAP 的不同时间为 BY2 1、BY2H 2、BY2O 10 个；这只是现有事件表可确认的计数，不冒充所有消息间隔超限数。runner 未另保存每个源间隔的全表，本次不为补该统计重读原始文件。",
        "", "BY2H 保留 1 个 current-stale 和 1 个 interval-too-long 网格；BY2O 分别保留 10 和 3 个。全网格 actual-dt 统计包括被拒绝的长区间，不能用它的最大值反过来声称有效几何越过 0.15 s 工作限制；有效记录逐项复核均满足因果时序及既定源间隔条件。",
        "", "## 可执行接口边界",
        "", "下一步若接入研发后端，只能构造随 rank 变化的可观子空间旋转增量因子；rank-2 时保留 nullspace，支撑 episode 更换、源断点或无共同足时撤销该因子，不能补零、续旧弧或施加三维强姿态先验。陀螺在空窗传播不等于接触因子仍有效。",
        "", "Q=I、w_linearization=0 在本次仅用于无权几何计算，没有输出校准协方差，也没有按差值调任何门限。真实误差、滑移敏感性、SDK 与 IMU 相关性尚未闭合；不能把本次内部差值拟合出的噪声当成独立传感器标定。是否进入后续融合应由另行登记的观测模型、保守误差处理与导航不退化试验决定。",
        "", "## 完整产物与复核",
        "", "BODY_PROXY_AUDIT_COUNTS.csv / SUMMARY.json 为原一次运行归纳；DERIVED.json 为只读全网格支持、秩/足组合及内部一致性分层复核。body_proxy_audit/ 下保存三窗 GRID、FAULTS、SUPPORT_EVENTS 的无损 gzip，共 9 文件；解压哈希与原 seal 一致，未删异常或只保留可用点。",
        "", "原 PLAN / INVOCATION / IO_AUDIT / COMPLETE 及日志位于 " + args.stage_alias + "。原 runner 在执行后未修改；本派生使用独立 trusted_heading_body_proxy_readout.py，0 原始输入再读、0 新解算。"]
    report = DOCS / "BODY_PROXY_AUDIT_REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf8")
    original_receipt = json.loads((DOCS / "BODY_PROXY_AUDIT_RECEIPT.json").read_text())
    original_receipt["pre_readout_publish_report_sha256"] = original_receipt["files"]["BODY_PROXY_AUDIT_REPORT.md"]
    original_receipt["files"]["BODY_PROXY_AUDIT_REPORT.md"] = sha(report)
    original_receipt["files"]["BODY_PROXY_AUDIT_DERIVED.json"] = sha(DOCS / "BODY_PROXY_AUDIT_DERIVED.json")
    original_receipt["derived_readout_script"] = str(Path(__file__).resolve().relative_to(CODE))
    original_receipt["derived_readout_script_sha256"] = sha(__file__)
    original_receipt["derived_data_scope"] = "sealed GRID/SUPPORT_EVENTS/FAULTS/summary only; raw replay 0"
    original_receipt["compressed_complete_tables"] = copied
    original_receipt["independent_static_review"] = "planner agent: causal grid/source ordering, full support history, gyro rotation order and complete denominator; no blocking issue, no execution."
    (DOCS / "BODY_PROXY_AUDIT_RECEIPT.json").write_text(
        json.dumps(original_receipt, indent=2, allow_nan=False) + "\n", encoding="utf8")
    print(json.dumps({"status": "READOUT_COMPLETE", "verified_grid_rows": output["rows_verified"],
                      "copied_tables": len(copied), "raw_replay": 0, "report_sha256": sha(report)}))


if __name__ == "__main__":
    main()
