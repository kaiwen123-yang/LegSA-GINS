# V3 源表读取说明与原数值摘录

本文件说明表与图来源收集的实际读取结果；运行身份、失败与每个评价槽以同目录的 `V3_RUN_RESULT_INDEX.csv` 为准。下面的数字均来自已存在的 CSV/JSON，未重新计算 RMSE、分位数、bootstrap 或置信区间。

## 读取覆盖和入口

表来源收集器实际完整解析 **189 份 CSV，共 791,937 条数据记录，111 份 JSON**，另完整读取 **50 份文字文件**。这些记录含同一结果的多种汇总、两种评价口径、原工作树与当前工作树副本、已有时间序列，**不是 791,937 次实验**。文件登记共 483 项；其余 120 项为存在性已核对而载荷未解析，13 项为源代码入口存在且未执行。此计数是表来源子集，不能代替整个交付的合并文件清单。

`TABLE_RESULT_FILES.csv` 给出每份原文件的表头、实际读入行数、状态、原始 SHA256 记录与本轮已读字节 SHA256。`V3_TABLE_FIGURE_SOURCES.csv` 有 **1,065 条来源关系**，含结果表关联、10 组阶段图、24 个论文表映射、11 个论文图映射行（10 个图 ID）、207 个原有数字台账条目，以及 HX-05 的精确单元格来源。

最容易直接阅读的完整源表视图：

- [MAIN_TABLE_V3.csv](source_tables/MAIN_TABLE_V3.csv)：52 行，包含 15 个 V3 五配置自然序列展示行与 37 个保留的外部行。
- [FULL_ABLATION_TABLE_V3.csv](source_tables/FULL_ABLATION_TABLE_V3.csv)：全部 33 个自然序列评价行，三序列各 11 配置。
- [FAILURE_FAMILY_CONFIG.csv](source_tables/FAILURE_FAMILY_CONFIG.csv)：594 行；原零计数保留。
- [BY2O_SEGMENT_TABLE.csv](source_tables/BY2O_SEGMENT_TABLE.csv)：150 行；含两种评价口径、内部配置、外部与敏感性来源。
- [CORE_541_SUMMARY_V3.csv](source_tables/CORE_541_SUMMARY_V3.csv)、[CORE_541_FAMILY_SUMMARY_V3.csv](source_tables/CORE_541_FAMILY_SUMMARY_V3.csv)、[CORE_541_TYPE_SUMMARY_V3.csv](source_tables/CORE_541_TYPE_SUMMARY_V3.csv)：依次为配置、族、类型级既有汇总。
- [PAIRWISE_SUMMARY_V3.csv](source_tables/PAIRWISE_SUMMARY_V3.csv)：490 行既有配对统计。逐例配对与分布视图按文件拆分，入口在 `TABLE_RESULT_FILES.csv` 的 `shared_view`。
- [ADDENDUM_FAMILY_SUMMARY_V3.csv](source_tables/ADDENDUM_FAMILY_SUMMARY_V3.csv)：A1/A2 全配置分族汇总。

每个新源表视图添加 `_source_path` 与 `_source_row_key`。后者的 `data_row_1based:N` **不含表头**，原行身份字段和原字段名保留；源数值和状态词不改。数值字段的空串、`UNAVAILABLE`、`NOT_APPLICABLE` 不转换成零。路径前缀替换成已解析别名。

大型 A 表已经完整读入，完整逐运行评价统计由 `run_statistics/` 的评价记录收集提供，不再次复制约 57 MB 的 CORE 原表。大型 B 旧协议/敏感性浏览表保留所有行、身份、终态、支持数、RMSE/P95 的原始字符串；省略列逐一记于 `TABLE_COLLECTION_SUMMARY.json` 的 `large_table_projections`，原始完整表留原位并可按索引读取。该浏览投影不冒充完整原表副本。没有把 error_series、NAV、STD 或 raw 载荷放入新 Git 文件。

## 表的分母与版本

实际读取的收尾 59 CSV 完整对账：`07_AGGREGATE` **51** 份、`07C_FAILURE_FAMILY_CONFIG` **7** 份、`07D_CLASSIFICATION_PROVENANCE` **1** 份。另读 `07E_UNIFIED_FAILURE` 的 **22** 份后续审查 CSV 与其硬停/续作记录，保留为后续待核查历史；不把它们替代 59 份收尾表。`10_UNCERTAINTY` 有 14 份 CSV；仓库 `docs/paper_rebuild/v3/uncertainty/` 有 23 份 CSV，后者包括后续 UNC 表与对应 UA-01 表，不增加 native 分母。

| 原结果表（v3、v2 每版） | 实读行数 | 阅读分母 |
|---|---:|---|
| CORE_541_TABLE | 5,951 | 541 案例 × 11 配置，失败也有行 |
| ADDENDUM_TABLE | 495 | A1 的 27 案例、A2 的 18 案例，各 11 配置 |
| SEQUENCE_TABLE / FULL_ABLATION_TABLE | 33 | 三自然序列 × 11；其中 BY2 C00 已属于 CORE |
| SUBSET61_TABLE | 671 | CORE 既有 61 案例 × 11，不是新增运行 |
| MAIN_TABLE | 52 | 15 个内部展示行 + 37 个保留外部行 |
| ABLATION_TABLE | 15 | 五配置展示梯 × 三序列 |
| CORE_541_SUMMARY | 77 | 11 配置 × 7 指标 |
| CORE_541_FAMILY_SUMMARY | 693 | 11 配置 × 9 族（含 clean）× 7 指标 |
| CORE_541_TYPE_SUMMARY | 4,697 | 11 配置 × 61 类型（含 CLEAN）× 7 指标 |
| CORE_541_DISTRIBUTION | 39,676 | 有限案例指标的排序记录；失败不被当作有限数值 |
| PAIRWISE_CASE_LEVEL | 25,284 | 既有有限配对的逐案例、比较、指标行 |
| PAIRWISE_SUMMARY | 490 | 既有比较 × 指标 × overall/family 汇总 |
| ADDENDUM_FAMILY_SUMMARY | 154 | 11 配置 × 2 族 × 7 指标 |
| T5BCR_REFERENCE_THREE_SEQUENCES | 15 | 独立候选敏感性展示行，属于 B |
| T5BCR_REFERENCE_SUBSET61 | 183 | 已有候选敏感性选取，属于 B |

`FAILURE_FAMILY_CONFIG.csv` 的 594 行分别为 `(evaluator=v3, protocol=v3)` 198、`(v2,v3)` 198、`(v3,v2.1)` 99、`(v2,v2.1)` 99。不能把这 594 行理解为 594 个失败或 594 次运行。`07D/F01_IDENTICAL_NAV_CLASSIFICATION.csv` 有 20 条历史分类来源记录；后续 07E 硬停同样保留，本轮不裁决其科学可靠性。

**实验 Protocol V3、评价器 v3/v2、表的修订版本、物理 run_id 是四个不同轴。** `CORE_541_V21_COMPARISON_V3.csv` 是 V3 对 v2.1、采用评价器 v3；文件名中的 `V21` 不是评价器 v2。07C 的同名比较表仅修订 `v21_failure` 分类字段；其原 manifest 记载 `numeric_tokens_changed=0`，原 07_AGGREGATE 表仍在索引中，不能按同名覆盖。

## 自然三序列

全部 11 配置读 `FULL_ABLATION_TABLE_V3.csv`，五配置展示读 `ABLATION_TABLE_V3.csv`。F03/A02、F04/A01 是配置别名；不重复形成物理运行。以下为原源表里的 F04 值，单位分别为 m 和 deg：

| sequence_id | horizontal_rmse_m | yaw_rmse_deg |
|---|---:|---:|
| BY2 | 0.09790607774950152 | 1.8862718548526467 |
| BY2H | 0.06836245149191253 | 1.93377013508875 |
| BY2O | 0.054543210912875166 | 2.433814932823714 |

来源：`07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv`，键 `(sequence_id, method_id=F04)`。这些是各自完整窗支持，不能用后文共同支持的 paired RMSE 覆盖。BY2O 同表 F02 yaw 为 `2.309490986722553` deg，低于 F04 的 `2.433814932823714` deg；BY2 的 A04 水平 `0.09691990156944293` m，低于 F04 `0.09790607774950152` m。这只是现有行的排序描述，不是机制或显著性结论。

## Canonical-541

下表逐字摘录 `CORE_541_SUMMARY_V3.csv` 的 `horizontal_rmse_m` 与 `yaw_rmse_deg`。每配置 registered=541；mean/median/p95 使用原表有限分母，不能视为把失败补零后的均值。

| method_id | finite / 541 | failures | horizontal median m | horizontal P95 m | yaw median deg | yaw P95 deg |
|---|---:|---:|---:|---:|---:|---:|
| F01 | 521 | 20 | 0.09261054876350382 | 3.0181413938779036 | 8.089647422454789 | 40.611345267892865 |
| F02 | 498 | 43 | 0.10199492498489396 | 3.0080284475367183 | 2.231952255808013 | 3.3709281530825943 |
| F03 | 512 | 29 | 0.1002369468362462 | 3.0214369297083286 | 1.9155910498740765 | 9.592960818858016 |
| A04 | 513 | 28 | 0.09784136547266481 | 3.015940224356186 | 1.886000833151237 | 2.7461951021142736 |
| F04 | 519 | 22 | 0.09822807379435361 | 3.5510500790754915 | 1.8862717388088417 | 2.4465376134717114 |

完整 77 行包括另外六个消融配置。各族与 D01–D60 的配置结果、失败/有限数见 family/type summary；全部 case/seed/method 原评价见运行索引与 `run_statistics/`。`CORE_541_DISTRIBUTION` 中 P95 是 across-case 的阈值；`worst_5pct_mean` 是原有最坏 5% 均值，二者不能互换。两种评价器各保留自己的表。

## A1/A2

A1/D61 为 10/20/30 s × 9 种子，A2/D62 为 10/20 s × 9 种子。原 ADDENDUM 表每版 495 行，原族汇总中各配置 A1 的 finite/registered=27/27、A2=18/18；失败列仍保留。

`ADDENDUM_FAMILY_SUMMARY_V3.csv` 中 F04 水平 RMSE：A1 median=`10.107797646034916` m，P95=`42.42440238675533` m；A2 median=`0.17667112573862742` m，P95=`0.2877465570267067` m。F03 对应 A2 median=`2.850680656057537` m，P95=`17.11498668249498` m。这些为全窗结果，不能改称中断区间内 RMSE。分时长原统计见 `UA01_ADDENDUM_STATS.csv`（264 行）与 `UA01_ADDENDUM_PAIRED.csv`（96 行）；原始逐种子统计保留在 ADDENDUM 逐运行评价中。

## BY2O 分段与段外

`BY2O_SEGMENT_TABLE.csv` 的 v3 F04 原行 71–75（不含表头）为 full、primary、secondary、inside_union、outside。primary=`[3369.94,3411.95]` s、secondary=`[3495.94,3508.94]` s，端点及 union/outside 定义原样保留。

| segment | F04 yaw RMSE deg | F04 支持历元 | LC01 yaw RMSE deg | LC01 支持历元 |
|---|---:|---:|---:|---:|
| full | 2.433814932823714 | 76548 | 2.4536970334279924 | 78441 |
| occlusion_primary | 0.2325140820805299 | 7612 | 4.008201405335621 | 7823 |
| occlusion_secondary | 1.861542194198912 | 2754 | 6.174020555087572 | 2819 |
| inside_union | 0.9799785484386794 | 10366 | 4.680528011199139 | 10642 |
| outside | 2.5885939307825425 | 66182 | 1.8780275781753495 | 67799 |

LC01 为 `FILE_START` 文献配置，源行 1–5；F04 为 `FROZEN_V21_RUNTIME_CONFIG`。两方法支持历元不同。primary 的排序在 outside 反转；不能将局部区间推广为全序列普遍优于。表后半的评价器 v2 行保留，不以数值大小选口径。

## 既有配对、分位数与不确定度

`PAIRWISE_SUMMARY_V3.csv`，键 `(comparison=full_vs_strong, metric_name=yaw_rmse_deg, scope=overall, family=ALL)`：finite pairs=`512`，median delta=`-0.02935448271831105` deg，原 median CI95=`[-0.0294778148435411,-0.0293191950214298]`，win_count=`506`。同一比较水平 mean CI95 为 `[-0.05939601061052893,0.00411440964962635]` m，含零。原 bootstrap 设定为 n=10000、seed=20260904，本轮仅读取。

`full_vs_no_SA` 的水平 median delta=`0.00098121009139` m，finite=513，win_count=115；yaw mean delta=`-1.7389797737493646` deg，而 yaw median delta=`0.0002579935045803` deg。原均值、尾部与中位数可呈不同方向，不应从某一个汇总量推断普遍收益。

仓库不确定度文件可直接阅读，未复制成同名新权威：

- `docs/paper_rebuild/v3/uncertainty/UA01_DISTRIBUTION_QUANTILES.csv`：44 行，按类型 cluster 与 naive 的既有区间分别保留。
- `UA01_PAIRED_OVERALL.csv`：20 行；其退化集 registered=540，排除 C00，因此 F04–F03 的 finite pairs=511，与阶段含 C00 的 512 不矛盾。
- `UA01_TYPE_SEED_DISPERSION.csv`：2,640 行；`UA01_PAIRED_CASE_VALUES.csv`：10,112 行；`UA01_PAIRED_CASE_DIFFERENCES.csv`：1,200 行。
- `UNC_DISTINGUISHABILITY.csv`：56 行配对；`UNC_REALIZATION_INTERVALS.csv`：111 行窗实现区间；`UNC_BUDGET.csv`：13 行。字段名 `rmse_recomputed` 是 UA-01/UA-02 当时的列名，并不表示本轮重新计算。

`UNC_DISTINGUISHABILITY.csv` 原 `pair_A_minus_B=LC01-F04, metric=yaw, segment=full`：BY2 的 delta=`1.1103372814582677` deg、MBB95=`[-0.2151695911095197,2.5738499973094195]`，共同支持 56628；BY2H delta=`0.2741892278945445` deg、MBB95=`[-0.0520599344381443,0.5142639522923124]`，共同支持 58554；BY2O delta=`0.0174754860961838` deg、MBB95=`[-1.3442060289453843,1.4010706010080711]`，共同支持 76166。原 verdict 分别为 `DIRECTION_ONLY`、`DIRECTION_ONLY`、`PARITY`。它们与全窗单方法 RMSE 的支持不同，不互相替代。

## B：展示引用的旧协议、敏感性和外部来源

`V3_REPORT_SOURCE_INDEX.json` 的 **17 个明确文件入口均已实际读取**：14 个结果 CSV、1 个 selection JSON、2 个契约/配置文件。包括：

- CLEAN6 v2.1：core 每评价器 5,951、addendum 495、sequence 33 行。完整表实际读入；浏览投影按方法拆分，保留所有行。它们是对照协议，不计为 A 的新 V3 运行。
- H-EXT-04L：MAIN_TABLE 每评价器 52 行，BY2O_SEGMENT_SUMMARY 90 行及原 selection JSON。
- T5bc-R：PILOT_TABLE 每评价器 36 行、SUBSET61_TABLE 每评价器 305 行、SUBSET61_SUMMARY 18 行。阶段选取的 15/183 行敏感性表并非独立新增矩阵。

论文包 `TABLE_MAP/FIGURE_MAP/READ_FILES` 引用 HX-05 汇编。已沿其 `SOURCE_CITATIONS.json` 与 `D43_SOURCE_CITATIONS.json` 继续读到：

| 原始来源 | 实读记录 |
|---|---:|
| HX02 / EXTERNAL_FIVE_CATEGORY_TABLE.csv | 480 长表指标行 |
| HX02E / HARTLEY_OFFICIAL_TABLE.csv | 96 长表指标行 |
| HX03R2 / DEGRADATION_EXTERNAL_TABLE_R2.csv | 396 逐例指标行 |
| HX03R2 / DEGRADATION_EXTERNAL_SUMMARY_R2.csv | 186 汇总行 |
| HX03R2 / DEGRADATION_PAIRED_R2.csv | 744 配对行 |
| HX03R2 / STATE_TRANSITIONS_R2.csv | 62 审计状态行 |
| HX05 / RUNS/{BY2,BY2H,BY2O}/RESULT.json | 3 个既有 LEG-DR 结果对象 |

HX-05 主展示 14 个身份、补充 12 个身份、退化表 9 个族，D43 单独补充。三序列某些单元格为 heading-only 有效率/valid RMSE/hold RMSE，某些为相对位姿漂移，某些为 IMU-point navigation RMSE；原类型与分母全部保留。外部表存在不等于论文算法已完整复现，也不允许跨输出类型平排精度。

本次还完整读了 3 个外部保留 error_series CSV：BY2 LC01 58014 行、BY2H LC01 59934 行、BY2O LC01 78441 行；以及 HX02 BY2O 6 个 heading error series 各 1885 行。它们是**既有评价输出**，不是原始 reference trace。没有从这些序列重新求指标；载荷继续留原位，不推到 GitHub。A 的逐运行时间序列保留状态由运行收集器登记，不能把这里的 B 全读状态推广给 A。

## 表图采用版本与缺项

阶段 `08_FIGURES/RENDER_MANIFEST.json` 的 MFIG00–MFIG06、SFIG01、FIG02S、FIG02S-b 为 10 组/30 导出。论文包的 Fig01–Fig08、SFig01–SFig02 为另一个 10 组/30 导出，来源地图 11 行包含 Fig01 两个 panel。论文 Fig01/b 仍标 `PLACEHOLDER_NEED_PHOTO`。格式三份并非三次实验；SFig02 的复制来源可追到阶段 SFIG01，其余同名关系不自动合并。

阶段图的 manifest 只在部分图给出精确 source_rows。图关系表保留实际源文件、caption 指明的 case/method/比较键、确切的 run-specific series，以及 FIG02S/FIG02S-b 的完整源行身份；未给出的精确行选择明确写 unknown/未枚举。阶段与论文的已有机器/视觉验收是历史记录，本轮只确认图导出入口，没有重新看图或重绘。

当前表来源子集没有未找到文件，也没有需要从归档才能读取的表。归档全局定位由总入口页另行报告，不能从本子集推出所有运行载荷都已取得。

两个**历史 recorded pin 与当前原工作树字节不同**，不删除、不自动选新版：

| 原工作树文件 | recorded SHA256 | 本轮 verified SHA256 |
|---|---|---|
| `<AUDIT_SOURCE_WORKTREE>/AGENTS.md` | `6e0190994d953ab819bb801c77ee0f9d8b2b5cbb2529fc78cd6c53437024c7e1` | `df4c615dcd8c40114257a232844e582f0e67db975749193aea303c121f1b8b40` |
| `<AUDIT_SOURCE_WORKTREE>/paper_package/gpss_v0/FIGURE_MAP.csv` | `631e3adf90480a1e38212b02ea701af85c8b3750de6421c4580fb7e83414c9c1` | `2d05a9f4203721145d015c58011649e48a947dbe4ced8149a5af9abc6c1bbfd2` |

本文实际采用的是当前审查工作树中存在的论文映射，并保留其原文件引用。207 项数字台账中，73 个直接 CSV 数值按**原台账指定的行筛选、列、正则和显示小数位**逐项相符；其余 134 项是文件文字/YAML/既有派生表达式，只保留来源，没有执行新的派生检验。这不是对论文所有数字或科学正确性的 PASS。

已有 07E 硬停与旧缺陷清单仅建立待审来源链接。数学解释、算法审核、缺陷影响、修复、插桩、重放、重新评价、文献复现与下一阶段实验均未进入本次范围。
