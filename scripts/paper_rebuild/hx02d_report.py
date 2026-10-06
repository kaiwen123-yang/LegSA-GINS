#!/usr/bin/env python3
"""Render HX-02D report solely from completed diagnostic JSON records."""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def fmt(value, digits=3):
    return "不能判定" if value is None else f"{value:.{digits}f}"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(map(str, headers)) + " |", "|" + "---|" * len(headers)] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows]) + "\n"


def render(root, code_root):
    runroot = root / "EXECUTION_V2"
    data = {s: {"B": load(runroot / f"B_REFERENCE_FREE/{s}/OUTPUT/B_TABLES.json"),
                "C": load(runroot / f"C_REFERENCE/{s}/OUTPUT/C_TABLES.json")} for s in ["BY2", "BY2O"]}
    state = load(runroot / "B_SAVED_STATE_READOUT/B2_STATE_DECOMPOSITION.json")
    branches = [(s, label, data[s]["B"]["branches"][label]["evaluation_window"], data[s]["C"]["branches"][label])
                for s in data for label in ["HARTLEY_S", "HARTLEY_LIT"]]
    def name(s, label): return s + " " + label.replace("HARTLEY_", "")
    judgment = """**最可能的原因是 H3：本次生产移植及其运行配置中的接触更新／零偏估计路线。现有证据不能判定具体哪一行代码或哪一项数学公式有错，也不能把该结果推广为 Hartley 论文算法的精度结论。**

**H1 的支持与反对证据。** 历史 H7 的参考点及姿态框架门没有闭合，仍是解释边界，不能宣称所有坐标或物理点误差都已排除。但本次四支 roll/pitch 的原轴序、原符号均优于所列互换与取反假设；RMS 为 roll 0.692–3.127°、pitch 0.468–4.801°，没有接近 180° 的差。C2 的最佳水平 RMSE 改善仅 1.000–1.075 倍，yaw RMSE 没有改善，达不到十倍证据门。C3 斜率依次为 +0.960、−0.402、−8.132、−0.331，均不呈现简单 yaw 反向的 −2 模式；这些是描述性 OLS，不能仅凭斜率接近或远离某个数就作因果判定。所检查的轴序、东向镜像和单边 yaw 符号错误不支持作为主因。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.branches.<BRANCH>.evaluation_window.B1_raw_rpy、sequences.<SEQ>.C.branches.<BRANCH>.C2/C3；历史边界见 A1/A2。

**H2 的支持与反对证据。** 接触阈值处在日志低、高足力主群之间，但接触标签本身由足力阈值生成，不能独立证明物理支撑／摆动识别正确；接触延迟、滑动与 Go2 FK 代理的相关误差仍可能影响更新。另一方面，相同接触/FK 输入用 Go2 姿态旋转后，BY2/BY2O 纯腿轨迹的漂移斜率为 +0.069/−0.379 m/100 m，水平 RMSE 为 6.209/6.322 m，终点误差为 0.243/1.029 m/100 m；固定的足位置差分口径也给出 +0.107/−0.918 m/100 m、10.238/10.966 m。没有出现输入轨迹自身约 30% 的失效证据。零接触区间没有速度观测，主口径在这些区间不累加位移，评分窗口内未观测时间为 0.204/0.116 s。Go2 姿态来自机载估计器，这项检查是条件诊断，不能作为经证明的精度上限；负漂移斜率只表示误差范数随路程的回归下降。H2 单独足以解释全部异常的说法不受支持，但 H2 与滤波器观测模型／噪声配置的失配不能排除。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.B3、sequences.<SEQ>.C.C4、saved_state_readout.<SEQ>_leg_gap_window。

**H3 的支持与反对证据。** 在适配器和参考评估之前，Hartley 原生 yaw 已偏离原始 z 陀螺积分，OLS 速率为 +96.926、−35.347、−496.910、−15.960°/min。保存状态分解将其定位到零偏与接触更新：零偏项依次为 −56.324、−22.954、−185.172、−24.986°/min，直接接触旋转更新项为 +153.736、−12.289、−311.163、+8.892°/min；安装角及三维旋转项绝对值均小于 0.576°/min。各区间从保存状态独立计算，未运行滤波器。四支原生位置轨迹路程分别为参考的 6.419、2.096、10.478、3.350 倍，而两种姿态旋转的主口径腿轨迹约为 0.921–0.925 倍。反对把它直接定为公式错误的证据是：数学回归和结构验证曾通过，官方早期后端回归也通过；同时，噪声、接触质量、模型失配仍可使正确实现的更新不适用。官方早期后端的通过不能替代生产 IJRR 后端的真实精度验收。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.branches.<BRANCH>.evaluation_window.B2/B4、saved_state_readout.<SEQ>_<BRANCH>.components；后端差异见 A1。

**综合判定。** H1 的简单手性／yaw 符号解释未获支持；H2 的“输入只能给出约 30% 漂移”解释未获支持；最强直接证据落在生产滤波器的接触更新与零偏反馈路径，因此以 H3 为首要定位方向。接触切换相关性并非四支一致，不能进一步声称所有异常都发生在切换瞬间。准确缺陷是实现、噪声配置还是输入与更新模型的耦合，**不能判定**。

**下一步两个选项。**

1. 若后续独立坐标／物理点证据确立 H1，登记评估器或适配器修正，只重新评估既有原生输出，不重新解算。本次没有达到启用这一选项的证据门。
2. 按当前更支持 H2/H3 路线的证据，论文使用“未通过精度验证的移植、不作对比行”，将这些结果与诊断挪至补充材料。此次仅给出该建议，不修改论文、HX-02 结果或任何方法实现。
"""
    result = {"status": "DIAGNOSTIC_CALCULATIONS_COMPLETE_FINAL_INTEGRITY_PENDING", "sequences": data,
              "saved_state_readout": state, "judgment_zh": judgment,
              "source_conventions": {"B": "EXECUTION_V2/B_REFERENCE_FREE/<SEQ>/OUTPUT/B_TABLES.json",
                                     "C": "EXECUTION_V2/C_REFERENCE/<SEQ>/OUTPUT/C_TABLES.json",
                                     "state": "EXECUTION_V2/B_SAVED_STATE_READOUT/B2_STATE_DECOMPOSITION.json"},
              "counters": {"legsa_native_calls": 0, "external_native_calls": 0, "reference_evaluator_children": 2,
                           "reference_free_B_children": 3, "reference_free_B_successes": 2,
                           "reference_free_state_readout_children": 1, "diagnostic_subprocesses_total": 6,
                           "reference_open_count": 2, "controller_reference_opens": 0,
                           "B_reference_opens": 0, "bag_fpl_opens": 0},
              "serialization_failure": "Initial B child failed JSON serialization; original artifacts preserved; C had not started.",
              "starting_head": "e612eeb0ad37bf150a4076eb636424fe85f1d222", "report_notes_commit": "无需补提交"}
    # Preserve the already inspected A record, excluding its temporary stop/status sections.
    prior = (root / "PREREQUISITE_CHECK.md").read_text()
    a = prior[prior.index("## A1"):prior.index("## 尚未执行与计数")]
    a += "\n等价的显式报告变换为 `S_ENU_to_NED=[[0,1,0],[1,0,0],[0,0,-1]]`、`F_FLU_to_FRD=diag(1,-1,-1)`，\n`R_NED_FRD=S_ENU_to_NED * R_ENU_FLU * F_FLU_to_FRD`，`p_NED=S_ENU_to_NED*p_ENU`。\n两矩阵行列式均为 +1；这给出 `yaw_NED=wrap360(90-yaw_ENU)`，无需把 NAV 旋转矩阵转置。\n此处是 A2 源码公式的代数展开，不是新增数据拟合；HX-02 实际实现仍在 ENU 中计算位置误差，只将 yaw 残差转为 NED。\n"
    a += "\nH6R 的含偏置真实轨迹模型中，四接触的 rank/nullity 为 23/4，两接触为 17/4；在 0.1、1、10 倍秩阈值下稳定。\n出处：H/10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json:bias_augmented[*].contact_count,raw_rank,raw_nullity；\n同目录 OBSERVABILITY_RANK_SENSITIVITY_R1.csv:model=BIAS_AUGMENTED_REAL_TRAJECTORY 的 tolerance_multiplier,rank,nullity。\n这确认已知规范自由度，不能证明相对运动估计精度。H0–H2、H3–H4 的原记录采用联合终端，表中按原记录分组，不虚构逐编号的单独验收。\n"
    text = """# HX-02D Hartley 相对位姿只读诊断

本任务未运行任何原生解算，未修改方法本体、HX-02 输出或既有合约。最可能原因是生产移植／配置中的接触更新及零偏反馈路线（H3）；具体公式或代码缺陷不能判定。以下结论仅针对已保存的四个运行。

起点按用户裁定为 `e612eeb0ad37bf150a4076eb636424fe85f1d222`。HX02 docs 七个已有同名报告文件与源目录完全一致，主表 SHA256 为 `7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`，**无需补提交**。出处：00_CONTROL/REPORT_COPY_CHECK.json:pairs,table_sha256；历史起点阻断和裁定见 PREREQUISITE_CHECK.md。

## 数据与计算口径

- B 主表在各自 HX-02 评分窗口内取原生共同时间戳：BY2 为 [66,340] s，BY2O 为 [3186,3563] s；各支另有全原生窗口结果。出处：B_TABLES.json:sources.window、branches.<BRANCH>.full_native。
- C 沿用 HX-02 闭区间 10 Hz 网格、SO(3) 插值、参考插值和天线中点杆臂。C1 的 t=0 是评分窗口起点。位置误差为估计减参考；按 N/E/U 报告。yaw 为 NED 估计减参考，表内同时保留 wrap 到 [−180,180) 与连续展开两列。出处：C_TABLES.json:time_zero、branches.<BRANCH>.C1；计算代码 hx02d_reference_evaluation.py:evaluate,score。
- B2 以机体系 FLU／向上世界的正向 yaw 增量比较，因而其偏离速率的符号与 C 的 NED yaw 误差不同；展开后比较，不把多圈偏离折回。原始 z 轴陀螺积分不扣零偏，使用前一采样值的区间保持规则。另报安装角修正后的 z 积分和保存状态分解。
- B3 接触占空比主报按实际 dt 加权；JSON 另含逐样本比例。接触段时长只对完整段取中位数，窗口端点截断段另计。足力单位沿用原日志数值，不凭空改称牛顿。低／高足力群是代理，不能充当独立接触真值。
- B4 使用每个有效接触足 `v_b=−(ω×p+ṗ)` 并取多足平均；ω 为缓存已安装修正的角速度，p 为 foot_position_body，主 ṗ 为 foot_speed_body。另报非均匀时间轴二阶差分敏感性。状态速度以 Rᵀ 转回机体再比较。方向只在两种速度模长均大于 0.05 m/s 时定义；JSON 给出分母。积分是梯形积分，无接触区间不累加位移，并明确记录缺测，不宣称完整可观测。路程统一在 10 Hz 轨迹上计算，参考分母直接取旧 HX-02 数值。
- 漂移沿用 HX-02 的 OLS 斜率定义：水平误差范数对累计参考水平路程的带截距斜率乘 100。它不是终点百分比；C4 同时报告终点误差，避免闭环路程与负斜率造成误读。
- 数据定位：下文 B(s) 指 `EXECUTION_V2/B_REFERENCE_FREE/<s>/OUTPUT/B_TABLES.json`，C(s) 指 `EXECUTION_V2/C_REFERENCE/<s>/OUTPUT/C_TABLES.json`，D 指 `EXECUTION_V2/B_SAVED_STATE_READOUT/B2_STATE_DECOMPOSITION.json`。每张表标明对应字段；未四舍五入原值在 DIAGNOSTIC_TABLES.json。B 的来源及 SHA256 在 B(s):sources 和对应缓存清单，逐历元数组及原日志记录起始行在 B_ARRAYS.npz:source_start_line。
- 历史路径 H 指 `<CLEAN4>/07_LSE01_HARTLEY_CONTACT_INEKF`。原生率 NPZ 与初次失败数组保留在 G: 的 HX02D 阶段目录；仓库 docs 保留报告、JSON 表、抽样序列和全部 strace 审计。审计中的 scratch 绝对路径是执行时路径，归档时相对目录结构保持不变。

""" + a
    text += "\n## B1 姿态约定\n\n原始高层 rpy 比较；均值、RMS 和最大绝差单位均为度。来源：B(s):branches.<支>.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1。\n\n"
    text += table(["运行", "roll 均值", "pitch 均值", "roll RMS", "pitch RMS", "roll 最大绝差", "pitch 最大绝差", "最接近假设"],
                  [[name(s, k), *[fmt(b["B1_raw_rpy"]["hypotheses"]["identity_roll+1_pitch+1"][v]) for v in
                     ["roll_mean_deg", "pitch_mean_deg", "roll_rms_deg", "pitch_rms_deg", "roll_max_abs_deg", "pitch_max_abs_deg"]], "原轴序、原符号"] for s,k,b,c in branches])
    text += "\n为完整覆盖互换、单轴取反和双轴取反，列出全部八种有符号排列的联合 RMS。变换作用于 Go2 对照 rpy，不修改 NAV。来源：同上 hypotheses.<假设>.joint_rms_deg。每个假设的两轴均值/RMS/最大值均在 JSON。\n\n"
    hypotheses = list(branches[0][2]["B1_raw_rpy"]["hypotheses"])
    text += table(["假设"]+[name(s,k) for s,k,b,c in branches], [[h]+[fmt(b["B1_raw_rpy"]["hypotheses"][h]["joint_rms_deg"]) for s,k,b,c in branches] for h in hypotheses])
    text += "\n原轴序、原符号四支均最接近，没有 180° 或互换明显优于原样的证据。安装角调整对照另存 B1_installation_adjusted_rpy，不从两者之间按参考误差选择约定。\n"
    text += "\n## B2 yaw 来源分离\n\n每对差值先各减本窗口首值，RMS 单位 °，漂移率单位 °/min。来源：B(s):branches.<支>.evaluation_window.B2.<比较>.rms_difference_deg,drift_deg_per_min。\n\n"
    pairs = [("Hartley−原始 gyro-z", "hartley_minus_raw_gyro_z"), ("Hartley−Go2 yaw", "hartley_minus_go2"), ("Go2 yaw−原始 gyro-z", "go2_minus_raw_gyro_z")]
    text += table(["运行", "比较", "RMS", "OLS 漂移率"], [[name(s,k), title, fmt(b["B2"][p]["rms_difference_deg"]),fmt(b["B2"][p]["drift_deg_per_min"])] for s,k,b,c in branches for title,p in pairs])
    text += "\nAllan 记录的平均轴 gyro bias instability 为 4.550529e−5 rad/s，即 0.1564356638°/min；逐 z 轴值不可恢复。来源：configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml:bias_instability_diagnostics.gyro_bias_instability、provenance_limitations.exact_per_axis_values_available；转换值在 B(s):gyro_bias_instability_deg_per_min。它不是本次初始常值零偏的上限：Go2 yaw 与未扣偏的 z 积分也相差约 −4°/min，不能单靠超过此 Allan 数字就断言更新错误。\n"
    text += "\n接触事件对齐：epoch 相关是切换指示与瞬时偏离速率绝对值；1 s 相关是切换数量与累计绝对偏离。来源：B(s):branches.<支>.evaluation_window.B2.contact_switch_correlation。\n\n"
    keys = ["epoch_absolute_rate_pearson","one_second_signed_departure_vs_switch_count","one_second_total_absolute_departure_vs_switch_count","mean_abs_rate_at_switch_deg_per_s","mean_abs_rate_without_switch_deg_per_s"]
    text += table(["运行","epoch 绝对速率 r","1s 有符号 r","1s 绝对量 r","切换处绝对速率 °/s","非切换处绝对速率 °/s"],[[name(s,k)]+[fmt(b['B2']['contact_switch_correlation'][v]) for v in keys] for s,k,b,c in branches])
    text += "\n保存状态的独立逐区间恒等式将 native yaw 增量分为原始 z 积分、安装角与三维旋转、保存 gyro bias、接触旋转更新四项。每个区间从保存的 R_k 开始，不把计算结果递推至下一时刻，不调用滤波器。源代码执行顺序见 run_h5.cpp:430–443，更新改变 R 与 bias 见 backend.cpp:1197–1211。以下为各累计项对时间的 OLS 速率，单位 °/min；来源：D:<SEQ>_<BRANCH>.components.<项>.ols_rate_deg_per_min。\n\n"
    comps=["raw_sensor_z_integral","installation_and_3d_rotation","saved_gyro_bias_effect","contact_update_rotation_effect","actual_native_yaw_increment"]
    text += table(["运行","原始 z","安装/三维","零偏项","接触更新项","原生 yaw"],[[name(s,k)]+[fmt(state[s+'_'+k]['components'][v]['ols_rate_deg_per_min']) for v in comps] for s,k,b,c in branches])
    text += "\n恒等式残差逐区间通过检查；完整数值见 D:exact_increment_identity_max_abs_deg，1 s 分解及接触切换数量见同目录 *_B2_DECOMPOSITION_1S.csv。接触更新包括持续接触校正，不只发生在切换时刻，因此低切换相关性不能排除更新来源。\n"
    text += "\n## B3 接触与足力\n\nS/LIT 使用同一序列的同一缓存，以下每行同时适用于该序列两支，不重复计样本。来源：B(s):B3.evaluation_window.legs.<腿>。足力分位数为 P05/P50/P95。\n\n"
    legs=["FR","FL","RR","RL"]
    rows=[]
    for s in data:
        for leg in legs:
            v=data[s]['B']['B3']['evaluation_window']['legs'][leg]
            rows.append([s+' S/LIT',leg,fmt(v['duty_time_fraction']*100),fmt(v['switches_per_s']),fmt(v['complete_stance_median_s']),
                         f"{v['off_threshold']}/{v['on_threshold']}",'/'.join(fmt(x,0) for x in v['force_contact_quantiles']),
                         '/'.join(fmt(x,0) for x in v['force_noncontact_quantiles']),fmt(v['between_off_on_fraction']*100)])
    text+=table(['适用运行','腿','占空比 %','切换/s','完整接触段中位 s','off/on','接触足力 P05/50/95','非接触足力 P05/50/95','off–on 占比 %'],rows)
    text+='\n同时接触足数直方图，逐样本百分比；来源：B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction。按时间加权版本也在 JSON。\n\n'
    text+=table(['适用运行','0 足 %','1 足 %','2 足 %','3 足 %','4 足 %'],[[s+' S/LIT']+[fmt(data[s]['B']['B3']['evaluation_window']['simultaneous_contacts_sample_fraction'][str(j)]*100) for j in range(5)] for s in data])
    text+='\n足力直方图为样本计数，区间左闭右开（最末区间含右端）；来源：B(s):B3.evaluation_window.histogram_edges、legs.<腿>.force_histogram_counts。\n\n'
    headers=['运行','腿','<0','0–10','10–20','20–25','25–30','30–35','35–40','40–50','50–75','75–100','100–150','≥150']
    text+=table(headers,[[s+' S/LIT',leg]+data[s]['B']['B3']['evaluation_window']['legs'][leg]['force_histogram_counts'] for s in data for leg in legs])
    text+='\n阈值在低、高足力主群之间；两种接触类别的分布尾部重叠，且有三样本驻留规则，不能把条件分位数当成独立识别正确率。没有独立支撑／摆动标签，阈值是否准确识别真实接触仍为“不能判定”。\n'
    text+='\n## B4 腿里程计自洽\n\n速度差为模长 RMS；另列向量差 RMS。方向中位数使用已登记的 0.05 m/s 双侧门。来源：B(s):branches.<支>.evaluation_window.B4。\n\n'
    text+=table(['运行','模长差 RMS m/s','向量差 RMS m/s','方向中位 °','方向有效行','零接触行'],[[name(s,k),fmt(b['B4']['speed_magnitude_difference_rms_mps']),fmt(b['B4']['velocity_vector_difference_rms_mps']),fmt(b['B4']['direction_median_deg']),b['B4']['direction_rows'],b['B4']['unobserved_velocity_rows']] for s,k,b,c in branches])
    text+='\n三条主轨迹水平路程及相对旧参考路程的比值；来源：同字段 path_lengths_10hz_m、path_length_ratios_to_recorded_reference、recorded_reference_path_length_m。\n\n'
    text+=table(['运行','腿×Hartley 姿态 m /比值','腿×Go2 姿态 m /比值','Hartley 位置 m /比值','旧参考 m'],[[name(s,k)]+[fmt(b['B4']['path_lengths_10hz_m'][v])+' / '+fmt(b['B4']['path_length_ratios_to_recorded_reference'][v]) for v in ['leg_hartley','leg_go2','hartley']]+[fmt(b['B4']['recorded_reference_path_length_m'],9)] for s,k,b,c in branches])
    text+='\n有限差分足速度与日志 foot_speed_body 在接触足上的向量 RMS 差为 BY2 0.335 m/s、BY2O 0.275 m/s；差分腿轨迹路程为 285.577/292.805 m，分别是旧参考的 0.869/0.868。来源：B(s):branches.HARTLEY_S.evaluation_window.B4.foot_speed_vs_finite_difference_contact_rms_mps、path_lengths_10hz_m.leg_go2_fd、path_length_ratios_to_recorded_reference.leg_go2_fd；所以本报告保留两种口径而不把它们混同。\n'
    text+='\n## C1 冻结对齐后的误差\n\n对齐角使用原 JSON 的完整精度，平移不重新拟合。来源：C(s):branches.<支>.C1.frozen_alignment。\n\n'
    text+=table(['运行','绕 Z 对齐角 °','平移 E/N/U m'],[[name(s,k),fmt(c['C1']['frozen_alignment']['yaw_offset_deg'],9),'/'.join(fmt(v,9) for v in c['C1']['frozen_alignment']['translation_enu_m'])] for s,k,b,c in branches])
    text+='\n指定时刻误差；t 为评分窗口开始后秒数。来源：C(s):branches.<支>.C1.samples（elapsed_s 对应行），列 err_n_m/err_e_m/err_u_m/yaw_error_ned_wrapped_deg/yaw_error_ned_unwrapped_deg。完整 1 s 抽样见同目录 HARTLEY_*_C1_1S.csv。\n\n'
    text+=table(['运行','t s','N m','E m','U m','yaw wrap °','yaw 连续 °'],[[name(s,k),v['elapsed_s']]+[fmt(v[j]) for j in ['err_n_m','err_e_m','err_u_m','yaw_error_ned_wrapped_deg','yaw_error_ned_unwrapped_deg']] for s,k,b,c in branches for v in c['C1']['samples']])
    text+='\n旧 HX-02 的水平/yaw RMSE 与位置/yaw 漂移均在子进程内复现，容差为 1e−7；逐值差见 C(s):branches.<支>.C1.reproduction_check。此容差只检验诊断复现一致性，不用来判定方法精度。\n'
    text+='\n## C2 手性与符号\n\n变换定义在原始冻结对齐后的 ENU 天线中点轨迹：东向镜像仅将 E 取反，yaw 取反仅改 ENU yaw，然后对每种情况重新做相同初始 10 s 四自由度对齐。这样“东”有确定含义；不改变原生输出。来源：C(s):branches.<支>.C2.transforms.<变换>。\n\n'
    cn={'original':'原样','east_mirror':'东向镜像','yaw_negated':'yaw 取反','east_mirror_and_yaw_negated':'两者同时'}
    text+=table(['运行','变换','水平 RMSE m','yaw RMSE °'],[[name(s,k),cn[v],fmt(x['horizontal_rmse_m']),fmt(x['yaw_rmse_deg'])] for s,k,b,c in branches for v,x in c['C2']['transforms'].items()])
    text+='\n没有十倍改善。不能由这组有限变换排除所有时间、杆臂或物理点问题，但它不支持简单东向镜像／yaw 反号是主因。\n'
    text+='\n## C3 yaw 误差对参考转向回归\n\n主口径为连续 NED yaw 误差对连续 NED 参考 yaw 增量的带截距 OLS，使用全部评分网格。另列 wrap 残差敏感性，避免将两种残差口径混用。来源：C(s):branches.<支>.C3。\n\n'
    text+=table(['运行','连续误差斜率','R²','wrap 误差斜率','wrap R²'],[[name(s,k),fmt(c['C3']['unwrapped_error_vs_unwrapped_reference_turn']['slope']),fmt(c['C3']['unwrapped_error_vs_unwrapped_reference_turn']['r2']),fmt(c['C3']['wrapped_error_sensitivity']['slope']),fmt(c['C3']['wrapped_error_sensitivity']['r2'])] for s,k,b,c in branches])
    text+='\n没有预期的 −2 反向模式；LIT 的 −0.402/−0.331 是部分转向相关误差，不是估计完全不转。BY2O-S 的 −8.132 反映额外多圈运动与路径相关，不能解释为单纯反号。\n'
    text+='\n## C4 使用 Go2 姿态的输入层条件诊断\n\n沿用同一 10 s 对齐及天线中点评估点；同序列的 S/LIT 共用此输入检查。来源：C(s):C4.<口径>。\n\n'
    text+=table(['适用运行','足速度口径','位置漂移 m/100m','水平 RMSE m','终点水平误差 m','终点 m/100m','yaw RMSE °'],[[s+' S/LIT',v]+[fmt(x[k]) for k in ['position_drift_m_per_100m','horizontal_rmse_m','endpoint_horizontal_error_m','endpoint_error_m_per_100m','yaw_rmse_deg']] for s in data for v,x in data[s]['C']['C4'].items()])
    text+='\nGo2 姿态是机载姿态估计，不是独立真值；这不是数学上已证明的输入精度上限。零接触未观测时间在整个原生窗口为 0.204/1.276 s，在评分窗口为 0.204/0.116 s；来源：B(s):leg_integration_gaps 与 D:<SEQ>_leg_gap_window。C4 JSON 的 integration_gap_record 记录全原生窗口，不能误读成评分窗口缺测量。\n'
    text+='\n## 四个运行的独立汇总\n'
    for s,k,b,c in branches:
        a=b['B1_raw_rpy']['hypotheses']['identity_roll+1_pitch+1'];m=c['C1']['metrics'];leg=data[s]['C']['C4']['foot_speed_body']
        text+='\n### '+name(s,k)+'\n\n'
        text+=table(['项目','结果','原值字段'],[
            ['B1 roll/pitch RMS °',fmt(a['roll_rms_deg'])+' / '+fmt(a['pitch_rms_deg']),'B(s):branches.'+k+'.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1'],
            ['B2 Hartley−raw-z 速率 °/min',fmt(b['B2']['hartley_minus_raw_gyro_z']['drift_deg_per_min']),'B(s):branches.'+k+'.evaluation_window.B2.hartley_minus_raw_gyro_z'],
            ['B3 同时两足/四足 %',fmt(data[s]['B']['B3']['evaluation_window']['simultaneous_contacts_sample_fraction']['2']*100)+' / '+fmt(data[s]['B']['B3']['evaluation_window']['simultaneous_contacts_sample_fraction']['4']*100),'B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction'],
            ['B4 模长差 RMS /方向中位',fmt(b['B4']['speed_magnitude_difference_rms_mps'])+' m/s / '+fmt(b['B4']['direction_median_deg'])+'°','B(s):branches.'+k+'.evaluation_window.B4'],
            ['C1 水平/yaw RMSE',fmt(m['horizontal_rmse_m'])+' m / '+fmt(m['yaw_rmse_deg'])+'°','C(s):branches.'+k+'.C1.metrics'],
            ['原位置/yaw 漂移',fmt(m['position_drift_m_per_100m'])+' m/100m / '+fmt(m['heading_drift_deg_per_min'])+'°/min','C(s):branches.'+k+'.C1.metrics'],
            ['C2 最大水平改善倍数',fmt(c['C2']['max_horizontal_improvement_factor']),'C(s):branches.'+k+'.C2.max_horizontal_improvement_factor'],
            ['C3 斜率 /R²',fmt(c['C3']['unwrapped_error_vs_unwrapped_reference_turn']['slope'])+' / '+fmt(c['C3']['unwrapped_error_vs_unwrapped_reference_turn']['r2']),'C(s):branches.'+k+'.C3.unwrapped_error_vs_unwrapped_reference_turn'],
            ['C4 腿轨迹漂移 /水平 RMSE',fmt(leg['position_drift_m_per_100m'])+' m/100m / '+fmt(leg['horizontal_rmse_m'])+' m','C(s):C4.foot_speed_body']])
    text+='\n## 判定\n\n'+judgment
    text+='\n## 执行、审计与完整性\n\n'
    text+='原生解算 LegSA/外部为 0/0。参考评估子进程共 2 次（每序列一次，在同一内存中处理两支），每次 trace 只读打开 1 次并按同一份字节核验 SHA256；全部 C 计算只在该子进程内执行。来源：EXECUTION_V2/00_CONTROL/EXECUTION_COUNTERS.json、EXECUTION_V2/C_REFERENCE/{BY2,BY2O}/EVALUATOR_STRACE_AUDIT.json。\n\n'
    text+='B 主诊断子进程实际调用 3 次，其中第一次 BY2 因 NumPy int64 的 JSON 序列化错误失败，成功 2 次；另有无参考保存状态分解子进程 1 次。诊断子进程总计 6 次，失败前后未启动原生程序。失败的 B_ARRAYS.npz 和部分 JSON、stderr、strace 原样保留，续作只改变新诊断 JSON 编码，没有改变科学计算式。来源：00_CONTROL/SERIALIZATION_FAILURE_RECORD.json、00_CONTROL/CALLS.jsonl、EXECUTION_V2/00_CONTROL/CALLS.jsonl。\n\n'
    text+='控制进程参考打开 0，B 与保存状态分解参考打开 0，bag/fpl 打开 0；来源：00_CONTROL/CONTROLLER_AND_READOUT_AUDITS.json 与三份 B_STRACE_AUDIT.json。现有 hx02_evaluation_process.py 字节未改；诊断子进程只在当前控制进程的登记表里增加一个新项，源码 SHA256 在子进程启动前写入 DIAGNOSTIC_CHILD_REGISTRATION.json。原始失败登记与续作登记都保留。\n\n'
    text+='初次起点检查、暂停前、续作开始的封存核对均为 65/65、CSV 59/59 一致；记录分别为 00_CONTROL/SEALED_TABLES_START.json、SEALED_TABLES_PREREQUISITE_STOP.json、SEALED_TABLES_RESUME_START.json。提交前另做 SEALED_TABLES_PRECOMMIT.json；不会把先前检查冒称为提交前检查。\n\n'
    text+='新的诊断代数检查为 7 passed（包括序列化边界），没有原生解算或参考访问；源码 tests/paper_rebuild/test_hx02d_diagnostic.py。HX-02 全目录前后核对、方法字节与既有 29 个未跟踪文件保持、复制后逐文件 SHA256、scratch 清空与提交前封存状态见 FINAL_INTEGRITY.json。无交接包。\n'
    for forbidden in ['shared-source','同源','semisynthetic','pre-registered','preregistered','hash-locked']:
        assert forbidden not in text
    (root / 'HX02D_HARTLEY_DIAGNOSTIC.md').write_text(text,encoding='utf-8')
    (root / 'DIAGNOSTIC_TABLES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (root / 'JUDGMENT_ZH.md').write_text(judgment,encoding='utf-8')
    print('Rendered report and full tables from existing diagnostic records.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--code-root',type=Path,required=True)
    args=parser.parse_args()
    render(args.root,args.code_root)
