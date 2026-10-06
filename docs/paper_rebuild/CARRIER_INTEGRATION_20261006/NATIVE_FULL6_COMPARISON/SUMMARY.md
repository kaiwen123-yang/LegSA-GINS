# 完整 120 窗原生后端对比（只读已完成结果）

同一输入/科学配置：True；完成窗口均为 120。比较脚本未调用 CILS、导航或参考评估。

| 项目 | 原 PARTIAL6 Python | NATIVE_FULL6 |
|---|---:|---:|
| 有全局证书 | 112/120 | 120/120 |
| 有效实验测量 | 16 | 17 |
| 求解耗时中位数 s（全部实际调用） | 3.120553 | 0.462893 |
| 求解耗时 P90 s（全部实际调用） | 21.534079 | 3.401316 |
| 求解耗时 P95 s（全部实际调用） | 30.000230 | 5.240184 |
| 求解耗时 P99 s（全部实际调用） | 30.000627 | 15.082195 |
| 求解耗时最大值 s（全部实际调用） | 30.001614 | 17.336170 |
| 求解耗时总和 s（全部实际调用） | 799.999127 | 155.878422 |

共同有证书 112 窗：两候选全整数、所选整数类、目标值容差、基线容差、冻结候选、后续状态及测量载荷的通过计数见 SUMMARY.json；实质不一致 0 窗。
其中目标值逐字段数值完全相等 105 窗，基线数组完全相等 105 窗。最大目标绝对差 2.72848410532e-12，最大基线分量差 1.94289029309e-15 m。
共同证书窗的逐窗求解时间比中位数 6.3865，P10/P90 4.7789/7.0192。使用实际记录耗时，没有按旧耗时乘加速系数。

新增证书 8 窗；原证书丢失 0 窗。新增窗逐项保留原终态、是否 timeout、当前验收状态，不以未证书候选冒充等价证书。

- partial_0116.00: SEARCH_TIMEOUT → GLOBAL_BOUND_CERTIFIED; REJECTED_RESIDUAL; valid=False
- partial_0162.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; REJECTED_PHASE_FAULT_DIAGNOSTIC; valid=False
- partial_0178.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; EXPERIMENTAL_FIXED_CANDIDATE; valid=True
- partial_0266.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; REJECTED_LENGTH; valid=False
- partial_0318.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; UNRESOLVED_ACTIVE_ARC_CHANGED; valid=False
- partial_0330.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; UNRESOLVED_ACTIVE_ARC_CHANGED; valid=False
- partial_0334.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; REJECTED_LENGTH; valid=False
- partial_0336.00: SEARCH_TIMEOUT_CHILD_GENERATION → GLOBAL_BOUND_CERTIFIED; UNRESOLVED_ACTIVE_ARC_CHANGED; valid=False

当前对照包含原 Python 到缓存加原生标量内核的整体实现变化，不能把全部收益单独归于 C++。较早 Python 时序不是同时交替重复基准；系统负载波动及超时截断必须保留。
全局证书只针对既定似然目标。整数正确性、风险校准、连续测量覆盖和真实时间融合效果仍需独立证据。

所有 120 窗见 CASE_COMPARISON.csv；全部状态分布、实际运行分位、源差异与小型身份回执见 SUMMARY.json。
