# 跨时相位：来源相关性模型与可检验的突破条件

2026-10-07。分析依据为本地 `31c786b` 及其新先验诊断。此文新增条件推导和定向源码追踪；没有读真实相位/先验载荷，没有新矩阵、导航、评价、参数扫描或实机执行。现有 V3 和全部数值结果保留。

## 1. 这次要解决的具体问题

最新三窗 857 个合格块在四个固定 Young 目标上仍全部 SKIP，并均满足宽泛 UNKNOWN-cross 工作集合的无信息反例条件。因而下一步不是寻找另一个 epsilon，而是回答：**实际生成链能否排除足以取消目标信息的 state–phase cross？**

“相位两端互不相关”“相位放在 END 的 GNSS 更新前”“SDK 是另一个消息”分别不等价于 state–phase 独立。报告时间合法也不等价于物理采样、到达及条件误差模型合格。

本文件不给真实 cross 赋值；下面的数学分界用于说明必须取得什么证据。既有 P/Q 是未完成物理资格的工作数组，不能直接套用正收益结论。

## 2. 精确矩模型下，相关性要约束到什么程度

全部变量条件于同一个固定信息集 I，H 和目标在本次残差之前固定。假设误差已经中心化且

    r = H e + d,
    Cov(e | I) = P >= 0,
    Cov(d | I) = R > 0,
    Cov(e,d | I) = C.

这里 P、R 是有效的精确边缘矩；不是“工作矩阵已通过 PSD”或“仅有上界”。未知偏差还需单独处理，Cov 约束不能自动保证 MSE。

令对称平方根/伪逆平方根定义

    D = P^(dagger/2) C R^(-1/2),
    M = R^(-1/2) H P^(1/2),
    gamma_bar = min(gamma, 1).

P 奇异时必须满足 range(C) subset range(P)。考虑所有 joint PSD 且 ||D||_2 <= gamma_bar 的完整相关性集合，gamma >= 0 必须由来源证据支持。joint PSD 自身只给 ||D||_2 <= 1，通常太宽。

### 2.1 完全取消状态信息的门槛

反例 C* = -P H^T 对应 D* = -M^T；因此它属于上述集合，当且仅当

    sqrt(rho) <= gamma_bar,
    rho = ||M||_2^2 = lambda_max(R^(-1/2) H P H^T R^(-1/2)).

这给出“该反例能否被源约束排除”的精确门槛。单纯拒绝某一个反例通常不足以证明收益；下一节在这个特定完整谱范数集合内给出固定标量目标的双向判据。

### 2.2 预先指定标量目标的分界

令目标为 l^T e，tau = l^T P l > 0，并定义

    u = P^(1/2) l / sqrt(tau),
    s_l = ||M u||_2.

l 必须事先由所关心的物理方向和误差定义给定，不能看残差或结果后选取。tau=0 时，不能严格改善零方差。

**无保证改善的一侧。** 若 s_l <= gamma_bar，取 D=-u(Mu)^T。它的范数为 s_l，且列空间在 range(P) 中。令 x 为标准 Gaussian，z 为与 x 独立的零均值 Gaussian、Cov(z)=I-D^T D，并取

    e = P^(1/2) x,
    d = R^(1/2) (D^T x + z).

这保持 P、R、合法 C 和 joint PSD。归一化目标 t=l^T e/sqrt(tau)=u^T x 与整个白化创新 Mx+D^T x+z 的 cross 为零；联合 Gaussian 下两者独立，允许退化 Gaussian。因此任何仅依赖本次创新、具有有限二阶矩的修正，都不能在整个允许集合中保证严格改善这个目标。

**可构造保证改善的一侧。** 若 s_l > gamma_bar，令

    b = M u / s_l,
    alpha = ||M^T b||_2^2,
    V = 1 + alpha + 2 gamma_bar sqrt(alpha),
    k = (s_l - gamma_bar) / V,
    G = k (P l / sqrt(tau)) b^T R^(-1/2).

对所有允许 cross，标量测量 y=b^T R^(-1/2)r 满足

    Cov(t,y) >= s_l - gamma_bar,
    Var(y) <= V.

于是固定线性更新 e-G r 满足

    Var(l^T(e-G r)) / tau
      <= 1 - (s_l-gamma_bar)^2 / V < 1.

两式直接来自 ||D||_2 的双线性界，无需把未知 C 填零。这是保守的可构造增益，并未声称它是完整矩阵目标的最优增益。

**范围。** 在此精确矩/中心化/完整谱范数类内，gamma_bar < s_l 是固定非零方差标量目标存在保证改善的充要条件；gamma_bar < sqrt(rho) 等价于存在某个有向标量目标可以改善。后者不保证预定 yaw，也不保证原四个矩阵目标或 H/V/yaw 联合改善。若未来采用更具体的源结构，可行 C 集合不再是这个完整范数球，需按该集合重新分析。

### 2.3 当前 857 块不能给出什么

已报告最大 rho=0.03275681435907679 对应当前 Rbar 工作模型。它不提供任何块的真实 gamma，也不提供某个固定 yaw 目标的 s_l，更不能把跨块最大值当每块下界。当前 Rbar 是条件上界，P 是工作先验，精确矩、中心化及总误差前提尚未成立。因此本轮不计算“假设 gamma”收益曲线，不添加接受事件。

负反例可在上界集合中通过饱和上界构造；正侧保证不能未经证明地从精确矩模型升级到未知真实边缘矩或非零偏差模型。这两种逻辑用途分开。

## 3. 如何从生成链得到 C，而不是猜 C

在同一 I 下，把可追踪的共同原始误差与校准参数组成 xi：包括接收机每个物理 epoch/signal 的码/相位误差、广播几何/时钟、anchor、设备时钟及安装、SDK 内部估计或关节模型等。只有实际共享的身份才共用同一分量；同名字段不能证明共享，不同消息也不能证明独立。

一个候选线性来源模型为

    e = E xi + eta_e,
    d = N xi + eta_d,
    Omega = Cov(xi | I).

完整 cross 为

    C = E Omega N^T
        + E Cov(xi,eta_d | I)
        + Cov(eta_e,xi | I) N^T
        + Cov(eta_e,eta_d | I).

只有对后三项分别有依据，才能删除它们；仅写“独立残差”不是证明。P、R 同样必须包含对应的全部 cross 项。共同偏差可以作为有资格的 nuisance 保留；完全未知偏差不能靠中心化标签消掉。

对同弧相位差，来源系数必须按真实关系矩阵形成 N=F1 N1-F0 N0，保留两端几何、pivot、信号/弧身份及重复来源。状态端则需从实际初始化、传播和更新累积 E；例如在 r=H e+d、e+=e-Kr 的约定下，E+=(I-KH)E- K N，之后继续乘实际误差反馈/reset 的雅可比。不能在读出 P6 时凭空生成 E。

现有 `arc_phase_information.py:284–309` 已有 SUPPLIED_CROSS 的完整 joint PSD、innovation 和 Joseph 检查。它是将来可复用的工作数值入口，但输入来源与物理误差资格由调用方承担。现在缺的是有根据的 E/N/Omega 和剩余误差合同，不需要再造一个默认 C=0 的入口。仅 joint PSD 通过不能说明提供的 C 是真实或保守有效的。

## 4. 当前来源事实与不能通过改调度消除的共享

本表为当前跟踪生成链的定向静态追踪；部分字段另外与既有小型运行 manifest 对照，没有重读全体真实输入或接收机内部软件。路径相对仓库根目录。

|来源层|代码支持的事实|对 cross 的实际含义|
|---|---|---|
|当前直接方向|`src/legsa_gins/paper_rebuild/protocol_v3/providers.py:225–240`用两机原始文件解码的HPPOSECEF共同iTOW构造R5；`hext/t5a_provider.py:239–258`结合两机NAV-PVT carrSoln门；V3仅覆盖GNSS18 yaw/valid|直接航向不是旧status A1；通道名pvt_priority_control也不表示独立原始源。两机内部原始测量/历史权重未知，不能从输出STD恢复其与RAWX相位的cross。|
|速度辅助中的历史航向|`src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py:175–192`用旧A1插值、SDK RP旋转SDK速度；`protocol_v3/providers.py:118–186`明确HV未重生|当前R5与HV内嵌旧A1必须分开追踪。新ready资格不会删除旧A1的误差或把它变成独立来源。|
|PVT/位置/Doppler|`src/legsa_gins/input_generation/process_data_compat.py:247–316`及`paper_rebuild/clean5_sequence/provider_chain.py:228`分别追到GNSS1 status、NAV-PVT、RAWX/SFRBX；`cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:1163,1248,1321`保留RAW_ROW_ID_UNKNOWN|已知设备/文件共享，不等于已知内部原始观测影响矩阵；缺失的影响矩阵不能由P6或单条STD唯一反演。|
|IMU原始流与SDK RP|`src/legsa_gins/input_generation/imu_txt_builder.py:95`从Go2状态流读取gyro/acc；RP取SDK姿态字段|共同消息流可追溯，但SDK姿态/速度生成与IMU的统计依赖未闭合，不能把它们默认独立。|
|IMU标定参数|`src/legsa_gins/paper_rebuild/clean5_calibrated/calibration.py:113–145`以A1/RP旋转的IMU增量与PVT速度差构造标定残差；174–188生成噪声参数；同目录`providers.py:47–79,82–97`保持gyro/time、应用固定scale并限定一次BY2标定|这是共享参数/开发数据来源，不能误写为每行IMU直接注入GNSS。H/O继承BY2模型；固定参数条件与参数估计不确定性须明确分开。|
|相位/anchor/广播源|`scripts/paper_rebuild/carrier_phase/real_trial.py:319–348`用RX1 code SPP生成或保持anchor；`src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_backend.py:41`及`carrier_phase/multignss.py:276–301`将码时标、星历/钟差和anchor用于几何与相位修正|默认Q仅传播报告相位STD及DD pivot关系。anchor、星历/钟差、安装/时间的总误差及其共享项尚未入模。|

表内简写 `hext/`、`carrier_phase/`、`protocol_v3/` 均在 `src/legsa_gins/paper_rebuild/` 下。

执行时序提供了另一条明确边：`gi_engine.cpp:478–537`处理已有位置/航向/速度/Doppler/HV/RP更新，770–788行反馈后才处理ARC；`gi_engine_arc_clone.cpp:136–150`在START克隆已条件化状态，163–175行在END读取完整joint先验。期间普通更新继续作用于joint状态。因此仅把END相位移到当前GNSS更新前，至多去掉当次更新的直接影响，不能撤销START和区间历史、持有anchor或共享参数。

来源审查曾沿基础生成链作出“direct yaw仍为旧A1”的中间猜测，继续查到V3覆盖逻辑后已否定；该猜测没有用于任何数值计算或最终模型。最终身份以上述R5与HV旧A1分离为准。

## 5. 下一项真实计算的进入条件

先闭合一个明确版本的源模型：准确指出进入初始化和每次更新的 GNSS/heading/SDK 测量来源、共同校准、两相位端点/anchor 的来源与物理时钟。选择同一条件信息集，说明每个已知 cross、剩余 cross 上界和偏差/余项的依据，以及其适用的固定目标。没有资格的字段保持 UNKNOWN。

若接收机输出的内部误差映射不可取得，不能从 PVT 的 STD、P6 或经验残差唯一恢复 state–phase cross。此时应明确选择：取得可验证的独立辅助来源，或为新研究臂使用原始观测联合建模并与同来源空相位控制匹配；两者都要重新规定初始化/校准与误差模型。单独改 END 更新顺序不解决旧端点、初始方位、共享校准或未知传感器内部融合。

只有源模型使既定目标出现可解释的增量，并通过原有故障准入/撤销条件，才进入 R4 的同后端联合收益试验。当前未满足；本轮没有降低 R、改变窗口或用假定 gamma 触发融合。

数学复核：root 推导固定目标构造，heading_evidence 独立核对奇异 P 的 range、Gaussian 反例、正侧固定增益及适用边界。最终§2–3文档独立复核PASS。均为代数审查，无数值测试。
