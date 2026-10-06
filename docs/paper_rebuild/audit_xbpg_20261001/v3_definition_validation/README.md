# V3 定义收敛与单因素闭环验证

本轮已完成并停止于[最终裁定](FINAL_DEFINITION_VALIDATION.md)：原V3不变；N12顺序NIS与N16维度质量契约分别修正并实测，N09保留为可选新增RP能力。三个候选均没有合入原版。直接5 Hz标量heading、HV继承旧status-heading等原范围已继承，不重新待决策，也不自动追加研究。

原定[10个候选组合](CANDIDATE_QUEUE.csv)全部完成，复用7个可信原版基线；新增真实native10、基线native0、合成fixture进程9、冻结离线evaluator17、reference子进程打开17，真实运行/评价失败与重试均0。实际指标含N12/D15不利yaw和N09/A1水平改善但Up变差，没有用单例RMSE决定数学定义。十个组合共享一条BY2录制，不是十个独立自然试验。

建议阅读顺序：

1. [FINAL_DEFINITION_VALIDATION.md](FINAL_DEFINITION_VALIDATION.md)：继承定义、必要修正/可选扩展、实际指标/事件与原V3结论边界。
2. [V3_DEFINITION_DECISIONS.md](V3_DEFINITION_DECISIONS.md)：执行前双栏定义、公式、调用顺序和固定判据；[CASE_RESULTS_README.md](CASE_RESULTS_README.md)、[CASE_METRICS.csv](CASE_METRICS.csv)、[CASE_SUPPORT.csv](CASE_SUPPORT.csv)给全部10组合/22窗口/110指标对。
3. [event_analysis/README.md](event_analysis/README.md)：17条完成事件流、各候选实际R/更新/首状态分叉。A1原80关联摘要须连同100条更正表阅读，这是本轮分析器文本键问题。
4. [P_MODEL_BOUNDARY.md](P_MODEL_BOUNDARY.md)、[METHOD_APPLICABILITY.csv](METHOD_APPLICABILITY.csv)、[OPEN_ISSUES.csv](OPEN_ISSUES.csv)：数值诊断与已有问题的明确边界，非自动后续队列。
5. [CALL_ACCOUNTING.json](CALL_ACCOUNTING.json)、[RUN_MANIFEST.csv](RUN_MANIFEST.csv)、[EVAL_MANIFEST.csv](evaluation/EVAL_MANIFEST.csv)、[EVENT_READ_SUMMARY.csv](EVENT_READ_SUMMARY.csv)：真实调用、来源和读取深度；[三张说明图](figures/README.md)保留不利变化。

每项保存后立即提交/推送，回执见[PROGRESS.md](PROGRESS.md)及[COMMITS.csv](COMMITS.csv)。最后提交自身SHA由终端给出，不为记录自身递归提交。

范围只含算法定义、原生测试、必要真实闭环/离线评价及技术裁定。原性能表、维护论文、原科学源码/二进制和历史结果不变；没有全矩阵、外部复现、XB、联合候选或参数搜索。局部数学契约与闭环性能分别判断。

本机根使用ignored `configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json`：`<VALIDATION_ROOT>`保留新native/评价/事件/失败，`<VALIDATION_BUILD_ROOT>`保存隔离源与构建。原基线仍在`<MECHANISM_ROOT>`。大载荷不上传、不清理，tracked文件使用别名。
