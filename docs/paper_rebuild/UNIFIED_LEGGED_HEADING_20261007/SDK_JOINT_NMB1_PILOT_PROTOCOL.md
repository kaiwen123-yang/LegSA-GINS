# NMB1 同状态 SDK 有效来源差异：下一匹配 pilot 协议

2026-10-07。阶段名 `SUPPORT_SDK_JOINT_NMB1_01`。本文为执行前冻结协议；其后已按预算完成2 native＋2原冻结评价，未扩展或重跑。PLAN SHA为740c8dfc…de85ce，binary c42f1609…ebe327；首轮全部封存、在线参考0。常量模型的匹配水平收益判据失败，完整结果见 SDK_JOINT_NMB1_ATTRIBUTION.md；下文保留原问题、控制与评价合同。

## 问题与唯一模型变化

已有原足点与 SDK 速度之间的共同水平差，在完整支撑弧中仍约 6%，不能由 100 ms 相位采样或历史 1° 安装假设充分解释。足点与 SDK position 在源内位移关系上更一致，记录 foot_speed 与足点导数又具有阶段差；所有这些字段都不是独立真值。因此本次不拟合尺度、不把共同差叫滑移，不以贴 SDK 为依据替换足点。

两臂同时设置 `go2_body_velocity_discrepancy_mode: joint_constant`。二维 b 表示 SDK 相对于共享导航状态和其他观测的**有效来源差异**，在同一导航后验中保留 b 与状态、clone 的交叉协方差。它不是预先标定偏置，不宣称唯一物理来源，也不因当前差异与速度相关就引入更复杂模型。

首次有效 SDK 关联只增广 b 及其联合不确定度，不对原导航先验再做一次 SDK 更新；seed 单列，旧 SDK accepted/update counter 不增加。随后 source-aware 接受数可因 b 改变而变化；只核对源机会和替代时序，不要求旧 accepted 数恒等。之后 SDK、足端和其他观测均沿共同状态及交叉协方差作用。常量模型没有新增 random-walk、相位参数或结果驱动噪声调参。

## 两臂与控制

| 新臂 | shared SDK b2 | 足端 XYZ 更新 | SDK 替代时序 |
|---|---|---|---|
| REPLACE_NULL | joint_constant | 不更新，保留 clone 生命周期 | 原规则 |
| REPLACE_SUPPORT_XYZ | joint_constant | 原 XYZ 因子 | 与 NULL 相同 |

两份 config 从原 XYZ 模板生成，除 run/output 身份外唯一差异为 `support_pose_mode`。不用 SDK_NULL 第三臂。旧 off-mode REPLACE_NULL 与 REPLACE_SUPPORT_XYZ 已封存结果作背景对照；旧 null/XYZ 的 binary 身份差异继续披露，不为 metadata 重跑旧臂。

恢复原 R5 IMU8（包括历史 Rx(-1°)、既有 gyro 均值移除与 accelerometer scalar），不使用 nominal-frame 诊断的转换文件。原足端 XYZ、point sigma=0.01 m、SDK body-FRD provider、0.2 s timer、替代区间、足端 NIS、初始化、其他噪声数值、PVT priority fallback 和 carrier 输入全部保留。

完整窗 40621.403808498384–40972.56780471802 s；同一位置空窗 40749.60018873215–40912.600195646286 s；预期每臂 80,272 个 native／匹配评价时间点。空窗仍没有新绝对 carrier 航向信息，不能将 b 的改善宣称为新增绝对航向可观性。

## 证据与评价

原 R5 point transform、reference bracket=0.15 s 和评价样本保持。先封存两臂 native 与 online file audit，再打开参考，最多两次臂级评价；共享一次只读 reference payload 不构成额外方法评价。全窗、空窗、恢复后首 carrier 前及尾段的 H/Up/yaw、p99 和支持分母按原定义。

新增 `SDK_DISCREPANCY_EVENTS.csv` 由 engine 提供，保存 seed／SDK 接受与拒绝／ordinary／FOOT_UPDATE 的：来源时间与身份、b_f/b_r 更新前后值、后验 Pbb00/01/11、Pxb 与 Pbclone 范数、共同状态 delta_p_NED/delta_v_NED/delta_phi_NED/delta_ba，以及实际创新向量与 NIS。最终列名固定在 PLAN。delta_phi 是 NED 左旋转切向量，不是欧拉 RPY 差；所有 delta 表示 measurement conditional-error-mean 的变化映射到反馈切向，不是精确 NAV 跳变。b 前后值是 nominal 加 conditional error mean。SDK source_time 是实际源行，FOOT 是实际源事件，其他 ordinary 行是 state update time。

需回答的实际问题：

- seed 是否恰好一次、导航状态未被双计入，后续 SDK/foot 源创新及接受分母是否实际发生。
- 足端更新是否通过既有 cross covariance 改变 b 与导航状态；静态 b 曲线或 shadow ledger 不足以证明这一点。
- b 的估计和不确定度如何演变，NULL 与足端臂有何差异；不要把 Pbb 缩小等同于真实标定正确。
- 新的 foot-minus-null 水平效果与旧 off-mode 效果相比是否改变；若 H 惩罚仍在，就报告常量模型不足，不继续扫参数或选择阈值。

没有为了通过 gate 而设置误差门、删除片段或把 SDK position 变成新在线输入。b 可能与体速／姿态存在不可辨识方向，数学检查与实际协方差读出共同限制其解释；本 pilot 不预先宣称研究目标完成。

## 执行入口与封存

新增 `scripts/paper_rebuild/unified_legged_heading_20261007/sdk_joint_nmb1.py`，包含 prepare/native/evaluate 三个入口，复用原 audited native runner 与冻结 evaluator 数学。prepare 会复制最终 binary，固定新源码／runner／所有原 provider／旧对照及新 config 哈希。最终 diagnostic 增加 SDK_DISCREPANCY_SUMMARY.json，保留 mode、initialized、seed 身份与次数、final_b/Pbb 及维度。首 SDK 的 kind=SDK_SEED_NO_NAVIGATION_UPDATE、innovation_dimensions=0，BODY accepted=0；后续 SDK kind=BODY_HORIZONTAL_VELOCITY。创新已经包含 b 并减去 full H*conditional mean，NIS 使用 full joint P 和 scaled R，不能再减一次 b。

计划输出 `/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/SUPPORT_SDK_JOINT_NMB1_01/`。root 保留数学检查、binary 审核、执行授权及结果后的下一动作选择权。协议本身不触发 native。
