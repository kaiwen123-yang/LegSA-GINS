# Protocol V3：逐组解释与保留时序核对

本轮接续 `v3_results/`，起点 `d9763ea40fd19963a71321c2a6ca930a022c159d`，不重建大索引、不替换历史结果。阅读顺序：方法/指标 → BY2 → BY2H → BY2O → CORE 各故障族 → A1/A2 各时长 → 配对与不确定度 → 外部引用与实际看图 → 旧问题映射。完成范围与下一项见 [PROGRESS.md](PROGRESS.md)。

- [方法与指标说明书](METRIC_AND_METHOD_GUIDE.md)：正式配置、版本、参考物理点、时间支持和分母。
- `natural/`、`core/`、`addendum/`：按小项提交的解释及来源行。
- `series_checks/`：独立 validation calculation；历史 recorded 值与本轮 check 值分别保存。
- `COMMITS.csv`：此前小项的提交和远端核验回执；当前提交身份由 Git 自身给出，避免递归改写。

四级证据深度分别为 `INDEXED_ONLY`、`HEADER_READ`、`FULL_PAYLOAD_READ`、`NUMERICALLY_CHECKED_WITHIN_SCOPE`。全文读取要求到达文件 EOF，数值核对只覆盖保留字段及相同时间支持。转录一致、保留误差统计一致、从原始输入复现 NAV、算法数学正确和参考独立性是不同问题。

本轮允许独立计数、配对算术和保留误差序列指标核算，并单独标记；上一轮 `new_performance_statistics=0` 的历史回执不变。native solver、provider generator、原 evaluator、aggregate/controller、bootstrap、原始 reference 读取均不在本轮调用范围。原结果只读；不存在的 NAV/STD 不重建。

共享路径使用 `<V3_ROOT>`、`<CODE_ROOT>` 等既有别名；本机解析沿用 ignored 的 `configs/paper_rebuild/V3_RESULTS_ROOTS.local.json`。本目录报告不提升商业融合 reference 为独立真值，也不宣布科学审查完毕。
