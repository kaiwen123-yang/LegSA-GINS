# Protocol v2 method statement

人类决定（2026-09-13）：论文提出方法为 **F04（AB1111）**。方法由 KF-GINS 骨干、双天线短基线机身航向、scheme-C 质量感知门控、机身 roll/pitch 弱先验、Raw Doppler 辅助速度、腿部水平速度弱先验和 Source-Aware 加权组成。消融阶梯为 **F01→F02→F03→A04→F04**。A04（AB1011）是 v1 预注册规则的既有决定，作为无 Source-Aware 的消融行保留；原决定规则与 Outcome 不变。

协议 v2 的主评估点为 v3。下表来自已冻结的 541 核心表；附加族独立报告，不合并入核心统计。差值为候选减参考，负值表示该误差统计量降低。分布 P95 是有限逐 case RMSE 的第 95 百分位，即最差 5% 的进入阈值，不是最差 5% 的均值；算法失败另计。

| 层或对比 | 冻结证据（v3） | 来源及 CSV 物理行（含表头） |
|---|---|---|
| 双天线，F02−F01 | 航向 RMSE 配对中位差 −5.70214540134477°，n=541 | PAIRWISE_SUMMARY:1041 |
| 门控，F02→F03 | 逐 case 航向 RMSE 的 P95：27.69463843498005→12.920123968025251° | UNIQUE_METHOD_SUMMARY:3357,3761 |
| 辅助模块阶梯，F03→A04 | 航向 RMSE 的 P95：12.920123968025251→6.720069208034486°；roll/pitch 配对中位差 −1.2994137177604803/−0.7637280146069414°，n=526 | UNIQUE_METHOD_SUMMARY:3761,529；PAIRWISE_SUMMARY:361,321 |
| 单独 RP 消融，F04−A05 | roll/pitch RMSE 配对中位差 −1.11310497919139/−0.6428940882327567°，n=521 | PAIRWISE_SUMMARY:1531,1491 |
| RD，D05 的 F04−A03 | 故障窗水平 RMSE 配对中位差 −4.996628167587727 m，均值差 −5.0589279093657495 m，n=9 | PAIRWISE_CASE_LEVEL:18544,18557,18570,18583,18596,18609,18622,18635,18648 |
| HV，D05 的 F04−A06 | 故障窗水平 RMSE 配对中位差 −0.10316249601704364 m，均值差 −0.2023366410739 m，n=9 | PAIRWISE_CASE_LEVEL:36420,36433,36446,36459,36472,36485,36498,36511,36524 |
| SA，A04→F04 | 航向 RMSE 的 P95：6.720069208034486→3.157590053291289°；有限 case 均值：5.3842849624636075→3.870187833231392°；算法失败 A04=7、F04=11 | UNIQUE_METHOD_SUMMARY:529,4165 |

F03→A04 同时加入 RD、RP、HV，不能把这一步的全部变化归为 RP 的独立作用。上述单独 RP 行保留对应的模块消融。原拟写的 roll/pitch −1.2/−0.7° 不对应这两组冻结配对统计，本文使用表中的原值。

RD/HV 定位为“速度辅助冗余层／优雅退化阶梯”。接收机速度有效时，已有速度观测约束了同一速度状态，弱辅助项的边际变化可能很小；小的正常窗差值不等于失效场景下没有作用。D05 在位置与接收机速度同时中断时保留 RD；A1/A2 进一步关闭 RD，用于检验 HV 在唯一辅助速度来源条件下的表现。该解释是状态约束与信息冗余的机理说明，不是普遍收益保证。

附加族登记说明：ADDENDUM_FAMILIES_A1_A2 — pre-registered 2026-09-13, added after the 541-core results were seen, to cover a scenario absent from the library。A1/D61 包含 10/20/30 s、27 case；A2/D62 包含 10/20 s、18 case。全部 495 次新增求解与双版本评估仅进入 `13_AGGREGATE_ADDENDUM/{v3,v2}`。这是在真实 BY2 基础上注入中断的半合成实验，不能称为自然 GNSS 全断实录。

<!-- ADDENDUM_OUTCOMES_BEGIN -->
v3/v2 的冻结假设判定一致：H1 `PARTIALLY_SUPPORTED`；H2 `SUPPORTED`；H3 `OBSERVED_SOME_SEED_HARM`。H3 判定中 `full_vs_no_Go2` 的有害 case–metric 行数为 32，缺失行数为 0；此计数不是独立种子数。495 次求解、v3/v2 各 495 条评估均为 `COMPLETED`，算法失败为 0。

以下为 v3 的 F04−A06（full_vs_no_HV）族级冻结配对值；A1 n=27，A2 n=18。完整八项配对、各时长九 case 分组与逐种子符号见 [ADDENDUM_FAMILIES_A1_A2_RESULTS.md](ADDENDUM_FAMILIES_A1_A2_RESULTS.md)。

| 族 | 指标 | 均值差 (m) | 中位差 (m) | 中位差 bootstrap 95% CI (m) | 胜率 | Wilcoxon p |
|---|---|---:|---:|---|---:|---:|
| A1 | fault_window_horizontal_rmse_m | -0.011142076463065018 | -0.00690213830242925 | [-0.01614328016192701, 0.00110470758839476] | 0.6666666666666666 | 0.00441385778107854 |
| A2 | fault_window_horizontal_rmse_m | -10.881309529635626 | -5.45592910851764 | [-20.17804452336491, -2.2361079069689964] | 1.0 | 7.62939453125e-06 |
| A1 | outage_end_horizontal_error_m | -0.022014158767246488 | -0.013668375752843076 | [-0.03241384619519749, 0.0020710995034924906] | 0.6666666666666666 | 0.00441385778107854 |
| A2 | outage_end_horizontal_error_m | -31.19100264997546 | -15.971134595412632 | [-56.792582590804564, -6.915448530501524] | 1.0 | 7.62939453125e-06 |

来源：`<ADDENDUM_ROOT>/13_AGGREGATE_ADDENDUM/v3/PAIRWISE_SUMMARY.csv`，物理行 86、87、95、96（含表头，按上表顺序）；SHA-256 `b31b250a5af7fee5cc5b9a0e078f79ce52a51266daa400c9d7db8de3cba9a2ae`。
<!-- ADDENDUM_OUTCOMES_END -->

D06 所示的航向丢失条件下，机身先验可能在部分种子上有害。机身系速度向导航系的投影依赖姿态；航向约束丢失后，姿态与辅助速度误差可能耦合。因此保留逐种子正负号、失败数和完整不利结果。后续工作包括航向可观测性条件下的先验可信度诊断；本协议没有据此调参、改权、删除历元或修正输出。

相对 v1 预注册 A04 决定的修订理由：v1 的位置界失败发生于其噪声模型与实际传感器不匹配的条件；冻结 BY2 标定参数并盲传至 BY2H/BY2O 后，v2 的位置界在 v3 和并行 v2 评估下均为 PASS。原航向检验基于未人工注入退化的真实序列，而 SA 的论文定位是退化条件下的保护模块。人类依据协议 v2 的退化证据选择 F04；这不把原规则的 FAIL 改写为 PASS，也不声称所有改善都由单一噪声参数因果解释。

位置界来源：`<CLEAN5_CALIBRATED_ROOT>/08_AGGREGATE/CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv`，v3 位置第 21 行、v2 位置第 11 行 PASS，v3 航向第 20 行仍为 FAIL；`outcome_changed=false`、`new_outcome_created=false`。标定链仍标注 `NOT_THE_PREREGISTERED_COMPARISON_PROTOCOL`。

参考轨迹表述：the fused navigation solution output directly by the commercial low-cost dual-antenna GNSS/INS receiver (Fixposition Vision-RTK 2); the estimator under test never reads it (file-access audit)。图中使用 `Truth`；参考不确定度由独立的对话 D 记录。文件访问审计证明估计器不读取该解，不能单独证明参考误差独立或参考无误差。

核心来源根：`<CANONICAL541_V2_ROOT>/13_AGGREGATE/v3/`。SHA-256：

| 来源 | SHA-256 |
|---|---|
| UNIQUE_METHOD_SUMMARY.csv | `2028886e334ee0791ec394626f3f730b26328533b755cee3cbf954b7496845d0` |
| PAIRWISE_SUMMARY.csv | `90dbfd24870cb8168f13942b92a93f5936a88118fdb94c5c62ba7cf12c24737e` |
| PAIRWISE_CASE_LEVEL.csv | `99958ef6902789803ebb9b5b5f6a63676a2781ef6d8ffc043cdc89469b7462ff` |
| CALIBRATED_CHAIN_ROBUSTNESS_CHECK.csv | `77211ce62a1ef3f05e9cf25585578a3735803cc62499bc322ae6cde0ca0b0cb9` |
