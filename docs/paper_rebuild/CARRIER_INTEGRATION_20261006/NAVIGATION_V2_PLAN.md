# V2 body 速度四臂导航执行计划

本次只新增 4 次 native 导航和随后 4 次冻结离线评价，不重做 HV-off，不改载波源码、选择规则、协方差或门限。

输入等待条件：FRONTEND_V2_PILOT/SUMMARY_0002.json 与 CARRIER_FULL_0002.csv、CARRIER_PARTIAL_0002.csv 均完成，两份 CSV 各有完整 120 窗，时间范围保持 101.998–339.998 s。全部成功、失败和未决观测原样输入，不能按评价结果选观测。

输出目录为 <CARRIER_SCRATCH>/NAVIGATION_BODY_HV_V2。导航窗口 66–340 s，沿用 BUILD_BODY_HV 二进制、原 IMU/P/RV/RD/RP、同一 body FRD 速度、初始化、PVT 三维侧车与冻结评价器。四臂均为 AB1111：C0 双位置标量航向，C1 双位置三维基线，C2 全量载波，C3 部分载波。body sigma=0.2 m/s、scale=1、period=0.2 s。

运行前核对 V1/V2 的共享输入内容 hash、二进制 hash 与四臂配置差异。仅载波文件内容及输出/复制路径允许改变。C0/C1 没有消费载波，运行后要求其 NAV/STD 与 V1 字节一致。全部四臂 native 完成、共同时间键与封存检查通过，才读取参考做四次评价。

主报告保留全时段 66–340 s，以及原定 66–100 s、100–340 s 两个子域；统一完整时间支持的 H/V/3D/yaw 指标、实际 carrier/body/RD/RP 更新计数。载波输入 valid 数与 native baseline3d_accept_count 分开。

V2 是输入生命周期更新后的整链比较：按既定计划更新因果 NAV 前缀、SPP anchor 保持策略和缺失 pivot 处理，不能把变化归结成单个部分模糊度算法因素。候选没有整数真值；Fixposition 参考不是独立真值；共享历史初始化不是 AR 冷启动；墙钟求解延迟未注入状态时间。
