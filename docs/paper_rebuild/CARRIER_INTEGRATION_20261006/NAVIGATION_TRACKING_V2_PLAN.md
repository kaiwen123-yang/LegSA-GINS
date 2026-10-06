# 连续跟踪导航阶段计划（尚未执行）

本计划只准备下一次完整导航比较。只有 ROOT 明确确认源码冻结及 TRACKING_V2 完成，才允许启动；本次准备不启动轮询或导航进程。

预期输入：<CARRIER_SCRATCH>/TRACKING_V2/SUMMARY.json、CARRIER_TRACKED_FULL.csv、CARRIER_TRACKED_PARTIAL.csv；两个侧车各保留原始 1,200 个历元，失败/无效行也保留。连续跟踪不新增 CILS，不能把每个跟踪历元算作一次独立整数搜索或独立成功固定。

导航输出目录为 <CARRIER_SCRATCH>/NAVIGATION_TRACKING_V2。仅 body HV 开启的四臂，共同 66–340 s 原始 IMU/P/RV/RD/RP/body provider、初始化与既有 BUILD_BODY_HV 二进制。C0 双位置标量航向、C1 双位置向量、C2 全量跟踪载波、C3 部分跟踪载波。除载波侧车和输出路径外，配置及共享输入内容须与 V2 相同。门限、噪声参数与评价器保持冻结。

预算：4 次新 native，全数封存后 4 次新冻结评价；V1/V2 原结果仅复用比较，不重跑。C0/C1 的 NAV/STD 应与 V2 字节一致。V2 全量初始候选为 0，连续跟踪也必须为 0；额外要求 C2 的 NAV/STD 与 V2 字节一致，验证增加无效事件行没有改变 IMU 传播或辅助源调度。

保存完整 66–340 s，以及原定 66–100 s、100–340 s 三域 H/V/3D/yaw 指标和最大绝对误差；全部链核共同原始/STD/评价时间键。记录侧车 valid 历元数、native 实际接受数、body/RP/RD 更新数。时间密集的同一固定整数跟踪具有相关性，不能用历元计数代替独立整数正确性或 false-fix 证据。

参考来自 Fixposition，非独立真值；共同初始化不是 AR 冷启动；所有 native 完成前不得读取参考。仍为不模拟 CILS 墙钟延迟的离线回放。无效事件等价性或其他运行契约失败须保留原输出并报告，不以指标选择额外运行。
