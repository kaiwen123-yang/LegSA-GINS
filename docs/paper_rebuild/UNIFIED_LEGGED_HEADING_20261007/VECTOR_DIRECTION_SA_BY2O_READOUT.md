# 向量方向 SA：BY2O 匹配读出

2026-10-07。结论：修正三维载波的 scalar yaw std 适用性后，部分方向的强信息确实进入共同姿态、速度、位置及 IMU bias；本窗相对参考 yaw RMSE 改善 7.705%，但水平位置 RMSE 仅改善 0.460 mm。实际原生位置变化仍是亚毫米级，不能宣称实现了稳定、实质性的组合导航收益。

## 冻结比较与完整结果

LEGACY c42f1609… / VECTOR 317a6677… 使用相同原 BY2O [3186,3563] s 完整窗、ROLLING 向量及各向异性 covariance、足端 XY、SDK discrepancy=off、SDK 替换时序、初值、噪声与阈值。只改变 external 3D carrier 的 scalar yaw std 适用性。两次 native 和两次原冻结评价均 COMPLETED；在线 reference opens=0；两臂都保存 76,548 个相同原生/评价时刻。参考仅由原冻结 evaluator 离线使用，本读出没有读取新 reference payload。

| arm | H RMSE m | Up RMSE m | yaw RMSE deg | H p99 m | yaw p99 deg |
|---|---:|---:|---:|---:|---:|
| LEGACY | 0.055756518 | 0.043680167 | 3.306508317 | 0.205110631 | 13.688601441 |
| VECTOR | 0.055296530 | 0.043682567 | 3.051726190 | 0.204930123 | 13.248872911 |

H RMSE 改善 0.459988 mm，H p99 改善 0.180508 mm；Up RMSE 增大 0.002401 mm。coverage 均为 1。原输入定义的全部 10 个场景（含 full、4 点 body-unavailable、39 点 PVT unknown/stale）见 `VECTOR_DIRECTION_SA_METRICS.csv`，没有按结果删点；场景重叠，不能相加当独立分母。原 fresh-PVT-heading-invalid 11,018 点中 yaw RMSE 改善 0.455502°、H 改善 1.004523 mm；这仍是固定场景的相对参考评价，不能升格成独立真值精度或长中断保障。

## 信息消费与因果起点

固定原供给为 1,885 点：FULL valid 168、PARTIAL valid 117、invalid 1,600。两臂均实际尝试 285 点。FULL 接受 142/168 不变；PARTIAL 接受 105/117→106/117。invalid 日志消费 1,599，另有 1,884 个 missing-exact-time 诊断；源分母与原生消费分母均保留，不能混为拒绝数。

旧实际 PARTIAL SA 的 LSIM 分档为 ×6 共 89、×2 共 12、×1 共 4；新 106 条均 ×1，scalar yaw std 全部写 NOT_APPLICABLE。FULL 两臂 LSIM 均 ×1。OIM 未取消：新 PARTIAL 11 条 OIM>1，最大 1.005271；FULL 24 条 OIM>1。完整 R、hard 3DOF NIS、来源 cap 均仍工作。

首次实际 LSIM 变化为 3202.7980001 s 的 PARTIAL，×6→1。此前 3,740 个保存的原生 state/bias 行完全相同；首个状态差出现在 3202.799052 s，即其后 1.052 ms：Δp_N=−0.3553 mm、Δv_N=−0.0012144 m/s、Δyaw=−0.142610°。该时序与首次受影响观测一致，没有启动默认值造成的提前分歧。这里的“首次”按保存精度逐元素比较，不是另设显著性阈值。

唯一 carrier 接受翻转在 3203.7980001 s 的 PARTIAL：hard NIS 12.137443→11.049760，由拒绝变为接受。这是同一滤波状态历史变化后的实际判断，不能只由新 LSIM 档位推定。

## 共同状态、足式链和评价杆臂

| VECTOR−LEGACY 全窗差 | RMS |
|---|---:|
| 原生 IMU 点水平位置 | 0.407909 mm |
| 原生水平速度 | 0.00158912 m/s |
| 姿态旋转角 | 0.420269° |
| gyro bias 三维范数 | 3.569299 deg/h |
| accel bias 三维范数 | 0.00122157 m/s² |
| 评价杆臂旋转项的水平差 | 1.079216 mm |
| 最终评价误差向量的水平差 | 1.378278 mm |

评价杆臂项变化大于原生位置变化；这两个 RMS 不能按标量相加，也不等于各自对 RMSE 改善的贡献。不能把 0.460 mm 的最终评价改善全部称为原生平移状态收益。原生加杆臂与评价差的三维闭合 RMS 为 0.056227 mm，保留高精度原生与冻结 KF 输出舍入、局部坐标差异；没有为追求闭合修改评价数据。

两臂足端接受均 1,157/1,158 END，SDK 接受均 1,010、替代 871；RP 1,877，PVT position/velocity 各 1,884，raw Doppler 927，接受计数均不变。1157 对共同接受 foot END 中，1114 个 NIS 有变化（|ΔNIS| median 0.005005、max 0.386192），说明新共同状态确实进入原足端判断；不是新增足端供给或放宽足端门。SDK SA combined scale 仍为 1，RP 仍为 1.5；PVT position/velocity/Doppler 分别有 242/151/291 个配对 combined scale 变化，属于状态与原 OIM 的后续反馈，不能把最终效果全归给一次方向更新。

本次有真实共同状态作用和实际接受翻转，但没有足式背景放大位置收益的实证。两臂都是同一个足端背景，不能单靠这一对结果分离“足端导致的额外增益”；更不能用 NIS 变化替代导航收益。自然 REVOKE=0，普通 RETIRE 保留历史；本窗不认证撤销重放暴露。

## 证据与边界

全机器读出：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/VECTOR_DIRECTION_SA_BY2O_01/READOUT/READOUT.json`。该目录同时保留原 SA/carrier 全行、每来源权重/理由、全部场景、foot/SDK 汇总与 `MECHANISM_SUMMARY.json`。仓库配套表为 `VECTOR_DIRECTION_SA_METRICS.csv`、`VECTOR_DIRECTION_SA_STATE_EFFECT.csv`、`VECTOR_DIRECTION_SA_CARRIER_COUNTS.csv`。

父 PLAN SHA256 `3526d5d84706976342a7d3cd39fef90d6098a514c1dfb902334650eb4a0227b2`。执行脚本为 `scripts/paper_rebuild/unified_legged_heading_20261007/vector_direction_sa_readout.py`；只做一次完整归因，后续机制计数直接汇总已保存日志，不再调用 native/evaluator。

这是 reference-relative 单窗诊断。评价点杆臂沿用既有假设，不是独立 POI 标定；原足端仍为 XY，本次没有解决 NMB1 共同平移源矛盾。事件场景归属使用原保存时刻最近键，不冒称精确事件前后跳变。明显相对航向改善成立，总体研究目标仍未完成。
