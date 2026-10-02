# V3 定义收敛与单因素闭环验证

本轮保留原V3，按 [定义决策](V3_DEFINITION_DECISIONS.md) 分别实施N12_ONLY、N16_ONLY、N09_RP_ONLY，限定 [10个候选组合](CANDIDATE_QUEUE.csv)，复用上轮7个可信原版基线。实际调用见 [RUN_MANIFEST.csv](RUN_MANIFEST.csv)，小项完成即提交/推送，状态见PROGRESS.md及COMMITS.csv。

范围只含算法定义、原生测试、必要真实闭环/离线评价及技术裁定。原性能表、维护论文、原科学源码/二进制和历史结果不变；没有全矩阵、外部复现、XB、联合候选或参数搜索。局部数学契约与闭环性能分别判断。

本机根使用ignored `configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json`：`<VALIDATION_ROOT>`保留新native/评价/事件/失败，`<VALIDATION_BUILD_ROOT>`保存隔离源与构建。原基线仍在`<MECHANISM_ROOT>`。大载荷不上传、不清理，tracked文件使用别名。
