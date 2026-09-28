# HX-07-R 登记：精确控制与星座/星历变体

2026-09-27。起点 42a5b14d9f563f24b2d1596e40107ff4503f5ec5；分支 stage/clean3-math-repair。数据模式 recorded_raw_gnss；synthetic_data_used=false、semisynthetic_data_used=false。本文件和三个新脚本提交并 push 成功后才执行。输入 pin 119 项，继承 91/91、RTKLIB 源码 927/927，29 条基线及四份旧硬停文件均已逐字节核验。

## 1. 续作缘由与历史保留

HX-07 V0 用 DG-01R 的窗内官方 convbin 观测，去复现 HX-02 完整重建 UBX 流经同一 convbin 转换的观测。HX-02 BY2/BY2H/BY2O 完整历元 1509/1483/2231、窗内 1370/1350/1885。DG01R_RINEX_CROSSCHECK.csv 共同伪距 551568、相位 247270 数值差异 0，LLI bit0 差异 15 处。原登记虽然说明历史不同，仍设 ±2 门；BY2 得 157/1370 对 153/1370（+4）而硬停，原生退出码 0。这是输入历史未固定的控制组设计问题，不据此宣称解算错误。HX-07 157/1370 保留为转换路径/输入历史敏感性补充，不删不改。这里只读已有 obs，不再 convbin、不改 raw。

## 2. 输入身份、版本与源码映射

HX07R_INPUT_SHA256.json 逐项列实际文件别名、字节数、SHA-256。六份唯一观测输入为 HX-02 三序列 RTKLIB run 的 SOURCE_BACKEND/gnss1.obs、gnss2.obs，逐项匹配 RTKLIB_PREPARED.json 中的 obs_sha256。三份原 .pos、原 argv、与 HX-05 MAIN.06/SUPP.07 数字相符的 HEADING_METRICS.json、HX-05 三张主/补充/分段表，以及 HX-07 硬停 .pos/门/停止回执均已登记。参考文件只登记旧 SPEC 的路径和 hash，不在父进程读取。

BRDC 第一行原文：

```text
     3.05           NAVIGATION DATA     MIXED               RINEX VERSION / TYPE
```

版本 3.05，文件类型 NAVIGATION DATA / MIXED，主版本 3 通过。只用该文件，不改换星历，SHA-256 8d5222d82ea957d96a6d4bbe318a6f384532ed4a22016c92be84d78a3dac11cc；Galileo 记录 6378 条沿用 HX-07 已登记计数。源码 code2idx/code2freq 映射与片段见 HX07R_SIGNAL_MAPPING.md，G 1C/2L/2S、E 1C/7Q、C 2I/7I、J 1C/2L/2S 各对应索引 0/1。无源码修改或适用性判断。

受保护目录按实际归档名为 CLEAN8_PROTOCOL_V3、HX02_FIVE_CATEGORY、HX03_DEGRADATION、HX03R2_AUDIT_REEVAL、HX05_CLOSEOUT、DG01R、HX07。开工前完整 size+mtime_ns 快照在 PROTECTED_METADATA_START.json，登记提交前及结果提交前分别再扫对比；任何新增、缺失或变化即 G5 硬停。只读文件元数据，不打开其中的参考 payload。

## 3. 写定的配置与 argv

| variant | conf | observations | navigation | manuscript |
|---|---|---|---|---|
| V0 | HX07/CONFIGS/V0.conf，原配置字节不变 | HX02 完整 gnss2.obs、gnss1.obs | 原 gnss1.nav、gnss2.nav | MAIN.06 不变 |
| V0E | 同 V0 | 同上 | 仅固定 BRDC | 补充，星历完整性效应 |
| V1 | HX07/CONFIGS/V1.conf，仅 navsys 33→57 | 同上 | 仅固定 BRDC | MAIN.06b |
| V2 | HX07/CONFIGS/V2.conf，再仅 continuous→fix-and-hold | 同上 | 仅固定 BRDC | 补充 |
| V0-convbin | 不运行 | 读 HX07/BY2_V0 的已核 hash 航向表 | 不运行 | BY2 敏感性补充 |

原 argv 必须为 `[rnx2rtkp,-k,conf,-o,pos,(-ts,date,time)?,gnss2.obs,gnss1.obs,gnss1.nav,gnss2.nav]`。原记录中的历史 scratch 路径已不存在，按同名 SOURCE_BACKEND 文件映射为当前 G: 归档路径，文件哈希逐项匹配，参数顺序不变。新 argv 只按此文件身份映射与本任务输出替换路径；-k 选择上表 conf，-o 指本 run 的 solution.pos，V0 保留两 nav 原顺序，其他变体只用 BRDC，在 `-o pos` 后插入 `-y 2`。BY2H `-ts 2026/03/06 08:07:11.198` GPST 原样保留，BY2/BY2O 无 -ts。

`-y 2` 在 rnx2rtkp.c L175 只设 solopt.sstat，不改 prcopt。所有 .conf 全部只读，线程环境变量均为 1，不设置其他科学环境差异。每次 COMMAND.json 保存实际 argv、旧 argv、exe/conf/obs/nav SHA-256、时间与返回码，stdout/stderr/独立 strace 留 G:。

## 4. 复现门与停止条件

| sequence | base_time | closed window s | paired n | Q1 exact | valid RMSE deg | hold RMSE deg | Q2 exact | Q2 RMSE deg |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| BY2 | 1772784000 | [66,340] | 1370 | 153 | 14.566166 | 58.241052 | 416 | 90.785046 |
| BY2H | 1772784000 | [413,683] | 1350 | 179 | 27.011169 | 55.117993 | 286 | 104.891563 |
| BY2O | 1772780400 | [3186,3563] | 1885 | 112 | 23.138950 | 129.988223 | 168 | 91.735474 |

G1：所有 pin、二进制/代码/配置/观测/argv 形状与 BRDC 主版本通过。
G2：每条 V0 完成即按冻结 hx02_rtklib.heading_table 和旧 selected_pairs 关联；Q1 必须精确等于表中整数，容差 0；失败立即停止，任何评估和后续变体均不运行。
G2b：.pos 删除 `%` 注释行后逐行原文比对，记录不同行数与前 5 处，另比全文件 Q1/Q2/Q5；仅记录，不设停止门。
G3：三个 V0 全部 G2 通过后才分别评估；有效计数/Q2 计数精确匹配，三个 RMSE 与表值绝对差 ≤1e-5 deg，任一失败硬停。
G4：每条 native 的 strace 只允许 rnx2rtkp execve，raw/参考 trace_vrtk/.bag/.fpl 打开 0，写入只在本 run 与 /dev；每评估恰一次参考只读打开并核验同一批 bytes，其他 raw 和程序 0，写入仅该评估输出。父进程审计钩子禁止 raw/reference。失败硬停。
G5：受保护目录元数据前后一致。G6：Git 只允许新 HX07R 文档、三个新脚本和 AGENTS.md 末尾追加，29 条未跟踪原样保留，四份旧报告只提交不改内容。

## 5. 唯一执行顺序、预算与失败规则

V0/BY2→G2→V0/BY2H→G2→V0/BY2O→G2；然后 V0 三评估→G3；再 V0E 三序列且各评估；再 V1 三序列且各评估；再 V2 三序列且各评估；最后只对旧 BY2/V0-convbin 航向表做一次评估。序列顺序均 BY2/BY2H/BY2O。无重试、无按结果修改输入/参数；正常预算 native 12、评估 13、参考打开 13，LegSA 解算/评估 0/0，其他方法 0。V0 返回非零或无 .pos 硬停；V0E/V1/V2 同类失败只记 NOT_AVAILABLE、原因与 stderr 尾 40 行并继续，不重跑，也不填造解；实际调用数如实报告。EXECUTION_STARTED.json 存在即拒绝重新执行，中断即停止，不自动续作。任何硬停写记录/报告、不做结果提交。

## 6. 统计、图表与手稿规则（事先写定）

关联使用旧 selected_pairs；同周唯一最近、严格单调一一对应、不按数值匹配；valid=Q1 且有限航向，无解 q=-1；不重配原始观测，不缩 1370/1350/1885 分母。body yaw=GNSS2−GNSS1 基线 heading+90°，误差 wrap180(method−reference)。冻结 H 评估器 eedb3faf…：reference yaw=wrap360(90−interp(unwrap(yaw_ENU)))，仅参考支持内插值；因果保持自原生起点开始，首个有效前不计零，报告缺航向数和实际评分分母。Q2 按 HX05 SUPP.07 独立子集。

有效评分历元 |error| 的 P50/P95/max、|error|>10° 的数量及比例；10° 为用户事先指定，作为整数固定错误代理，不认定整数正确性。参考约 1.1° 不确定度只引用 UNC_BUDGET.csv，不重算。分位数统一 NumPy linear。

BY2O 沿用 HX05 heading_slice_statistics：primary=[3369.94,3411.95]、secondary=[3495.94,3508.94] 闭区间，outside 为补集，另报 full/inside_union；切既有误差，不重启保持、不再次读取参考。

.pos Q1/Q2/Q5（另列无解）分全文件、.pos 标签闭窗、配对闭窗三种分母，各报告自身比例及相对配对分母比例。窗内 ratio 对全部/Q1/Q2 报 n/min/P05/median/P95/max；Q1/Q2 长度残差 norm(ENU)−0.350 m 报 n/mean/median/P05/P95/max absolute。约束 .350±.010 m 不变，此统计只作诊断。

$SAT 每行 17 字段，顺序与代码片段见 SIGNAL_MAPPING。逐系统 G/R/E/C/J/S、频率 1/2 计 vsat=1 的不同卫星；分母为窗内 $POS 输出历元，某系统无有效卫星时计 0，报 min/median/max、不同卫星总数、至少 1 颗 E/J 的历元数。图中跨频率按卫星去重，不重复计数。Q=1（按同 week/TOW 的 $POS 状态）且 vsat=1 的 resc 分系统报 RMS、带符号 P95 和绝对 P95；分频表亦保留。缺少 $SAT 或字段不符则该统计 UNAVAILABLE，不停止。

MAIN.06 所有旧列内容原样复制、标 UNCHANGED_HX05_MAIN_06；V1 新增 MAIN.06b，方法 ID `RTKLIB_MOVING_BASE_GPS_GAL_BDS_QZS_BRDC`，显示名 “RTKLIB moving-base, GPS+Galileo+BDS+QZSS, external broadcast ephemeris (BKG BRDC)”。V0E、V2、V0-convbin、Q2、分段进补充，不论结果均保留。EXT01–03 行去向由作者依据已提交审计决定，不改 HX05。

图 SFIG-HX7 四面板：(a) 四变体×三序列 Q1 可用率、标分母；(b) BY2 V0/V1 三态 Q；(c) BY2 V0/V1 有效航向误差 ±180°；(d) BY2 V0/V0E/V1 各系统有效卫星数堆叠，跨频去重。只读 HX07R 产物，174 mm、PNG≥4096 px/PDF/SVG，style.py、qa.py 并实际看图。详细每 run 产物留 G:；repo≤20 MB、scratch≤10 GB，结束删除 scratch，不做交接包。

报告勘误：原“0.2 s 内自身运动≤1.2 mm”不改历史；按 |Δclk|≤0.443 ms，给条件速度≤1.2 m/s 时上界约0.53 mm（未舍入0.5316 mm），2 m/s 时约0.89 mm（0.886 mm）。这是条件界，不把速度假设当成新测量。
