# HX-07 登记：RTKLIB 动基线星座变体

登记日期 2026-09-27。起点 2723868b6605e9b6239d9829762caa799fa98eb4；分支 stage/clean3-math-repair。既有未跟踪文件 29/29 路径与 SHA-256 一致。数据模式 recorded_raw_gnss；synthetic_data_used=false，semisynthetic_data_used=false。本文件在任何 HX-07 科学程序执行前提交并 push。

## 1. 输入身份与允许范围

输入完整路径别名、字节数及 SHA-256 见 HX07_INPUT_SHA256.json。六份观测只取 DG01R/CONVBIN/*_R1.obs 与 *_R2.obs，逐个与 DG-01R 输出清单核验。不读或重建 raw；不运行 convbin。官方 RTKLIB 源码提交 180043ee24b6d2b168f98b64be15f69d50046b1a，源码不改；rnx2rtkp SHA-256 3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda。全部源码文件另存 G: RTKLIB_SOURCE_SHA256.json。HX-02 合约 code_sha256 53 项全部核验，航向评估器 eedb3faf56ccffca222d915c401d3075dc64583ce68a10f08add9f8b705fa994，启动器 c94093d1fbf94c9f4db9f6f59334666ea8897c59bcd67654afd4a9914c7764fb。

外部广播星历由 BKG 官方镜像下载：

[BRDC00WRD_R_20260650000_01D_MN.rnx.gz](https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/065/BRDC00WRD_R_20260650000_01D_MN.rnx.gz)，UTC 2026-09-27T12:39:31.791402+00:00。

压缩 SHA-256 `664724f91cd3c8ca91f8a933ae879c13fb3fb77b7e8976d6e78a8d748d051aac`；RINEX SHA-256 `8d5222d82ea957d96a6d4bbe318a6f384532ed4a22016c92be84d78a3dac11cc`。

星历记录数（按 RINEX 记录首行，非唯一卫星数）：C=2423, E=6378, G=484, I=304, J=127, R=1412, S=16465。Galileo 存在门通过。下载回执 HX07_DOWNLOAD.json。

写入仅 <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX07、<W>/docs/paper_rebuild/hext/HX07、<W>/scripts/paper_rebuild/hx07_*.py 与 AGENTS.md 末尾。scratch 仅指定 HX07，结束删除。仓库交付 ≤20 MB、scratch ≤10 GB。v3/HX02–HX05 只读；禁止 LegSA 解算/评估、其他外部方法、调参和重试。

## 2. 三个配置与执行顺序（写定）

| 配置 | .conf 改动 | 观测 | 星历 | 手稿位置 |
|---|---|---|---|---|
| V0 | HX-02 原配置逐字节不变 | 六份官方 convbin 观测 | 各序列 HX-02 原 gnss1.nav、gnss2.nav | 控制，保留原主表行 |
| V1 | 仅 pos1-navsys：33 → 57 | 同 V0 | 外部 BKG 多系统 BRDC | 新增主表行 |
| V2 | V1 再仅 pos2-armode：continuous → fix-and-hold | 同 V0 | 同 V1 | 补充材料 |

三配置都通过命令行 `-y 1` 设置输出状态等级，对应 out-outstat=1；不修改 V0 配置的 out-outstat=off 字节。该参数只改 solopt.sstat（rnx2rtkp.c L175），不改变 prcopt。RTKLIB rtkpos.c L331 表明等级 1 不写逐卫星残差，故交付保留该级状态日志和 .pos 中的 ratio，不擅自升到 2，也不声称等级 1 含完整逐卫星残差。

以下参数保持原值：elmask=15、snrmask=0（off）、frequency=l1+l2、gloarmode=off、bdsarmode=on、arthres=3、baselen=0.350、basesig=0.010、arminfix=10；未显式列出的 elmaskhold 继续用同一官方默认值。三份配置 diff 与实际 .conf 的 SHA-256 同时登记。GNSS2 为 rover，GNSS1 为 base；ENU 基线为 GNSS2−GNSS1，body yaw=baseline heading+90°，wrap-safe。

顺序固定 V0/BY2 → V0/BY2H → V0/BY2O，再 V1 三序列，再 V2 三序列；每项最多一次，总预算 9 次 rnx2rtkp、9 次航向评估。每完成一条 V0 即检查复现门，任何一条差值绝对值 >2 历元立即停止全部后续科学执行，不做已完成 V0 的参考评估；全部 V0 通过后才进行三次 V0 航向评估及后续 V1/V2。没有按结果改变配置或输入的分支。

## 3. 时间、分母与 V0 门

| 序列 | base_time Unix s | 闭评估窗 s | 起点约定 | 配对分母 | V0 期望 Q=1 | 允许区间 |
|---|---:|---|---|---:|---:|---|
| BY2 | 1772784000 | [66,340] | C00，沿用原 argv 无 -ts | 1370 | 153 | 151–155 |
| BY2H | 1772784000 | [413,683] | CONTRACT_START，-ts 2026/03/06 08:07:11.198 GPST | 1350 | 179 | 177–181 |
| BY2O | 1772780400 | [3186,3563] | FILE_START，沿用原 argv 无 -ts | 1885 | 112 | 110–114 |

读取 HX-02 RTKLIB_PREPARED.json 的完整 selected_pairs，沿用 hx02_rtklib.heading_table 的同周唯一最近时间关联，仅在统计时取闭评估窗；不重新配对原始文件。即使新观测少端点，也不缩小配对分母或填造解。配对表中无 .pos 解的历元 rtklib_q=-1、valid=0。

已知输入覆盖差异在执行前声明：DG-01R official convbin 只从评估窗内 raw CSV 帧生成观测；HX-02 的 BY2/BY2O 包含窗前观测，BY2H 从合约起点开始。因此此处没有宣称暖启动历史相同，也不补回窗前数据。差异是否触发复现门只按上述固定计数判定，不能改容差或重跑。

## 4. 评估口径与审计

Q=1/2/5 给 .pos 全行计数、.pos 时间标签窗内计数及 HX-02 配对窗内计数，分别给各自分母和配对分母；边界差异显式保留。ratio 对 .pos 窗内全部/Q=1/Q=2 分别报 n/min/P05/median/P95/max；固定解基线长度残差为 norm(ENU)−0.350 m，报相同统计及绝对值 P95。零个样本为 UNAVAILABLE。

H 型沿用冻结 hx02_heading_evaluation：有效=Q=1 且有限航向；可用率=窗内有效/配对分母；有效误差 wrap180(body yaw−reference yaw)，参考语义 wrap360(90−interp(unwrap(yaw_ENU)))，只在参考支持内插值、不外推。全窗保持值从原生起点因果保持最后有效航向，首个有效值前不记零，另报无航向数与实际评分分母。

每个运行单独一个参考评估子进程，读取且 SHA-256 核验同一批 bytes；strace 强制参考成功只读打开一次，其他原始数据打开零、其他程序执行零、写入仅该评估输出目录。父进程审计钩子禁止 raw/reference 打开；rnx2rtkp 独立 strace，原生参考打开零。

BY2O 分段采用 HX-05 heading_slice_statistics，primary=[3369.94,3411.95] s，secondary=[3495.94,3508.94] s，outside=full 减两闭区间；同时给 full/inside_union 校对行。直接切已评估误差序列，不重新打开参考，不在段首重置保持值。

## 5. 手稿行与只读源码核查

规则不依赖结果：主表模糊度类保留 HX-05 第 06 行原配置，并新增 V1 行 “RTKLIB moving-base, four constellations with external ephemeris”；V2 放补充。V0/V1/V2 全部报告，不用最好结果替换原行；遇硬停时未执行行明确 NOT_RUN，不生成虚构指标。不修改 HX-05 表。

EXT01–EXT03 的 (a) 卫星时刻、(b) NAV-CLOCK/SPP 钟差、(c) 物理时刻假设、(d) SD/DD 钟差项只读核查，逐项附源码行号与片段；不修源码、不重跑。只陈述缺少或存在的处理，不作“方法不适用”结论。最终图沿用 publication/style.py 与 qa.py，并实际看 PNG。登记提交/push 成功后才允许 rnx2rtkp。
