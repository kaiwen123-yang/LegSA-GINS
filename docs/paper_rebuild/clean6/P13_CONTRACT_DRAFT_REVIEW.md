> SUPERSEDED 2026-09-14: All five conflicts were resolved by explicit human decision. This document preserves the earlier draft review; current execution authority is SENSOR_MODEL_V21_CONTRACT.yaml and P13_APPENDIX.md.

# P-13 v2.1 合约草案审阅

起点：`a01ceb931049f84af8c900b39e4cf01c52f627c6`。

状态：`DRAFT_BLOCKED_SCIENTIFIC_CONTRACT_CONFLICTS`。合约 `executable=false`、`preregistered=false`；本文件与 `configs/paper_rebuild/clean6/SENSOR_MODEL_V21_CONTRACT.yaml` 仅供审阅。尚未生成 provider、运行求解器/评估器、生成图或交接包，也未提交或 push。草案不是已完成的预注册，所有科学验证门均为 `NOT_EVALUATED`。

## 已保留的任务范围

三项修正逐项登记：HV 的 FLU→FRD、Go2 roll/负 pitch 与 A1 NED yaw 旋转、`k_HV=1/0.962142`、`σ_HV=0.132838 m/s`；RP 使用 `[roll,−pitch]` 且 std 保持 1.6°；两项 fixed yaw std 从 1.5° 改为 2.933193°。BY2 常数一次冻结，BY2H/BY2O 盲转移，不重新拟合。P-12 不改陀螺标度、arw/gbstd 和安装角的数值与辨识限制均进入草案；Scheme-C、决定规则、Outcome、可执行文件和评估器保持冻结。

请求范围为 `10×(541+45)+3×10=5890` 个主链请求条目。其中 10 个 BY2 序列/C00 条目与矩阵 C00 同一身份，故为 **5880 个唯一重跑**；另有 50 个 F01 不变门审计 run。正式 F01 仍逐字节沿用 v2，审计输出不替换正式输出。下游误差预算阶梯、九格网格、V-CHK A04 与 A04/F04 稳健性复核另列，未计入 5880；实施前须列出准确身份，不重做决定。

交付完整保留：v3 主评估、v2 并行；同名聚合表、附加族、三序列、`V2_V21_COMPARISON.csv`；H7–H11 全报；§7/§11/§18 和方法声明；除 MFIG21 外全部图到 `figures/v21`，MFIG20 增加 HV/RP 修正前后残差子图；两个指定 ZIP 写入 `<HANDOFF_ROOT>`。P-09c 修订后的 256-run 分批、最多 22 个求解器、RSS 约束评估并发、每 8 批 push、封存和逐项精确清理均登记，未扩大删除范围。

## 必须先解决的五项冲突

| ID | 已确认的冲突 | 尚未采用的处理提案 |
|---|---|---|
| B01 | 冻结正式 F02 loader 在 `cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:372-373` 强制 `basic_dual_yaw_fixed_std_deg=1.5`，容差 1e-12；2.933193 会报 `basic_dual_yaw_EKF fixed yaw std must be 1.5 deg`。冻结科学提交有相同 guard；二进制 hash 与指定值一致。 | 人类可另行选择仅让 guard 接受 1.5 和预注册 2.933193 两值、保留数学更新与门控、保留旧二进制并登记新 SHA。这会修订原二进制冻结要求，目前未授权。不得自行绕过 guard、改算法身份、偷偷保留 1.5 或漏跑 F02。 |
| B02 | P-11b H-A 残差是未乘 k 的统计；最终 HV 乘 k 后，残差一般不能仍在 1e-6 内等于它。 | 对新 HV 先逆标度，按同一配对样本/掩码复现 H-A 坐标统计；另报最终乘 k 残差，不将两者说成相同。 |
| B03 | 修改 15/18 列文件的第 15 列（零基 index 14）yaw_std，GNSS 全文件 SHA-256 必然变化。 | 旧输入全文件 hash 对冻结值；新文件单独 hash，并核对全部非 yaw_std token 逐字节相同。IMU、RD 继续全文件 hash 相同。 |
| B04 | 现有 `frozen_parameter_hash` 只覆盖运行时科学配置；status std 是 provider 生成字段，HV std 位于 CSV，RP/HV 变换也不在该 hash 中。现有命名 runtime 字段仅 basic_dual std 有变化。 | 保留原 hash 算法，逐配置报告实际差异；另锁包含三个修正组的 sensor-model payload/hash，不能称作原 hash 恰有三个 runtime key 差异。 |
| B05 | A1/D61 故障会移除 yaw，而新 HV 依赖 A1。先用干净 A1 生成 HV 再注入 yaw outage，会在 HV 中保留缺失的航向信息；原附加合约则要求保留 Go2 有效位。 | 先作各 case yaw 注入，再从注入后的 A1 建 HV；>1.2 s 缺口使派生 HV 无效。A2/D62 保留 yaw。分别记录原 Go2 有效位与 A1 支持有效位，并明确新增依赖。 |

以上提案均为 `proposal_not_adopted`；不得把本次草案写入视为接受。B01 使要求的十配置完整链当前不能按原约束运行。

## 尚待在执行前冻结的定义

H7–H11 的目标原文已经保留，尚缺明确的配置覆盖、逐序列/逐种子或汇总判定、缺失数据规则，以及 H7 的准确一致性比字段。H9 保留 20 s 中断末端误差严格 `<10 m`，末端取样继续使用附加合约的半开区间最后一个匹配历元。H11 不预设方向。定义必须在新结果产生前冻结，不能看到结果后选择支持规则，也不改变原决定规则或 Outcome。

50 个 F01 的确定性样本身份与科学输出比较文件集合、下游诊断的原合约 hash 和确切 run 清单亦需在执行前冻结。现有 v2 被封存或清理的完整文件不能用显示抽稀文件冒充逐字节比较来源；若指定 anchor 不可用，明确记录 `UNAVAILABLE`。

## 固定来源与当前验证边界

草案已锁定现场原合约、CAL 模型、P-11b/H-A/P-12 JSON、求解器与评估器 SHA-256。P-09c 原合约 `8c034244…4587c`，附加合约 `fd11e416…546ec`；可执行文件 `9c00565c…3235f`，评估器 `aa049248…978da`。完整 hash 均在 YAML，不使用 v1/v2 表中的旧数字作为新执行证据。

三序列原观测检查的显示参照：H-A 样本数 `16968/17558/23022`，未乘 k 的 σ_HV 为 `0.132838/0.210121/0.106398 m/s`；P-12 静止 pitch 均值由 `2.028821/2.212328/−4.296193°` 变为 `−0.444112/−0.420844/−0.412029°`。这些是被冻结的目标来源；新 provider 尚不存在，不能据此报告新验证门通过。

草案的 YAML 解析与差异格式检查只验证文档结构，不验证传感器模型、运行兼容性或科学门。
