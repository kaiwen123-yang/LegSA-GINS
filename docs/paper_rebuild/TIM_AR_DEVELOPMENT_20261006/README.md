# TIM R4 成稿推进与载波相位机制验证

2026-10-06。本轮在原 V3 成稿基线上推进 TIM 完整正文，并完成一个独立载波相位候选机制及固定原始时间弧资格审计。算法修改、求解、数据审计和数值复核全部在 E 盘 Ubuntu-22.04 WSL 完成；Word 排版/渲染使用文档工具。

## 先读哪些文件

- [完整 TIM R4 Word](manuscript/manuscript_tim_r4.docx) / [可追踪 Markdown 源稿](manuscript/manuscript_tim_r4.md)：15 页工作稿，13 个可编辑显示公式、2 表、15 条编号文献及 8 个计划图注。
- [中文测量章节与入稿说明](manuscript/manuscript_measurement_sections_zh.md)；[测量与 AR 独立补充稿](manuscript/supplement_measurement_and_ar_r4.md)。
- [作者决策](01_AUTHOR_DECISION.md)：当前三条成稿线索、AR 去留及真实缺口。
- [主文修订与证据映射](03_TIM_MANUSCRIPT_AND_EVIDENCE.md)、[24 条 claim–evidence 对照](claims-evidence-map.csv)、[23 项来源目录](evidence-catalog.csv)。
- [D 试验完整结果](04_D_RESULTS.md)与[独立复核](D_INDEPENDENT_REVIEW.md)。
- [原始时间弧资格审计](07_RAW_ARC_QUALIFICATION.md)与[下一方法决策](06_NEXT_METHOD_DECISION.md)。

## 这轮实际得到什么

TIM 正文将基线投影角、Euler yaw、原 V3 近似和后续诊断模型分开；补充倾斜、异步采样、跨接收机相关性和方向误差预算。原性能表、控制矩阵和新合成/诊断结果保留各自身份。新增分析模型未被倒写成原 V3 已实现的完整协方差处理。

D 是标准有界 RP 惩罚的适配。先冻结代码与合同，再完成20次C-ILS和独立代价/角度/整数复算。正确 RP 下保留3个有用纠错；错误 RP 下仍3/4错误候选，相位偏差下仍2/4。四份噪声在条件之间共享，不是独立风险估计。D 保留为方法对照，未升级为可信 FIX，也没有新的 EKF 融合。

预先固定的 BY2 80–82 s 原始窗口有10个精确配对历元，4个GPS L1信号连续严格有效，跨度约1.8s；这只是下一步时间弧研究的输入资格。其余星座/频点确有公共相位支持，GPS L1隔离对照不能充当完整同信息方法排名。

## Git 与使用标签

| 里程碑 | Git 标注 | 成稿身份 |
|---|---|---|
| 授权、范围、证据标注 | 03ac3a0 / docs(tim-paper) | 决策与边界 |
| D 实现及事前冻结 | 0f9f472 / feat(ar-research) | SUPPLEMENT_EXPLORATORY |
| D 20次结果与独立复核 | 8d4dc01 / experiment(ar-validation) | SUPPLEMENT_EXPLORATORY，含失败 |
| 原始弧资格审计 | 9f87aba / experiment(ar-validation) | 仅输入资格 |
| 完整 R4 与成稿映射 | 本目录 docs(tim-paper) 提交 | 测量分析/支持；未宣称投稿就绪 |

[范围与状态定义](00_SCOPE_AND_PAPER_LABELS.md)统一 MAIN_TEXT_READY、SUPPLEMENT_EXPLORATORY 和 NEEDS_MEASUREMENT。原 V3、旧论文和旧科学输出保持不变。当前仍需物理输入标定、独立或相关性明确的参考，以及图件完成；本文不是已证实新 AR 方法或已达到期刊新颖性门槛的声明。

## 执行与复算

本轮新增科学求解为20次C-ILS；新增SPP/导航求解均0。固定时间窗审计不调用求解器或参考。完整合同、逐条指标和来源hash保存在本目录；脚本在 [tim_ar_development_20261006](../../../scripts/paper_rebuild/tim_ar_development_20261006/README.md)。原始及中间大文件留在登记scratch，未混入论文源数据。
