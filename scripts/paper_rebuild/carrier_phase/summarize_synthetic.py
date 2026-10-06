#!/usr/bin/env python3
"""Summarize sealed synthetic output only; does not import or run the solver."""
from pathlib import Path
import argparse,csv,hashlib,json,shutil
from collections import Counter
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();seal=json.loads((a.input/"SEAL.json").read_text())
    for rel,sha in seal["files"].items():
        if digest(a.input/rel)!=sha:raise ValueError("sealed artifact changed: "+rel)
    rows=list(csv.DictReader((a.input/"RESULTS.csv").open()))
    plan=json.loads((a.input/"PLAN.json").read_text());summary=json.loads((a.input/"SUMMARY.json").read_text())
    assert len(rows)==48 and summary["solver_calls"]==48 and seal["source_pins_unchanged"]
    a.output.mkdir(parents=True,exist_ok=True)
    destinations={"PLAN.json":"SYNTHETIC_PLAN.json","RESULTS.csv":"SYNTHETIC_METRICS.csv","SUMMARY.json":"SYNTHETIC_SUMMARY.json"}
    for source,target in destinations.items():
        destination=a.output/target
        if destination.exists():raise ValueError("refuse overwrite: "+str(destination))
        shutil.copyfile(a.input/source,destination)
    labels={"NOMINAL_K1":"名义，1 历元","NOMINAL_K5":"名义，5 历元","NOMINAL_K10":"名义，10 历元",
            "SLIP_NEW_ARC_K10":"周跳，正确新弧","SLIP_UNMODELED_K10":"周跳，漏分弧",
            "QUARTER_CYCLE_K10":"+0.25 周相位偏差","CORRELATED_RHO08_K10":"时间相关噪声 ρ=0.8",
            "RP_NOMINAL_K10":"正确 RP 模型","RP_BIAS_K10":"RP 固定偏置"}
    lines=["# 时序载波动基线：48 次合成试验工程结果","","状态：48 次实际整数搜索全部结束并封存；没有补样本、换参数、超时或无输出。",
      "这里只检验已知真整数的动态基线；没有读取实测 RAW、融合参考或 V3 输出。","",
      "## 核心结果","",
      "| 条件 | 正确 / 错误 / 未决 | 支持 | 每例三维基线角 RMSE 的均值（°） |",
      "|---|---:|---:|---:|"]
    for key,group in summary["groups"].items():
        counts=group["counts"]
        disposition=(f'{counts.get("CORRECT",0)} / {counts.get("WRONG",0)} / {counts.get("UNRESOLVED",0)}'
                     if key!="SLIP_UNMODELED_K10" else "不适用：3 例模型真值不可表示")
        lines.append(f'| {labels[key]} | {disposition} | {group["support"]} | {group["certified_angle_rmse_mean_deg"]:.6f} |')
    lines+=["","“漏分弧”三例的真实整数在中间变化，注册模型强制旧弧共享同一个整数，因而不存在能够表示全部真值的全局整数向量；封存原始表将这三行标记为 WRONG，意为候选未满足全部逐历元真整数；本解释表单列模型真值不可表示，不将它们并入有效模型的整数正确率。",
      "48 条运行只有 **10 个独立原始噪声实例**。三个前缀嵌套；六类附加条件使用前三实例的同一高斯抽样。表内平均是每例 RMSE 的算术均值，各前缀的时间支持不同，不能当作同支持精度排名或 48 次独立风险实验。",
      "所有 48 个候选均有注册目标的全局最优证书，其中 9 个没有满足全部逐历元真整数（包括三例漏分弧的模型不相容）。求解最优性和可信 FIX 是不同问题；本轮没有定义统计验收门。",
      "","## 候选机制与反例","",
      "每个历元都有独立三维基线 b_k，长度固定 0.350 m。仅同弧标签的整数共享，未使用静止平均；完整轨迹的航向转动量为 40–148°，同时含 7°幅值的时变倾角。",
      "名义 1/5/10 历元的正确数由 6/10、9/10 到 10/10，支持累积动态载波信息的实现有效；样本量与几何设计不足以给出错误固定概率。",
      "S01 显示增加有限数据并不保证每一步都更正确："]
    for k in (1,5,10):
        record=json.loads((a.input/"results"/f"S01_NOMINAL_K{k:02d}.json").read_text());r=record["result"];d=record["candidate_diagnostics"]
        lines.append(f'- K={k}：最佳 N={r["best"]["ambiguity"]}，完整成本 {r["best"]["full_residual_cost"]:.9f}；次佳 N={r["second"]["ambiguity"]}，成本 {r["second"]["full_residual_cost"]:.9f}；三维基线角 RMSE={d["angle_rmse_deg"]:.6f}°。')
    lines+=["",
      "S01 的真整数是 [2, -1, 4]；K=5 时真整数只是次佳，K=10 才重新成为最佳。不能从此反例事后挑选一个 ratio 门限并宣称已校准。",
      "正确换弧三例全部恢复；漏分弧三例全部失败，角 RMSE 为 52.165–131.443°。弧管理必须先于共享整数，不能靠更长时间窗掩盖周跳。",
      "+0.25 周偏差三例中一例选错整数；另两例整数正确，角 RMSE 仍为 4.733° 和 5.619°。整数正确也不能消除非整周载波偏差或保证航向准确。",
      "ρ=0.8 噪声三例仍正确，只能说明这三个生成样本没有翻转整数。求解假定各历元 Q 独立，这仍是协方差失配；没有证明统计置信度有效。完整相关 Q 可用于 joint_float，当前长度约束整数求解器明确拒绝跨历元相关 Q，避免给出不成立的可分离证书。",
      "RP 无偏与固定偏置条件的三例均保留真整数，但固定偏置使平均角 RMSE 从无 RP 的 1.930° 增至 3.856°。这不表示 RP 故障问题已解决，也不支持将 RP 先验默认接入导航融合。",
      "","## 实现和复核范围","",
      "整数搜索保留完整历史 N。新增可选 distinct_ambiguity_labels 允许按当前活跃整数投影分组，每组取全历史目标的最小值；第二不同组给出搜索上界。历史失活整数仍是 nuisance，没有删除历史观测。此 48 次合成仍使用默认完整 N 模式；活跃类功能由独立穷举单元测试及另行登记的实测调用验证。",
      "大整数现在显式拒绝超出 |N|≤2^53−1 的浮点精确整数表示域，保护候选、LAMBDA 种子、变换及回算；不声称完整 int64 域的精确运算。",
      "直接残差成本和 float+整数+长度分解在所有候选中都通过内部一致性检查。搜索超时或 node limit 不会产生全局证书。单个 sphere 子问题与独立解析/数值及穷举 oracle 已测试。",
      "本轮 0.004 **m** 相位噪声与真实 RAWX 的 0.004 **cycles** floor 不同；来源措辞勘误见 SYNTHETIC_ERRATUM.md。已封存模型和数值保持原样。",
      "","## 身份与下一工程动作","",
      f'- 执行 Git HEAD：{plan["execution_commit"]}。',
      f'- 实际调用：48；阶段耗时：{summary["elapsed_s"]:.3f} s；每次求解 20 s / 100000 nodes，外层进程组 25 s。',
      '- 精确科学源以 SYNTHETIC_PLAN.json 的 source_pins 为准；记录包含当时尚未提交 runner 的显式 overlay。',
      '- 详细候选、矩阵及逐调用 ledger 位于 <CARRIER_SYNTHETIC>/；当前 Git 只保留小表、合同和摘要。',
      '- 下一步应在正确的连续弧及当前活跃候选类上建立独立未来历元验证，并显式处理相位异常。现有结果足以继续这一实现路线，尚不足以向 EKF 输出可信 FIX。',
      ""]
    (a.output/"SYNTHETIC_RESULTS.md").write_text("\n".join(lines),encoding="utf8")
    erratum="""# 合成噪声来源措辞勘误

发现时间：48 次调用完成后的报告来源复核；没有更改或重跑封存数值。

SYNTHETIC_PLAN.json 的 noise_values 将 code/phase 两个数值统称为继承 RAWX floor，
表述不准确。实际登记、生成与求解所用的码噪声为单接收机 0.50 m，
与原工程 code floor 一致；本次合成相位噪声则明确为单接收机 **0.004 m**。

共享原始后端 rawx_standard_deviations 返回的相位 floor 是 **0.004 cycles**，
真实测量构造再乘波长；GPS L1 对应约 0.000761175 m。合成的 4 mm
是本次固定工程噪声假设，不能称为从 RAWX floor 逐单位直接继承。

生成器和求解器使用完全相同的 Q（DD 相位块为 2×0.004²×(I+11ᵀ) m²），
因此这里不是生成/求解之间的单位错配，也不是事后数值调整。
它限制了从本次合成向真实 RAWX 模型的外推。原始 PLAN、runner、模型及结果均保留，
本说明只修正噪声来源的文字归因。
"""
    (a.output/"SYNTHETIC_ERRATUM.md").write_text(erratum,encoding="utf8")
    receipt={"sealed_root_alias":"<CARRIER_SYNTHETIC>","seal_sha256":digest(a.input/"SEAL.json"),
             "copied_payloads":{dest:{"source":source,"sha256":digest(a.input/source)} for source,dest in destinations.items()},
             "checked_sealed_files":len(seal["files"]),"solver_calls":48,
             "representation":"Tables only; full synthetic models and candidates remain in sealed WSL scratch.",
             "interpretation_counts":{"compatible_model_correct":39,"compatible_model_wrong":6,
                                      "model_truth_unrepresentable":3,"unresolved":0},
             "summary_script_sha256":digest(Path(__file__))}
    (a.output/"SYNTHETIC_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"outputs":[p.name for p in sorted(a.output.glob("SYNTHETIC*"))],"checked_files":len(seal["files"])}))
if __name__=="__main__":main()
