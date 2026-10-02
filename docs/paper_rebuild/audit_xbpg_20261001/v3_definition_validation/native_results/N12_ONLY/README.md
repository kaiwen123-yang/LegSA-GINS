# N12_ONLY：两次真实闭环已完成

计划2/实际2，C00/F04和D15_seed_00/F04均退出0，无重试。每对象99项固定manifest身份/参数一致，访问检查通过；十份科学输出均存在且与原可信hash不同。大NAV/STD和全部事件保留于 `<VALIDATION_ROOT>/candidates/N12_ONLY/<baseline_run_id>/`。

已记录的真实闭环变化（完整源字段见 COUNTERS.csv）：C00 source_aware_weight_changed_count 为3946→3711；D15为6729→6795。D15 yaw实际接受1346→1345，说明固定门公式下，候选闭环状态变化也会改变后续接受，不能把旧影子“拒绝未改变”搬到新闭环。两例RD接受均1108、RP/HV各1369，与基线相同。原checkCov失败均0，但它只查对角，完整P诊断另行读取，不能在此提前PASS。

这里仅转录调用、输出hash和native计数；并未从计数判断精度优劣。同口径离线评价、实际事件首分叉/完整P分析尚待完成，将作为下一独立可核查小项提交。候选输出不是历史NAV，原版未覆盖；两例不外推全矩阵。STATUS保留计划分母，OUTPUT_HASHES的DIFFERENT_OR_MISSING在本批均是存在但不同，没有缺文件。
