> 阶段记录：以下保留组图生成前的结果恢复与规划。文中的待办和候选主线反映该阶段；当前决定与下一步以[交接入口](../../README.md)为准。

# 已完成的外部融合比较：记录恢复与论文用途

日期：2026-10-11。范围：LC01 / LC01-S / EXT05C、HX03→HX03R2、OiSAM strict / segmented、Wen TC、GNC、GINav，以及鲁棒形状对照的身份。这里只读取既有源、配置、运行与结果；新 solver / evaluator / provider 调用均为 0。全部写入仅在本目录。

## 先纠正此前的判断

外部比较已经相当完整，不能再概括为“还没有同输入对照”或“还需要先补 FGO”。已经找到并追到实际运行的内容包括：

1. 同一 IEKF 骨架的双位置更新与单位置更新：LC01 / EXT05C；LIT / S 参数条件均有自然三序列结果和起点条件记录。
2. LC01 / EXT05C 的 Classic-18、A2 退化，以及 LC01-BR 的相对基线更新控制。更正后的 HX03R2 已有 **396 条逻辑结果、744 条逐型/族配对指标行**；396 不是新增 native 次数。
3. 三种 FGO 路线的 9 个 strict 自然数据身份；OiSAM 在缺 IMU 时停下的原因、实际输出支持、原始求解事件均已保存。
4. 另身份的 OiSAM 分段恢复诊断：**3 个新 OiSAM native、11 个预登记真实输入区段、6 个复用 Wen/GNC native**。BY2 无缺口控制的 285 行状态及旧事件字段与 strict exact 相同。
5. 将 FGO 输出统一到 GNSS1 物理点、区分主动态输出与 prior-only、同时报告自身/共同支持。这些公平评价工作已经完成。
6. 官方 GINav 也已真实运行。早期解压阶段 BLOCKED 记录不能覆盖后来的运行与失败结果。

现在的主要任务是选择现有证据、使用正确结果版本，以及让不同层次的比较分别回答清楚的问题。

## 这次实际读到了哪一层

`SOURCES_READ.csv` 记录绝对路径、读取深度、用途、此次读取 SHA256。对部分大源码是全文获取后选段解释，未声称逐行人工审阅所有内容。

- 读取原 frozen V3 `MAIN_TABLE_V3.csv`，抽取全部 **16 条 LC01/LC01-S/EXT05C/EXT05C-S 自然条件**。
- 读取 HX03、R1、R2 的登记、更正和最终记录；读取全部 396 行结果、744 行配对和全部族统计。
- 直接读取 9 个 strict FGO 的实际 `RUN.json`、`ACCESS.json` 与全量 `STATES.csv`；RUN manifest **9/9**、STATES **9/9** 与原 `RUNS.csv` 哈希一致。BY2 3×285 行、BY2H 3×282 行、BY2O 3×420 行，包含窗外热身与无效状态，不能把行数直接当有效覆盖。
- 直接读取 3 个 segmented OiSAM 的 `RUN.json/BLOCKS.json/ACCESS.json/STATES.csv/SOLVER_EVENTS.jsonl`；读取全部 9 组主误差 CSV。
- 直接读取 HX03 A2 20 s、seed_00 的 LC01/EXT05C/LC01-BR 三支 COMMAND、PARAMS_ECHO、INPUT_HASHES、NATIVE_RESULT 和 stderr；三份 R2 留存误差均 58,014 行。
- 直接读取 GINav 三序列 COMMAND、GINAV_RUN、D8_BOUNDED_GATE、GINAV_EVALUATION。stdout 文件实际为空；执行证据来自 MATLAB command、returncode、native 输出哈希与 gate/evaluation JSON，未把空 stdout 描述为成功日志。
- 静态读取 IEKF 测量更新、HX03 注入和 relative-only 更新、OiSAM 缺口处理、Wen/GNC 实现；strict 三方法另读取 BY2 运行目录中的 SOURCE_SNAPSHOT 源文件。没有导入这些模块。

当前登记表 `EXPERIMENTS.csv` 共 **434 行证据身份**：16 自然 IEKF 条件 + 396 HX03R2 逻辑结果 + 9 strict FGO + 9 segmented 评价身份 + 3 GINav + 1 无缺口控制。它不是 434 次独立实验：A1、no-op、复用 native 的行均注明。

## 一、LC01、LIT/S、EXT05C：最近的融合路线和信息控制

### 实现身份

`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py` 实现 Pavlasek 等的两位置接收机 SE₂(3) IEKF：9 维 R/v/p，不估计 IMU bias。`PavlasekIEKF` 的 `two_receiver` 开关在同一传播和更新机械下选择双/单接收机；双接收机联合测量采用位置与相对基线，联合协方差保留 `[[R1,-R1],[-R1,R1+R2]]` 的相关结构。Van Loan、Joseph 更新、群误差注入均在代码中。

因此 **LC01 vs EXT05C 是已经存在的、共用骨架的观测信息控制**。EXT05C 在线只更新第一接收机位置，但其初始化仍用第二接收机形成初始方向；论文可称“单位置更新”，不宜称“从启动到运行完全单天线”。

LIT / S 是同算法的参数/标定条件。源码 `hext/ext05_sequence_runner.py` 的配置映射明确给出 LC01/EXT05C 与 LC01-S/EXT05C-S；S 采用本项目有效传感器模型，因此不能把两种配置当作两篇不同方法。自然主表的实际科学版本与原生哈希在每行 notes / NATIVE_SUMMARY 中保留。

### 已有自然工况成绩（V3 评价合同）

BY2H 下列采用 CONTRACT_START；另外 FILE_START 全部保存在 16 行原表中。

| 条件 | BY2 H RMSE m / yaw ° | BY2H H RMSE m / yaw ° | BY2O H RMSE m / yaw ° |
|---|---:|---:|---:|
| LC01 LIT | 0.097548 / 2.994827 | 0.074606 / 2.208612 | 0.054304 / 2.453697 |
| LC01 S | 0.103525 / 1.539239 | 0.0837 / 1.943003 | 0.0605 / 4.015602 |
| EXT05C LIT | 0.087751 / 12.048642 | 0.0692 / 20.108223 | 0.0520 / 5.845502 |
| LegSA-GINS frozen V3 | 0.097906 / 1.886272 | 0.068362 / 1.933770 | 0.054543 / 2.433815 |

上表足以说明为什么不能把论文写成所有指标全面胜出：LC01-S 的 BY2 yaw 比 LegSA-GINS 更低；LC01 LIT 与 LegSA 的自然位置误差接近。与此同时，双位置在线更新相对 EXT05C 显著改善了这些配置下的航向结果，已经有可讲清“外部方向约束作用”的实测材料。

BY2H 的 LC01/LC01-S 两起点共 4 行有几何审查 FAIL，原标记 `AVAILABLE_GEOMETRIC_AUDIT_FAIL` 不应丢失。EXT05C-S 的 BY2H FILE_START 原生发散另保留。此问题不是没有运行，也不是缺少数值，而是正确选择用途并保留条件。LIT 的主行选择带结果见后修订记录，不能重写成纯事前选择。

**建议论文用途：** IEKF-LIT 作为最近的外部融合路线；IEKF-S 表明参数条件敏感性；单位置更新作为信息控制。自然图需要同时看 heading 与位置，避免只挑最有利的一列。

原始入口：

- `/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/07_AGGREGATE/MAIN_TABLE_V3.csv`
- `/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/04_NATIVE_RUNS/{SEQ}/{METHOD}/{START}/NATIVE_SUMMARY.json`
- 本目录 `LC_NATIVE_TABLE_READ.csv` 为本次原字段抽取，不改变原数据。

## 二、HX03→HX03R2：已经完成的外部退化和基线保留控制

### 必须采用 R2 结果版本

HX03 当时的球面近似审查观察器与冻结 WGS84 评价器不一致，导致 146 条逻辑行被判审计不可用。R2 采用既有 WGS84 观察器后，492 个 v3/v2 评价槽全部通过原 D12；**984 份冻结科学 summary/error 与旧版本字节相同**。R2 的新增动作是审计重评，native 为 0，没有通过重跑算法换取较好结果。

当前状态为 **360/396 有限、36/396 原生发散、0/396 审计不可用**。36 发散全部来自 D14/D21 的 LC01/EXT05C，各型各方法 9/9。旧“LC01-BR 0/18 有效，所以不能判断”的描述已被 R2 更正。

### A2 已有真正运行的 relative-only 支路

源码 `hext/hx03_relative_update.py` 的 relative_update 使用 `(p2-p1)-R b`、协方差 `Rᵀ(R1+R2)R`，保留 Joseph 后验与原群注入；不更新绝对位置测量。`hx03_native.py` 在预登记 A2 窗由 `relative_only` 触发该函数。

本次追到三支 seed_00：20 s 窗为 **196.2–216.2 s**，同为 100 个位置历元。LC01/EXT05C 关闭相应位置更新；LC01-BR 的 INPUT_HASHES 记 `relative_only_epochs=100`，native 记录实际 relative-only 更新。三支共享 LIT 参数来源 SHA，姿态初值 STD 60°、位置/速度初值 STD 0.1 m / 0.1 m/s，gyro PSD `[0.0004,0.0004,0.000324]`、accel PSD `[0.0289,0.0225,0.0576]`。

| A2 两时长、9 seeds 共 18 例 | 有限数 | H RMSE 中位 m | yaw RMSE 中位 ° |
|---|---:|---:|---:|
| LC01 | 18/18 | 1.4073499261 | 2.9980624597 |
| EXT05C | 18/18 | 1.4222228466 | 12.4305669047 |
| LC01-BR（改动的 LC01） | 18/18 | 2.7857817730 | 2.9953496705 |

这里的科学信息很有价值：**在这套输入、状态和噪声条件下，保留基线方向并没有自行转化为较好的位置结果。** BR 的航向接近 LC01，但水平误差中位数更大。这一负结果能与本文“方向约束如何与机器人速度信息共同发挥作用”的内部实验形成解释关系，无需把它隐藏，也无需再把 BR 控制列为新实验。

已有 R2 配对表也逐例对齐了 F04/F02。以 A2 对 F04 的外部减本文差为例：LC01 H 差中位 **+1.1875448724 m**、yaw **+1.1128795423°**；BR H **+2.6011793966 m**、yaw **+1.1108442031°**，配对均 18。这里是同一注册退化案例下的系统比较，不能说整套在线输入完全相同，因为 F04 还有其他辅助。

### 哪些故障是等价控制

经典 18 型已有已实现扰动逐值复用，不需要重新造一套故障。D43、D42、D46/D47/D50 对这些滤波器属于未读通道，已有 C00 native 等价核验。D05 与 D03 的物理作用存在等价；A1 的 18 行是 LC01 A2 的等价报告。这些记录证明输入映射经过处理，同时意味着不能把 no-op 数量当作额外抗扰能力。

D31 的 LC01 跳过整次双位置更新，EXT05C 不受第二接收机影响；D57 的位置事件时移与 V3 无有效 scalar heading 是不同暴露。图表应按实际作用对象解释，不能仅按同名 D 编号声称完全相同信息。

原始入口：

- `/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv`
- 同目录 `DEGRADATION_PAIRED_R2.csv`、`DEGRADATION_EXTERNAL_SUMMARY_R2.csv`、`HX03R2_RESULTS.md`。
- `/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION/RUNS/BY2__LC01-BR__LIT__D62_20s_seed_00__seed_00/`
- 对应留存 error：`/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN9_EXTERNAL_COMPARISON/HX03R2_AUDIT_REEVAL/RUNS/BY2__LC01-BR__LIT__D62_20s_seed_00__seed_00/v3_R2/error_series_R2.csv.gz`

## 三、FGO：完整运行、缺测控制和统一评价已经完成

### 三篇路线的真实身份

- **OiSAM**：RTK 位置 + body IMU + 初始化方向，估计 R/p/v/两类 bias；实际 OB_GINS Earth 预积分、Givens / incremental QR、A-JSWR、边缘化与 Ceres 重线性化。不是用普通最小二乘改名，也没有在线双天线 heading factor。
- **Wen TC**：原始伪距、时钟、运动、外部 AHRS/INS 速度联系；实际 ECEF p/v/accel bias/钟偏批处理。姿态是 Go2 quaternion 等适配输入，不是其自行估计输出。
- **GNC**：原始伪距 + Doppler，ECEF 位置/钟偏图，GM 平方权重和 1.4 连续化；没有自行估计姿态。

三个 strict 运行实际源包含 base `0625cea...` 加 per-file overlay；已保存 source snapshot，不应只写 HEAD 就声称绑定全部执行源。源与配置已读，9 个 RUN/状态哈希已核。

### 严格协议与分段诊断各自回答不同问题

| OiSAM 协议 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| strict 一次初始化：有效/名义槽 | 275/275 | 0/271 | 55/378 |
| segmented 主动态输出：有效/名义槽 | 275/275 | 267/271 | 370/378 |
| segmented H RMSE m（GNSS1） | 0.097867 | 0.064957 | 0.052046 |
| segmented yaw RMSE ° | 4.652921 | 2.534907 | 3.971789 |

strict 的 H/O 支持不足是已记录真实 IMU 缺口触发的停机策略。segmented 事前以真实输入缺口分 11 块，各块一次合法 A1 初始化，块内不按失败重启，prior-only 不进主结果。BY2 是没有缺口的 exact 控制，因此对“缺测策略是否偷改估计核心”已有实际检查。

segmented 还完成 **GNSS1 同一物理点** 转换：OiSAM 用自身估计姿态运输 IMU→GNSS1；Wen/GNC 原输出即 GNSS1；没有用参考姿态改 OiSAM 结果。共同主支持为 **274/267/369**；保持原名义分母。本文 V3 的原中点评价不能未经同点处理就与 GNSS1 表直接作毫米差排名。

OiSAM 在 BY2O 3286 s 的 Ceres 返回 `NO_CONVERGENCE` 但 usable，20 次更新后 cost 182.2842→182.2721；原有限结果保留。已有矩阵秩、条件数、残差构成诊断与保存载荷，不能说没有处理过，也不能说问题已被修复至收敛。

Wen/GNC 主自身支持分别 274/270/377；H RMSE m 为 Wen **7.692119/7.672239/9.583724**，GNC **2.173504/2.134280/2.724164**。两者不能与 RTK 解级输入等价解释；Wen/GNC 也不是同状态同辅助，差值不能全部归因于鲁棒核。

### 图怎么复用

导航主比较优先围绕最近的 IEKF 与 OiSAM 展示位置、航向、输出连续性。strict OiSAM 展示真实输入缺口对连续导航的影响，segmented 作为明确恢复策略下的性能对照。Wen/GNC 可独立展示原始码层定位路线，避免米级图把 RTK 路线的厘米差淹没。

同一图中可以并列应用结果；图注一次说明各自输入与启动/重启策略，主文解释为什么选这些路线。无需把每个面板写成完整审计日志。

原始入口：

- strict：`/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z/runs/{SEQ}/{METHOD}/PAPER_CONTRACT/RUN.json`
- strict 表：`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/hext/FGO_REPRODUCTION_FIX_20261004/METRICS.csv`
- segmented：`/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z/`
- 无缺口控制：`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/FGO_COMPLETE_AUDIT_20261004/SEGMENTED_NATIVE_CHECKPOINT/BY2_NO_RESTART_CONTROL.json`

## 四、GINav 与鲁棒形状：不能把不同“未完成”混为一谈

GINav 官方 `bc6b3ab6c40db996a4fd8e8ca5b748fe21a23666` 已在 HX02 三序列真实运行。实际 MATLAB 命令、config、输出 SHA 与 returncode=0 保存；BY2/ O 随后的 D8 gate 判断速度越界，分别 244.999 s 的 50.639 m/s、3561.999 s 的 68.772 m/s。BY2H 2/271 支持，H约 2.8949 m、yaw约11.662°。早期归档元数据技术 stop 不是最新状态。

因此 GINav 用于展示 raw SPP/INS 及速度对准路线在当前平台数据上的启动/运行边界，已有结果足够作补充，不能再作为待实现项目。

7 类 Huber/Cauchy/Tukey/IGG3/Barron/DCS/switchable analogue 在 `source_aware_policy.cpp` 中是 OIM 等效 R 倍率形状，源码实现存在。当前本支检索已读 scope 表和实现，**尚未定位到可绑定 frozen V3 的这 7 类完整 native 性能矩阵**；此处状态是“运行结果待跨线核实”，不是“没有做”。`author_complete_algorithm_reproduction=false` 只说明不是七篇作者完整估计器，不能推出内部同骨架形状对照未做。不得从库代码存在反推每项已跑；也不得从作者复现 BLOCKED 反推内部对照没有结果。

## 五、可直接推进论文的内容与剩余定位事项

| 已完成、可整理复用 | 可支撑的论文任务 |
|---|---|
| LC01/EXT05C 同骨架、LIT/S 条件 | 外部方向观测价值与参数条件；最近融合路线 |
| Classic-18 与 R2 744 行配对 | 外部退化下的应用比较，不需要再做重复矩阵 |
| A2 LC01-BR 18/18 | 保留方向并不自动保证平移稳定，连接本文内部速度辅助证据 |
| OiSAM strict vs segmented + BY2 exact 控制 | 真实输入缺口、初始化与输出连续性的解释 |
| 三方法同 GNSS1、主动态/共同支持表 | 可公平读取现有 FGO 系统结果的基础 |
| GINav 实际 native 与 D8 | 传统 SPP/INS 路线的边界补充 |

本轮未提出必需新增实验。需要继续整理/核实的是：

1. 7 类鲁棒形状是否有其他阶段实际 native/summary（由内部证据线交叉检索）；找到后先分清 V3、早期诊断或独立研究版本。
2. 论文采用哪套 OiSAM 缺测策略作主比较，并保留另一协议结果。两套都已完成，属于叙述选择。
3. 已找到 V3 与 strict OiSAM 的 **POI 中点、共同时间支持表**，见下一节及 `V3_OISAM_EXISTING_COMMON_POINT.csv`。可直接复用它组织相同物理点比较。GNSS1 点的 segmented 三方法表继续按自己的已完成协议展示。
4. 选择少量真实工况区段，复用已保存误差、输出状态和事件生成读者图。本轮不重画。

从结果结构看，正文应让外部比较回答“这套系统在同一机器人数据上是否有实际竞争力”，让自身受控实验回答“它为什么有效”。已有 LC01-BR 和 OiSAM 连续控制可以成为两者之间的联系，而非继续增加算法数量。

## 六、有界补查：已完成同点对照与历史 QA 工作

### V3 / OiSAM 的同点、共同支持比较已经存在

准确源表：`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/docs/paper_rebuild/hext/FGO_REPRODUCTION_FIX_20261004/COMPARISON_TABLE.csv`，筛选 `support=COMMON_POI_OISAM_V3_TIME`。两者 `physical_point=POI_MIDPOINT`，不是把 V3 中点和 OiSAM GNSS1 生硬相减。原代码 `fgo_comparison/evaluation.py::output_at_poi` 已用 OiSAM 自身姿态完成物理运输；`report.py:76–101` 从留存 V3 误差按时间取点。

| 序列 | 共同匹配/原槽数 | OiSAM H m / yaw ° | V3 F04 H m / yaw ° |
|---|---:|---:|---:|
| BY2 | 274/275 | 0.1059533150 / 4.6594609942 | 0.0967573391 / 1.7781761781 |
| BY2H | 0/271 | NA / NA | NA / NA |
| BY2O | 54/378 | 0.0402854186 / 0.9859230838 | 0.0402802039 / 1.2111635437 |

BY2O 的短共同支持上，OiSAM 航向误差更低；不能只拿全窗 V3 和这 54 点数值比较，也不能删除这条不利于全面胜出叙事的结果。BY2H 空交集是 strict 缺口策略的事实。

本次逐行无损导出上述 6 行到 **`V3_OISAM_EXISTING_COMMON_POINT.csv`**，增加源 CSV 行号、全部已解析绝对路径、原误差字段名、误差文件行数/此次 SHA、匹配代码位置。6 个 curve 文件全部存在并已读：OiSAM 275/271/378 行（含无效占位），V3 56642/58580/76548 行。文件包含各自原误差全集；共同图沿原规则取同一 nominal second 距离 ≤5 ms，V3 同槽多个输出取最近时间，不看误差大小。此导出不重新运行 evaluator、不新算成绩。

### 历史 QA 不等于没有做，也不等于 frozen V3 实验

除 V3 七类 R 倍率 scope 外，这次在仓库历史目录实际找到：

`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001/suanfahengxiangduibi/PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC/02_evidence_consolidation/qa_full_matrix_evidence.csv`

这份历史汇总记录 PAPER2A 选取 **NIS χ² FDE、RAIM residual FDE、Huber IRLS、IGG-III、GNC Geman–McClure、robust adaptive KF、Doppler consistency QC** 七类 QA，完成 BY2 **840/840**、BY3 **497/497**、XB **560/560**，共 **1897 个可评价行**，并将逐行性能限定为 common-backend QA-wrapper evidence。记录写明 trace_used_online=false 与 receiver IMU 不作 body IMU；这里仅转述历史记录，不把它升级成本轮重新核证。

它所指的 `PAPER2A_METHOD_SELECTION_TABLE.csv`、`PAPER2A_SUPERVISOR_FINAL_REPORT.md`、`PAPER2A_ROW_LEVEL_MASTER_TABLE.csv` 本次尚未定位到原始载荷。当前 Git 文件清单、`git log --all -- '*PAPER2A*'`、G:/export 与 G:/handoff 文件名检索无对应命中。`legacy_freeze_202607/selected_reports/LEGACY_STAGE_INDEX.md` 明确旧 PAPER0–PAPER10 保留 selected specs/claim limits，performance rows 已 retired。

还在 `src/legsa_gins/reporting/by2_algorithm_runner.py:531–604` 找到 QA11E 的实际配置别名：`qa11e_huber_weight_EKF`、`qa11e_cauchy_weight_EKF`、`qa11e_tukey_biweight_EKF`、`qa11e_igg3_weight_EKF`、`qa11e_barron_loss_EKF`、`qa11e_dcs_weight_EKF`、`qa11e_switchable_weight_EKF`，均是旧共用骨架上的 R 形状实例；另有 QA11G 具体文献衍生别名与测试。静态代码不等于执行回执；目前不能把 PAPER2A 的 1897 行自动绑定到这七个 QA11E 别名，更不能当作 frozen V3 结果。

因此准确结论是：**历史 QA 大矩阵有“完成过”的项目记录；原行载荷待定位。当前七种 covariance 形状的实现身份已定位，独立 native 性能结果仍待绑定。** 这比“七种外部算法没做”更符合记录，也保留了作者算法复现与内部共骨架比较之间的区别。

最终有界内容检索覆盖 G: 下 CLEAN2/CLEAN3/CLEAN4 的 10 个 stage 根，以及当前仓库 `docs/paper_rebuild/hext`、`configs/paper_rebuild`；最大深度 5、单文件 ≤2 MiB，文本类型 md/json/csv/yaml/yml/txt，排除 error_series/NAV/INNOVATION/NIS 逐历元载荷。`rg --stats` 实际报告 **10,601 files searched，269,368,539 bytes searched，8 files contained matches**。命中是 GINav 的 IGG3 路线声明、旧 Yin 代码来源审查、OiSAM Gaussian/Huber 配置差别及 GNC 作者库边界，没有发现这七种 R 形状对应的独立 native 结果表。具体根、过滤条件、命中文件和原始统计保存在 `BOUNDED_ROBUST_SEARCH.json` 与 `BOUNDED_ROBUST_SEARCH_STATS.txt`。另查旧仓库 `suanfahengxiangduibi`、`docs/codex_context`、legacy selected_reports/specs/lessons，才找到上述 PAPER2A 历史完成汇总。此结论限于明确检索范围，不推断全磁盘或其他归档不存在结果。
