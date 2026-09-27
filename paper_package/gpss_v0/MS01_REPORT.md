# MS-01 执行报告

成稿 v0 已完成；保留明确的作者待补项。提交与推送的最终回执随本报告全文回贴。

工作树：`/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair`；分支：`stage/clean3-math-repair`。
起点：`5007bf1149b028f323573cc178cd925060f2c35f`；按续作指令核验通过。起点状态为指定 29 条未跟踪基线加已有报告目录。

## 交付与词数

交付主稿、补充材料、中文逐节说明、参考请求、数字台账与检查器、图表及来源映射。主稿包含 Abstract、1–9 节和 Declarations；主表 1–8、补充表 S1–S10 共拆为 24 份 CSV。图 1–8 与 S1–S2 共 10 张，每张有 PNG/PDF/SVG；图 1 另登记照片占位。

正文 **9871 词**；摘要 **209 词**。计数为英文词，连字符词计一次，排除表格、图表注、节标题、公式、摘要、声明和参考文献。

| 节 | 词数 |
| --- | ---: |
| 1 Introduction | 670 |
| 2 Related work | 724 |
| 3 Platform, sensors and data | 866 |
| 4 Method | 2017 |
| 5 Experimental design | 1648 |
| 6 Results | 2583 |
| 7 Discussion | 736 |
| 8 Limitations and future work | 431 |
| 9 Conclusions | 196 |

数字台账：**207 PASS / 0 FAIL**。CSV 按唯一行条件定位；DOC/YAML 按行或键校验；差值方向和百分比转换按输入 claim_id 复算。每次数字出现单列登记，表格单元由 TABLE_MAP 定位。结构编号、型号和代数常数不作为实验量值。参考请求 12 项、正文 13 处引用占位，现有书目信息按库存 reference 字段原文复制。

## 图与 QA

| 状态 | 数量 |
| --- | ---: |
| DRAWN_SCHEMATIC | 2 |
| REDRAWN | 4 |
| COPIED | 4 |
| PLACEHOLDER_NEED_PHOTO | 1 |
| SOURCE_MISSING | 0 |

11 条面板记录对应 10 张图。新图为 174 mm 双栏宽；PNG 宽 4110 px。复制图宽 4180–4183 px，PNG/PDF/SVG 与来源逐字节一致。

| 图 | qa.py 通过 / 失败 | 实际 PNG 检视 |
| --- | --- | --- |
| Fig01 | 7 / 0 | PASS |
| Fig02 | 6 / 0 | PASS |
| Fig03 | 7 / 0 | PASS |
| Fig04 | 7 / 0 | PASS |
| Fig05 | 7 / 0 | PASS |
| Fig06 | 7 / 0 | PASS |
| Fig07、Fig08、SFig01、SFig02 | 复制，不重新构造画布；格式与来源哈希通过 | 4 / 4 PASS |

新图机器 QA 合计 **41/41**；实际图像检视 **10/10**。Fig. 6 采用已有逐例 RMSE 点，避免为作图新算时长分组 median/P95。图内未发现需替换的 Truth 标签；图 7 的 “F04 reference” 是比较线，图注已说明。

## 边界与 Git 复核

解算器 / 评估器 / provider / 外部方法二进制 / MATLAB 调用：**0 / 0 / 0 / 0 / 0**。参考原始轨迹读取 **0**。只使用允许的聚合表、方法源码和保留误差序列；未读取原始 trace、bag、fpl 或 MATCHED_TRAJECTORY。G: 写入 **0**。上述为本次命令和输入清单记录，不冒充 strace 全系统审计。

没有运行既有实验脚本，没有重算科学指标或 bootstrap。数字核对只校验已有量值及文本中的代数派生。未创建交接包。`figures/_build/` 已删除；包约 6.8 MB，低于 200 MB 上限。

第一次提交前后及第二次提交前，**既有未跟踪 29/29 不变**，逐文件 SHA256 与 MS01_BASELINE.json 一致。未改写、暂存、移动或删除这些文件。非授权新增或变化路径 **0**。第二次提交后再次核验同一基线，并在最终回贴提供结果。

第一提交：`fa119c2b6928458249f354b459ba3d853e2f99ef`
`MS-01 manuscript v0 part 1: tables, figures, setup, method, results`

第二提交信息：`MS-01 manuscript v0 part 2: front/back matter, supplement, notes`。本报告属于该提交；可用 `git log -1 --format=%H -- paper_package/gpss_v0/MS01_REPORT.md` 取得确切哈希。为避免提交内容与自身哈希循环依赖，确切第二提交哈希和 push 输出放在最终回贴，不另建第三次提交。

## 问题、证据修正与作者待补

1. 0.205 s 时标修正未在指定文件找到同值可引用字段；现有表给约 0.2067 s，未替换含义，正文保留 NEED。实际 IMU 流频率也保留 NEED，未以配置频率冒充采集事实。
2. F03 未启用 RP；F02→F03 同时涉及接收机速度和航向门控，不能写成单独 RP 收益。F03−F02 的配对航向差按来源写为 −0.32°/−0.34°。
3. LC01 roll 三序列更低，pitch 仅 BY2/BY2O 更低；BY2H pitch 是反例。A1 各配置有同类漂移增长，不能写成数值逐项相同。F02 A2 P95 依源值写 17.077 m。
4. 指定 UNC03 原文逐字保留，但共同参考项在 MSE/RMSE 差中一般不会严格抵消，正文紧接交叉项限定。原文的所有估计器相同、约半数贡献等概括在 NOTES_ZH 标为待作者收紧；未做方差扣除。
5. F04−F03 故障配对胜率摘要缺少明确配对分母，正文保留 NEED，不套用其他配对分母。照片、正式书目、repository/DOI、基金、贡献和利益冲突确认也列为作者待补。
6. 外部实现身份按库存区分官方库和文献复现，未把所有实现称为原作者代码。LC01-S、BY2O 的 F02 优势、非独立参考、时间戳暴露差异均保留。
7. 图 QA 的 numpy.bool_ 在保存时转为 bool；首次绘图日志写入竞争改为顺序记录。分段选行明确限定当前 evaluator 合约。以上均未触发科学重跑。

## 耗时与读取清单

本次续作起点时间：2026-09-27T10:54:25.717957+00:00；报告封口检查时间：2026-09-27T11:22:16.248804+00:00。至此耗时 **27.84 分钟**；后续提交和推送耗时见终态回执。

READ_FILES.json 登记 92 个输入/控制/图源条目及 SHA256、字节数；其中包含本任务自己的 FIGURE_MAP 读取记录。AGENTS.md 仅作规则/追加段格式来源，不取旧结果数值。全部条目如下。路径别名 W 为上述工作树，V3 为只读结果根，SCRATCH 为 `/home/kaiwen/research/LegSA-GINS-SCRATCH`，CLEAN_ROOT 为 `/mnt/g/LegSA-GINS-project/clean_rebuild_202607`。

```text
$SCRATCH/CLEAN7_HEXT_EXTERNAL_SEQUENCES/H_EXT_02/07_OFFLINE_EVALUATION/v3/BY2H__LC01__CONTRACT_START/EXACT_EVALUATOR_OUTPUT/error_series.csv
$SCRATCH/CLEAN7_HEXT_EXTERNAL_SEQUENCES/H_EXT_03/07_OFFLINE_EVALUATION/v3/BY2O__LC01__FILE_START/EXACT_EVALUATOR_OUTPUT/error_series.csv
$W/AGENTS.md
$W/configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml
$W/configs/paper_rebuild/clean5/CLEAN5_BY2H_SEQUENCE_CONTRACT.yaml
$W/configs/paper_rebuild/clean5/CLEAN5_BY2O_SEQUENCE_CONTRACT.yaml
$W/configs/paper_rebuild/clean6/ADDENDUM_FAMILIES_A1_A2_CONTRACT.yaml
$W/configs/paper_rebuild/degradation_60types_9seeds.yaml
$W/configs/paper_rebuild/final_v23_parity_contract.yaml
$W/configs/paper_rebuild/methods.yaml
$W/configs/paper_rebuild/v3/PROTOCOL_V3_CONTRACT.yaml
$W/cpp/legsa_v23_port_core/include/legsa_v23_port_core/options.hpp
$W/cpp/legsa_v23_port_core/src/factors/go2_weak_prior_loader.cpp
$W/cpp/legsa_v23_port_core/src/factors/raw_doppler_factor.cpp
$W/cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp
$W/cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp
$W/docs/paper_rebuild/ACTIVE_CONTEXT.md
$W/docs/paper_rebuild/CLEAN5_PARITY_PLAN.md
$W/docs/paper_rebuild/CLEAN5_SENSOR_CALIBRATION_RECORD.md
$W/docs/paper_rebuild/CLEAN5_STAGE2_CLOSEOUT.md
$W/docs/paper_rebuild/CONVERSATION_HANDOFF.md
$W/docs/paper_rebuild/DATA_ROLES.md
$W/docs/paper_rebuild/PROTOCOL_V2_METHOD_STATEMENT.md
$W/docs/paper_rebuild/hext/HX02/HX02_RESULTS.md
$W/docs/paper_rebuild/hext/HX02D/HX02D_HARTLEY_DIAGNOSTIC.md
$W/docs/paper_rebuild/hext/HX02E/HX02E_RESULTS.md
$W/docs/paper_rebuild/hext/HX02_PREREG.md
$W/docs/paper_rebuild/hext/HX05/BY2O_SEGMENT_TABLE_EXT.csv
$W/docs/paper_rebuild/hext/HX05/CAPTIONS_HX05.md
$W/docs/paper_rebuild/hext/HX05/D43_VELOCITY_NOISE_SUPPLEMENT.csv
$W/docs/paper_rebuild/hext/HX05/DEGRADATION_MANUSCRIPT.csv
$W/docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv
$W/docs/paper_rebuild/hext/HX05/EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv
$W/docs/paper_rebuild/hext/HX05/FIG02D.pdf
$W/docs/paper_rebuild/hext/HX05/FIG02D.png
$W/docs/paper_rebuild/hext/HX05/FIG02D.svg
$W/docs/paper_rebuild/hext/HX05/FIG02S.pdf
$W/docs/paper_rebuild/hext/HX05/FIG02S.png
$W/docs/paper_rebuild/hext/HX05/FIG02S.svg
$W/docs/paper_rebuild/hext/HX05/HX05_CLOSEOUT.md
$W/docs/paper_rebuild/hext/HX05/LEG_DR/BY2/RESULT.json
$W/docs/paper_rebuild/hext/HX05/LEG_DR/BY2H/RESULT.json
$W/docs/paper_rebuild/hext/HX05/LEG_DR/BY2O/RESULT.json
$W/docs/paper_rebuild/hext/HX05/MANUSCRIPT_DATA.json
$W/docs/paper_rebuild/hext/HX05/MANUSCRIPT_TABLES_FULL.md
$W/docs/paper_rebuild/hext/HX05/SFIG-HX.pdf
$W/docs/paper_rebuild/hext/HX05/SFIG-HX.png
$W/docs/paper_rebuild/hext/HX05/SFIG-HX.svg
$W/docs/paper_rebuild/hext/HX05/SOURCE_CITATIONS.json
$W/docs/paper_rebuild/hext/HX05_PREREG.md
$W/docs/paper_rebuild/hext/HX_INVENTORY.md
$W/docs/paper_rebuild/hext/T5A_R_HEADING_SENSITIVITY.md
$W/docs/paper_rebuild/v3/ERROR_SERIES_RETENTION_INDEX.csv
$W/docs/paper_rebuild/v3/PROTOCOL_V3_PREREG.md
$W/docs/paper_rebuild/v3/V3_01R_MANUSCRIPT_REPLACEMENT.md
$W/docs/paper_rebuild/v3/uncertainty/UA01_INPUT_SHA256.json
$W/docs/paper_rebuild/v3/uncertainty/UNC01_UNCERTAINTY_BUDGET.md
$W/docs/paper_rebuild/v3/uncertainty/UNC02_DISTINGUISHABILITY.md
$W/docs/paper_rebuild/v3/uncertainty/UNC03_MANUSCRIPT_TEXT.md
$W/docs/paper_rebuild/v3/uncertainty/UNCERTAINTY_HANDOFF.md
$W/docs/paper_rebuild/v3/uncertainty/UNC_BUDGET.csv
$W/docs/paper_rebuild/v3/uncertainty/UNC_DISTINGUISHABILITY.csv
$W/docs/paper_rebuild/v3/uncertainty/UNC_HORIZONTAL_BODY_DECOMPOSITION.csv
$W/docs/paper_rebuild/v3/uncertainty/UNC_REALIZATION_INTERVALS.csv
$W/docs/paper_rebuild/v3/uncertainty/UNC_SEED_DISPERSION_SUMMARY.csv
$W/docs/paper_rebuild/v3/uncertainty/UNC_YAW_DECOMPOSITION.csv
$W/paper_package/gpss_v0/FIGURE_MAP.csv
$W/src/legsa_gins/paper_rebuild/publication/qa.py
$W/src/legsa_gins/paper_rebuild/publication/style.py
$CLEAN_ROOT/stages/CLEAN5_DEGSUBSET_BY2/09_HORIZONTAL_V3/LC01_EXT05A/FROZEN_EVALUATOR/error_series.csv
$V3/04_EVALUATION/RUN_00004/v3/FROZEN_EVALUATOR/error_series.csv.gz
$V3/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2H_F04/v3/FROZEN_EVALUATOR/error_series.csv.gz
$V3/04_EVALUATION/V3R_CONTINUATION/SEQUENCE_BY2O_F04/v3/FROZEN_EVALUATOR/error_series.csv.gz
$V3/07C_FAILURE_FAMILY_CONFIG/FAILURE_FAMILY_CONFIG.csv
$V3/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv
$V3/07_AGGREGATE/ABLATION_TABLE_V3.csv
$V3/07_AGGREGATE/ADDENDUM_SUMMARY_V3.csv
$V3/07_AGGREGATE/ADDENDUM_TABLE_V3.csv
$V3/07_AGGREGATE/BY2O_SEGMENT_TABLE.csv
$V3/07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv
$V3/07_AGGREGATE/CORE_541_SUMMARY_V3.csv
$V3/07_AGGREGATE/MAIN_TABLE_V3.csv
$V3/07_AGGREGATE/SUBSET61_SUMMARY_V3.csv
$V3/07_AGGREGATE/SUBSET61_TABLE_V3.csv
$V3/07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_TAIL_SUMMARY.csv
$V3/07_AGGREGATE/T5BCR_REFERENCE_SUBSET61_V3.csv
$V3/07_AGGREGATE/T5BCR_REFERENCE_THREE_SEQUENCES_V3.csv
$V3/08_FIGURES/CAPTIONS.md
$V3/08_FIGURES/FIGURE_INDEX.md
$V3/08_FIGURES/SFIG01/SFIG01.pdf
$V3/08_FIGURES/SFIG01/SFIG01.png
$V3/08_FIGURES/SFIG01/SFIG01.svg
```

辅助规则读取：记忆索引 MEMORY.md 的任务边界条目，以及 data-analytics:visualize-data 的 SKILL.md；仅用于执行与图形 QA 约定，不提供论文结果数字。生成文件的自检读取不另当作科学输入。
