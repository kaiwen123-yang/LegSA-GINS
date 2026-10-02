# CLEAN4 的 EXT01 / EXT02 既有结果与诊断入口

本小项只转录既有结果，不复评、不做新实现诊断。根目录是 `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`；真实路径由 ignored `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json` 解析。逐文件、原字段和版本见 [EXT01_EXT02_INDEX.csv](EXT01_EXT02_INDEX.csv)；完整小型源副本在 [ext01_ext02_sources](ext01_ext02_sources/)。CSV 的 `source_row_key=ALL_DATA_ROWS_1_BASED` 指原表所有数据行，JSON 使用 `$.字段`。数值不从图或四舍五入正文提取。

## 应先打开的原始证据

|对象|原路径（相对本阶段根）|本轮读取|判定层级|
|---|---|---|---|
|EXT01 当前旧 R2|`11_REPORT/PHASE1R_R2_EXT01_C00_VALIDITY_REPORT.md`；`02_EXT01_CLAMBDA/C00_VALIDATED_R2/EXT01_C00_VALIDATED_SUMMARY.json`|完整正文及 JSON|`UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION`；保留旧适用性结论，不升级成这轮已确认的因果解释|
|EXT01 R1 历史阻断|`11_REPORT/PHASE1R_STATUS.json`；`PHASE1R_EXT01_C00_VALIDITY_REPORT.md`|完整|`BLOCKED_PHASE1R_SEARCH_OBJECTIVE_CROSSCHECK_FAILED`，不能被 R2 覆盖掉|
|EXT02 原生|`03_EXT02_CWLS/C00/EXT02_C00_NATIVE_SUMMARY.json`；`EXT02_C00_NATIVE_FREEZE.json`|完整|原生终态 `PASS_PHASE2_EXT02_CWLS_C00_READY_FOR_NATIVE_COMPARISON`，其中 `evaluation=NOT_EVALUATED` 是原生摘要的原词，不否定后续存在诊断|
|EXT02 最终旧诊断恢复|`03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1/EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json`|完整|`PASS_PHASE2_EXT02_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`；`ready_for_paper_claims=false`|
|EXT02 恢复报告|`11_REPORT/PHASE2_EXT02_C00_REPORT_PROXY_TIME_ASSOCIATION_R1.md`；`PHASE2_STATUS_PROXY_TIME_ASSOCIATION_R1.json`|完整|修正 proxy 时间关联的后处理版本；原 native 不重跑、不替换|

EXT02 的旧 primary post 数据也保留并读取，索引版本为 `PHASE2_PRIMARY_POST_PRESERVED` / `PHASE2_NATIVE_OR_PRIMARY_POST`。最终 proxy 诊断取恢复子目录，是因为原记录明示 `supersedes_for_proxy_diagnostics_only=true`，不是依据文件更新日期或数值好坏择优。恢复记录 `native_outputs_mutated=false`，本轮未重新验证其旧哈希。

## 原数字与分母

|原有字段|EXT01 R2|EXT02 原生 / 恢复诊断|
|---|---:|---:|
|全部原生配对历元|1509|1509|
|返回整数解 / accepted wrapped solution|1077|1057|
|无结果 / failure|432|452|
|对应可用比例|0.7137176938369781|0.7004638833664678|
|native 相对 HPPOSECEF proxy 的 yaw RMSE（°）|120.73505854071854|120.98227411490542|
|native 相对既有 trace 的 yaw RMSE（°）|120.5700062447263|120.52876042302128|
|该 trace RMSE 的有效数|1077|964|

EXT01 数字来自 R2 SUMMARY 的 `native_counts`、`proxy.native_minus_proxy_yaw_deg`、`trace.native_vs_trace_yaw`。EXT02 数字来自原生 SUMMARY 的 `paired_epoch_count` / `success_row_count` / `failure_row_count` / `accepted_wrapped_solution_rate`，以及恢复 MANIFEST 的 `descriptive_aggregates.native_minus_proxy_body_yaw_wrapsafe` 和 `trace_native_yaw_error_deg`。

这些是 raw dual-antenna 单历元航向结果，不是整轨迹导航 RMSE，也不是 1509 次 native 进程。EXT01 的旧 trace 诊断用其既有支持；EXT02 在固定 66–340 s 评价窗内有 `valid_denominator=1370`、`valid_count=964`、`valid_coverage=0.7036496350364964`。两个 trace 分母不同，不能把约 120°横向误差合并为共同支持比较。HPPOSECEF 是同源接收机的 solution-level proxy，trace 是既有评价参考，均不能据此称作独立真值。

两者共有的失败原词及数量：`INSUFFICIENT_CP_VALID=11`、`INSUFFICIENT_DD_DIMENSION=1`、`INSUFFICIENT_HALF_CYCLE_VALID=374`、`INSUFFICIENT_SATELLITE_STATES=46`。EXT02 另外有 `NUMERICAL_FAILURE=20`。两份完整 native 表各 1509 行、失败表分别 432 / 452 行已读并附小型源副本，失败行未删除。

EXT01 的 1077 次全局搜索证书表述只涉及搜索目标的完整性，`ambiguity_acceptance_test_defined=false`、`ambiguity_accepted_count=null`。EXT02 为 `ambiguity_correctness_known=false`、`ambiguity_success_rate/fixed_rate/float_rate=NA`；不能把 accepted wrapped solution 或实现验证 PASS 翻译成正确模糊度固定率。

## fractional-DD / phase-bias 的既有判定层级

EXT01 R2 SUMMARY `fractional_dd` 保存 4118 条个体记录、27 个分组，原规则为 `count>=30 and abs(circular_mean)>=0.20 cycles and circular_std<=0.10 cycles`，报告 8 个 persistent-offset 组，`calibration_applied=false`。全部 4118 条 CSV 与 27 行 half-cycle 分组表已读；后者有公开小副本。原 R2 报告中关于模型适用性的判断是历史诊断，不能仅由这些分组直接断言具体硬件偏差来源、改正量或标定后性能。

EXT02 恢复 MANIFEST 的精确来源键为 `descriptive_aggregates.fractional_dd_relationships`：

|关系（既有 Pearson 字段）|paired_count|pearson_correlation|
|---|---:|---:|
|fractional_rms_vs_abs_trace_yaw_error|964|0.10776367439615221|
|fractional_rms_vs_native_objective|1057|0.6920050716468352|
|fractional_rms_vs_proxy_vector_angle|1057|0.04515066594894081|
|fractional_rms_vs_unique_candidate_count|1057|0.7540178112888336|
|proxy_objective_gap_vs_vector_angle|1057|0.029726359009222925|

这些相关性是原有 `DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING` 字段，本轮没有重算。原报告第 794–796 行明确没有 phase-bias calibration、correction、selection 或 substitution；37 个稳定 satellite/pivot/subHalfCyc 分组也是既有描述，不能由相关性升级为已验证因果。`proxy_minus_production_objective.min=9.75603372236621`，1057 个可用历元没有 materially-lower proxy objective；它检验旧目标/搜索关系，不证明物理航向正确。11 个 objective-oracle 比较通过同样不等于全体误差合理。

原记录的 half-cycle contract 是使用接收机已报告的 `cpMes`；`subHalfCyc` 表示接收机已减去半周，不能再补一次 ±0.5 周。此处仅保留旧契约，实际输入链语义尚待后续独立核对。

## 来源、旧测试与读取边界

当前可定位的实现入口为 `src/legsa_gins/paper_rebuild/horizontal_literature/{ext01_clambda.py,ext02_cwls.py,phase1r_runner.py,phase2_runner.py}`；对应脚本和 V2 / V1 合约已登记。测试入口为 `tests/paper_rebuild/test_horizontal_ext01_clambda.py`、`test_horizontal_ext02_cwls.py`、`test_horizontal_phase2_c00.py`。本轮只核这些入口存在，没有 import、`--help`、源码语义审查或测试执行。

旧 HX_INVENTORY 已记录当前 shared backend / bridge、EXT02 runner 与原生冻结身份有变化；因此本轮只复用原摘要里的 `code_commit`、`source_fingerprint` 和 recorded hashes，未断言当前文件能复现旧原生结果。EXT02 旧状态中的 focused 97 PASS、active 719 PASS / 10 skipped / 14 warnings 是历史回执，不是本轮测试数。

本小项最后一次收集通过完整解析 14 个 JSON、22 个 CSV（32191 条数据行）、3 份正文；另外 3 个大型诊断表只做文件元数据检查：EXT01 tracking 82766398 字节，EXT02 candidate 78614325 字节、refinement 66456300 字节。它们未被当作已经全文读取。原始 RAWX、UBX、trace/reference 载荷均未打开；这里的 `TRACE_DIAGNOSTICS.csv` 是既有后处理表。表中记录的旧 trace-open 计数不是本轮访问。

本轮 native / provider / evaluator / 新哈希均为 0。无新归档、无科学指标计算。原始路径镜像位于 `<EXT_REPRO_ROOT>/existing_clean.local.csv`，不进入 Git。读取回执 [EXT01_EXT02_READ_RECEIPT.json](EXT01_EXT02_READ_RECEIPT.json) 统计本小项最后一次收集的唯一文件/表行，不冒充累计 I/O 次数。首次浏览索引遇到标准 CSV 单字段长度限制，已将大 provenance 映射保留在完整源副本、缩短索引引用；没有修改原源表。
