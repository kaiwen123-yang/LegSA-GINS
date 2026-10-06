# 阶段 B：原冻结整数经剩余弧投影后的固定 N 诊断

状态：准备与小型合成 oracle 检查；真实数据执行须由 root 审查、Git 冻结后单独启动。本计划在观察阶段 A 支持审计后登记，不回称先于该结果。

## 问题与固定分母

检验阶段 A 的 516 个条件几何支持上界窗口，是否仍暴露残差、长度、相位故障或不可检测性缺口。保留全部原 1191 个窗口，不只跑 516。同步报告三个固定分层：全部 1191；原 exact-label 失败 535；其中阶段 A 条件支持上界 516。此为诊断，始终不输出 accepted/FIX/false-fix 风险。

输入全部沿用 ARC_SUPPORT_AUDIT_PLAN：<CARRIER_INTEGRATION>/DENSE_SELECTED_FRONTEND 的合同、SUMMARY_0001 和全部 cases；REAL_100_340_V2 的 PLAN、1200 原模型和 ARC_EVENTS；<TRUSTED_HEADING>/ARC_SUPPORT_AUDIT_ATTEMPT01 的 INPUT_IDENTITY、CASE_INPUT_PINS、RESULTS、SUMMARY。逐一核对阶段 A 保存的 SHA，不重开 raw、参考、NAV/STD 或误差序列。

case start=100+i/5，i=0..1190。固定前五个 selection 时键与后五个 future 时键，不平移窗口。原 frozen_candidates 的 primary/competitor 身份、selected_at、source_id、六个 active labels 和全部整数完全不变；校验与原 search best/second 及保存的 fingerprint 相符。只能把原选择结果作为条件假设；不重新优化、筛选或重排 N。

## 变换与诊断

1. 二支各自由原候选构造 FrozenIntegerGraph。每 future 槽先按两接收机原 arc token、eligible 和 temporal_link_qualified 不可逆退休失效节点；禁止重新出现的同卫星/同标签使旧节点复活。原分量之间不得新连边。
2. 调用 arc_projection.transport_epoch 重构当前观测，保留全部 code；剩余 phase 采用幸存旧关系的合法当前 DD 行差。必须检查两支有相同 U、labels、y/A/B/Q；只有条件 N 可以不同。不得根据 y/残差改变支持。
3. 物理相位故障矩阵由原 grouped epoch 建立，然后 F_new=U F_original。原物理 SD 信号、完整频率、arc token、单位 metres/cycle 保留；未知当前 pivot 可能得到严格零列，不能删去或称“已证明无故障”。phase 故障不覆盖 code-only bias。
4. 每支每槽做一次固定 N、自由三维基线 GLS，记录 S、df=n−3、bhat、Cb、已知行/未知整数；秩亏时协方差不可当完整估计，诊断为不足支持。记录最小长度球面代价 D，不改变观测或 N。
5. 五槽全部可构造且满秩时，再做一次联合固定 N GLS，保留独立的五个三维 baseline。Q 为原五槽 Q 的 block diagonal，明确这是未校准的时间独立工作假设。联合长度代价为各槽最小 D 之和，检查 S_joint 与逐槽 S 之和、长度和与直接 raw residual 恒等式。任何未知整数依赖行不许填零。
6. 逐槽和联合的物理 SD 单故障 GLRT 使用现有 alpha=.01、Holm 规则；联合列按 receiver/完整信号/显式 SD arc token 合并为“该弧上恒定 cycle bias”备择，不能跨新弧或跨频合并。报告 alias、不可观列和诊断 flags。
7. 使用既有 sensitivity 分析，family_alpha=.01、miss_probability=.05、observability_tolerance=1e-10。保留所有原物理列，包括投影后零列；报告 h、每历元自由 GLS baseline gain、MDB cycles 和 MDB 对应最大历元 baseline bias。不可检测列 MDB=null 且 unbounded=true。MDB 不是实际误差、sphere baseline 误差、heading protection 或整数正确性。

残差/长度采用原工作门：总 alpha=.01，S 与 D 各 .005；单槽 df 分别 n−3 和 3，五槽分别 sum(n_k−3) 和 15。这里仅输出 nominal diagnostic flags，不调用 CausalAdmissionSession、不生成测量。逐槽多重诊断以及重叠窗口总体未额外校准；不能把任意 flags 组合称统一 alpha 风险保证。GLRT “未拒绝”不等于故障可检测，也不等于正确 N。

## 候选集合和选择遗留

每槽记录两原候选投影是否相同，并记录五槽整体是否完全合并。原两候选合并不代表未知竞争消失；始终 all_alternatives_covered=false、search_certificate_transferred=false。原 top-2 全局证书只对应原 selection 似然，删除支持或投影后不继承排名；未知第三候选未枚举。保存原 selection 两支完整目标、原筛选身份和旧证书作用域作为 provenance，不用其优劣决定未来支持。

本次读取未来 y 仅为上述固定候选诊断；不将诊断用于回溯改变原 N。原 N 与观测选择、历史噪声和未来噪声可能相关，block-diagonal Q 并未解决这些相关性。

## 预算、失败、输出

上限 1191×2×(5+1)=14292 次 fixed-N GLS，最多相同数量 GLRT/sensitivity；最多11910次单槽三维长度球面计算。0 CILS、0 candidate enumeration、0 acceptance、0 native、0 evaluator、0 reference。有限 wall budget=1800 s，在窗口边界检查；未执行项记 NOT_RUN_WALL_BUDGET，仍出现在1191行总表。技术输入错误保留；不补窗、不调参、不重复真实运行。小型合成 oracle 测试另计，不读取真实数据。

执行需指定 root 冻结的 execution commit；脚本在开始/结束记录并比对实际导入的本仓库 source SHA、计划 SHA、原输入 SHA。输出必须新目录，拒绝覆盖。逐槽详细诊断、U/N/provenance 和 physical-column sensitivity 存入 scratch 压缩 JSONL；小表 CSV/summary 同时列全部1191/535/516以及不足支持/未执行/技术错误。

所有行包含 accepted_integer_measurement=false、false_fix_probability=null、all_alternatives_covered=false。主要状态只表示诊断执行情况：DIAGNOSTIC_COMPLETE、INSUFFICIENT_SUPPORT、INPUT_ERROR、NOT_RUN_WALL_BUDGET。报告需分别呈现支持、残差/长度 flags、故障可检测性、两支合并，不能合成“新的固定率”。

## 最小 oracle 检查

纯合成、无 LAMBDA：从物理 SD 生成数据与完整相关 Q；验证新 pivot 相消后 U 下的 y/B/Q/F 与直接 SD 差分一致；固定真 N 的 GLS 与独立显式最小二乘一致；目标信号与 pivot 故障符号、零列和 MDB-unbounded 正确；两弧同卫星不合并 persistent 故障列；五个动态 baseline 不被强制静止，联合成本等于逐槽和；候选投影合并仍不宣称接受；旧弧退休后不可复活；非法候选/时键/两支支持不一致拒绝。
