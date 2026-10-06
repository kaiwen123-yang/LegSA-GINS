# CLEAN4 / CLEAN7 既有横向结果：阅读入口

本目录只收集旧结果与来源，不新增科学性能。EXT01/02 的优先子项见 [EXT01_EXT02_EVIDENCE.md](EXT01_EXT02_EVIDENCE.md)，EXT03 见 [EXT03_EVIDENCE.md](EXT03_EVIDENCE.md)。两个阶段的正式/诊断表、全部方法/起点、失败槽和源版本完整保留在 [CLEAN4_CLEAN7_INDEX.csv](CLEAN4_CLEAN7_INDEX.csv)；小型完整表副本在 [horizontal_sources](horizontal_sources/)。本机完整工作索引的所选 CSV 原数据行以 `data_row=N` 登记，`source_values_json` 保存原字符串；较长原生历元表有完整源副本，不再膨胀成第二份逐单元格索引。

实际根由 ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json` 解析：

- `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`
- `<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES`
- `<HANDOFF_ROOT>` 内的明确交接 ZIP，见后文。
- `<EXT_REPRO_ROOT>/existing_clean.local.csv` 保存本目录索引的真实本机路径镜像及少量未纳入常用根的历史路径绑定，不进入 Git。

## CLEAN4：按信息层读取，不做跨层总排名

先读 `13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/00_METHOD_REGISTRY/FINAL_METHOD_REGISTRY_V2.csv` 的全部 11 项：RAW01/RAW02/RAW03 分别为旧 EXT01/EXT02/EXT03，EXT04 是附加诊断模块，LC01 是 Pavlasek 双接收机，LC02 是 GINav，LSE01 是 Hartley，另有 F02/F03/A04/F04。RAW 编号是登记别名，不是新增运行。

`12_FINAL_EVIDENCE_INTEGRATION/FINAL_C00_NATIVE_FORMAL_RESULTS.csv` 全 6 行已读。下列数值仅转录该表，单位水平 RMSE 为 m、yaw RMSE 为 °：

|method_id|matched_rows|coverage|horizontal_rmse_m|yaw_rmse_deg|
|---|---:|---:|---:|---:|
|GINAV|77|0.28|130.8187259110151|69.75333248293973|
|LC01|58014|1.0|0.1691391165921043|2.9948274600591076|
|F02|56642|1.0|0.35552607969271205|2.3384266253352437|
|F03|56642|1.0|0.352517110036549|1.9624133174349125|
|A04|56642|1.0|0.35238638733674005|1.9340756561653565|
|F04|56642|1.0|0.3548025409632719|1.9549590248265367|

表的 `evaluation_scope` 不同，matched rows 也不同，不能把 coverage 都解释成同一采样分母。GINav 正式窗分母 275，原生输出 80 行、有效匹配 77 行，旧摘要记录 48/116 个 SPP 有效、11 次 LC 更新、对齐延迟 113.002 s。稀疏覆盖没有被隐藏。

另一份 `FINAL_C00_COMMON_SUPPORT_DIAGNOSTIC.csv` 也是 6 行，但仅为 77 个 GINav 目标历元的共同支持诊断；原 literal 时间交集为 0，其他方法使用已有、与参考无关的包围插值。其 `diagnostic_only=true`、`eligible_for_primary_table=false`，不能替换正式全窗表，也不能冒充原生共同时间戳排名。

`13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/02_RAW_DUAL_ANTENNA/` 的所有汇总已读；raw 方法输出是 baseline/heading，未登记为完整位置导航。EXT04 原记录为 40743 个 policy 行中 0 accepted，187 FAR rejected、4368 PAR exhausted、36188 invalid，属于附加失效/适用性诊断，不计作三篇 raw 方法之一。

Hartley 在该旧阶段的角色是无全局锚定的 contact-aided InEKF 结构/gauge/可观测性证据；旧登记有 63277 原生行，但 reference 安装/坐标关系未闭合，不能用其结构验证表替代绝对位置或 yaw 性能。已读取最终 gauge/rank/NIS/topology 小表，保留原有 real/synthetic/结构角色；没有运行合成例。后续 HX-05 的新结果不倒填此阶段。

Yin/Chang 候选排除、EXT05B 未实现、GINav 保留尝试和 relocation ledgers 也已登记。旧 HORIZONTAL18 / legacy final_v23 仅保留当前索引中的身份与不适用说明，未打开其旧性能载荷作为新证据。CLEAN3 引用只定位；本轮不重复读取它的大矩阵，CLEAN4 已有的小型横向汇总仍保留原版本。

## CLEAN7：三序列、两个参数版本与两个 BY2H 起点

`08_AGGREGATE/HORIZONTAL_TABLE_V2_THREE_SEQUENCES.csv` 和 `HORIZONTAL_TABLE_V3_THREE_SEQUENCES.csv` 各 52 行，全列全文读取。每版包含：15 行旧内部方法、16 行 LC01/EXT05C 系列外部结果、21 行明确 `UNAVAILABLE`。52 行不是 52 次 native，`v3` 是评价口径身份，不等于 Protocol V3 自有新运行。

外部 16 行覆盖 BY2 的 LIT/S 四项、BY2H 的 LIT/S × FILE_START/CONTRACT_START 八项、BY2O 四项。每版外部状态为 11 `COMPLETED`、4 `AVAILABLE_GEOMETRIC_AUDIT_FAIL`、1 `NOT_RUN_ALGORITHM_FAILURE`。表中 unavailable 行保留原状态词和原因，没有把缺指标填为零。

下列完整 16 行水平/yaw 主读数直接来自 v3 主表；其余位置/姿态/尾部、v2 对照、body-frame bias、coverage 都在完整副本。

|原数据行|序列/方法/起点|h_rmse_m|yaw_rmse_deg|评价状态|
|---:|---|---:|---:|---|
|16|BY2 LC01 LIT FILE_START|0.0975479714305497|2.9948274600591076|COMPLETED|
|17|BY2 EXT05C LIT FILE_START|0.0877508129138417|12.048641737808111|COMPLETED|
|39|BY2 LC01-S S FILE_START|0.10352490362681992|1.5392385536245534|COMPLETED|
|40|BY2 EXT05C-S S FILE_START|0.11422779709467196|9.7220981511841|COMPLETED|
|41|BY2H LC01 LIT FILE_START|0.09745269819180266|2.1739364356142343|AVAILABLE_GEOMETRIC_AUDIT_FAIL|
|42|BY2H LC01 LIT CONTRACT_START|0.0746064486934978|2.208612313835051|AVAILABLE_GEOMETRIC_AUDIT_FAIL|
|43|BY2H EXT05C LIT FILE_START|0.1972843996333379|55.609933584769315|COMPLETED|
|44|BY2H EXT05C LIT CONTRACT_START|0.06918972281588827|20.108223061254332|COMPLETED|
|45|BY2H LC01-S S FILE_START|0.10670864118045774|1.7940541340876093|AVAILABLE_GEOMETRIC_AUDIT_FAIL|
|46|BY2H LC01-S S CONTRACT_START|0.08373314985151889|1.9430028350481119|AVAILABLE_GEOMETRIC_AUDIT_FAIL|
|47|BY2H EXT05C-S S FILE_START|UNAVAILABLE|UNAVAILABLE|NOT_RUN_ALGORITHM_FAILURE|
|48|BY2H EXT05C-S S CONTRACT_START|0.08541883542514975|8.114756205259614|COMPLETED|
|49|BY2O LC01 LIT FILE_START|0.05430420090026619|2.4536970334279924|COMPLETED|
|50|BY2O EXT05C LIT FILE_START|0.05195371361637804|5.845502312798482|COMPLETED|
|51|BY2O LC01-S S FILE_START|0.06046245535470896|4.015602467888004|COMPLETED|
|52|BY2O EXT05C-S S FILE_START|0.07507995368164405|8.266805432879499|COMPLETED|

BY2 LC01 的旧 CLEAN4 水平数 0.1691391165921043 与 CLEAN7 v3 数 0.0975479714305497 来自不同已登记评价口径/物理点；此处分别保留，未择好数替换旧表。BY2H 起点明显影响 EXT05C 的 yaw 表现，但本轮只描述差异，不推断单一机制。

`03_CONTINUATION/EXECUTION/EXECUTION_RECORDS.json` 的 14 个 native 身份及 `08_AGGREGATE/FINAL_SUMMARY.json.result_sources` 指向的 28 个 v2/v3 最终槽已全部读取，包括未调用槽。14 项终态是 13 completed、1 diverged；28 槽为 18 completed、8 geometric-audit-fail、2 not-run。另两行 BY2 LIT 使用既有 CLEAN4 native，所以主表外部身份为 16。旧收尾的 evaluator 累计实际调用数是 27，包含历史失败；这与最终终态槽 28 不同，也不是本轮调用数。

具体 `EVALUATION_RESULT.json.row` 的原状态是 26 `COMPLETED`、2 `NOT_RUN_ALGORITHM_FAILURE`；其中 8 槽在最终汇总的入表分类中标为 `AVAILABLE_GEOMETRIC_AUDIT_FAIL`。索引把 `EXISTING_EVALUATION_RESULT` 与 `FINAL_EVALUATION_DISPOSITION` 分列，保留两层原词；不能为了对齐分类计数改写 evaluator 原状态。

失败身份 `BY2H__EXT05C-S__FILE_START` 的原 `NATIVE_SUMMARY` 写进程完成，而 continuation 的 bounded gate 将其分类为 `ALGORITHM_FAILURE_DIVERGED`；两份原词均保留。旧 gate 记录第一超界数据行 2446、`time_seconds=418.59999990463257`、`speed_mps=51.19872445663034`，后续 final evaluation 槽未调用。没有把“进程完成”当作轨迹有效，也没有重读 NAV 来重新诊断。

## 最终展示版本与图的关系

旧 H-EXT-03 `08_AGGREGATE/FINAL_SUMMARY.json.selection` 依据 BY2 yaw 选 LC01-S；`11_READONLY_CLOSEOUT_H_EXT_04L/figures/HEXT_RENDER_MANIFEST.json.selection` 后续明确改选 LIT / LC01，保留 `amended_after_results_seen=true`、`prior_selected_method_id=LC01-S`，S 放补充。两份选择同时保留；不能用文件时间或“FINAL”字样自行择真。

closeout 的 `MAIN_TABLE_V2.csv`、`MAIN_TABLE_V3.csv`、`LC01_BOTH_CONFIGURATIONS_ALL_METRICS.csv` 和两个 scoreboard 全读。`BY2O_SEGMENT_SUMMARY.csv` 的 90 行及状态/窗口/端点列、其他 yaw/IMU/status 诊断小表也全读。这是既有分段分析；没有读取 error_series 或重新计算区间指标。

CLEAN4 `14_HORIZONTAL_FULL_PLOTTING/PLOT_CATALOG.csv` 有 66 组，源表/格式路径和全部目录可查；ZIP 中的 catalog 也是 66 行。CLEAN7 `10_FIGURES` 是旧 H-EXT-03 FIG02S，closeout 是后续 FIG02S 与 FIG02S-b，旧图另存 `previous_H_EXT_03`。本轮只核格式文件存在及 manifest，不重绘、不做新 raster QA。PNG/PDF/SVG 不是多次实验。

## 归档、没有取得的载荷与本轮计数

[LINKED_ARCHIVE_INDEX.csv](LINKED_ARCHIVE_INDEX.csv) 把旧/后续交接包分开：

- `<HANDOFF_ROOT>/hext_three_sequences_handoff.zip`：存在，570 个目录项；本轮只读 3 个旧 hard-stop 小成员，不能称完整任务交付包。
- `<HANDOFF_ROOT>/hext_three_sequences_handoff_v2.zip`：存在，770 个目录项；本轮只读 8 个指定运行、主表、汇总和保留 hard-stop 成员。
- `<HANDOFF_ROOT>/c541_v21_handoff.zip`：存在，4700 个目录项；只读 `sequence_error_series_subset/SUBSET_MANIFEST.csv`。读取 manifest 不等于读到其中每条 error_series，gzip 正文未读。
- CLEAN4 阶段内 `14_HORIZONTAL_FULL_PLOTTING.zip`：存在，只读其 central directory 和明确的 `PLOT_CATALOG.csv` 成员，未解压全部图片。

所有目标最终小表及 28 个最终评价槽已实际取得。图/时间大载荷为元数据检查，既有 SRC044–SRC054 等 CLEAN3 大矩阵引用为范围外定位；不冒充全文读取。CLEAN7 `SOURCE_RESOLUTION.json` 原先明确 BY2H/BY2O A04/F04 的全采样 NAV 不在当时 finalize/交接包中，保留其 `FULL_RATE_NAV_SEALED_NOT_RETAINED_ABSENT_FROM_FINALIZE_AND_VERIFIED_PACKAGE` 历史说明；本轮没有据此宣称刚发生数据丢失、用稀疏 NAV 替代或重建载荷。

第二收集子项全文读取 83 个 loose CSV、168 个 JSON、21 份正文，外加 CLEAN4 ZIP 的 1 个 catalog；CSV 数据行共 41460（其中包含不同版本/视图，不能相加成实验数）。另外 735 个唯一路径仅元数据检查。随后三个明确 handoff 只读 12 个小成员，详见各自回执，不算新试验。EXT01/02 前一子项的 22 CSV / 32191 行独立登记，重合来源只交叉引用，不再重复打开其正文。

本轮 native、provider、evaluator、指标重算、新 SHA-256 均为 0。全部 raw/reference 与 error-series 载荷读取为 0。源数字保留原字符串；哈希是 recorded hashes，未填为 newly verified。公开文本只使用别名。旧 source/manifest/claim 状态均未改写；下一阶段是否能复现和科学结论是否可靠，仍需独立验证。

公开副本范围：完整读取后，公开索引保留运行、评价、源表及载荷入口；重复逐单元格库存与较大源表副本留在 `<EXT_REPRO_ROOT>/collection_detail/existing_clean/`，详见 `PUBLIC_REDUCTION.json`。原 CLEAN4/CLEAN7 文件未移动。`horizontal_sources/` 中仅为必要小表副本；未公开副本仍可从索引原路径打开。
