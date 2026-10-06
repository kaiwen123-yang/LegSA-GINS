# Protocol V3：逐组解释与保留时序核对

本轮接续 `v3_results/`，起点 `d9763ea40fd19963a71321c2a6ca930a022c159d`。结果解释与有限证据核对已交付，未重建大索引、替换历史结果或进入修复/重放。先读 [最终解释](FINAL_INTERPRETATION.md)，再按下表选择源结果。提交状态见 [PROGRESS.md](PROGRESS.md) 和 [COMMITS.csv](COMMITS.csv)。

- [方法与指标说明书](METRIC_AND_METHOD_GUIDE.md)：正式配置、版本、参考物理点、时间支持和分母。
- [保留时序说明](RETAINED_SERIES_REVIEW.md) 与 [2309 行逐文件核对表](RETAINED_SERIES_CHECKS.csv)：2308 error_series + 1 matched 全文读取，原值与新 validation 分列。
- [说法与证据矩阵](CLAIM_EVIDENCE_MATRIX.csv)、[旧问题结果映射](ISSUE_RESULT_MAP.csv) 及 [最小后续证据](KNOWN_ISSUES_AND_NEXT_EVIDENCE.md)：解释差异与实际机制待验证事项。
- [交付检查回执](FINAL_DELIVERY_CHECKS.json)：限定改动路径、旧审查/大索引保持、CSV/脚本及阅读链接检查；不是科学正确性认证。

|阅读组|入口|完整的小型浏览表|
|---|---|---|
|自然三序列|[BY2](natural/BY2.md)、[BY2H](natural/BY2H.md)、[BY2O五段](natural/BY2O.md)|各序列 RECORDED、CONFIG_INPUTS/CONTRASTS、DIFFERENCES；BY2O SEGMENTS_RECORDED|
|CORE总览|[全部八族与283失败](core/CORE_OVERVIEW.md)|CORE_FAILURE_NATIVE_283、CORE_COMPLETION_COUNTS、CORE_F04_COMPLETION_2X2|
|CORE前三族|[GNSS中断](core/gnss_outage/README.md)、[采样](core/gnss_sampling/README.md)、[位置数值](core/position_value/README.md)|每族 ORIGINAL_RUN_VALUES、FAILURES、F04_PAIR_VALIDATION、WORST_TOP3、实际INJECTION_COMPONENTS|
|CORE中间三族|[位置std/status](core/position_std_status/README.md)、[双天线航向](core/dual_yaw/README.md)、[RV/RD](core/velocity_raw_doppler/README.md)|每族旧分布/原配对与新计数、2×2、配对算术分开|
|CORE后两族|[Go2/prior/metadata](core/go2_prior_metadata/README.md)、[混合](core/multi_source_mixed/README.md)|不能把no-active-path当真实注入；34个保留计划失败没有时序|
|A1|[10s](addendum/A1_10s.md)、[20s](addendum/A1_20s.md)、[30s](addendum/A1_30s.md)|各时长99native/198评价、全部11方法；原UA与本轮UA_CHECKS分列|
|A2|[10s](addendum/A2_10s.md)、[20s](addendum/A2_20s.md)|每时长RECORDED、SCOPE、PROVIDER_METADATA、PAIRED_CASES、STATUS_2X2、WORST_TOP3|
|配对与不确定度|[定义和结果](UNCERTAINTY_AND_PAIRING.md)|secondary/UNCERTAINTY_SOURCE_CELLS；原完整表仍在../../v3/uncertainty|
|展示引用层B|[旧协议](OLD_PROTOCOL_COMPARISONS.md)、[候选](CANDIDATE_SENSITIVITY.md)、[外部](EXTERNAL_AND_SENSITIVITY.md)|secondary/*_INPUTS_READ 与 *_SOURCE_CELLS；不增加A层运行分母|
|实际读图|[阶段10组](STAGE_FIGURES.md)、[论文10图](PAPER_FIGURES.md)|figures/*_SOURCE_LINKS、*_VIEW_RECEIPT、HISTORICAL_PINS|

`series_checks/<group>/` 内 FILE_CHECKS 记录全文读取、时间支持及同流 hash；METRIC_CHECKS 每行保存原值/新值/分母/容差/差值/源键；FIELD_QUALITY 为导出字段质量；WINDOW_SUMMARY 为明确标记的新固定窗口验证统计。总体 FULL_READ_SUMMARY、GROUP_READ_SUMMARY、UNSUPPORTED_METRICS 和 WINDOW_LIMITATIONS 给出闭合计数及缺口。各组已完成的 scanner 不应作为下一轮自动重启入口；合并脚本仅读这些回执。

这些小型统计/说明可从 GitHub 当前审查分支读取；raw、完整NAV/STD、逐历元大载荷和build没有加入本轮提交。COMMITS记录之前已推送的小项完整SHA；最后一项自身身份由Git及终端交付，避免递归改写。

四级证据深度分别为 `INDEXED_ONLY`、`HEADER_READ`、`FULL_PAYLOAD_READ`、`NUMERICALLY_CHECKED_WITHIN_SCOPE`。全文读取要求到达文件 EOF，数值核对只覆盖保留字段及相同时间支持。转录一致、保留误差统计一致、从原始输入复现 NAV、算法数学正确和参考独立性是不同问题。

本轮允许独立计数、配对算术和保留误差序列指标核算，并单独标记；上一轮 `new_performance_statistics=0` 的历史回执不变。native solver、provider generator、原 evaluator、aggregate/controller、bootstrap、原始 reference 读取均不在本轮调用范围。原结果只读；不存在的 NAV/STD 不重建。

共享路径使用 `<V3_ROOT>`、`<CODE_ROOT>` 等既有别名；本机解析沿用 ignored 的 `configs/paper_rebuild/V3_RESULTS_ROOTS.local.json`。本目录报告不提升商业融合 reference 为独立真值，也不宣布科学审查完毕。
