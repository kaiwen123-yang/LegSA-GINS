# CORE 阅读入口与分母

已全文读取 22 份 EVALUATION_CORE_{v3,v2}_{11方法}.csv，共 11902 评价槽，按真实 case/method/run_id 关联 5951 个唯一 native。每方法为 541 个案例：1 个 C00 + 60 类型×9 seed=540 个退化案例。C00 的 11 个物理运行就是自然 BY2 结果的复用入口，不再增计 native。F03/A02、F04/A01 为别名。

SUBSET61 是 C00 + D01–D60 的 seed_00，共 61 案例；它是 541 的子集，不是另外 61 次独立实验，也不能代表九种子完整总体。自然 C00 是 real_clean；540 注入案例为 semisynthetic。共享 BY2 原始轨迹、故障实例和模块配置不等于独立真实场景样本。

按 gnss_outage → gnss_sampling → position_value → position_std_status → dual_yaw → velocity_raw_doppler → go2_prior_metadata → multi_source_mixed 阅读各目录 README.md。每族含全部 11 方法、7 原指标、v3/v2 两版；FAILURES.csv 保留全部非完成槽，2×2 和配对差只是明确标为 VALIDATION 的计数/已有指标算术。

ORIGINAL_CORE_541_SUMMARIES.csv 是原整体 summary 转录；各族原分布与各类型原分布在其目录。不能把族均值无权平均冒充 CORE 均值，也不能把各自有限集均值差当成共同有限集配对差。新浏览视图不重做 bootstrap/CI，不从 error_series 或 NAV 重算本项统计。

INPUTS_READ.csv 记录全文读取到 EOF 的统计、合同和小型 bundle 元数据，不声称读取了其 provider payload。source_path/source_row_key/source_json_pointer 指回原记录，read_source_path/read_source_data_row 指回上一轮便携完整统计；同名原指标列保持原字符串。FIELD_MAP.csv 给出列/单位映射。各 README 中人工选出的导航值之外，全部原数保存在 CSV。

各族时序状态以其 README 和 series_checks/CORE_<family>/RECEIPT.json 为准；未完成的族保留 PENDING_ROOT_SERIES_CHECK，根代理在交付该小项时补唯一 scanner 的同组检查。coverage=matched/output 不证明连续、完整支持或独立参考样本。reference 是商用融合参考而非独立真值；本入口不宣布数学或因果机制审核通过。

## 八族与C00闭合（本轮计数验证）

八族540退化case×11=5,940 native，再加自然BY2复用的11个C00，得到5,951。不是把BY2再执行一次；SUBSET61=61case×11=671行，是这541中的子集。全部283 native失败在 CORE_FAILURE_NATIVE_283.csv 按run_id逐项保留：193 ALGORITHM_FAILURE_DIVERGED、90 ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT；其两评价未调用槽仍是566，不将283或566当成594个故障配置分组格。

| 方法 | 注册 | 完成 | 发散 | 无有效航向输入 |
| --- | --- | --- | --- | --- |
| F01 | 541 | 521 | 20 | 0 |
| F02 | 541 | 498 | 34 | 9 |
| F03 | 541 | 512 | 20 | 9 |
| F04 | 541 | 519 | 13 | 9 |
| A03 | 541 | 518 | 14 | 9 |
| A04 | 541 | 513 | 19 | 9 |
| A05 | 541 | 519 | 13 | 9 |
| A06 | 541 | 519 | 13 | 9 |
| A07 | 541 | 519 | 13 | 9 |
| A08 | 541 | 512 | 20 | 9 |
| A09 | 541 | 518 | 14 | 9 |

| F04对照 | 双方完成 | 仅F04完成 | 仅对照完成 | 双方未完成 |
| --- | --- | --- | --- | --- |
| F01 | 512 | 7 | 9 | 13 |
| F02 | 498 | 21 | 0 | 22 |
| F03 | 512 | 7 | 0 | 22 |
| A03 | 518 | 1 | 0 | 22 |
| A04 | 513 | 6 | 0 | 22 |
| A05 | 519 | 0 | 0 | 22 |
| A06 | 519 | 0 | 0 | 22 |
| A07 | 519 | 0 | 0 | 22 |
| A08 | 512 | 7 | 0 | 22 |
| A09 | 518 | 1 | 0 | 22 |

这些四格为完成状态而非逐指标有限配对；需与各指标有限集同时看。原整体 CORE_541_SUMMARY/DISTRIBUTION 的 v3 yaw RMSE P95：F01=40.611345267892865°、F03=9.592960818858016°、F04=2.4465376134717114°、A04=2.7461951021142736°；水平RMSE P95相应F01=3.0181413938779036 m、F03=3.0214369297083286 m、F04=3.5510500790754915 m、A04=3.015940224356186 m。来源在 ORIGINAL_CORE_541_SUMMARIES.csv 的method/metric键及各原分布表；这些不同有限子集的尾部不等于共同案例比较，不能只以较小yaw尾部宣布整体鲁棒性获胜。

F01较少失败不表示航向精度更好：它持续yaw关闭，D57的任务完成条件/输入暴露也不同。F04相对A04减少原失败次数，却并非每个有限案例都改善；均值/中位数/尾部和四格共同给出结论。原失败分类tokens不变，跨旧协议分类可比性另由引用材料章节说明，不在本轮统一重分类。
