# 原 V3 正式基线身份锁

本锁服务于后续研究分支的 AR 比较，不改变 main、原 V3、原始数据或旧结果。
机器入口为 [V3_BASELINE_LOCK.json](V3_BASELINE_LOCK.json)。当前研究
PVT／scalar／body-HV 对照不是原论文 V3，不得替换原 V3 标签。

## 仓库与执行版本分开

本次只读 git ls-remote 确认远端 main 为
077fb725612730d743ff1dd3ba698c43499b4fcb。本地同名 main 仍为
9f9727b74f5195141523ab570380cc35006f3d18，不能作为当前远端 main 的副本。
main 已收录后来的诊断文档/实现；原 V3 的实际执行身份仍独立冻结：

| 身份 | 固定值 |
| --- | --- |
| 原科学冻结 | 7d43b9af26120ed5dde21f53e515386361072ba6 |
| 原二进制 SHA256 | 96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c |
| 原 evaluator SHA256 | aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da |
| 原注册表 SHA256 | c89813daff415f6afbc723e954555bd8256b9d7f5221e49d56a02948552c1222 |
| 原注册数量 | 6468 个 native 身份；不是本任务新执行数量 |

原二进制路径：
`<FROZEN_CODE_ROOT>`/build/p13_v21_cpp/legsa_v23_port_core_demo。
原 evaluator 路径：
`<CLEAN_ROOT>`/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py。
二者当前字节已核验。注册表位于 <V3_SCRATCH>/00_PREREGISTRATION/REGISTRY.json。
别名的机器路径只存在本机 scratch AR_V3_RESEARCH_20261006/LOCAL_PATHS.json，
不进入 Git；该文件不包含 raw 数据副本。

## 三个正式全窗

原始根为 `<RAW_ROOT>`/BY2_BY3/2026-03-06/。接收机目录在其下
fixption数据/2026.3.6/；下表的 by3 对应 BY2H、by1 对应 BY2O，不能按序列名称猜路径。

| 正式序列 | 接收机目录后缀 | body 文件 | 完整相对时间窗 (s) | Unix 基准 (s) | 原 F04 run |
| --- | --- | --- | --- | --- | --- |
| BY2 | by2/vrtk2_a87c6e_2026-03-06-08-00-54_minimal | 高层数据/by2.txt | [66, 340] | 1772784000 | RUN_00004 |
| BY2H | by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal | 高层数据/by3.txt | [413, 683] | 1772784000 | SEQUENCE_BY2H_F04 |
| BY2O | by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal | 高层数据/by1.txt | [3186, 3563] | 1772780400 | SEQUENCE_BY2O_F04 |

各接收机目录的 gnss1-raw.csv、gnss2-raw.csv、gnss1-status.csv 及对应 body
哈希由原注册表继承；本次仅核存在性及大小，没有再次读取这些 raw 载荷或 trace。
真实 AR 使用的 UBX/星历派生物仍须单独保留到这些原记录的因果、转换与哈希链。
本锁不把“同一天/同目录”自动视为已通过所有新派生物身份核查。

三份实际原配置：

- <V3_ROOT>/03_NATIVE/RUN_00004/V3_RUNTIME_CONFIG.yaml
- <V3_ROOT>/03_NATIVE/V3R_CONTINUATION/SEQUENCE_BY2H_F04/V3_RUNTIME_CONFIG.yaml
- <V3_ROOT>/03_NATIVE/V3R_CONTINUATION/SEQUENCE_BY2O_F04/V3_RUNTIME_CONFIG.yaml

配置当前哈希分别为
3ac059cbaf5cacbf68929ca6027074629ab4efc969b4e8a5ddbb2ca300f4c542、
47b91241f40453d4de1b3e6cafa7913f2892589e77178e9af3edb6209ee1b0c0、
15ac163dc99443955cd939047806b2fd74fb5ee421acad8f49403124a1138bcb，
均与 main 中原任务账本一致。全部 init 字段、原 IMU/GNSS/RD/RP/HV provider 路径别名及
哈希列在机器锁；15 个 provider 当前字节均核验，不进行再生成。
历史配置内部的 transport case_id/stage_id/outputpath 可继承旧阶段；
科学 run/case 身份以原注册表及任务账本为准。

原 V3 航向来自 HPPOSECEF 双接收机精确配对的 5 Hz 位置差，
方向为 GNSS2−GNSS1，要求双方 carrier FIX，固定 std 标记为 2.933193°。
这不是载波整数解算。原 HV 仍使用历史 status-A1 航向旋转，不能描述为当前
GNSS-independent body-HV，不能悄悄替换后仍复用原 V3 成绩。

## 物理点、评价与已有结果

原 runtime antlever=[.03,.03,-.30] m；初始位置、速度、姿态及其标准差严格保留配置值，
不根据新方法或参考重新对齐。主比较采用 evaluator_contract_v3：
仅将原 NAV 的位置列按估计姿态及
lever_frd=[.03,.03-baseline_median/2,-.30] 转换到声明评价点，
时间、速度和姿态不变，不拟合参考。三序列 baseline median 分别为
0.356191491865984、0.35418777593777223、0.35013463864843675 m。
这不是将本次 AR 的 0.35 m 模型长度自动代入旧评价合同。

STD 保持原值，没有协方差运输，不能声称完整 NEES 或已校准该点的误差界。
参考是共享 GNSS 来源的商业融合轨迹，不是独立真值。
原 evaluator 使用各序列 Unix 基准及 --yaw_truth_mode enu；
WGS84/ENU、插值、wrap 和声明物理点合同一起冻结，仅 executable 相同不足以保证可比。

原结果根为 <V3_ROOT>=`<CLEAN_ROOT>`/stages/CLEAN8_PROTOCOL_V3。对应上述三个 run，
结果保存在 04_EVALUATION/<同一 run 子路径>/v3/。
三份 EVALUATION_RESULT.json 与 FROZEN_EVALUATOR/error_series.csv.gz 当前字节
均与归档 receipt 一致，可复用已有标量与逐时误差，不重跑原 solver/evaluator。
原 full NAV/STD 已按历史策略释放，本锁仅记录它们的旧封存哈希，未假称当前完整载荷存在。
保留结果的最后匹配时间为 339.997056、682.99505、3562.997055 s，
不能写成精确等于合同右端点。原失败/未评价条目始终保留在完整账本。

## 退化注入层不能混淆

[原 V3 合同](../../../configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml)、
[原故障窗口](../v3/HEADING_FAULT_WINDOWS.md)及 provider source index 是 case/seed/窗口权威。
protocol_v3/providers.py::lift_heading 只覆盖 GNSS18 的 yaw/valid，
既有有符号角扰动按原一秒半开单元映射到 5 Hz，不是新的独立 5 Hz 随机采样。
clean6_addendum/providers.py::apply_outage 修改冻结 CAL provider 的有效状态，
不读取或改变 RAWX。D40 元数据没有活动标量测量通路；D41 仍是标量角扰动。

因此旧 D61/D62、航向丢失/偏差等结果不能充当原始载波周跳、半周错误或原始消息
中断的对照。如果新方法仍使用未受扰 RAWX，其收益只能解释为新增信息源抵抗
PVT/provider 产品失效。新 raw 故障可复用 V3 原记录和预定时间窗，但须新登记
物理信号层故障及比较身份，不能把旧 V3 退化成绩改名贴入。

## 最小后续复用合同

先复用原 V3 三全窗基线、provider、初始化、已有误差和评价合同，只运行新方法，
产物单独封存后再离线评估。改变观测模型、独立速度或初始化时必须显式登记为新方法，
不能称为原 V3 的同配置复现。研究阶段的 BY2 100–340 s 不能代替正式 66–340 s；
早段没有载波、冷启动、失败和不可用必须保留。对照汇总及共同支持交集必须分别报告，
不按成功输出裁剪全窗。研究分支审核通过后才允许合并 main。

## 本次核验范围与复核命令

本次生成锁执行 **176/176** 项检查，固定 **43** 个非 raw 文件身份。
包括远端 main、科学提交祖先关系、三配置/15 provider、原二进制/evaluator、
三组归档结果和压缩误差的身份，以及窗口、初始化和评价物理点语义。
raw 重哈希、reference 载荷读取、新 solver、新 evaluator 均为 **0**。
这不是全部6468载荷的重新审计，也不是 raw 重新完整校验。

Ubuntu WSL 内使用只读复核脚本；`<LOCAL_PATHS_JSON>` 指向本机别名映射：

~~~sh
python3 scripts/paper_rebuild/ar_v3_research_20261006/v3_lock_validate.py \
  --lock docs/paper_rebuild/AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json \
  --local-paths '<LOCAL_PATHS_JSON>'
~~~

脚本仅 hash 列明的非 raw 文件，并读取登记/配置/回执；raw 只 stat，
reference 不打开，不 import 或启动 solver/evaluator，也不写原文件。
后续远端 main 变化需要独立确认，本命令不自动更新本锁中的历史基准。

只读复核脚本已实际返回 **248/248 PASS**：43 个非 raw 文件 hash、12 个 raw 文件 stat；
原始载荷/参考读取及 solver/evaluator 调用仍为 0。这是额外的结构与身份复核，
不是独立审稿人验收或新科学实验；脚本 SHA256 与完成时间保存在机器锁中。
