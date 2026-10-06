# 展示引用的旧协议对照：不增加 V3 运行分母

来源是 `configs/paper_rebuild/v3/V3_REPORT_SOURCE_INDEX.json` 中 frozen_core、frozen_addendum、frozen_sequences、horizontal_tables 和 frozen_by2o_segments。它们是最终展示明确引用的历史证据；本轮只读其原有结果，没有重新执行旧阶段。

原根为 `<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/20_FINALIZE/`，三个聚合目录分别 `13_AGGREGATE/`、`13_AGGREGATE_ADDENDUM/`、`13_AGGREGATE_SEQUENCES/`，各有 v3/v2/UNIQUE_EVALUATION_RESULTS.csv。这里目录中的 v3/v2 是评价口径，不是说这些 native 都来自 Protocol V3。

## 原身份与复用关系

|原组|每评价版本行数|实际身份|不能重复计数的关系|
|---|---:|---|---|
|CORE|5,951|5,410 SENSOR_MODEL_V2_1；541 个 F01 为 Canonical-541_protocol_v2_CAL|不是同一算法提交下统一重跑的“v2.1全集”|
|ADDENDUM|495|450 v2.1；45 个旧 F01 为 ADDENDUM protocol_v2_CAL|与 V3 的 495 新运行分列|
|三序列|33|30 v2.1；3 个旧 F01|BY2 C00 十一行与 CORE 重叠|
|SUBSET61|671|C00 + 60 类型的 seed00 × 11 方法|从 CORE 复用，不增加 671 次 native|

CORE 原行的 code_commit 分别为 `521901f0347e367281abed23b46686b84df86055` 与 `737a0fb5a4a5418500824855b89b0d25af69824a`；这只是对应 source-row 的 code 字段，不能当所有旧组统一 binary/runner 身份。旧 ADDENDUM 的 F01 还跨多个历史提交，须逐行保留。

旧 CORE 各评价表 5,774 COMPLETED、177 NOT_RUN_ALGORITHM_FAILURE；后者 solver_terminal_status 全部为 ALGORITHM_FAILURE_ALL_YAW_REJECTED。最终 V3 原 token 则含 DIVERGED/NO_VALID_HEADING_INPUT。不同协议分类尚未统一，不能简单把 283−177 当某个模块新增故障的因果计数。

`<V3_ROOT>/07_AGGREGATE/` 的 CORE_541_V21_COMPARISON_V3/V2、SUBSET61_V21_COMPARISON_V3/V2、ADDENDUM_V21_COMPARISON_V3/V2、SEQUENCE_V21_COMPARISON_V3/V2 分别每版 5,951/671/495/33 行；FAILURE_COMPARISON.csv 共 192 个单元格（含两个 evaluator、协议、domain 与分类/配置轴），不是 192 个失败。按原 case/method 键，CORE 两侧完成 5,496，只有旧侧失败而新侧完成 172，只有旧侧完成而新侧失败 278，两侧失败 5；SUBSET61 共同有限 626/671，sequence 33、addendum 495。计数仅描述状态转移，不能消除分类定义和版本差异。

## F04 自然全窗不是全指标单调改进

下表从 SEQUENCE_V21_COMPARISON_V3 按 dataset_id=BY2/BY2H/BY2O、method_id=F04（连同 case_id） 的原列转录，完整键/字段见 `secondary/LEGACY_SOURCE_CELLS.csv`。

|序列|旧 yaw RMSE (°)|V3 yaw RMSE (°)|旧 H RMSE (m)|V3 H RMSE (m)|描述|
|---|---:|---:|---:|---:|---|
|BY2|2.2211070025147257|1.8862718548526467|0.09716199583877864|0.09790607774950152|yaw 降低、H 升高|
|BY2H|1.773436559706182|1.93377013508875|0.06855282395068205|0.06836245149191253|yaw 升高、H 降低|
|BY2O|3.197136492350906|2.433814932823714|0.057041149159153724|0.054543210912875166|两项降低|

这是原输出的版本对照，不是只切换一个因子的新实验。共同 reference 不使其成为独立真值检验。v2 另一个评价视图保留在原表，不能挑数值更小者作为胜出证据。

## CLEAN7 旧外部入口

`<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/11_READONLY_CLOSEOUT_H_EXT_04L/MAIN_TABLE_V3.csv` 和 V2 各 52 行：26 COMPLETED、21 UNAVAILABLE、4 AVAILABLE_GEOMETRIC_AUDIT_FAIL、1 NOT_RUN_ALGORITHM_FAILURE。V3 当前主表替换了其中 15 个内部展示配置行，保留 37 个外部行；后来的 HX05 展示另有身份和来源，不应覆盖旧表。

该旧根 BY2O_SEGMENT_SUMMARY.csv 有 90 行（9 方法×5 段×2 评价版本）；当前 V3 BY2O_SEGMENT_TABLE 为 150 行。旧表原范围继续保留，不自动合并为同一版本。更晚的论文表图沿自己的 manifest/NUMBER_LEDGER 读取，而不是根据文件时间或 FINAL 名称选真值。

本项仅做来源转录、状态关联与解释；没有求解、重新评价或 bootstrap。所有这些材料属于引用层 B，不能加入 6,468 个正式 V3 native 的分母。
