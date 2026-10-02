#!/usr/bin/env python3
"""Read retained CORE statistics/metadata; write descriptive and validation views.

No project imports, subprocess, gzip, reference, NAV, provider payload, evaluator,
bootstrap or plotting. Output is confined to the approved interpretation/core.
Numeric validation is on previously published run metrics, never raw epochs.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import re

import numpy as np


METHODS = ("F01", "F02", "F03", "F04", "A03", "A04", "A05", "A06", "A07", "A08", "A09")
METRICS = ("horizontal_rmse_m", "position_3d_rmse_m", "up_rmse_m", "yaw_rmse_deg",
           "yaw_p95_absolute_deg", "roll_rmse_deg", "pitch_rmse_deg")
FAMILIES = ("gnss_outage", "gnss_sampling", "position_value", "position_std_status",
            "dual_yaw", "velocity_raw_doppler", "go2_prior_metadata", "multi_source_mixed")
TITLES = dict(zip(FAMILIES, ("GNSS 停测", "GNSS 采样与随机掉线", "位置数值扰动", "位置标准差与状态",
                              "双天线标量航向", "接收机速度与 Raw Doppler", "Go2 弱先验与元数据", "多源混合故障")))
EXPLANATIONS = {
    "gnss_outage": "D01–D04 只停 GNSS position，时长 3/5/10/20 s；D05 同停 position 与 RV 10 s；D06 同停 position、RV、dual yaw 20 s；D07 为三次各 3 s 位置停测。这里 D06 的名称 all_update 只覆盖列出的三通道，不能等同于 A1 的全部 GNSS/速度通道中断。RD、RP 和各 case 的 HV 文件按冻结源继承，是否使用由方法开关决定。",
    "gnss_sampling": "D08/D09/D10 的目标采样率为 5/2/1 Hz；D11/D12 继承 30%/60% 随机掉线事件。5 Hz 标量航向映射使用 anchor 相位分箱、每箱首个有效行；掉线事件沿原 [t,t+1) 时间单元延拓，未重新独立抽取 5 Hz 事件。D08 原 bundle 可记录 idempotent=true，故名义 downsample 不保证实际产生额外缺测。",
    "position_value": "D13–D15 为不同幅度位置噪声；D16/D17 为静态偏置；D18 漂移；D19 正弦多路径；D20/D21 单点尖峰；D22 突发尖峰。相同强度定义在不同 seed 有不同方向、符号或事件；D22 以已冻结秒制区间为准，不重新按原 YAML 的 3–5 行长度解释实际持续时间。",
    "position_std_status": "D23–D25 膨胀位置标准差，D26 使标准差过度乐观；D27 同时损坏位置值并缩小 std；D28 位置值不变但 std 悲观；D29 仅状态/质量降级。标准差是输入权重字段，不能直接称作真实误差方差。不同方法使用 SA 的差异可对应输入暴露差异，但本项不证明 SA 的因果保护机理。",
    "dual_yaw": "D30/D31 为 5/20 s 航向停测；D32/D33 为噪声，D34/D35 为尖峰；D36/D37 修改 std，D38 为坏 yaw 配乐观 std，D39 为质量掉线，D40 为 baseline/rel-acc 元数据，D41 为单接收机非对称扰动转成标量角差。D40 的真实 bundle 明示 no_active_path、baseline_length_solver_visible=false、solver_runtime_input_unchanged=true；它不是正式标量方法的 3D baseline 实验。随机扰动按原 1 s 单元延拓；std 缩放仅原有行继承，中间 5 Hz 行未补缩放。HV 仍继承原 status 航向旋转，不随新 5 Hz 航向重建。",
    "velocity_raw_doppler": "D42–D45 操作接收机速度 RV；D46–D49 操作 Raw Doppler；D50 注入二者冲突。两者是不同通道，F02 的 RV=false，RD 也仅部分方法打开；名义相同 case 不等于所有方法都接收同样被污染的更新。D50 实际组件需读 bundle：可为 RD 偏置而 receiver_velocity_unchanged=true，不能凭 affected_sources 名称宣称两边都改了值。",
    "go2_prior_metadata": "D51/D52 操作 RP 弱先验，D53/D54 操作 HV 弱先验；D55/D56 为 contact/motion/foot 元数据诊断。以 bundle 的 no_active_path 和组件回执识别元数据是否存在标量运行通路，不把诊断 case 当作已启用 contact/FK 因子。Go2 始终是弱先验/诊断源，不是真值；HV 仍继承原 status 航向旋转及有效性处理。",
    "multi_source_mixed": "D57 保留各源 latency/jitter 的真实时间 token，V3 只按原始 iTOW 精确匹配 raw 航向，不插值、不取邻行、不修正时标；预注册明示有效航向行为 0。D58 是位置停测+航向尖峰+恢复，D59 坏位置+RD/RV 冲突但航向不注入，D60 多源坏值+乐观 std+恢复。恢复区间只是注入组件元数据，现有 V3 全窗指标不能自动变成恢复时间或段内 RMSE。HV 原样继承 status 旋转。",
}
PAIRS = {"full_vs_strong": ("F04", "F03"), "full_vs_no_RD": ("F04", "A03"),
         "full_vs_no_SA": ("F04", "A04"), "full_vs_no_RP": ("F04", "A05"),
         "full_vs_no_HV": ("F04", "A06"), "full_vs_no_Go2": ("F04", "A07"),
         "A04_vs_F03": ("A04", "F03")}
REPO = Path(__file__).resolve().parents[2]
DEST = REPO / "docs/paper_rebuild/audit_xbpg_20261001/v3_interpretation/core"
READS = []
ALIASES = {}


def alias(value):
    if isinstance(value, str):
        for name, root in sorted(ALIASES.items(), key=lambda x: -len(x[1])):
            value = value.replace(root, name)
        return value
    if isinstance(value, dict):
        return {alias(k): alias(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [alias(v) for v in value]
    return value


def resolve(value):
    for name, root in ALIASES.items():
        if value == name or value.startswith(name + "/"):
            return Path(root) / value[len(name):].lstrip("/")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("Unresolved metadata path")
    return path


def read_text(path, kind):
    path = Path(path)
    if path.suffix not in (".json", ".csv", ".md", ".yaml") or path.is_symlink():
        raise ValueError("Only explicit text metadata/statistic files are admitted")
    text = path.read_text(encoding="utf-8-sig")
    READS.append(dict(source_path=alias(str(path)), read_depth="FULL_PAYLOAD_READ", source_kind=kind,
                      eof_reached=True, byte_size=path.stat().st_size, row_count="not_applicable",
                      hash_status="NOT_REHASHED_THIS_ITEM"))
    return text


def read_csv(path, kind="existing_statistics"):
    import io
    text = read_text(path, kind)
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    READS[-1]["row_count"] = len(rows)
    READS[-1]["columns"] = json.dumps(reader.fieldnames, ensure_ascii=False)
    for i, row in enumerate(rows, 1):
        row["_read_path"] = alias(str(path))
        row["_read_data_row"] = str(i)
    return rows


def dump_csv(path, rows, fallback=()):
    path = Path(path)
    if DEST not in path.parents:
        raise ValueError("Write outside approved core directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row)) or list(fallback)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            portable = alias(row)
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                             if isinstance(v, (list, dict, tuple)) else v for k, v in portable.items()})


def dump_json(path, data):
    if DEST not in Path(path).parents:
        raise ValueError("Write outside approved core directory")
    Path(path).write_text(json.dumps(alias(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def numeric(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def complete(row):
    return row["evaluation_status"] == "COMPLETED"


def same_numeric(a, b):
    x, y = numeric(a), numeric(b)
    if x is None or y is None:
        return x is None and y is None
    return math.isclose(x, y, rel_tol=1e-10, abs_tol=1e-10)


def original_row(row, version):
    return {"evaluator_version": version, **{k: v for k, v in row.items() if not k.startswith("_read_")}}


def definitions(text):
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"  - id: D\d\d$", line)]
    out = []
    for start, end in zip(starts, starts[1:] + [len(lines)]):
        block = lines[start:end]
        row = {"source_path": "<CODE_ROOT>/configs/paper_rebuild/degradation_60types_9seeds.yaml",
               "source_row_key": f"lines:{start+1}-{end}", "source_column": "degradation_types"}
        for line in block:
            m = re.match(r"\s+(?:- )?(id|name|family|parameters|affected_sources|claim_level):\s*(.*)", line)
            if m:
                row[m[1]] = m[2]
        out.append(row)
    if len(out) != 60:
        raise ValueError("Expected 60 explicit degradation definitions")
    return out


def validate_summary(source, group, version, scope):
    out = []
    for record in source:
        metric = record["metric"]
        selected = [r for r in group if r["method_id"] == record["method_id"]]
        if scope == "type":
            selected = [r for r in selected if r["degradation_type_id"] == record["degradation_id"]]
        vals = [numeric(r.get(metric)) for r in selected if complete(r)]
        if any(v is None for v in vals):
            raise ValueError("COMPLETED run has missing/nonfinite primary metric")
        a = np.asarray(vals, dtype=float)
        n = math.ceil(.05 * len(a))
        checks = dict(registered_count=len(selected), finite_count=len(a),
                      algorithm_failure_count=sum("ALGORITHM_FAILURE" in r["failure_classification"] for r in selected),
                      mean=float(a.mean()) if len(a) else None, median=float(np.median(a)) if len(a) else None,
                      p95=float(np.percentile(a, 95)) if len(a) else None,
                      maximum=float(a.max()) if len(a) else None,
                      worst_5pct_mean=float(np.sort(a)[-n:].mean()) if n else None, worst_5pct_count=n)
        for field, value in checks.items():
            out.append(dict(evaluator_version=version, scope=scope, method_id=record["method_id"],
                degradation_id=record.get("degradation_id", "ALL_FAMILY"), metric=metric,
                source_path=record["_source_path"], source_row_key=record["_source_row_key"],
                source_column=field, source_value=record[field], validation_value=value,
                validation_status="MATCH_WITHIN_TOLERANCE" if same_numeric(record[field], value) else "MISMATCH",
                calculation_type="VALIDATION_EXISTING_RUN_METRICS", tolerance="abs=1e-10;rel=1e-10",
                input_source="ORIGINAL_RUN_VALUES.csv", input_selector=f"version={version};method={record['method_id']};metric={metric};scope={scope};degradation={record.get('degradation_id','ALL_FAMILY')}"))
    return out


def family_report(family, values, summaries, types, pairs, matrix, pair_summary, tails, failures, injection, defs, checks):
    title = TITLES[family]
    cases = sorted({r["case_id"] for r in values})
    ids = sorted({r["degradation_type_id"] for r in values})
    lines = [f"# CORE — {title}（{family}）", "",
        f"本族包含 {len(ids)} 个退化类型（{ids[0]}–{ids[-1]}）、每类型 9 个种子，共 {len(cases)} 个案例；11 个方法对应 {len(cases)*11} 个唯一 native，v3/v2 合计 {len(values)} 个评价槽。BY2 同一条原始轨迹上的半合成受控退化，不是这些数量的独立实测序列。失败行完整保留。", "",
        "## 注入什么，保持什么", "", EXPLANATIONS[family], "",
        "[TYPE_DEFINITIONS.csv](TYPE_DEFINITIONS.csv) 保留原 YAML 定义；[INJECTION_CASES.csv](INJECTION_CASES.csv) 和 [INJECTION_COMPONENTS.csv](INJECTION_COMPONENTS.csv) 来自逐 case 的实际冻结 bundle，后者保留组件名、affected_source、affected_epoch_count、details 与原 JSON pointer。实际窗口、随机方向、幅度与 anchor 以这些已实现记录为准。", "",
        "所有非航向注入保持既有 Protocol v2.1 字节，Protocol V3 只换已注册 GNSS yaw/yaw_valid；持续航向方法为 raw HPPOSECEF scalar/BOTH_FIXED。HV 文件仍继承 status 航向旋转及原注入有效性，不能说整个航向依赖链都已变成 5 Hz。窗口内停测只影响实际指定通道，不自动停掉 RD、RP/HV。", "",
        "9 个 seed 的实际 anchor 如下。旧定义 YAML 的 seed_01=88、seed_02=146 等候选时刻没有当作实际事件时间。不同类型的具体半开区间/随机事件详见组件表；无 interval 字段时不凭 anchor 猜造时间窗。", "",
        "| seed | 实际 anchor(s) | seed_value |",
        "|---|---:|---:|"]
    seeds = defaultdict(set)
    seedvalues = defaultdict(set)
    for row in injection:
        seeds[row["seed_index"]].add(str(row["anchor_time_s"]))
        seedvalues[row["seed_index"]].add(str(row["seed_value"]))
    for seed in sorted(seeds):
        lines.append(f"| {seed} | {', '.join(sorted(seeds[seed]))} | {', '.join(sorted(seedvalues[seed]))} |")
    lines += ["", "V3 顶层及 bundle 的 data_mode 为 semisynthetic。历史嵌套 case_meta 仍可能写 semisynthetic_data_used=false；两层原值在注入表分列保留，不能用旧字段把当前受控退化称为自然实测。所有源 hash 在本项为 recorded，未重 hash provider 载荷。", "",
        "## 全部 11 方法的既有结果", "",
        "下表只作阅读导航，完整精度及全部 7 个指标、两评价版本在 [ORIGINAL_DISTRIBUTIONS.csv](ORIGINAL_DISTRIBUTIONS.csv)；逐类型见 [ORIGINAL_TYPE_DISTRIBUTIONS.csv](ORIGINAL_TYPE_DISTRIBUTIONS.csv)。H 为运行级水平 RMSE，单位 m；Yaw 为运行级 yaw RMSE，单位 deg。mean/median/P95 是跨成功案例的等案例权重统计，不是逐历元 pooled RMSE。", "",
        "| 方法 | v3 完成/注册 | v3 H mean | v3 H median | v3 H P95 | v3 Yaw mean | v2 H mean |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    lookup = {(r["evaluator_version"], r["method_id"], r["metric"]): r for r in summaries}
    for m in METHODS:
        h = lookup["v3", m, "horizontal_rmse_m"]; y = lookup["v3", m, "yaw_rmse_deg"]
        h2 = lookup["v2", m, "horizontal_rmse_m"]
        lines.append(f"| {m} | {h['finite_count']}/{h['registered_count']} | {h['mean']} | {h['median']} | {h['p95']} | {y['mean']} | {h2['mean']} |")
    lines += ["", "原始分布表另保留 maximum、worst_5pct_mean/count、故障分母；所有源路径/源数据行/列名均在 CSV 中。失败数按 native 状态、evaluator 状态和 failure_classification 分列计数，见 [STATUS_COUNTS.csv](STATUS_COUNTS.csv)；全部失败槽在 [FAILURES.csv](FAILURES.csv)，没有用 0 填 RMSE。", ""]
    failures_v3 = [r for r in failures if r["evaluator_version"] == "v3"]
    fc = Counter(r["native_status"] for r in failures_v3)
    lines += [f"本族 v3 非完成槽 {len(failures_v3)} 个，上述非完成槽的原 native 状态分布：`{json.dumps(dict(fc), ensure_ascii=False, sort_keys=True)}`。这不是新故障分类，07C/07E 的后续展示分类需保留其独立版本。", "",
        "## 同案例的完成状态与配对差", "",
        "[F04_COMPLETION_2X2.csv](F04_COMPLETION_2X2.csv) 按同 case 列出 F04 与另外十方法：双方完成、仅 F04 完成、仅对方完成、双方未完成。四格之和等于本族注册案例数；这是计数验证，不是新的评价。", "",
        "| 对照方法 | 双方完成 | 仅 F04 完成 | 仅对照完成 | 双方未完成 |",
        "|---|---:|---:|---:|---:|"]
    for row in matrix:
        if row["evaluator_version"] == "v3":
            lines.append(f"| {row['reference_method']} | {row['both_completed']} | {row['F04_only_completed']} | {row['reference_only_completed']} | {row['neither_completed']} |")
    lines += ["", "[F04_PAIR_VALIDATION.csv](F04_PAIR_VALIDATION.csv) 保存两方原值、原 run_id/JSON pointer 和 `F04−对照` 的 Decimal 减法，仅双方 COMPLETED 且该指标有限时给差值；非共同完成的行仍保留。汇总验证见 [F04_PAIR_SUMMARY_VALIDATION.csv](F04_PAIR_SUMMARY_VALIDATION.csv)，负差为较小误差；它不替代失败四格。", ""]
    ps = {(r["evaluator_version"], r["reference_method"], r["metric"]): r for r in pair_summary}
    for ref in ("F03", "A04"):
        h = ps["v3", ref, "horizontal_rmse_m"]; y = ps["v3", ref, "yaw_rmse_deg"]
        lines.append(f"在与 {ref} 的共同有限集上，F04 水平差均值为 {h['validation_mean_delta']} m（n={h['joint_finite_count']}，较小/持平/较大={h['win_count']}/{h['tie_count']}/{h['loss_count']}）；yaw 差均值为 {y['validation_mean_delta']} deg（n={y['joint_finite_count']}）。这些是对已存运行指标做的验证算术，不是新增 evaluator 输出或因果机制结论。")
    lines += ["", "原有 7 种配对的逐案例与 family 置信区间在 [ORIGINAL_PAIRWISE_CASES.csv](ORIGINAL_PAIRWISE_CASES.csv)、[ORIGINAL_PAIRWISE_SUMMARY.csv](ORIGINAL_PAIRWISE_SUMMARY.csv)。对应的原差值验证单列在 EXISTING_PAIR_DELTA_CHECK.csv；本项未重算 bootstrap/CI。F04 对 F01/F02/A08/A09 的新浏览差值不冒称为原报告已有推断。", "",
        "## 各类型与尾部", "",
        "| 类型 | F04 v3 完成/注册 | H mean(m) | Yaw mean(deg) |",
        "|---|---:|---:|---:|"]
    tl = {(r["evaluator_version"], r["degradation_id"], r["method_id"], r["metric"]): r for r in types}
    for deg in ids:
        h = tl["v3", deg, "F04", "horizontal_rmse_m"]; y = tl["v3", deg, "F04", "yaw_rmse_deg"]
        lines.append(f"| {deg} | {h['finite_count']}/{h['registered_count']} | {h['mean']} | {y['mean']} |")
    finite_h = [(deg, numeric(tl["v3", deg, "F04", "horizontal_rmse_m"]["mean"])) for deg in ids]
    finite_h = [(d, v) for d, v in finite_h if v is not None]
    if finite_h:
        low, high = min(finite_h, key=lambda x: x[1]), max(finite_h, key=lambda x: x[1])
        lines += ["", f"F04 水平跨例均值在本族类型间范围由 {low[0]} 的 {low[1]} m 到 {high[0]} 的 {high[1]} m。各类型注入对象/参数及有限集不同，这个排序不能单独解释为某种故障越强就必然更差。"]
    lines += ["", "尾部规则在读取前固定为：每评价版本×每方法×每指标，对 COMPLETED 且有限的运行按值降序、case_id/run_id 升序打破并列，取前 3 个；所有 11 方法和 7 指标同规则，全部条目在 [WORST_TOP3.csv](WORST_TOP3.csv)。失败无有限指标，留在失败表，不从尾部表反推出失败排序。", "",
        "下面仅展示同规则抽出的 F04 水平前三例用于导航；其他方法/指标全部在同一尾部表，不能把本段视为全体尾部结果。", "",
        "| case | run_id | H RMSE(m) | 原始源键 |", "|---|---|---:|---|"]
    for row in tails:
        if row["evaluator_version"] == "v3" and row["method_id"] == "F04" and row["metric"] == "horizontal_rmse_m":
            display_key = row["source_row_key"].replace("|", "\\|")
            lines.append(f"| {row['case_id']} | {row['run_id']} | {row['source_value']} | {display_key} |")
    mismatch = sum(r["validation_status"] == "MISMATCH" for r in checks)
    lines += ["", f"原 family/type summary 的计数及 mean/median/P95/max/worst5% 共 {len(checks)} 个单元格进行了已有指标算术验证，差异 {mismatch} 项，详见 [SUMMARY_CHECKS.csv](SUMMARY_CHECKS.csv)。容差 abs/rel 均为 1e-10；未用新值覆盖 original 字段。", "",
        "## 时间支持与尚未完成项", "",
        "评价合同窗为 BY2 [66,340] s，逐运行实际 time_start/time_end、output/matched/reference 点数及 coverage 原值在 ORIGINAL_RUN_VALUES.csv。coverage=matched/output 只说已有输出匹配率，不证明窗完整、连续、同历元支持或独立样本。此处对比运行级原数，没有施加共同历元网格，也没有从全窗指标推断故障段/恢复段结果。", "",
        "时序证据：`PENDING_ROOT_SERIES_CHECK`。本 worker 未读取 error_series gzip 正文；根代理须在处理到本族时链接唯一 scanner 的同组检查回执。不存在的 NAV/STD 不重建；不能以本项逐案例算术验证代替逐历元核对、求解重现或数学审查。", "",
        "数据与参考边界：Fixposition 商业融合 reference 不是独立真值；重复使用 BY2 原始轨迹和注入种子不构成独立真实场景样本。既有 bootstrap 的条件性和模块/参考相关性边界见 [方法与指标说明书](../../METRIC_AND_METHOD_GUIDE.md)。"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots-local", type=Path, default=REPO / "configs/paper_rebuild/V3_RESULTS_ROOTS.local.json")
    parser.add_argument("--family", choices=FAMILIES, required=True,
                        help="One explicitly released family; no automatic all-family continuation")
    args = parser.parse_args()
    global ALIASES
    ALIASES = json.loads(args.roots_local.read_text())["aliases"]
    if Path(ALIASES["<CODE_ROOT>"]).resolve() != REPO:
        raise ValueError("Configured code root differs from script worktree")
    DEST.mkdir(parents=True, exist_ok=True)
    inputs = resolve("<RESULTS_ROOT>")
    spec = definitions(read_text(REPO / "configs/paper_rebuild/degradation_60types_9seeds.yaml", "original_spec"))
    read_text(REPO / "docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md", "v3_preregistration")
    read_text(REPO / "docs/paper_rebuild/v3/HEADING_FAULT_WINDOWS.md", "frozen_window_ledger")
    native = {r["run_id"]: r for r in read_csv(inputs / "V3_RUN_RESULT_INDEX.csv", "previous_complete_native_eval_join") if r["domain"] == "CORE"}
    values = []
    for version in ("v3", "v2"):
        for method in METHODS:
            p = inputs / "run_statistics" / f"EVALUATION_CORE_{version}_{method}.csv"
            source = read_csv(p)
            if len(source) != 541:
                raise ValueError("Each CORE method/version must retain 541 rows")
            for row in source:
                if row["method_id"] != method or row["domain"] != "CORE" or row["evaluator_contract"] != "evaluator_contract_" + version:
                    raise ValueError("Actual identity disagrees with file partition")
                run = native[row["run_id"]]
                if (run["case_id"], run["method_id"]) != (row["case_id"], method):
                    raise ValueError("Native/evaluation run key disagreement")
                keys = ("run_id", "case_id", "case_family", "degradation_type_id", "seed_index", "method_id", "effective_profile", "data_mode", "synthetic_data_used", "semisynthetic_data_used", "evaluation_status", "failure_classification", "metrics_admitted", "evaluation_invoked", "output_epoch_count", "matched_epoch_count", "reference_epoch_count", "time_start", "time_end", "coverage_ratio", "sequence_window_start_s", "sequence_window_end_s", "source_path", "source_row_key", "source_json_pointer")
                item = {k: row.get(k, "__FIELD_ABSENT__") for k in keys}
                item.update(evaluator_version=version, native_status=run["native_status"],
                            native_failure_classification=run["native_failure_classification"],
                            native_source_path=run["native_ledger_source"], native_source_row_key=row["run_id"],
                            read_source_path=row["_read_path"], read_source_data_row=row["_read_data_row"])
                item.update({m: row.get(m, "__FIELD_ABSENT__") for m in METRICS})
                values.append(item)
    keyed = {(r["evaluator_version"], r["case_id"], r["method_id"]): r for r in values}
    if len(keyed) != 11902 or len(native) != 5951:
        raise ValueError("CORE unique identity denominator mismatch")
    tables = {}
    for version in ("v3", "v2"):
        for name in ("CORE_541_SUMMARY", "CORE_541_FAMILY_SUMMARY", "CORE_541_TYPE_SUMMARY", "PAIRWISE_CASE_LEVEL", "PAIRWISE_SUMMARY"):
            tables[version, name] = read_csv(inputs / "source_tables" / f"{name}_{version.upper()}.csv")
    registry_path = resolve("<V3_ROOT>/00_CONTROL/ORIGINAL_V3_METADATA/00_PREREGISTRATION/REGISTRY.json")
    registry = json.loads(read_text(registry_path, "frozen_registry_metadata"))
    selected = (args.family,)
    casespec = {}
    for i, row in enumerate(registry):
        if row["domain"] != "CORE" or row["case_family"] not in selected:
            continue
        case = row["case_id"]
        if case in casespec and casespec[case][0]["frozen_bundle"] != row["frozen_bundle"]:
            raise ValueError("Conflicting bundle pins within a physical case")
        casespec.setdefault(case, (row, i))
    del registry
    receipts = []
    for family in selected:
        out = DEST / family
        out.mkdir(exist_ok=True)
        vals = [r for r in values if r["case_family"] == family]
        cases = sorted({r["case_id"] for r in vals})
        ids = {r["degradation_type_id"] for r in vals}
        source_summary, source_types, original_pairs, original_pair_summary = [], [], [], []
        summary_checks, pair_checks = [], []
        for version in ("v3", "v2"):
            fs = [r for r in tables[version, "CORE_541_FAMILY_SUMMARY"] if r["case_family"] == family]
            ts = [r for r in tables[version, "CORE_541_TYPE_SUMMARY"] if r["degradation_id"] in ids]
            source_summary.extend(original_row(r, version) for r in fs)
            source_types.extend(original_row(r, version) for r in ts)
            group = [r for r in vals if r["evaluator_version"] == version]
            summary_checks += validate_summary(fs, group, version, "family") + validate_summary(ts, group, version, "type")
            for row in tables[version, "PAIRWISE_CASE_LEVEL"]:
                if row["case_family"] != family:
                    continue
                original_pairs.append(original_row(row, version))
                candidate, ref = PAIRS[row["comparison"]]
                ca, re = keyed[version, row["case_id"], candidate], keyed[version, row["case_id"], ref]
                metric = row["metric_name"]
                difference = str(Decimal(ca[metric]) - Decimal(re[metric]))
                pair_checks.append(dict(evaluator_version=version, comparison=row["comparison"], case_id=row["case_id"], metric=metric,
                    source_path=row["_source_path"], source_row_key=row["_source_row_key"], source_column="delta_candidate_minus_reference",
                    source_value=row["delta_candidate_minus_reference"], validation_decimal_delta=difference,
                    candidate_run_id=ca["run_id"], reference_run_id=re["run_id"],
                    source_candidate_value=row["candidate_value"], source_reference_value=row["reference_value"],
                    candidate_original_value=ca[metric], reference_original_value=re[metric],
                    validation_status="MATCH_WITHIN_TOLERANCE" if same_numeric(difference, row["delta_candidate_minus_reference"]) and same_numeric(ca[metric], row["candidate_value"]) and same_numeric(re[metric], row["reference_value"]) else "MISMATCH",
                    calculation_type="VALIDATION_EXISTING_PAIR_DELTA"))
            original_pair_summary.extend(original_row(r, version) for r in tables[version, "PAIRWISE_SUMMARY"] if r["scope"] == "family" and r["family"] == family)
        injection, components = [], []
        for case in cases:
            reg, pointer = casespec[case]
            pin = reg["frozen_bundle"]
            bundle = json.loads(read_text(resolve(pin["path"]), "existing_provider_bundle_metadata_only"))
            meta = bundle["case_meta"]
            if bundle["case_id"] != case or meta["case_id"] != case:
                raise ValueError("Bundle case identity mismatch")
            inj = dict(case_id=case, degradation_id=reg["degradation_type_id"], family=family,
                source_path=alias(pin["path"]), source_row_key="/case_meta", source_column="case_meta;components;semantics",
                recorded_sha256=pin["sha256"], newly_verified_sha256="", read_depth="FULL_PAYLOAD_READ",
                registry_source_path=alias(str(registry_path)), registry_json_pointer=f"/{pointer}",
                V3_data_mode=reg["data_mode"], V3_semisynthetic_data_used=reg["semisynthetic_data_used"],
                bundle_protocol_id=bundle.get("protocol_id"), bundle_data_mode=bundle.get("data_mode"),
                bundle_semisynthetic_data_used=bundle.get("semisynthetic_data_used"),
                historical_case_meta_data_mode=meta.get("data_mode"), historical_case_meta_semisynthetic_data_used=meta.get("semisynthetic_data_used"),
                seed_index=meta["seed_index"], seed_value=meta["seed_value"], anchor_name=meta.get("anchor_name"), anchor_time_s=meta["anchor_time_s"],
                duration_s=meta.get("duration_s"), affected_sources=meta.get("affected_sources"), unaffected_sources=meta.get("unaffected_sources"),
                degradation_parameters_json=meta["degradation_parameters_json"], semantics_json=bundle["semantics"],
                components_json=bundle["components"], semantic_equivalence_json=bundle.get("semantic_equivalence", {}),
                case_meta_original_json=meta, evaluation_window=reg["evaluation"]["window"],
                provider_payload_read=False, HV_policy="frozen_case_HV_status_heading_rotation_reused")
            injection.append(inj)
            for k, component in enumerate(bundle["components"]):
                components.append(dict(case_id=case, degradation_id=reg["degradation_type_id"], seed_index=meta["seed_index"],
                    source_path=alias(pin["path"]), source_row_key=f"/components/{k}", source_column="component;affected_source;affected_epoch_count;details;status", **component))
        status_groups = defaultdict(list)
        for row in vals:
            status_groups[tuple(row[k] for k in ("evaluator_version", "method_id", "native_status", "evaluation_status", "failure_classification"))].append(row)
        statuses = [dict(zip(("evaluator_version", "method_id", "native_status", "evaluation_status", "failure_classification"), key),
                         validation_count=len(group), source_path=group[0]["source_path"], source_row_keys=[r["source_row_key"] for r in group],
                         native_source_path=group[0]["native_source_path"], native_run_ids=[r["run_id"] for r in group], calculation_type="VALIDATION_COUNT_ORIGINAL_STATUSES")
                    for key, group in sorted(status_groups.items())]
        failures = [r for r in vals if not complete(r) or r["native_status"] != "COMPLETED"]
        matrix, pair_values, pair_summary = [], [], []
        for version in ("v3", "v2"):
            for ref in METHODS:
                if ref == "F04":
                    continue
                counts = Counter(); metric_deltas = defaultdict(list)
                for case in cases:
                    a, b = keyed[version, case, "F04"], keyed[version, case, ref]
                    counts[complete(a), complete(b)] += 1
                    p = dict(evaluator_version=version, case_id=case, reference_method=ref, F04_run_id=a["run_id"], reference_run_id=b["run_id"],
                        F04_evaluation_status=a["evaluation_status"], reference_evaluation_status=b["evaluation_status"],
                        F04_source_path=a["source_path"], F04_source_row_key=a["source_row_key"], F04_source_json_pointer=a["source_json_pointer"],
                        reference_source_path=b["source_path"], reference_source_row_key=b["source_row_key"], reference_source_json_pointer=b["source_json_pointer"],
                        calculation_type="VALIDATION_DECIMAL_SUBTRACTION_ON_ORIGINAL_RUN_VALUES")
                    for m in METRICS:
                        ok = complete(a) and complete(b) and numeric(a[m]) is not None and numeric(b[m]) is not None
                        d = str(Decimal(a[m]) - Decimal(b[m])) if ok else "UNAVAILABLE_NONJOINT_FINITE"
                        p["F04_"+m], p["reference_"+m], p["validation_delta_"+m] = a[m], b[m], d
                        if ok:
                            metric_deltas[m].append(float(d))
                    pair_values.append(p)
                matrix.append(dict(evaluator_version=version, candidate_method="F04", reference_method=ref, registered_case_count=len(cases),
                    both_completed=counts[True, True], F04_only_completed=counts[True, False], reference_only_completed=counts[False, True], neither_completed=counts[False, False],
                    source_path="ORIGINAL_RUN_VALUES.csv", source_row_key=f"version={version};methods=F04|{ref};case_ids=all_family_cases", source_column="evaluation_status",
                    calculation_type="VALIDATION_COMPLETION_2X2_COUNTS"))
                for m in METRICS:
                    a = np.asarray(metric_deltas[m], dtype=float)
                    pair_summary.append(dict(evaluator_version=version, candidate_method="F04", reference_method=ref, metric=m,
                        joint_finite_count=len(a), validation_mean_delta=float(a.mean()) if len(a) else "UNAVAILABLE", validation_median_delta=float(np.median(a)) if len(a) else "UNAVAILABLE",
                        win_count=int(np.sum(a < -1e-12)), tie_count=int(np.sum(np.abs(a) <= 1e-12)), loss_count=int(np.sum(a > 1e-12)),
                        source_path="F04_PAIR_VALIDATION.csv", source_row_key=f"version={version};reference={ref};all_family_cases", source_column="validation_delta_"+m,
                        calculation_type="VALIDATION_PAIRED_RUN_METRIC_ARITHMETIC", new_bootstrap=False, new_CI=False))
        tails = []
        for version in ("v3", "v2"):
            for method in METHODS:
                group = [r for r in vals if r["evaluator_version"] == version and r["method_id"] == method and complete(r)]
                for metric in METRICS:
                    finite = [r for r in group if numeric(r[metric]) is not None]
                    for rank, row in enumerate(sorted(finite, key=lambda r: (-float(r[metric]), r["case_id"], r["run_id"]))[:3], 1):
                        tails.append(dict(evaluator_version=version, method_id=method, metric=metric, rank=rank, case_id=row["case_id"], run_id=row["run_id"],
                            source_path=row["source_path"], source_row_key=row["source_row_key"], source_json_pointer=row["source_json_pointer"], source_column=metric,
                            source_value=row[metric], selection_rule="descending_original_metric;case_id_then_run_id_ascending;top3_each_method_each_metric_each_version", finite_count=len(finite)))
        outputs = {"ORIGINAL_RUN_VALUES.csv": vals, "ORIGINAL_DISTRIBUTIONS.csv": source_summary,
            "ORIGINAL_TYPE_DISTRIBUTIONS.csv": source_types, "ORIGINAL_PAIRWISE_CASES.csv": original_pairs,
            "ORIGINAL_PAIRWISE_SUMMARY.csv": original_pair_summary, "EXISTING_PAIR_DELTA_CHECK.csv": pair_checks,
            "SUMMARY_CHECKS.csv": summary_checks, "INJECTION_CASES.csv": injection, "INJECTION_COMPONENTS.csv": components,
            "TYPE_DEFINITIONS.csv": [r for r in spec if r["family"] == family], "STATUS_COUNTS.csv": statuses,
            "FAILURES.csv": failures, "F04_COMPLETION_2X2.csv": matrix, "F04_PAIR_VALIDATION.csv": pair_values,
            "F04_PAIR_SUMMARY_VALIDATION.csv": pair_summary, "WORST_TOP3.csv": tails}
        for name, data in outputs.items():
            dump_csv(out / name, data, tuple(vals[0]) if name == "FAILURES.csv" else ())
        report = family_report(family, vals, source_summary, source_types, original_pairs, matrix, pair_summary, tails, failures, injection, spec, summary_checks)
        (out / "README.md").write_text(report, encoding="utf-8")
        receipt = dict(family=family, case_count=len(cases), unique_native_count=len(cases)*11, evaluation_slots=len(vals),
                       original_distribution_rows=len(source_summary), original_type_distribution_rows=len(source_types),
                       original_pair_case_rows=len(original_pairs), bundle_metadata_files_read=len(injection),
                       summary_check_cells=len(summary_checks), summary_mismatch_cells=sum(r["validation_status"] == "MISMATCH" for r in summary_checks),
                       original_pair_difference_checks=len(pair_checks), original_pair_difference_mismatches=sum(r["validation_status"] == "MISMATCH" for r in pair_checks),
                       output_row_counts={k: len(v) for k, v in outputs.items()}, series_evidence="PENDING_ROOT_SERIES_CHECK", data_mode="semisynthetic",
                       synthetic_data_used=False, semisynthetic_data_used=True, scientific_process_calls=0, provider_payload_reads=0, error_series_body_reads=0, raw_reference_reads=0, bootstrap_calls=0)
        dump_json(out / "READ_AND_VALIDATION_RECEIPT.json", receipt)
        receipts.append(receipt)
        print("READY", family, json.dumps(receipt, separators=(",", ":")), flush=True)
    read_index = DEST / "INPUTS_READ.csv"
    prior_reads = list(csv.DictReader(read_index.open(encoding="utf-8"))) if read_index.is_file() else []
    merged_reads = {row["source_path"]: row for row in prior_reads}
    merged_reads.update({row["source_path"]: row for row in READS})
    dump_csv(read_index, list(merged_reads.values()))
    dump_csv(DEST / "DEGRADATION_DEFINITIONS.csv", spec)
    dump_csv(DEST / "ORIGINAL_CORE_541_SUMMARIES.csv", [original_row(r, v) for v in ("v3", "v2") for r in tables[v, "CORE_541_SUMMARY"]])
    prior_receipts_path = DEST / "FAMILY_RECEIPTS.csv"
    prior_receipts = list(csv.DictReader(prior_receipts_path.open(encoding="utf-8"))) if prior_receipts_path.is_file() else []
    merged_receipts = {row["family"]: row for row in prior_receipts}
    merged_receipts.update({row["family"]: row for row in receipts})
    dump_csv(prior_receipts_path, [merged_receipts[f] for f in FAMILIES if f in merged_receipts])
    dump_csv(DEST / "FIELD_MAP.csv", [dict(output_column=m, source_column=m, source_path="<V3_ROOT>/FINAL_EVALUATION_RECORDS.json", source_json_pointer_rule="ORIGINAL_RUN_VALUES.source_json_pointer + '/' + source_column", numeric_values="original CSV strings unchanged;__FIELD_ABSENT__ remains missing", unit="deg" if m.endswith("deg") else "m") for m in METRICS])
    overview = """# CORE 阅读入口与分母

已全文读取 22 份 EVALUATION_CORE_{v3,v2}_{11方法}.csv，共 11902 评价槽，按真实 case/method/run_id 关联 5951 个唯一 native。每方法为 541 个案例：1 个 C00 + 60 类型×9 seed=540 个退化案例。C00 的 11 个物理运行就是自然 BY2 结果的复用入口，不再增计 native。F03/A02、F04/A01 为别名。

SUBSET61 是 C00 + D01–D60 的 seed_00，共 61 案例；它是 541 的子集，不是另外 61 次独立实验，也不能代表九种子完整总体。自然 C00 是 real_clean；540 注入案例为 semisynthetic。共享 BY2 原始轨迹、故障实例和模块配置不等于独立真实场景样本。

按 gnss_outage → gnss_sampling → position_value → position_std_status → dual_yaw → velocity_raw_doppler → go2_prior_metadata → multi_source_mixed 阅读各目录 README.md。每族含全部 11 方法、7 原指标、v3/v2 两版；FAILURES.csv 保留全部非完成槽，2×2 和配对差只是明确标为 VALIDATION 的计数/已有指标算术。

ORIGINAL_CORE_541_SUMMARIES.csv 是原整体 summary 转录；各族原分布与各类型原分布在其目录。不能把族均值无权平均冒充 CORE 均值，也不能把各自有限集均值差当成共同有限集配对差。新浏览视图不重做 bootstrap/CI，不从 error_series 或 NAV 重算本项统计。

INPUTS_READ.csv 记录全文读取到 EOF 的统计、合同和小型 bundle 元数据，不声称读取了其 provider payload。source_path/source_row_key/source_json_pointer 指回原记录，read_source_path/read_source_data_row 指回上一轮便携完整统计；同名原指标列保持原字符串。FIELD_MAP.csv 给出列/单位映射。各 README 中人工选出的导航值之外，全部原数保存在 CSV。

各族时序状态以其 README 和 series_checks/CORE_<family>/RECEIPT.json 为准；未完成的族保留 PENDING_ROOT_SERIES_CHECK，根代理在交付该小项时补唯一 scanner 的同组检查。coverage=matched/output 不证明连续、完整支持或独立参考样本。reference 是商用融合参考而非独立真值；本入口不宣布数学或因果机制审核通过。
"""
    # The root agent owns subsequent group/series status amendments to this entry.
    # A later family release must preserve an already published overview verbatim.
    overview_path = DEST / "CORE_OVERVIEW.md"
    if not overview_path.exists():
        overview_path.write_text(overview, encoding="utf-8")
    print("DONE", json.dumps({"families": len(receipts), "read_files": len(READS), "full_core_eval_rows": len(values), "summary_mismatches": sum(r["summary_mismatch_cells"] for r in receipts)}), flush=True)


if __name__ == "__main__":
    main()
