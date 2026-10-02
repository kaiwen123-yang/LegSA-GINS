# CORE 阅读入口与分母

已全文读取 22 份 EVALUATION_CORE_{v3,v2}_{11方法}.csv，共 11902 评价槽，按真实 case/method/run_id 关联 5951 个唯一 native。每方法为 541 个案例：1 个 C00 + 60 类型×9 seed=540 个退化案例。C00 的 11 个物理运行就是自然 BY2 结果的复用入口，不再增计 native。F03/A02、F04/A01 为别名。

SUBSET61 是 C00 + D01–D60 的 seed_00，共 61 案例；它是 541 的子集，不是另外 61 次独立实验，也不能代表九种子完整总体。自然 C00 是 real_clean；540 注入案例为 semisynthetic。共享 BY2 原始轨迹、故障实例和模块配置不等于独立真实场景样本。

按 gnss_outage → gnss_sampling → position_value → position_std_status → dual_yaw → velocity_raw_doppler → go2_prior_metadata → multi_source_mixed 阅读各目录 README.md。每族含全部 11 方法、7 原指标、v3/v2 两版；FAILURES.csv 保留全部非完成槽，2×2 和配对差只是明确标为 VALIDATION 的计数/已有指标算术。

ORIGINAL_CORE_541_SUMMARIES.csv 是原整体 summary 转录；各族原分布与各类型原分布在其目录。不能把族均值无权平均冒充 CORE 均值，也不能把各自有限集均值差当成共同有限集配对差。新浏览视图不重做 bootstrap/CI，不从 error_series 或 NAV 重算本项统计。

INPUTS_READ.csv 记录全文读取到 EOF 的统计、合同和小型 bundle 元数据，不声称读取了其 provider payload。source_path/source_row_key/source_json_pointer 指回原记录，read_source_path/read_source_data_row 指回上一轮便携完整统计；同名原指标列保持原字符串。FIELD_MAP.csv 给出列/单位映射。各 README 中人工选出的导航值之外，全部原数保存在 CSV。

各族时序状态以其 README 和 series_checks/CORE_<family>/RECEIPT.json 为准；未完成的族保留 PENDING_ROOT_SERIES_CHECK，根代理在交付该小项时补唯一 scanner 的同组检查。coverage=matched/output 不证明连续、完整支持或独立参考样本。reference 是商用融合参考而非独立真值；本入口不宣布数学或因果机制审核通过。
