# 相位无增益：相关性反例与来源模型决策

日期：2026-10-07。状态：ANALYTICAL_IMPLICATION_OF_EXISTING_WORKING_DIAGNOSTICS。本轮读取当前源码与既有小结果报告，复核代数；没有重新读取原始/provider/联合先验/相位模型大型输出，没有新增矩阵诊断、测试、导航或评价。既有全部结果和 V3 保留。

## 1. 新结论及其证据范围

原结果只判定四个固定目标在 UNKNOWN-cross Young 更新族内无改善。本次把问题进一步定位到当前线性工作模型允许的相关性集合：它容许一个相位创新完全不携带新状态信息的反例。因此，仅改变 epsilon、固定线性增益，甚至仅基于同一创新改变非线性修正方式，都不能保证在这个完整不确定集合内改善。

这不证明真实载波没有信息，也不是物理 SO(3)、全部原始相位观测或实际机器人导航的不可改善定理。需要用来源事实收窄允许的相关性结构，或引入确有新增信息的观测/场景；不能把反例当作实际噪声机制。

数值依据复用 ARC_PHASE_REAL_INFORMATION_RESULTS.json 的原登记 e80e9d9：857 个有效配对块，全部已记录 Rbar 白化 HPHᵀ 最大特征值不超过 0.03274515714116526；61 个缺模型和3个末端缺先验不适用，仍保留原921分母。原独立结果复核已检查这些标量字段。本轮不是逐矩阵独立复算或区间 PSD 证明。

这些谱属于旧用样策略的完整两端 P6。新因果用样策略改变先验数值；本推论不能自动算作新策略下857块的数值验证。

## 2. 保留两端边缘矩的条件反例

全部量条件于同一个固定信息集 I。e 是六维两端姿态线性化误差，创新 r=H e+d；P 为其有效条件二阶矩上界。Q0、Q1 是已经映射到共同差分关系空间的端点噪声矩，不再重复映射。当前代码使用 Rbar=2(Q0+Q1)，对跨端相位相关性及状态—相位相关性均不作已知声明。

先把矩阵视为精确有效矩，假设 P>=0、Q0>=0、Q1>=0、S=Q0+Q1>0，且 A=HPHᵀ<=S。模型集合只约束这些边缘矩及 joint PSD，不附加误差支持域、独立性、生成链或其他 cross 限制。

选择独立零均值 Gaussian 变量 e、v，Cov(e)=P，Cov(v)=S-A，并令

    d = -H e + v.

因此 Cov(d)=S，Cov(e,d)=-PHᵀ，创新 r=v 与 e 独立。奇异 P 或 S-A 允许退化 Gaussian，无需求 P 的逆。

这个构造还能保持两个端点各自的边缘矩。定义

    B = Q1 - Q1 S^-1 Q1
      = Q1 S^-1 Q0
      = Q0 S^-1 Q1
      = Q0 - Q0 S^-1 Q0 >= 0.

各矩阵不要求交换。等式由 S=Q0+Q1 得到，对称性由第一式得到；B 的半正定性由 0<=Q1<=S 的 Schur 补得到。取零均值 Gaussian 变量 u，与(e,v)独立且 Cov(u)=B，再定义

    eta1 =  Q1 S^-1 d + u,
    eta0 = -Q0 S^-1 d + u.

直接代入可得

    eta1-eta0 = d,
    Cov(eta0)=Q0,  Cov(eta1)=Q1,
    Cov(eta0,eta1)=0.

所有量是独立 Gaussian 源的线性变换，完整联合矩自动 PSD；Q0 或 Q1 可以奇异，只需要 S 正定。端点噪声之间不相关，并不意味着它们与状态误差不相关。

这里的零跨端 cross 只是证明存在合法反例的一个数学选择，不是把实际未知 Q01 设置为0，也不是实际更新方案。若 P/Q 是上界而非精确边缘矩，该构造以 P、Q0、Q1 饱和上界，仍属于仅有这些上界的集合；如果源合同另有限制则必须重新判断其归属。

## 3. 为什么不限于 Young 网格

在上述反例下，对看到本次创新前确定的任意线性 K，更新误差 e-Kr 的二阶矩为

    P + K(S-A)Kᵀ.

对事先固定的任意 W>=0，风险不低于跳过更新的 T=tr(WP)。不更新对全部允许模型风险不超过 T，而反例的原误差矩等于 P，因此在这一不确定集合中，跳过是 minimax 解之一，不要求唯一。

若进一步允许任意仅依赖本次 r（以及固定 I）的可测修正 g(r)，并要求有限二阶矩，Gaussian 反例中的 e 与 r 独立且 E[e|I]=0，所以

    E[(e-g(r))ᵀ W (e-g(r)) | I]
      = tr(WP) + E[g(r)ᵀ W g(r) | I] >= tr(WP).

这一加强限于同一个无支持域限制的线性 surrogate 及同一残差信息。它不约束使用额外原始测量、已知物理误差支持、另行证明的源结构或新的观测模型的方法；不把 Gaussian 当作实际接收机噪声假设。

四个旧目标都具有 W=LᵀL 的形式，因而包含在以上条件命题内。它们是两端/当前/相对/公共姿态的小角误差工作风险，不是实际 yaw、H/V、完整导航状态或轨迹精度结论。

## 4. 原信息谱为何满足更强的充分条件

源码 arc_phase_real_information.py:312-315 明确构造 Rbar=2S；arc_phase_information.py:261-275 用 Cholesky 计算 L_R^-1 A L_R^-T 的谱。S 白化的最大特征值相应为原值的2倍：

    lambda_max(S^-1/2 A S^-1/2)
      <= 2 * 0.03274515714116526 < 1.

所以已有数值诊断远离 A<=S 的边界。此处仅复用已报告最大值与精确缩放恒等式，没有另做矩阵分解、修补、特征值裁剪或新样本判定。P/Q 的原资格仍是浮点容差下的工作资格；物理误差矩及精确实数 PSD 未因此得到认证。

这一加强意味着：即使将来只证明两个相位端点不相关，从 Rbar=2S 换为 S，在状态—相位 cross 仍完全未知的相同工作集合中，上述反例仍存在。仅去掉2倍因子不足以保证获得信息。它不排除具有依据的、更完整源模型带来收益。

## 5. 当前代码能证明的来源边

以下为当前跟踪代码的定向静态追踪。没有重读真实载荷、重建 provider 或证明整个磁盘不存在采集程序。

|来源边|源码位置|已经证明与仍缺内容|
|---|---|---|
|RAWX精度字段→工作Q|`src/legsa_gins/paper_rebuild/horizontal_literature/shared_raw_backend.py:1139–1151`；`carrier_phase/multignss.py:272–296`|代码将两机报告的相位标准差转米、方差相加，并传播共享pivot的DD相关性。默认SD矩为对角工作模型，未资格接收机间、信号间、code–phase物理cross，也不是总相位误差界。|
|保存Q→两端Q0/Q1|`scripts/paper_rebuild/carrier_phase/real_trial.py:344–350`、`arc_phase_saved_model_qualification.py:225–249`；`carrier_phase/arc_phase_difference.py:309–333`|phase子块经F0/F1映射；跨端Q01未知，使用条件界2(Q0+Q1)。代数传播没有增加物理校准。|
|原始码/星历→anchor/G/相位修正|`real_trial.py:319–335`；`multignss.py:219–220,276–301`|RX1 raw-code SPP给anchor；两机pseudorange决定发射时刻，所有DD共用NAV与anchor。因而存在共享输入，几何/anchor/钟差误差尚未传播进Q。|
|广播质量→误差矩|`carrier_phase/ephemeris.py:50–74`；`multignss.py:280–296`|广播状态记录variance_m2及健康/时效门，但Q构造未使用该variance。不能把“有字段/通过门”解释成LOS总误差已受界。|
|anchor→有限误差域|`carrier_phase/causal_anchor.py:1–21,36–40,116–128,203–220`|100m初始半径、5m/s增长、20s保持属于显式工程假设。现有雅可比只是局部一阶敏感度，不是有限半径误差界；SPP RMS不替代anchor covariance。|
|后端更新→P6与C_en|`cpp/legsa_v23_port_core/src/kf_gins/gi_engine_arc_clone.cpp:163–175`；`gi_engine.cpp:1144–1145,1229–1230,1302–1303`|P24/映射P6保留state-state cross；GNSS/PVT内部原始观测身份仍UNKNOWN，无PVT对RAWX的影响矩阵。普通工作Kalman/Joseph传播也不能自证P是实机误差界。|
|SDK足点→足对|`scripts/paper_rebuild/carrier_phase/foot_pair_provider.py:52,163–191`|直接读取12维SDK足位置，做轴翻转后取两足差；未读q/dq，也未用足速。SDK字段→provider明确，编码器→FK→SDK字段的链没有闭合。|
|SDK力→支撑弧|`carrier_phase/support_arcs.py:94–97,157–245`|力阈值、持续时间和退役逻辑可追溯；这些规则没有认证真实接触/无滑移，高层运动状态也不能代替。|
|SDK速度/RP+A1→NED-HV|`src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py:142–154,175–192`|对A1 yaw展开并线性插值，再旋转/缩放SDK速度。行time不是全部上游依赖时刻；这是新的具体来源时序缺口，见下一节。|
|IMU/足端安装与时间|`src/legsa_gins/input_generation/imu_txt_builder.py:89–136`；`foot_pair_provider.py:143–148,176`|IMU有轴变换及默认安装旋转，足点仅轴翻转；无证据可盲目给足点追加同一旋转。两足差消去共同原点平移，不能消去未知旋转。source stamp与replay availability不证明实际采样/接收时间。|

表中缩写 `carrier_phase/` 均位于 `src/legsa_gins/paper_rebuild/`。安装、天线相位中心变化、时变bias、物理错时及非线性余项也未建立总误差预算。相位弧的lock/half-cycle/TDCP门不能认证没有隐藏周跳。

独立来源追踪分别由 research_map（相位/P来源）和 fusion_evidence（SDK/速度/足端）完成，均限只读代码与既有小报告。foot_position的字段名、Go2高层接口、SDK内部姿态一致性，都不能用来推断统计独立。

## 6. NED-HV上游插值：下一项可执行工作

`interpolate_a1`在142–154行对整段A1序列调用np.interp。对严格位于两个A1历元之间的查询时刻，数值同时依赖前后两个航向样本；175–180行还会在常规路径先把A1时间舍入到毫秒。此实现的来源含义不能仅由输出行time表达。

上一轮causal_unique_latest保证的是选中的provider报告时刻不晚于触发和实际状态，且同一generation不重复尝试。它没有重建provider，更没有验证其每个上游原始依赖时刻。本发现不推翻4598条provider行层面的已通过结果，但阻止将它扩大为整条源生成链已因果。

当前只能从代码证明存在这个依赖机制，尚未统计三个真实窗口中多少次接受依赖后续A1。不得把1880或4598直接当作这一上游问题的计数，也不推断实际网络arrival。

下一项应是一次有界、被动的依赖时刻核对：沿已有provider生成身份，关联每个HV行的Go2源以及实际用于插值的A1左右端点，保留原始和舍入后时刻；再与新策略的接受记录连接。记录数值完全不变，先回答“哪些接受在报告源依赖层面使用了状态之后的A1”。所有真实数值读取另行登记有限输入/次数，原始及旧结果只读。本轮未执行此核对，也未选择新的旋转/保持规则。

若证实仍有后续依赖，再单独设计来源完整的可用性门或明确的因果重建方案，分别报告代价与速度值变化；不得将这项上游处理的作用归为载波信息收益。真实arrival资格仍须采集链支持。

## 7. 科学决策与范围

- 暂不接入当前相位更新，不重复epsilon搜索；当前强反例要求优先给出来源支持的state-phase cross限制与总误差模型。未来若有可信的非零Q01使差分误差更小，须按新模型重新判断，本结论不禁止该路线。
- 下一项可直接开展的是上述HV上游依赖核对；它能利用现有文件推进，不需要先假定具备新硬件。信息增益计算不因用样政策改变而自动重跑或升级。
- 足端继续要求实际collector/固件、原始关节、安装与时钟证据。新reader的重复字段/精确维数和frame_evidence绑定也有可修缺口，但解析加固不能制造独立测量；本轮不修改它们或旧provider。
- 真实转动/支撑切换/断弧的最终验证仍需独立参考及设备信息，按既有ACQUISITION_PLAN.md执行。新增局部命题和来源诊断不构成目标完成。

独立代数复核（heading_evidence）：第1–4节分端构造、饱和上界见证、固定线性minimax结论和仅依赖同一创新的g(r)推论均成立；无需矩阵交换或端点矩可逆。旧策略谱不能自动验证新策略，浮点资格不能替代物理/精确PSD认证。此次仅静态复核，未执行数值计算或测试。

证据入口：[原真实信息诊断](ARC_PHASE_REAL_INFORMATION_RESULTS.md)、[原独立结果复核](ARC_PHASE_REAL_INFORMATION_RESULTS_REVIEW.md)、[足端条件反例](FOOT_UNKNOWN_CROSS_PROOF.md)、[因果用样修正](HV_CAUSAL_POLICY_RESULTS.md)。总体研究目标仍未完成。
