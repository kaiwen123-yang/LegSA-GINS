# SDK XY 来源差异的共同状态模型：最小设计

2026-10-07；依据本地 ea5ad99 诊断封存结果。**状态：实施前冻结设计。其后实现与必要合成检查已完成，2＋2匹配实测水平收益判据失败，未正式采用；当前结果见 SDK_JOINT_NMB1_ATTRIBUTION.md 与 PROGRESS.json。** 本文不改 C++、不新增测试或 native，不把名义 frame 诊断转为默认配置。默认继续沿用历史输入合同（含原 IMU 安装旋转）、原初始化、XYZ 足因子、噪声、杆臂、baseline、SDK 区间替代和 carrier provider。

## 1. 要回答的问题及本次模型选择

NMB1 主空窗旧匹配 null/XYZ 的 H 为 5.55048/7.99076 m；撤掉历史 IMU 安装旋转后为 5.31623/7.98646 m，足端惩罚由约 2.440 m 变为 2.670 m。故停止安装角方向。XYZ 已保住垂向信息，但足端与 SDK 的共同水平位移来源冲突仍在。

源内部证据同时表明：足端与 SDK position 增量接近，SDK velocity 积分更大；足点与 foot_speed 通道也有相位相关差异。完整共同支撑弧仍有约 6% 差异，不能只靠延长首 100 ms 区间消除。SDK position、velocity、foot 均不能互充独立真值，因此本设计不宣称“SDK 真偏置已识别”，不按 7.5% 缩放输入，也不把偏差预先指定给真实滑移。

选择一个可反驳的最小工作模型：**SDK 原前／右两维速度，相对足端／PVT／carrier 共同后验，允许存在一个持续、body 分量固定的加性来源差异 b=[b_f,b_r]。** 保留足端 XYZ 的全部共同与差分信息。已观察到的速度关联说明常量加性模型未必充分；这里只检验其能否吸收持续均值分歧，而不让 SDK 与足端轮流把同一运动状态拉向不同均值。若该最小模型失败，不能在本 pilot 内增大 Q、改为速度尺度或按时段换参数来追结果。

## 2. 状态、误差和测量符号

R 为当前 engine body 到 NED 的旋转，v 为当前 NED 速度；S=[[1,0,0],[0,1,0]]，SDK 实际只有原 body XY 观测，不补 z。

    z_k = h(x_k) + b + nu_k
    h(x_k) = S R_k^T v_k
    r_k = h(xhat_k) + bhat_k - z_k

b 是现有工作坐标合同下的来源差异参数，不是世界系速度向量，也不是足端 slip 状态。机器人转向时不把 b 另转到世界系；其两个数始终对应 SDK forward/right 通道。安装角、原点或内部滤波差异仍可能贡献这个 effective 参数，不能从 b 的数值反推单一物理原因。

按仓库当前混合误差约定：

    v_true = vhat - delta_v
    R_true = Exp(delta_phi_NED) Rhat
    b_true = bhat + delta_b

反馈是 vhat←vhat−delta_v、Rhat←Exp(delta_phi)Rhat、bhat←bhat+delta_b。线性化 h_true=hhat−H_x delta_x，故：

    r = H_x delta_x - delta_b - nu
    H_v   = S Rhat^T
    H_phi = -S Rhat^T [vhat]_x
    H_b   = -I_2

**H_b 必须为负号。** 若误用 +I，却仍加法反馈 b，会把来源差异推向错误方向。其余当前状态列及 clone 列按该瞬时速度模型为零；原 body velocity 模型的 H_v/H_phi 保持。

常态状态为 23 维，活跃 pose clone 时为 29 维：

| 索引 | 状态及误差坐标 |
|---|---|
| 0–20 | 原 21 维共同导航误差，约定不变 |
| 21–22 | SDK 来源差异 delta_b，true−nominal，m/s |
| 23–25 | clone position，nominal−true，ECEF m |
| 26–28 | clone attitude，ECEF 左乘误差 |

未初始化 b 时仍是原 21/27 维；初始化标志属于 engine 状态。不是把 b 放进输出后的补偿层，也不是两个彼此独立的滤波器。

## 3. 首个 SDK 观测的关联增广，不设任意宽先验

选择**原调度下首个实际有资格消费的 SDK 源行**：沿用过去最新、唯一尝试、原 age/source_valid、原 START–END 区间替代规则。不能借用被替代的 SDK tick 提前初始化，也不能按 residual、参考误差或某个好窗口换首行。

令初始化前完整 joint error 为 xi，均值 mu、协方差 P；它可以是无 clone 的 21 维，也可一般性包含一个 27 维旧 clone。H0 是该 SDK h 对完整 xi 的 Jacobian，clone 列为零。观测噪声记 nu0，工作协方差为 R0。

选取 nominal：

    bhat0 = z0 - h(xhat0)

这不是已确认的真实偏差，而是新参数的零残差坐标原点。由观测模型直接得到：

    delta_b0 = H0 xi - nu0
    mu_b     = H0 mu
    P_xb     = P H0^T
    P_bb     = H0 P H0^T + R0

即：

    mu_aug = [ mu ; H0 mu ]
    P_aug  = [ P          P H0^T                 ]
             [ H0 P       H0 P H0^T + R0         ]

按第 2 节的规范索引排列 b 与 clone。若正常路径在各更新后已经反馈清零，则 mu=0，新增误差均值也是零；若不是，不能强行丢弃 H0 mu。也可把 H0 mu 加入 bhat0 后把新增误差均值置零，但须与整个 nominal feedback 一致，不能两种约定混用。

**增广必须原样保留旧导航／clone 的 mu 和 P；首行不再执行一次 ordinaryUpdate。** 首 SDK 为自由 b 提供了关联分布，未凭空给导航增加绝对速度信息。记为独立事件 `SDK_DISCREPANCY_INITIALIZED`，记录源行身份、bhat、P_bb 和 P_xb；不能把其人工零 residual 算作导航更新成功。

这里 R0 使用同一 SDK provider 的 std、现有固定 std_scale 所定义的 2×2 基础测量协方差，不另拍宽先验。当前 source-aware 具有 rolling innovation 状态：首行 b 无先验，零 residual 不具有创新检验意义，因此初始化**不把零 residual 写入 rolling innovation、不重复跑 residual 驱动更新**。源合法性／时间／替代规则不变；从第二个 SDK 行开始，用含 b 的真实 residual 进入原 source-aware 流程，保留其余既有机制。这一初始化例外须写进 manifest，不能静默伪装成原普通 SDK 接受。

上述 P 公式的工作假设是 N=Cov(xi,nu0)=0。SDK 内部使用惯性／运动学，真实 N 未标定；增加 b 不会自动证明噪声独立。若未来已知 N，正确公式应为：

    P_xb = P H0^T - N
    P_bb = H0 P H0^T + R0 - H0 N - N^T H0^T

本 pilot 不拟合 N，也不声称解决所有 SDK／foot 噪声相关性。它精确保留的是**初始化主动引入的状态—来源差异交叉协方差**，并显式建模一个持续均值差异。

## 4. 传播、普通更新、clone 和反馈必须共同进行

唯一首轮过程模型为常量 body 参数：b_{k+1}=b_k，Q_b=0。这是待证伪的确定性参数假设，不是由参考结果选择的极小噪声。不存在每步遗忘、速度相关 Q、足对特有 Q 或 token 切换重置。

对常态 23 维：

    Phi23 = diag(Phi21, I2)
    Q23   = diag(Q21, 0_2)
    P_xb_next = Phi21 P_xb

pose clone 活跃时扩为 diag(Phi21,I2,I6)，保留所有交叉项。原 IMU bias、scale、p/v/R 过程和噪声保持。

- 后续 SDK 使用 H=[H_x,−I2,0_clone]，2D residual/covariance 进入**整个** 23/29 维 Joseph 更新；SDK 可以通过交叉项改变 b 和导航，不能称为 GNSS-only calibration。
- PVT position、receiver velocity、RP、native carrier 和足端因子的直接 b 列均为零，但通过 P_bx 更新 b；反向也可通过 P_xb 影响共同 R/v/p 及原 IMU bias。不能只更新 P_bb 或把交叉项清零。
- START 的原 pose augmentation Jacobian 为 J6×21。新 Jacobian 是 [J,0_6×2]；虽然直接 b 列为零，clone 与 b 的交叉为 J P_xb，必须保留。
- 原 XYZ 两足因子的残差、完整点噪声和几何 Jacobian 不改。仅把原 H 的 clone 列 21–26 搬到 23–28，插入两列 b=0。它的共同及差分信息都保留，不把速度来源差异转嫁为足端降维。
- END/RETIRE 后只边缘化六维 clone，保留完整 23 维状态。b 不随正常 episode 结束消失。
- feedback 使用原导航及 clone 反馈，并执行 bhat+=delta_b。reset Jacobian 在 b 块为 I2，其余使用原 current/clone reset，**全矩阵**运输 P；b 是 additive source 参数，不跟随姿态误差反馈另旋转。

SDK 的 source-aware 信息接受也必须使用同一个联合分布，不能仅改 residual 后仍沿用旧 21 维 HPH：

    innovation = r - (H_x mu_x - mu_b)
    S_innov = H_x P_xx H_x^T + P_bb
              - H_x P_xb - P_bx H_x^T + R

这是 H_full P_joint H_full^T+R 的等价式，保留 source discrepancy 的不确定性及交叉抵消项。当前 `applySourceAwareWeighting` 直接读取旧 dx_/Cov_，实现时必须显式接入 full joint 计算或上述等价式。普通 b 列为零的源使用当前导航边缘分布与 full joint 计算相同；SDK 不相同。这里的信息接受、权重、更新和后续撤销须共享同一 posterior。

源调度沿用 REPLACE 模式：START 到 END/RETIRE 之间原本被替代的 SDK tick 仍被替代。该设计没有把 SDK 强塞进足端区间，也不恢复历史被替代的 SDK。

## 5. 可辨识与冷启动边界

首条关联增广是适定的有限分布构造，不等于 b 已识别。其不确定性包含当前导航误差 H0 P H0^T；当前速度／姿态越不确定，新增 b 越不确定，且两者高度相关。不能只输出 sqrt(diag(P_bb)) 而丢掉 cross 后宣布校准完成。

在定姿、无外部运动约束的简单情形，v→v+R a、b→b−S a 保持所有 SDK 测量不变；因此 SDK 自身不能区分共同速度偏移和 b。单次 position 也未必即时拆开二者，需要跨时刻动力学或实际速度约束。足端共同项在其接触假设成立时提供区间位移约束；足对差分主要提供相对方向约束，不能独自识别共同速度差异。carrier 直接约束方向，经相同状态和动力学帮助区分映射，但不自动给出平移真值。

PVT／receiver velocity 可用期、有效 XYZ 支撑以及转动条件共同决定可辨识性。IMU acc bias／倾斜会经加速度和时间积累与速度来源差异耦合；在近定速、短同长支撑区间里尤其容易混淆。共同 foot/SDK 误差仍可同时误导运动状态，本模型不将足端或 SDK position 升格为真值。

失联期 b 从此前联合后验传播，不设为零，也不凭 SDK residual 变小宣称重新校准。Q_b=0 不阻止测量改变 b 的后验均值，但断言同一个潜在 b 持续不变；若源差异随速度／步态变化，该假设会留下结构化 residual，或使后验过度确信。因此只允许一次固定 pilot，不能在失败后通过增大 Q 让 b 任意跟踪每次冲突。

冷启动期间仍可用足端、PVT 和 carrier 原机制；首个 SDK 只增广，随后 SDK 保留与先前观测相容的变化信息。没有任何有效 SDK 时维持原状态，不伪造 b。若首 SDK 被支撑区间替代，按原时序等下一实际机会。有限先验不是“再等参考给出偏差”，也不是先运行旧算法再拿其 NAV 当真值拟合 b。

## 6. 0.5 s 撤销的实际含义

所有 checkpoint 必须完整保存 b 是否初始化、bhat、23/29 维 mu/P、首行来源身份、SDK 唯一消费时钟和 source-aware 记忆。现有 deep-copy GIEngine 的设计可以承载这些字段；只在 writer 外另存 b 会破坏此条件。

在现有 0.5 s 可恢复范围内，某个足因子被原点／长度证据撤销后：恢复该因子 START 前的共同 checkpoint，排除该因子，重放原 IMU、SDK、PVT 和 carrier。b 对这个足因子的响应以及它随后经 SDK 对导航的影响均会重算。如果 checkpoint 早于首 SDK，回放应从未初始化状态重新用同一首源行增广；如果在其后，恢复当时的完整 b posterior，不再次消费首行。

独立 partial carrier 前端候选不因为 b 或足端撤销而被删掉；其在被纠正共同后验上的 innovation、权重和接受需重新计算。SDK 原区间替代时序仍保留，撤销不意味着补回当时被替代的 SDK。

超过现有历史窗口、已进入 b/导航后验的旧因子依赖，仍不能从当前 P 中简单相减。要继续报告 EXPIRED_NO_POSTERIOR_RESTORATION，不能宣称 b 被清零就完成撤销。本设计没有扩大回放窗口，也没有证明任意长期的来源追溯已解决。自然数据没有 REVOKE 的 pilot，只能验证普通共同作用链，不能冒充新的实测撤销证据。

## 7. 唯一首要数学检查

采用**一个线性联合 Gaussian fixture 对照独立 batch posterior**，包括非零 SDK H_phi、有限导航 prior、首 SDK、一个后续运动锚和第二个 SDK。batch 把 b 设为无信息先验，首 SDK likelihood 只出现一次；sequential 按第 3 节增广，再按第 4 节更新。比较完整 mean、P 和 P_xb，不只比残差。

同一 fixture 必须体现三个决定性事实：首 SDK 不收缩原导航 P；H_b=−I 与加法反馈一致；后续锚／SDK 的联合 posterior 与 batch 一致，并在无锚的定姿速度平移方向上不凭空增加可辨识性。这样能同时抓住符号错误、首行双计数和 cross 丢失；无需重跑已闭合的全部 pose-clone 数学测试。未来实现阶段再执行该检查，本次设计没有运行。

## 8. 单次匹配 pilot 的准入与判读

实现前只需冻结上述模型、初始化例外和 source lineage，并通过第 7 节必要检查。为 b 另设噪声／门限、改安装角、按误差换首 SDK 或改足端 XYZ 都不在本 pilot 范围。

只运行同一既有 NMB1 全窗的两个匹配臂，沿用历史输入合同：

| 臂 | b 模型 | 原 SDK 区间替代 | XYZ 足端因子 |
|---|---|---|---|
| REPLACE_NULL + SDK_DISCREPANCY | 开 | 保持 | 不消费 |
| REPLACE_SUPPORT_XYZ + SDK_DISCREPANCY | 开 | 保持 | 原样消费 |

两臂的首 SDK 选择规则、Q_b=0、全部原噪声、时间窗口、init、binary 和 raw/provider 身份相同；仅足端消费不同。既有历史 null/XYZ 是已封存背景，不新增安装角或速度缩放臂。实际首源行若因为原时序相同，应身份一致；不能从结果另选校准段。

先读真实机制：初始化时原导航后验未被 SDK 额外更新；随后足端/PVT/carrier 通过 full cross 改变 b，后续 SDK 又影响共同 v/p；XYZ 仍有真实接受，不能靠全部拒绝来消除惩罚。记录 b_f/b_r、P_bb、与 v/phi/acc-bias 的 cross 摘要以及 SDK 含 b 创新，不把诊断输出反馈为调参输入。

核心科学判据是主空窗中，**新增模型下 XYZ 对其匹配 null 的水平位置增量效应是否从惩罚变为收益，同时保留已有 XYZ 垂向收益**。若只降低 SDK residual、只让两臂共同变好、或仅缩小而未消除足端惩罚，须分别报告，不能称为统一导航目标已达成。读取固定全窗及主空窗的水平速度／位置、Up 和 source acceptance，保证最终作用确实沿同一 R/v/p 链发生；参考只用于冻结窗口的离线评价，不校准 b 或选模型。

速度关联的 residual 可用预先固定源速度分层作解释，但不得在本轮增加速度尺度、Q 或分段参数。任何结果都只支持／反驳这个“持续常量来源差异”工作模型；不证明 SDK 的真实物理偏置，不直接转为正式方案。

## 9. 现有代码接入约束（供下一实现）

- `factors/body_velocity_model.cpp:13–20`：现有 residual/H_v/H_phi 是基础；新增 b 需要进入 residual 和完整 joint H，不在 provider 文件里先减估计值。
- `factors/pose_clone.hpp:8–11`：当前硬编码 21/27 维，新的当前 23／活跃 29 维与 clone 索引须明确；不能只给输出追加两个数。
- `factors/pose_clone.cpp:84–124`：ordinary update、full reset 和 marginal 必须保留新增状态及全部 cross；XYZ 几何本身不改。
- `kf_gins/gi_engine.cpp:1706–1750`：现有 SDK 独立 tick／唯一源消费与 source-aware 路径；首行增广与后续普通联合更新要分清，原区间替代继续生效。
- `runtime/support_pose_replay.cpp:54,99–112`：缓存输入与完整 engine 恢复／重放；新增 b 及初始化/source-aware 状态必须随 checkpoint 一起恢复。

下一实施最关键的边界是：**关联增广一次、H_b 负号、所有更新保留完整 cross、首零残差不污染 source-aware 记忆、历史 frame 默认不改。**
