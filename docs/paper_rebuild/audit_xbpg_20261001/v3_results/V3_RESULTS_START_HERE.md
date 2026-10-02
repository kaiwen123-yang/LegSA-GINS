# Protocol V3 既有结果入口

本目录收集既有结果，保留其原始状态和版本。它不宣布数学审查完成，也不改变此前的缺陷、覆盖率和硬停记录。工作起点为审查分支 `audit/code-xbpg-20260105-20261001` 的 `ed74ca06dc8d146b9bf620cf81549edfa14f8fef`。

## 先打开什么

1. [V3_RESULTS_OVERVIEW.md](V3_RESULTS_OVERVIEW.md)：自然三序列、Canonical-541、A1/A2、全消融、分段、配对及不确定度的原有数字与分母。
2. [V3_RUN_RESULT_INDEX.csv](V3_RUN_RESULT_INDEX.csv)：全部正式物理运行，关联双评价口径、失败、支持时间和保留位置。全量原有逐运行统计在 `run_statistics/`：CORE 按 `EVALUATION_CORE_v3_F04.csv` 这样的评价版本/方法命名，每份 541 行；ADDENDUM、SEQUENCE 另表。`FAILURE_RUNS.csv` 为全部 283 个失败，`NATURAL_C00_ALL_CONFIGS.csv` 为全部 33 个自然配置。
3. [V3_RESULT_FILES.csv](V3_RESULT_FILES.csv)：文件及明确归档成员的实际读取状态、行数、字段与原始路径；存在性不等于已读取。
4. [V3_TABLE_FIGURE_SOURCES.csv](V3_TABLE_FIGURE_SOURCES.csv)：阶段图与后续论文表图分别追到来源。
5. [COLLECTION_RECEIPT.json](COLLECTION_RECEIPT.json)、[RUN_COLLECTION_SUMMARY.json](RUN_COLLECTION_SUMMARY.json)、[TABLE_COLLECTION_SUMMARY.json](TABLE_COLLECTION_SUMMARY.json)：实际计数、缺项和本轮读取边界。

## 实际位置怎样打开

共享文件仅用别名，机器根映射从已忽略的 `configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml` 解析。
本轮生成的 `configs/paper_rebuild/V3_RESULTS_ROOTS.local.json` 给出 WSL/Windows 根映射；本目录忽略的 `V3_RESULT_FILES.local.csv` 把共享索引逐行解析成真实可打开位置。两份本机文件不上传 GitHub。

| 别名 | 作用与入口 |
| --- | --- |
| `<CODE_ROOT>` | 当前审查 worktree；包含本目录及既有审查记录 |
| `<AUDIT_SOURCE_WORKTREE>` | 原 `clean3-math-repair` 工作树；保留源表原位置，未自动以当前工作树替换 |
| `<CLEAN_ROOT>` | local YAML 的 `clean_root`，不是项目盘根 |
| `<V3_ROOT>` | `<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`；正式结果根，在经 `findmnt` 核实的 G: 挂载上 |
| `<PROTOCOL_V3_SCRATCH>` | 旧运行暂存与保留元数据；历史 scratch 路径不能冒充当前结果位置 |
| `<PROTOCOL_V3_ARCHIVE>` | local YAML 中的旧 ext4 归档线索；本轮核实该目录不存在 |
| `<HANDOFF_ROOT>` | 既有旧协议、外部、敏感性和不确定度 ZIP；并无最终 Protocol V3 ZIP |

正式根中首先打开 `FINAL_RUN_RECORDS.json`、`FINAL_EVALUATION_RECORDS.json`、`07_AGGREGATE/MAIN_TABLE_V3.csv`、`07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv`。前两份大总账原位保留；本目录提供完整逐运行统计阅读入口。

## 两层全集，四种版本

A 为 Protocol V3 自有正式运行：CORE 5,951（含 BY2 C00）、BY2H/BY2O C00 共 22、ADDENDUM 495。预期 6,468 个 native 身份、每个 v3/v2 两个评价槽；以实际注册表和总账核对结果为准。F03=A02、F04=A01 是别名，不能增加分母。

B 为展示引用的其他材料：CLEAN6 的协议 v2.1、CLEAN7 的外部/敏感性、后续外部比较、UA-01/UA-02 不确定度及 `paper_package/gpss_v0`。它们保留自己的身份和用途；外部结果有表，不表示目标论文已完整复现。

分别阅读 `protocol_id`（实验协议）、`evaluator_contract`（评价口径）、manifest/论文映射（展示版本）和 `run_id` 加 native/config 哈希（物理身份）。文件名 `V3`、最新时间或 `FINAL` 字样均不足以单独选定来源。旧包 `c541_v2_handoff_v3.zip` 中的 v3 是包修订版本。

## 哪个版本被采用

| 材料 | 本次采用/保留关系 |
| --- | --- |
| 正式运行和评价 | 顶层两份 FINAL 总账对独立注册表；原始状态不重新分类 |
| 阶段结果表 | `07_AGGREGATE/` 实际 51 CSV；`MAIN_TABLE_V3.csv` 为 52 行 |
| 最终全消融/失败附表 | `07C_FAILURE_FAMILY_CONFIG/` 的 7 CSV；完整消融 33 行；其同名 V21 比较表和旧 `07_AGGREGATE` 表分开登记 |
| F01 分类溯源 | `07D_CLASSIFICATION_PROVENANCE/` 的 20 行表和 manifest；上述三处合计 59 CSV |
| 阶段图 | `08_FIGURES/` 的 10 组/30 导出，由 `09_HANDOFF/VISUAL_REVIEW.json` 与 FINAL_DELIVERY 绑定；PREVIOUS 另列历史 |
| 统一失败后续记录 | `07E_UNIFIED_FAILURE/` 的硬停/续作；未冒充统一分类已经完成或替换正式终态 |
| 不确定度 | 原 UA-01/UA-02 表和 pin，单列后处理版本，不重新计算 |
| 论文展示 | `paper_package/gpss_v0/` 的现有 24 表、10 图；原 TABLE_MAP/FIGURE_MAP/NUMBER_LEDGER 保持原样 |

来源关系表有 1,065 行，不是 1,065 次实验。源表读取登记为 189 CSV / 791,937 CSV 记录、111 JSON、50 文本；记录数包含原始与展示副本、长表、既有诊断表，不能当运行分母。V3_REPORT_SOURCE_INDEX 的 17 项全部定位（14 CSV、1 selection JSON、2 config/contract），单独保留 B 身份。

已有两项历史 pin 与当前原工作树文件字节不同：`<AUDIT_SOURCE_WORKTREE>/AGENTS.md`、`<AUDIT_SOURCE_WORKTREE>/paper_package/gpss_v0/FIGURE_MAP.csv`。[SOURCE_PIN_DIFFERENCES.csv](SOURCE_PIN_DIFFERENCES.csv) 与索引同时保留 recorded 和 verified 哈希；不据此改写原 pin 或自动选更晚版本。当前审查工作树的来源快照与原工作树分开。

## 保留规则与历史状态

正式收尾采用 `09_HANDOFF/FINAL_DELIVERY.json` 及其绑定的表格/视觉回执。`08_FIGURES/RENDER_MANIFEST.json` 内的旧 `PENDING_ACTUAL_RASTER_REVIEW`、`DONE.json` 内旧 package pending 字段与后续回执按时间和用途并列；不改写旧文件。`PREVIOUS` 和原硬停保留为历史。

原 V3 收尾明确 `SKIPPED_BY_USER`，本轮不制作 ZIP。full NAV/STD/EVAL_NAV、部分 strace 和未入保留集合的 error_series 按已有规则释放；具体文件依据 receipt 分类。稀疏 NAV、matched trajectory 和 full NAV 分别登记，不能互相替代。收尾访问回执曾记载 native strace 512 份重新解析、5,956 份已释放，evaluator strace 1,024 份重新解析、11,346 份已释放；这是原回执的历史审计口径，本轮没有把它改称新的 strace 全量审计。失败后未调用的评价槽仍保留，缺失指标不填零。

## 本轮操作边界

只读取、解析、关联、排序、计数和转录既有记录；归档只读明确成员，没有执行其代码。没有 solver、provider generator、evaluator、聚合控制器、重放、RMSE/bootstrap/CI 重算、绘图、科学代码修复、XB 执行、清理或新 ZIP。旧审查的待核查事项仍见 [原 FINAL_SUMMARY](../FINAL_SUMMARY.md)、[FINDINGS](../FINDINGS.csv) 和 [METHOD_IDENTITY](../METHOD_IDENTITY.csv)。

复查脚本位于 `scripts/paper_rebuild/collect_v3_run_results.py`、`collect_v3_table_sources.py`、`collect_v3_existing_results.py`。仅运行这些独立收集脚本的明确入口；不要调用历史 controller 或实例化运行 Context 来浏览结果。


## 直接看小型表

- [MAIN_TABLE_V3](source_tables/MAIN_TABLE_V3.csv)：15 个内部展示行与 37 个外部行。
- [FULL_ABLATION_TABLE_V3](source_tables/FULL_ABLATION_TABLE_V3.csv)：三序列全部 11 配置。
- [CORE_541_SUMMARY_V3](source_tables/CORE_541_SUMMARY_V3.csv)：每配置注册/有限/失败分母及跨案例分布。
- [FAILURE_FAMILY_CONFIG](source_tables/FAILURE_FAMILY_CONFIG.csv)：594 个分组单元格；同时包含协议/评价版本，不能直接加成失败运行数。
- [BY2O_SEGMENT_TABLE](source_tables/BY2O_SEGMENT_TABLE.csv)：150 行，包含局部、全窗及段外。
- [PAIRWISE_SUMMARY_V3](source_tables/PAIRWISE_SUMMARY_V3.csv)：490 行已有配对统计和区间。
- [TABLE_COLLECTION_NOTES](TABLE_COLLECTION_NOTES.md)：不确定度、外部引用、图表和数字账本的详细阅读入口。

这些共享浏览表只增加原 source_path/row_key（通常以 `_source_` 前缀命名），原指标列及字符串不变。较大的 B 表按 `table_views/` 分片/投影，省略列与原表入口明确登记；A 的全量指标在 `run_statistics/`。


## 最终获取状态

本轮状态：**RESULT_RECORDS_COLLECTED_WITH_DOCUMENTED_RELEASES_AND_PIN_DIFFERENCES**。注册表/两份总账逐键一致；缺 native/评价槽、重复身份、逐例结果与总账差异、应保留未找到文件、读取错误均为 0。现有审查文件 62/62 本轮前后 SHA256 不变。

合并索引有 184,702 条读取/保留观察，覆盖 184,657 个不同来源位置；包含已释放路径、同一路径的独立登记和归档成员，不能称作这么多当前存在的结果文件。另将 PREVIOUS/PREVIOUS_REVIEW_DOCS 中 49 个历史文件独立登记，当前采用版本不变。

| 对象 | 本轮取得情况 | 未取得载荷的准确解释 |
| --- | --- | --- |
| native / evaluator 结果 JSON | 6,468 / 12,936，全部解析 | 0 缺项；566 未调用槽也有记录 |
| evaluator summary / capture / access-audit | 各 12,370，全部解析 | 未调用槽不冒充进程 |
| native manifest / runtime config | 6,378 / 6,468，全部解析 | 90 个无有效 heading 失败未生成 manifest |
| 完整 NAV / STD | 原值哈希及释放凭据取得，载荷均不在保留集合 | 各 6,378 按策略释放、90 失败未生成；不能从稀疏/匹配文件重建 |
| error_series | 2,308 个 gzip 文件入口与表头可读，每评价版本 1,154 | 10,062 按策略释放，566 失败未生成 |
| matched trajectory | 1 个 gzip 入口/表头和完整 manifest | 其它成功槽无该成员登记；不能假设每个运行都有 matched 文件 |
| 原 strace | native 512 / evaluator 1,024 实物存在，仅核对元数据 | native 5,956 / evaluator 11,346 有释放凭据；本轮未解析其日志内容 |
| 既有 B ZIP | 6 个中央目录、36 个明确表成员已解析 | 未宣称读完所有 ZIP 成员；无最终 Protocol V3 ZIP 是原用户省略决定 |
| 展示来源 | 17/17 report-source 入口；189 CSV、111 JSON、50 文本 | 0 来源未找到；2 个历史 pin 差异单列 |

计划保留集合为 1,188 个 native，其中 1,154 完成、24 divergence、10 no-heading；34 个失败对应 68 个未生成的评价序列，解释 2,376 计划槽与 2,308 实际 error_series 的差额。本轮没有补跑它们。

共享文件索引约 78.9 MB，完整运行索引约 39.1 MB；为保留全量身份和位置而保留较大的文本索引。日常阅读优先小型源表与按方法拆分的 `run_statistics/`。重复 schema/说明通过 [FILE_SCHEMA_INDEX.csv](run_statistics/FILE_SCHEMA_INDEX.csv) 引用，receipt 的 `@receipt` 语法见 [RUN_COLLECTION_NOTES](RUN_COLLECTION_NOTES.md)。`RUN_RESULT_FILES.csv` 是忽略的本地中间文件，其全部记录已合入共享 `V3_RESULT_FILES.csv`，不在 Git 再存一份。

既有结果表已全部实际读取；大载荷的存在性/表头核查不是全量载荷解析。B 中原来作为直接来源的三份 error_series CSV 是例外，已由表来源收集器完整读取，但没有复制进 Git。所有来源、缺项与释放分类都限定于注册表、总账和已登记展示来源链，没有全盘搜索或声称全盘逐文件审核。
