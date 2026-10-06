# 原记录服务时间约束下的连续跟踪导航比较

本轮复用原 PARTIAL6 的 120 条记录及其 certificate.elapsed_s，按单worker busy-drop/noqueue 与历史catchup规则生成新可用时间流，新增 C-ILS 为 0。PARTIAL6 为主要无延迟对照，其他版本仅复用。计算使用原 c25a48e→dbf 同一科学冻结链记录费用，不以新缓存基准替代；准备、验证、跟踪、I/O 和资源争用成本计零，因此不属于硬件实时验证。

完整窗口 66–340 s，另保留原定 66–100 s 和 100–340 s 子域；没有只统计载波有效时刻。本轮新增 4 次 native 和封存后的 4 次离线评价；其余版本结果仅复用。

| 版本 | 输入 | H RMSE (m) | V RMSE (m) | Yaw RMSE (deg) | valid 历元 | native 向量接受 |
|---|---|---:|---:|---:|---:|---:|
| V1 | C0_SCALAR | 0.098205 | 0.048800 | 1.712163 | NA | NA（标量） |
| V1 | C1_DUAL_PVT_VECTOR | 0.098646 | 0.048823 | 1.620834 | NA | 1302 |
| V1 | C2_FULL_CARRIER_VECTOR | 0.102812 | 0.048793 | 2.748727 | 1 | 1 |
| V1 | C3_PARTIAL_CARRIER_VECTOR | 0.102216 | 0.048795 | 2.479564 | 7 | 5 |
| V2 | C0_SCALAR | 0.098205 | 0.048800 | 1.712163 | NA | NA（标量） |
| V2 | C1_DUAL_PVT_VECTOR | 0.098646 | 0.048823 | 1.620834 | NA | 1302 |
| V2 | C2_FULL_CARRIER_VECTOR | 0.102820 | 0.048792 | 2.756924 | 0 | 0 |
| V2 | C3_PARTIAL_CARRIER_VECTOR | 0.102334 | 0.048792 | 2.557707 | 6 | 4 |
| TRACKING_V2 | C0_SCALAR | 0.098205 | 0.048800 | 1.712163 | NA | NA（标量） |
| TRACKING_V2 | C1_DUAL_PVT_VECTOR | 0.098646 | 0.048823 | 1.620834 | NA | 1302 |
| TRACKING_V2 | C2_FULL_CARRIER_VECTOR | 0.102820 | 0.048792 | 2.756924 | 0 | 0 |
| TRACKING_V2 | C3_PARTIAL_CARRIER_VECTOR | 0.101068 | 0.048785 | 2.249469 | 24 | 20 |
| PARTIAL6 | C0_SCALAR | 0.098205 | 0.048800 | 1.712163 | NA | NA（标量） |
| PARTIAL6 | C1_DUAL_PVT_VECTOR | 0.098646 | 0.048823 | 1.620834 | NA | 1302 |
| PARTIAL6 | C2_FULL_CARRIER_VECTOR | 0.102820 | 0.048792 | 2.756924 | 0 | 0 |
| PARTIAL6 | C3_PARTIAL_CARRIER_VECTOR | 0.099993 | 0.048782 | 1.994934 | 70 | 68 |
| SERIAL_LATENCY_PARTIAL6 | C0_SCALAR | 0.098205 | 0.048800 | 1.712163 | NA | NA（标量） |
| SERIAL_LATENCY_PARTIAL6 | C1_DUAL_PVT_VECTOR | 0.098646 | 0.048823 | 1.620834 | NA | 1302 |
| SERIAL_LATENCY_PARTIAL6 | C2_FULL_CARRIER_VECTOR | 0.102820 | 0.048792 | 2.756924 | 0 | 0 |
| SERIAL_LATENCY_PARTIAL6 | C3_PARTIAL_CARRIER_VECTOR | 0.101844 | 0.048793 | 2.403444 | 11 | 10 |

本轮部分载波共有 11 个 valid 输入历元，native 接受 10 次；PARTIAL6 对应为 70 个 / 68 次。全时段 yaw RMSE 由 1.994934° 变为 2.403444°，H 由 0.099993 m 变为 0.101844 m。双位置向量链仍为 yaw 1.620834°、H 0.098646 m，相对双位置向量对照，本轮载波的航向 RMSE 更高，水平 RMSE 更高。

本轮完整窗口中最长没有接受载波更新的间隔为 121.202 s。精确接受时刻保留在 SUMMARY；这些历元来自共享整数和短时相邻观测，不能解释为同数量的独立正确固定或已校准完整性。这里报告的是固定输入/门限下的本次点估计，不额外挑选成功区间或调整参数。

控制 NAV/STD 字节一致性：C0_SCALAR=PASS, C1_DUAL_PVT_VECTOR=PASS, C2_FULL_CARRIER_VECTOR=PASS。

各版本共享二进制、PVT与辅助输入的 hash；全部链原始/STD/评价时间键相同。RUN_COUNTS 分开列 valid 历元、native 接受及 body/RP/RD 更新数；DIFFERENCES 给出本轮相对每个旧版本的三域差值。密集跟踪使用共享整数，历元数量不能当作独立成功固定次数或校准的错误固定概率。

参考为 Fixposition 派生结果，非独立真值；整数没有真实标签。初始条件非 AR 冷启动，参数没有按本轮结果调整；本轮已经使用原记录 C-ILS 完成时间约束 provider 可用性，仅向导航提供当时的当前测量；其余处理成本仍计零，不能视为真实实时系统验证。
