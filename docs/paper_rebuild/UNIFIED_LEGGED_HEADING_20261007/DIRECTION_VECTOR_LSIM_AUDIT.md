# 三维方向观测被标量 LSIM 再降权：现有输出审查

2026-10-07。**最明确、已有真实消费计数的缺口位于三维 baseline 观测进入 source-aware weighting 的元数据边界。** 后端保留完整各向异性 R，却把 `sqrt(R_NN)/0.35` 命名为 scalar yaw standard deviation，再据其大小将整张 R 乘 2 或 6。三窗已接受的 302 条 partial 中，281 条乘 6、17 条乘 2；638 条完整方向的 LSIM 均为 1。

本轮仅读既有 provider、前端保存域和 native 更新诊断；没有读 NAV/reference/raw，没有 native/evaluator，没有更改噪声或筛掉观测。下面的修正候选来自观测类型和坐标等变性，不是为得到更小 RMSE 选择更小 sigma。此时未得到新导航结果。

## 1. 分母与实际动作

FULL 指同槽原 `FULL.csv` 已有效，PARTIAL 指原 FULL 无效而 `MOTION.csv`（rolling）新增有效；没有依据估计误差或接受结果选择时间。所有尝试与接受分母均保留。

| 原 rolling 实验 | 类型 | 尝试 / 接受 | 已接受 LSIM×1 | ×2 | ×6 |
|---|---|---:|---:|---:|---:|
| BY2 | FULL | 181 / 174 | 174 | 0 | 0 |
| BY2 | PARTIAL | 142 / 123 | 0 | 0 | 123 |
| BY2H | FULL | 345 / 321 | 321 | 0 | 0 |
| BY2H | PARTIAL | 83 / 75 | 0 | 5 | 70 |
| BY2O | FULL | 168 / 143 | 143 | 0 | 0 |
| BY2O | PARTIAL | 117 / 104 | 4 | 12 | 88 |
| 合计 | FULL | 694 / 638 | 638 | 0 | 0 |
| 合计 | PARTIAL | 342 / 302 | 4 | 17 | 281 |

40 条 partial 在硬 NIS 阶段已拒绝，不能把它们说成此次 scalar LSIM 丢弃；302 条通过后才进入这里的比较。表中 LSIM×1 不等于总 R 必定不变：完整方向仍有少量 OIM 增权。partial 的本表 2/6 则全部由 `lsim_dual_yaw_std_high/extreme` 主导，combined 取 max(LSIM,OIM)，不是将两者相乘。

已有统一足端背景另列，不加入上表三窗分母：
`SUPPORT_POSE_NATIVE_BY2O_01/NATIVE/BY2O__REPLACE_SUPPORT` 的 105 条已接受 partial 为 **89×6、12×2、4×1**。这是足端因子真实进入同一 R/v/p 后的实际消费，存在可审查的下一 matched 对照窗口。

## 2. 具体信息在哪一步损失

原活路径为 `gi_engine.cpp::Baseline3DUpdate`（本轮修正前约 1488–1507 行）：

1. `model.R` 是完整 NED 协方差，非对角项保留；`h=R r_body`，实际姿态 Jacobian 使用 `[h]x`。
2. 原硬 NIS 使用 `R_QA=qa_scale*model.R` 和完整创新协方差；原 3 DOF 11.34 门先执行。
3. 填 `metadata.rel_acc_m=sqrt(model.R(0,0))`、`metadata.yaw_std_rad=rel_acc/0.35`，观测被标为 `kDualAntennaYaw`。
4. 当前 `clean_v1_conservative_innovation_covariance` 的 LSIM 把该代理 >15°/>30° 映射为至少 2/6（`source_aware_policy.cpp` 修正前 382–387 行）。这是 scalar yaw 产品的规则，未使用三维强弱方向或水平投影。
5. OIM 仍使用完整 R 和创新 S；combined 取 `max(LSIM,OIM)`，实际 EKF 最后使用 `combined*R_QA`。当前相应实验 QA/QM off，因此这里确实是额外一次整张 tensor 的 2/6 倍膨胀。

`yaw_std` 在这条实际路径影响 LSIM 的置信度分支及日志，不替代硬 NIS/OIM 中的完整 R。当前没有把三维测量直接变成 scalar yaw 更新；问题是三维观测借用了不适用的 scalar-yaw 质量元数据。既有 [PARTIAL_BACKEND_MODEL.md](../CONTINUOUS_HEADING_20261007/PARTIAL_BACKEND_MODEL.md) 已指出此近似，本轮补齐全部实际计数与等变反例。

在同一 h 下，整张 R 乘 6 使 `H^T R^−1 H` 的所有可观测方向一起变为 1/6，强方向也损失 5/6 的名义测量信息。该代数结论不等于姿态误差或 RMSE 会改善六倍，也不替代未知跨来源相关性建模。

## 3. 两种物理 sigma 必须区分

对保存的预测基线 `h=(hN,hE,hD)`，令 `hH²=hN²+hE²`：

```
g = [−hE,hN,0]/hH²
sigma_azimuth² = g R g^T
jpsi = [−hE,hN,0]
sigma_psi_fixed_others² = 1/(jpsi^T R^−1 jpsi).
```

前者是无约束三维基线产品经 atan2 的局部协方差传播，保留水平投影趋零时的退化。后者是假定其他姿态分量固定时，物理基线对 yaw 局部切向的均值信息；它不是对未观测姿态自由度边缘化后的绝对 yaw 精度，更不是圆周多模态置信区间。

| 全部已接受 partial，中位数 | 原 R_NN/0.35 代理 | azimuth delta sigma | 固定其他姿态 sigma |
|---|---:|---:|---:|
| BY2，123 条 | 84.3467° | 41.8406° | 2.2641° |
| BY2H，75 条 | 60.2421° | 63.4722° | 5.7834° |
| BY2O，104 条 | 64.0840° | 56.6044° | 2.4316° |

不能因为第三列数值小就把它填进 LSIM。即使改用有坐标意义的 azimuth delta sigma，再把整张 R 按它放大，也会把基线产品的弱分量惩罚施加到独立的强切向。partial 在物理球面上可能仍有多个方向分量；大局部 azimuth sigma 也不能替代这些分量。

以已接受的 BY2O **3202.798000097275 s** 为例：

- R 本征值约 `[0.000112911,0.000713490,0.487237361] m²`，条件数约 4315；
- R_NN≈0.3628175 m²，其中约 **0.3627739 m² 来自最弱本征方向**；
- `jpsi^T R^−1 jpsi≈664.9109 rad⁻²`，其中约 **648.6201 rad⁻² 来自最强本征方向**；
- 原代理 98.6049°，azimuth delta 63.3503°，固定其他姿态 2.2220°；实际整张 R×6。

这说明代理把强弱方向混为一个产品质量标签。它不证明共享整数必然正确，也不授权取消真实质量或失效证据。

## 4. 23 个实际行上的坐标等变反例

只对已保存的 h、R 做一次纯坐标变化：
`O=Rz(90°), h'=Oh, R'=ORO^T`。没有改变物理观测，没有运行滤波，也没有重新选择数据。azimuth delta 方差和固定其他姿态信息保持不变，原代理却使用新 R_NN；旧 LSIM 档位发生变化：

| 全部 302 已接受 partial | 档位变化条数 |
|---|---:|
| BY2 123 | 0 |
| BY2H 75 | 6 |
| BY2O 104 | 17 |
| 合计 | **23** |

所有 23 条列在机器表，不只保存一个有利例。BY2H **489.99799990654 s**：原代理 25.485455°→旋转后 7.032598°，使旧档位 **2→1**；azimuth delta 始终 8.868430°，固定其他姿态始终 1.761564°。BY2O **3248.197999954224 s** 则反向 **1→2**，不是只寻找减权例。

全 302 条的 azimuth 差最大 0°；固定其他姿态差最大约 2.22e−12°。North 只是坐标轴，当前模型没有一个“North 误差决定所有方向独立质量”的物理假设。该不等变是确定的观测类型边界问题；修正收益仍须匹配运行反驳。

## 5. NMB1 的 8 条最终 partial：版本与消费不能混写

上一 [源内差分读出](DIFFERENTIAL_DIRECTION_SOURCE_READOUT.md) 使用的是**实际 native 供给及配套旧部分协议**：
`NAVIGATION_NMB1_01/PROVIDERS/NMB1/CARRIER.csv` 为 227 条完整方向，`TRANSFER_NMB1_NATIVE_READOUT_01` 旧门为 32 partial 域、0 准入。

后来的最终 `TRANSFER_FINAL_PARTIAL_01/NMB1` 已以保留子集自身质量得到 **8 条 partial 新增、共 235 条 valid**；不是“当前前端所有 partial 都未准入”。8 条来自两组原 acquisition source：

- A：`0cd49a9f84abf12d63b6c33fd32ba7fbc32595ec617f938ed0e561db005164e9`；origin `c1cd8ac20d56a5301913e2e4fd412cb797a4334dad601937b917a1daa8408c55`，共同整数 2、phase rank 2。
- B：`3efdb05aff3da01b712f31137b32dc06e264e5148362e06b808fc132527342c5`；origin `ebff20faa1f4e54729f8a142f6959f9be2ba3b7bd3047eacb9b70bde2d8f8fc2`，共同整数 1、phase rank 1。

| index | measurement time (s) | source | 原 joint 分量 | directed 分量 / 包围宽度 | 实际 PVT age |
|---:|---:|---|---:|---:|---:|
| 462 | 40713.80399990082 | A | 2 | 2 / 179.648438° | 3.812790 ms |
| 463 | 40714.00399994850 | A | 2 | 2 / 178.945313° | 3.812790 ms |
| 464 | 40714.20399999619 | A | 2 | 2 / 175.781250° | 3.812790 ms |
| 1700 | 40961.40400004387 | B | 2 | 1 / 17.578125° | 3.802776 ms |
| 1701 | 40961.60400009155 | B | 2 | 2 / 100.898438° | 3.802776 ms |
| 1702 | 40961.80399990082 | B | 2 | 1 / 18.281250° | 3.802538 ms |
| 1703 | 40962.00399994850 | B | 2 | 1 / 19.600983° | 3.802538 ms |
| 1704 | 40962.20399999619 | B | 2 | 1 / 18.984375° | 3.802538 ms |

8/8 均有新鲜有效 PVT 航向，原 provider yaw_std 均 2.933193°。方向域宽度与 Gaussian sigma 是不同量，不能直接以宽度排序精度。原始物理 joint 域全部双分量；gyro 条件 directed 域也有 4 条仍双分量，不能给它们造一个单峰 yaw 观测。

当前真实 native 配置仍读旧 227 点 CARRIER 文件，因此这 8 个槽的真实日志是 `carrier_valid=0, attempted=0, CARRIER_SOURCE_INVALID`，并未进入 SA。若仅改读最终 235 点文件，原 `pvt_priority_fallback` 也会被有效 PVT 覆盖；已保存 `TRANSFER_CONSUMPTION_EQUIVALENCE.json` 证明最终 reset/rolling 在该策略下与旧文件的 12 条可消费载荷相同。不能把这 8 条称为“被 SA 拒绝”或新增补缺。

raw carrier 与 PVT 都来自同一对 GNSS 接收机；前者使用已列出的 code/shared phase，后者是接收机位置/航向产品，且部分前端还以 RP/gyro 作资格。它们不是已证独立信息。现有摘要不提供 PVT 与该 raw likelihood 的 cross 或条件剩余信息，故不能判断这 8 条在已用 PVT 后究竟增加多少；也不为让它们生效而关闭可靠 PVT 或独立加两遍。8 条均在主 163 s 空窗之外，NMB gap 的 valid/partial 供给仍为 0。

## 6. 本轮单一实施候选及停止边界

最小修正是**明确 external carrier baseline3D 不提供 scalar yaw_std 产品**，从而不进入这个标量产品标准差的 LSIM 2/6 分支。保留完整各向异性 R、物理 h/H、原 hard NIS、完整 S 的 OIM、真实源资格/失效语义及 source 分类日志。scalar yaw 产品及旧内部 baseline3D 路径仍沿原规则；不把原代理换成上表某个较小 sigma，不改原 provider floor、partial 五槽或整数质量，不改变 PVT 优先策略。

这是对观测类型误用的修正，不是已完成校准、来源去相关或滑移认证。整张 R 已表达几何不确定性，额外基于其中一个坐标分量的“高 yaw_std”惩罚没有独立故障依据；实际不良源仍由保留的资格、质量、NIS/OIM 和依赖撤销处理。缺少相关性标定不能由多乘一个任意标量得到解决。

选已有 BY2O 足端＋ROLLING 完整窗做一次匹配诊断具备实证基础；其历史源为：

- 配置：`<U>/SUPPORT_POSE_NATIVE_BY2O_01/CONFIGS/BY2O__REPLACE_SUPPORT.yaml`；
- 实际输出：`<U>/SUPPORT_POSE_NATIVE_BY2O_01/NATIVE/BY2O__REPLACE_SUPPORT`；
- 载波：`<C>/PARTIAL_FULL_WINDOW_01/BY2O/MOTION.csv`；
- 足点：`<U>/SUPPORT_POSE_PROVIDER_BY2O_01/SUPPORT_POSE_EVENTS.csv`；
- 历史二进制 SHA：`4f7920fec25af4b2d64a22cfbb71309c2c0807a75c5b6af7e690c1b7ff141f38`。

该配置明确 `heading_source_policy=configured`、`baseline3d_source=external_carrier`、原 XY 足点 REPLACE_SUPPORT 与 body-FRD SDK。它是已有研究对照，不是临时关闭 PVT 造效果；能否复用历史控制须另核当前代码关闭新功能时的科学身份，不能仅凭相同配置名假定相同。NMB 不作为本次 partial pilot，也不重复上轮足差分。

## 7. 保存结果与复现身份

`<C>=/home/kaiwen/research/LegSA-GINS-SCRATCH/CONTINUOUS_HEADING_20261007`；
`<U>=/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007`。

可复现脚本：`scripts/paper_rebuild/unified_legged_heading_20261007/direction_vector_lsim_audit.py`。

实际成功输出为 `<U>/DIRECTION_VECTOR_LSIM_AUDIT_02`：

- `ACCEPTED_GEOMETRY.csv` 保留三窗全部 940 条已接受行及统一足端背景的单列行，包含原 h/R、本征分解、两种 sigma 和纯坐标变换结果；
- `STAGE_COUNTS.csv` 保留所有 attempted/accepted 及 FULL/PARTIAL 分类；
- `ROTATION_COUNTEREXAMPLES.csv` 保存全部 23 条主三窗档位变化；
- `NMB1_FINAL_EIGHT_PARTIAL.csv` 保存 8 条完整 source/origin/整数/保留原始行/域分量/PVT 身份；
- `SUMMARY.json` 和 `OUTPUT_SEAL.json` 记录所有输入 hash、脚本及输出身份。

首个 `DIRECTION_VECTOR_LSIM_AUDIT_01` 在任何结果输出前因归档脚本 argparse 循环覆盖同名时间 key 函数而退出；只修变量名，在新目录完成相同只读计算，失败目录保留 `FAILED_PRE_OUTPUT.json`。没有新的科学参数或真实 solver 调用。此前临时只读统计与本次归档统计一致。

仓库精炼表：`DIRECTION_VECTOR_LSIM_COUNTS.csv`、`DIRECTION_VECTOR_LSIM_ROTATION_CASES.csv`、`DIRECTION_VECTOR_LSIM_NMB1_EIGHT.csv`。上一源内读出仅更正前端版本措辞，其机器结果与封存身份不变。

