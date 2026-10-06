# 导航控制器恢复与终态核验

首个控制器在 prepare 成功后、任何 native 调用前停止：它误将配置实际终点 339.997056 s 与名义窗口终点 340 s 直接比较。旧跟踪版与本轮配置实际终点完全相同，都是注册 IMU 最后一条样本。修正后的独立控制器同时严格核对名义 [66,340]、新旧实际起止值和 segment.last，没有放宽算法、输入或评价支持。

原失败控制器的 12 个文件及已经生成的 10 个配置/输入/计划文件逐项 hash 不变。恢复使用独立 NAVIGATION_DRIVER_PARTIAL6_RECOVERY_01 目录；不重 prepare、不重前端、不重跟踪、不重复任何导航或评价调用。总计 prepare 1 次（4 个配置检查）、native 4 次、冻结 evaluator 4 次。所有 native 封存并通过 C0/C1/C2 与 TRACKING_V2 的 NAV/STD 字节一致检查后，才开始评价。

全部 V1、V2、TRACKING_V2、PARTIAL6 的 16 条链共有 56,642 个相同时间键，实际输出区间为 66.005054–339.997056 s。当前四臂 online reference 打开均为 0，offline evaluator 各为 1；body/RP 各 1369 次、RD 各 666 次。完整三域指标、计数、差值分别保留在 [RESULTS](PARTIAL6_NAVIGATION_RESULTS.csv)、[RUN_COUNTS](PARTIAL6_NAVIGATION_RUN_COUNTS.csv)、[DIFFERENCES](PARTIAL6_NAVIGATION_DIFFERENCES.csv)。

部分载波 70 个 valid 历元中实际接受 68 次。全时段 H/V/yaw RMSE 为 0.099992977 m / 0.048781623 m / 1.994933772°。相比八维上限跟踪版的 2.249469173°，yaw RMSE 下降；但最大绝对 yaw 偏差由 6.520853511° 上升至 7.258837203°，不能把 RMSE 改善概括为所有误差指标均改善。双位置向量对照的 yaw RMSE 仍更低（1.620833504°）。

这些是同一已使用序列上的有限开发结果；连续观测共享整数，68 次接受不等于 68 次独立正确固定，Fixposition 派生评价参考不是独立真值。未新增门限、调参、成功时段筛选或墙钟延迟补偿。详尽恢复证据、阶段时间、hash 与计数见 [RECOVERY.json](PARTIAL6_NAVIGATION_RECOVERY.json)。
