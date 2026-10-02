# 既有配对与不确定度：先认清抽样单位

这里解释已经保存的区间，不重新 bootstrap，不把密集历元或九个半合成种子称为独立场地。本轮的误差序列复算回执另见 `series_checks/`；它不验证旧 bootstrap 的全部随机实现，也不赋予 reference 独立真值资格。

路径缩写：U=`<CODE_ROOT>/docs/paper_rebuild/v3/uncertainty/`，A=`<V3_ROOT>/07_AGGREGATE/`。下面的 CSV 名均接在相应根后。精确行键、字段及未舍入原值见 `secondary/UNCERTAINTY_SOURCE_CELLS.csv`；完整原表已经在仓库 U 内，未另造替代表。

指标单位：H/up/3D 为 m；yaw/roll/pitch/yaw 绝对误差 P95 为 deg。mean/median 差、CI 和 SD 沿同一指标单位；win_rate/touch fraction 无量纲，count 为次数。跨 case yaw RMSE 的 P95 与逐历元绝对 yaw P95 仍是不同统计量。

## 三种不同的区间

|既有记录|抽样单位与分母|区间回答什么|不能回答什么|
|---|---|---|---|
|A/PAIRWISE_SUMMARY_V3.csv、V2.csv，各 490 行|7 比较 × 7 指标 × 10 scope；overall 包含 C00；每个共同有限 case 等权|case 配对差均值、配对差中位数的既有 percentile 95% CI|不是 11 配置所有两两比较，不包含失败误差，也不是 type cluster CI|
|U/UA01_PAIRED_OVERALL.csv，20 行|5 比较 × 4 指标；540 个退化 case，不含 C00；按 type cluster 或 naive case 重抽样|共同有限案例的配对差中位数区间|不是两个总体中位数相减，不估计失败概率、不表示跨场地泛化|
|U/UA01_DISTRIBUTION_QUANTILES.csv，44 行|11 配置 × 4 指标，541 注册，按各自有限集合|各方法 median/P95 的 cluster 与 naive CI，共 176 个区间|成功子集不同，区间不能自行解决幸存者选择问题|
|U/UA01_C00_SERIES_STATS.csv，185 行|37 条自然序列方法身份 × 5 字段；BY2 13，BY2H/BY2O 各 12|单条录制误差 RMSE 的 MBB 区间|不是 185 次自然实验，也不是 reference 精度区间|
|U/UA01_C00_PAIRED_SERIES.csv，56 行|一对方法共同匹配历元，同索引重抽样|共同支持上的 RMSE(A)−RMSE(B) MBB 区间|不能用各自全支持 RMSE 替代，也不是新采集数据|

原 `clean6_canonical_v2/aggregate.py::finite_stats` 使用 B=10000、PCG64 seed=20260904。原 `PAIRWISE_CASE_LEVEL_V3/V2.csv` 各 25,284 行，包含 7 比较 × 7 指标的共同有限差值。SUMMARY 的 mean_delta 和 median_delta 各有区间；std_delta 是 ddof=0，胜负/平局阈值为 1e-12，win_rate 分母为共同有限数。柱线不能统称为“标准差”。

UA 的 case 分散表 `UA01_TYPE_SEED_DISPERSION.csv` 为 2,640 行（11×4×60），每 type 注册九种子，SD 使用 ddof=1；`UA01_FAMILY_DISPERSION_SUMMARY.csv` 为 352 行（11×4×8），其 median(sd)、P90(sd)、max(sd) 在 type 的 SD 上计算，不是族内原 RMSE 的平均。`UA01_PAIRED_CASE_VALUES.csv` 10,112 行、CASE_DIFFERENCES 1,200 行保存不同层次，不能相加为实验数。

UA cluster 标签集合含 61 个 type，包括 paired 540 域中的空 C00。每次有放回抽 61 个 type，将该 type 的全部有限 case 一起带入，再对拼接后的 case 求统计量；最后仍是 case 权重，不是对每个 type 均值等权。B=10000，seed=20260927 加组 SHA 派生。所有有限值 CI 条件于已有成功集合；未生成失败概率 CI、参考不确定度传播或多重比较校正。

## 均值、配对中位数与尾部可能给出不同答案

`PAIRWISE_SUMMARY_V3.csv` 的 `full_vs_no_SA/overall/horizontal_rmse_m`：513 个共同有限 case（含 C00），配对 mean 为 +0.02424462761201026 m，median 为 +0.00098121009139 m，median CI 为 [0.00097197142658232, 0.00098617618005859] m。各自总体 median 为 F04 0.098228073794353596、A04 0.097841365472664796 m，两者相减约 0.0003867083 m，显然不是前述配对 median。

UA 排除 C00 后，同一 H 比较 n=512，median=+0.00098070698562425368 m，type cluster CI=[0.00093644556402569523, 0.00098617618005859831] m。它与 stage 区间不是冲突：分母和重抽样单位都不同。

同一 stage 的 yaw 比较 n=513，mean=−1.7389797737493646°，mean CI=[−2.9934110209854183, −0.6735296744077047]；median=+0.0002579935045803°，median CI=[0.0002230909351091, 0.000271010929156]，190 次降低、323 次升高。少数大幅改善影响均值，绝大多数 nominal 微小差异影响中位数；不能只挑一种统计量说 SA 全面改善。

F04 yaw P95 原值 2.4465376134717114°，type cluster CI=[2.0011628967739465, 4.1757175822195558]，naive CI=[2.1076183513750042, 2.7034286882599177]。H P95=3.5510500790754915 m，对应 cluster [1.5172037277886301, 4.9152966826710651]、naive [2.0129328355943472, 3.6052374374987375]。这里 P95 是跨有限 case 的 RMSE 分位数，不是一次运行内逐历元绝对误差 P95；较宽 cluster 区间提醒 type 组成重要。

## 自然序列的 MBB 与时间支持

原 `ua01_uncertainty_stats.py::moving_block_rmse` 令 block=round(20/dt_median) 个样本，在全部重叠起点中均匀抽块，抽 ceil(n/block) 块并截断为 n，B=2000。paired 使用相同索引，求 sqrt(mean(eA²))−sqrt(mean(eB²))。这是样本权重，不是时长积分；块不在 gap 处主动切断。20/40 秒 batch 会舍弃末尾不足块；ACF 对中心化平方误差取首次非正相关截断，上限 round(60/dt_median)。n_eff 是此估计定义，不是独立物理场地数量。

F04 的原 dt_max：BY2 0.091676 s、BY2H 0.176012 s、BY2O 0.379999 s。20 秒 batch 数分别 11/11/15，40 秒为 5/5/7。包络 [t_start,t_end] 内不能据此声称无缺口。

56 个 paired 行均标 `EXACT_ROUNDED_1US`，nearest 为 NOT_NEEDED；最大时间差约 0.5 µs，因此不是原时间字符串逐字相同。LC01−F04 yaw/full 的共同 N 为 BY2 56,628、BY2H 58,554、BY2O 76,166，分别小于部分方法自己的支持；BY2O primary 共同 N=7,576，F04 自己有 7,612。

|原表 pair=LC01-F04，series=yaw_err_deg|共同支持上的 delta_rmse (°)|已有 paired MBB 95% CI (°)|读取方法|
|---|---:|---|---|
|BY2/full|1.1103372814582677|[-0.21516959110951978, 2.5738499973094195]|UA01_C00_PAIRED_SERIES 的 sequence/pair/segment/series 键|
|BY2H/full|0.27418922789454458|[-0.052059934438144398, 0.51426395229231248]|同上|
|BY2O/full|0.017475486096183879|[-1.3442060289453843, 1.4010706010080711]|同上|
|BY2O/primary|3.776270532494427|[2.1968137884816796, 4.4382142777679379]|只有两个完整 20 s batch，原 n_eff≈4.0814|

手稿若显示 F04−LC01，必须将 delta 取负且区间改为 [−high,−low]；原源键并不是 F04−LC01。完整窗区间跨零，不能由点估计写普遍优越。BY2 的 LC01-S−F04 yaw 区间 [-0.59036009951069612,−0.15213476967667347] 方向相反，敏感性身份要保留。此处只转录旧区间，未重开外部时序或重新抽样。

## 后续不确定度表的边界与实有文字差异

`UNC_REALIZATION_INTERVALS.csv` 111 行是 185 个 MBB 行中的三个字段子集；`UNC_DISTINGUISHABILITY.csv` 56 行是前述 paired 结果再分类，不是新的 56 次试验。`UA01_BY2O_SEGMENT_BANDS.csv` 48 行为 12 方法×full/primary/secondary/outside，没有 CI 字段；不能由文件名 bands 推断置信带。

已看到的展示差异保持来源并列，未改原文：

1. `UNC02_DISTINGUISHABILITY.md` 把 BY2/BY2H 的 F04−F02 H 写成 RESOLVED；机器表对应行是 **RESOLVED_NEGLIGIBLE**。delta 约 −0.00401580/−0.00313808 m，实用阈值 0.005 m。已有 277 项 `UNC_CLAIM_CHECK_RESULTS.csv` PASS 校验 delta/low/high，并不校验这两个分类文字。
2. UNC01 所称 median CI “zero-width”不能取代完整精度：F04 yaw cluster q50=[1.8859878395987226,1.8862718548526467] 并非零宽。
3. `UNC_FAST_COMPONENT_RANGE.csv` 的估计器数为 13/12/12，fast 范围分别 [1.2285876737227843,1.3106866300547064]、[1.39070061808866,1.4151634553301873]、[1.0531180735462389,1.0786035904015538]°，不支持“所有十三个完全相同”。
4. `UNC_YAW_DECOMPOSITION.csv` 的 F04 closure_ratio 为 0.9979658535306676 / 1.0044098237342136 / 0.9433684273009736。bias、slow、fast 分量不是已证明正交；`estimator_specific` 及减参考方差的量不应升级为独立识别的算法真误差或安装角。
5. 共享 reference 对有符号误差差 eA−eB 可相消，但平方差含 −2r(a−b)，RMSE 差一般不能相消 reference。当前扩展手稿 §5.5 已紧接旧说法加了此限制，不能把旧 UNC03 的无条件说法当成手稿无保留主张。
6. `UNC_HORIZONTAL_BODY_DECOMPOSITION.csv` 的 source 指向 CLEAN5_STAGE2_CLOSEOUT §10 B3，是旧层 B 材料，不能混进正式 Protocol V3 的新运行结果。

未提供的内容包括所有 11 方法全部配对区间、BY2H/BY2O 的 LC01-S 配对、BY2O secondary/outside 配对 CI、失败感知的精度区间、参考传播及 block 长度敏感性。没有这些信息不等于对应效果为零。

`UA01_ADDENDUM_STATS.csv` 264 行中 44 行 D62_30s 是 NOT_REGISTERED；paired 96 行中 16 行对应 n=0。`UA01_EXTERNAL_PAIRED.csv` 720 行中 504 未注册、180 为 9/9 有限、36 为注册九个但零有限；零配对不得统一记成算法失败。

以上是指标语义、源值阅读和明确的文字/分类差异。没有新 bootstrap，没有修订原科学结果；算法正确性与真实触发机制留待定向审查。
