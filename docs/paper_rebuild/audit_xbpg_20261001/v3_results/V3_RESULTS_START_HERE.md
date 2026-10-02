# Protocol V3 既有结果入口

本目录收集既有结果，保留其原始状态和版本。它不宣布数学审查完成，也不改变此前的缺陷、覆盖率和硬停记录。工作起点为审查分支 `audit/code-xbpg-20260105-20261001` 的 `ed74ca06dc8d146b9bf620cf81549edfa14f8fef`。

## 先打开什么

1. [V3_RESULTS_OVERVIEW.md](V3_RESULTS_OVERVIEW.md)：自然三序列、Canonical-541、A1/A2、全消融、分段、配对及不确定度的原有数字与分母。
2. [V3_RUN_RESULT_INDEX.csv](V3_RUN_RESULT_INDEX.csv)：全部正式物理运行，关联双评价口径、失败、支持时间和保留位置。全量原有逐运行统计在 `run_statistics/`。
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

## 保留规则与历史状态

正式收尾采用 `09_HANDOFF/FINAL_DELIVERY.json` 及其绑定的表格/视觉回执。`08_FIGURES/RENDER_MANIFEST.json` 内的旧 `PENDING_ACTUAL_RASTER_REVIEW`、`DONE.json` 内旧 package pending 字段与后续回执按时间和用途并列；不改写旧文件。`PREVIOUS` 和原硬停保留为历史。

原 V3 收尾明确 `SKIPPED_BY_USER`，本轮不制作 ZIP。full NAV/STD/EVAL_NAV、部分 strace 和未入保留集合的 error_series 按已有规则释放；具体文件依据 receipt 分类。稀疏 NAV、matched trajectory 和 full NAV 分别登记，不能互相替代。失败后未调用的评价槽仍保留，缺失指标不填零。

## 本轮操作边界

只读取、解析、关联、排序、计数和转录既有记录；归档只读明确成员，没有执行其代码。没有 solver、provider generator、evaluator、聚合控制器、重放、RMSE/bootstrap/CI 重算、绘图、科学代码修复、XB 执行、清理或新 ZIP。旧审查的待核查事项仍见 [原 FINAL_SUMMARY](../FINAL_SUMMARY.md)、[FINDINGS](../FINDINGS.csv) 和 [METHOD_IDENTITY](../METHOD_IDENTITY.csv)。

复查脚本位于 `scripts/paper_rebuild/collect_v3_run_results.py`、`collect_v3_table_sources.py`、`collect_v3_existing_results.py`。仅运行这些独立收集脚本的明确入口；不要调用历史 controller 或实例化运行 Context 来浏览结果。
